import asyncio
from datetime import datetime
import json
import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.models import Novel, Chapter, Glossary
from app.services.crawler.engine import scrape_chapter_content
from app.services.cleaner.pipeline import clean_raw_chinese_text, clean_translated_vietnamese_text
from app.services.translator.client import TranslatorClient
from app.services.translator.pipeline import TranslationPipeline
from app.services.translator.text_processor import extract_novel_entities
from app.services.translator.memory import (
    build_glossary_prompt,
    get_previous_chapters_context,
    create_system_instruction,
)
from app.services.exporter.packager import NovelPackager
from app.services.crawler.playwright_manager import playwright_manager

logger = logging.getLogger(__name__)

class TranslationJobManager:
    """
    Singleton-style manager that coordinates async crawling & translation jobs,
    tracks status, handles pause/resume, and broadcasts updates via SSE.
    """
    
    def __init__(self):
        self.is_running = False
        self.novel_id: Optional[int] = None
        self.novel_title: str = ""
        self.current_chapter_no: int = 0
        self.stage = "idle"  # idle, crawling, translating, packaging, completed, paused, failed
        self.logs: List[Dict[str, Any]] = []
        self.subscribers: List[asyncio.Queue] = []
        
        # Job settings
        self.provider = ""
        self.model = ""
        self.api_keys = ""
        self.custom_prompt = ""
        self.delay = 0.1  # delay giữa các chương (được điều chỉnh tự động)
        self.concurrency = 15  # số luồng song song tối ưu cho OpenRouter
        self.start_chapter: Optional[int] = None
        self.end_chapter: Optional[int] = None
        
        # Async tasks & Sync tools
        self._worker_tasks: List[asyncio.Task] = []
        self._db_lock = asyncio.Lock()
        self._packaging_triggered = False
        self.consecutive_failures = 0
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Adaptive rate limiting
        self._adaptive_delay = 0.2  # Bắt đầu với delay thấp nhất có thể
        self._min_delay = 0.05      # Tốc độ tối đa (50ms giữa các chương)
        self._max_delay = 15.0      # Tốc độ tối thiểu khi bị rate limit
        self._success_streak = 0    # Số lần thành công liên tiếp
        
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {"time": timestamp, "message": message, "level": level}
        self.logs.append(log_entry)
        # Limit log history
        if len(self.logs) > 500:
            self.logs.pop(0)
        self.broadcast("log", log_entry)

    def broadcast(self, event: str, data: Any):
        """Sends data payload to all connected SSE clients."""
        payload = {"event": event, "data": data}
        for queue in self.subscribers:
            queue.put_nowait(payload)

    async def get_progress(self, db: AsyncSession) -> Dict[str, Any]:
        """Calculates novel statistics to send to UI."""
        if not self.novel_id:
            return {"isRunning": False, "stage": "idle"}
            
        # Count total, completed, and failed chapters
        stmt_total = select(Chapter).where(Chapter.novel_id == self.novel_id)
        result_total = await db.execute(stmt_total)
        total_ch = len(result_total.scalars().all())
        
        stmt_comp = select(Chapter).where(Chapter.novel_id == self.novel_id, Chapter.status == "COMPLETED")
        result_comp = await db.execute(stmt_comp)
        comp_ch = len(result_comp.scalars().all())
        
        stmt_fail = select(Chapter).where(Chapter.novel_id == self.novel_id, Chapter.status == "FAILED")
        result_fail = await db.execute(stmt_fail)
        fail_ch = len(result_fail.scalars().all())
        
        return {
            "isRunning": self.is_running,
            "novelId": self.novel_id,
            "novelTitle": self.novel_title,
            "stage": self.stage,
            "totalChapters": total_ch,
            "completedChapters": comp_ch,
            "failedChapters": fail_ch,
            "currentChapterNo": self.current_chapter_no
        }

    async def start_job(self, novel_id: int, config: Dict[str, Any]):
        """Starts background translation tasks (multi-worker configuration)."""
        if self.is_running:
            raise Exception("Another job is already running.")
            
        self.novel_id = novel_id
        self.provider = config.get("provider", "gemini")
        self.model = config.get("model", "")
        self.api_keys = config.get("api_key", "")
        self.custom_prompt = config.get("prompt", "")
        self.delay = float(config.get("delay", 0.1))
        self.concurrency = max(int(config.get("concurrency", 3)), 1)
        self.start_chapter = config.get("start_chapter")
        self.end_chapter = config.get("end_chapter")
        
        self.is_running = True
        self.stage = "running"
        self.logs.clear()
        self._packaging_triggered = False
        self.consecutive_failures = 0
        # Tăng max_connections lên 100 để đáp ứng 15+ luồng song song
        self.http_client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(connect=10.0, read=55.0, write=15.0, pool=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=40),
        )
        
        async with async_session() as db:
            novel = await db.get(Novel, novel_id)
            self.novel_title = novel.title if novel else "Unknown Novel"
            
            # Revert any chapters left in CRAWLING or TRANSLATING status back to PENDING so they aren't stuck
            await db.execute(
                update(Chapter)
                .where(Chapter.novel_id == novel_id)
                .where(Chapter.status.in_(["CRAWLING", "TRANSLATING"]))
                .values(status="PENDING")
            )
            await db.commit()
            
        self.add_log(f"🚀 Khởi chạy tiến trình dịch: {self.novel_title} (Số luồng song song: {self.concurrency})")
        self._worker_tasks = [
            asyncio.create_task(self._run_job()) for _ in range(self.concurrency)
        ]

    async def pause_job(self):
        """Pauses all active worker tasks."""
        if not self.is_running:
            return
        self.is_running = False
        self.stage = "paused"
        self.add_log("⏸️ Tiến trình được tạm dừng bởi người dùng.", "warning")
        
        if self._worker_tasks:
            for task in self._worker_tasks:
                task.cancel()
            for task in self._worker_tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._worker_tasks.clear()
            
        if self.http_client:
            try:
                await self.http_client.aclose()
            except Exception:
                pass
            self.http_client = None
            
        async with async_session() as db:
            progress = await self.get_progress(db)
            self.broadcast("progress", progress)

    async def clear_job(self):
        """Resets the job manager state."""
        await self.pause_job()
        self.novel_id = None
        self.novel_title = ""
        self.current_chapter_no = 0
        self.stage = "idle"
        self.logs.clear()

    async def _run_job(self):
        """Concurrent translation worker."""
        client = None
        try:
            client = TranslatorClient(
                self.provider,
                self.model,
                self.api_keys,
                concurrency=self.concurrency,
                http_client=self.http_client
            )
        except Exception as e:
            self.is_running = False
            self.stage = "failed"
            self.add_log(f"❌ Khởi tạo AI Client thất bại: {e}", "danger")
            return

        while self.is_running:
            chapter = None
            chapter_id = None
            should_sleep = False  # sleep NGOÀI lock để tránh giữ lock khi idle
            should_wait_active = False  # đang chờ worker khác xử lý xong
            _wait_active_since = getattr(self, '_wait_active_since', None)
            
            # Acquire DB lock to query and reserve the next chapter safely
            async with self._db_lock:
                async with async_session() as db:
                    # Fetch next uncompleted chapter (either PENDING or FAILED)
                    stmt = (
                        select(Chapter)
                        .where(Chapter.novel_id == self.novel_id)
                        .where(Chapter.status.in_(["PENDING", "FAILED"]))
                    )
                    if self.start_chapter is not None:
                        stmt = stmt.where(Chapter.chapter_no >= self.start_chapter)
                    if self.end_chapter is not None:
                        stmt = stmt.where(Chapter.chapter_no <= self.end_chapter)
                    stmt = stmt.order_by(Chapter.chapter_no.asc()).limit(1)
                    result = await db.execute(stmt)
                    chapter = result.scalar_one_or_none()
                    
                    if not chapter:
                        # No pending chapters. Check if other workers are still processing active chapters.
                        stmt_active = (
                            select(Chapter)
                            .where(Chapter.novel_id == self.novel_id)
                            .where(Chapter.status.in_(["CRAWLING", "TRANSLATING"]))
                        )
                        result_active = await db.execute(stmt_active)
                        active_chapters = result_active.scalars().all()
                        
                        if not active_chapters:
                            # No pending, failed, or active chapters -> All chapters completed!
                            if not self._packaging_triggered:
                                self._packaging_triggered = True
                                self.stage = "packaging"
                                self.add_log("📦 Tất cả các chương đã dịch xong. Đang tiến hành đóng gói sách...")
                                
                                try:
                                    packager = NovelPackager(output_dir="output")
                                    pkg_res = await packager.package_novel(db, self.novel_id)
                                    self.add_log("🎉 Đóng gói thành công! Bản dịch đã sẵn sàng tải xuống.", "success")
                                    self.broadcast("packaged", pkg_res)
                                except Exception as e:
                                    self.add_log(f"⚠️ Đóng gói thất bại: {e}", "danger")
                                    
                                self.is_running = False
                                self.stage = "completed"
                                progress = await self.get_progress(db)
                                self.broadcast("progress", progress)
                                
                                if self.http_client:
                                    try:
                                        await self.http_client.aclose()
                                    except Exception:
                                        pass
                                    self.http_client = None
                                    
                            break
                        else:
                            # Còn worker khác đang xử lý → chờ bên ngoài lock
                            should_wait_active = True
                    else:
                        # Atomic check-and-set: chỉ reserve nếu status vẫn còn PENDING/FAILED
                        # Dùng UPDATE ... WHERE status IN (...) để tránh race condition giữa các worker
                        target_status = "TRANSLATING" if chapter.raw_text else "CRAWLING"
                        reserve_result = await db.execute(
                            update(Chapter)
                            .where(Chapter.id == chapter.id)
                            .where(Chapter.status.in_(["PENDING", "FAILED"]))
                            .values(status=target_status)
                        )
                        await db.commit()
                        
                        if reserve_result.rowcount == 0:
                            # Một worker khác đã reserve chapter này trước — thử lại sau
                            chapter = None
                            should_sleep = True
                        else:
                            # Fetch essential variables to process outside the lock
                            chapter_id = chapter.id
                            chapter_no = chapter.chapter_no
                            chapter_title = chapter.title
                            chapter_source_url = chapter.source_url
                            chapter_raw_text = chapter.raw_text
                            self.current_chapter_no = chapter_no
            
            # Xử lý ngoài lock để không block worker khác
            if should_wait_active:
                import time as _time
                now = _time.monotonic()
                if _wait_active_since is None:
                    self._wait_active_since = now
                elif now - _wait_active_since > 300:  # 5 phút bị stuck
                    # Rescue: reset các chương stuck về PENDING
                    self.add_log("⚠️ Phát hiện chương bị kẹt (stuck >5phút). Đang reset về PENDING...", "warning")
                    async with async_session() as db:
                        await db.execute(
                            update(Chapter)
                            .where(Chapter.novel_id == self.novel_id)
                            .where(Chapter.status.in_(["CRAWLING", "TRANSLATING"]))
                            .values(status="PENDING", error_msg="Auto-reset: stuck quá 5 phút")
                        )
                        await db.commit()
                    self._wait_active_since = None
                # Chờ dài hơn khi không có chương nào để làm — tránh busy-wait
                await asyncio.sleep(1.0)
                continue
            else:
                # Reset bộ đếm khi có việc làm
                self._wait_active_since = None
            
            if should_sleep or not chapter:
                # Race condition: bị worker khác cướp mất — retry nhanh
                await asyncio.sleep(0.2)
                continue


            try:
                # Fetch glossary settings (global and novel specific)
                async with async_session() as db:
                    stmt_glossary = (
                        select(Glossary)
                        .where((Glossary.novel_id == self.novel_id) | (Glossary.novel_id == None))
                    )
                    result_g = await db.execute(stmt_glossary)
                    glossaries = list(result_g.scalars().all())

                # 2. Scrape chapter content if not already scraped
                raw_text = chapter_raw_text
                if not raw_text:
                    self.add_log(f"📥 Đang cào: Chương {chapter_no} - {chapter_title}")
                    try:
                        raw_text_scraped = await scrape_chapter_content(chapter_source_url)
                        raw_text = clean_raw_chinese_text(raw_text_scraped)
                        
                        async with async_session() as db:
                            await db.execute(
                                update(Chapter)
                                .where(Chapter.id == chapter_id)
                                .values(raw_text=raw_text, status="TRANSLATING")
                            )
                            await db.commit()
                    except Exception as e:
                        self.consecutive_failures += 1
                        self.add_log(f"⚠️ Cào chương {chapter_no} thất bại: {str(e)}", "danger")
                        async with async_session() as db:
                            await db.execute(
                                update(Chapter)
                                .where(Chapter.id == chapter_id)
                                .values(status="FAILED", error_msg=f"Lỗi cào: {str(e)}")
                            )
                            await db.commit()
                        
                        if self.consecutive_failures >= 5:
                            self.is_running = False
                            self.stage = "failed"
                            self.add_log("❌ Dừng tiến trình do gặp 5 lỗi cào/dịch liên tiếp.", "danger")
                            for task in self._worker_tasks:
                                if task != asyncio.current_task():
                                    task.cancel()
                            break
                        
                        await asyncio.sleep(self.delay)
                        continue

                # 3. Translate Chapter
                self.add_log(f"🤖 Đang dịch (Luồng song song): Chương {chapter_no} - {chapter_title}")
                try:
                    # Run the translation pipeline
                    async with async_session() as db:
                        pipeline = TranslationPipeline(client, db, http_client=self.http_client)
                        translated_cleaned = await pipeline.translate_chapter(
                            raw_chinese=raw_text,
                            glossaries=glossaries,
                            custom_prompt=self.custom_prompt,
                            bypass_cache=True,
                            novel_title=self.novel_title
                        )
                        
                        await db.execute(
                            update(Chapter)
                            .where(Chapter.id == chapter_id)
                            .values(
                                translated_text=translated_cleaned,
                                status="COMPLETED",
                                token_count=0,
                                error_msg=None
                            )
                        )
                        await db.commit()

                        # Tự động trích xuất Tên riêng mới từ chương vừa dịch và lưu vào DB Glossary cho bộ truyện này
                        try:
                            extracted_terms = await extract_novel_entities(raw_text, translated_cleaned, client)
                            if extracted_terms:
                                added_count = 0
                                for term in extracted_terms:
                                    zh = term["chinese_term"]
                                    vi = term["vietnamese_term"]
                                    cat = term.get("category", "NAME")
                                    
                                    stmt = select(Glossary).where(
                                        (Glossary.novel_id == self.novel_id) | (Glossary.novel_id == None),
                                        Glossary.chinese_term == zh
                                    )
                                    res_g = await db.execute(stmt)
                                    if not res_g.scalar_one_or_none():
                                        new_g = Glossary(
                                            novel_id=self.novel_id,
                                            chinese_term=zh,
                                            vietnamese_term=vi,
                                            category=cat
                                        )
                                        db.add(new_g)
                                        added_count += 1
                                if added_count > 0:
                                    await db.commit()
                                    self.add_log(f"🏷️ Tự động ghi nhớ {added_count} tên riêng mới vào Từ điển của bộ truyện!")
                        except Exception as ext_err:
                            logger.warning(f"Failed to auto extract entities for chapter {chapter_no}: {ext_err}")
                    
                    self.add_log(f"✅ Dịch xong: Chương {chapter_no}")
                    self.consecutive_failures = 0
                    self._success_streak += 1
                    
                    # Adaptive speedup: giảm delay sau mỗi 2 lần thành công liên tiếp
                    if self._success_streak >= 2 and self._adaptive_delay > self._min_delay:
                        self._adaptive_delay = max(self._min_delay, self._adaptive_delay * 0.6)
                        logger.info(f"⚡ Adaptive speedup: delay giảm xuống {self._adaptive_delay:.3f}s")
                    
                    # Auto-save chapter to folder
                    try:
                        invalid_chars = '<>:"/\\|?*\r\n\t'
                        safe_novel_title = "".join(c for c in self.novel_title if c not in invalid_chars).strip()
                        safe_novel_title = safe_novel_title.replace("  ", " ")
                        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                        novel_folder = os.path.join(BASE_DIR, "output", safe_novel_title)
                        os.makedirs(novel_folder, exist_ok=True)
                        
                        ch_title = "".join(c for c in chapter_title if c not in invalid_chars).strip()
                        filename = f"Chương {chapter_no:04d} - {ch_title}.txt"
                        filepath = os.path.join(novel_folder, filename)
                        
                        from app.services.exporter.packager import strip_html_tags
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(f"{chapter_title}\n")
                            f.write("=" * 40 + "\n\n")
                            f.write(strip_html_tags(translated_cleaned))
                        
                        self.add_log(f"💾 Đã lưu: {filename}")
                    except Exception as save_err:
                        self.add_log(f"⚠️ Lưu file thất bại: {save_err}", "warning")
                    
                except Exception as e:
                    self.consecutive_failures += 1
                    self._success_streak = 0
                    # Adaptive slowdown khi gặp lỗi
                    self._adaptive_delay = min(self._max_delay, self._adaptive_delay * 1.5)
                    logger.info(f"🐢 Adaptive slowdown: delay tăng lên {self._adaptive_delay:.1f}s")
                    err_msg = str(e)
                    self.add_log(f"⚠️ Dịch chương {chapter_no} thất bại: {err_msg}", "danger")
                    async with async_session() as db:
                        await db.execute(
                            update(Chapter)
                            .where(Chapter.id == chapter_id)
                            .values(status="FAILED", error_msg=f"Lỗi dịch: {err_msg}")
                        )
                        await db.commit()
                    
                    # Stop immediately if key is exhausted, rate limited, or invalid
                    err_lower = err_msg.lower()
                    is_api_exhausted = (
                        "429" in err_lower or 
                        "402" in err_lower or 
                        "credit" in err_lower or 
                        "insufficient" in err_lower or 
                        "quota" in err_lower or 
                        "exhausted" in err_lower or 
                        "limit" in err_lower or 
                        "api key" in err_lower or 
                        "unauthenticated" in err_lower or 
                        "invalid" in err_lower
                    )
                    
                    if is_api_exhausted:
                        self.is_running = False
                        self.stage = "failed"
                        self.add_log("❌ Dừng tiến trình ngay lập tức vì API Key đã hết hạn mức (Quota/Rate Limit) hoặc không hợp lệ.", "danger")
                        for task in self._worker_tasks:
                            if task != asyncio.current_task():
                                task.cancel()
                        break
                    
                    if self.consecutive_failures >= 5:
                        self.is_running = False
                        self.stage = "failed"
                        self.add_log("❌ Dừng tiến trình do gặp 5 lỗi cào/dịch liên tiếp.", "danger")
                        for task in self._worker_tasks:
                            if task != asyncio.current_task():
                                task.cancel()
                        break
                        
                # Update UI progress
                async with async_session() as db:
                    progress = await self.get_progress(db)
                    self.broadcast("progress", progress)
                    
                # Adaptive inter-chapter delay
                actual_delay = max(self._adaptive_delay, self.delay)
                await asyncio.sleep(actual_delay)

            except asyncio.CancelledError:
                # Revert chapter status to PENDING so it can be picked up when resumed
                self.add_log(f"🛑 Bị hủy trong lúc xử lý chương {chapter_no}", "warning")
                import random
                for retry in range(5):
                    try:
                        async with async_session() as db:
                            await db.execute(
                                update(Chapter)
                                .where(Chapter.id == chapter_id)
                                .values(status="PENDING", error_msg="Bị hủy do tạm dừng")
                            )
                            await db.commit()
                        break
                    except Exception as e:
                        if "locked" in str(e).lower() and retry < 4:
                            # Random jittered sleep to let other concurrent transactions finish
                            await asyncio.sleep(0.15 * (retry + 1) + random.random() * 0.1)
                        else:
                            logger.error(f"Revert status for chapter {chapter_no} failed: {e}")
                            break
                raise

# Singleton manager
job_manager = TranslationJobManager()

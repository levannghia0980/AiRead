import os
import gc
import logging
from typing import Dict, Any, Optional
from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion
from app.services.preprocessing.crawler.engine import scrape_novel_metadata, scrape_chapter_content
from app.services.preprocessing.crawler.google_translator import translate_text_best_quality
from app.services.storage.file_storage import (
    save_chapter_version_file, 
    delete_novel_disk_files, 
    delete_version_disk_files
)

logger = logging.getLogger(__name__)

async def process_novel_link(novel_url: str) -> Dict[str, Any]:
    """
    Cào link truyện (Mục Lục) -> Dịch nhanh tiêu đề truyện bằng Google Translate -> Lưu DB (status = 'WAIT').
    """
    logger.info(f"🕷️ Đang cào mục lục bộ truyện từ URL: {novel_url}")
    data = await scrape_novel_metadata(novel_url)
    
    title_raw = data.get("title", "Unknown Novel")
    # Chỉ dịch duy nhất tên truyện bằng Google Translate để tránh lag
    from app.services.preprocessing.crawler.google_translator import translate_text_best_quality
    title_rough = await translate_text_best_quality(title_raw)
    
    author = data.get("author", "Unknown Author")
    cover_url = data.get("cover_url", "")
    genres = data.get("genres", "")
    status = data.get("status", "Ongoing")
    chapters_data = data.get("chapters", [])

    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.source_url == novel_url)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()

        if not novel:
            novel = Novel(
                title_raw=title_raw,
                title_rough=title_rough,
                author=author,
                cover_url=cover_url,
                genres=genres or "XIANXIA",
                context_profile=(genres or "XIANXIA").lower(),
                status=status,
                source_url=novel_url
            )
            session.add(novel)
            await session.flush()
        else:
            novel.title_rough = title_rough
            novel.author = author
            novel.cover_url = cover_url

        added_count = 0
        for ch_info in chapters_data:
            ch_no = ch_info["chapter_no"]
            ch_title_raw = ch_info["title"]
            # Làm sạch tiêu đề chương khỏi lỗi "KHÔNG.Xchương", "NO.Xchương", "第X章" của dịch máy
            import re
            ch_title_raw = re.sub(r'(?i)(?:KHÔNG|NO)\s*\.?\s*(\d+)\s*(?:chương|Chương|章)?\s*[:.:-]?\s*', r'Chương \1: ', ch_title_raw)
            ch_title_raw = re.sub(r'第\s*(\d+)\s*章\s*[:.:-]?\s*', r'Chương \1: ', ch_title_raw)
            ch_title_raw = re.sub(r':\s*:', r':', ch_title_raw).strip()
            
            # Không dịch Hán Việt tiêu đề chương để chống lag cho hàng ngàn chương
            ch_title_rough = ch_title_raw
            ch_url = ch_info["url"]

            stmt_ch = select(Chapter).where(Chapter.novel_id == novel.id, Chapter.chapter_no == ch_no)
            ch_res = await session.execute(stmt_ch)
            existing_ch = ch_res.scalar_one_or_none()

            if not existing_ch:
                new_ch = Chapter(
                    novel_id=novel.id,
                    chapter_no=ch_no,
                    title_raw=ch_title_raw,
                    title_rough=ch_title_rough,
                    url=ch_url,
                    status="WAIT"
                )
                session.add(new_ch)
                added_count += 1

        await session.commit()
        novel_id = novel.id

    logger.info(f"✅ Đã khởi tạo bộ truyện ID {novel_id} ('{title_rough}') với {added_count} chương mới trong DB.")
    
    del data
    del chapters_data
    gc.collect()

    return {
        "novel_id": novel_id,
        "title_raw": title_raw,
        "title_rough": title_rough,
        "author": author,
        "cover_url": cover_url,
        "genres": genres,
        "status": status,
        "total_chapters": added_count
    }

async def process_single_chapter_crawl(chapter_id: int, skip_gg: bool = True) -> Dict[str, Any]:
    """
    Xử lý cào 1 chương đơn lẻ (chỉ lưu bản gốc RAW tiếng Trung vào Output/01_BanGoc).
    """
    logger.info(f"Bắt đầu cào chương ID: {chapter_id}")
    
    async with AsyncSessionLocal() as session:
        stmt = select(Chapter, Novel).join(Novel, Chapter.novel_id == Novel.id).where(Chapter.id == chapter_id)
        res = await session.execute(stmt)
        row = res.first()
        if not row:
            raise Exception(f"Không tìm thấy chapter_id: {chapter_id}")
        chapter, novel = row
        
        ch_no = chapter.chapter_no
        ch_title_raw = chapter.title_raw
        ch_title_rough = chapter.title_rough
        ch_url = chapter.url
        
        novel_title_raw = novel.title_raw
        novel_title_rough = novel.title_rough or novel_title_raw
        chapter.status = "CRAWLING"
        await session.commit()

    try:
        # 1. Kiểm tra xem đã có sẵn file RAW trong thư mục 01_BanGoc chưa (đặc biệt hữu ích cho Fanqie khi nạp full 1 lần)
        from app.services.storage.file_storage import get_version_dir
        expected_raw_dir = get_version_dir("RAW", novel_title_rough or novel_title_raw)
        expected_raw_file = expected_raw_dir / f"{ch_no:06d}.txt"

        raw_content = ""
        if expected_raw_file.exists() and expected_raw_file.stat().st_size > 100:
            try:
                with open(expected_raw_file, "r", encoding="utf-8", errors="ignore") as f:
                    raw_content = f.read()
                logger.info(f"⚡ [TẬN DỤNG BẢN GỐC CÓ SẴN] Chương {ch_no} đã có sẵn trong 01_BanGoc ({len(raw_content)} ký tự), bỏ qua cào mạng!")
            except Exception as read_err:
                logger.warning(f"Không thể đọc file RAW có sẵn của chương {ch_no}: {read_err}")
                raw_content = ""

        # ĐẶC BIỆT: Truyện upload bằng file TXT (URL = local://) — đọc từ DB thay vì cào web
        if not raw_content and ch_url and ch_url.startswith("local://"):
            async with AsyncSessionLocal() as session:
                stmt_v_raw = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == chapter_id,
                    ChapterVersion.version_type == "RAW"
                )
                res_v_raw = await session.execute(stmt_v_raw)
                v_raw_db = res_v_raw.scalar_one_or_none()
                if v_raw_db:
                    # Thử đọc từ file_path trong DB
                    if v_raw_db.file_path and os.path.exists(v_raw_db.file_path) and os.path.getsize(v_raw_db.file_path) > 100:
                        try:
                            with open(v_raw_db.file_path, "r", encoding="utf-8", errors="ignore") as f:
                                raw_content = f.read()
                            logger.info(f"🛡️ [LOCAL-FILE] Chương {ch_no} đọc RAW từ DB file_path ({len(raw_content)} ký tự)")
                        except Exception:
                            pass
                    # Thử đọc từ content trong DB
                    if not raw_content and v_raw_db.content and len(v_raw_db.content.strip()) > 50:
                        raw_content = v_raw_db.content
                        logger.info(f"🛡️ [LOCAL-DB] Chương {ch_no} đọc RAW từ DB content ({len(raw_content)} ký tự)")

            if not raw_content:
                raise Exception(
                    f"Truyện upload bằng TXT: Không tìm thấy bản gốc (RAW) cho Chương {ch_no} trong DB hoặc file đĩa. "
                    f"Vui lòng upload lại file TXT gốc hoặc khôi phục file 01_BanGoc/{ch_no:06d}.txt"
                )

        if not raw_content:
            raw_content = await scrape_chapter_content(ch_url)

        file_path_raw = save_chapter_version_file(
            version_type="RAW",
            novel_title_raw=novel_title_raw,
            novel_title_rough=novel_title_rough,
            chapter_no=ch_no,
            chapter_title_raw=ch_title_raw,
            chapter_title_rough=ch_title_rough,
            content_text=raw_content
        )

        # 2. Ghi DB
        async with AsyncSessionLocal() as session:
            # Ghi nhận bản RAW
            stmt_v_raw = select(ChapterVersion).where(
                ChapterVersion.chapter_id == chapter_id, 
                ChapterVersion.version_type == "RAW"
            )
            v_res_raw = await session.execute(stmt_v_raw)
            ver_raw = v_res_raw.scalar_one_or_none()

            if not ver_raw:
                ver_raw = ChapterVersion(
                    chapter_id=chapter_id,
                    version_type="RAW",
                    engine="crawler",
                    file_path=file_path_raw,
                    status="COMPLETED"
                )
                session.add(ver_raw)
            else:
                ver_raw.file_path = file_path_raw
                ver_raw.status = "COMPLETED"

            # Cập nhật trạng thái chapter
            stmt_ch = select(Chapter).where(Chapter.id == chapter_id)
            ch_res = await session.execute(stmt_ch)
            ch = ch_res.scalar_one_or_none()
            if ch:
                ch.status = "CRAWLED"
                ch.error_message = ""

            await session.commit()

        # Giải phóng RAM
        del raw_content
        gc.collect()

        return {
            "chapter_id": chapter_id,
            "chapter_no": ch_no,
            "raw_path": file_path_raw,
            "status": "CRAWLED"
        }
    except Exception as e:
        async with AsyncSessionLocal() as session:
            stmt = select(Chapter).where(Chapter.id == chapter_id)
            res = await session.execute(stmt)
            ch = res.scalar_one_or_none()
            if ch:
                ch.status = "FAILED"
                ch.error_message = str(e)
                await session.commit()
        raise e

async def delete_novel_completely(novel_id: int) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()

        if not novel:
            return {
                "novel_id": novel_id,
                "title_rough": "",
                "message": f"Bộ truyện ID {novel_id} đã được xóa trước đó hoặc không tồn tại."
            }

        novel_title_rough = novel.title_rough or novel.title_raw

        await session.delete(novel)
        await session.commit()

    delete_novel_disk_files(novel_title_rough)

    return {
        "novel_id": novel_id,
        "title_rough": novel_title_rough,
        "message": "Đã xóa sạch bộ truyện khỏi Database và đĩa cứng."
    }

async def delete_novel_version(novel_id: int, version_type: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()

        if not novel:
            raise Exception(f"Không tìm thấy bộ truyện ID {novel_id}")

        novel_title_rough = novel.title_rough or novel.title_raw

        stmt_ch_ids = select(Chapter.id).where(Chapter.novel_id == novel_id)
        ch_ids_res = await session.execute(stmt_ch_ids)
        ch_ids = ch_ids_res.scalars().all()

        if ch_ids:
            v_types = [version_type.upper()]
            if version_type.upper() == "FINAL":
                v_types.extend(["LLM", "TTS_TEXT", "AUDIO"])
            stmt_del = delete(ChapterVersion).where(
                ChapterVersion.chapter_id.in_(ch_ids),
                ChapterVersion.version_type.in_(v_types)
            )
            await session.execute(stmt_del)
            await session.commit()

    delete_version_disk_files(version_type, novel_title_rough)
    if version_type.upper() == "FINAL":
        delete_version_disk_files("LLM", novel_title_rough)
        delete_version_disk_files("TTS_TEXT", novel_title_rough)
        delete_version_disk_files("AUDIO", novel_title_rough)

    return {
        "novel_id": novel_id,
        "version_type": version_type.upper(),
        "message": f"Đã xóa sạch phiên bản '{version_type.upper()}' của bộ truyện để sẵn sàng dịch lại."
    }

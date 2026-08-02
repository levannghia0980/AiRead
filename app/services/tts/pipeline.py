import os
import re
import time
import asyncio
import subprocess
import psutil
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion, TTSChunk
from app.services.storage.file_storage import sanitize_filename

# Bản đồ ánh xạ cấu hình giọng đọc của Edge-TTS sang tên giọng nói thực tế
VOICE_MAP = {
    "default": "vi-VN-HoaiMyNeural",
    "female": "vi-VN-HoaiMyNeural",
    "nu": "vi-VN-HoaiMyNeural",
    "male": "vi-VN-NamMinhNeural",
    "nam": "vi-VN-NamMinhNeural"
}

# Theo dõi các tác vụ TTS đang chạy trực tiếp trên bộ nhớ để thăm dò trạng thái
ACTIVE_TTS_JOBS: Dict[str, Dict[str, Any]] = {}

def get_voice_name(profile_name: str) -> str:
    p = profile_name.lower().strip()
    return VOICE_MAP.get(p, p)

def get_audio_duration_ffmpeg(file_path: str) -> str:
    """Sử dụng FFmpeg -i để trích xuất độ dài (duration) của file âm thanh"""
    if not os.path.exists(file_path):
        return "00:00:00"
    try:
        cmd = ["ffmpeg", "-i", file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        output = result.stderr
        match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2})", output)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[TTS-MERGER] Lỗi đọc duration tệp {file_path}: {e}")
    return "00:00:00"

def merge_audio_files(file_paths: List[str], output_path: str) -> bool:
    """Ghép nối danh sách các tệp mp3 bằng FFmpeg Concat Demuxer (-c copy)"""
    if not file_paths:
        return False
    
    list_file_path = output_path + ".txt"
    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for fp in file_paths:
                # Chuẩn hóa đường dẫn chứa dấu gạch chéo xuôi cho FFmpeg tương thích Windows
                normalized_path = fp.replace("\\", "/")
                f.write(f"file '{normalized_path}'\n")
        
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        return result.returncode == 0
    except Exception as e:
        print(f"[TTS-MERGER] Lỗi khi chạy lệnh ghép nối FFmpeg: {e}")
        return False
    finally:
        if os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
            except Exception:
                pass

def split_text_into_chunks(text: str, max_chars: int = 1200) -> List[str]:
    """Phân tách văn bản lớn thành các chunk câu từ 1000-1200 ký tự"""
    # Tách câu dựa trên ranh giới dấu câu kết câu và dấu xuống dòng
    sentences = re.split(r'(?<=[.!?\n])\s+', text)
    chunks = []
    current_chunk = []
    current_len = 0
    
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        s_len = len(s)
        
        if s_len > max_chars:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0
            
            # Nếu câu quá dài vượt quá max_chars, bẻ nhỏ theo ký tự
            start = 0
            while start < s_len:
                end = min(start + max_chars, s_len)
                chunks.append(s[start:end].strip())
                start = end
            continue
            
        if current_len + s_len + 1 > max_chars:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0
        current_chunk.append(s)
        current_len += s_len + 1
        
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

async def prepare_volume_chunks(novel_id: int, volume_no: int, chapters: List[Chapter]) -> int:
    """Nạp văn bản dịch của các chương và chia chunk lưu vào SQLite"""
    from app.services.storage.file_storage import read_version_file_content

    async with AsyncSessionLocal() as session:
        # Kiểm tra xem volume này đã được chia chunk từ trước chưa
        stmt_exist = select(TTSChunk.id).where(TTSChunk.novel_id == novel_id, TTSChunk.volume_no == volume_no)
        res_exist = await session.execute(stmt_exist)
        existing_chunks = res_exist.scalars().all()
        
        if existing_chunks:
            return len(existing_chunks)
            
        combined_text_list = []
        for ch in chapters:
            # Chỉ lấy duy nhất bản dịch hoàn chỉnh (FINAL) đã qua LLM và hậu xử lý
            stmt_ver = select(ChapterVersion).where(
                ChapterVersion.chapter_id == ch.id,
                ChapterVersion.version_type == "FINAL"
            )
            res_ver = await session.execute(stmt_ver)
            ver_final = res_ver.scalar_one_or_none()
            
            if not ver_final or not ver_final.file_path or not os.path.exists(ver_final.file_path):
                continue
                
            translated_text = read_version_file_content(ver_final.file_path)
            if not translated_text or not translated_text.strip():
                continue
                
            # Đọc kèm tiêu đề chương để phát âm
            ch_title = ch.title_rough if ch.title_rough else ch.title_raw
            chapter_header = f"Chương {ch.chapter_no}: {ch_title}.\n\n"
            combined_text_list.append(chapter_header + translated_text)
            
        if not combined_text_list:
            return 0
            
        full_text = "\n\n=== TIẾP THEO ===\n\n".join(combined_text_list)
        chunks = split_text_into_chunks(full_text)
        
        # Insert các chunk vào DB
        for idx, chunk_text in enumerate(chunks):
            session.add(TTSChunk(
                novel_id=novel_id,
                volume_no=volume_no,
                chunk_id=idx,
                text_content=chunk_text,
                status="PENDING",
                retry_count=0
            ))
        await session.commit()
        return len(chunks)

async def check_and_flush_batch(novel_id: int, volume_no: int, chunk_id: int, temp_dir: str):
    """Ghép lô batch-flush tự động khi 100 chunk liên tiếp có trạng thái DONE"""
    batch_no = chunk_id // 100
    start_chunk = batch_no * 100
    
    async with AsyncSessionLocal() as session:
        # Lấy tổng số lượng chunk của volume
        stmt_total = select(TTSChunk.chunk_id).where(TTSChunk.novel_id == novel_id, TTSChunk.volume_no == volume_no)
        res_total = await session.execute(stmt_total)
        total_chunks = len(res_total.scalars().all())
        
        end_chunk = min(start_chunk + 99, total_chunks - 1)
        expected_count = end_chunk - start_chunk + 1
        
        # Đếm số lượng chunk hoàn thành trong khoảng
        stmt_done = select(TTSChunk).where(
            TTSChunk.novel_id == novel_id,
            TTSChunk.volume_no == volume_no,
            TTSChunk.chunk_id >= start_chunk,
            TTSChunk.chunk_id <= end_chunk,
            TTSChunk.status == "DONE"
        )
        res_done = await session.execute(stmt_done)
        done_chunks = res_done.scalars().all()
        
        if len(done_chunks) == expected_count:
            # Đủ điều kiện gom tệp batch
            batch_output_path = os.path.join(temp_dir, f"batch_{batch_no:04d}.mp3")
            chunk_files = [os.path.join(temp_dir, f"chunk_{cid:05d}.mp3") for cid in range(start_chunk, end_chunk + 1)]
            
            # Chỉ tiến hành nếu toàn bộ file chunk tồn tại thực tế trên ổ đĩa
            if not all(os.path.exists(fp) for fp in chunk_files):
                return
                
            success = merge_audio_files(chunk_files, batch_output_path)
            if success:
                # Xóa các file chunk nhỏ
                for fp in chunk_files:
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
                # Cập nhật đường dẫn tệp batch mới trong DB
                for chunk in done_chunks:
                    chunk.audio_path = batch_output_path
                await session.commit()

async def tts_worker(queue: asyncio.Queue, novel_id: int, volume_no: int, voice: str, temp_dir: str, job_info: Dict[str, Any]):
    """Async Worker xử lý gọi Edge-TTS, lưu file mp3 tạm và cập nhật DB"""
    import edge_tts
    
    while True:
        try:
            chunk_id_db = await queue.get()
        except asyncio.CancelledError:
            break
            
        if chunk_id_db is None:
            queue.task_done()
            break
            
        async with AsyncSessionLocal() as session:
            stmt = select(TTSChunk).where(TTSChunk.id == chunk_id_db)
            res = await session.execute(stmt)
            chunk = res.scalar_one_or_none()
            if not chunk or chunk.status == "DONE":
                queue.task_done()
                continue
                
            # Đánh dấu PROCESSING tránh worker khác tranh giành
            chunk.status = "PROCESSING"
            await session.commit()
            
            chunk_id = chunk.chunk_id
            text = chunk.text_content
            
        temp_mp3_path = os.path.join(temp_dir, f"chunk_{chunk_id:05d}.mp3")
        success = False
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(temp_mp3_path)
            success = os.path.exists(temp_mp3_path) and os.path.getsize(temp_mp3_path) > 0
        except Exception as e:
            print(f"[TTS-WORKER] Thất bại sinh chunk {chunk_id}: {e}")
            
        async with AsyncSessionLocal() as session:
            stmt = select(TTSChunk).where(TTSChunk.id == chunk_id_db)
            res = await session.execute(stmt)
            chunk = res.scalar_one_or_none()
            if chunk:
                if success:
                    chunk.status = "DONE"
                    chunk.audio_path = temp_mp3_path
                    job_info["done_chunks"] += 1
                    job_info["recent_successes"] += 1
                else:
                    chunk.retry_count += 1
                    job_info["recent_failures"] += 1
                    if chunk.retry_count >= 3:
                        chunk.status = "FAILED"
                        job_info["failed_chunks"] += 1
                    else:
                        chunk.status = "PENDING"
                        # Đưa lại vào hàng đợi kèm backoff nhẹ tăng dần theo retry
                        async def re_add(cid_db=chunk_id_db, retries=chunk.retry_count):
                            await asyncio.sleep(2.0 * retries)
                            await queue.put(cid_db)
                        asyncio.create_task(re_add())
                await session.commit()
                
        if success:
            try:
                await check_and_flush_batch(novel_id, volume_no, chunk_id, temp_dir)
            except Exception as e:
                print(f"[TTS-WORKER] Lỗi ghép lô tự động: {e}")
                
        queue.task_done()

async def cleanup_tts_volume(novel_id: int, volume_no: int, temp_dir: str):
    """
    Dọn dẹp sạch sẽ dữ liệu của volume khi tiến trình bị hủy hoặc thất bại giữa chừng:
    - Xóa toàn bộ file tạm và thư mục tạm
    - Xóa các bản ghi tts_chunks trong SQLite để chạy lại từ đầu sạch sẽ
    """
    import shutil
    from sqlalchemy import delete
    
    print(f"[TTS-CLEANUP] Bắt đầu dọn dẹp cho novel_id={novel_id}, volume_no={volume_no}...")
    # 1. Xóa thư mục tạm chứa chunk/batch
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"  - Đã xóa thư mục tạm: {temp_dir}")
        except Exception as e:
            print(f"  - Lỗi khi xóa thư mục tạm {temp_dir}: {e}")
            
    # 2. Xóa các bản ghi chunks trong DB
    async with AsyncSessionLocal() as session:
        try:
            stmt = delete(TTSChunk).where(TTSChunk.novel_id == novel_id, TTSChunk.volume_no == volume_no)
            await session.execute(stmt)
            await session.commit()
            print("  - Đã xóa các bản ghi chunks trong SQLite.")
        except Exception as e:
            print(f"  - Lỗi khi xóa bản ghi CSDL: {e}")

async def run_tts_volume_pipeline(novel_id: int, volume_no: int, chapters_per_volume: int, voice_profile: str = "default"):
    """Pipeline Edge-TTS hoàn chỉnh điều phối hàng đợi và ghép nối FFmpeg"""
    job_key = f"{novel_id}_{volume_no}"
    job_info = ACTIVE_TTS_JOBS[job_key]
    
    # 1. Khởi tạo đường dẫn
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_audio_dir, novel_folder)
    temp_dir = os.path.join(out_dir, f"temp_vol_{volume_no}")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Lấy danh sách chương của Volume
    async with AsyncSessionLocal() as session:
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no)
        res_ch = await session.execute(stmt_ch)
        all_chapters = res_ch.scalars().all()
        
    if volume_no >= 1000000:
        rem = volume_no - 1000000
        start_ch = rem // 10000
        end_ch = rem % 10000
        volume_chapters = [ch for ch in all_chapters if start_ch <= ch.chapter_no <= end_ch]
    else:
        start_idx = (volume_no - 1) * chapters_per_volume
        end_idx = min(start_idx + chapters_per_volume, len(all_chapters))
        volume_chapters = all_chapters[start_idx:end_idx]
    
    if not volume_chapters:
        job_info["status"] = "failed"
        job_info["is_running"] = False
        return
        
    # 2. Chuẩn bị text chia chunk
    total_chunks = await prepare_volume_chunks(novel_id, volume_no, volume_chapters)
    job_info["total_chunks"] = total_chunks
    
    if total_chunks == 0:
        job_info["status"] = "failed"
        job_info["is_running"] = False
        return
        
    # Đọc số lượng chunk hoàn thành thực tế trong DB đề phòng trường hợp resume
    async with AsyncSessionLocal() as session:
        stmt_done = select(TTSChunk).where(
            TTSChunk.novel_id == novel_id,
            TTSChunk.volume_no == volume_no,
            TTSChunk.status == "DONE"
        )
        res_done = await session.execute(stmt_done)
        job_info["done_chunks"] = len(res_done.scalars().all())
        
        stmt_failed = select(TTSChunk).where(
            TTSChunk.novel_id == novel_id,
            TTSChunk.volume_no == volume_no,
            TTSChunk.status == "FAILED"
        )
        res_failed = await session.execute(stmt_failed)
        job_info["failed_chunks"] = len(res_failed.scalars().all())

    # 3. Tạo hàng đợi và nạp chunk ID PENDING
    queue = asyncio.Queue()
    async with AsyncSessionLocal() as session:
        stmt_pending = select(TTSChunk.id).where(
            TTSChunk.novel_id == novel_id,
            TTSChunk.volume_no == volume_no,
            TTSChunk.status.in_(["PENDING", "PROCESSING"])  # Phục hồi luôn các chunk dở dang cũ
        )
        res_pending = await session.execute(stmt_pending)
        pending_ids = res_pending.scalars().all()
        
    for pid in pending_ids:
        await queue.put(pid)
        
    # 4. Khởi chạy Worker Pool bất đồng bộ
    voice = get_voice_name(voice_profile)
    start_time = time.time()
    
    num_workers = 24  # Mặc định khởi chạy 24 worker song song
    job_info["worker_count"] = num_workers
    workers = []
    
    try:
        for _ in range(num_workers):
            t = asyncio.create_task(tts_worker(queue, novel_id, volume_no, voice, temp_dir, job_info))
            workers.append(t)
            
        # 5. Vòng lặp giám sát định kỳ & Auto-scaling
        while True:
            # Đợi một chút rồi đo lường tiến độ
            await asyncio.sleep(5)
            
            # Cập nhật RAM & Tiến trình
            job_info["ram_usage_percent"] = psutil.virtual_memory().percent
            elapsed = time.time() - start_time
            done = job_info["done_chunks"]
            total = job_info["total_chunks"]
            
            if done > 0 and elapsed > 0:
                speed = (done / elapsed) * 60
                job_info["speed_chunks_per_min"] = round(speed, 2)
                job_info["eta_seconds"] = int((total - done) / (speed / 60)) if speed > 0 else 0
                job_info["percent"] = round((done / total) * 100, 1)
            
            # Kiểm tra trạng thái hàng đợi và worker
            all_done_workers = all(w.done() for w in workers)
            if all_done_workers and queue.empty():
                break
                
            # Cơ chế Tự thích nghi (Concurreny Auto-Scaling) khi phát hiện tỷ lệ lỗi tăng cao (>15%)
            total_recent = job_info["recent_successes"] + job_info["recent_failures"]
            if total_recent >= 30:
                fail_rate = job_info["recent_failures"] / total_recent
                if fail_rate > 0.15 and num_workers > 8:
                    # Giảm số worker để hạ tải tránh bị block IP
                    num_workers = max(8, num_workers - 4)
                    job_info["worker_count"] = num_workers
                    print(f"[TTS-SCALING] Phát hiện tỷ lệ lỗi cao ({round(fail_rate*100, 1)}%). Hạ số worker xuống {num_workers}")
                    # Gửi tin dừng tới queue cho các worker dư thừa
                    for _ in range(4):
                        await queue.put(None)
                # Reset counters
                job_info["recent_successes"] = 0
                job_info["recent_failures"] = 0
                
        # Đợi toàn bộ worker tắt hẳn
        for _ in range(len(workers)):
            await queue.put(None)
        await asyncio.gather(*workers, return_exceptions=True)
        
        # 6. Ghép nối lần cuối thành tệp Audiobook hoàn chỉnh
        async with AsyncSessionLocal() as session:
            stmt_all_chunks = select(TTSChunk).where(
                TTSChunk.novel_id == novel_id,
                TTSChunk.volume_no == volume_no
            ).order_by(TTSChunk.chunk_id)
            res_all_chunks = await session.execute(stmt_all_chunks)
            all_vol_chunks = res_all_chunks.scalars().all()
            
        if not all_vol_chunks:
            job_info["status"] = "failed"
            job_info["is_running"] = False
            return
            
        # Tổng hợp danh sách tệp duy nhất theo thứ tự
        unique_audio_files = []
        last_path = None
        for chunk in all_vol_chunks:
            if chunk.audio_path and chunk.audio_path != last_path:
                if os.path.exists(chunk.audio_path):
                    unique_audio_files.append(chunk.audio_path)
                    last_path = chunk.audio_path
                    
        if volume_no >= 1000000:
            rem = volume_no - 1000000
            start_ch = rem // 10000
            end_ch = rem % 10000
            final_vol_name = f"{novel_folder}_Ch{start_ch}_to_Ch{end_ch}.mp3"
        else:
            final_vol_name = f"{novel_folder}_Vol{volume_no:03d}.mp3"
            
        print(f"[TTS-PIPELINE] Bắt đầu ghép nối {len(unique_audio_files)} tệp thành Audiobook cuối cùng...")
        job_info["status_msg"] = f"🎬 Đã hoàn thành 100% chunk! Đang ghép nối file MP3 bằng FFmpeg..."
        success_merge = merge_audio_files(unique_audio_files, final_output_path)
        
        if success_merge:
            # Xóa toàn bộ file tạm
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
                
            # Cập nhật đường dẫn file cuối cùng vào DB
            async with AsyncSessionLocal() as session:
                for chunk in all_vol_chunks:
                    chunk.audio_path = final_output_path
                await session.commit()
                
            job_info["status"] = "completed"
            print(f"🎉 Ghép nối thành công! Đã lưu audiobook tại {final_output_path}")
        else:
            job_info["status"] = "failed"
            print(f"❌ Ghép nối tệp audiobook thất bại.")
            # Xóa sạch nếu ghép thất bại để tránh rác
            await cleanup_tts_volume(novel_id, volume_no, temp_dir)
            
    except asyncio.CancelledError:
        print(f"[TTS-PIPELINE] Tiến trình {job_key} bị hủy bởi người dùng.")
        # Dọn dẹp các worker
        for w in workers:
            if not w.done():
                w.cancel()
        job_info["status"] = "cancelled"
        job_info["is_running"] = False
        # Xóa sạch những gì đã làm được dở dang
        await cleanup_tts_volume(novel_id, volume_no, temp_dir)
        return
        
    except Exception as e:
        print(f"[TTS-PIPELINE ERROR] Lỗi không xác định: {e}")
        for w in workers:
            if not w.done():
                w.cancel()
        job_info["status"] = "failed"
        job_info["is_running"] = False
        # Xóa sạch những gì đã làm được dở dang
        await cleanup_tts_volume(novel_id, volume_no, temp_dir)
        raise e
        
    job_info["is_running"] = False

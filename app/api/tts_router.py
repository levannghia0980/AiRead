import os
import re
import shutil
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion
from app.services.storage.file_storage import sanitize_filename
from app.services.tts.pipeline import (
    ACTIVE_TTS_JOBS,
    run_tts_volume_pipeline,
    get_audio_duration_ffmpeg
)

router = APIRouter(prefix="/novels/{novel_id}/audio", tags=["Audiobook"])

def format_file_size(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"

@router.get("/volumes")
async def get_audio_volumes(
    novel_id: int = Path(...),
    chapters_per_volume: int = Query(50, ge=1)
):
    """Lấy danh sách các tập chia nhỏ của bộ truyện kèm trạng thái tệp âm thanh"""
    from sqlalchemy.orm import selectinload
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
        # 1. Thư mục Output/04_KetQua trên đĩa
        base_dir = r"D:\NENGHIA0980\AIREAD\Output\04_KetQua"
        novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
        out_dir = os.path.join(base_dir, novel_folder, "chapters")

        max_completed_ch = 0
        
        # Quét CSDL lấy chương có số thứ tự lớn nhất
        stmt_max = (
            select(Chapter.chapter_no)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_no.desc())
            .limit(1)
        )
        res_max = await session.execute(stmt_max)
        db_max = res_max.scalar_one_or_none()
        if db_max:
            max_completed_ch = db_max

        # Quét thêm thực tế các file .txt có trên đĩa ổ D:\...
        for subfolder in ["04_KetQua", "03_DichAI_LLM", "02_DichMau_GG"]:
            chk_dir = os.path.join(base_dir, subfolder, novel_folder, "chapters")
            if os.path.exists(chk_dir):
                for f in os.listdir(chk_dir):
                    if f.endswith(".txt"):
                        try:
                            c_no = int(os.path.splitext(f)[0])
                            if c_no > max_completed_ch:
                                max_completed_ch = c_no
                        except ValueError:
                            pass

        if max_completed_ch == 0:
            return {
                "novel_title": novel.title_rough or novel.title_raw,
                "total_chapters": 0,
                "chapters_per_volume": chapters_per_volume,
                "created_volumes_count": 0,
                "volumes": []
            }

        # 2. Lấy toàn bộ các chương từ chương 1 đến chương lớn nhất
        stmt_ch = (
            select(Chapter)
            .where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_no <= max_completed_ch
            )
            .options(selectinload(Chapter.versions))
            .order_by(Chapter.chapter_no.asc())
        )
        res_ch = await session.execute(stmt_ch)
        chapters = res_ch.scalars().all()
        
    if not chapters:
        return {
            "novel_title": novel.title_rough or novel.title_raw,
            "total_chapters": 0,
            "chapters_per_volume": chapters_per_volume,
            "created_volumes_count": 0,
            "volumes": []
        }
        
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_audio_dir, novel_folder)
    
    volumes = []
    created_count = 0
    total_ch = len(chapters)
    
    # Chia danh sách chương thành các tập
    num_volumes = (total_ch + chapters_per_volume - 1) // chapters_per_volume
    for i in range(num_volumes):
        vol_no = i + 1
        start_ch_idx = i * chapters_per_volume
        end_ch_idx = min(start_ch_idx + chapters_per_volume, total_ch)
        
        vol_chapters = chapters[start_ch_idx:end_ch_idx]
        start_chapter = vol_chapters[0].chapter_no
        end_chapter = vol_chapters[-1].chapter_no
        chapter_count = len(vol_chapters)
        
        # Ước lượng số từ dựa trên bản dịch AI (FINAL, LLM, GG trong DB hoặc đĩa cứng)
        word_count = 0
        final_count = 0

        for ch in vol_chapters:
            v_best = next((v for v in ch.versions if v.version_type in ["FINAL", "LLM"]), None)
            if v_best and v_best.content:
                word_count += len(v_best.content) // 4
                final_count += 1
            else:
                for subfolder in ["04_KetQua", "03_DichAI_LLM"]:
                    disk_ch_path = os.path.join(r"D:\NENGHIA0980\AIREAD\Output", subfolder, novel_folder, "chapters", f"{ch.chapter_no:06d}.txt")
                    if os.path.exists(disk_ch_path) and os.path.getsize(disk_ch_path) > 0:
                        try:
                            with open(disk_ch_path, "r", encoding="utf-8", errors="ignore") as f:
                                c_text = f.read()
                                if c_text:
                                    word_count += len(c_text) // 4
                                    final_count += 1
                                    break
                        except Exception:
                            pass
                    
        estimated_hours = round(word_count / 10000, 1)
        if estimated_hours < 0.1 and word_count > 0:
            estimated_hours = 0.1
            
        # Đếm số chương đã có cache mp3 riêng lẻ
        chapters_cache_dir = os.path.join(out_dir, "chapters")
        vol_cached_count = 0
        vol_ch_nos = [ch.chapter_no for ch in vol_chapters]
        if os.path.exists(chapters_cache_dir):
            for c_no in vol_ch_nos:
                c_path = os.path.join(chapters_cache_dir, f"{c_no:06d}.mp3")
                if os.path.exists(c_path) and os.path.getsize(c_path) > 0:
                    vol_cached_count += 1

        filename = f"{novel_folder}_Vol{vol_no:03d}.mp3"
        file_path = os.path.join(out_dir, filename)
        is_created = os.path.exists(file_path) and os.path.getsize(file_path) > 0
        
        # Tự động gộp file tập nếu tất cả các chương trong tập đã được cache
        if not is_created and vol_cached_count == chapter_count and chapter_count > 0:
            from app.services.tts.pipeline import generate_range_mp3
            if generate_range_mp3(chapters_cache_dir, vol_ch_nos, file_path):
                is_created = True

        file_size = ""
        duration = ""
        download_url = ""
        size_mb = 0.0
        
        if is_created:
            created_count += 1
            f_size = os.path.getsize(file_path)
            file_size = format_file_size(f_size)
            size_mb = round(f_size / (1024 * 1024), 1)
            duration = get_audio_duration_ffmpeg(file_path)
            download_url = f"/api/novels/{novel_id}/audio/download/{filename}"
            
        volumes.append({
            "volume_no": vol_no,
            "start_chapter": start_chapter,
            "end_chapter": end_chapter,
            "chapter_count": chapter_count,
            "cached_chapters_count": vol_cached_count,
            "word_count": word_count,
            "estimated_hours": estimated_hours,
            "is_created": is_created,
            "filename": filename if is_created else "",
            "download_url": download_url,
            "file_size": file_size,
            "size_mb": size_mb,
            "duration": duration
        })
        
    # Thăm dò các chương đã cache để tự động gộp file khoảng tùy chỉnh nếu có
    chapters_cache_dir = os.path.join(out_dir, "chapters")
    if os.path.exists(chapters_cache_dir):
        cached_nos = sorted([
            int(os.path.splitext(f)[0])
            for f in os.listdir(chapters_cache_dir)
            if f.endswith(".mp3") and re.match(r"^\d{6}\.mp3$", f) and os.path.getsize(os.path.join(chapters_cache_dir, f)) > 0
        ])
        if cached_nos:
            min_ch = cached_nos[0]
            max_ch = cached_nos[-1]
            cust_filename = f"{novel_folder}_Ch{min_ch}_to_Ch{max_ch}.mp3"
            cust_file_path = os.path.join(out_dir, cust_filename)
            if not os.path.exists(cust_file_path):
                from app.services.tts.pipeline import generate_range_mp3
                generate_range_mp3(chapters_cache_dir, cached_nos, cust_file_path)

    # Thăm dò và bổ sung các tệp audio khoảng tùy chỉnh (Custom Range) có trên đĩa
    if os.path.exists(out_dir):
        for f in os.listdir(out_dir):
            if f.endswith(".mp3") and "_Ch" in f and "_to_Ch" in f:
                match = re.search(r"_Ch(\d+)_to_Ch(\d+)(?:_norm)?\.mp3$", f)
                if match:
                    start_ch = int(match.group(1))
                    end_ch = int(match.group(2))
                    vol_no = 1000000 + start_ch * 10000 + end_ch
                    
                    # Tránh thêm trùng nếu đã có trong danh sách
                    if any(v["volume_no"] == vol_no for v in volumes):
                        continue
                        
                    file_path = os.path.join(out_dir, f)
                    f_size = os.path.getsize(file_path)
                    file_size = format_file_size(f_size)
                    size_mb = round(f_size / (1024 * 1024), 1)
                    duration = get_audio_duration_ffmpeg(file_path)
                    download_url = f"/api/novels/{novel_id}/audio/download/{f}"
                    
                    vol_chapters = [ch for ch in chapters if start_ch <= ch.chapter_no <= end_ch]
                    chapter_count = len(vol_chapters) or (end_ch - start_ch + 1)
                    
                    word_count = 0
                    for ch in vol_chapters:
                        v_final = next((v for v in ch.versions if v.version_type in ["FINAL", "LLM"]), None)
                        if v_final and v_final.content:
                            word_count += len(v_final.content) // 4
                        else:
                            word_count += 1500
                                
                    estimated_hours = round(word_count / 10000, 1)
                    if estimated_hours < 0.1:
                        estimated_hours = 0.1
                        
                    created_count += 1
                    volumes.append({
                        "volume_no": vol_no,
                        "start_chapter": start_ch,
                        "end_chapter": end_ch,
                        "chapter_count": chapter_count,
                        "cached_chapters_count": chapter_count,
                        "word_count": word_count,
                        "estimated_hours": estimated_hours,
                        "is_created": True,
                        "filename": f,
                        "download_url": download_url,
                        "file_size": file_size,
                        "size_mb": size_mb,
                        "duration": duration,
                        "is_custom": True
                    })
        
    return {
        "novel_title": novel.title_rough or novel.title_raw,
        "total_chapters": total_ch,
        "chapters_per_volume": chapters_per_volume,
        "created_volumes_count": created_count,
        "volumes": volumes
    }

@router.get("/status")
async def get_audio_status(novel_id: int = Path(...)):
    """Kiểm tra trạng thái hàng đợi và tiến độ tác vụ sinh audio cho truyện"""
    from app.models.schema import TTSChunk

    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_"):
            is_running = job.get("is_running", False)
            status = job.get("status", "processing")
            status_msg = job.get("status_msg")

            total = job.get("total_chunks", 0)
            vol_no = job.get("volume_no", 1)
            worker_count = job.get("worker_count") or 6
            done = job.get("done_chunks", 0)

            percent = round((done / total) * 100, 1) if total > 0 else 0.0
            job["percent"] = percent

            speed = job.get("speed_chunks_per_min", 0.0)
            eta_sec = job.get("eta_seconds", 0)
            
            if total > 0 and done > 0 and eta_sec > 0:
                eta_m = int(eta_sec // 60)
                eta_s = int(eta_sec % 60)
                eta_display = f"{eta_m} phút {eta_s} giây" if eta_m > 0 else f"{eta_s} giây"
            else:
                eta_display = "Đang tính toán..."
            
            vol_label = f"Tập {vol_no}" if vol_no < 1000000 else "Khoảng chương tùy chỉnh"
            if status_msg:
                msg = status_msg
            elif done == 0 and total > 0:
                msg = f"🚀 Đang khởi động {worker_count} Workers tổng hợp audio {vol_label}..."
            elif done > 0 and total > 0:
                msg = f"Đang tổng hợp audio {vol_label}: {done}/{total} chương ({percent}%)"
            else:
                msg = "Đang quét cache chương..."

            if is_running:
                return {
                    "is_running": True,
                    "novel_id": novel_id,
                    "volume_no": vol_no,
                    "progress_pct": percent,
                    "msg": msg,
                    "eta_display": eta_display,
                    "progress": {
                        "total_chunks": total,
                        "done_chunks": done,
                        "failed_chunks": job.get("failed_chunks", 0),
                        "status": status,
                        "eta_seconds": eta_sec,
                        "percent": percent,
                        "worker_count": worker_count,
                        "ram_usage_percent": job.get("ram_usage_percent", 0.0),
                        "speed_chunks_per_min": speed
                    },
                    "stats": {
                        "speed_chapters_per_min": round(speed / 5, 1) if speed > 0 else 0
                    }
                }
            elif status == "failed" or status_msg:
                return {
                    "is_running": False,
                    "status": "failed",
                    "novel_id": novel_id,
                    "volume_no": vol_no,
                    "progress_pct": percent,
                    "msg": status_msg or "❌ Tạo audio thất bại.",
                    "error": status_msg or "❌ Tạo audio thất bại."
                }

    return {"is_running": False}

@router.post("/generate_volume/{volume_no}")
async def generate_volume(
    novel_id: int = Path(...),
    volume_no: int = Path(...),
    voice_profile: str = Query("default"),
    chapters_per_volume: int = Query(50, ge=1)
):
    """Kích hoạt tiến trình sinh tệp audiobook bất đồng bộ cho một tập cụ thể"""
    # 1. Đảm bảo không có job tts nào khác đang chạy cho novel này
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            raise HTTPException(
                status_code=400,
                detail="Đang có tiến trình tạo audio khác đang chạy cho truyện này. Vui lòng chờ hoàn tất hoặc hủy nó trước."
            )
            
    job_key = f"{novel_id}_{volume_no}"
    
    # 2. Khởi tạo trạng thái job mới
    job_info = {
        "novel_id": novel_id,
        "volume_no": volume_no,
        "is_running": True,
        "total_chunks": 0,
        "done_chunks": 0,
        "failed_chunks": 0,
        "status": "processing",
        "eta_seconds": 0,
        "percent": 0.0,
        "worker_count": 0,
        "ram_usage_percent": 0.0,
        "speed_chunks_per_min": 0.0,
        "recent_successes": 0,
        "recent_failures": 0
    }
    ACTIVE_TTS_JOBS[job_key] = job_info
    
    # 3. Kích hoạt task chạy nền
    task = asyncio.create_task(
        run_tts_volume_pipeline(novel_id, volume_no, chapters_per_volume, voice_profile)
    )
    job_info["task"] = task
    
    return {
        "status": "success",
        "message": f"Đã kích hoạt tạo audio thành công cho Tập {volume_no}."
    }

@router.post("/generate_range")
async def generate_range(
    novel_id: int = Path(...),
    start_chapter: int = Query(..., ge=1),
    end_chapter: int = Query(..., ge=1),
    voice_profile: str = Query("default")
):
    """Kích hoạt tiến trình sinh tệp audiobook cho khoảng chương tùy chỉnh (luồng tương tự dịch truyện)"""
    if start_chapter > end_chapter:
        raise HTTPException(status_code=400, detail="Chương bắt đầu không được lớn hơn chương kết thúc.")
        
    # 1. Đảm bảo không có job tts nào khác đang chạy cho novel này
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            raise HTTPException(
                status_code=400,
                detail="Đang có tiến trình tạo audio khác đang chạy cho truyện này. Vui lòng chờ hoàn tất hoặc hủy nó trước."
            )
            
    # Tính volume_no đặc biệt đại diện cho custom range: 1.000.000 + start_chapter * 10.000 + end_chapter
    volume_no = 1000000 + start_chapter * 10000 + end_chapter
    job_key = f"{novel_id}_{volume_no}"
    
    # 2. Khởi tạo trạng thái job mới
    job_info = {
        "novel_id": novel_id,
        "volume_no": volume_no,
        "is_running": True,
        "total_chunks": 0,
        "done_chunks": 0,
        "failed_chunks": 0,
        "status": "processing",
        "eta_seconds": 0,
        "percent": 0.0,
        "worker_count": 0,
        "ram_usage_percent": 0.0,
        "speed_chunks_per_min": 0.0,
        "recent_successes": 0,
        "recent_failures": 0
    }
    ACTIVE_TTS_JOBS[job_key] = job_info
    
    # 3. Kích hoạt task chạy nền
    task = asyncio.create_task(
        run_tts_volume_pipeline(novel_id, volume_no, chapters_per_volume=99999, voice_profile=voice_profile)
    )
    job_info["task"] = task
    
    return {
        "status": "success",
        "message": f"Đã kích hoạt tạo audio thành công cho khoảng chương {start_chapter} - {end_chapter}."
    }

@router.post("/cancel")
async def cancel_audio_job(novel_id: int = Path(...)):
    """Hủy tiến trình tạo audio đang chạy của truyện và dọn sạch các file tạm _tmp_ch*"""
    cancelled_any = False
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            task = job.get("task")
            if task and not task.done():
                task.cancel()
                cancelled_any = True
            job["is_running"] = False
            job["status"] = "cancelled"
            
    # Dọn sạch các thư mục tạm _tmp_ch* dở dang trên đĩa
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if novel:
            novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
            chapters_cache_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS", novel_folder, "chapters")
            if os.path.exists(chapters_cache_dir):
                for f in os.listdir(chapters_cache_dir):
                    if f.startswith("_tmp_ch"):
                        shutil.rmtree(os.path.join(chapters_cache_dir, f), ignore_errors=True)

    if cancelled_any:
        return {"status": "success", "message": "Đã hủy bỏ tiến trình sinh audio và dọn sạch dữ liệu tạm dở dang."}
    return {"status": "warning", "message": "Không tìm thấy tiến trình sinh audio nào đang hoạt động."}

@router.get("/download/{filename}")
async def download_audio_file(
    novel_id: int = Path(...),
    filename: str = Path(...)
):
    """FileResponse cho phép tải xuống hoặc chơi trực tiếp tệp audio trên browser"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    file_path = os.path.join(base_audio_dir, novel_folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Tệp âm thanh không tồn tại trên máy chủ.")
        
    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)

@router.delete("/files/{filename}")
@router.post("/delete_file/{filename}")
async def delete_audio_file(
    novel_id: int = Path(...),
    filename: str = Path(...)
):
    """Xóa một tệp âm thanh cụ thể trên đĩa + dọn dẹp bộ nhớ đệm chương để ép đọc bản dịch mới"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    base_tts_text_dir = r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    file_path = os.path.join(base_audio_dir, novel_folder, filename)
    chapters_cache_dir = os.path.join(base_audio_dir, novel_folder, "chapters")
    tts_text_novel_dir = os.path.join(base_tts_text_dir, novel_folder)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            # Dọn dẹp sạch cache chương để khi tạo lại Audio bắt buộc phải đọc bản dịch mới nhất
            if os.path.exists(chapters_cache_dir):
                shutil.rmtree(chapters_cache_dir, ignore_errors=True)
                os.makedirs(chapters_cache_dir, exist_ok=True)
            if os.path.exists(tts_text_novel_dir):
                shutil.rmtree(tts_text_novel_dir, ignore_errors=True)
            return {"status": "success", "message": f"Đã xóa thành công tệp {filename} và làm sạch bộ nhớ đệm audio."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa tệp: {str(e)}")
            
    raise HTTPException(status_code=404, detail="Tệp không tồn tại.")

@router.delete("/files")
@router.post("/delete_all")
async def delete_all_audio_files(novel_id: int = Path(...)):
    """Xóa toàn bộ các tệp âm thanh + cache chương của truyện"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    base_tts_text_dir = r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    novel_audio_dir = os.path.join(base_audio_dir, novel_folder)
    tts_text_novel_dir = os.path.join(base_tts_text_dir, novel_folder)
    
    if os.path.exists(novel_audio_dir) or os.path.exists(tts_text_novel_dir):
        try:
            if os.path.exists(novel_audio_dir):
                shutil.rmtree(novel_audio_dir)
            if os.path.exists(tts_text_novel_dir):
                shutil.rmtree(tts_text_novel_dir, ignore_errors=True)
            return {"status": "success", "message": "Đã xóa toàn bộ thư mục âm thanh và bộ nhớ đệm của truyện thành công."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa toàn bộ thư mục: {str(e)}")
            
    return {"status": "success", "message": "Thư mục âm thanh trống."}

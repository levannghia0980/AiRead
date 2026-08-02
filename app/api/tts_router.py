import os
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
            
        stmt_ch = (
            select(Chapter)
            .join(ChapterVersion, Chapter.id == ChapterVersion.chapter_id)
            .where(Chapter.novel_id == novel_id, ChapterVersion.version_type == "FINAL")
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
        
        # Ước lượng số từ dựa trên độ dài nội dung dịch
        word_count = 0
        for ch in vol_chapters:
            v_final = next((v for v in ch.versions if v.version_type == "FINAL"), None)
            if v_final and v_final.content:
                word_count += len(v_final.content) // 4
            else:
                v_gg = next((v for v in ch.versions if v.version_type == "GG"), None)
                if v_gg and v_gg.content:
                    word_count += len(v_gg.content) // 4
                else:
                    word_count += 1500
                    
        estimated_hours = round(word_count / 10000, 1)
        if estimated_hours < 0.1:
            estimated_hours = 0.1
            
        filename = f"{novel_folder}_Vol{vol_no:03d}.mp3"
        file_path = os.path.join(out_dir, filename)
        is_created = os.path.exists(file_path) and os.path.getsize(file_path) > 0
        
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
            "word_count": word_count,
            "estimated_hours": estimated_hours,
            "is_created": is_created,
            "filename": filename if is_created else "",
            "download_url": download_url,
            "file_size": file_size,
            "size_mb": size_mb,
            "duration": duration
        })
        
    # Thăm dò và bổ sung các tệp audio khoảng tùy chỉnh (Custom Range) có trên đĩa
    import re
    if os.path.exists(out_dir):
        for f in os.listdir(out_dir):
            if f.endswith(".mp3") and "_Ch" in f and "_to_Ch" in f:
                match = re.search(r"_Ch(\d+)_to_Ch(\d+)\.mp3$", f)
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
                    chapter_count = len(vol_chapters)
                    
                    word_count = 0
                    for ch in vol_chapters:
                        v_final = next((v for v in ch.versions if v.version_type == "FINAL"), None)
                        if v_final and v_final.content:
                            word_count += len(v_final.content) // 4
                        else:
                            v_gg = next((v for v in ch.versions if v.version_type == "GG"), None)
                            if v_gg and v_gg.content:
                                word_count += len(v_gg.content) // 4
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
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            # Cập nhật thông số tính toán phần trăm
            done = job.get("done_chunks", 0)
            total = job.get("total_chunks", 0)
            percent = round((done / total) * 100, 1) if total > 0 else 0
            vol_no = job.get("volume_no", 1)
            speed = job.get("speed_chunks_per_min", 0.0)
            eta_sec = job.get("eta_seconds", 0)
            
            status_msg = job.get("status_msg")
            if status_msg:
                msg = status_msg
            elif done == 0 and total > 0:
                msg = f"🚀 Đang khởi động 24 Workers tổng hợp Tập {vol_no}..."
            elif done > 0 and total > 0:
                msg = f"Đang tổng hợp Tập {vol_no}: {done}/{total} chunk ({percent}%)"
            else:
                msg = "Đang chuẩn bị dữ liệu chunk..."

            return {
                "is_running": True,
                "novel_id": novel_id,
                "volume_no": vol_no,
                "progress_pct": percent,
                "msg": msg,
                "eta_display": eta_display if total > 0 and done > 0 else "Đang tính toán...",
                "progress": {
                    "total_chunks": total,
                    "done_chunks": done,
                    "failed_chunks": job.get("failed_chunks", 0),
                    "status": job.get("status", "processing"),
                    "eta_seconds": eta_sec,
                    "percent": percent,
                    "worker_count": job.get("worker_count", 0),
                    "ram_usage_percent": job.get("ram_usage_percent", 0.0),
                    "speed_chunks_per_min": speed
                },
                "stats": {
                    "speed_chapters_per_min": round(speed / 5, 1) if speed > 0 else 0
                }
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
    """Hủy tiến trình tạo audio đang chạy của truyện"""
    cancelled_any = False
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            task = job.get("task")
            if task and not task.done():
                task.cancel()
                cancelled_any = True
            job["is_running"] = False
            job["status"] = "cancelled"
            
    if cancelled_any:
        return {"status": "success", "message": "Đã hủy bỏ tiến trình sinh audio thành công."}
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
    """Xóa một tệp âm thanh cụ thể trên đĩa"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    file_path = os.path.join(base_audio_dir, novel_folder, filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"status": "success", "message": f"Đã xóa thành công tệp {filename}."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa tệp: {str(e)}")
            
    raise HTTPException(status_code=404, detail="Tệp không tồn tại.")

@router.delete("/files")
@router.post("/delete_all")
async def delete_all_audio_files(novel_id: int = Path(...)):
    """Xóa toàn bộ các tệp âm thanh của truyện"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    novel_audio_dir = os.path.join(base_audio_dir, novel_folder)
    
    if os.path.exists(novel_audio_dir):
        try:
            shutil.rmtree(novel_audio_dir)
            return {"status": "success", "message": "Đã xóa toàn bộ thư mục âm thanh của truyện thành công."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa toàn bộ thư mục: {str(e)}")
            
    return {"status": "success", "message": "Thư mục âm thanh trống."}

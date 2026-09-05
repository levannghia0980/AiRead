import os
import re
import json
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
test_router = APIRouter(prefix="/tts", tags=["TTS Testing"])

@test_router.get("/synthesize")
@test_router.post("/synthesize")
async def test_synthesize_audio(text: str = Query(...), voice: str = Query("vi-VN-HoaiMyNeural")):
    """Tổng hợp âm thanh trực tiếp qua Microsoft Edge-TTS bằng Python backend"""
    import edge_tts
    from fastapi import Response
    from app.services.tts.pipeline import sanitize_tts_text
    clean_text = sanitize_tts_text(text) if text else ""
    if not clean_text or not clean_text.strip():
        raise HTTPException(status_code=400, detail="Văn bản rỗng hoặc chỉ chứa thông báo kết thúc chương sau khi làm sạch.")
    try:
        comm = edge_tts.Communicate(clean_text, voice)
        audio_data = b""
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                audio_data += chunk["data"]
        
        if not audio_data or len(audio_data) < 200:
            raise HTTPException(status_code=400, detail="NoAudioReceived: Bị Microsoft Safety Filter chặn nội dung 18+")
            
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")

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
        for subfolder in ["04_KetQua", "03_DichAI_LLM"]:
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
        alt_filename = f"{novel_folder}_Ch{start_chapter}_to_Ch{end_chapter}.mp3"
        file_path = os.path.join(out_dir, filename)
        alt_file_path = os.path.join(out_dir, alt_filename)

        if not (os.path.exists(file_path) and os.path.getsize(file_path) > 0) and (os.path.exists(alt_file_path) and os.path.getsize(alt_file_path) > 0):
            filename = alt_filename
            file_path = alt_file_path

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
            "translated_chapters_count": final_count,
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
                    if any(v["volume_no"] == vol_no or v.get("filename") == f for v in volumes):
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
        "total_volumes": len(volumes),
        "max_translated_chapter": max_completed_ch,
        "chapters_per_volume": chapters_per_volume,
        "created_volumes_count": created_count,
        "volumes": volumes
    }

from fastapi.responses import FileResponse, StreamingResponse
import json

@router.get("/events")
async def audio_events_stream(novel_id: int = Path(...)):
    """Server-Sent Events (SSE) stream đẩy tiến độ TTS trực tiếp về Frontend theo thời gian thực (Zero Polling)"""
    async def event_generator():
        while True:
            job_found = False
            for key, job in ACTIVE_TTS_JOBS.items():
                if key.startswith(f"{novel_id}_"):
                    job_found = True
                    is_running = job.get("is_running", False)
                    status = job.get("status", "processing")
                    status_msg = job.get("status_msg")
                    total = job.get("total_chapters") or job.get("total_chunks", 0)
                    vol_no = job.get("volume_no", 1)
                    worker_count = job.get("worker_count") or 8
                    done = job.get("done_chapters") if "done_chapters" in job else job.get("done_chunks", 0)
                    
                    # Ưu tiên lấy % tính theo subchunks thời gian thực từ pipeline (0% -> 99.9% -> 100%)
                    percent = job.get("percent", 0.0)
                    if percent == 0.0 and total > 0 and done > 0:
                        percent = round((done / total) * 100, 1)
                    
                    speed = job.get("speed_chunks_per_min", 0.0)
                    eta_sec = job.get("eta_seconds", 0)
                    
                    if total > 0 and done > 0 and eta_sec > 0:
                        eta_m = int(eta_sec // 60)
                        eta_s = int(eta_sec % 60)
                        eta_display = f"{eta_m} phút {eta_s} giây" if eta_m > 0 else f"{eta_s} giây"
                    else:
                        eta_display = "Đang tính toán..."
                        
                    vol_label = f"Tập {vol_no}" if vol_no < 1000000 else "Khoảng chương"
                    done_sc = job.get("done_subchunks", 0)
                    total_sc = job.get("total_subchunks", 0)
                    
                    if status_msg:
                        msg = status_msg
                    elif done == 0 and total > 0:
                        if total_sc > 0 and done_sc > 0:
                            msg = f"🚀 Đang xử lý {vol_label}: {done_sc}/{total_sc} đoạn ({percent}%)"
                        else:
                            msg = f"🚀 Đang khởi động {worker_count} Workers tổng hợp audio {vol_label}..."
                    elif done > 0 and total > 0:
                        msg = f"Đang tổng hợp audio {vol_label}: {done_sc}/{total_sc} đoạn ({percent}%)"
                    else:
                        msg = "Đang quét cache chương..."
                        
                    payload = {
                        "is_running": is_running,
                        "novel_id": novel_id,
                        "volume_no": vol_no,
                        "progress_pct": percent,
                        "msg": msg,
                        "eta_display": eta_display,
                        "done_chapters": job.get("done_chapters", 0),
                        "last_completed_chapter": job.get("last_completed_chapter"),
                        "last_chunk_log": job.get("last_chunk_log", ""),
                        "logs": job.get("logs", []),
                        "progress": {
                            "total_chunks": total,
                            "done_chunks": done,
                            "done_chapters": job.get("done_chapters", 0),
                            "done_subchunks": done_sc,
                            "total_subchunks": total_sc,
                            "failed_chapters": job.get("failed_chapters", 0),
                            "failed_chunks": job.get("failed_chunks", 0),
                            "status": status,
                            "eta_seconds": eta_sec,
                            "percent": percent,
                            "worker_count": worker_count,
                            "speed_chunks_per_min": speed
                        }
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    break
                    
            if not job_found:
                yield f"data: {json.dumps({'is_running': False, 'progress_pct': 0}, ensure_ascii=False)}\n\n"
                
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/job_status")
async def get_audio_job_status(novel_id: int = Path(...)):
    """Lấy trạng thái tiến trình tạo audio tức thì theo novel_id"""
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_"):
            percent = job.get("percent", 0.0)
            done_sc = job.get("done_subchunks", 0)
            total_sc = job.get("total_subchunks", 0)
            eta_sec = job.get("eta_seconds", 0)
            eta_m = int(eta_sec // 60)
            eta_s = int(eta_sec % 60)
            eta_display = f"{eta_m} phút {eta_s} giây" if eta_m > 0 else (f"{eta_s} giây" if eta_s > 0 else "Đang tính...")
            return {
                "is_running": job.get("is_running", False),
                "novel_id": novel_id,
                "progress_pct": percent,
                "msg": job.get("status_msg") or f"Đang tạo audio: {done_sc}/{total_sc} đoạn ({percent}%)",
                "eta_display": eta_display,
                "done_chapters": job.get("done_chapters", 0),
                "last_completed_chapter": job.get("last_completed_chapter"),
                "last_chunk_log": job.get("last_chunk_log", ""),
                "logs": job.get("logs", []),
                "done_subchunks": done_sc,
                "total_subchunks": total_sc
            }
    return {"is_running": False, "progress_pct": 0}

@router.post("/generate_volume/{volume_no}")
async def generate_volume(
    novel_id: int = Path(...),
    volume_no: int = Path(...),
    voice_profile: str = Query("default"),
    chapters_per_volume: int = Query(50, ge=1),
    force_regenerate: bool = Query(False),
    workers: Optional[int] = Query(None, ge=1, le=128)
):
    """Kích hoạt tiến trình sinh tệp audiobook bất đồng bộ cho một tập cụ thể"""
    import gc
    # 1. Dọn dẹp các job cũ không còn chạy của novel này để giải phóng bộ nhớ
    to_del = [k for k, j in ACTIVE_TTS_JOBS.items() if k.startswith(f"{novel_id}_") and not j.get("is_running", False)]
    for k in to_del:
        ACTIVE_TTS_JOBS.pop(k, None)
    gc.collect()

    # 2. Đảm bảo không có job tts nào khác đang chạy cho novel này
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            raise HTTPException(
                status_code=400,
                detail="Đang có tiến trình tạo audio khác đang chạy cho truyện này. Vui lòng chờ hoàn tất hoặc hủy nó trước."
            )
            
    job_key = f"{novel_id}_{volume_no}"
    
    # 3. Khởi tạo trạng thái job mới
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
        "worker_count": workers or 8,
        "ram_usage_percent": 0.0,
        "speed_chunks_per_min": 0.0,
        "recent_successes": 0,
        "recent_failures": 0
    }
    ACTIVE_TTS_JOBS[job_key] = job_info
    
    # 4. Kích hoạt task chạy nền
    task = asyncio.create_task(
        run_tts_volume_pipeline(novel_id, volume_no, chapters_per_volume, voice_profile, force_regenerate=force_regenerate, custom_workers=workers)
    )
    job_info["task"] = task
    
    return {
        "status": "success",
        "message": f"Đã kích hoạt tạo audio thành công cho Tập {volume_no}."
    }

@router.post("/generate_range")
@router.post("/generate_custom_range")
async def generate_range(
    novel_id: int = Path(...),
    start_chapter: int = Query(..., ge=1),
    end_chapter: int = Query(..., ge=1),
    voice_profile: str = Query("default"),
    force_regenerate: bool = Query(False),
    workers: Optional[int] = Query(None, ge=1, le=128)
):
    """Kích hoạt tiến trình sinh tệp audiobook cho khoảng chương tùy chỉnh (luồng tương tự dịch truyện)"""
    import gc
    if start_chapter > end_chapter:
        raise HTTPException(status_code=400, detail="Chương bắt đầu không được lớn hơn chương kết thúc.")
        
    # 1. Dọn dẹp các job cũ không còn chạy của novel này để giải phóng bộ nhớ
    to_del = [k for k, j in ACTIVE_TTS_JOBS.items() if k.startswith(f"{novel_id}_") and not j.get("is_running", False)]
    for k in to_del:
        ACTIVE_TTS_JOBS.pop(k, None)
    gc.collect()

    # 2. Đảm bảo không có job tts nào khác đang chạy cho novel này
    for key, job in ACTIVE_TTS_JOBS.items():
        if key.startswith(f"{novel_id}_") and job.get("is_running", False):
            raise HTTPException(
                status_code=400,
                detail="Đang có tiến trình tạo audio khác đang chạy cho truyện này. Vui lòng chờ hoàn tất hoặc hủy nó trước."
            )
            
    # Tính volume_no đặc biệt đại diện cho custom range: 1.000.000 + start_chapter * 10.000 + end_chapter
    volume_no = 1000000 + start_chapter * 10000 + end_chapter
    job_key = f"{novel_id}_{volume_no}"
    
    # 3. Khởi tạo trạng thái job mới
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
        "worker_count": workers or 8,
        "ram_usage_percent": 0.0,
        "speed_chunks_per_min": 0.0,
        "recent_successes": 0,
        "recent_failures": 0
    }
    ACTIVE_TTS_JOBS[job_key] = job_info
    
    # 4. Kích hoạt task chạy nền
    task = asyncio.create_task(
        run_tts_volume_pipeline(novel_id, volume_no, chapters_per_volume=99999, voice_profile=voice_profile, force_regenerate=force_regenerate, custom_workers=workers)
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

@router.post("/merge_range")
async def merge_custom_range(
    novel_id: int = Path(...),
    start_chapter: int = Query(..., ge=1),
    end_chapter: int = Query(..., ge=1),
    speed: float = Query(1.0, ge=0.25, le=4.0)
):
    """Ghép nối nhanh bằng FFmpeg các chương MP3 đã có sẵn trong cache thành một file gộp duy nhất kèm hỗ trợ chọn tốc độ phát (speed)"""
    if start_chapter > end_chapter:
        raise HTTPException(status_code=400, detail="Chương bắt đầu không được lớn hơn chương kết thúc.")
        
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")

    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_audio_dir, novel_folder)
    chapters_cache_dir = os.path.join(out_dir, "chapters")
    
    chapter_nos = list(range(start_chapter, end_chapter + 1))
    from app.services.tts.pipeline import generate_range_mp3, get_audio_duration_ffmpeg
    cached_chapters = []
    for c in chapter_nos:
        f_p = _find_chapter_audio_path(chapters_cache_dir, c)
        if f_p and os.path.exists(f_p) and os.path.getsize(f_p) > 1024:
            cached_chapters.append(c)
    
    if not cached_chapters:
        all_cached = []
        if os.path.exists(chapters_cache_dir):
            for f in os.listdir(chapters_cache_dir):
                if f.endswith(".mp3") and not f.startswith("_"):
                    try:
                        c_num = int(os.path.splitext(f)[0])
                        all_cached.append(c_num)
                    except ValueError:
                        pass
        all_cached.sort()
        if all_cached:
            raise HTTPException(
                status_code=400, 
                detail=f"Khoảng chương {start_chapter} → {end_chapter} chưa có Audio MP3 nào! Hiện truyện có sẵn Audio từ Chương {all_cached[0]} đến Chương {all_cached[-1]} ({len(all_cached)} chương). Vui lòng chọn khoảng có sẵn hoặc bấm 'Tạo Audio' trước."
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail="Truyện này chưa có chương nào được tạo Audio MP3. Vui lòng bấm 'Tạo Audio' trước khi xuất file gộp!"
            )
        
    short_title = novel_folder[:30].strip() if len(novel_folder) > 30 else novel_folder
    speed_tag = f"_{speed}x" if abs(speed - 1.0) >= 0.01 else ""
    final_name = f"{short_title}_Ch{cached_chapters[0]}_to_Ch{cached_chapters[-1]}{speed_tag}.mp3"
    final_path = os.path.join(out_dir, final_name)
    
    success = await asyncio.to_thread(generate_range_mp3, chapters_cache_dir, cached_chapters, final_path, 0.35, False, speed)
    if not success:
        raise HTTPException(status_code=500, detail="Lỗi khi ghép nối âm thanh bằng FFmpeg.")
        
    dur_str = await asyncio.to_thread(get_audio_duration_ffmpeg, final_path)
    sz = os.path.getsize(final_path) if os.path.exists(final_path) else 0
    
    speed_info = f" (Tốc độ {speed}x)" if abs(speed - 1.0) >= 0.01 else ""
    json_filename = f"{short_title}_Ch{cached_chapters[0]}_to_Ch{cached_chapters[-1]}{speed_tag}_timeline.json"
    json_download_url = f"/api/novels/{novel_id}/audio/export_timeline_json?start_chapter={cached_chapters[0]}&end_chapter={cached_chapters[-1]}&speed={speed}"
    return {
        "status": "success",
        "message": f"Ghép thành công {len(cached_chapters)} chương (Chương {cached_chapters[0]} → {cached_chapters[-1]}){speed_info} vào tệp {final_name}!",
        "filename": final_name,
        "download_url": f"/api/novels/{novel_id}/audio/download/{final_name}",
        "file_size": format_file_size(sz),
        "duration": dur_str,
        "start_chapter": cached_chapters[0],
        "end_chapter": cached_chapters[-1],
        "speed": speed,
        "json_filename": json_filename,
        "json_download_url": json_download_url
    }

@router.get("/auto_partition_bundles")
async def get_auto_partition_bundles(
    novel_id: int = Path(...),
    speed: float = Query(1.5, ge=0.25, le=4.0),
    min_hours: float = Query(10.0, ge=1.0, le=24.0),
    max_hours: float = Query(11.95, ge=2.0, le=24.0)
):
    """
    Tự động tính toán phân tập thông minh cho truyện dựa trên độ dài thực tế của từng chương audio.
    Mỗi tập được gom sao cho thời lượng sau khi scale tốc độ (ví dụ 1.5x) nằm trong khoảng min_hours -> max_hours (10h - <12h).
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")

    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_audio_dir, novel_folder)
    chapters_cache_dir = os.path.join(out_dir, "chapters")

    if not os.path.exists(chapters_cache_dir):
        return {"status": "success", "bundles": [], "total_chapters": 0}

    # Đọc danh sách tất cả các chương audio có sẵn và thời lượng của chúng
    cached_items = []
    for f in sorted(os.listdir(chapters_cache_dir)):
        if f.endswith(".json") and not f.startswith("_"):
            try:
                c_num = int(os.path.splitext(f)[0])
                mp3_p = _find_chapter_audio_path(chapters_cache_dir, c_num)
                if mp3_p and os.path.exists(mp3_p) and os.path.getsize(mp3_p) > 100:
                    dur_sec = 0.0
                    try:
                        with open(os.path.join(chapters_cache_dir, f), "r", encoding="utf-8") as jf:
                            jdata = json.load(jf)
                            dur_sec = float(jdata.get("duration", 0))
                    except Exception:
                        pass
                    if dur_sec <= 0:
                        dur_str = get_audio_duration_ffmpeg(mp3_p)
                        parts = dur_str.split(":")
                        if len(parts) == 3:
                            dur_sec = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                    if dur_sec > 0:
                        cached_items.append((c_num, dur_sec, mp3_p))
            except ValueError:
                pass

    cached_items.sort(key=lambda x: x[0])
    if not cached_items:
        return {"status": "success", "bundles": [], "total_chapters": 0}

    effective_speed = float(speed.default if hasattr(speed, 'default') else speed)
    effective_speed = max(0.25, min(4.0, effective_speed))
    effective_min_h = float(min_hours.default if hasattr(min_hours, 'default') else min_hours)
    effective_max_h = float(max_hours.default if hasattr(max_hours, 'default') else max_hours)
    min_sec = effective_min_h * 3600
    max_sec = effective_max_h * 3600

    bundles_raw = []
    curr_bundle = []
    curr_dur_orig = 0.0

    for c_num, dur, mp3_p in cached_items:
        new_dur_scaled = (curr_dur_orig + dur) / effective_speed
        if curr_bundle and new_dur_scaled > max_sec and (curr_dur_orig / effective_speed) >= min_sec:
            bundles_raw.append((curr_bundle, curr_dur_orig))
            curr_bundle = [c_num]
            curr_dur_orig = dur
        elif curr_bundle and new_dur_scaled > max_sec:
            if (curr_dur_orig / effective_speed) >= 8.0 * 3600:
                bundles_raw.append((curr_bundle, curr_dur_orig))
                curr_bundle = [c_num]
                curr_dur_orig = dur
            else:
                curr_bundle.append(c_num)
                curr_dur_orig += dur
        else:
            curr_bundle.append(c_num)
            curr_dur_orig += dur

    if curr_bundle:
        bundles_raw.append((curr_bundle, curr_dur_orig))

    short_title = novel_folder[:30].strip() if len(novel_folder) > 30 else novel_folder
    speed_tag = f"_{effective_speed}x" if abs(effective_speed - 1.0) >= 0.01 else ""

    result_bundles = []
    for idx, (ch_list, dur_orig) in enumerate(bundles_raw):
        start_c = ch_list[0]
        end_c = ch_list[-1]
        dur_scaled = dur_orig / effective_speed
        h = int(dur_scaled // 3600)
        m = int((dur_scaled % 3600) // 60)
        s = int(dur_scaled % 60)
        dur_formatted = f"{h}h {m}m {s}s"
        
        merged_filename = f"{short_title}_Ch{start_c}_to_Ch{end_c}{speed_tag}.mp3"
        merged_path = os.path.join(out_dir, merged_filename)
        is_merged = os.path.exists(merged_path) and os.path.getsize(merged_path) > 1024
        file_sz_str = format_file_size(os.path.getsize(merged_path)) if is_merged else ""

        json_filename = f"{short_title}_Ch{start_c}_to_Ch{end_c}{speed_tag}_timeline.json"
        json_download_url = f"/api/novels/{novel_id}/audio/export_timeline_json?start_chapter={start_c}&end_chapter={end_c}&speed={effective_speed}"

        result_bundles.append({
            "part": idx + 1,
            "title": f"Tập {idx + 1}: Chương {start_c} → Chương {end_c}",
            "start_chapter": start_c,
            "end_chapter": end_c,
            "chapter_count": len(ch_list),
            "duration_seconds": round(dur_scaled, 1),
            "duration_hours": round(dur_scaled / 3600, 2),
            "duration_formatted": dur_formatted,
            "speed": effective_speed,
            "filename": merged_filename,
            "is_merged": is_merged,
            "file_size": file_sz_str,
            "download_url": f"/api/novels/{novel_id}/audio/download/{merged_filename}" if is_merged else "",
            "json_filename": json_filename,
            "json_download_url": json_download_url
        })

    return {
        "status": "success",
        "speed": effective_speed,
        "total_audio_chapters": len(cached_items),
        "total_bundles": len(result_bundles),
        "bundles": result_bundles
    }

@router.get("/download/{filename}")
async def download_audio_file(
    novel_id: int = Path(...),
    filename: str = Path(...)
):
    """FileResponse cho phép tải xuống hoặc chơi trực tiếp tệp audio trên browser/mobile với hỗ trợ Range Streaming"""
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
        
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename,
        headers={"Accept-Ranges": "bytes"}
    )

@router.delete("/files/{filename}")
@router.post("/delete_file/{filename}")
async def delete_audio_file(
    novel_id: int = Path(...),
    filename: str = Path(...)
):
    """Xóa một tệp âm thanh cụ thể trên đĩa + dọn dẹp bộ nhớ đệm chương & text TTS để ép đọc bản dịch mới"""
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
            except Exception:
                pass

        # Dọn dẹp sạch cache chương và text 04b_VanBanTTS
        if os.path.exists(chapters_cache_dir):
            shutil.rmtree(chapters_cache_dir, ignore_errors=True)
            os.makedirs(chapters_cache_dir, exist_ok=True)
        if os.path.exists(tts_text_novel_dir):
            shutil.rmtree(tts_text_novel_dir, ignore_errors=True)

        # Xóa các bản ghi TTS_TEXT và AUDIO trong DB
        from sqlalchemy import delete
        stmt_ch_ids = select(Chapter.id).where(Chapter.novel_id == novel_id)
        ch_res = await session.execute(stmt_ch_ids)
        c_ids = ch_res.scalars().all()
        if c_ids:
            stmt_del_ver = delete(ChapterVersion).where(
                ChapterVersion.chapter_id.in_(c_ids),
                ChapterVersion.version_type.in_(["TTS_TEXT", "AUDIO"])
            )
            await session.execute(stmt_del_ver)
            await session.commit()

        return {"status": "success", "message": f"Đã xóa thành công tệp {filename} và làm sạch toàn bộ bộ nhớ đệm audio & text TTS."}

@router.delete("/chapters/{chapter_no}")
@router.post("/delete_chapter/{chapter_no}")
async def delete_single_chapter_audio(
    novel_id: int = Path(...),
    chapter_no: int = Path(...)
):
    """Xóa file Audio MP3 và file 04b_VanBanTTS của 1 chương lẻ để chuẩn bị tạo lại từ bản dịch mới nhất"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
        base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
        base_tts_text_dir = r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS"
        novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
        
        # 1. Xóa file mp3 chương và file json subtitle
        chapters_cache_dir = os.path.join(base_audio_dir, novel_folder, "chapters")
        found_p = _find_chapter_audio_path(chapters_cache_dir, chapter_no)
        if found_p and os.path.exists(found_p):
            try:
                os.remove(found_p)
            except Exception:
                pass

        found_j = _find_chapter_json_path(chapters_cache_dir, chapter_no)
        if found_j and os.path.exists(found_j):
            try:
                os.remove(found_j)
            except Exception:
                pass
                
        # 2. Xóa file 04b_VanBanTTS
        tts_txt_p = os.path.join(base_tts_text_dir, novel_folder, "chapters", f"{chapter_no:06d}.txt")
        if os.path.exists(tts_txt_p):
            try:
                os.remove(tts_txt_p)
            except Exception:
                pass
                
        # 3. Xóa thư mục tạm _tmp_ch nếu có
        tmp_ch = os.path.join(chapters_cache_dir, f"_tmp_ch{chapter_no:06d}")
        if os.path.exists(tmp_ch):
            try:
                shutil.rmtree(tmp_ch, ignore_errors=True)
            except Exception:
                pass
                
        # 4. Xóa bản ghi trong DB
        stmt_ch = select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapter_no)
        res_ch = await session.execute(stmt_ch)
        db_ch_id = res_ch.scalar_one_or_none()
        if db_ch_id:
            from sqlalchemy import delete
            stmt_del = delete(ChapterVersion).where(
                ChapterVersion.chapter_id == db_ch_id,
                ChapterVersion.version_type.in_(["TTS_TEXT", "AUDIO"])
            )
            await session.execute(stmt_del)
            await session.commit()
            
        return {"status": "success", "message": f"Đã xóa Audio và văn bản TTS chương {chapter_no} thành công!"}

@router.delete("/files")
@router.post("/delete_all")
async def delete_all_audio_files(novel_id: int = Path(...)):
    """Xóa toàn bộ các tệp âm thanh + cache chương và text TTS của truyện"""
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
                    shutil.rmtree(novel_audio_dir, ignore_errors=True)
                if os.path.exists(tts_text_novel_dir):
                    shutil.rmtree(tts_text_novel_dir, ignore_errors=True)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Lỗi khi xóa thư mục: {str(e)}")

        # Xóa các bản ghi TTS_TEXT và AUDIO trong DB
        from sqlalchemy import delete
        stmt_ch_ids = select(Chapter.id).where(Chapter.novel_id == novel_id)
        ch_res = await session.execute(stmt_ch_ids)
        c_ids = ch_res.scalars().all()
        if c_ids:
            stmt_del_ver = delete(ChapterVersion).where(
                ChapterVersion.chapter_id.in_(c_ids),
                ChapterVersion.version_type.in_(["TTS_TEXT", "AUDIO"])
            )
            await session.execute(stmt_del_ver)
            await session.commit()
            
        return {"status": "success", "message": "Đã xóa toàn bộ thư mục âm thanh và bộ nhớ đệm của truyện thành công."}


def _find_chapter_audio_path(chapters_dir: str, c_no: int) -> Optional[str]:
    if not os.path.exists(chapters_dir):
        return None
    candidates = [
        f"{c_no:06d}.mp3",
        f"{c_no:05d}.mp3",
        f"{c_no:04d}.mp3",
        f"{c_no}.mp3"
    ]
    for c in candidates:
        p = os.path.join(chapters_dir, c)
        if os.path.exists(p) and os.path.getsize(p) > 100:
            return p
    return None


def _find_chapter_json_path(chapters_dir: str, c_no: int) -> Optional[str]:
    if not os.path.exists(chapters_dir):
        return None
    candidates = [
        f"{c_no:06d}.json",
        f"{c_no:05d}.json",
        f"{c_no:04d}.json",
        f"{c_no}.json"
    ]
    for c in candidates:
        p = os.path.join(chapters_dir, c)
        if os.path.exists(p) and os.path.getsize(p) > 10:
            return p
    return None


@router.get("/playlist")
async def get_audio_playlist(novel_id: int = Path(...)):
    """
    Trả về danh sách Playlist đầy đủ tất cả các chương của truyện từ đầu đến cuối
    kèm trạng thái file audio từng chương.
    """
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
        base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
        novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
        chapters_audio_dir = os.path.join(base_audio_dir, novel_folder, "chapters")

        # 1. Lấy tất cả chương của truyện
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
        res_ch = await session.execute(stmt_ch)
        all_chapters = res_ch.scalars().all()
        ch_ids = [c.id for c in all_chapters]

        # 2. Lấy danh sách chapter_id có bản dịch ĐÃ HOÀN TẤT KẾT QUẢ (FINAL / AUDIO)
        trans_chapter_ids = set()
        if ch_ids:
            stmt_ver = select(ChapterVersion.chapter_id).where(
                ChapterVersion.chapter_id.in_(ch_ids),
                ChapterVersion.version_type.in_(["FINAL", "AUDIO"])
            )
            res_ver = await session.execute(stmt_ver)
            trans_chapter_ids = set(res_ver.scalars().all())

        ketqua_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\04_KetQua", novel_folder, "chapters")

        playlist = []
        created_count = 0
        for ch in all_chapters:
            found_p = _find_chapter_audio_path(chapters_audio_dir, ch.chapter_no)
            found_j = _find_chapter_json_path(chapters_audio_dir, ch.chapter_no)
            has_audio = found_p is not None
            has_json = (found_j is not None) or has_audio
            if has_audio:
                created_count += 1
                f_size = os.path.getsize(found_p)
                size_str = format_file_size(f_size)
            else:
                f_size = 0
                size_str = None

            # Chỉ đưa vào Playlist các chương đã có kết quả dịch (FINAL / file 04_KetQua) hoặc đã có audio
            has_ketqua_file = False
            if os.path.exists(ketqua_dir):
                k_path = os.path.join(ketqua_dir, f"{ch.chapter_no:06d}.txt")
                has_ketqua_file = os.path.exists(k_path) and os.path.getsize(k_path) > 0

            is_completed_translation = (
                ch.id in trans_chapter_ids
                or has_ketqua_file
                or has_audio
            )
            if not is_completed_translation:
                continue
                
            playlist.append({
                "chapter_no": ch.chapter_no,
                "title": ch.title_rough or ch.title_raw or f"Chương {ch.chapter_no}",
                "has_audio": has_audio,
                "has_json": has_json,
                "audio_url": f"/api/novels/{novel_id}/audio/stream_chapter/{ch.chapter_no}" if has_audio else None,
                "json_url": f"/api/novels/{novel_id}/audio/json/{ch.chapter_no}" if has_json else None,
                "file_size": size_str,
                "size_bytes": f_size
            })
            
        return {
            "status": "success",
            "novel_title": novel.title_rough or novel.title_raw,
            "total_chapters": len(playlist),
            "created_audio_count": created_count,
            "playlist": playlist
        }


@router.get("/stream_chapter/{chapter_no}")
async def stream_chapter_audio(novel_id: int = Path(...), chapter_no: int = Path(...)):
    """Phát trực tiếp hoặc tải tệp audio của một chương cụ thể hỗ trợ Range Stream"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    chapters_dir = os.path.join(base_audio_dir, novel_folder, "chapters")
    file_path = _find_chapter_audio_path(chapters_dir, chapter_no)
    
    if not file_path:
        raise HTTPException(status_code=404, detail=f"Chưa có tệp âm thanh cho chương {chapter_no}.")
        
    return FileResponse(file_path, media_type="audio/mpeg", filename=f"chapter_{chapter_no}.mp3")


@router.get("/json/{chapter_no}")
async def get_chapter_subtitle_json(
    novel_id: int = Path(...),
    chapter_no: int = Path(...)
):
    """Tải file JSON mốc thời gian phụ đề Karaoke của một chương lẻ"""
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")

    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    chapters_dir = os.path.join(base_audio_dir, novel_folder, "chapters")
    json_path = _find_chapter_json_path(chapters_dir, chapter_no)

    if json_path and os.path.exists(json_path):
        return FileResponse(json_path, media_type="application/json", filename=f"chap_{chapter_no:02d}.json")

    # Nếu chưa có JSON nhưng đã có Audio MP3 -> fallback tự sinh JSON từ text & duration
    audio_path = _find_chapter_audio_path(chapters_dir, chapter_no)
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail=f"Chưa có tệp âm thanh hoặc subtitle cho chương {chapter_no}.")

    from app.services.tts.pipeline import get_audio_duration_ffmpeg, _read_chapter_text_from_db_or_disk, sanitize_tts_text
    from app.services.tts.tts_exporter import estimate_chapter_json_from_text

    raw_text = ""
    ch_title = f"Chương {chapter_no}"
    async with AsyncSessionLocal() as session:
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapter_no)
        res_ch = await session.execute(stmt_ch)
        db_ch = res_ch.scalar_one_or_none()
        if db_ch:
            ch_title = db_ch.title_rough or db_ch.title_raw or ch_title
            raw_text = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, db_ch)

    clean_text = sanitize_tts_text(raw_text or "", chapter_no=chapter_no, chapter_title=ch_title)
    dur_str = get_audio_duration_ffmpeg(audio_path)
    dur_parts = [float(p) for p in dur_str.split(":")]
    tot_sec = dur_parts[0]*3600 + dur_parts[1]*60 + dur_parts[2] if len(dur_parts) == 3 else 60.0

    target_json_path = os.path.join(chapters_dir, f"{chapter_no:06d}.json")
    estimate_chapter_json_from_text(
        text=clean_text,
        total_duration_sec=tot_sec,
        chapter_no=chapter_no,
        chapter_title=ch_title,
        output_json_path=target_json_path
    )

    return FileResponse(target_json_path, media_type="application/json", filename=f"chap_{chapter_no:02d}.json")


@router.get("/export_timeline_json")
async def export_timeline_json(
    novel_id: int = Path(...),
    start_chapter: int = Query(..., ge=1),
    end_chapter: int = Query(..., ge=1),
    speed: float = Query(1.0, ge=0.25, le=4.0)
):
    """Xuất file JSON gộp toàn bộ timeline chuỗi chương (Karaoke Subtitle Full) hỗ trợ scale tốc độ (speed)"""
    if start_chapter > end_chapter:
        raise HTTPException(status_code=400, detail="Chương bắt đầu không được lớn hơn chương kết thúc.")

    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")

    base_audio_dir = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_audio_dir, novel_folder)
    chapters_dir = os.path.join(out_dir, "chapters")

    from app.services.tts.tts_exporter import merge_chapters_timeline, estimate_chapter_json_from_text
    from app.services.tts.pipeline import get_audio_duration_ffmpeg, _read_chapter_text_from_db_or_disk, sanitize_tts_text

    chapters_data_list = []
    
    async with AsyncSessionLocal() as session:
        for c_no in range(start_chapter, end_chapter + 1):
            json_p = _find_chapter_json_path(chapters_dir, c_no)
            if json_p and os.path.exists(json_p):
                try:
                    with open(json_p, "r", encoding="utf-8") as f:
                        chapters_data_list.append(json.load(f))
                    continue
                except Exception:
                    pass

            # Fallback nếu có file MP3 nhưng chưa có JSON
            audio_p = _find_chapter_audio_path(chapters_dir, c_no)
            if audio_p and os.path.exists(audio_p):
                stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id, Chapter.chapter_no == c_no)
                res_ch = await session.execute(stmt_ch)
                db_ch = res_ch.scalar_one_or_none()
                raw_text = ""
                ch_title = f"Chương {c_no}"
                if db_ch:
                    ch_title = db_ch.title_rough or db_ch.title_raw or ch_title
                    raw_text = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, db_ch)

                clean_text = sanitize_tts_text(raw_text or "", chapter_no=c_no, chapter_title=ch_title)
                dur_str = get_audio_duration_ffmpeg(audio_p)
                dur_parts = [float(p) for p in dur_str.split(":")]
                tot_sec = dur_parts[0]*3600 + dur_parts[1]*60 + dur_parts[2] if len(dur_parts) == 3 else 60.0

                target_json_path = os.path.join(chapters_dir, f"{c_no:06d}.json")
                c_data = estimate_chapter_json_from_text(
                    text=clean_text,
                    total_duration_sec=tot_sec,
                    chapter_no=c_no,
                    chapter_title=ch_title,
                    output_json_path=target_json_path
                )
                chapters_data_list.append(c_data)

    if not chapters_data_list:
        raise HTTPException(status_code=400, detail="Chưa có chương nào có file Audio hoặc Subtitle trong khoảng này.")

    # Thu thập độ dài thực tế của từng file MP3 để đồng bộ 100% với file MP3 ghép nối
    actual_durations = []
    for c_no in range(start_chapter, end_chapter + 1):
        audio_p = _find_chapter_audio_path(chapters_dir, c_no)
        if audio_p and os.path.exists(audio_p):
            dur_str = get_audio_duration_ffmpeg(audio_p)
            dur_parts = [float(p) for p in dur_str.split(":")]
            tot_sec = dur_parts[0]*3600 + dur_parts[1]*60 + dur_parts[2] if len(dur_parts) == 3 else 0.0
            actual_durations.append(round(tot_sec, 3))
        else:
            actual_durations.append(0.0)

    novel_title = novel.title_rough or novel.title_raw or novel.title
    speed_tag = f"_{speed}x" if abs(speed - 1.0) >= 0.01 else ""
    merged_filename = f"{novel_folder}_Ch{start_chapter}_to_Ch{end_chapter}{speed_tag}_timeline.json"
    merged_output_path = os.path.join(out_dir, merged_filename)

    merge_chapters_timeline(
        chapters_data_list=chapters_data_list,
        output_json_path=merged_output_path,
        novel_title=novel_title,
        actual_durations=actual_durations,
        speed=speed
    )

    return FileResponse(
        merged_output_path,
        media_type="application/json",
        filename=merged_filename
    )


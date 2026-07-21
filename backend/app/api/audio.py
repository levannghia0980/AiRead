import os
import logging
import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.models.models import Novel, Chapter
from app.services.audio.audio_engine import AudioBatcher, AudioTTSManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/novels", tags=["Audio Engine"])

# Global job tracking state for Audio generation
AUDIO_JOBS: Dict[int, Dict[str, Any]] = {}


async def _run_audio_generation_job(novel_id: int):
    """Background task running Audio generation for all completed chapters of a novel."""
    global AUDIO_JOBS
    
    AUDIO_JOBS[novel_id] = {
        "is_running": True,
        "status": "RUNNING",
        "progress_pct": 0,
        "current_volume": 1,
        "total_volumes": 0,
        "msg": "Đang chuẩn bị gom tập...",
        "generated_files": []
    }
    
    try:
        async with async_session() as db:
            novel = await db.get(Novel, novel_id)
            if not novel:
                AUDIO_JOBS[novel_id] = {"is_running": False, "status": "FAILED", "msg": "Không tìm thấy truyện"}
                return

            stmt = (
                select(Chapter)
                .where(Chapter.novel_id == novel_id, Chapter.status == "COMPLETED")
                .order_by(Chapter.chapter_no.asc())
            )
            result = await db.execute(stmt)
            chapters = list(result.scalars().all())

            if not chapters:
                AUDIO_JOBS[novel_id] = {
                    "is_running": False,
                    "status": "FAILED",
                    "msg": "Chưa có chương nào được dịch COMPLETED để tạo Audio"
                }
                return

            volumes = AudioBatcher.group_chapters_into_volumes(chapters)
            AUDIO_JOBS[novel_id]["total_volumes"] = len(volumes)
            AUDIO_JOBS[novel_id]["msg"] = f"Đã gom thành {len(volumes)} Tập Audio (3-4 tiếng/tập)"

            manager = AudioTTSManager()
            generated_files = []

            for idx, vol in enumerate(volumes):
                vol_no = vol["volume_no"]
                AUDIO_JOBS[novel_id]["current_volume"] = vol_no
                AUDIO_JOBS[novel_id]["msg"] = f"Đang tạo Tập {vol_no}/{len(volumes)} (Chương {vol['start_chapter']} - {vol['end_chapter']})..."

                async def _progress_cb(curr_ch: int, total_ch: int, ch_no: int):
                    pct = int(((idx + (curr_ch / total_ch)) / len(volumes)) * 100)
                    AUDIO_JOBS[novel_id]["progress_pct"] = pct
                    AUDIO_JOBS[novel_id]["msg"] = f"Tập {vol_no}/{len(volumes)}: Đang sinh Audio Chương {ch_no} ({curr_ch}/{total_ch})..."

                mp3_path = await manager.generate_volume_audio(
                    novel.title,
                    vol,
                    progress_callback=_progress_cb
                )

                if mp3_path and os.path.exists(mp3_path):
                    filename = os.path.basename(mp3_path)
                    size_mb = round(os.path.getsize(mp3_path) / (1024 * 1024), 2)
                    generated_files.append({
                        "filename": filename,
                        "volume_no": vol_no,
                        "start_chapter": vol["start_chapter"],
                        "end_chapter": vol["end_chapter"],
                        "estimated_hours": vol["estimated_hours"],
                        "size_mb": size_mb,
                        "path": mp3_path
                    })

            AUDIO_JOBS[novel_id] = {
                "is_running": False,
                "status": "COMPLETED",
                "progress_pct": 100,
                "msg": f"🎉 Đã sinh thành công {len(generated_files)} Tập Audio (3-4 tiếng/tập)!",
                "generated_files": generated_files
            }

    except Exception as e:
        logger.error(f"Lỗi khi chạy job sinh Audio cho novel {novel_id}: {e}")
        AUDIO_JOBS[novel_id] = {
            "is_running": False,
            "status": "FAILED",
            "msg": f"Lỗi sinh Audio: {str(e)}"
        }


@router.post("/{novel_id}/audio/generate")
async def start_audio_generation(
    novel_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Kích hoạt tiến trình ngầm sinh Audio Hoài My (1.75x) phân tập 3-4 tiếng."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    # Nếu đang chạy -> báo lỗi
    current_job = AUDIO_JOBS.get(novel_id, {})
    if current_job.get("is_running", False):
        return {"success": True, "message": "Tiến trình sinh Audio đang chạy...", "status": current_job}

    background_tasks.add_task(_run_audio_generation_job, novel_id)
    return {
        "success": True,
        "message": f"Đã kích hoạt tiến trình tạo Audio Hoài My 1.75x cho truyện '{novel.title}'."
    }


@router.get("/{novel_id}/audio/status")
async def get_audio_generation_status(novel_id: int):
    """Lấy trạng thái và tiến độ tiến trình sinh Audio."""
    job_info = AUDIO_JOBS.get(novel_id, {
        "is_running": False,
        "status": "IDLE",
        "progress_pct": 0,
        "msg": "Chưa có tiến trình sinh Audio nào được khởi tạo.",
        "generated_files": []
    })
    return job_info


@router.get("/{novel_id}/audio/volumes")
async def get_novel_audio_volumes(novel_id: int, db: AsyncSession = Depends(get_db)):
    """Trả về danh sách tất cả các Tập Audio dự kiến kèm trạng thái Đã Tạo vs Chưa Tạo."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id, Chapter.status == "COMPLETED")
        .order_by(Chapter.chapter_no.asc())
    )
    result = await db.execute(stmt)
    chapters = list(result.scalars().all())

    if not chapters:
        return {"novel_title": novel.title, "total_volumes": 0, "volumes": []}

    volumes = AudioBatcher.group_chapters_into_volumes(chapters)

    invalid_chars = '<>:"/\\|?*\r\n\t'
    safe_title = "".join(c for c in novel.title if c not in invalid_chars).strip().replace("  ", " ")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    audio_folder = os.path.join(BASE_DIR, "output", safe_title, "audio")

    volume_list = []
    for vol in volumes:
        v_no = vol["volume_no"]
        start_ch = vol["start_chapter"]
        end_ch = vol["end_chapter"]
        filename = f"{safe_title} - Tập {v_no:02d} (Chương {start_ch:04d} - Chương {end_ch:04d}).mp3"
        filepath = os.path.join(audio_folder, filename)

        is_created = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2) if is_created else 0.0

        volume_list.append({
            "volume_no": v_no,
            "start_chapter": start_ch,
            "end_chapter": end_ch,
            "chapter_count": len(vol["chapters"]),
            "word_count": vol["word_count"],
            "estimated_hours": vol["estimated_hours"],
            "is_created": is_created,
            "filename": filename,
            "size_mb": size_mb,
            "download_url": f"/api/novels/{novel_id}/audio/download/{filename}" if is_created else None
        })

    return {
        "novel_title": novel.title,
        "total_volumes": len(volume_list),
        "created_volumes_count": sum(1 for v in volume_list if v["is_created"]),
        "volumes": volume_list
    }


async def _run_single_volume_generation(novel_id: int, volume_no: int):
    """Background task generating a single targeted volume."""
    global AUDIO_JOBS
    
    AUDIO_JOBS[novel_id] = {
        "is_running": True,
        "status": "RUNNING",
        "progress_pct": 0,
        "current_volume": volume_no,
        "total_volumes": 1,
        "msg": f"Đang chuẩn bị sinh Tập {volume_no}...",
        "generated_files": []
    }

    try:
        async with async_session() as db:
            novel = await db.get(Novel, novel_id)
            if not novel:
                AUDIO_JOBS[novel_id] = {"is_running": False, "status": "FAILED", "msg": "Không tìm thấy truyện"}
                return

            stmt = (
                select(Chapter)
                .where(Chapter.novel_id == novel_id, Chapter.status == "COMPLETED")
                .order_by(Chapter.chapter_no.asc())
            )
            result = await db.execute(stmt)
            chapters = list(result.scalars().all())
            volumes = AudioBatcher.group_chapters_into_volumes(chapters)

            target_vol = next((v for v in volumes if v["volume_no"] == volume_no), None)
            if not target_vol:
                AUDIO_JOBS[novel_id] = {"is_running": False, "status": "FAILED", "msg": f"Không tìm thấy Tập {volume_no}"}
                return

            manager = AudioTTSManager()
            async def _progress_cb(curr_ch: int, total_ch: int, ch_no: int):
                pct = int((curr_ch / total_ch) * 100)
                AUDIO_JOBS[novel_id]["progress_pct"] = pct
                AUDIO_JOBS[novel_id]["msg"] = f"Tập {volume_no}: Đang sinh Audio Chương {ch_no} ({curr_ch}/{total_ch})..."

            mp3_path = await manager.generate_volume_audio(novel.title, target_vol, progress_callback=_progress_cb)
            if mp3_path and os.path.exists(mp3_path):
                filename = os.path.basename(mp3_path)
                size_mb = round(os.path.getsize(mp3_path) / (1024 * 1024), 2)
                AUDIO_JOBS[novel_id] = {
                    "is_running": False,
                    "status": "COMPLETED",
                    "progress_pct": 100,
                    "msg": f"🎉 Đã tạo xong Tập {volume_no:02d}: {filename}!",
                    "generated_files": [{
                        "filename": filename,
                        "volume_no": volume_no,
                        "size_mb": size_mb,
                        "path": mp3_path
                    }]
                }
    except Exception as e:
        logger.error(f"Lỗi khi sinh Tập {volume_no} cho novel {novel_id}: {e}")
        AUDIO_JOBS[novel_id] = {"is_running": False, "status": "FAILED", "msg": f"Lỗi sinh Tập {volume_no}: {e}"}


@router.post("/{novel_id}/audio/generate_volume/{volume_no}")
async def generate_single_volume(
    novel_id: int,
    volume_no: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Kích hoạt tiến trình sinh lẻ 1 Tập Audio cụ thể."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    current_job = AUDIO_JOBS.get(novel_id, {})
    if current_job.get("is_running", False):
        return {"success": True, "message": "Đang có tiến trình sinh Audio khác chạy...", "status": current_job}

    background_tasks.add_task(_run_single_volume_generation, novel_id, volume_no)
    return {
        "success": True,
        "message": f"Đã kích hoạt sinh Tập {volume_no:02d} cho truyện '{novel.title}'."
    }


@router.get("/{novel_id}/audio/files")
async def get_created_audio_files(
    novel_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Liệt kê toàn bộ danh sách tất cả các file Audio MP3 đã được tạo thành công của bộ truyện này."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    invalid_chars = '<>:"/\\|?*\r\n\t'
    safe_title = "".join(c for c in novel.title if c not in invalid_chars).strip().replace("  ", " ")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    audio_folder = os.path.join(BASE_DIR, "output", safe_title, "audio")

    files_list = []
    if os.path.exists(audio_folder):
        for fname in sorted(os.listdir(audio_folder)):
            if fname.endswith(".mp3"):
                fpath = os.path.join(audio_folder, fname)
                size_mb = round(os.path.getsize(fpath) / (1024 * 1024), 2)
                files_list.append({
                    "filename": fname,
                    "size_mb": size_mb,
                    "download_url": f"/api/novels/{novel_id}/audio/download/{fname}"
                })

    return {
        "novel_title": novel.title,
        "total_files": len(files_list),
        "files": files_list
    }


@router.get("/{novel_id}/audio/download/{filename}")
async def download_audio_file(
    novel_id: int,
    filename: str,
    db: AsyncSession = Depends(get_db)
):
    """Tải / Trích xuất luồng Audio MP3 trực tiếp cho giao diện Trình Phát Truyện."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    invalid_chars = '<>:"/\\|?*\r\n\t'
    safe_title = "".join(c for c in novel.title if c not in invalid_chars).strip().replace("  ", " ")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    filepath = os.path.join(BASE_DIR, "output", safe_title, "audio", filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File Audio không tồn tại")

    return FileResponse(
        path=filepath,
        media_type="audio/mpeg",
        filename=filename
    )



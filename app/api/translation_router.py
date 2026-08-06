import asyncio
import json
import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter

router = APIRouter(prefix="/translation", tags=["Translation"])

# Global SSE broadcast & job state
_SSE_CLIENTS = set()
_LOG_HISTORY: List[Dict[str, str]] = []
_CURRENT_PROGRESS: Dict[str, Any] = {
    "isRunning": False,
    "stage": "IDLE",
    "completedChapters": 0,
    "totalChapters": 0
}
_CURRENT_TASK: Optional[asyncio.Task] = None
_PAUSE_EVENT = asyncio.Event()
_PAUSE_EVENT.set() # Default: running (not paused)

def broadcast_sse(event_type: str, data: Any):
    """Gửi sự kiện real-time tới tất cả client đang kết nối SSE"""
    global _CURRENT_PROGRESS
    if event_type == "log":
        _LOG_HISTORY.append(data)
        if len(_LOG_HISTORY) > 500:
            _LOG_HISTORY.pop(0)
    elif event_type == "progress":
        _CURRENT_PROGRESS = data

    payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
    dead_clients = set()
    for q in list(_SSE_CLIENTS):
        try:
            q.put_nowait(payload)
        except Exception:
            dead_clients.add(q)
    for q in dead_clients:
        _SSE_CLIENTS.discard(q)

def add_system_log(msg: str, level: str = "info"):
    timestamp = time.strftime("%H:%M:%S")
    log_entry = {"time": timestamp, "message": msg, "level": level}
    broadcast_sse("log", log_entry)

@router.get("/logs")
async def sse_logs(request: Request):
    """
    Server-Sent Events (SSE) stream nhận log real-time và tiến độ cho Frontend
    """
    queue = asyncio.Queue()
    _SSE_CLIENTS.add(queue)

    async def event_generator():
        # Gửi dữ liệu ban đầu
        yield f"data: {json.dumps({'event': 'init_logs', 'data': _LOG_HISTORY}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'event': 'progress', 'data': _CURRENT_PROGRESS}, ensure_ascii=False)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await queue.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _SSE_CLIENTS.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

class StartTranslationRequest(BaseModel):
    novel_id: int
    provider: Optional[str] = "openrouter"
    model: Optional[str] = "openrouter/free"
    api_key: Optional[str] = ""
    prompt: Optional[str] = ""
    delay: Optional[float] = 0.5
    batch_size: Optional[int] = 3
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None
    translation_style: Optional[str] = "original_only"
    enable_unblock: Optional[bool] = False
    enable_llm_extract: Optional[bool] = True
    enable_names_dict: Optional[bool] = True
    enable_gg_corrections: Optional[bool] = True

async def _bg_translation_worker(payload: StartTranslationRequest):
    global _CURRENT_PROGRESS, _PAUSE_EVENT
    from app.services.translation.pipeline import run_translation_batch_pipeline
    try:
        add_system_log(f"🚀 Bắt đầu tiến trình dịch cho bộ truyện ID {payload.novel_id}...", "info")
        broadcast_sse("progress", {
            "isRunning": True,
            "novelId": payload.novel_id,
            "stage": "TRANSLATING",
            "completedChapters": 0,
            "totalChapters": 0
        })

        # Cập nhật API Key & Settings tạm thời vào env nếu truyền lên
        if payload.api_key:
            import os
            os.environ["AIREAD_API_KEYS"] = payload.api_key
        if payload.provider:
            import os
            os.environ["AIREAD_PROVIDER"] = payload.provider
        if payload.model:
            import os
            os.environ["AIREAD_MODEL"] = payload.model

        flow = "contextt" if payload.translation_style in ["draft_only", "edited_only", "contextt"] else "rawt"
        start_ch = payload.start_chapter or 0
        end_ch = payload.end_chapter or 0
        batch_sz = payload.batch_size if (payload.batch_size is not None and payload.batch_size > 0) else 3
        delay_s = payload.delay if (payload.delay is not None and payload.delay >= 0) else 0.5

        res = await run_translation_batch_pipeline(
            novel_id=payload.novel_id,
            translation_flow=flow,
            batch_size=batch_sz,
            delay_sec=delay_s,
            start_chapter=start_ch,
            end_chapter=end_ch,
            enable_llm_extract=payload.enable_llm_extract if payload.enable_llm_extract is not None else True,
            enable_names_dict=payload.enable_names_dict if payload.enable_names_dict is not None else True,
            enable_gg_corrections=payload.enable_gg_corrections if payload.enable_gg_corrections is not None else True,
            enable_unblock=payload.enable_unblock if payload.enable_unblock is not None else True
        )

        if res.get("status") == "completed":
            add_system_log(f"🎉 Hoàn tất dịch bộ truyện ID {payload.novel_id}! Tổng số chương: {res.get('total_chapters')}", "success")
            from app.services.postprocessing.post_processor import export_full_novel_txt
            exp = await export_full_novel_txt(payload.novel_id)
            broadcast_sse("packaged", {
                "success": True,
                "title": exp.get("title", ""),
                "txt": exp.get("file_path"),
                "txt_clean": exp.get("file_path"),
                "html": None,
                "docx": None,
                "epub": None
            })
        else:
            add_system_log(f"⚠️ Tiến trình dịch hoàn tất với trạng thái: {res.get('message', res.get('status'))}", "warning")

    except asyncio.CancelledError:
        add_system_log("🛑 Tiến trình dịch đã bị hủy bởi người dùng.", "warning")
    except Exception as e:
        add_system_log(f"❌ Lỗi tiến trình dịch: {str(e)}", "error")
    finally:
        broadcast_sse("progress", {
            "isRunning": False,
            "novelId": payload.novel_id,
            "stage": "FINISHED"
        })

@router.post("/start")
async def start_translation(payload: StartTranslationRequest):
    """
    Bắt đầu dịch tự động bộ truyện cho Frontend
    """
    global _CURRENT_TASK
    if _CURRENT_TASK and not _CURRENT_TASK.done():
        raise HTTPException(status_code=400, detail="Đang có tiến trình dịch khác đang chạy. Vui lòng dừng hoặc chờ hoàn tất.")

    _CURRENT_TASK = asyncio.create_task(_bg_translation_worker(payload))
    return {"status": "success", "message": "Đã khởi chạy tiến trình dịch tự động."}

@router.post("/pause")
async def pause_translation():
    """
    Tạm dừng / Dừng tiến trình dịch
    """
    global _CURRENT_TASK
    if _CURRENT_TASK and not _CURRENT_TASK.done():
        _CURRENT_TASK.cancel()
        _CURRENT_TASK = None
    add_system_log("⏸️ Đã nhận lệnh tạm dừng dịch.", "warning")
    broadcast_sse("progress", {"isRunning": False, "stage": "PAUSED"})
    return {"status": "success", "message": "Đã tạm dừng tiến trình dịch."}

@router.post("/clear")
async def clear_job():
    """
    Xóa tiến trình & làm sạch log
    """
    global _LOG_HISTORY, _CURRENT_PROGRESS, _CURRENT_TASK
    if _CURRENT_TASK and not _CURRENT_TASK.done():
        _CURRENT_TASK.cancel()
        _CURRENT_TASK = None
    _LOG_HISTORY.clear()
    _CURRENT_PROGRESS = {"isRunning": False, "stage": "IDLE"}
    broadcast_sse("progress", _CURRENT_PROGRESS)
    return {"status": "success", "message": "Đã xóa job và dọn dẹp log."}

class ExportRequest(BaseModel):
    novel_id: int

@router.post("/export")
async def manual_export(payload: ExportRequest):
    """
    Xuất file truyện đóng gói cho Frontend
    """
    from app.services.postprocessing.post_processor import export_full_novel_txt
    try:
        exp = await export_full_novel_txt(payload.novel_id)
        res = {
            "success": True,
            "title": exp.get("title", ""),
            "txt": exp.get("file_path"),
            "txt_clean": exp.get("file_path"),
            "html": None,
            "docx": None,
            "epub": None
        }
        broadcast_sse("packaged", res)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TestKeyRequest(BaseModel):
    provider: str
    model: str
    api_key: str

@router.post("/test-key")
async def test_key(payload: TestKeyRequest):
    """
    Kiểm tra tính hợp lệ của API Key
    """
    from app.api.settings_router import test_api_connection, TestConnectionPayload
    req = TestConnectionPayload(
        provider=payload.provider,
        model=payload.model if payload.model in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"] else "gemini-3.5-flash-lite",
        api_key=payload.api_key
    )
    res = await test_api_connection(req)
    return {"success": res.get("status") == "success", "message": res.get("message")}

class SetContextRequest(BaseModel):
    context_profile: str

@router.put("/novel/{novel_id}/context")
async def set_novel_context(novel_id: int, payload: SetContextRequest):
    valid_profiles = ["urban", "xianxia", "wuxia"]
    if payload.context_profile.lower() not in valid_profiles:
        raise HTTPException(status_code=400, detail=f"Ngữ cảnh không hợp lệ: {valid_profiles}")

    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
        novel.context_profile = payload.context_profile.lower()
        await session.commit()
        
    return {
        "status": "success",
        "message": f"Đã thiết lập ngữ cảnh '{payload.context_profile}' cho truyện '{novel.title_raw}'."
    }

class PipelineRunRequest(BaseModel):
    translation_flow: str # rawt, contextt
    start_chapter: int = 0
    end_chapter: int = 0
    batch_size: int = 3
    delay_sec: float = 2.0
    enable_unblock: Optional[bool] = False

@router.post("/novel/{novel_id}/pipeline/start")
async def start_translation_pipeline(novel_id: int, payload: PipelineRunRequest):
    from app.services.translation.pipeline import run_translation_batch_pipeline
    
    if payload.translation_flow not in ["rawt", "contextt"]:
        raise HTTPException(status_code=400, detail="Luồng dịch không hợp lệ (phải là rawt hoặc contextt)")
        
    try:
        result = await run_translation_batch_pipeline(
            novel_id=novel_id,
            translation_flow=payload.translation_flow,
            batch_size=payload.batch_size,
            delay_sec=payload.delay_sec,
            start_chapter=payload.start_chapter,
            end_chapter=payload.end_chapter,
            enable_unblock=payload.enable_unblock or False
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/novel/{novel_id}/batch-fix-swept-errors")
async def batch_fix_swept_errors(novel_id: int):
    """
    Quét tìm lỗi Hán tự bị gạch chân xanh (<span class='swept-chinese'>) trong các chương dịch
    và gửi 1 request LLM duy nhất để dịch chuẩn lại toàn bộ, sau đó tự động chèn lại vào file.
    """
    from app.services.postprocessing.translation_auditor import batch_fix_swept_errors_llm
    try:
        add_system_log(f"🔍 Đang quét và sửa lỗi Hán tự gạch chân xanh cho truyện ID {novel_id}...", "info")
        result = await batch_fix_swept_errors_llm(novel_id)
        if result.get("status") == "success":
            fixed_count = result.get("fixed_count", 0)
            if fixed_count > 0:
                add_system_log(f"✅ Sửa thành công {fixed_count} lỗi Hán tự gạch chân xanh!", "success")
            else:
                add_system_log(f"ℹ️ Không tìm thấy lỗi gạch chân xanh nào cần sửa.", "info")
        else:
            add_system_log(f"⚠️ Sửa lỗi Hán tự thất bại: {result.get('message')}", "danger")
        return result
    except Exception as e:
        add_system_log(f"❌ Lỗi hệ thống khi sửa lỗi Hán tự: {str(e)}", "danger")
        raise HTTPException(status_code=500, detail=str(e))

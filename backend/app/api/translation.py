import asyncio
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import httpx

from app.core.database import get_db, async_session
from app.services.queue.worker import job_manager
from app.services.exporter.packager import NovelPackager

router = APIRouter(prefix="/api/translation", tags=["Translation"])

class StartTranslationRequest(BaseModel):
    novel_id: int
    provider: str
    model: str
    api_key: str
    prompt: Optional[str] = ""
    delay: Optional[float] = 3.0
    concurrency: Optional[int] = 3
    start_chapter: Optional[int] = None
    end_chapter: Optional[int] = None

class TestKeyRequest(BaseModel):
    provider: str
    model: str
    api_key: str

class ExportRequest(BaseModel):
    novel_id: int

@router.post("/test-key")
async def test_api_key(payload: TestKeyRequest):
    """Tests if the provided API key is valid by sending a minimal request."""
    provider = payload.provider.lower()
    model = payload.model
    api_key = payload.api_key.split(";")[0].strip()  # Test with first key only
    
    if not api_key:
        return {"success": False, "message": "API Key không được để trống."}
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload_data = {
                    "contents": [{"parts": [{"text": "Trả lời đúng 1 từ: Xin chào"}]}],
                    "generationConfig": {"maxOutputTokens": 32}
                }
                resp = await client.post(url, json=payload_data, headers={"Content-Type": "application/json"})
            elif provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                payload_data = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Trả lời đúng 1 từ: Xin chào"}],
                    "max_tokens": 32
                }
                resp = await client.post(url, json=payload_data, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
            elif provider == "openrouter":
                url = "https://openrouter.ai/api/v1/chat/completions"
                payload_data = {
                    "model": model if model else "deepseek/deepseek-chat",
                    "messages": [{"role": "user", "content": "Trả lời đúng 1 từ: Xin chào"}],
                    "max_tokens": 16
                }
                resp = await client.post(url, json=payload_data, headers={
                    "Content-Type": "application/json", 
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/airead/airead2",
                    "X-Title": "AiRead v2"
                })
            elif provider == "claude":
                url = "https://api.anthropic.com/v1/messages"
                payload_data = {
                    "model": model,
                    "max_tokens": 32,
                    "messages": [{"role": "user", "content": "Trả lời đúng 1 từ: Xin chào"}]
                }
                resp = await client.post(url, json=payload_data, headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"})
            else:
                return {"success": False, "message": f"Provider không hợp lệ: {provider}"}
            
            if resp.status_code == 200:
                return {"success": True, "message": f"✅ Key hợp lệ! Model '{model}' phản hồi thành công."}
            else:
                error_detail = resp.text[:300]
                return {"success": False, "message": f"❌ Lỗi {resp.status_code}: {error_detail}"}
    except httpx.TimeoutException:
        return {"success": False, "message": "⏳ Hết thời gian chờ kết nối (timeout 20s)."}
    except Exception as e:
        return {"success": False, "message": f"❌ Lỗi kết nối: {str(e)}"}

@router.post("/start")
async def start_translation(payload: StartTranslationRequest):
    """Starts/resumes the translation job for a novel."""
    if not payload.api_key or not payload.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key không được để trống. Vui lòng cấu hình API Key trên giao diện.")
    try:
        config = {
            "provider": payload.provider,
            "model": payload.model,
            "api_key": payload.api_key,
            "prompt": payload.prompt,
            "delay": payload.delay,
            "concurrency": payload.concurrency,
            "start_chapter": payload.start_chapter,
            "end_chapter": payload.end_chapter
        }
        await job_manager.start_job(payload.novel_id, config)
        return {"success": True, "message": "Đã bắt đầu tiến trình dịch."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/pause")
async def pause_translation():
    """Pauses the active translation job."""
    await job_manager.pause_job()
    return {"success": True, "message": "Đã tạm dừng tiến trình."}

@router.post("/clear")
async def clear_job():
    """Resets the job manager state."""
    await job_manager.clear_job()
    return {"success": True, "message": "Đã xóa trạng thái công việc."}

@router.post("/export")
async def export_novel(payload: ExportRequest):
    """Manually compiles and packages completed chapters."""
    async with async_session() as db:
        try:
            packager = NovelPackager(output_dir="output")
            result = await packager.package_novel(db, payload.novel_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi đóng gói: {str(e)}")

@router.get("/logs")
async def get_logs_stream(request: Request):
    """SSE Event Stream yielding logs and progress data in real-time."""
    async def event_generator():
        # Setup SSE subscriber queue
        queue = asyncio.Queue()
        job_manager.subscribers.append(queue)
        
        # Stream historical logs
        yield f"data: {json.dumps({'event': 'init_logs', 'data': job_manager.logs})}\n\n"
        
        # Send initial status if novel is loaded
        async with async_session() as db:
            progress = await job_manager.get_progress(db)
            yield f"data: {json.dumps({'event': 'progress', 'data': progress})}\n\n"
            
        try:
            while True:
                # Check client disconnect
                if await request.is_disconnected():
                    break
                    
                try:
                    # Await messages from queue
                    msg = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # SSE Keep-alive heartbeat
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in job_manager.subscribers:
                job_manager.subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

"""
FastAPI Server cho Grok API (Port 8020)
Cho phép gửi yêu cầu dịch thuật tới Grok Web qua HTTP REST API.
"""

import sys
import os
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from fastapi.middleware.cors import CORSMiddleware
from src.api.grok_tool import GrokTool

app = FastAPI(title="Grok API Server", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
grok_tool: Optional[GrokTool] = None


class TranslationRequest(BaseModel):
    text: str
    prompt: Optional[str] = None
    system_instruction: Optional[str] = None
    timeout: float = 180.0


@app.on_event("startup")
async def startup_event():
    global grok_tool
    print("🚀 [Grok API Server] Đang khởi tạo GrokTool...")
    grok_tool = GrokTool()
    
    async def _auto_open():
        try:
            print("🌐 [Grok API Server] Đang tự động mở cửa sổ Edge tới grok.com...")
            await grok_tool.start()
            await grok_tool.adapter.connect()
            print("✅ [Grok API Server] Cửa sổ Edge đã mở thành công trên màn hình!")
        except Exception as e:
            print(f"⚠️ [Grok API Server] Không thể tự động mở Edge: {e}")

    asyncio.create_task(_auto_open())



@app.on_event("shutdown")
async def shutdown_event():
    global grok_tool
    if grok_tool:
        print("🛑 [Grok API Server] Đang tắt Grok Browser Manager...")
        await grok_tool.close()


@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Grok API Server", "port": 8020}


@app.post("/connect")
@app.get("/connect")
async def connect_browser():
    global grok_tool
    if grok_tool is None:
        grok_tool = GrokTool()
    try:
        if grok_tool.page_controller is None or grok_tool.adapter is None:
            await grok_tool.start()
        await grok_tool.adapter.connect()
        has_session = await grok_tool._has_valid_session()
        if has_session:
            return {
                "status": "success",
                "message": "🟢 Đã kết nối Grok Web thành công! Trình duyệt Edge đã sẵn sàng dịch.",
                "has_session": True
            }
        else:
            return {
                "status": "warning",
                "message": "⚠️ Trình duyệt Edge đã mở trang grok.com! Vui lòng đăng nhập trên cửa sổ Edge để bắt đầu dịch.",
                "has_session": False
            }
    except Exception as e:
        return {"status": "error", "message": f"Lỗi khởi động Edge: {e}", "has_session": False}



@app.post("/relogin")
async def relogin():
    global grok_tool
    try:
        if grok_tool:
            if grok_tool.cookie_file.exists():
                grok_tool.cookie_file.unlink()
            # Yêu cầu khởi động lại browser flow nếu đang kết nối
            if grok_tool.page_controller and grok_tool.page_controller.page:
                try:
                    await grok_tool.page_controller.page.context.clear_cookies()
                except Exception:
                    pass
        return {"status": "success", "message": "Đã xóa phiên đăng nhập cũ. Vui lòng quay lại cửa sổ trình duyệt Edge đang mở để đăng nhập tài khoản Grok mới!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate-text")
@app.post("/translate")
async def translate_text(req: TranslationRequest):
    global grok_tool
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Văn bản cần dịch không được để trống")

    if grok_tool is None:
        grok_tool = GrokTool()

    prefix = req.system_instruction or req.prompt
    try:
        result = await grok_tool.request(
            text=req.text,
            prompt_prefix=prefix,
            timeout=req.timeout,
        )
        if not result:
            raise HTTPException(status_code=500, detail="Grok API không trả về kết quả")
        return {"status": "success", "translated_text": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8020, reload=False)

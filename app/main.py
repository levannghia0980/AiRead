import os
import sys
import subprocess

# Đảm bảo thư mục gốc dự án nằm trong sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.api.crawler_router import router as crawler_router
from app.api.dictionary_router import router as dictionary_router
from app.api.settings_router import router as settings_router
from app.api.unblock_router import router as unblock_router
from app.api.translation_router import router as translation_router
from app.api.novel_router import router as novel_router
from app.api.tts_router import router as tts_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lifecycle startup: Khởi tạo bảng trong DB
    await init_db()
    yield
    # Shutdown logic if needed

app = FastAPI(
    title="AIREAD Multi-Service API",
    description="Hệ thống cào & dịch truyện quy mô lớn (100k+ chương) chạy Async 24/7",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký router với cả tiền tố /api và không có tiền tố để tương thích 100% với Frontend và API direct
app.include_router(crawler_router, prefix="/api")
app.include_router(dictionary_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(unblock_router, prefix="/api")
app.include_router(translation_router, prefix="/api")
app.include_router(novel_router, prefix="/api")
app.include_router(tts_router, prefix="/api")

app.include_router(crawler_router)
app.include_router(dictionary_router)
app.include_router(settings_router)
app.include_router(unblock_router)
app.include_router(translation_router)
app.include_router(novel_router)
app.include_router(tts_router)

from fastapi.staticfiles import StaticFiles

# Phục vụ giao diện tĩnh Frontend (React build) nếu thư mục frontend/dist tồn tại
frontend_dist = os.path.join(PROJECT_ROOT, "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    @app.get("/")
    async def root():
        return {
            "status": "online",
            "service": "AIREAD FastAPI Backend",
            "docs_url": "/docs"
        }

def ensure_virtualenv():
    in_venv = (sys.prefix != sys.base_prefix) or hasattr(sys, 'real_prefix')
    if in_venv:
        return

    windows_venv_py = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    unix_venv_py = os.path.join(PROJECT_ROOT, "venv", "bin", "python")

    venv_py = None
    if os.path.exists(windows_venv_py):
        venv_py = windows_venv_py
    elif os.path.exists(unix_venv_py):
        venv_py = unix_venv_py

    if venv_py:
        print(f"[AIREAD] Phát hiện môi trường ảo tại '{venv_py}'. Đang tự động kích hoạt venv...")
        cmd = [venv_py] + sys.argv
        sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    ensure_virtualenv()

    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

import os
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.api.novels import router as novels_router
from app.api.translation import router as translation_router

app = FastAPI(title="AiRead Novel Translator API v2")

# Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory for exported books
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mount files download directory
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# Register routers
app.include_router(novels_router)
app.include_router(translation_router)

@app.on_event("startup")
async def startup_event():
    """Initializes tables on server startup."""
    await init_db()

# Serve static frontend builds if dist folder exists
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    async def index():
        return {
            "message": "FastAPI Backend is running.",
            "frontend": "Not built yet. Use Vite Dev Server."
        }

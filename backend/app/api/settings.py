"""
Settings API — đọc/ghi cấu hình API key vào file .env của backend.
Key được lưu tại: backend/.env (hoặc .venv/.env nếu chạy từ venv)
"""
import os
import re
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["Settings"])

# Đường dẫn file .env — ưu tiên backend root
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_BACKEND_DIR, ".env")


def _read_env_file() -> dict:
    """Đọc file .env và trả về dict key=value."""
    result = {}
    if not os.path.exists(_ENV_PATH):
        return result
    try:
        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    result[key.strip()] = val.strip()
    except Exception as e:
        logger.warning(f"Không thể đọc .env: {e}")
    return result


def _write_env_key(key: str, value: str):
    """Cập nhật hoặc thêm một key=value vào file .env, giữ nguyên phần còn lại."""
    lines = []
    found = False

    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped == key:
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # Thêm dòng mới cuối file
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    with open(_ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # Cập nhật biến môi trường trong process hiện tại ngay lập tức
    os.environ[key] = value
    logger.info(f"✅ .env cập nhật: {key}=***")


class SaveApiKeyRequest(BaseModel):
    api_keys: str
    provider: Optional[str] = ""
    model: Optional[str] = ""


class SaveSettingsRequest(BaseModel):
    api_keys: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    concurrency: Optional[int] = None
    delay: Optional[float] = None
    custom_prompt: Optional[str] = None


@router.get("")
async def get_settings():
    """Trả về cấu hình đang được lưu trong .env."""
    env = _read_env_file()
    return {
        "api_keys": env.get("AIREAD_API_KEYS", ""),
        "provider": env.get("AIREAD_PROVIDER", "openrouter"),
        "model": env.get("AIREAD_MODEL", "openrouter/free"),
        "concurrency": int(env.get("AIREAD_CONCURRENCY", "10")),
        "delay": float(env.get("AIREAD_DELAY", "0.5")),
        "custom_prompt": env.get("AIREAD_CUSTOM_PROMPT", ""),
        "env_path": _ENV_PATH,
    }


@router.post("/save")
async def save_settings(payload: SaveSettingsRequest):
    """Lưu toàn bộ settings vào file .env backend."""
    saved = []
    if payload.api_keys is not None:
        _write_env_key("AIREAD_API_KEYS", payload.api_keys)
        saved.append("api_keys")
    if payload.provider is not None:
        _write_env_key("AIREAD_PROVIDER", payload.provider)
        saved.append("provider")
    if payload.model is not None:
        _write_env_key("AIREAD_MODEL", payload.model)
        saved.append("model")
    if payload.concurrency is not None:
        _write_env_key("AIREAD_CONCURRENCY", str(payload.concurrency))
        saved.append("concurrency")
    if payload.delay is not None:
        _write_env_key("AIREAD_DELAY", str(payload.delay))
        saved.append("delay")
    if payload.custom_prompt is not None:
        _write_env_key("AIREAD_CUSTOM_PROMPT", payload.custom_prompt)
        saved.append("custom_prompt")

    return {
        "success": True,
        "message": f"✅ Đã lưu vào .env: {', '.join(saved)}",
        "env_path": _ENV_PATH,
        "saved": saved,
    }

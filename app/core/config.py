from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Cấu hình mặc định nạp từ file .env
    AIREAD_PROVIDER: str = "gemini"
    AIREAD_MODEL: str = "gemini-3.5-flash-lite"
    AIREAD_API_KEYS: str = ""
    AIREAD_CONCURRENCY: int = 15
    AIREAD_DELAY: float = 0.0
    AIREAD_BATCH_SIZE: int = 1
    AIREAD_TRANSLATION_STYLE: str = "draft_only"
    AIREAD_CUSTOM_PROMPT: Optional[str] = ""
    TTS_MAX_WORKERS: int = 1  # Số lượng worker TTS (1 luồng duy nhất đảm bảo độ ổn định và tránh rate-limit)
    TTS_RATE: str = "-4%"      # Tốc độ đọc Neural (phát âm rõ chữ, nhẹ nhàng, tự nhiên)
    TTS_PITCH: str = "+0Hz"    # Cao độ mặc định từ mô hình Neural Microsoft
    TTS_SILENCE_MS: int = 250  # Khoảng nghỉ (milliseconds) ngắt câu giữa các phân đoạn
    TTS_MAX_CHUNK_SIZE: int = 600  # 600 ký tự mỗi chunk theo đúng tính toán tối ưu
    TTS_PACING_SECONDS: float = 0.5  # 0.5s nghỉ giữa các chunk trong cùng 1 ống (worker)
    TTS_PARALLEL_WORKERS: int = 8    # 8 luồng song song mặc định, mỗi luồng giữ 1 proxy riêng biệt
    TTS_BATCH_PER_CONN: int = 5      # Số chunk mỗi WebSocket session trước khi xoay kết nối
    TTS_PROXY_LIST: str = ""         # Proxy HTTP/SOCKS5 xoay vòng (phân cách bằng dấu phẩy)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

async def get_active_setting(key: str) -> str:
    """
    Nạp giá trị cấu hình động:
    1. Ưu tiên tìm trong bảng settings của Database SQLite trước.
    2. Nếu không tìm thấy, fallback lấy từ cấu hình mặc định của file .env.
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.schema import Setting

    async with AsyncSessionLocal() as session:
        stmt = select(Setting).where(Setting.key == key)
        res = await session.execute(stmt)
        db_setting = res.scalar_one_or_none()
        if db_setting is not None:
            return db_setting.value

    # Fallback về .env qua Pydantic Settings
    val = getattr(settings, key, None)
    if val is not None:
        return str(val)
    return ""

async def get_all_active_settings() -> dict:
    """
    Hợp nhất và trả về toàn bộ cấu hình hệ thống đang hoạt động
    (Kết hợp giữa Database và các giá trị mặc định của file .env)
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.schema import Setting

    db_map = {}
    async with AsyncSessionLocal() as session:
        stmt = select(Setting)
        res = await session.execute(stmt)
        for row in res.scalars().all():
            db_map[row.key] = row.value

    # Defaults từ Settings class
    defaults = {
        "AIREAD_PROVIDER": settings.AIREAD_PROVIDER,
        "AIREAD_MODEL": settings.AIREAD_MODEL,
        "AIREAD_API_KEYS": settings.AIREAD_API_KEYS,
        "AIREAD_CONCURRENCY": str(settings.AIREAD_CONCURRENCY),
        "AIREAD_DELAY": str(settings.AIREAD_DELAY),
        "AIREAD_BATCH_SIZE": str(settings.AIREAD_BATCH_SIZE),
        "AIREAD_TRANSLATION_STYLE": settings.AIREAD_TRANSLATION_STYLE,
        "AIREAD_CUSTOM_PROMPT": settings.AIREAD_CUSTOM_PROMPT or "",
        "TTS_MAX_WORKERS": str(settings.TTS_MAX_WORKERS),
        "TTS_RATE": str(settings.TTS_RATE),
        "TTS_PITCH": str(settings.TTS_PITCH),
        "TTS_SILENCE_MS": str(settings.TTS_SILENCE_MS),
        "TTS_MAX_CHUNK_SIZE": str(settings.TTS_MAX_CHUNK_SIZE),
        "TTS_PACING_SECONDS": str(settings.TTS_PACING_SECONDS),
        "TTS_PARALLEL_WORKERS": str(settings.TTS_PARALLEL_WORKERS),
        "TTS_BATCH_PER_CONN": str(settings.TTS_BATCH_PER_CONN),
        "TTS_PROXY_LIST": str(settings.TTS_PROXY_LIST),
    }

    result = dict(defaults)
    result.update(db_map)
    return result


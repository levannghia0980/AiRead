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

    result = {
        "AIREAD_PROVIDER": str(settings.AIREAD_PROVIDER),
        "AIREAD_MODEL": str(settings.AIREAD_MODEL),
        "AIREAD_API_KEYS": str(settings.AIREAD_API_KEYS),
        "AIREAD_CONCURRENCY": str(settings.AIREAD_CONCURRENCY),
        "AIREAD_DELAY": str(settings.AIREAD_DELAY),
        "AIREAD_BATCH_SIZE": str(settings.AIREAD_BATCH_SIZE),
        "AIREAD_TRANSLATION_STYLE": str(settings.AIREAD_TRANSLATION_STYLE),
        "AIREAD_CUSTOM_PROMPT": str(settings.AIREAD_CUSTOM_PROMPT or ""),
    }

    async with AsyncSessionLocal() as session:
        stmt = select(Setting)
        res = await session.execute(stmt)
        for db_setting in res.scalars():
            result[db_setting.key] = db_setting.value

    return result


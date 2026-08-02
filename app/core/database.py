import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Mặc định sử dụng aiosqlite cho local SQLite database.db
DEFAULT_DB_PATH = Path("d:/NENGHIA0980/AIREAD/database.db").resolve()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}")

# Cấu hình Async Engine với Connection Pooling
if "postgresql" in DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600
    )
else:
    # SQLite async engine settings
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

async def get_db_session():
    """Dependency injection cho DB session"""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Khởi tạo bảng trong Database"""
    import app.models.schema  # Nạp toàn bộ ORM schema models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

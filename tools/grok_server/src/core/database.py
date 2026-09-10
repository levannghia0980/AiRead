import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
import aiosqlite
from loguru import logger

class DatabaseManager:
    """
    SQLite persistence layer for caching, task logging, metrics, and session tracking.
    """
    def __init__(self, db_path: str = "data/grok_engine.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Creates table schemas if they do not exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    prompt_hash TEXT PRIMARY KEY,
                    prompt TEXT,
                    response TEXT,
                    provider TEXT,
                    created_at REAL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    prompt TEXT,
                    response TEXT,
                    status TEXT,
                    error TEXT,
                    retry_count INTEGER,
                    created_at REAL,
                    completed_at REAL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    provider TEXT PRIMARY KEY,
                    status TEXT,
                    last_check REAL,
                    cookies_json TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    value REAL,
                    timestamp REAL
                )
            """)
            await db.commit()
            logger.info(f"[DatabaseManager] Database initialized at {self.db_path}")

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    async def get_cached_response(self, prompt: str, provider: str = "grok") -> Optional[str]:
        prompt_hash = self.hash_text(prompt)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT response FROM cache WHERE prompt_hash = ? AND provider = ?",
                (prompt_hash, provider)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    logger.info(f"[DatabaseManager] Cache hit for hash {prompt_hash[:8]}")
                    return row[0]
        return None

    async def clear_cache(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM cache")
            await db.commit()
            logger.info("[DatabaseManager] Cleared response cache.")

    async def save_cache(self, prompt: str, response: str, provider: str = "grok"):
        prompt_hash = self.hash_text(prompt)
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cache (prompt_hash, prompt, response, provider, created_at) VALUES (?, ?, ?, ?, ?)",
                (prompt_hash, prompt, response, provider, now)
            )
            await db.commit()

    async def log_task(self, task_id: str, prompt: str, status: str = "PENDING", response: Optional[str] = None, error: Optional[str] = None, retry_count: int = 0):
        now = time.time()
        completed_at = now if status in ("COMPLETED", "FAILED") else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO tasks (task_id, prompt, response, status, error, retry_count, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, prompt, response, status, error, retry_count, now, completed_at)
            )
            await db.commit()

    async def update_session_state(self, provider: str, status: str, cookies: Optional[Dict[str, Any]] = None):
        now = time.time()
        cookies_json = json.dumps(cookies) if cookies else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sessions (provider, status, last_check, cookies_json) VALUES (?, ?, ?, ?)",
                (provider, status, now, cookies_json)
            )
            await db.commit()

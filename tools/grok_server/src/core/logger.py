import os
import sys
from pathlib import Path
from loguru import logger

def setup_logger(log_dir: str = "logs", log_level: str = "INFO", rotation: str = "10 MB", retention: str = "30 days"):
    """
    Configure structured rotating logger.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Remove default logger
    logger.remove()
    
    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # File handler (Rotating daily or size)
    log_file_path = os.path.join(log_dir, "{time:YYYY-MM-DD}.log")
    logger.add(
        log_file_path,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:8} | {name}:{function}:{line} - {message}",
        level=log_level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8"
    )
    
    return logger

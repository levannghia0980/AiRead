import unicodedata
import re

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa văn bản đầu vào:
    1. Unicode NFC
    2. Chuẩn hóa khoảng trắng (nếu cần thiết)
    """
    if not text:
        return ""
        
    # Chuẩn hóa Unicode
    text = unicodedata.normalize('NFC', text)
    
    return text

def normalize_for_matching(text: str) -> str:
    """
    Chuẩn hóa riêng cho việc matching (lowercase, bỏ dấu câu đặc biệt nếu cần).
    """
    return normalize_text(text).lower()

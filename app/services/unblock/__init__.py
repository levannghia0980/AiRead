"""
Module Unblock Preprocessor (Multi-Stage Obfuscation Engine)
Hệ thống mở khóa & bảo vệ nội dung nhạy cảm cho AiRead.
"""

from app.services.unblock.preprocessor.normalize import normalize_text
from app.services.unblock.preprocessor.trie_matcher import LongestMatchTrie
from app.services.unblock.preprocessor.placeholder_encoder import PlaceholderEncoder
from app.services.unblock.unblock_pipeline import (
    is_sensitive_text,
    mask_text_with_dictionary,
    unmask_text_with_dictionary
)

__all__ = [
    "normalize_text",
    "LongestMatchTrie",
    "PlaceholderEncoder",
    "is_sensitive_text",
    "mask_text_with_dictionary",
    "unmask_text_with_dictionary"
]

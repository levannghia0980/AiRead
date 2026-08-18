import re
import logging
from typing import Dict
from app.services.unblock.contextt.contextt_dictionary import (
    VN_TO_EROTIC_MAP, 
    VN_TO_SOFT_MAP, 
    upgrade_contextt_phrase, 
    harmonize_contextt_phrase_soft
)
from app.services.unblock.common.slang_cleaner import clean_duplicate_slang_words

logger = logging.getLogger(__name__)

class ContexttDecoder:
    """
    Decoder chuyên biệt cho Luồng CONTEXTT (Biên tập GG Translate):
    - Độc lập 100% với luồng RAWT.
    - Giải mã Placeholder và nâng cấp từ ngữ Google Dịch 1 lần duy nhất.
    """
    @staticmethod
    def decode(text: str, mapping_table: Dict[str, Dict[str, str]], highlight: bool = False, enable_erotic: bool = True) -> str:
        if not text:
            return ""

        v_map = VN_TO_EROTIC_MAP if enable_erotic else VN_TO_SOFT_MAP
        restored_text = text

        if mapping_table:
            for token, data in mapping_table.items():
                clean_token = token.strip(" §[]⟦⟧")
                parts = clean_token.split("_")
                flex_clean = r"[\s_-]*".join([re.escape(p) for p in parts])
                token_pattern = r"(?:§|{|\[|⟦|\()?[\s_-]*" + flex_clean + r"[\s_-]*(?:§|}|\]|⟧|\))?"
                
                matched_pattern = None
                if re.search(token_pattern, restored_text, re.IGNORECASE):
                    matched_pattern = token_pattern
                elif len(parts) == 2 and len(parts[1]) >= 3 and re.search(rf"(?i)\b{re.escape(parts[1])}\b", restored_text):
                    matched_pattern = rf"(?i)\b{re.escape(parts[1])}\b"

                if matched_pattern:
                    orig_term = data.get("text", "")
                    target_replacement = v_map.get(orig_term.lower(), orig_term)

                    if highlight:
                        replacement = f'<span class="unblock-sensitive" title="Đã khôi phục: {orig_term} → {target_replacement}">{target_replacement}</span>'
                    else:
                        replacement = target_replacement
                        
                    restored_text = re.sub(matched_pattern, replacement, restored_text, flags=re.IGNORECASE)

            for token, data in mapping_table.items():
                orig_term = data.get("text", "")
                target_rep = v_map.get(orig_term.lower(), orig_term)
                if token in restored_text:
                    restored_text = restored_text.replace(token, target_rep)

        # Dọn sạch triệt để mọi biến thể thẻ markup rò rỉ hoặc bị LLM làm mất đuôi/mất dấu §
        restored_text = re.sub(r'§[A-Z]+(?:_[A-Z0-9]+)?§?', '', restored_text)
        restored_text = re.sub(r'§[A-Za-z0-9_]*§', '', restored_text)
        restored_text = re.sub(r'\b(?:STRICT|ZH|ACT|OBJ|BDY|SCN|PREFIX)_[A-Z0-9]+\b', '', restored_text)
        restored_text = re.sub(r'\b(?:STRICT|ZH|ACT|OBJ|BDY|SCN|PREFIX)\b', '', restored_text)

        # Áp dụng bộ lọc dọn dẹp trùng lặp & tách dính chữ
        restored_text = clean_duplicate_slang_words(restored_text)

        restored_text = re.sub(r'[ \t]+', ' ', restored_text)
        restored_text = re.sub(r' *\n *', '\n', restored_text)

        return restored_text.strip()

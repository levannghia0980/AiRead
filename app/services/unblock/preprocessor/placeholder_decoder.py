import re
import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

_global_zh_to_vn_map = None

def get_zh_to_vn_map() -> Dict[str, str]:
    global _global_zh_to_vn_map
    if _global_zh_to_vn_map is None:
        filepath = os.path.join(os.path.dirname(__file__), "..", "dictionary", "zh_to_vn_map.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    _global_zh_to_vn_map = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load zh_to_vn_map.json in decoder: {e}")
                _global_zh_to_vn_map = {}
        else:
            _global_zh_to_vn_map = {}
    return _global_zh_to_vn_map

VN_UNCENSORED_UPGRADE_MAP = {
    "dương vật": "cặc",
    "cự vật": "cây cặc bự",
    "âm đạo": "lồn",
    "âm hộ": "âm hộ",
    "tiểu huyệt": "lồn nhỏ",
    "hoa huyệt": "lồn hoa",
    "mật huyệt": "lồn dâm",
    "nộn huyệt": "lồn non",
    "nhũ hoa": "núm vú",
    "bồng đảo": "bầu vú",
    "nhũ phòng": "bầu vú",
    "quy đầu": "đầu cặc",
    "tinh hoàn": "hạt dái",
    "âm nang": "túi dái",
    "âm vật": "hạt đậu dâm",
    "hoan ái": "chịch nhau",
    "giao hợp": "làm tình chịch nhau",
    "làm tình": "chịch nhau",
    "quan hệ tình dục": "chịch làm tình",
    "nhấp đâm": "nhấp chịch",
    "đâm tiến vào": "đâm cặc vào",
    "cắm vào": "cắm cặc vào lồn",
    "bắn tinh": "bắn tinh trùng",
    "trào xuy": "phụt nước dâm",
    "mút liếm": "bú liếm lồn",
    "liếm": "liếm lồn",
    "mút": "bú cặc",
    "bới móc": "móc lồn",
    "mơn trớn": "mơn trớn dâm dật",
    "nắn bóp": "nắn bóp vú",
    "ngậm mút": "ngậm bú cặc",
    "dâm thủy": "nước lồn dâm",
    "mật dịch": "nước dâm ngọt",
    "rên rỉ": "rên dâm",
    "kiều xuy": "rên dâm kiều xuy",
    "thở dốc": "thở dốc dâm dật",
    "cao trào": "lên đỉnh dâm sướng",
    "thôi tình": "kích dâm",
    "xuân dược": "thuốc kích dâm",
}

def upgrade_vietnamese_sensitive_term(vi_text: str) -> str:
    if not vi_text:
        return ""
    res = vi_text
    sorted_keys = sorted(VN_UNCENSORED_UPGRADE_MAP.keys(), key=lambda x: len(x), reverse=True)
    for k in sorted_keys:
        v = VN_UNCENSORED_UPGRADE_MAP[k]
        pattern = r"\b" + re.escape(k) + r"\b"
        res = re.sub(pattern, v, res, flags=re.IGNORECASE)
    return res


def deduplicate_sensitive_terms(text: str) -> str:
    """
    Dọn dẹp khoảng trắng trước dấu câu và xóa 100% các từ thô tục bị lặp lại đứng liền kề nhau
    (VD: 'chịch nhau chịch nhau' -> 'chịch nhau', 'lồn lồn' -> 'lồn', 'cặc cặc' -> 'cặc').
    """
    if not text:
        return text

    # Dọn dẹp rác khoảng trắng xung quanh dấu câu
    cleaned = re.sub(r" {2,}", " ", text)
    cleaned = re.sub(r"\s+([.,!?:;])", r"\1", cleaned)

    # Chỉ deduplicate các từ thô tục bị lặp đứng liền kề
    dup_vulgar = ["chịch", "lồn", "cặc", "đụ", "bú", "xoạc", "phịch", "bím", "cu", "dâm ô", "hiếp dâm"]
    for w in dup_vulgar:
        pattern = r"\b(" + re.escape(w) + r")(?:\s+\1)+\b"
        cleaned = re.sub(pattern, r"\1", cleaned, flags=re.IGNORECASE)

    return cleaned



class PlaceholderDecoder:
    @staticmethod
    def harmonize_pronouns(orig_text: str, context_text: str) -> str:
        """
        Hậu xử lý đồng bộ xưng hô: Quét đại từ xưng hô xuất hiện trong văn bản biên tập của LLM
        (như Bố - Con, Sư phụ - Đồ đệ, Huynh - Muội) và thay thế lại các đại từ cũ trong orig_text cho đồng bộ 100%.
        """
        if not orig_text or not context_text:
            return orig_text

        pronoun_shift_rules = [
            (r"\bhắn\b", ["Bố", "Cha", "Sư phụ", "Sếp", "Chú", "Cậu", "Bác", "Anh", "Huynh"]),
            (r"\bnàng\b", ["Con", "Đồ đệ", "Trợ lý", "Cháu", "Em", "Muội"]),
            (r"\bta\b", ["Bố", "Sư phụ", "Anh", "Chú"]),
            (r"\bngươi\b", ["Con", "Đồ đệ", "Em", "Cháu"]),
        ]

        harmonized = orig_text
        for old_regex, candidates in pronoun_shift_rules:
            for new_w in candidates:
                if re.search(r"\b" + re.escape(new_w) + r"\b", context_text, re.IGNORECASE):
                    harmonized = re.sub(old_regex, new_w.lower(), harmonized, flags=re.IGNORECASE)
                    harmonized = re.sub(r"(^|[.!?]\s+)" + re.escape(new_w.lower()), r"\1" + new_w.capitalize(), harmonized)
                    break

        return harmonized

    @staticmethod
    def decode(text: str, mapping_table: Dict[str, Dict[str, str]], highlight: bool = False, is_draft_only: bool = False) -> str:
        """
        Giải mã và khôi phục các token §PREFIX_XXXX§:
        - NẾU DỊCH GỐC (is_draft_only = False): Khôi phục về NGUYÊN BẢN HÁN-VIỆT TỰ NHIÊN, sát nghĩa nguyên tác.
        - NẾU DỊCH THÔ (is_draft_only = True): Nâng cấp các từ nhạy cảm Tiếng Việt sang ngôn từ 18+ THÔ TỤC HƠN, ĐÚNG NGHĨA NHẤT SO VỚI GỐC.
        """
        if not text or not mapping_table:
            return text or ""

        zh_map = get_zh_to_vn_map()
        from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name

        restored_text = text
        for token, data in mapping_table.items():
            clean_token = token.strip("§")
            token_pattern = r"(?:§|\{|\[)?\s*" + re.escape(clean_token) + r"\s*(?:§|\}|\])?(?:\s*\([^)]*\))?"
            
            if re.search(token_pattern, restored_text, re.IGNORECASE):
                orig_term = data.get("text", "")
                is_chinese = bool(re.search(r"[\u4e00-\u9fff]", orig_term))
                
                if is_chinese:
                    # Dịch Gốc: Tra cứu zh_to_vn_map nguyên bản / Hán-Việt mượt mà tự nhiên
                    target_replacement = zh_map.get(orig_term) or zh_map.get(orig_term.lower())
                    if not target_replacement:
                        sorted_zh_keys = sorted(zh_map.keys(), key=lambda x: len(x), reverse=True)
                        translated_parts = orig_term
                        for zh_key in sorted_zh_keys:
                            if zh_key in translated_parts:
                                vn_val = zh_map[zh_key]
                                translated_parts = translated_parts.replace(zh_key, f" {vn_val} ")

                        if re.search(r"[\u4e00-\u9fff]", translated_parts):
                            translated_parts = build_hanviet_name(translated_parts) or translated_parts

                        target_replacement = re.sub(r"\s+", " ", translated_parts).strip()
                else:
                    # Dịch Thô: Khôi phục từ Tiếng Việt và NÂNG CẤP sang 18+ thô tục chuẩn nghĩa sắc văn nếu is_draft_only = True
                    if is_draft_only:
                        target_replacement = PlaceholderDecoder.harmonize_pronouns(orig_term, restored_text)
                        target_replacement = upgrade_vietnamese_sensitive_term(target_replacement)
                    else:
                        target_replacement = orig_term


                if highlight:
                    replacement = f'<span class="unblock-sensitive" title="Đã khôi phục từ từ điển mở khóa">{target_replacement}</span>'
                else:
                    replacement = target_replacement
                    
                restored_text = re.sub(token_pattern, replacement, restored_text, flags=re.IGNORECASE)

        restored_text = re.sub(r"§[A-Z0-9_]+§(?:\s*\([^)]*\))?", "", restored_text)
        restored_text = re.sub(r" {2,}", " ", restored_text)

        # Dọn dẹp rác lặp từ nhạy cảm 2-3 lần & sửa khoảng cách từ bị rách
        restored_text = deduplicate_sensitive_terms(restored_text)
        return restored_text

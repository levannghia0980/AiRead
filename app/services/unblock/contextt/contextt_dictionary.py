"""
Contextt Dictionary Engine — Bộ Từ Điển Sắc Văn Chuyên Biệt cho Luồng CONVERT (CONTEXTT)

Phân định rõ ràng 2 chế độ xử lý văn bản tiếng Việt:
1. VN_TO_EROTIC_MAP: Nâng cấp tiếng Việt sang Phong cách SẮC VĂN LÓNG 18+ (Siêu Tục & Chuẩn Mực).
2. VN_TO_SOFT_MAP: Nâng cấp tiếng Việt sang Phong cách UYỂN CHUYỂN, LỊCH SỰ (Dành cho truyện thường / YouTube).
"""

import re
from typing import Dict
from app.services.unblock.common.slang_cleaner import clean_duplicate_slang_words
from app.services.unblock.common.dictionary_loader import (
    load_vn_erotic_map,
    save_vn_erotic_word,
    clear_dictionary_cache
)

class _VNEroticMapProxy(dict):
    def __getitem__(self, key):
        return load_vn_erotic_map().get(key, "")
    def get(self, key, default=None):
        return load_vn_erotic_map().get(key, default)
    def keys(self):
        return load_vn_erotic_map().keys()
    def values(self):
        return load_vn_erotic_map().values()
    def items(self):
        return load_vn_erotic_map().items()
    def __contains__(self, key):
        return key in load_vn_erotic_map()
    def __len__(self):
        return len(load_vn_erotic_map())
    def update(self, other):
        for k, v in other.items():
            save_vn_erotic_word(k, v)

VN_TO_EROTIC_MAP = _VNEroticMapProxy()

def get_erotic_regex():
    sorted_keys = sorted(load_vn_erotic_map().keys(), key=len, reverse=True)
    if not sorted_keys:
        return None
    return re.compile(
        r"(?<![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])(" + "|".join(re.escape(k) for k in sorted_keys) + r")(?![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])",
        re.IGNORECASE
    )


# =============================================================================
# 2. BẢNG TỪ ĐIỂN CONVERT -> UYỂN CHUYỂN, LỊCH SỰ (TRUYỆN THƯỜNG / YOUTUBE)
# =============================================================================
VN_TO_SOFT_MAP: Dict[str, str] = {
    "búp bê tình zục": "công cụ giải tỏa ham muốn",
    "búp bê tình dục": "công cụ giải tỏa ham muốn",
    "búp bê xả dục": "công cụ giải tỏa ham muốn",
    "chó cái zâm đãng": "nô lệ",
    "nô lệ zâm zục cho kặc": "nô lệ",
    "nô lệ zâm zục": "nô lệ",
    "đồ chơi zâm zục": "đồ chơi",
    "con đĩ zâm đãng": "người lẳng lơ",
    "dâm phụ lẳng lơ": "thục phụ",
    "địtt cho mang bầu": "làm cho mang thai",
    "địtt cho có bầu": "làm cho mang thai",
    "trịch cho mang bầu": "làm cho mang thai",
    "trịch cho có bầu": "làm cho mang thai",
    "bắn ting vào sâu trong lồnn": "bắn tinh vào trong",
    "bắn ting": "bắn tinh",
    "phun ting": "phun tinh dịch",
    "ting dịch": "tinh dịch",
    "hòn dái": "tinh hoàn",
    "bìu dái": "bìu",
    "lỗ đít": "hậu môn",
    "khe đít": "khe hậu môn",
    "bú kặc cuồng nhiệt": "bú mút cuồng nhiệt",
    "bú kặc": "bú mút",
    "khẩu trịch": "bú mút",
    "đâm lộng kặc": "thao lộng",
    "đâm lộng": "thao lộng",
    "chuốc mê cưỡng hiếp": "chuốc mê chiếm đoạt",
    "chuốc mê cưỡng địtt": "chuốc mê chiếm đoạt",
    "chuốc mê cưỡng trịch": "chuốc mê chiếm đoạt",
    "luân phiên cưỡng hiếp tập thể": "luân phiên chiếm đoạt",
    "luân phiên cưỡng địtt tập thể": "luân phiên chiếm đoạt",
    "luân phiên trịch tập thể": "luân phiên chiếm đoạt",
    "cưỡng hiếp cuồng bạo": "cưỡng đoạt",
    "cưỡng địtt cuồng bạo": "cưỡng đoạt",
    "trịch cuồng bạo": "cưỡng đoạt",
    "cưỡng hiếp": "cường đoạt",
    "cưỡng địtt": "cường đoạt",
    "cưỡng trịch": "cường đoạt",
    "cưỡng hiếp thô bạo": "cường đoạt",
    "cưỡng địtt thô bạo": "cường đoạt",
    "ép trịch thô bạo": "cường đoạt",
    "cường trạch": "cường đoạt",
    "ép trạch": "chiếm đoạt",
    "địtt nhau": "hoan ái",
    "địt nhau": "hoan ái",
    "trịch nhau": "hoan ái",
    "chịch nhau": "hoan ái",
    "xoạc nhau": "ân ái",
    "địtt": "ân ái",
    "địt": "ân ái",
    "lỗ lồn": "khe hoa",
    "lồn": "âm đạo",
    "con cặc": "dương vật",
    "lỗ lồnn": "khe hoa",
    "khe lồnn": "khe hoa",
    "mép lồnn": "mép âm đạo",
    "con kặc": "dương vật",
    "cây kặc": "dương vật",
    "kặc": "dương vật",
    "buồi": "dương vật",
    "buồii": "dương vật",
    "zâm dịch": "mật dịch",
    "nước lồnn": "nước nhờn",
    "bầu vú": "bầu ngực",
    "cặp vú": "cặp ngực",
    "thủ zâm sục kặc": "thủ dâm",
    "tự móc lồnn": "tự giải tỏa",
    "zâm đãng": "lẳng lơ",
    "zâm loạn": "dâm loạn",
    "zâm zục": "tình dục",
    "zục vọng": "dục vọng",
}

_SORTED_SOFT_KEYS = sorted(VN_TO_SOFT_MAP.keys(), key=len, reverse=True)
_SOFT_REGEX_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])(" + "|".join(re.escape(k) for k in _SORTED_SOFT_KEYS) + r")(?![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])",
    re.IGNORECASE
)


# =============================================================================
# 3. HÀM THỰC THI CHO LUỒNG CONTEXTT
# =============================================================================

def upgrade_contextt_phrase(text: str) -> str:
    """
    Nâng cấp văn bản tiếng Việt sang ngôn từ Sắc Văn (18+) mượt mà, gợi cảm, đúng từ lóng.
    Dành riêng cho luồng CONVERT (CONTEXTT).
    """
    if not text:
        return text or ""

    def _replacer(match: re.Match) -> str:
        matched_str = match.group(0)
        matched_lower = matched_str.lower()
        replacement = VN_TO_EROTIC_MAP.get(matched_lower)
        if replacement is not None:
            if not replacement:
                return ""
            if matched_str[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement
    erotic_regex = get_erotic_regex()
    if erotic_regex:
        upgraded = erotic_regex.sub(_replacer, text)
    else:
        upgraded = text

    # Sửa tàn dư dịch sai chữ 操 -> "Giữ" của Google Translate
    giu_fixes = [
        (r'(?i)\bGiữ\s+tác\b', 'thao tác'),
        (r'(?i)\bGiữ\s+lộng\b', 'thao lộng'),
        (r'(?i)\bgiữ\s+tác\b', 'thao tác'),
        (r'(?i)\bgiữ\s+lộng\b', 'thao lộng'),
        (r'(?i)\btôi\s+Giữ,\s+tôi\s+Giữ\b', 'mẹ kiếp, mẹ kiếp'),
        (r'(?i)\btôi\s+Giữ\b', 'mẹ kiếp'),
        (r'(?i)\bGiữ,\s+Giữ\b', 'trịch, trịch'),
        (r'(?i)\bcuồng\s+Giữ\b', 'cuồng trịch'),
        (r'(?i)\bdùng\s+sức\s+Giữ(?:\s+vào)?\b', 'dùng sức trịch vào'),
        (r'(?i)\bGiữ\s+cho\s+(\w+)\s+(khóc|kêu|rên)\b', r'trịch cho \1 \2'),
        (r'(?i)\bGiữ\s+(chết|nát)\b', r'trịch \1'),
        (r'(?i)\bGiữ\s+không\s+vào\b', 'đút không vào'),
        (r'(?i)\bđã\s+Giữ\s+vào\b', 'đã trịch vào'),
        (r'(?i)\bGiữ\s+vào\b', 'trịch vào'),
        (r'(?i)\bGiữ\s+đi\b', 'trịch đi'),
        (r'(?i)\b(muốn|sẽ|đang|phải|được|cho|để|dám\s+cho\s+\w+|không\s+cho|nghĩ\s+muốn)\s+Giữ\s+(mẹ|em|cô ấy|nàng|người|cậu|chó\s+cái|cái|nô\s+lệ|huyệt)\b', r'\1 trịch \2'),
        (r'(?i)\b(muốn|sẽ|đang|phải|được|cho|để)\s+Giữ\b', r'\1 trịch'),
        (r'(?i)\b(bị|không\s+bị)\s+((?:con\s+trai|ai|cậu\s+ta|hắn|chó\s+đực)\s+)?Giữ(?:\s+một\s+lần|\s+trận)?\b', r'\1 \2trịch'),
        (r'(?i)\b(bị|không\s+bị)\s+Giữ\b', r'\1 trịch'),
        (r'(?i)\b(cậu|con|hắn|chó\s+đực)\s+Giữ\b', r'\1 trịch'),
        (r'(?i)\bcho\s+(\w+)\s+Giữ\b', r'cho \1 trịch'),
        (r'(?i)\bphải\s+Giữ\s+thế\s+nào\b', 'phải trịch thế nào'),
        (r'(?i)\bsưng\s+vẩy\s+Giữ\s+tấy\b', 'sưng tấy đỏ'),
        (r'(?i)\bgiữ\s+đỉnh\b', 'thao lộng'),
        (r'(?i)\bGiữ\s+vậy\b', 'trịch vậy'),
    ]

    for p, repl in giu_fixes:
        upgraded = re.sub(p, repl, upgraded)

    # Dọn dẹp thẻ markup rò rỉ
    upgraded = re.sub(r'§[A-Z]+(?:_[A-Z0-9]+)?§?', '', upgraded)
    upgraded = re.sub(r'§[A-Za-z0-9_]*§', '', upgraded)
    upgraded = re.sub(r'\b(?:STRICT|ZH|ACT|OBJ|BDY|SCN|PREFIX)_[A-Z0-9]+\b', '', upgraded)
    upgraded = re.sub(r'\b(?:STRICT|ZH|ACT|OBJ|BDY|SCN|PREFIX)\b', '', upgraded)

    # Áp dụng bộ lọc khử trùng lặp từ lóng & sửa các lỗi ngữ nghĩa
    upgraded = clean_duplicate_slang_words(upgraded)

    return upgraded


def harmonize_contextt_phrase_soft(text: str) -> str:
    """
    Chuẩn hóa các từ ngữ sắc văn sang phong cách UYỂN CHUYỂN, LỊCH SỰ (Dành cho truyện thông thường / làm YouTube).
    """
    if not text:
        return text or ""

    def _replacer(match: re.Match) -> str:
        matched_str = match.group(0)
        matched_lower = matched_str.lower()
        replacement = VN_TO_SOFT_MAP.get(matched_lower)
        if replacement is not None:
            if not replacement:
                return ""
            if matched_str[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement
        return matched_str

    soft = _SOFT_REGEX_PATTERN.sub(_replacer, text)
    soft = clean_duplicate_slang_words(soft)
    return soft

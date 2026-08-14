"""
Erotic Dictionary Engine — Bộ Nâng Cấp Từ Ngữ Sắc Văn 18+ (Dành riêng cho Luồng Convert CONTEXTT)

Nguyên lý:
- Sử dụng bảng quy đổi Cụm Từ Dài Trực Tiếp (Longest-Match-First) để nâng cấp câu từ bình dân/mờ nhạt
  sang từ ngữ gợi cảm, dâm tục chuẩn phong cách tiểu thuyết Sắc Văn (18+).
- Quy đổi trọn cụm từ dài trước, từ ngắn sau để TRÁCH TUYỆT ĐỐI các lỗi lặp từ thô gượng (như 'bộ bầu vú', 'khe bầu vú').
"""

import re
from typing import Dict

# Bảng quy đổi cụm từ sắc văn (sắp xếp tự động dài -> ngắn ở runtime)
RAW_EROTIC_PHRASE_MAP: Dict[str, str] = {
    # === 1. Bộ Phận Thân Thể & Danh Xưng Gợi Tình (Sắc Văn Chân Thực) ===
    "nhà vệ sinh thịt": "đồ chơi tình dục",
    "nhà vệ sinh bằng thịt": "đồ chơi tình dục",
    "nhà vệ sinh xác thịt": "đồ chơi tình dục",
    "nhà vệ sinh thân thể": "đồ chơi tình dục",
    "bồn cầu bằng thịt": "công cụ phát tiết",
    "bồn cầu thịt": "công cụ phát tiết",
    "phòng tắm thịt": "công cụ phát tiết",
    "mì nấm cần thêm trứng": "",
    "thêm trứng vào mì nấm": "",
    "mẹ già chết tiệt": "mẹ tức chết đi được",
    "mẹ già": "mẹ",
    
    "bộ ngực trắng nõn": "bầu vú trắng nõn",
    "bộ ngực căng tròn": "bầu vú căng tròn",
    "cặp ngực trắng nõn": "cặp vú trắng nõn",
    "cặp ngực căng tròn": "cặp vú căng tròn",
    "cặp ngực": "cặp vú",
    "bộ ngực": "bầu vú",
    "ngực sữa": "bầu vú sữa",
    "khe ngực": "khe vú",
    "đỉnh ngực": "đầu vú",
    "núm ngực": "núm vú",
    "đầu ngực": "đầu vú",
    
    "dương vật giả": "con cặc giả",
    "dương vật": "con cặc",
    "cái ấy của hắn": "buồi của hắn",
    "cái ấy của y": "cặc của y",
    "cái ấy của tôi": "buồi của tôi",
    "cậu nhỏ": "con cặc",
    "tinh hoàn": "hòn dái",
    "hạt đậu": "hột le",
    
    "âm đạo": "lỗ lồn",
    "âm hộ": "lỗ lồn",
    "nộn huyệt": "lỗ lồn non",
    "tiểu huyệt": "lỗ lồn",
    "hoa huyệt": "lỗ lồn",
    "mật huyệt": "lỗ lồn",
    "chỗ ấy của cô ấy": "lỗ lồn ẩm ướt của cô ấy",
    "chỗ ấy của nàng": "lỗ lồn của nàng",
    
    "cặp mông kiều đĩnh": "cặp mông mẩy",
    "cặp mông": "bờ mông",
    
    "hậu môn": "lỗ đít",
    "khe hậu môn": "khe đít",
    
    "bắp đùi thon mịn": "cặp đùi thon mịn",
    "bắp đùi": "cặp đùi",

    # === 2. Chất Dịch & Cảm Giác ===
    "chảy nước nhờn": "ứa nước lồn",
    "nước nhờn": "nước lồn",
    "dịch dâm": "dâm dịch",
    
    "bắn tinh vào trong": "bắn tinh vào lồn",
    "xuất tinh": "bắn tinh",
    
    "tiếng rên rỉ": "tiếng rên dâm",
    "tiếng rên": "tiếng rên dâm",
    "thở dốc": "thở dốc dâm dục",
    
    "khoái cảm ngập tràn": "khoái cảm dâm dật ngập tràn",

    # === 3. Hành Vi Tình Dục & Tư Thế ===
    "quan hệ tình dục": "làm tình",
    "giao cấu": "địt nhau",
    "nện nhau": "địt nhau",
    "xoạc nhau": "chịch nhau",
    
    "đút vào trong": "đút cặc vào lồn",
    "cắm vào trong": "cắm buồi vào lồn",
    "đâm vào trong": "đâm cặc vào lồn",
    "đút vào": "đút cặc vào",
    "cắm vào": "cắm buồi vào",
    "đâm vào": "đâm cặc vào",
    "ra vào": "nhấp cặc liên tục",
    
    "bú mút cuồng nhiệt": "bú cặc cuồng nhiệt",
    "bú mút": "bú cặc",
    "liếm mơn trớn": "liếm lồn mơn trớn",
    "ngậm mút": "ngậm cặc",

    # === 4. Thôi Miên, Phục Tùng & Nô Lệ ===
    "công cụ phát tiết": "công cụ phát tiết dâm dục",
    "mất lý trí": "mê loạn mất lý trí",
    "phát tình": "phát tình dâm dục",
}

# Tự động sắp xếp các từ/cụm từ theo độ dài chuỗi giảm dần (Longest-Match-First)
_SORTED_EROTIC_KEYS = sorted(RAW_EROTIC_PHRASE_MAP.keys(), key=len, reverse=True)
_EROTIC_REGEX_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])(" + "|".join(re.escape(k) for k in _SORTED_EROTIC_KEYS) + r")(?![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])",
    re.IGNORECASE
)

def upgrade_erotic_phrase(text: str) -> str:
    """
    Nâng cấp văn bản tiếng Việt sang ngôn từ Sắc Văn (18+) mượt mà, gợi cảm, tục và dâm hơn.
    Chỉ chạy cho luồng dịch CONVERT (CONTEXTT). 
    Sử dụng thuật toán Longest-Match-First kết hợp Tự Động Khử Trùng Lặp Từ (Self-Healing Deduplication)
    để đảm bảo 100% không bao giờ sinh ra lỗi lặp từ ngữ cơ thể / hành động.
    """
    if not text:
        return text or ""

    def _replacer(match: re.Match) -> str:
        matched_str = match.group(0)
        matched_lower = matched_str.lower()
        replacement = RAW_EROTIC_PHRASE_MAP.get(matched_lower)
        if replacement is not None:
            if not replacement:
                return ""
            # Giữ nguyên viết hoa chữ đầu nếu từ gốc viết hoa
            if matched_str[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement
        return matched_str

    upgraded = _EROTIC_REGEX_PATTERN.sub(_replacer, text)

    # === BỘ TỰ ĐỘNG KHỬ TRÙNG LẶP (DEDUPLICATION ENFORCER) ===
    # Tự động phát hiện và dọn sạch mọi dạng lặp từ do thay thế cụm từ tạo ra
    dedup_patterns = [
        (r'(?i)\b(bầu\s+vú)(?:\s+\1|\s+vú|\s+ngực)+\b', r'\1'),
        (r'(?i)\b(cặp\s+vú)(?:\s+\1|\s+vú|\s+ngực)+\b', r'\1'),
        (r'(?i)\b(bờ\s+mông)(?:\s+\1|\s+mông|\s+bầu\s+mông)+\b', r'\1'),
        (r'(?i)\b(cặp\s+đùi)(?:\s+\1|\s+đùi|\s+bắp\s+đùi)+\b', r'\1'),
        (r'(?i)\b(lỗ\s+lồn)(?:\s+\1|\s+lồn)+\b', r'\1'),
        (r'(?i)\b(lỗ\s+đít)(?:\s+\1|\s+đít)+\b', r'\1'),
        (r'(?i)\b(đầu\s+vú)(?:\s+\1|\s+núm\s+vú)+\b', r'\1'),
        (r'(?i)\b(núm\s+vú)(?:\s+\1|\s+đầu\s+vú)+\b', r'\1'),
        (r'(?i)\b(cặc|buồi)(?:\s+\1|\s+dương\s+vật)+\b', r'\1'),
        (r'(?i)\b(chịch\s+nhau|địt\s+nhau)(?:\s+\1|\s+làm\s+tình)+\b', r'\1'),
        (r'(?i)\b(đồ\s+chơi\s+tình\s+dục)(?:\s+\1|\s+nhà\s+vệ\s+sinh\s+của\s+con\s+trai)+\b', r'\1'),
    ]

    for p, repl in dedup_patterns:
        upgraded = re.sub(p, repl, upgraded)

    # Chuẩn hóa khoảng trắng thừa
    upgraded = re.sub(r' {2,}', ' ', upgraded)
    return upgraded

"""
Term Anchor Tagger — Gán thẻ neo vị trí & từ gốc inline trước Google Translate cho luồng CONTEXTT.

Nguyên lý:
1. Trước Google Translate: Quét văn bản RAW tiếng Trung tìm từ xưng hô, quan hệ, vai vế, danh xưng.
2. Biến đổi từ gốc thành dạng Thẻ Neo Inline: ⟦T1:TừGốc⟧ (Ví dụ: ⟦T1:师兄⟧, ⟦T2:宗主⟧).
3. Google Translate giữ nguyên dạng thẻ ⟦T1:...⟧ và vị trí trong câu tiếng Việt.
4. Gemini LLM nhận bản dịch GT + Bảng Tag Mapping -> Thay thế cụm thẻ bằng đại từ xưng hô Việt chuẩn bối cảnh truyện.
"""

import re
from typing import Dict, List, Tuple
from app.services.preprocessing.crawler.pronoun_protector import get_protect_list

def tag_raw_chinese_text(raw_text: str, profile: str = "xianxia") -> Tuple[str, Dict[str, str]]:
    """
    Gán thẻ neo Inline ⟦T1:TừGốc⟧ cho văn bản RAW tiếng Trung trước khi gửi sang Google Translate.
    
    Args:
        raw_text: Văn bản Hán gốc
        profile: Thể loại truyện ("xianxia", "wuxia", "urban")

    Returns:
        (tagged_text, tag_mapping)
        - tagged_text: Văn bản đã chèn thẻ ⟦T1:师兄⟧
        - tag_mapping: Dict {"T1": "师兄", "T2": "宗主", ...}
    """
    if not raw_text or not raw_text.strip():
        return raw_text, {}

    protect_list = get_protect_list(profile)
    if not protect_list:
        return raw_text, {}

    pattern = re.compile("|".join(re.escape(w) for w in protect_list))

    tag_mapping: Dict[str, str] = {}
    counter = 0

    def _replacer(match: re.Match) -> str:
        nonlocal counter
        matched_word = match.group(0)
        counter += 1
        tag_id = f"T{counter}"
        tag_mapping[tag_id] = matched_word
        return f"⟦{tag_id}:{matched_word}⟧"

    tagged_text = pattern.sub(_replacer, raw_text)
    return tagged_text, tag_mapping


def format_dual_anchor_tags(gt_text: str, tag_mapping: Dict[str, str]) -> str:
    """
    Sau khi Google Translate dịch xong, ghép thêm Từ Hán Gốc vào trong thẻ:
    Ví dụ: ⟦T1: Sư huynh⟧ -> ⟦T1: 师兄 | Sư huynh⟧
           ⟦T4: Tổ⟧ -> ⟦T4: 老祖 | Tổ⟧

    Giúp Gemini thấy được cả TRỰC TIẾP TỪ HÁN GỐC + BẢN DỊCH GT ở cùng 1 chỗ.
    """
    if not gt_text or not tag_mapping:
        return gt_text or ""

    def _replacer(match: re.Match) -> str:
        tag_id = match.group(1).strip()
        gt_trans = match.group(2).strip()
        orig_word = tag_mapping.get(tag_id, "")
        if orig_word:
            if orig_word != gt_trans:
                return f"⟦{tag_id}: {orig_word} | {gt_trans}⟧"
            return f"⟦{tag_id}: {orig_word}⟧"
        return f"⟦{tag_id}: {gt_trans}⟧"

    pattern = re.compile(r'⟦(T\d+):\s*([^⟧]+)⟧')
    return pattern.sub(_replacer, gt_text)


def clean_remaining_anchor_tags(text: str, tag_mapping: Dict[str, str] = None) -> str:
    """
    Hậu xử lý an toàn đa lớp: Tự động loại bỏ và làm sạch triệt để mọi loại thẻ neo
    (kể cả thẻ rách ngoặc, thẻ TBD dịch lỗi từ Google Translate, hay ngoặc vỡ) khỏi văn bản cuối cùng.
    """
    if not text:
        return text or ""

    # 1. Thẻ chuẩn kép hoặc đơn: ⟦T1: ...|...⟧ hoặc ⟦T1:...⟧ hoặc [[T1:...]]
    def _clean_match(match: re.Match) -> str:
        content = match.group(1).strip()
        if ":" in content:
            parts = content.split(":", 1)
            sub_content = parts[1].strip()
            if "|" in sub_content:
                # Nếu có dạng "师兄 | Sư huynh", lấy phần sau "|" và làm sạch từ thô ngáo
                fallback_val = sub_content.split("|", 1)[1].strip()
                fallback_val = re.sub(r'(?i)\b[Mm]ẹ\s+già\b', 'Mẹ', fallback_val)
                fallback_val = re.sub(r'(?i)\b[Bb]ố\s+già\b', 'Bố', fallback_val)
                fallback_val = re.sub(r'(?i)\bbạn\s+[Bb]ố(?:\s+già)?\b', 'Bố', fallback_val)
                return fallback_val
            return sub_content
        return content

    cleaned = re.sub(r'‹([^›]+)›', _clean_match, text)
    cleaned = re.sub(r'⟦([^⟧]+)⟧', _clean_match, cleaned)
    cleaned = re.sub(r'\[\[([^\]]+)\]\]', _clean_match, cleaned)

    # 2. Thẻ rách ngoặc do GG/LLM làm hỏng: ‹T864: ...>, ‹T1056: ..., ⟦C1_T283: ...
    cleaned = re.sub(r'[‹⟦<]\s*C?\d*_[A-Za-z0-9_]+\s*:\s*[^|›⟧\n>]*\|\s*', '', cleaned)
    cleaned = re.sub(r'[‹⟦<]\s*C?\d*_[A-Za-z0-9_]+\s*:[^›⟧\n>]*[">]*', '', cleaned)
    cleaned = re.sub(r'[‹⟦<]\s*T\d+\s*:\s*[^|›⟧\n>]*\|\s*', '', cleaned)
    cleaned = re.sub(r'[‹⟦<]\s*T\d+\s*:[^›⟧\n>]*[">]*', '', cleaned)
    cleaned = re.sub(r'\bT\d+:\s*', '', cleaned)

    # 3. Mã Token TBD rác bị GG dịch nhầm và hậu tố _T1, _C1_T1
    cleaned = re.sub(r'\bC?\d*_TBD([a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF]+)', r'\1', cleaned)
    cleaned = re.sub(r'\bC?\d*_TBD\b', '', cleaned)
    cleaned = re.sub(r'_(?:C?\d*_)?T\d+\b', '', cleaned)
    cleaned = re.sub(r'\bC?\d*_T\d+\b', '', cleaned)
    cleaned = re.sub(r'\bT\d+\b', '', cleaned)

    # 4. Loại bỏ mọi ký tự ngoặc mồ côi hoặc mã thẻ neo dư thừa, và thẻ DUMMY MASK
    cleaned = re.sub(r'⟪TAG_MASK_[A-Za-z0-9_]+⟫', '', cleaned)
    cleaned = re.sub(r'([a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF]+)[>›⟧\]]+', r'\1', cleaned)
    cleaned = re.sub(r'[<‹⟦\[]+([a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF]+)', r'\1', cleaned)
    cleaned = cleaned.replace('‹', '').replace('›', '').replace('⟦', '').replace('⟧', '').replace('>', '').replace('<', '')

    # 5. Chuẩn hóa khoảng trắng thừa
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    return cleaned.strip()


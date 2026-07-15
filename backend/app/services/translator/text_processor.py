"""
Tiền xử lý (Pre-processing) và Hậu xử lý (Post-processing) chuyên dụng
cho pipeline dịch thuật tiểu thuyết Trung → Việt.

Dựa trên 22 quy tắc dịch thuật chất lượng biên tập viên.
"""
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# TIỀN XỬ LÝ (PRE-PROCESSING) - Áp dụng trước khi gửi cho AI dịch
# ==============================================================================

# ---- Chuẩn hóa dấu câu tiếng Trung ----
CHINESE_PUNCTUATION_MAP = {
    "　": " ",      # fullwidth space -> normal space
    "．": ".",
    "，": ",",
    "；": ";",
    "：": ":",
    "！": "!",
    "？": "?",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "〈": "<",
    "〉": ">",
    "\u200b": "",   # zero-width space
    "\u200c": "",   # zero-width non-joiner
    "\u200d": "",   # zero-width joiner
    "\ufeff": "",   # BOM
    "\xa0": " ",    # non-breaking space
}

# Quảng cáo, watermark phổ biến trên trang truyện Trung Quốc
AD_PATTERNS = [
    r"https?://[a-zA-Z0-9\./\-_]+",
    r"www\.[a-zA-Z0-9\./\-_]+",
    r"[a-zA-Z0-9\-]+\.(cx|pro|me|com|net|org|xyz|site|club|vip|info)",
    r"最新网址[：:].*",
    r"请收藏.*",
    r"手机阅读.*",
    r"本站.*",
    r"无广告.*",
    r"更新最快.*",
    r"订阅.*",
    r"点击下载.*",
    r"TXT下载.*",
    r"记住网址.*",
    r"&nbsp;",
    r"\\t",
    r"【.*?(github|discord|telegram|app|web|tải|truyện|dịch).*?】",
    r"（.*?广告.*?）",
    r"\(.*?广告.*?\)",
    r"\[.*?广告.*?\]",
]
COMPILED_AD_PATTERNS = [re.compile(p, re.IGNORECASE) for p in AD_PATTERNS]

# Từ khóa trang truyện (sẽ xóa nguyên dòng nếu chứa)
SITE_KEYWORDS = ["69shuba", "69shu", "69shu.pro", "69shu.cx", "69shu.me", "六九书吧",
                 "twkan", "twkan.com", "twkan.co", "shuba", "52shuku",
                 "biquge", "xbiquge", "笔趣阁", "新笔趣阁",
                 "uukanshu", "uu看书", "qidian", "起点", "zongheng", "纵横",
                 "maofly", "shuhaige", "ptwxz", "18xs", "x23us",
                 "novelsemperor", "wuxiaworld", "royalroad",
                 "请收藏", "最新网址", "手机阅读", "记住网址",
                 "本站", "无广告", "更新最快", "订阅"]


def preprocess_chinese_text(raw_text: str) -> str:
    """
    Tiền xử lý văn bản tiếng Trung thô trước khi dịch.
    
    Bước 1: Chuẩn hóa ký tự đặc biệt (fullwidth, BOM, zero-width)
    Bước 2: Xóa quảng cáo, watermark, link website
    Bước 3: Xóa dòng chỉ chứa tên trang truyện
    Bước 4: Loại bỏ dòng trùng lặp liên tiếp
    Bước 5: Chuẩn hóa khoảng trắng và xuống dòng
    """
    if not raw_text:
        return ""
    
    # Bước 1: Chuẩn hóa ký tự unicode đặc biệt
    for old, new in CHINESE_PUNCTUATION_MAP.items():
        raw_text = raw_text.replace(old, new)
    
    # Bước 2 & 3: Xử lý từng dòng
    lines = raw_text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Xóa quảng cáo
        for pattern in COMPILED_AD_PATTERNS:
            line = pattern.sub("", line)
        line = line.strip()
        
        if not line:
            continue
        
        # Xóa dòng chỉ chứa tên trang truyện
        line_lower = line.lower()
        if any(kw in line_lower for kw in SITE_KEYWORDS):
            continue
        
        # Xóa dòng quá ngắn mà chỉ toàn dấu câu (còn sót sau khi xóa quảng cáo)
        if len(line) <= 2 and not any('\u4e00' <= c <= '\u9fff' for c in line):
            continue
            
        # Bước 4: Loại bỏ các dòng lặp lại liên tiếp (lỗi cào lặp từ nguồn hoặc watermark lặp)
        if cleaned_lines and line == cleaned_lines[-1]:
            continue
        
        cleaned_lines.append(line)
    
    # Bước 5: Chuẩn hóa khoảng trắng
    text = "\n\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


def build_glossary_context(text: str, glossaries: list) -> Tuple[str, Dict[str, str]]:
    """
    Trích xuất các thuật ngữ Glossary xuất hiện trong đoạn văn bản.
    
    Trả về:
      - glossary_prompt: chuỗi để chèn vào prompt cho AI
      - glossary_map: dict {chinese_term -> vietnamese_term} để dùng cho post-processing
    """
    if not text or not glossaries:
        return "", {}
    
    matched = []
    glossary_map = {}
    seen = set()
    
    # Ưu tiên cụm từ dài hơn trước (longest match first)
    sorted_glossaries = sorted(glossaries, key=lambda x: len(x.chinese_term), reverse=True)
    
    for g in sorted_glossaries:
        if not g.is_active or g.chinese_term in seen:
            continue
        if g.chinese_term in text:
            seen.add(g.chinese_term)
            matched.append(f"  {g.chinese_term} → {g.vietnamese_term}")
            glossary_map[g.chinese_term] = g.vietnamese_term
    
    if not matched:
        return "", {}
    
    glossary_prompt = (
        "Bảng thuật ngữ bắt buộc (PHẢI dùng đúng chính tả dưới đây, KHÔNG được dịch khác):\n"
        + "\n".join(matched)
    )
    return glossary_prompt, glossary_map


# ==============================================================================
# HẬU XỬ LÝ (POST-PROCESSING) - Áp dụng sau khi AI dịch xong
# ==============================================================================

# ---- Bảng thay thế lỗi dịch máy phổ biến (machine translation artifacts) ----
# Key: regex pattern (case insensitive), Value: replacement
MACHINE_TRANSLATION_FIXES = [
    # Lỗi dịch nghĩa đen (literal translation artifacts)
    (r"ăn một (?:cái )?kinh ngạc", "giật mình"),
    (r"ăn một (?:cái )?kinh hãi", "giật mình kinh hãi"),
    (r"uống một (?:cái )?kinh", "giật mình"),
    (r"nâng đầu(?! gối)", "ngẩng đầu"),                    # 抬头 -> ngẩng đầu
    (r"thổi bay", "thổi tung"),
    (r"treo khí", "treo mạng"),
    (r"treo một hơi", "giữ một hơi thở"),
    (r"cái nồi từ trên trời rơi xuống", "nỗi oan từ trên trời rơi xuống"),
    (r"bất động thanh sắc", "im lặng"),
    (r"xấu hổi vô cùng", "xấu hổ khôn siết"),
    (r"cười khổ một tiếng", "cười khổ một tiếng"),  # giữ nguyên
    
    # Cụm thừa / sượng / cải thiện văn phong
    (r"làm cái gì", "làm gì"),
    (r"muốn làm cái gì", "muốn làm gì"),
    (r"là cái gì", "là gì"),
    (r"cái gì vậy\?", "gì vậy?"),
    (r"cái quái gì", "quái gì"),
    (r"nhẹ nhàng gật đầu", "khẽ gật đầu"),
    (r"nhẹ gật đầu", "khẽ gật đầu"),
    (r"sắc mặt thay đổi", "sắc mặt biến đổi"),
    (r"người đàn ông xa lạ", "nam tử xa lạ"),
    (r"người đàn ông trung niên", "trung niên nam tử"),
    
    # Thêm: lỗi dịch phổ biến khác
    (r"(?:không có cách nào|không thể nào) không", "không thể không"),
    (r"nhìn chằm chằm", "ngước nhìn"),
    (r"chứa đựng", "chứa chan"),
    (r"bát náo", "huyên náo"),
    (r"tiêu hao", "tiêu tốn"),
    (r"trong lòng bụng", "trong lòng"),
    (r"lưu xuất", "rò rỉ"),
    (r"hóa độ nàng", "cảm hóa nàng"),
    (r"không khỏi", "khỏi"),
    
    # Lặp thừa (reduplication artifacts)
    (r"(?:rất )+rất ", "rất "),
    (r"(?:đã )+đã ", "đã "),
    (r"(?:sẽ )+sẽ ", "sẽ "),
    (r"(?:lại )+lại ", "lại "),
    (r"hắn hắn hắn", "hắn"),
    (r"nàng nàng nàng", "nàng"),
    
    # Dấu câu bị dịch sai
    (r"~+", "~"),
    (r"\.{4,}", "..."),
    (r"!{3,}", "!!"),
    (r"\?{3,}", "??"),
    # Chuẩn hóa gạch ngang hội thoại: dấu gạch nọm (–) -> em dash (—)
    (r" – ", " — "),
    (r"^- ", "— "),  # Đầu dòng là "-" -> "—"
]
COMPILED_MT_FIXES = [(re.compile(p, re.IGNORECASE), r) for p, r in MACHINE_TRANSLATION_FIXES]

# ---- Chuẩn hóa dấu câu tiếng Việt ----
QUOTE_NORMALIZATION = [
    ("「", '"'), ("」", '"'),
    ("『", "'"), ("』", "'"),
    ("\u201c", '"'), ("\u201d", '"'),   # " "
    ("\u2018", "'"), ("\u2019", "'"),   # ' '
    ("《", '"'), ("》", '"'),
    ("〝", '"'), ("〞", '"'),
]


def postprocess_translated_text(
    translated: str,
    glossary_map: Dict[str, str],
    raw_chinese: str = ""
) -> str:
    """
    Hậu xử lý bản dịch tiếng Việt sau khi nhận từ AI.
    
    Bước 1: Chuẩn hóa dấu ngoặc kép, dấu câu
    Bước 2: Sửa lỗi dịch máy phổ biến (machine translation artifacts)
    Bước 3: Đối chiếu & ép Glossary bắt buộc (post-enforcement)
    Bước 4: Chuẩn hóa khoảng trắng và xuống dòng
    Bước 5: Loại bỏ lời giải thích / ghi chú do AI tự thêm
    """
    if not translated:
        return ""
    
    # ---- Bước 1: Chuẩn hóa dấu ngoặc kép ----
    for old, new in QUOTE_NORMALIZATION:
        translated = translated.replace(old, new)
    
    # ---- Bước 2: Sửa lỗi dịch máy phổ biến ----
    for pattern, replacement in COMPILED_MT_FIXES:
        translated = pattern.sub(replacement, translated)
        
    # Sửa lỗi thuật ngữ luyện đan theo ngữ cảnh bản gốc Trung Quốc
    if raw_chinese:
        if "炼丹" in raw_chinese:
            translated = re.sub(r"\bnhà luy[ệê]n kim\b", "luyện đan sư", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bthầy luy[ệê]n kim\b", "luyện đan sư", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bthuật luy[ệê]n kim\b", "thuật luyện đan", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bcâu lạc bộ luy[ệê]n kim\b", "hội luyện đan", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bluy[ệê]n kim\b", "luyện đan", translated, flags=re.IGNORECASE)
        if "丹药" in raw_chinese:
            translated = re.sub(r"\bviên thuốc\b", "đan dược", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bthuốc tiên\b", "đan dược", translated, flags=re.IGNORECASE)
        if "丹鼎" in raw_chinese:
            translated = re.sub(r"\blò luy[ệê]n kim\b", "đan đỉnh", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bvạc luy[ệê]n kim\b", "đan đỉnh", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\blò luy[ệê]n đan\b", "đan đỉnh", translated, flags=re.IGNORECASE)
            translated = re.sub(r"\bvạc luy[ệê]n đan\b", "đan đỉnh", translated, flags=re.IGNORECASE)
    
    # ---- Bước 3: Ép Glossary bắt buộc (post-enforcement) ----
    # Đây là bước quan trọng nhất: dù AI có dịch sai tên, ta vẫn sửa lại bằng code
    if glossary_map:
        translated = _enforce_glossary(translated, glossary_map, raw_chinese)
    
    # ---- Bước 4: Chuẩn hóa dấu câu & khoảng trắng ----
    # Xóa khoảng trắng thừa trước dấu câu
    translated = re.sub(r"\s+([,.\?!;:\)）\]])", r"\1", translated)
    # Xóa khoảng trắng thừa sau dấu mở ngoặc
    translated = re.sub(r"([\(（\[]) +", r"\1", translated)
    # Xóa khoảng trắng nhiều dấu
    translated = re.sub(r" {2,}", " ", translated)
    # Chuẩn hóa dấu 3 chấm
    translated = re.sub(r"\.{2}", "...", translated)
    translated = re.sub(r"\.{4,}", "...", translated)
    # Xóa dòng trắng dư thừa
    translated = re.sub(r"\n{3,}", "\n\n", translated)
    
    # ---- Bước 5: Loại bỏ lời giải thích / ghi chú do AI tự thêm ----
    translated = _remove_ai_notes(translated)
    
    # Xóa khoảng trắng đầu cuối mỗi dòng
    lines = [line.strip() for line in translated.split("\n")]
    translated = "\n".join(lines)
    
    # Gom các dòng trống liên tiếp thành một
    translated = re.sub(r"\n{3,}", "\n\n", translated)
    
    return translated.strip()


def _enforce_glossary(translated: str, glossary_map: Dict[str, str], raw_chinese: str = "") -> str:
    """
    Ép Glossary bắt buộc: tìm và thay thế các biến thể sai trong bản dịch.
    
    Chiến lược nhiều lớp:
    1. Variant matching: tìm biến thể dấu thanh sai phổ biến
    2. Family name matching: nếu tên đúng có 2-3 từ viết hoa, tìm các cụm từ viết hoa 
       cùng độ dài mà chia sẻ họ (từ đầu tiên) và thay thế
    3. Đối với thuật ngữ 1 từ: tìm và thay thế trực tiếp
    """
    if not glossary_map:
        return translated
    
    # Sắp xếp theo độ dài giảm dần (thay cụm dài trước)
    sorted_terms = sorted(glossary_map.items(), key=lambda x: len(x[1]), reverse=True)
    
    for zh_term, vi_correct in sorted_terms:
        # Chỉ xử lý thuật ngữ thực sự xuất hiện trong bản gốc
        if raw_chinese and zh_term not in raw_chinese:
            continue
        
        # Nếu bản dịch đã chứa đúng tên rồi thì bỏ qua
        if vi_correct in translated:
            continue
        
        vi_parts = vi_correct.split()
        
        # Chiến lược 1: Variant matching (dấu thanh)
        vi_wrong_variants = _generate_name_variants(vi_correct)
        for wrong_variant in vi_wrong_variants:
            if wrong_variant in translated and wrong_variant != vi_correct:
                translated = translated.replace(wrong_variant, vi_correct)
                logger.info(f"Glossary enforcement (variant): '{wrong_variant}' → '{vi_correct}'")
        
        # Kiểm tra lại sau variant matching
        if vi_correct in translated:
            continue
        
        # Chiến lược 2: Family name regex matching (cho tên 2-4 từ viết hoa)
        if len(vi_parts) >= 2 and all(p[0].isupper() for p in vi_parts if p):
            family_name = vi_parts[0]
            num_parts = len(vi_parts)
            
            # Tạo regex: Họ + (num_parts-1) từ viết hoa bất kỳ
            # Ví dụ: "Từ" + 2 từ viết hoa = "Từ [A-ZĐ][a-záàảãạăắặẳẵâấậẩẫéèẻẽẹêếệểễíìỉĩịóòỏõọôốộổỗơớợởỡúùủũụưứựửữýỳỷỹỵ]+ [A-ZĐ][a-z...]+"
            viet_lower = r"[a-záàảãạăắặẳẵâấậẩẫéèẻẽẹêếệểễíìỉĩịóòỏõọôốộổỗơớợởỡúùủũụưứựửữýỳỷỹỵđ]+"
            viet_upper = r"[A-ZÁÀẢÃẠĂẮẶẲẴÂẤẬẨẪÉÈẺẼẸÊẾỆỂỄÍÌỈĨỊÓÒỎÕỌÔỐỘỔỖƠỚỢỞỠÚÙỦŨỤƯỨỰỬỮÝỲỶỸỴĐ]"
            
            word_pattern = f"{viet_upper}{viet_lower}"
            remaining_words = r"\s+".join([word_pattern] * (num_parts - 1))
            
            pattern = re.compile(
                rf"(?<![a-záàảãạ]){re.escape(family_name)}\s+{remaining_words}(?![a-záàảãạ])"
            )
            
            matches = pattern.findall(translated)
            for match in matches:
                if match.strip() != vi_correct and match.strip() != vi_correct.strip():
                    translated = translated.replace(match, vi_correct)
                    logger.info(f"Glossary enforcement (family): '{match}' → '{vi_correct}'")
    
    return translated


def _generate_name_variants(correct_name: str) -> List[str]:
    """
    Tạo ra các biến thể sai phổ biến của một tên nhân vật Hán-Việt.
    
    Ví dụ: "Từ Tiểu Thụ" → ["Từ Hiểu Thụ", "Từ Hiểu Thọ", "Hứa Hiểu Thọ", 
                              "Từ Tiểu Thọ", "Từ Tiểu Thủ", ...]
    
    Logic: 
    - Tách tên thành các từ
    - Đổi chữ cái đầu tiên thành viết hoa/viết thường
    - Thêm biến thể dấu thanh (ụ->ọ, ủ->ọ, etc.)
    """
    parts = correct_name.split()
    if len(parts) < 2:
        return [correct_name]
    
    variants = set()
    variants.add(correct_name)
    
    # Biến thể viết thường
    variants.add(correct_name.lower())
    # Biến thể viết HOA toàn bộ 
    variants.add(correct_name.upper())
    
    # Bảng hoán đổi dấu thanh phổ biến (lỗi Google Translate hay mắc)
    tone_swaps = {
        'ụ': ['ọ', 'ủ'], 'ọ': ['ụ', 'ủ'], 'ủ': ['ọ', 'ụ'],
        'ị': ['ệ', 'ỉ'], 'ệ': ['ị', 'ỉ'], 'ỉ': ['ị', 'ệ'],
        'ắ': ['ặ', 'ẳ'], 'ặ': ['ắ', 'ẳ'], 'ẳ': ['ắ', 'ặ'],
        'ứ': ['ự', 'ử'], 'ự': ['ứ', 'ử'], 'ử': ['ứ', 'ự'],
        'ấ': ['ậ', 'ẩ'], 'ậ': ['ấ', 'ẩ'], 'ẩ': ['ấ', 'ậ'],
        'ế': ['ệ', 'ể'], 'ể': ['ế', 'ệ'],
        'ố': ['ộ', 'ổ'], 'ộ': ['ố', 'ổ'], 'ổ': ['ố', 'ộ'],
    }
    
    # Tạo biến thể bằng cách hoán đổi dấu thanh trong từng từ
    for i, part in enumerate(parts):
        for char_idx, char in enumerate(part.lower()):
            if char in tone_swaps:
                for swap in tone_swaps[char]:
                    new_part = part[:char_idx] + swap + part[char_idx+1:]
                    new_parts = parts.copy()
                    new_parts[i] = new_part.capitalize() if parts[i][0].isupper() else new_part
                    variants.add(" ".join(new_parts))
    
    # Loại bỏ chính xác bản đúng khỏi danh sách biến thể sai
    variants.discard(correct_name)
    
    return list(variants)


def _remove_ai_notes(text: str) -> str:
    """
    Loại bỏ các dòng ghi chú, giải thích do AI tự thêm vào bản dịch.
    
    Ví dụ:
      "Lưu ý: Tôi đã dịch..."
      "(Ghi chú của người dịch: ...)"
      "Note: ..."
      "[Translator's note: ...]"
    """
    # Xóa các ghi chú phổ biến ở cuối văn bản
    ai_note_patterns = [
        r"\n*(?:Lưu ý|Note|Ghi chú|Chú thích|Translator'?s? note)[:\s].*$",
        r"\n*\((?:Lưu ý|Note|Ghi chú|Chú thích|Translator'?s? note)[:\s].*?\)$",
        r"\n*\[(?:Lưu ý|Note|Ghi chú|Chú thích|Translator'?s? note)[:\s].*?\]$",
        r"\n*---+\n*(?:Lưu ý|Note|Ghi chú).*$",
        # Xóa các dòng bắt đầu bằng "*" ở cuối (AI hay thêm giải thích dạng bullet)
        r"\n*\*\s*(?:Lưu ý|Note|Ghi chú|Trong bản gốc|Tôi đã).*$",
    ]
    
    for pattern in ai_note_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    
    return text


# ==============================================================================
# KIỂM DUYỆT CHẤT LƯỢNG (QUALITY CHECK)
# ==============================================================================

def quality_check(translated: str, raw_chinese: str, glossary_map: Dict[str, str]) -> List[str]:
    """
    Kiểm duyệt chất lượng bản dịch và trả về danh sách cảnh báo.
    Không chặn (non-blocking) - chỉ ghi log.
    
    Kiểm tra:
    1. Tỷ lệ độ dài (length ratio)
    2. Glossary compliance (thuật ngữ có được dùng đúng không)
    3. Phát hiện lỗi xưng hô hiện đại trong truyện cổ trang
    4. Phát hiện cụm từ dịch máy sót
    5. Phát hiện tên pinyin lại cưa được Hán Việt hóa
    """
    warnings = []
    
    if not translated or not raw_chinese:
        return warnings
    
    # 1. Length ratio check
    ratio = len(translated) / len(raw_chinese) if len(raw_chinese) > 0 else 1.0
    if ratio < 0.7:
        warnings.append(f"⚠️ Bản dịch ngắn bất thường (ratio={ratio:.2f}). Có thể mất nội dung.")
    elif ratio > 3.8:
        warnings.append(f"⚠️ Bản dịch dài bất thường (ratio={ratio:.2f}). AI có thể đã thêm nội dung.")
    
    # 2. Glossary compliance
    for zh_term, vi_correct in glossary_map.items():
        if zh_term in raw_chinese and vi_correct not in translated:
            warnings.append(f"⚠️ Glossary violation: '{zh_term}' → '{vi_correct}' không xuất hiện trong bản dịch.")
    
    # 3. Phát hiện xưng hô hiện đại trong truyện (khả năng cao là lỗi)
    modern_pronouns = ["anh ấy", "cô ấy", "bạn ơi", "mình ơi", "cậu ơi"]
    for pronoun in modern_pronouns:
        count = translated.lower().count(pronoun)
        if count >= 3:
            warnings.append(f"⚠️ Xưng hô hiện đại xuất hiện nhiều: '{pronoun}' ({count} lần)")
    
    # 4. Phát hiện cụm từ dịch máy sót
    mt_artifacts = [
        "ăn một kinh ngạc", "nâng đầu", "treo khí",
        "làm cái gì", "cái quái gì vậy thế", "hắn hắn hắn"
    ]
    for artifact in mt_artifacts:
        if artifact in translated.lower():
            warnings.append(f"⚠️ Phát hiện lỗi dịch máy sót: '{artifact}'")
    
    # 5. Phát hiện tên pinyin chưa được Hán Việt hóa (ví dụ: Zhang Wei, Li Ming)
    pinyin_pattern = re.compile(
        r"\b(Zhang|Wang|Li|Liu|Chen|Yang|Zhao|Wu|Zhou|Xu|Sun|Ma|Zhu|Hu|Guo|He|Gao|Lin|Luo|Zheng|Liang|Xie|Tang|Han|Cao|Xu|Deng|Xiao|Feng|Zeng|Peng|Lai|Lu|Ye|Su|Cheng|Jiang)\s+[A-Z][a-z]+\b",
        re.IGNORECASE
    )
    pinyin_matches = pinyin_pattern.findall(translated)
    if pinyin_matches:
        warnings.append(f"⚠️ Phát hiện có thể tên pinyin chưa Hán Việt hóa: {set(pinyin_matches)}")
    
    return warnings




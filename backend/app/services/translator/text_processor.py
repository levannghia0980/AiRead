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


# Từ điển từ nhạy cảm tiếng Trung (Censor Bypass) để tránh bị Gemini / LLM Blocked Content
# Thay thế trực tiếp sang nghĩa tiếng Việt để LLM dịch mượt mà không bao giờ bị dính bộ lọc an toàn.
SENSITIVE_LEXICON = {
    # ── CẤP ĐỘ 1: QUAN HỆ TÌNH DỤC ──────────────────────────────────────────
    "性交": "quan hệ tình dục",
    "做愛": "quan hệ",
    "做爱": "quan hệ",
    "交配": "giao phối",
    "交媾": "giao cấu",
    "做愛中": "đang quan hệ",
    "做爱中": "đang quan hệ",
    "性爱": "ân ái",
    "性行为": "hành vi tình dục",
    "性关系": "quan hệ tình dục",
    "发生关系": "phát sinh quan hệ",
    "发生性关系": "phát sinh quan hệ tình dục",
    "性交中": "đang quan hệ tình dục",
    "性交体位": "tư thế quan hệ",
    "做愛姿勢": "tư thế quan hệ",
    "做爱姿勢": "tư thế quan hệ",
    
    # ── ORAL ─────────────────────────────────────────────────────────────
    "口交": "quan hệ bằng miệng",
    "口爆": "bắn vào miệng",
    "舔鸡巴": "liếm dương vật",
    "舔阳具": "liếm dương cụ",
    "舔阴": "liếm âm hộ",
    "舔穴": "liếm tiểu huyệt",
    "舔乳头": "liếm đầu ngực",
    "吸吮": "hút mút",
    "深喉": "thọc sâu vào họng",
    "吞精": "nuốt tinh dịch",
    
    # ── ANAL ─────────────────────────────────────────────────────────────
    "肛交": "quan hệ cửa sau",
    "爆菊": "thông cúc",
    "后庭": "hậu đình",
    "肛门性爱": "quan hệ hậu môn",
    
    # ── BỘ PHẬN SINH DỤC NAM ──────────────────────────────────────────────
    "阴茎": "dương vật",
    "肉棒": "côn thịt",
    "阳具": "dương cụ",
    "鸡巴": "dương vật",
    "JB": "dương vật",
    "大屌": "dương cụ cực to",
    "龟头": "quy đầu",
    "蛋蛋": "tinh hoàn",
    "睾丸": "tinh hoàn",
    
    # ── BỘ PHẬN SINH DỤC NỮ ──────────────────────────────────────────────
    "阴道": "âm đạo",
    "阴户": "âm hộ",
    "阴唇": "âm môi",
    "阴蒂": "âm vật",
    "蜜穴": "mật huyệt",
    "花穴": "hoa huyệt",
    "骚穴": "tiểu huyệt",
    "肉穴": "thịt huyệt",
    "小穴": "tiểu huyệt",
    "私处": "nơi tư mật",
    
    # ── CHẤT DỊCH ─────────────────────────────────────────────────────────
    "精液": "tinh dịch",
    "精子": "tinh tử",
    "白浆": "dịch trắng",
    "白浆四溅": "dịch trắng tung tóe",
    "射精": "phóng tinh",
    "内射": "bắn vào trong",
    "外射": "bắn ra ngoài",
    "潮吹": "phun dịch",
    "爱液": "mật dịch",
    "淫液": "dịch nhờn",
    
    # ── HÀNH ĐỘNG ─────────────────────────────────────────────────────────
    "插入": "cắm vào",
    "抽插": "đâm chọc",
    "猛插": "đâm mạnh",
    "狠狠干": "hành hạ",
    "狠狠干她": "hành hạ nàng",
    "顶进去": "đâm vào trong",
    "进入身体": "vào trong cơ thể",
    "贯穿": "xuyên thấu",
    "插到底": "đâm vào tận cùng",
    
    # ── CỰC KHOÁI ─────────────────────────────────────────────────────────
    "高潮": "cao trào",
    "快感": "khoái cảm",
    "高潮不断": "cao trào liên tục",
    "高潮迭起": "cao trào dâng trào",
    "高潮喷发": "bộc phát cao trào",
    
    # ── CẤP ĐỘ 2: HIẾP DÂM & LOẠN LUÂN & THỦ DÂM & BDSM ───────────────────
    "强奸": "cưỡng hiếp",
    "轮奸": "luân hiếp",
    "迷奸": "chuốc thuốc hiếp dâm",
    "诱奸": "dụ hiếp",
    "性侵": "xâm hại tình dục",
    "侵犯": "xâm phạm",
    "强暴": "cưỡng bạo",
    "乱伦": "loạn luân",
    "母子": "mẹ con",
    "父女": "cha con",
    "兄妹": "anh em",
    "姐弟": "chị em",
    "近亲": "cận thân",
    "自慰": "tự an ủi",
    "手淫": "thủ dâm",
    "撸管": "thủ dâm",
    "打飞机": "thủ dâm",
    "自摸": "tự sờ mó",
    "SM": "SM",
    "虐待": "ngược đãi",
    "调教": "huấn luyện",
    "拘束": "ràng buộc",
    "捆绑": "trói buộc",
    "鞭打": "quất roi",
    "滴蜡": "nhỏ sáp",
    
    # ── CẤP ĐỘ 3: TỪ TỤC ──────────────────────────────────────────────────
    "卧槽": "đệt mờ",
    "我操": "đệt mờ",
    "我草": "đệt mờ",
    "我日": "đệt",
    "草泥马": "đệch mợ",
    "妈的": "mẹ kiếp",
    "去你妈": "cút đi",
    "狗日的": "đồ chó đẻ",
    "狗东西": "đồ chó hoang",
    "傻逼": "ngốc nghếch",
    "煞笔": "ngốc nghếch",
    "沙比": "ngốc nghếch",
    "脑残": "não tàn",
    "废物": "phế vật",
    "垃圾": "rác rưởi",
    "王八蛋": "tên khốn",
    
    # ── CẤP ĐỘ 4: BẠO LỰC ─────────────────────────────────────────────────
    "砍头": "chém đầu",
    "斩首": "trảm thủ",
    "腰斩": "chém ngang lưng",
    "碎尸": "băm thây",
    "肢解": "phân thây",
    "爆头": "bắn nát đầu",
    "鲜血": "máu tươi",
    "尸体": "thi thể",
    "尸块": "mảnh xác",
    "挖眼": "móc mắt",
    "断肢": "đứt tay chân",
    "开膛": "mổ bụng",
    "剖腹": "mổ bụng",
    "活埋": "chôn sống",
    "虐杀": "ngược sát",
    
    # ── CẤP ĐỘ 5: MA TÚY ──────────────────────────────────────────────────
    "冰毒": "ma túy đá",
    "海洛因": "hê-rô-in",
    "吗啡": "moóc-phin",
    "可卡因": "cô-ca-in",
    "摇头丸": "thuốc lắc",
    "大麻": "cần sa",
    "吸毒": "hút ma túy",
    "毒品": "chất cấm",
    
    # ── CẤP ĐỘ 6: TỰ SÁT ──────────────────────────────────────────────────
    "自杀": "tự sát",
    "跳楼": "nhảy lầu",
    "服毒": "uống độc",
    "割腕": "cắt cổ tay",
    "上吊": "treo cổ",
    "烧炭": "đốt than",
    "轻生": "hủy hoại bản thân",
    
    # ── CẤP ĐỘ 7: KHỦNG BỐ ────────────────────────────────────────────────
    "炸弹": "bom",
    "炸药": "thuốc nổ",
    "恐怖袭击": "tấn công bạo lực",
    "人体炸弹": "bom người",
    "绑架": "bắt cóc",
    "人质": "con tin",
    "枪击": "nổ súng",
    
    # ── CẤP ĐỘ 8: CHÍNH TRỊ ───────────────────────────────────────────────
    "六四": "sự kiện 89",
    "天安门": "quảng trường trung tâm",
    "共产党": "Đành",
    "共产党": "Đảng",
    "习近平": "lãnh đạo tối cao",
    "毛泽东": "Chủ tịch Mao",
    "台湾独立": "vấn đề Đài Loan",
    "新疆独立": "vấn đề Tân Cương",
    "西藏独立": "vấn đề Tây Tạng",
    "法轮功": "môn phái khí công",
    
    # ── CỤM TỪ ẨN (TIÊN HIỆP/HUYỀN HUYỄN) ──────────────────────────────────
    "水乳交融": "hòa quyện hoàn hảo",
    "水乳、交融": "hòa quyện, gắn bó",
    "乳交": "quan hệ bằng ngực",
    "榨干": "vắt kiệt",
    "榨精": "hút cạn tinh túy",
    "双修": "song tu",
    "采阴补阳": "hút âm bổ dương",
    "采阳补阴": "hút dương bổ âm",
    "炉鼎": "lò luyện khí",
    "媚药": "thuốc kích thích",
    "春药": "thuốc kích thích",
    "媚术": "mị thuật",
    "合欢宗": "Hợp Hoan Tông",
    "阴阳交合": "âm dương hòa hợp",
    "男女交欢": "nam nữ ân ái",
    "房中术": "phòng trung thuật",
    "云雨": "mây mưa",
    "春宵": "đêm xuân",
    "鱼水之欢": "niềm vui cá nước",
    
    # ── TIẾNG LÓNG & ĐỒNG ÂM & EMOJI ──────────────────────────────────────
    "啪啪啪": "bạch bạch bạch",
    "嗯啊": "rên rỉ",
    "啊啊啊": "kêu gào",
    "好爽": "sung sướng",
    "不要": "đừng mà",
    "轻点": "nhẹ chút",
    "快点": "nhanh chút",
    "慢一点": "chậm chút",
    "我要了": "ta muốn",
    "鸡鸡": "dương vật",
    "JJ": "dương vật",
    "小弟弟": "tiểu đệ đệ",
    "小妹妹": "tiểu muội muội",
    "那个地方": "nơi đó",
    "那里": "nơi đó",
    "🍆": "dương vật",
    "🍑": "mông",
    "💦": "nước nhờn",
    "👅": "liếm mút"
}

# Regex bẻ nhạy cảm hỗ trợ khoảng trắng hoặc ký tự nhiễu xen giữa (ví dụ: 乳、交, 做~爱...)
# _NOISE_RE khớp: dấu cách, tab, dấu gạch ngang, dấu chấm, dấu phẩy, dấu ngã, dấu hoa thị...
_NOISE_RE = r"[\s\·\-\,\、\.\_\?\!\/\#\$\%\^\&\*\~\=\+\|\\\'\"\‘\’\“\”]*"
_COMPILE_CENSOR_PATTERNS = []

for zh_word, vi_trans in SENSITIVE_LEXICON.items():
    if len(zh_word) >= 2:
        chars = list(zh_word)
        pattern = _NOISE_RE.join(re.escape(c) for c in chars)
        # Bắt case insensitive cho emoji và tiếng lóng latin (như JJ, JB, SM)
        _COMPILE_CENSOR_PATTERNS.append((re.compile(pattern, re.IGNORECASE), vi_trans))
    else:
        _COMPILE_CENSOR_PATTERNS.append((re.compile(re.escape(zh_word), re.IGNORECASE), vi_trans))


def preprocess_chinese_text(raw_text: str) -> str:
    """
    Tiền xử lý văn bản tiếng Trung thô trước khi dịch.
    
    Bước 0: Quét thông minh và dịch trực tiếp các cụm từ nhạy cảm để bypass Censor
    Bước 1: Chuẩn hóa ký tự đặc biệt (fullwidth, BOM, zero-width)
    Bước 2: Xóa quảng cáo, watermark, link website
    Bước 3: Xóa dòng chỉ chứa tên trang truyện
    Bước 4: Loại bỏ dòng trùng lặp liên tiếp
    Bước 5: Chuẩn hóa khoảng trắng và xuống dòng
    """
    if not raw_text:
        return ""

    # Bước 0: Censor Bypass (thay thế trực tiếp từ nhạy cảm sang tiếng Việt)
    for pattern, vi_trans in _COMPILE_CENSOR_PATTERNS:
        raw_text = pattern.sub(vi_trans, raw_text)
        
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




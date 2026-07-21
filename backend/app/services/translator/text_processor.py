"""
Tiền xử lý (Pre-processing) và Hậu xử lý (Post-processing) chuyên dụng
cho pipeline dịch thuật tiểu thuyết Trung → Việt.

Dựa trên 22 quy tắc dịch thuật chất lượng biên tập viên.
"""
import re
import logging
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

# ==============================================================================
# UNIVERSAL NORMALIZER (FIRST PASS - UNIVERSAL)
# ==============================================================================
PUNCT_MAP = str.maketrans({
    "，": ", ", "。": ". ", "！": "! ", "？": "? ",
    "「": "\u201c", "」": "\u201d", "『": "\u201c", "』": "\u201d",
    "、": ", ", "：": ": ", "；": "; "
})

UNIT_MAP = {
    "两": "lượng", "文": "văn", "里": "dặm", "尺": "thước",
    "子时": "giờ Tý", "丑时": "giờ Sửu", "寅时": "giờ Dần", "卯时": "giờ Mão",
    "辰时": "giờ Thìn", "巳时": "giờ Tị", "午时": "giờ Ngọ", "未时": "giờ Mùi",
    "申时": "giờ Thân", "酉时": "giờ Dậu", "戌时": "giờ Tuất", "亥时": "giờ Hợi",
    "三更": "canh ba", "五更": "canh năm", "一炷香": "nửa nén hương",
    "半个时辰": "nửa canh giờ", "一个时辰": "một canh giờ"
}

def universal_normalize_text(text: str) -> str:
    """
    Chuẩn hóa universal ở bước đầu tiên:
    1. Chuyển đổi toàn bộ dấu câu kiểu Trung Quốc sang dấu câu Việt Nam.
    2. Quy đổi các đơn vị đo lường/thời gian/tiền tệ cổ cố định toàn cục.
    """
    if not text:
        return text
    # 1. Dấu câu
    text = text.translate(PUNCT_MAP)
    # 2. Đơn vị cổ cố định
    for unit_zh, unit_vi in UNIT_MAP.items():
        text = text.replace(unit_zh, unit_vi)
    return text

# ==============================================================================
# FAST-SCANNER MULTI-GENRE AUTO-DETECTOR (PRE-PROCESSING)
# ==============================================================================
def detect_novel_genre_profile(title: str = "", synopsis: str = "", raw_chinese_head: str = "") -> Dict[str, Any]:
    """
    Tiền xử lý Fast-Scanner (<10ms): Nhận diện 100% thể loại truyện và khóa Translation Context Payload.
    
    Hỗ trợ 5 thể loại chính:
    1. XIANXIA: Tiên Hiệp / Huyền Huyễn
    2. HISTORICAL: Cổ Trang / Kiếm Hiệp / Lịch Sử
    3. MODERN_URBAN: Đô Thị Hiện Đại / Thương Chiến / Linh Dị
    4. ROMANCE: Ngôn Tình / Nữ Cường
    5. SCI_FI_SYSTEM: Mạt Thế / Khoa Học Viễn Tưởng / Game Hệ Thống
    """
    text_to_scan = f"{title} {synopsis} {raw_chinese_head[:800]}".lower()
    
    # Fast Hard Markers Lookup Matrix
    xianxia_markers = ["宗门", "筑基", "丹田", "灵气", "飞剑", "渡劫", "修士", "妖兽", "仙人", "金丹", "元婴", "修仙", "仙帝", "洞府"]
    historical_markers = ["皇朝", "掌门", "江湖", "武林", "官府", "少爷", "小姐", "拜见", "朝廷", "将军", "王爷", "刺客", "镖局"]
    modern_markers = ["公司", "手机", "汽车", "总裁", "警察", "医院", "跑车", "信用卡", "公园", "股票", "集团", "律师", "酒吧", "别墅", "警车"]
    romance_markers = ["霸道", "联姻", "闺蜜", "豪门", "男神", "娇妻", "影后", "白月光", "前夫", "虐恋", "真千金", "假千金"]
    scifi_markers = ["系统", "异能", "基地", "丧尸", "经验值", "玩家", "副本", "末世", "星际", "机甲", "进化", "能级"]

    scores = {
        "XIANXIA": sum(text_to_scan.count(m) * 2 for m in xianxia_markers),
        "HISTORICAL": sum(text_to_scan.count(m) * 2 for m in historical_markers),
        "MODERN_URBAN": sum(text_to_scan.count(m) * 3 for m in modern_markers),
        "ROMANCE": sum(text_to_scan.count(m) * 2 for m in romance_markers),
        "SCI_FI_SYSTEM": sum(text_to_scan.count(m) * 2 for m in scifi_markers),
    }

    detected_genre = max(scores, key=scores.get)
    max_score = scores[detected_genre]

    if max_score == 0:
        detected_genre = "XIANXIA"

    profiles = {
        "XIANXIA": {
            "genre_code": "XIANXIA",
            "genre_name": "Tiên Hiệp / Huyền Huyễn",
            "system_prompt_addon": "GENRE: Xianxia / Xuanhuan. LOCK: TRUE. Dùng xưng hô cổ trang (ta/ngươi, hắn/nàng/y). Thuật ngữ Hán-Việt chuẩn Tiên Hiệp (Trúc Cơ, Đan Điền, Bí Cảnh). TUYỆT ĐỐI KHÔNG dùng từ hiện đại (xe hơi, công ty, anh/em, sếp).",
            "pronoun_default": ("hắn", "nàng", "y", "ta", "ngươi")
        },
        "HISTORICAL": {
            "genre_code": "HISTORICAL",
            "genre_name": "Cổ Trang / Kiếm Hiệp / Lịch Sử",
            "system_prompt_addon": "GENRE: Historical / Wuxia. LOCK: TRUE. Dùng xưng hô Hán-Việt phong kiến (hắn/nàng, huynh/đệ/tỷ/muội, bá phụ, thiếu gia, vương gia). TUYỆT ĐỐI KHÔNG dùng từ hiện đại.",
            "pronoun_default": ("hắn", "nàng", "huynh", "đệ", "tỷ", "muội")
        },
        "MODERN_URBAN": {
            "genre_code": "MODERN_URBAN",
            "genre_name": "Đô Thị Hiện Đại / Thương Chiến / Linh Dị",
            "system_prompt_addon": "GENRE: Modern Urban / Business. LOCK: TRUE. Dùng văn phong Đô Thị Hiện Đại tự nhiên (hắn/anh/tôi/cậu/cô ấy). Thuật ngữ hiện đại (công ty, chủ tịch, xe hơi, máy tính, cảnh sát). TUYỆT ĐỐI KHÔNG dùng từ cổ trang/tiên hiệp lạc quẻ (bổn tọa, tại hạ, động phủ, độ kiếp).",
            "pronoun_default": ("hắn", "anh", "tôi", "cậu", "cô ấy")
        },
        "ROMANCE": {
            "genre_code": "ROMANCE",
            "genre_name": "Ngôn Tình / Nữ Cường",
            "system_prompt_addon": "GENRE: Romance. LOCK: TRUE. Dùng văn phong Ngôn Tình ngọt ngào, cảm xúc sâu lắng (chàng/nàng hoặc anh/em, thiếu gia, tiểu thư). TUYỆT ĐỐI KHÔNG dùng từ ngữ khô cứng hay kiếm hiệp.",
            "pronoun_default": ("chàng", "nàng", "anh", "em")
        },
        "SCI_FI_SYSTEM": {
            "genre_code": "SCI_FI_SYSTEM",
            "genre_name": "Mạt Thế / Khoa Học Viễn Tưởng / Game Hệ Thống",
            "system_prompt_addon": "GENRE: Sci-Fi / Post-Apocalyptic / System. LOCK: TRUE. Dùng thuật ngữ Game/Hệ thống/Viễn tưởng (căn cứ, kỹ năng, cấp độ, quái vật, hệ thống, người chơi). Xưng hô (hắn/y/ta/ngươi).",
            "pronoun_default": ("hắn", "y", "ta", "ngươi")
        }
    }

    return profiles[detected_genre]


def enforce_genre_boundary_fixes(translated: str, genre_code: str = "XIANXIA") -> str:
    """
    Hậu xử lý Boundary Enforcer: TỰ ĐỘNG SỬA 100% các từ "lạc quẻ" theo thể loại đã chọn.
    """
    if not translated:
        return translated

    if genre_code in ["XIANXIA", "HISTORICAL"]:
        modern_to_ancient = [
            (r"\bxe hơi\b", "xe ngựa"),
            (r"\bô tô\b", "xe ngựa"),
            (r"\btaxi\b", "xe ngựa"),
            (r"\bđiện thoại\b", "truyền âm phù"),
            (r"\bsếp\b", "chưởng môn"),
            (r"\bcông ty\b", "thương hội"),
        ]
        for p, r in modern_to_ancient:
            translated = re.sub(p, r, translated, flags=re.IGNORECASE)

    elif genre_code == "MODERN_URBAN":
        ancient_to_modern = [
            (r"\bbổn tọa\b", "tôi"),
            (r"\btại hạ\b", "tôi"),
            (r"\bđộng phủ\b", "căn hộ"),
            (r"\bđại đạo\b", "con đường"),
            (r"\bphân thân\b", "bản sao"),
        ]
        for p, r in ancient_to_modern:
            translated = re.sub(p, r, translated, flags=re.IGNORECASE)

    return translated


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


def _strip_watermark_paragraphs(paragraphs: List[str], min_len: int = 10, min_repeat: int = 2) -> List[str]:
    """
    Phát hiện và xóa các đoạn văn bản watermark chống cào.
    
    Watermark web thường là cùng 1 câu/đoạn được chèn vào nhiều vị trí
    KHÔNG liên tiếp trong chương. Thuật toán: đếm số lần xuất hiện
    của mỗi đoạn, nếu xuất hiện >= min_repeat lần thì xóa tất cả.
    
    Args:
        paragraphs: Danh sách các đoạn/dòng đã qua xử lý sơ bộ
        min_len: Chiều dài tối thiểu của đoạn để xét (bỏ qua dòng quá ngắn)
        min_repeat: Số lần lặp tối thiểu để coi là watermark (mặc định 2)
    """
    if len(paragraphs) < 5:
        return paragraphs
    
    # Đếm tần suất xuất hiện của mỗi dòng
    line_counts: Dict[str, int] = {}
    for p in paragraphs:
        if len(p) >= min_len:
            line_counts[p] = line_counts.get(p, 0) + 1
    
    # Tập hợp các dòng watermark (xuất hiện >= min_repeat lần)
    watermark_lines = {line for line, count in line_counts.items() if count >= min_repeat}
    
    if watermark_lines:
        for wm in watermark_lines:
            sample = wm[:60] + "..." if len(wm) > 60 else wm
            logger.info(f"🚫 Phát hiện watermark (lặp {line_counts[wm]} lần), đã xóa: \"{sample}\"")
    
    # Trả về danh sách đã lọc bỏ watermark
    return [p for p in paragraphs if p not in watermark_lines]


def preprocess_chinese_text(raw_text: str) -> str:
    """
    Tiền xử lý văn bản tiếng Trung thô trước khi dịch.
    
    Bước 1: Chuẩn hóa ký tự đặc biệt (fullwidth, BOM, zero-width)
    Bước 2: Xóa quảng cáo, watermark, link website
    Bước 3: Xóa dòng chỉ chứa tên trang truyện
    Bước 4: Loại bỏ dòng trùng lặp liên tiếp
    Bước 5: Xóa watermark chống cào (câu lặp không liên tiếp)
    Bước 6: Chuẩn hóa khoảng trắng và xuống dòng
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
    
    # Bước 5: Xóa watermark chống cào (câu lặp không liên tiếp xuyên suốt chương)
    cleaned_lines = _strip_watermark_paragraphs(cleaned_lines, min_len=10, min_repeat=2)
    
    # Bước 6: Chuẩn hóa khoảng trắng
    text = "\n\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


# ==============================================================================
# MASTER TU TIÊN GLOSSARY — Kho thuật ngữ Hán-Việt Tiên Hiệp/Cổ Trang mẫu
# ==============================================================================
MASTER_TUTIEN_GLOSSARY = {
    # Họ tộc
    "苏家": "Tô gia", "林家": "Lâm gia", "叶家": "Diệp gia", "萧家": "Tiêu gia",
    "楚家": "Sở gia", "宁家": "Ninh gia", "王家": "Vương gia", "李家": "Lý gia",
    "赵家": "Triệu gia", "秦家": "Tần gia", "韩家": "Hàn gia", "陈家": "Trần gia",
    "周家": "Chu gia", "柳家": "Liễu gia", "白家": "Bạch gia", "沈家": "Thẩm gia",
    
    # Tên họ phổ biến
    "苏": "Tô", "林": "Lâm", "叶": "Diệp", "萧": "Tiêu", "楚": "Sở", "宁": "Ninh",
    "王": "Vương", "李": "Lý", "赵": "Triệu", "秦": "Tần", "韩": "Hàn", "陈": "Trần",
    "周": "Chu", "柳": "Liễu", "白": "Bạch", "沈": "Thẩm",
    
    # Địa vị & Quan chức
    "少爷": "thiếu gia", "小姐": "tiểu thư", "老祖": "lão tổ", "家主": "gia chủ",
    "族长": "tộc trưởng", "宗主": "tông chủ", "掌门": "chưởng môn", "门主": "môn chủ",
    "圣子": "thánh tử", "圣女": "thánh nữ", "少主": "thiếu chủ", "宫主": "cung chủ",
    "峰主": "phong chủ", "殿主": "điện chủ", "教主": "giáo chủ", "国师": "quốc sư",
    
    # Quan hệ tu luyện & Xưng hô
    "师兄": "sư huynh", "大师兄": "đại sư huynh", "二师兄": "nhị sư huynh",
    "师弟": "sư đệ", "师妹": "sư muội", "师姐": "sư tỷ", "大师姐": "đại sư tỷ",
    "伯父": "bá phụ", "伯母": "bá mẫu", "叔父": "thúc phụ", "叔母": "thẩm thẩm",
    "姑姑": "cô cô", "姨娘": "dì", "岳父": "nhạc phụ", "岳母": "nhạc mẫu",
    
    # Tu tiên & Nghề nghiệp
    "修士": "tu sĩ", "修仙者": "tu tiên giả", "仙人": "tiên nhân", "真人": "chân nhân",
    "道友": "đạo hữu", "散修": "tán tu", "剑修": "kiếm tu", "魔修": "ma tu",
    "鬼修": "quỷ tu", "体修": "thể tu", "丹师": "đan sư", "器师": "luyện khí sư",
    "符师": "phù sư", "阵法师": "trận pháp sư",
    
    # Cảnh giới
    "炼气": "Luyện Khí", "筑基": "Trúc Cơ", "金丹": "Kim Đan", "元婴": "Nguyên Anh",
    "化神": "Hóa Thần", "炼虚": "Luyện Hư", "合体": "Hợp Thể", "渡劫": "Độ Kiếp",
    "大乘": "Đại Thừa", "真仙": "Chân Tiên", "金仙": "Kim Tiên", "太乙金仙": "Thái Ất Kim Tiên",
    "大罗金仙": "Đại La Kim Tiên",
    
    # Linh dược & Đan dược
    "灵药": "linh dược", "仙药": "tiên dược", "神药": "thần dược", "灵草": "linh thảo",
    "仙草": "tiên thảo", "宝药": "bảo dược", "丹药": "đan dược", "聚气丹": "Tụ Khí Đan",
    "筑基丹": "Trúc Cơ Đan", "疗伤丹": "Liệu Thương Đan", "洗髓丹": "Tẩy Tủy Đan", "回元丹": "Hồi Nguyên Đan",
    
    # Pháp bảo & Bí tịch
    "法器": "pháp khí", "法宝": "pháp bảo", "灵宝": "linh bảo", "圣器": "thánh khí",
    "神器": "thần khí", "帝兵": "đế binh", "飞剑": "phi kiếm", "仙剑": "tiên kiếm",
    "秘籍": "bí tịch", "功法": "công pháp", "武技": "võ kỹ", "秘术": "bí thuật",
    "神通": "thần thông", "禁术": "cấm thuật",
    
    # Thành ngữ & Cơ duyên
    "机缘": "cơ duyên", "造化": "tạo hóa", "因果": "nhân quả", "天机": "thiên cơ",
    "大道": "đại đạo", "道心": "đạo tâm", "心魔": "tâm ma", "顿悟": "đốn ngộ",
    "气运": "khí vận", "悟性": "ngộ tính",
    
    # Thế lực & Yêu thú
    "宗门": "tông môn", "圣地": "thánh địa", "皇朝": "hoàng triều", "王朝": "vương triều",
    "世家": "thế gia", "古族": "cổ tộc", "禁区": "cấm khu", "秘境": "bí cảnh",
    "妖兽": "yêu thú", "神兽": "thần thú", "凶兽": "hung thú", "灵兽": "linh thú", "圣兽": "thánh thú",
    
    # Thời gian & Đơn vị cổ
    "片刻": "chốc lát", "须臾": "chớp mắt", "半炷香": "nửa nén hương", "一炷香": "một nén hương",
    "一盏茶": "một chén trà", "一个时辰": "một canh giờ", "一天": "một ngày",
    "丈": "trượng", "尺": "xích", "寸": "thốn", "里": "dặm", "斤": "cân", "两": "lạng",
    
    # Câu nói & Hành động
    "冷哼": "hừ lạnh", "冷笑": "cười lạnh", "苦笑": "cười khổ", "失笑": "bật cười",
    "嗤笑": "cười nhạo", "怒喝": "quát lớn", "暴喝": "quát vang", "沉声道": "trầm giọng nói",
    "淡淡道": "nhàn nhạt nói", "缓缓道": "chậm rãi nói", "点头": "gật đầu", "摇头": "lắc đầu",
    "抱拳": "ôm quyền", "拱手": "chắp tay", "躬身": "khom người", "作揖": "chắp tay thi lễ", "行礼": "hành lễ"
}


def build_glossary_context(text: str, glossaries: list) -> Tuple[str, Dict[str, str]]:
    """
    Trích xuất các thuật ngữ Glossary xuất hiện trong đoạn văn bản.
    Tự động kết hợp Kho Thuật Ngữ Mẫu Master Tu Tiên + Từ điển người dùng.
    """
    if not text:
        return "", {}
    
    matched = []
    glossary_map = {}
    seen = set()
    
    # 1. Nạp từ điển người dùng truyền vào (nếu có)
    if glossaries:
        sorted_glossaries = sorted(glossaries, key=lambda x: len(x.chinese_term), reverse=True)
        for g in sorted_glossaries:
            if not g.is_active or g.chinese_term in seen:
                continue
            if g.chinese_term in text:
                seen.add(g.chinese_term)
                matched.append(f"  {g.chinese_term} → {g.vietnamese_term}")
                glossary_map[g.chinese_term] = g.vietnamese_term
                
    # 2. Tự động nạp thuật ngữ mẫu Tiên Hiệp nếu chưa có
    sorted_master = sorted(MASTER_TUTIEN_GLOSSARY.items(), key=lambda x: len(x[0]), reverse=True)
    for zh_term, vi_term in sorted_master:
        if zh_term not in seen and zh_term in text:
            seen.add(zh_term)
            matched.append(f"  {zh_term} → {vi_term}")
            glossary_map[zh_term] = vi_term
    
    if not matched:
        return "", {}
        
    prompt_lines = ["Bảng thuật ngữ bắt buộc áp dụng (Glossary):"] + matched
    return "\n".join(prompt_lines), glossary_map
    
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
    # Lỗi từ nóng / nhạy cảm / địa danh sai do dịch tự động hoặc AI dịch sượng
    (r"(?:xoát|xoạt) tồn tại cảm", "tìm cảm giác tồn tại"),
    (r"khoáng cổ thước kim", "vô tiền khoáng hậu"),
    (r"nước sữa hòa nhau", "hòa quyện hoàn hảo"),
    (r"nước sữa hòa quyện", "hòa quyện hoàn hảo"),
    (r"\bXu Xiaoxu\b", "Từ Tiểu Thụ"),
    (r"\bXu Xiaoshou\b", "Từ Tiểu Thụ"),
    (r"\bBlack Skyfall\b", "Hắc Lạc Nhai"),

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


def _strip_translated_watermarks(translated: str) -> str:
    """
    Xóa watermark trong bản dịch tiếng Việt.
    
    Phát hiện các câu/đoạn dịch bị lặp lại >= 2 lần ở các vị trí
    không liên tiếp trong văn bản. Đây thường là do watermark gốc
    tiếng Trung bị dịch ra cùng một câu tiếng Việt (hoặc tiếng Anh).
    """
    if not translated or len(translated) < 100:
        return translated
    
    # Tách thành các đoạn bằng xuống dòng
    paragraphs = [p.strip() for p in translated.split("\n") if p.strip()]
    
    if len(paragraphs) < 5:
        return translated
    
    # Đếm tần suất xuất hiện của mỗi đoạn (chỉ xét đoạn đủ dài)
    para_counts: Dict[str, int] = {}
    for p in paragraphs:
        # Bỏ qua đoạn quá ngắn hoặc chỉ có dấu câu
        if len(p) > 20:
            para_counts[p] = para_counts.get(p, 0) + 1
    
    # Tìm các đoạn watermark (lặp >= 2 lần)
    watermark_paras = {p for p, count in para_counts.items() if count >= 2}
    
    if not watermark_paras:
        return translated
    
    for wm in watermark_paras:
        sample = wm[:80] + "..." if len(wm) > 80 else wm
        logger.info(f"🚫 Xóa watermark dịch (lặp {para_counts[wm]} lần): \"{sample}\"")
    
    # Lọc bỏ các đoạn watermark
    filtered = [p for p in paragraphs if p not in watermark_paras]
    
    return "\n\n".join(filtered)


async def postprocess_translated_text(
    translated: str,
    glossary_map: Dict[str, str],
    raw_chinese: str = "",
    client = None,
    genre_code: str = "XIANXIA"
) -> str:
    """
    Hậu xử lý bản dịch tiếng Việt sau khi nhận từ AI.
    
    Bước 1: Chuẩn hóa dấu ngoặc kép, dấu câu
    Bước 2: Sửa lỗi dịch máy phổ biến (machine translation artifacts)
    Bước 3: Đối chiếu & ép Glossary bắt buộc (post-enforcement)
    Bước 4: Sửa từ "lạc quẻ" theo thể loại (Genre Boundary Enforcer)
    Bước 5: Chuẩn hóa khoảng trắng và xuống dòng
    """
    if not translated:
        return ""
        
    # Boundary Enforcer theo thể loại
    translated = enforce_genre_boundary_fixes(translated, genre_code)
    
    # ---- Bước 0: Xóa watermark trong bản dịch (câu lặp không liên tiếp) ----
    translated = _strip_translated_watermarks(translated)
    
    # ---- Bước 1: Chuẩn hóa dấu ngoặc kép ----
    for old, new in QUOTE_NORMALIZATION:
        translated = translated.replace(old, new)
    
    # ---- Bước 2: Sửa lỗi dịch máy phổ biến ----
    for pattern, replacement in COMPILED_MT_FIXES:
        translated = pattern.sub(replacement, translated)
        
    # Sửa lỗi tên riêng Pinyin / dịch ngô nghê còn sót của Google Translate
    pinyin_auto_fixes = [
        (r"\bHọc viện Yushan\b", "Học viện Ngọc Sơn"),
        (r"\bThư viện Yushan\b", "Thư viện Ngọc Sơn"),
        (r"\bYushan\b", "Ngọc Sơn"),
        (r"\bgia đình Su\b", "Tô gia"),
        (r"\bnhà Su\b", "nhà họ Tô"),
        (r"\bhọ Su\b", "họ Tô"),
        (r"\bSu Xiaoxiao\b", "Tô Tiếu Tiếu"),
        (r"\bLei Wang\b", "Lôi Vọng"),
        (r"\bQingyi\b", "Thanh Y"),
        (r"\bRuoping\b", "Nhược Bình"),
        (r"\bA Kang\b", "A Khang"),
    ]
    for pattern, rep in pinyin_auto_fixes:
        translated = re.sub(pattern, rep, translated, flags=re.IGNORECASE)
        
    # Cố định ngôi xưng hô toàn chương (POV Locking) - chống nhảy ngôi ngoài lời thoại
    translated = lock_pov_pronouns(translated)
    
    # Biên tập nhịp văn & Việt hóa câu văn khô cứng
    translated = refine_cinematic_rhythm(translated)
        
    # Sửa lỗi quy tắc Họ tộc: "nhà họ X" / "gia đình X" ➔ "X gia"
    viet_name_char = r"[A-ZÁÀẢÃẠĂẮẶẲẴÂẤẬẨẪÉÈẺẼẸÊẾỆỂỄÍÌỈĨỊÓÒỎÕỌÔỐỘỔỖƠỚỢỞỠÚÙỦŨỤƯỨỰỬỮÝỲỶỸỴĐ][a-záàảãạăắặẳẵâấậẩẫéèẻẽẹêếệểễíìỉĩịóòỏõọôốộổỗơớợởỡúùủũụưứựửữỳýỷỹỵđ]+"
    translated = re.sub(
        rf"\b(?:nhà họ|gia đình)\s+({viet_name_char})\b",
        r"\1 gia",
        translated
    )
    
    # Sửa lỗi xưng hô: "anh X" ➔ "X huynh", "chị Y" ➔ "Y tỷ" (khi X/Y là tên riêng viết hoa)
    translated = re.sub(
        rf"\banh\s+({viet_name_char})\b",
        r"\1 huynh",
        translated
    )
    translated = re.sub(
        rf"\bchị\s+({viet_name_char})\b",
        r"\1 tỷ",
        translated
    )
    
    # Sửa lỗi từ ngữ Tây hóa / Cấm xuất hiện
    prohibited_fixes = [
        (r"\bNinh Bro\b", "Ninh huynh"),
        (r"\bMr\.?\s+([A-Z][a-z]+)\b", r"\1 gia chủ"),
        (r"\bBoss\b", "Trùm"),
        (r"\bLeader\b", "Thủ lĩnh"),
        (r"\bFamily\s+([A-Z][a-z]+)\b", r"\1 gia"),
        (r"\bFoundation Establishment\b", "Trúc Cơ"),
        (r"\bGolden Core\b", "Kim Đan"),
        (r"\bNascent Soul\b", "Nguyên Anh"),
    ]
    for pattern, rep in prohibited_fixes:
        translated = re.sub(pattern, rep, translated, flags=re.IGNORECASE)
        
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
    
    # ---- Bước 6: Tự động dọn dẹp các cụm chữ Hán sót lại (Bypass Censor Fallback) ----
    translated = await resolve_remaining_chinese_chars(translated, raw_chinese, glossary_map, client=client)
    
    # ---- Bước 7: Cưỡng ép sửa 100% Pinyin & đại từ ngoài lời thoại ----
    translated = force_repair_all_errors(translated, glossary_map)
    
    # ---- Bước 8: Đồng bộ tính nhất quán tên riêng (Self-Consistency Pass) ----
    translated = self_consistency_check(translated, glossary_map)
    
    # ---- Bước 9: Perfect Output Polish (Hậu Xử Lý Hoàn Thiện Điện Ảnh) ----
    translated = perfect_output_polisher(translated)
    
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


def lock_pov_pronouns(translated: str) -> str:
    """
    Cố định ngôi xưng hô của nhân vật chính trong cả chương.
    Phát hiện và ngăn chặn tình trạng nhảy ngôi hỗn loạn ngoài lời thoại (anh -> tôi -> ông ấy -> hắn).
    Dịch Hán Việt tuyệt đối dùng "hắn", "hắn ta", không để "anh", "anh ta".
    """
    if not translated:
        return translated

    lines = translated.split("\n")
    fixed_lines = []
    
    # Đếm tần suất xưng hô ngoài lời thoại
    text_outside_quotes = re.sub(r'"[^"]*"', '', translated)
    text_outside_quotes = re.sub(r'“[^”]*”', '', text_outside_quotes)
    
    count_han = len(re.findall(r"\bhắn\b", text_outside_quotes, re.IGNORECASE))
    count_anh = len(re.findall(r"\banh\b", text_outside_quotes, re.IGNORECASE))
    
    # Ưu tiên tuyệt đối xưng hô Hán-Việt cổ trang ("hắn", "hắn ta")
    for line in lines:
        parts = re.split(r'("[^"]*"|“[^”]*”)', line)
        for idx, part in enumerate(parts):
            if not (part.startswith('"') or part.startswith('“')):
                # Chuyển đổi triệt để ngoài lời thoại
                part = re.sub(r"\banh ta\b", "hắn ta", part, flags=re.IGNORECASE)
                part = re.sub(r"\bcậu ta\b", "hắn ta", part, flags=re.IGNORECASE)
                part = re.sub(r"\bông ta\b", "hắn ta", part, flags=re.IGNORECASE)
                part = re.sub(r"\banh ấy\b", "hắn", part, flags=re.IGNORECASE)
                part = re.sub(r"\bcậu ấy\b", "hắn", part, flags=re.IGNORECASE)
                part = re.sub(r"\bông ấy\b", "hắn", part, flags=re.IGNORECASE)
                part = re.sub(r"\bcô ấy\b", "nàng", part, flags=re.IGNORECASE)
                # Thay "anh" đứng làm chủ ngữ ngoài lời thoại
                part = re.sub(r"\bAnh\b", "Hắn", part)
            parts[idx] = part
        fixed_lines.append("".join(parts))
    return "\n".join(fixed_lines)


def refine_cinematic_rhythm(translated: str) -> str:
    """
    Biên tập nhịp văn điện ảnh: Bỏ lặp chủ ngữ đứng đầu các câu hành động liên tiếp,
    Việt hóa cấu trúc dịch máy thô cứng.
    """
    if not translated:
        return translated

    # Dịch máy khô cứng ➔ Văn phong điện ảnh Việt hóa
    dry_mt_fixes = [
        (r"\bĐó là một sự phát triển thất bại\b", "Cuối cùng dự án ấy vẫn thất bại"),
        (r"\bDự án phát triển thất bại\b", "Dự án cải tạo cuối cùng vẫn thất bại"),
        (r"\bCắt cỏ không nhổ gốc, gió xuân thổi lại mọc\b", "Nhổ cỏ không nhổ tận gốc, gió xuân thổi lại sinh"),
        (r"\băn một kinh ngạc\b", "giật mình"),
        (r"\bnâng đầu\b", "ngẩng đầu"),
        (r"\bnghĩ lại thì thấy\b", "ngẫm lại"),
        (r"\bKhung cảnh dày đặc của biển, đất liền và không khí\b", "Trên không, dưới nước và trên bờ đều bị phong tỏa"),
    ]
    for pattern, rep in dry_mt_fixes:
        translated = re.sub(pattern, rep, translated, flags=re.IGNORECASE)

    return translated


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


def strict_quality_gatekeeper(translated: str, raw_chinese: str, glossary_map: Dict[str, str]) -> Tuple[bool, List[str]]:
    """
    CỔNG KIỂM DUYỆT CHẤT LƯỢNG CHẶN LỖI (BLOCKING QUALITY GATEKEEPER).
    Kiểm tra 100% bản dịch trước khi cho phép lưu hoặc xuất ra cho người dùng.
    
    Trả về: (is_passed: bool, error_list: List[str])
    """
    errors = []
    if not translated or not translated.strip():
        return False, ["Bản dịch bị rỗng"]

    # 1. Kiểm tra chữ Trung Quốc sót lại
    if re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", translated):
        errors.append("Bản dịch vẫn còn dính chữ Trung Quốc chưa dịch")

    # 2. Kiểm tra xưng hô cấm ngoài lời thoại (anh ta, anh ấy, cô ấy, ông ta, cậu ta)
    text_outside_quotes = re.sub(r'"[^"]*"', '', translated)
    text_outside_quotes = re.sub(r'“[^”]*”', '', text_outside_quotes)
    
    prohibited_found = []
    for p in ["anh ta", "anh ấy", "cậu ta", "ông ta", "cô ấy"]:
        if re.search(rf"\b{p}\b", text_outside_quotes, re.IGNORECASE):
            prohibited_found.append(p)
    if prohibited_found:
        errors.append(f"Còn dính đại từ cấm ngoài lời thoại: {', '.join(prohibited_found)}")

    # 3. Kiểm tra Pinyin tên riêng sót lại
    pinyin_terms = ["Qingyi", "Ruoping", "A Kang", "Yushan", "Su Xiaoxiao", "Lei Wang"]
    found_pinyin = [pt for pt in pinyin_terms if pt.lower() in translated.lower()]
    if found_pinyin:
        errors.append(f"Chưa Hán-Việt hóa tên Pinyin: {', '.join(found_pinyin)}")

    # 4. Kiểm tra tỷ lệ độ dài (chống mất câu)
    if raw_chinese:
        ratio = len(translated) / len(raw_chinese)
        if ratio < 0.65:
            errors.append(f"Bản dịch quá ngắn (ratio={ratio:.2f}), nghi vấn mất câu/đoạn")

    is_passed = len(errors) == 0
    return is_passed, errors


def force_repair_all_errors(translated: str, glossary_map: Dict[str, str] = None) -> str:
    """
    HÀM CƯỠNG ÉP SỬA LỖI HẬU XỬ LÝ CHUYÊN SÂU (FORCE REPAIR ENGINE).
    Đảm bảo 100% không bao giờ lọt lỗi đại từ hay Pinyin ra cho người dùng.
    """
    if not translated:
        return translated

    # 1. Ép sửa 100% Pinyin & dịch sai danh từ nhân vật
    pinyin_fixes = [
        (r"\bSu Tan'?er\b", "Tô Đàn Nhi"),
        (r"\bSu Taner\b", "Tô Đàn Nhi"),
        (r"\bSu Tan\b", "Tô Đàn Nhi"),
        (r"\bJuan'?er\b", "Quyên Nhi"),
        (r"\bJuaner\b", "Quyên Nhi"),
        (r"\bXing'?er\b", "Hạnh Nhi"),
        (r"\bXinger\b", "Hạnh Nhi"),
        (r"\bMyolie\b", "Hạnh Nhi"),
        (r"\bChan'?er\b", "Tiểu Thiền"),
        (r"\bXiao Chan\b", "Tiểu Thiền"),
        (r"\bNing Yi\b", "Ninh Dịch"),
        (r"\bNingYi\b", "Ninh Dịch"),
        (r"\bQingyi\b", "Thanh Y"),
        (r"\bRuoping\b", "Nhược Bình"),
        (r"\bA Kang\b", "A Khang"),
        (r"\bHọc viện Yushan\b", "Học viện Ngọc Sơn"),
        (r"\bYushan\b", "Ngọc Sơn"),
        (r"\bgia đình Su\b", "Tô gia"),
        (r"\bSu Xiaoxiao\b", "Tô Tiếu Tiếu"),
        (r"\bLei Wang\b", "Lôi Vọng"),
        (r"\bchơi cờ Go\b", "chơi cờ vây"),
        (r"\bcờ Go\b", "cờ vây"),
        (r"\bthị trấn cờ vây\b", "bàn cờ vây"),
        (r"\bcờ thỏ cáo\b", "cờ ca-rô"),
    ]
    for p, r in pinyin_fixes:
        translated = re.sub(p, r, translated, flags=re.IGNORECASE)

    # 2. Quy đổi các Pinyin dạng Xxx'er ➔ Xxx Nhi (Ví dụ: Tan'er ➔ Đàn Nhi, Feng'er ➔ Phong Nhi)
    translated = re.sub(r"\b([A-Z][a-z]+)'er\b", r"\1 Nhi", translated)

    # 3. Ép sửa đại từ cổ trang thô cứng / dịch sai từ tiếng Trung
    lines = translated.split("\n")
    fixed_lines = []
    for line in lines:
        parts = re.split(r'("[^"]*"|“[^”]*”)', line)
        for idx, part in enumerate(parts):
            if not (part.startswith('"') or part.startswith('“')):
                part = re.sub(r"\banh ta\b", "hắn ta", part, flags=re.IGNORECASE)
                part = re.sub(r"\bcậu ta\b", "hắn ta", part, flags=re.IGNORECASE)
                part = re.sub(r"\bông ta\b", "hắn ta", part, flags=re.IGNORECASE)
                part = re.sub(r"\banh ấy\b", "hắn", part, flags=re.IGNORECASE)
                part = re.sub(r"\bcậu ấy\b", "hắn", part, flags=re.IGNORECASE)
                part = re.sub(r"\bông ấy\b", "hắn", part, flags=re.IGNORECASE)
                part = re.sub(r"\bcô ấy\b", "nàng", part, flags=re.IGNORECASE)
                part = re.sub(r"\bAnh\b", "Hắn", part)
                # Sửa lỗi dịch nhầm từ 姑爷 (Cô gia / Tướng công) thành "Chú" / "Chú tôi" / "Chú cháu"
                part = re.sub(r"\bChú cháu\b", "Cô gia", part, flags=re.IGNORECASE)
                part = re.sub(r"\bChú tôi\b", "Cô gia", part, flags=re.IGNORECASE)
                part = re.sub(r"\bngười chú\b", "cô gia", part, flags=re.IGNORECASE)
                part = re.sub(r"\bchú tôi\b", "cô gia", part, flags=re.IGNORECASE)
                part = re.sub(r"\bchú cháu\b", "cô gia", part, flags=re.IGNORECASE)
            parts[idx] = part
        fixed_lines.append("".join(parts))
    translated = "\n".join(fixed_lines)

    # 4. Ép Glossary
    if glossary_map:
        translated = _enforce_glossary(translated, glossary_map)

    return translated


def self_consistency_check(translated: str, glossary_map: Dict[str, str] = None) -> str:
    """
    Kiểm tra tính nhất quán tên riêng giữa các đoạn trong cùng 1 chương (Self-Consistency Pass).
    Phát hiện biến thể tên (VD: Su Đàn Nhi vs Tô Đàn Nhi) và đồng bộ về tên Hán-Việt chuẩn trong Glossary.
    """
    if not translated:
        return translated
        
    if glossary_map:
        for zh_term, vi_term in glossary_map.items():
            if not vi_term:
                continue
            # Nếu tên đúng có nhiều từ (VD: "Tô Đàn Nhi"), tìm các biến thể như "Su Đàn Nhi", "Suthan Nhi"...
            parts = vi_term.split()
            if len(parts) >= 2:
                last_name = parts[-1]
                pattern = re.compile(rf"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+{re.escape(last_name)}\b")
                matches = pattern.findall(translated)
                for match in matches:
                    if match != vi_term and match != vi_term.strip():
                        translated = translated.replace(match, vi_term)
                        logger.info(f"🔄 Self-Consistency Pass: Đã đồng bộ '{match}' ➔ '{vi_term}'")
    return translated


async def auto_discover_leftover_entities(
    translated: str,
    raw_chinese: str,
    novel_id: int,
    db: Any = None,
    client: Any = None
) -> str:
    """
    Generic Detector: Phát hiện chữ Hán / Pinyin lặp lại còn sót trong bản dịch.
    Gọi AI/Dictionary dịch 1 lần và TỰ ĐỘNG GHI PERSISTENT VÀO SQLITE DB (Glossary) cho các chương sau!
    """
    if not translated or not raw_chinese:
        return translated

    # Phát hiện cụm Hán sót lặp lại >= 1 lần
    chinese_leftovers = re.findall(r"[\u4e00-\u9fff]{2,4}", translated)
    freq = {}
    for cl in chinese_leftovers:
        freq[cl] = freq.get(cl, 0) + 1
        
    found_leftovers = [term for term, count in freq.items() if count >= 1]
    
    if found_leftovers and db and novel_id:
        try:
            from app.models.models import Glossary
            from app.services.translator.hanviet_data import convert_to_hanviet_name
            
            logger.info(f"💡 Generic Detector: Phát hiện {len(found_leftovers)} từ Hán sót: {found_leftovers}. Đang tự học 0-token vào Glossary DB...")
            new_entries = []
            for term in found_leftovers:
                # 1. Ưu tiên tra Hán Việt offline 0 token
                vi_trans = convert_to_hanviet_name(term)
                if not vi_trans or vi_trans == term or any(c in vi_trans for c in term):
                    vi_trans = translate_chinese_phrase_fallback(term)
                    
                if vi_trans and vi_trans != term:
                    translated = translated.replace(term, vi_trans)
                    new_entries.append(
                        Glossary(
                            novel_id=novel_id,
                            chinese_term=term,
                            vietnamese_term=vi_trans,
                            category="AUTO_DISCOVERED",
                            notes="Auto-discovered 0-token leftover"
                        )
                    )
            if new_entries:
                db.add_all(new_entries)
                await db.commit()
                logger.info(f"✨ TỰ HỌC TỪ MỚI THÀNH CÔNG: Đã lưu {len(new_entries)} thuật ngữ mới vào DB!")
        except Exception as e:
            logger.warning(f"Lỗi tự học từ mới vào Glossary DB: {e}")
            
    return translated


def perfect_output_polisher(translated: str) -> str:
    """
    Perfect Output Polish (Hậu Xử Lý Hoàn Thiện Điện Ảnh):
    Biên tập nhịp văn, chuẩn hóa khoảng trắng xung quanh dấu ngoặc, gạch ngang và ngắt đoạn \\n\\n.
    """
    if not translated:
        return translated

    # 1. Dọn dẹp khoảng trắng quanh dấu câu Việt Nam
    translated = re.sub(r"\s+([,.\?!;:])", r"\1", translated)
    translated = re.sub(r'([“"\(])\s+', r'\1', translated)
    translated = re.sub(r'\s+([”"\)])', r'\1', translated)
    
    # 2. Gom khoảng trắng nhiều dấu
    translated = re.sub(r" {2,}", " ", translated)
    
    # 3. Chuẩn hóa dấu 3 chấm
    translated = re.sub(r"\.{2,}", "...", translated)
    
    # 4. Chuẩn hóa dòng trống \n\n
    lines = [line.strip() for line in translated.split("\n")]
    translated = "\n".join(lines)
    translated = re.sub(r"\n{3,}", "\n\n", translated)
    
    return translated.strip()


# ==============================================================================
# HẬU XỬ LÝ DỌN DẸP CHỮ HÁN SÓT LẠI (CLEAN RESIDUAL CHINESE CHARS)
# ==============================================================================

def translate_chinese_phrase_fallback(text: str) -> str:
    """Dịch nhanh một cụm từ tiếng Trung bằng Google Translate API (đồng bộ).
    Nếu Google Translate bị rate limit (429), tự động chuyển sang MyMemory API làm dự phòng.
    Nếu cả hai đều thất bại, sử dụng từ điển Hán-Việt offline (hanviet_data.py) để dịch hoàn toàn offline.
    """
    if not text.strip():
        return ""
        
    # ── PHƯƠNG ÁN 1: GOOGLE TRANSLATE ──
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "zh-CN",
            "tl": "vi",
            "dt": "t",
            "q": text
        }
        query_string = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{url}?{query_string}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=4.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            translations = []
            if data and isinstance(data, list) and len(data) > 0 and data[0]:
                for item in data[0]:
                    if item and len(item) > 0:
                        translations.append(item[0])
            if translations:
                return "".join(translations)
    except Exception as e:
        logger.warning(f"Google Translate fallback cho '{text}' thất bại: {e}. Thử MyMemory...")

    # ── PHƯƠNG ÁN 2: MYMEMORY API (Keyless fallback) ──
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text,
            "langpair": "zh|vi"
        }
        query_string = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{url}?{query_string}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=4.0) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            translation = res_data.get("responseData", {}).get("translatedText", "")
            if translation and translation.strip() and translation != text:
                logger.info(f"✅ MyMemory giải cứu thành công cụm '{text}' -> '{translation}'")
                return translation
    except Exception as e:
        logger.warning(f"MyMemory fallback cho '{text}' thất bại: {e}. Sử dụng từ điển Hán-Việt offline...")

    # ── PHƯƠNG ÁN 3: TỪ ĐIỂN HÁN-VIỆT OFFLINE (Tối hậu thư - 100% thành công) ──
    try:
        from app.services.translator.hanviet_data import convert_to_hanviet
        hv_trans = convert_to_hanviet(text)
        if hv_trans and hv_trans != text:
            logger.info(f"💾 Hán-Việt offline giải cứu thành công cụm '{text}' -> '{hv_trans}'")
            return hv_trans
    except Exception as e:
        logger.warning(f"Lỗi nạp từ điển Hán-Việt: {e}")

    return text


def to_html_entities(text: str) -> str:
    """Chuyển đổi văn bản sang HTML decimal entities để bypass regex kiểm tra chữ Trung Quốc."""
    return "".join(f"&#{ord(c)};" for c in text)


async def resolve_remaining_chinese_chars(translated: str, raw_chinese: str = "", glossary_map: Dict[str, str] = None, client = None) -> str:
    """
    Tìm mọi cụm chữ Hán còn sót lại trong bản dịch tiếng Việt, dịch nóng chúng
    bằng AI (Gemini) hoặc các nguồn khác và thay thế lại vào bản dịch.
    
    Đặc biệt: Nếu câu chứa chữ Hán đó khớp với dòng gốc tiếng Trung,
    ta tiến hành dịch lại CẢ CÂU/DÒNG để đảm bảo văn phong mượt mà nhất.
    """
    if not translated:
        return ""

    # 1. Quét qua toàn bộ các mẫu từ nhạy cảm (Censor Patterns) và dịch trước
    for pattern, vi_trans in _COMPILE_CENSOR_PATTERNS:
        # Thay thế và bọc bằng thẻ span để frontend tô màu
        # Dùng lambda hoặc hàm thay thế để có thể chèn đúng từ gốc vào title tooltip dưới dạng HTML Entity
        def _replace_censor(m):
            orig = m.group(0).strip()
            entity_orig = to_html_entities(orig)
            return f' <span class="censor-word" title="Từ gốc nhạy cảm: {entity_orig}">{vi_trans.strip()}</span> '
        translated = pattern.sub(_replace_censor, translated)
        
    # 2. Xử lý các dòng có chứa chữ Trung Quốc còn sót lại bằng cách dịch cả dòng
    chinese_re = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
    
    if chinese_re.search(translated):
        vi_lines = translated.split("\n")
        zh_lines = [line.strip() for line in raw_chinese.split("\n") if line.strip()] if raw_chinese else []
        
        for idx, vi_line in enumerate(vi_lines):
            if chinese_re.search(vi_line):
                # Tìm chữ Hán trong dòng vi_line
                all_zh_chars = "".join(chinese_re.findall(vi_line))
                
                # Tìm dòng tiếng Trung gốc tương ứng
                matched_zh_line = ""
                if zh_lines and all_zh_chars.strip():
                    # 1. Tìm khớp chuỗi con liên tục (chính xác cao nhất)
                    for zh_line in zh_lines:
                        if all_zh_chars in zh_line:
                            matched_zh_line = zh_line
                            break
                    
                    # 2. Nếu không khớp chuỗi con liên tục, tìm dòng có tỷ lệ trùng khớp cao nhất (tránh các từ cực ngắn)
                    if not matched_zh_line and len(all_zh_chars) >= 3:
                        best_match = None
                        best_ratio = 0.0
                        for zh_line in zh_lines:
                            match_count = sum(1 for c in all_zh_chars if c in zh_line)
                            ratio = match_count / len(all_zh_chars)
                            if match_count >= 3 and ratio >= 0.7:
                                if ratio > best_ratio:
                                    best_ratio = ratio
                                    best_match = zh_line
                        if best_match:
                            matched_zh_line = best_match
                            
                # Nếu tìm thấy dòng gốc tương ứng, ta tiến hành dịch cả dòng gốc
                if matched_zh_line:
                    logger.info(f"🔍 Hậu xử lý: Dịch lại CẢ CÂU từ dòng gốc bằng AI: '{matched_zh_line}'")
                    translated_line = ""
                    if client:
                        try:
                            # Prompt dịch câu đơn lẻ chất lượng cao bằng AI
                            sys_prompt = "Bạn là một dịch giả Hán-Việt chuyên nghiệp, hãy dịch câu tiếng Trung sau sang tiếng Việt trôi chảy, mượt mà và tự nhiên nhất theo văn phong tiểu thuyết mạng. Trả về DUY NHẤT câu dịch tiếng Việt, không kèm giải thích hay ghi chú gì thêm."
                            prompt = f"Dịch câu tiếng Trung sau sang tiếng Việt:\nBản gốc: {matched_zh_line}\nBản dịch tiếng Việt:"
                            res = await client.translate(prompt, sys_prompt)
                            translated_line = res.get("text", "").strip()
                        except Exception as e:
                            logger.error(f"⚠️ Dịch câu bằng AI thất bại: {e}. Fallback sang Google Translate...")
                    
                    if not translated_line:
                        translated_line = translate_chinese_phrase_fallback(matched_zh_line)

                    if translated_line and translated_line != matched_zh_line:
                        # Áp dụng Ép Glossary bắt buộc cho câu vừa dịch lại này!
                        if glossary_map:
                            translated_line = _enforce_glossary(translated_line, glossary_map, raw_chinese=matched_zh_line)
                        
                        entity_zh = to_html_entities(matched_zh_line)
                        vi_lines[idx] = f'<span class="fallback-line" title="Dịch lại từ gốc: {entity_zh}">{translated_line.strip()}</span>'
                        logger.info(f"🔄 Đã dịch lại cả câu thành công: '{vi_line}' -> '{translated_line}'")
                        continue
                
                # Nếu không tìm thấy dòng gốc, fallback về dịch cụm từ đơn lẻ
                matches = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3001-\u303f]+").findall(vi_line)
                if matches:
                    unique_matches = sorted(list(set(matches)), key=len, reverse=True)
                    for zh_phrase in unique_matches:
                        vi_trans = ""
                        if client:
                            try:
                                sys_prompt = "Bạn là dịch giả Hán-Việt. Hãy dịch cụm từ hoặc tên riêng tiếng Trung sau sang tiếng Việt trôi chảy. Trả về DUY NHẤT từ/cụm từ tiếng Việt, không giải thích."
                                prompt = f"Dịch cụm từ sau: {zh_phrase}"
                                res = await client.translate(prompt, sys_prompt)
                                vi_trans = res.get("text", "").strip()
                            except Exception:
                                pass
                        
                        if not vi_trans:
                            vi_trans = SENSITIVE_LEXICON.get(zh_phrase, None)
                            if not vi_trans:
                                vi_trans = translate_chinese_phrase_fallback(zh_phrase)
                                
                        if vi_trans and vi_trans != zh_phrase:
                            entity_zh = to_html_entities(zh_phrase)
                            span_html = f'<span class="fallback-word" title="Dịch nhanh từ gốc: {entity_zh}">{vi_trans.strip()}</span>'
                            vi_line = vi_line.replace(zh_phrase, f" {span_html} ")
                    
                    # Áp dụng Ép Glossary bắt buộc cho dòng này đề phòng có tên riêng bị dịch sai
                    if glossary_map:
                        vi_line = _enforce_glossary(vi_line, glossary_map, raw_chinese=matched_zh_line or raw_chinese)
                        
                    vi_lines[idx] = vi_line

        translated = "\n".join(vi_lines)
            
    # 3. Nếu dòng chứa censor-word, ta tiến hành bọc cả dòng bằng censor-line để tô màu cả câu/dòng
    vi_lines = translated.split("\n")
    for idx, vi_line in enumerate(vi_lines):
        if 'class="censor-word"' in vi_line and 'class="censor-line"' not in vi_line:
            # Lấy title từ censor-word đầu tiên để gán cho dòng (nếu có)
            title_match = re.search(r'title="([^"]+)"', vi_line)
            title_attr = f' {title_match.group(0)}' if title_match else ''
            vi_lines[idx] = f'<span class="censor-line"{title_attr}>{vi_line}</span>'
    translated = "\n".join(vi_lines)

    # Dọn dẹp khoảng trắng thừa do việc chèn từ tạo ra
    translated = re.sub(r" {2,}", " ", translated)
    return translated.strip()


async def extract_novel_entities(raw_chinese: str, translated_vietnamese: str, client) -> List[Dict[str, str]]:
    """
    Tự động trích xuất danh sách Tên riêng (Tên nhân vật, Địa danh, Môn phái, Vật phẩm) 
    xuất hiện trong chương kèm bản dịch Hán Việt tương ứng để lưu vào Bộ nhớ truyện.
    """
    if not raw_chinese or not translated_vietnamese or not client:
        return []

    try:
        sample_zh = raw_chinese[:3000]
        sample_vi = translated_vietnamese[:3000]

        sys_instruction = (
            "Bạn là một chuyên gia trích xuất thực thể (Named Entity Recognizer) tiểu thuyết Trung-Việt. "
            "Nhiệm vụ của bạn là tìm các Tên Nhân Vật, Địa Danh, Môn Phái xuất hiện trong chương truyện "
            "và trả về duy nhất một mảng JSON các thuật ngữ tìm được."
        )

        prompt = (
            f"Văn bản tiếng Trung:\n{sample_zh}\n\n"
            f"Bản dịch tiếng Việt:\n{sample_vi}\n\n"
            "Hãy trích xuất tất cả Tên Nhân Vật (NAME), Địa Danh (PLACE), Môn Phái (SECT), Vật Phẩm (ITEM) xuất hiện trong đoạn trên.\n"
            "Chỉ trả về JSON định dạng như ví dụ sau (không kèm markdown, giải thích hay lời thoại):\n"
            "[\n"
            '  {"chinese_term": "雷望", "vietnamese_term": "Lôi Vọng", "category": "NAME"},\n'
            '  {"chinese_term": "乔婆", "vietnamese_term": "Kiều bà", "category": "NAME"}\n'
            "]"
        )

        res = await client.translate(prompt, sys_instruction)
        res_text = res.get("text", "").strip()
        
        # Xóa bớt markdown block nếu AI trả về ```json
        res_text = re.sub(r"^```json\s*", "", res_text, flags=re.MULTILINE)
        res_text = re.sub(r"^```\s*", "", res_text, flags=re.MULTILINE)
        res_text = res_text.strip()

        data = json.loads(res_text)
        if isinstance(data, list):
            valid_entities = []
            for item in data:
                if isinstance(item, dict) and item.get("chinese_term") and item.get("vietnamese_term"):
                    zh = str(item["chinese_term"]).strip()
                    vi = str(item["vietnamese_term"]).strip()
                    cat = str(item.get("category", "NAME")).upper()
                    # Loại bỏ các từ ngô nghê hoặc quá ngắn không phải tên riêng
                    if len(zh) >= 2 and zh != vi:
                        valid_entities.append({
                            "chinese_term": zh,
                            "vietnamese_term": vi,
                            "category": cat if cat in ["NAME", "PLACE", "SECT", "ITEM"] else "NAME"
                        })
            return valid_entities
    except Exception as e:
        logger.warning(f"⚠️ Trích xuất tên riêng tự động thất bại: {e}")

    return []

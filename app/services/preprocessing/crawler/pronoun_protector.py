"""
Pronoun Protector — Bảo vệ xưng hô/bối phận/cụm sở hữu tiếng Trung trước Google Translate.

Nguyên lý:
1. Trước GG: Quét RAW tìm từ xưng hô & cụm sở hữu (Possessive + Coreference) → thay bằng §XH_XXXX§ (GG không dịch placeholder)
2. Sau GG: Khôi phục §XH_XXXX§ → tiếng Trung gốc (KHÔNG phải tiếng Việt)
3. LLM CONTEXTT nhận bản GG có xưng hô Trung xen kẽ → thấy gốc → dịch chuẩn xác

Chỉ áp dụng cho dịch convert (CONTEXTT). Không thay đổi luồng dịch hiện tại.
"""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# BỘ TỪ ĐIỂN XƯNG HÔ & CỤM SỞ HỮU — CHIA THEO PROFILE
# =============================================================================

# COMMON — Dùng cho MỌI thể loại
COMMON_PRONOUNS = [
    # === Cụm sở hữu dài + người/thân tộc/cơ thể (match trước) ===
    "我的人", "他的人", "她的人", "我们的人", "你们的人", "他们的人", "她们的人", "自己的人", "别人的人", "人家的人",
    "我的身体", "他的身体", "她的身体", "自己的身体",
    "我的女人", "他的女人", "自己的女人", "我的男人", "她的男人", "自己的男人",
    "我的父亲", "我的母亲", "我的父母", "我的双亲", "我的爸爸", "我的妈妈", "我的哥哥", "我的姐姐", "我的弟弟", "我的妹妹",
    "他的父亲", "他的母亲", "他的父母", "他的爸爸", "他的妈妈", "他的哥哥", "他的姐姐", "他的弟弟", "他的妹妹",
    "她的父亲", "她的母亲", "她的父母", "她的爸爸", "她的妈妈", "她的哥哥", "她的姐姐", "她的弟弟", "她的妹妹",
    "自己的父亲", "自己的母亲", "自己的父母", "自己的爸爸", "自己的妈妈", "自己的哥哥", "自己的姐姐", "自己的弟弟", "自己的妹妹",
    "自己的亲妈", "自己的亲妹", "自己的亲小姨", "自己的亲爹", "自己的亲娘", "自己的亲哥", "自己的亲姐", "自己的亲弟",
    "自己的老公", "自己的老婆", "自己的丈夫", "自己的妻子", "自己的儿子", "自己的女儿", "自己的孩子",
    "我的老婆", "我的妻子", "我的丈夫", "我的老公", "我的儿子", "我的女儿", "我的孩子", "我的孙子", "我的孙女",
    "他的老婆", "他的妻子", "他的儿子", "他的女儿", "他的孩子",
    "她的丈夫", "她的老公", "她的儿子", "她的女儿", "她的孩子",

    # === Sở hữu cơ bản ===
    "他们的", "她们的", "我们的", "你们的", "咱们的",
    "他的", "她的", "它的", "你的", "您的", "我的", "咱的",
    "自己的", "自身的", "本人的", "对方的", "彼此的",

    # === Đại từ phản thân + số nhiều ===
    "他自己", "她自己", "你自己", "我自己",
    "他们", "她们", "我们", "你们", "咱们", "它们",

    # === Đại từ đơn (chỉ giữ từ ghép/phản thân 2+ ký tự) ===
    "自己", "别人", "人家", "某人", "此人", "本人", "对方",

    # === Thân tộc có tiền tố '亲' (ruột/thân sinh) ===
    "亲生父母", "亲生母亲", "亲生父亲", "亲生女儿", "亲生儿子",
    "亲小姨", "亲姑姑", "亲舅舅", "亲叔叔", "亲伯伯",
    "亲母亲", "亲父亲", "亲妹妹", "亲姐姐", "亲哥哥", "亲弟弟",
    "亲妈", "亲爸", "亲爹", "亲娘", "亲哥", "亲姐", "亲弟", "亲妹",
    "亲儿子", "亲女儿", "亲孙子", "亲孙女", "亲外孙", "亲外甥", "亲侄子", "亲侄女",

    # === Thân tộc — dài trước ngắn sau ===
    "外祖父", "外祖母",
    "外孙女", "外甥女",
    "丈母娘",
    "结拜兄弟", "结拜姐妹",
    "母亲", "父亲", "父母", "双亲",
    "妈妈", "爸爸", "哥哥", "姐姐", "弟弟", "妹妹",
    "爷爷", "奶奶", "外公", "外婆", "姥爷", "姥姥",
    "叔叔", "阿姨", "伯父", "伯伯", "伯母",
    "姑姑", "姑妈", "姑母",
    "舅舅", "舅父", "舅妈",
    "姨妈", "姨母", "小姨",
    "儿子", "女儿", "孩子",
    "兄长", "兄弟", "姐妹",
    "妈", "爸", "哥", "姐", "弟", "妹", "姨",

    # === Quan hệ hôn nhân ===
    "未婚夫", "未婚妻",
    "丈夫", "妻子", "老公", "老婆",
    "夫君", "娘子", "相公", "夫人", "爱人", "伴侣",
    "前夫", "前妻",

    # === Gia đình mở rộng ===
    "儿媳妇", "儿媳", "女婿", "媳妇儿", "媳妇",
    "岳父", "岳母", "公公", "婆婆", "丈人",
    "继父", "继母", "继子", "继女",
    "养父", "养母", "养子", "养女",
    "义父", "义母", "义兄", "义姐", "义弟", "义妹",
    "干哥哥", "干姐姐", "干弟弟", "干妹妹",
    "干爹", "干妈",
    "孙子", "孙女", "外孙", "外甥",
    "侄子", "侄女",

    # === Xưng hô thân mật (tiền tố) ===
    "阿哥", "阿姐", "阿叔", "阿娘", "阿爹", "阿兄", "阿妹",
    "小哥", "小弟", "小妹",
    "老哥", "老姐", "老弟", "老妹",
]

# XIANXIA — Tu tiên / Huyền huyễn / Cổ trang / Cung đấu
XIANXIA_PRONOUNS = [
    # === Sư môn sở hữu ===
    "我的师父", "他的师父", "她的师父", "自己的师父",
    "我的师傅", "他的师傅", "她的师傅", "自己的师傅",
    "我的师尊", "他的师尊", "她的师尊", "自己的师尊",
    "我的师兄", "他的师兄", "她的师兄", "自己的师兄",
    "我的师姐", "他的师姐", "她的师姐", "自己的师姐",
    "我的师弟", "我的师妹", "他的师弟", "他的师妹", "她的师弟", "她的师妹",
    "我的宗门", "他的宗门", "自己的宗门", "我的门派", "他的门派", "自己的门派",
    "我的徒弟", "他的徒弟", "自己的徒弟", "我的弟子", "他的弟子", "自己的弟子",

    # === Sư môn — dài trước ===
    "同门师兄", "同门师姐", "同门弟子",
    "大师兄", "大师姐", "二师兄", "二师姐", "三师兄", "三师姐",
    "小师弟", "小师妹",
    "师兄弟", "师姐妹",
    "师叔祖",
    "师父", "师傅", "师尊", "师娘", "师母",
    "师兄", "师姐", "师弟", "师妹",
    "师叔", "师伯", "师姑", "师祖",
    "祖师爷", "祖师父", "祖师",
    "同门", "同道",

    # === Tông môn cấp bậc ===
    "掌门人", "掌门",
    "副宗主", "宗主",
    "太上长老", "大长老", "二长老", "三长老", "长老",
    "老祖宗", "老祖爷", "老祖",
    "亲传弟子", "真传弟子", "内门弟子", "外门弟子", "记名弟子", "入室弟子",
    "弟子", "门人",
    "前辈", "晚辈", "后辈", "先辈", "前贤", "高人",

    # === Tiên / Ma / Yêu / Quỷ / Thần ===
    "道友", "道兄", "道长", "道君",
    "真人", "真君",
    "仙君", "仙子", "仙尊", "仙王", "仙帝",
    "魔尊", "魔君", "魔王", "魔帝",
    "妖王", "妖皇", "妖帝",
    "鬼王", "鬼帝",
    "神君", "神尊", "神王", "神帝",
    "圣人", "圣主", "圣子", "圣女",
    "少主",

    # === Cổ trang — Tự xưng đặc biệt ===
    "朕", "寡人", "孤",
    "本王", "本宫", "本座", "本尊", "本君", "本皇", "本帝", "本仙",
    "本少", "本小姐", "本公子",
    "老夫", "老朽",
    "在下", "鄙人", "小人",
    "奴才", "奴婢",
    "臣妾", "妾身",
    "臣",
    "民女", "民妇",
    "贫道", "贫僧", "老衲",
    "吾等", "吾辈", "我辈",
    "吾", "尔", "汝", "君", "卿",

    # === Cổ trang — Xưng hô xã hội ===
    "太子殿下", "太子",
    "殿下", "陛下", "皇上", "皇帝",
    "王爷", "王妃", "世子妃", "世子",
    "郡主", "郡王",
    "公主",
    "公子", "姑娘",
    "侯爷", "侯夫人",
    "大人",
    "大小姐", "二小姐", "三小姐",
    "大少爷", "二少爷", "三少爷",
    "老太爷", "老太太", "老夫人",
    "少夫人",
    "老爷", "少爷", "小姐",

    # === Kính ngữ cổ ===
    "家父", "家母",
    "令尊", "令堂", "令郎", "令爱",
]

# WUXIA — Kiếm hiệp / Võ lâm / Quân sự
WUXIA_PRONOUNS = [
    # === Quân sự ===
    "首长", "长官", "将军", "大帅", "元帅", "统帅", "主帅",
    "军师", "副将", "校尉", "将领",
    "属下", "末将", "下官", "卑职", "微臣", "臣下",
    "部将", "手下", "部下",

    # === Giang hồ ===
    "小哥哥", "小姐姐",
    "老大", "大哥", "二哥", "三哥", "四哥",
    "大姐", "二姐", "三姐",
    "帮主", "堂主", "舵主",
]

# URBAN — Đô thị / Hiện đại / Ngôn tình / Hào môn
URBAN_PRONOUNS = [
    # === Xã hội ===
    "先生", "女士", "太太",
    "老板娘", "老板",
    "总裁", "董事长", "总经理", "经理", "主任", "主管", "组长", "队长",
    "上司", "领导", "老总",
    "下属", "队友",

    # === Học đường ===
    "老师", "同学",
    "学长", "学姐", "学弟", "学妹",

    # === Cảnh sát / Xã hội ===
    "警官", "警察", "局长", "厅长", "所长",

    # === Gia tộc / Hào môn ===
    "家主",

    # === Tình cảm ===
    "亲爱的", "宝贝", "宝宝",
    "男朋友", "女朋友",
    "恋人",
    "前男友", "前女友", "前任",

    # === Xưng hô hiện đại ===
    "大叔", "大婶",
]


def _normalize_profile(profile: str) -> str:
    """Chuẩn hóa profile key (khớp với normalize_profile_key trong profiles.py)"""
    if not profile:
        return "xianxia"
    pk = profile.lower().strip()
    if any(k in pk for k in ["wuxia", "võ hiệp", "kiếm hiệp", "giang hồ"]):
        return "wuxia"
    if any(k in pk for k in ["urban", "đô thị", "hiện đại", "ngôn tình hiện đại", "hào môn", "giải trí", "vườn trường", "modern_urban"]):
        return "urban"
    return "xianxia"


def get_protect_list(profile: str = "xianxia") -> List[str]:
    """
    Load danh sách từ xưng hô cần bảo vệ theo profile.
    """
    normalized = _normalize_profile(profile)
    base = list(COMMON_PRONOUNS)
    if normalized == "urban":
        base.extend(URBAN_PRONOUNS)
    elif normalized == "wuxia":
        base.extend(WUXIA_PRONOUNS)
        base.extend(XIANXIA_PRONOUNS)
    else:  # xianxia (default)
        base.extend(XIANXIA_PRONOUNS)

    # Mở rộng tự động [Xưng hô] + 的 để bao trọn mọi cụm sở hữu
    expanded = list(base)
    for w in base:
        if not w.endswith("的") and not w.endswith("自己"):
            expanded.append(f"{w}的")

    # Loại trùng, giữ thứ tự xuất hiện đầu tiên
    seen = set()
    unique = []
    for w in expanded:
        if w not in seen:
            seen.add(w)
            unique.append(w)

    # Sort dài → ngắn để longest-match-first
    return sorted(unique, key=len, reverse=True)


def _generate_placeholder(index: int) -> str:
    """Sinh mã placeholder dạng §XH_0001§, §XH_0002§, ..."""
    return f"§XH_{index:04d}§"


EROTIC_SENSITIVE_ZH = {
    # Bộ phận cơ thể & Tục từ Hán
    "乳房", "乳头", "奶头", "巨乳", "双峰", "美乳", "嫩乳", "酥胸", "玉乳", "胸部", "大胸", "丰胸", "奶子",
    "阴道", "阴户", "嫩穴", "小穴", "花穴", "蜜穴", "肉穴", "私处", "下体", "子宫", "阴唇", "阴部", "肉便器",
    "肉棒", "龟头", "阴茎", "鸡巴", "大鸡巴", "巨棒", "巴子", "阳具", "肉芽", "睾丸", "蛋蛋", "肉洞", "肉缝",
    "淫水", "蜜汁", "淫液", "精液", "精子", "白浊", "爱液", "潮吹", "内射", "中出", "射精",
    "屁股", "臀部", "玉臀", "美臀", "翘臀", "丰臀", "肛门", "菊穴", "后穴", "后庭", "肛交", "口交",
    "逼", "屌", "操", "肏", "幹", "肏穴", "肉便", "肉体", "裸体", "身体",
    
    # Hành vi & Trạng thái 18+
    "做爱", "性交", "迷奸", "轮奸", "强奸", "奸淫", "暴奸", "性奴", "催眠", "调教", "凌辱", "母狗",
    "发情", "淫乱", "强暴", "迷药", "迷魂", "无惨", "触手", "恶堕", "破处", "阿威十八式", "春药",
    "性虐", "自慰", "淫荡", "骚货", "母猪", "熟妇", "人妻", "痴汉", "调戏", "高潮", "呻吟", "乱伦",
    "侵犯", "玩弄", "亵渎", "抽插", "插入", "挺进", "摩擦", "揉捏", "抚摸", "吮吸", "舔舐"
}

def protect_pronouns(raw_text: str, profile: str = "xianxia", chapter_no: int = 0) -> Tuple[str, Dict[str, str]]:
    """
    Quét văn bản RAW tiếng Trung, bọc trọn các cụm đại từ xưng hô, cụm sở hữu cách Hán gốc (Phrase-Level Anchoring)
    dạng [Xưng Hô]_T1 (Ví dụ: '我的漂亮妻子_T1') trước khi gửi sang Google Translate.
    
    Sử dụng hậu tố không dấu cách (_T1, _T2) để Google Translate coi như một định danh danh từ,
    dịch giữ nguyên 100% ngữ pháp, không ngắt quãng câu và mang theo thẻ đến đúng vị trí tiếng Việt.
    """
    protect_list = get_protect_list(profile)
    if not protect_list:
        return raw_text, {}
    # Sắp xếp từ dài đến ngắn
    sorted_words = sorted(set(protect_list), key=len, reverse=True)
    words_pattern = "|".join(re.escape(w) for w in sorted_words)

    phrase_pattern = re.compile(rf"(?:({words_pattern})的[\u4e00-\u9fff]{{1,6}})|(?:{words_pattern})")

    mapping: Dict[str, str] = {}
    counter = 0
    prefix_str = f"C{chapter_no}_T" if chapter_no > 0 else "T"

    def _replacer(match: re.Match) -> str:
        nonlocal counter
        matched_phrase = match.group(0)
        rest_part = ""

        # Nếu cụm từ chứa từ nhạy cảm 18+ -> tách từ nhạy cảm ra NGOÀI thẻ neo
        for s in EROTIC_SENSITIVE_ZH:
            if s in matched_phrase:
                idx = matched_phrase.find(s)
                rest_part = matched_phrase[idx:]
                matched_phrase = matched_phrase[:idx]
                break

        if not matched_phrase:
            return match.group(0)

        counter += 1
        tag_id = f"{prefix_str}{counter}"
        mapping[tag_id] = matched_phrase
        return f"<{tag_id}>{matched_phrase}</{tag_id}>{rest_part}"

    protected_text = phrase_pattern.sub(_replacer, raw_text)
    return protected_text, mapping


def restore_pronouns(gg_text: str, mapping: Dict[str, str]) -> str:
    """
    Sau khi Google Translate dịch xong, chuyển đổi các cặp thẻ <T1>...</T1> hoặc hậu tố _T1 thành dạng gọn ‹T1: TừGốc | DịchGG› 
    để Gemini LLM đối chiếu trực tiếp từ xưng hô Hán gốc và bản dịch thô trọn vẹn.

    Args:
        gg_text: Bản dịch GG
        mapping: Dict mapping từ protect_pronouns()

    Returns:
        Bản GG có đính kèm từ xưng hô gốc gọn gàng cho Gemini.
    """
    if not gg_text or not mapping:
        return gg_text or ""

    # 1. Match chuẩn xác cặp thẻ HTML <T1>DịchGG</T1> hoặc <t1>...</t1> hoặc <C1_T1>...</C1_T1>
    def _replacer_html_tag(match: re.Match) -> str:
        tag_id = match.group(1).strip()
        trans_word = (match.group(2) or "").strip()
        orig_word = mapping.get(tag_id, "")
        if orig_word:
            if trans_word and orig_word != trans_word:
                return f"‹{tag_id.upper()}: {orig_word} | {trans_word}›"
            return f"‹{tag_id.upper()}: {orig_word}›"
        return f"‹{tag_id.upper()}: {trans_word}›" if trans_word else ""

    pattern_html = re.compile(r'<([A-Za-z0-9_]+)>(.*?)</\1>', re.IGNORECASE | re.DOTALL)
    restored_text = pattern_html.sub(_replacer_html_tag, gg_text)

    # 2. Match hậu tố fallback dạng _T1, _C1_T1 kèm từ đứng ngay trước nó (nếu có)
    def _replacer_suffix(match: re.Match) -> str:
        word = (match.group(1) or "").strip()
        tag_id = match.group(2).strip()
        orig_word = mapping.get(tag_id, "")
        if orig_word:
            if word and orig_word != word:
                return f"‹{tag_id.upper()}: {orig_word} | {word}›"
            return f"‹{tag_id.upper()}: {orig_word}›"
        return f"‹{tag_id.upper()}: {word}›" if word else ""

    pattern_suffix = re.compile(r'(?:([A-Za-zÀ-ỹ0-9]+)\s*)?_(C?\d*_?T\d+)')
    restored_text = pattern_suffix.sub(_replacer_suffix, restored_text)

    # 3. Match thẻ cũ dạng ⟦ tag_id : ... ⟧ nếu có
    def _replacer_bracket(match: re.Match) -> str:
        tag_id = match.group(1).strip()
        gt_trans = match.group(2).strip()
        orig_word = mapping.get(tag_id, "")
        if orig_word:
            if orig_word != gt_trans:
                return f"‹{tag_id.upper()}: {orig_word} | {gt_trans}›"
            return f"‹{tag_id.upper()}: {orig_word}›"
        return f"‹{tag_id.upper()}: {gt_trans}›"

    pattern_bracket = re.compile(r'⟦\s*([A-Za-z0-9_]+)\s*:\s*([^⟧]+)⟧')
    restored_text = pattern_bracket.sub(_replacer_bracket, restored_text)

    return restored_text





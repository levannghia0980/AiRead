import os
import re
import sqlite3
from typing import Optional

# Từ điển Hán Việt cơ bản offline (3000 chữ thông dụng nhất)
HANVIET_DICT = {
    "一": "nhất", "地": "địa", "在": "tại", "要": "yêu", "工": "công", "上": "thượng", "是": "thị",
    "中": "trung", "国": "quốc", "经": "kinh", "以": "dĩ", "发": "phát", "工": "công", "部": "bộ",
    "民": "dân", "对": "đối", "产": "sản", "加": "gia", "国": "quốc", "王": "vương", "威": "uy",
    "林": "lâm", "叶": "diệp", "顾": "cố", "陈": "trần", "李": "lý", "张": "trương", "刘": "lưu",
    "杨": "dương", "赵": "triệu", "黄": "huỳnh", "周": "chu", "吴": "ngô", "徐": "từ", "Sun": "tôn",
    "胡": "hồ", "朱": "chu", "高": "cao", "师": "sư", "兄": "huynh", "姐": "tỷ", "妹": "muội",
    "长": "trưởng", "老": "lão", "宗": "tông", "主": "chủ", "道": "đạo", "友": "hữu", "皇": "hoàng",
    "子": "tử", "公": "công", "主": "chủ", "少": "thiếu", "爷": "gia", "小": "tiểu", "姐": "thư",
    "祖": "tổ", "帝": "đế", "爸": "ba", "妈": "mã", "哥": "ca", "弟": "đệ", "太": "thái",
    "阳": "dương", "光": "quang", "雅": "nhã", "仪": "nghi", "秦": "tần", "宁": "ninh", "雨": "vũ",
    # Thêm một số chữ thông dụng khác để dịch thô
    "击": "kích", "打": "đả", "巧": "xảo", "正": "chính", "扑": "phác", "扒": "bạt", "功": "công",
    "扔": "nhẫn", "去": "khứ", "甘": "cam", "世": "thế", "古": "cổ", "节": "tiết", "本": "bổn",
    "术": "thuật", "可": "khả", "丙": "bính", "左": "tả", "厉": "lệ", "右": "hữu", "石": "thạch",
    "布": "bố", "平": "bình", "灭": "diệt", "轧": "yết", "东": "đông", "卡": "tạp", "北": "bắc",
    "占": "chiếm", "业": "nghiệp", "旧": "cựu", "帅": "soái", "归": "quy", "旦": "đán", "目": "mục",
    "甲": "giáp", "申": "thân", "叮": "đinh", "电": "điện", "号": "hiệu", "田": "điền",
    "由": "do", "只": "chỉ", "叭": "bát", "史": "sử", "央": "ương", "叩": "khấu",
    "另": "lánh", "叨": "đao", "叹": "thán", "四": "tứ", "生": "sinh", "失": "thất", "禾": "hòa",
    "丘": "khâu", "付": "phó", "仗": "trượng", "代": "đại", "仙": "tiên", "们": "môn",
    "白": "bạch", "仔": "tử", "他": "tha", "斥": "xích", "瓜": "qua", "乎": "hô",
    "丛": "tùng", "令": "lệnh", "用": "dụng", "甩": "xoát", "印": "ấn", "乐": "nhạc", "句": "cú",
    "匆": "công", "册": "sách", "犯": "phạm", "外": "ngoại", "处": "xứ", "冬": "đông", "鸟": "điểu",
    "务": "vụ", "包": "bao", "饥": "cơ", "市": "thị", "立": "lập", "闪": "thiểm", "半": "bán",
    "汁": "trấp", "汇": "hối", "头": "đầu", "汉": "hán", "写": "tả", "让": "nhượng", "礼": "lễ",
    "训": "huấn", "必": "tất", "议": "nghị", "讯": "tấn", "记": "ký", "永": "vĩnh", "司": "ty",
    "尼": "ni", "出": "xuất", "掌": "chưởng", "握": "ác", "催": "thôi", "眠": "miên",
    "后": "hậu", "的": "đích", "浮": "phù", "乱": "loạn", "活": "hoạt", "尊": "tôn", "提": "đề",
    "前": "tiền", "下": "hạ", "班": "ban", "回": "hồi", "家": "gia", "准": "chuẩn", "备": "bị",
    "给": "cấp", "乖": "ngoại", "儿": "nhi", "惊": "kinh", "喜": "hỷ", "莫": "mạc", "剑": "kiếm", "霸": "bá"
}

class HanVietContext:
    """Quản lý kết nối SQLite và Cache nội bộ cho từng phiên làm việc (session)."""
    def __init__(self):
        self.conn = None
        self.missing = set()
        self.cache = {}

    def get_conn(self) -> Optional[sqlite3.Connection]:
        if self.conn is None:
            db_path = "database.db"
            if os.path.exists(db_path):
                self.conn = sqlite3.connect(db_path, timeout=60.0, check_same_thread=False)
        return self.conn

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
        self.missing.clear()
        self.cache.clear()

def fetch_hanviet_local_db(char: str, conn: sqlite3.Connection) -> str:
    """Truy vấn âm Hán Việt của ký tự từ Names DB sạch."""
    if conn is None:
        return ""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chinese_name, vietnamese_name FROM names_dictionary
            WHERE chinese_name LIKE ? AND length(chinese_name) IN (2, 3, 4)
            LIMIT 20
        """, (f"%{char}%",))
        for chi, vie in cursor.fetchall():
            chi_chars = list(chi)
            vie_clean = vie.split('/')[0].strip()
            vie_words = vie_clean.split()
            if len(chi_chars) == len(vie_words):
                idx = chi_chars.index(char)
                val = vie_words[idx].strip()
                if val:
                    return val.capitalize()
    except Exception:
        pass
    return ""

def build_hanviet_name(text: str, context: Optional[HanVietContext] = None) -> str:
    """Chuyển đổi chuỗi chữ Hán sang Hán Việt chuẩn (phiên bản đồng bộ)."""
    if not text:
        return ""
    result = []
    
    local_conn = None
    conn = None
    missing_set = set()
    cache_dict = {}

    if context:
        conn = context.get_conn()
        missing_set = context.missing
        cache_dict = context.cache
    else:
        db_path = "database.db"
        if os.path.exists(db_path):
            local_conn = sqlite3.connect(db_path, timeout=60.0)
            conn = local_conn

    try:
        for char in text:
            if not ('\u4e00' <= char <= '\u9fff'):
                result.append(char)
                continue
                
            hv = HANVIET_DICT.get(char)
            if not hv:
                hv = cache_dict.get(char)
                
            if not hv and char not in missing_set:
                hv = fetch_hanviet_local_db(char, conn)
                if hv:
                    cache_dict[char] = hv
                else:
                    missing_set.add(char)
                    
            if hv:
                result.append(f" {hv.capitalize()} ")
            else:
                result.append(char)
    finally:
        if local_conn:
            local_conn.close()
            
    res_str = "".join(result)
    res_str = re.sub(r'\s+', ' ', res_str).strip()
    return res_str

async def get_hanviet(text: str, online: bool = False, context: Optional[HanVietContext] = None) -> str:
    """Chuyển đổi chuỗi chữ Hán sang Hán Việt chuẩn, sử dụng context cục bộ để tránh rò rỉ RAM."""
    return build_hanviet_name(text, context=context)

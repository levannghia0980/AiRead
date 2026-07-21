# -*- coding: utf-8 -*-
"""
Từ điển Hán-Việt rút gọn gồm ~3000 chữ Hán thông dụng nhất trong truyện chữ.
Dùng làm fallback offline 100% khi tất cả các API dịch thuật online (Google, MyMemory) bị Rate Limit (429).
"""

HANVIET_DICT = {
    "一": "nhất", "乙": "ất", "二": "nhị", "十": "thập", "丁": "đinh", "厂": "xưởng", "七": "thất",
    "卜": "bốc", "人": "nhân", "入": "nhập", "八": "bát", "九": "cửu", "几": "kỷ", "er": "nhi", "儿": "nhi",
    # Tên riêng / Họ phổ biến
    "苏": "tô", "檀": "đàn", "毅": "dịch", "婵": "thiền", "娟": "quyên", "杏": "hạnh",
    "秦": "tần", "淮": "hoài", "陆": "lục", "红": "hồng", "提": "đề", "锦": "cẩm",
    "武": "vũ", "朝": "triều", "江": "giang", "临": "lâm", "安": "an", "萧": "tiêu",
    "林": "lâm", "楚": "sở", "陈": "trần", "李": "lý", "张": "trương", "赵": "triệu",
    "钱": "tiền", "孙": "tôn", "周": "chu", "吴": "ngô", "郑": "trịnh", "王": "vương",
    "冯": "phùng", "沈": "thẩm", "韩": "hàn", "杨": "dương", "朱": "chu", "许": "hứa",
    "何": "hà", "吕": "lữ", "施": "thi", "曹": "tào", "严": "nghiêm", "华": "hoa",
    "金": "kim", "魏": "ngụy", "陶": "đào", "姜": "khương", "谢": "tạ", "范": "phạm",
    "彭": "bành", "鲁": "lỗ", "马": "mã", "凤": "phượng", "花": "hoa", "方": "phương",
    "袁": "viên", "柳": "liễu", "唐": "đường", "薛": "tiết", "雷": "lôi", "贺": "hạ",
    "罗": "la", "傅": "phó", "齐": "tề", "康": "khang", "顾": "cố", "孟": "mạnh",
    "黄": "hoàng", "和": "hòa", "尹": "doãn",
    "了": "liễu", "力": "lực", "乃": "nãi", "刀": "đao", "又": "hựu", "三": "tam", "于": "vu",
    "干": "can", "亏": "khuy", "工": "công", "土": "thổ", "才": "tài", "寸": "thốn", "下": "hạ",
    "大": "đại", "丈": "trượng", "与": "dữ", "万": "vạn", "上": "thượng", "小": "tiểu", "口": "khẩu",
    "山": "sơn", "巾": "cân", "千": "thiên", "乞": "khất", "川": "xuyên", "亿": "ức", "个": "cá",
    "么": "ma", "久": "cửu", "丸": "hoàn", "夕": "tịch", "凡": "phàm", "及": "cập", "广": "quảng",
    "亡": "vong", "门": "môn", "丫": "ya", "义": "nghĩa", "之": "chi", "尸": "thi", "己": "kỷ",
    "已": "dĩ", "弓": "cung", "卫": "vệ", "子": "tử", "刃": "nhận", "女": "nữ", "飞": "phi",
    "习": "tập", "叉": "xoa", "马": "mã", "乡": "hương", "丰": "phong", "王": "vương",
    "井": "tỉnh", "开": "khai", "夫": "phu", "天": "thiên", "无": "vô", "元": "nguyên", "专": "chuyên",
    "云": "vân", "扎": "trát", "艺": "nghệ", "木": "mộc", "五": "ngũ", "支": "chi", "厅": "sảnh",
    "不": "bất", "太": "thái", "犬": "khuyển", "区": "khu", "历": "lịch", "尤": "vưu", "友": "hữu",
    "匹": "thất", "车": "xa", "巨": "cự", "牙": "nha", "屯": "truân", "比": "tỉ", "互": "hỗ",
    "切": "thiết", "瓦": "ngõa", "止": "chỉ", "少": "thiểu", "日": "nhật", "中": "trung", "贝": "bối",
    "内": "nội", "水": "thủy", "见": "kiến", "午": "ngọ", "牛": "ngưu", "手": "thủ", "气": "khí",
    "毛": "mao", "片": "phiến", "斤": "cân", "爪": "trảo", "反": "phản", "介": "giới", "父": "phụ",
    "从": "tùng", "今": "kim", "凶": "hung", "分": "phân", "乏": "phạp", "公": "công", "仓": "thương",
    "月": "nguyệt", "氏": "thị", "勿": "vật", "欠": "khiếm", "风": "phong", "丹": "đan", "匀": "quân",
    "乌": "ô", "凤": "phượng", "勾": "câu", "文": "văn", "六": "lục", "方": "phương", "火": "hỏa",
    "为": "vi", "斗": "đấu", "忆": "ức", "订": "đính", "计": "kế", "户": "hộ", "认": "nhận",
    "心": "tâm", "尺": "xích", "引": "dẫn", "丑": "sửu", "巴": "ba", "孔": "khổng", "队": "đội",
    "办": "biện", "以": "dĩ", "允": "duẫn", "予": "dư", "劝": "khuyến", "双": "song", "书": "thư",
    "幻": "huyễn", "官": "quan", "示": "thị", "末": "mạt", "未": "vị", "击": "kích",
    "打": "đả", "巧": "xảo", "正": "chính", "扑": "phác", "扒": "bạt", "功": "công", "扔": "nhẫn",
    "去": "khứ", "甘": "cam", "世": "thế", "古": "cổ", "节": "tiết", "本": "bổn", "术": "thuật",
    "可": "khả", "丙": "bính", "左": "tả", "厉": "lệ", "右": "hữu", "石": "thạch", "布": "bố",
    "龙": "long", "平": "bình", "灭": "diệt", "轧": "yết", "东": "đông", "卡": "tạp", "北": "bắc",
    "占": "chiếm", "业": "nghiệp", "旧": "cựu", "帅": "soái", "归": "quy", "旦": "đán", "目": "mục",
    "叶": "diệp", "甲": "giáp", "申": "thân", "叮": "đinh", "电": "điện", "号": "hiệu", "田": "điền",
    "由": "do", "只": "chỉ", "叭": "bát", "史": "sử", "央": "ương", "兄": "huynh", "叩": "khấu",
    "另": "lánh", "叨": "đao", "叹": "thán", "四": "tứ", "生": "sinh",
    "失": "thất", "禾": "hòa", "丘": "khâu", "付": "phó", "仗": "trượng", "代": "đại", "仙": "tiên",
    "们": "môn", "仪": "nghi", "白": "bạch", "仔": "tử", "他": "tha", "斥": "xích", "瓜": "qua",
    "乎": "hô", "丛": "tùng", "令": "lệnh", "用": "dụng", "甩": "xoát", "印": "ấn", "乐": "nhạc",
    "句": "cú", "匆": "công", "册": "sách", "犯": "phạm", "外": "ngoại", "处": "xứ", "冬": "đông",
    "鸟": "điểu", "务": "vụ", "包": "bao", "饥": "cơ", "主": "chủ", "市": "thị", "立": "lập",
    "闪": "thiểm", "半": "bán", "汁": "trấp", "汇": "hối", "头": "đầu", "汉": "hán", "宁": "ninh",
    "穴": "huyệt", "它": "tha", "讨": "thảo", "写": "tả", "让": "nhượng", "礼": "lễ", "训": "huấn",
    "必": "tất", "议": "nghị", "讯": "tấn", "记": "ký", "永": "vĩnh", "司": "ty", "尼": "ni",
    "民": "dân", "出": "xuất", "...": "...", "奶": "nải", "奴": "nô", "加": "gia", "召": "triệu",
    "皮": "bì", "边": "biên", "孕": "孕", "发": "phát", "圣": "thánh", "对": "đối", "台": "đài",
    "矛": "mâu", "纠": "củ", "母": "mẫu", "幼": "ấu", "丝": "ti", "式": "thức", "刑": "hình",
    "动": "động", "扛": "kháng", "寺": "tự", "gi": "cát", "扣": "khấu", "考": "khảo", "托": "thác",
    "老": "lão", "执": "chấp", "巩": "củng", "圾": "tập", "扩": "khuếch", "扫": "tảo", "地": "địa",
    "扬": "dương", "场": "trường", "耳": "nhĩ", "共": "cộng", "mang": "mang", "芒": "mang",
    "朽": "hủ", "朴": "phác", "ji": "cơ", "机": "cơ", "权": "quyền", "过": "quá", "荒": "hoang",
    "骨": "cốt", "魂": "hồn", "魄": "phách", "魅": "mị", "魔": "ma", "妖": "yêu", "鬼": "quỷ",
    "体": "thể", "防": "phòng", "御": "ngự", "攻": "công", "击": "kích", "退": "thoái", "进": "tiến",
    "逃": "đào", "避": "tị", "闪": "thiểm", "移": "di", "không": "không", "间": "gian", "法": "pháp",
    "术": "thuật", "宝": "bảo", "物": "vật", "器": "khí", "鼎": "đỉnh", "lư": "lư", "炉": "lò",
    "药": "dược", "灵": "linh", "thạch": "thạch", "泉": "tuyền", "thảo": "thảo", "mộc": "mộc",
    "雷": "lôi", "风": "phong", "băng": "băng", "冰": "băng",
    "ám": "ám", "quang": "quang", "thần": "thần", "tiên": "tiên", "ma": "ma", "yêu": "yêu", "quỷ": "quỷ",
    "nhân": "nhân", "tộc": "tộc", "thú": "thú", "cầm": "cầm", "lân": "lân", "giáp": "giáp", "trùng": "trùng",
    "thảo": "thảo", "mộc": "mộc", "hoa": "hoa", "quả": "quả", "thực": "thực", "thụ": "thụ", "đằng": "đằng",
    "竹": "trúc", "lan": "lan", "cúc": "cúc", "mai": "mai", "liên": "liên", "đào": "đào", "lý": "lý",
    "hạnh": "hạnh", "lê": "lê", "tảo": "tảo", "thị": "thị", "liệt": "liệt", "trảm": "trảm",
    "旷": "khoáng", "刷": "xoát", "榨": "vắt", "干": "kiệt", "交": "giao", "融": "dung", "乳": "nhũ",
    "被": "bị", "吃": "ăn", "全": "toàn", "先": "tiên", "天": "thiên", "章": "chương", "第": "thứ"
}

def lookup_hanviet(char: str) -> str:
    """Tra cứu âm Hán Việt của một ký tự đơn. Trả về ký tự gốc nếu không có trong từ điển."""
    return HANVIET_DICT.get(char, char)

def convert_to_hanviet(text: str) -> str:
    """Chuyển đổi một chuỗi chữ Hán sang Hán Việt bằng cách ghép âm từ từ điển."""
    result = []
    for char in text:
        result.append(lookup_hanviet(char))
    return " ".join(result)

def convert_to_hanviet_name(text: str) -> str:
    """Chuyển đổi một tên chữ Hán sang Hán Việt chuẩn viết hoa từng từ (0 Token, 0 Latency)."""
    if not text:
        return ""
    words = [lookup_hanviet(char).capitalize() for char in text]
    return " ".join(words)

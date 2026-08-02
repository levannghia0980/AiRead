import json

# Context Profiles cho Luồng Biên tập Ngữ cảnh (CONTEXTT)
# Đầu vào là Bản dịch Google, nhiệm vụ là biên tập và làm mượt mà.

URBAN_PROFILE = {
    "description": (
        "- Bối cảnh: Hiện đại / Đô thị.\n"
        "- Lời dẫn ngôi thứ ba (narrator): Sửa các đại từ của Google Dịch. TUYỆT ĐỐI KHÔNG dùng 'cậu' hoặc 'anh' khi kể chuyện, hãy sửa thành 'hắn', 'y', 'gã' cho đúng giọng văn tiểu thuyết.\n"
        "- Lời thoại & Suy nghĩ: Cho phép dùng các đại từ hiện đại ('tôi', 'bạn', 'anh', 'em', 'cậu', 'cô') mượt mà, hợp mối quan hệ."
    )
}

XIANXIA_PROFILE = {
    "description": (
        "- Bối cảnh: Tu tiên, huyền huyễn, cổ phong.\n"
        "- Đại từ cấm: TUYỆT ĐỐI KHÔNG để sót các đại từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô') trong cả lời dẫn và lời thoại.\n"
        "- Lời kể chuyện ngôi thứ ba: Sửa thành 'hắn', 'nàng', 'y', 'gã', 'ông', 'lão', 'tiểu tử'... (ví dụ: dùng 'hắn' hoặc 'y' cho Từ Tiểu Thụ, cấm để 'cậu').\n"
        "- Đối thoại nhân vật: Khôi phục xưng hô chuẩn cổ phong kiếm hiệp: 'ta - ngươi', 'ta - hắn/y', 'đệ tử - sư tôn/sư phụ', 'sư huynh - sư đệ', 'tiền bối - vãn bối', 'huynh - đệ', 'tỷ - muội'."
    )
}

WUXIA_PROFILE = {
    "description": (
        "- Bối cảnh: Kiếm hiệp, võ lâm, giang hồ truyền thống.\n"
        "- Đại từ cấm: TUYỆT ĐỐI KHÔNG để sót các đại từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô') trong toàn bộ văn bản.\n"
        "- Lời kể chuyện ngôi thứ ba: Sửa thành 'hắn', 'nàng', 'y', 'gã', 'ông'...\n"
        "- Đối thoại nhân vật: Khôi phục xưng hô giang hồ: 'ta - ngươi', 'ta - y/hắn', 'huynh - đệ', 'tỷ - muội', 'chưởng môn', 'các hạ', 'tiền bối - vãn bối'."
    )
}

COMMON_RULES = (
    "1. BIÊN TẬP XƯNG HÔ & PHỤC HỒI CHỦ NGỮ: Khôi phục các chủ ngữ ẩn bị mất từ Google Dịch. Thay đổi đại từ xưng hô generic (như bạn, tôi, anh ấy, cô ấy) thành xưng hô chuẩn của ngữ cảnh.\n"
    "2. DANH XƯNG & BỐI PHẬN: Luôn dùng cấu trúc [Tên riêng] + [Bối phận/Danh xưng] (Tên trước, chức danh sau). Sửa lại cấu trúc ngược của Google Dịch thành: 'Tang lão' (KHÔNG dùng 'Lão Tang'), 'Từ huynh' (KHÔNG dùng 'Huynh Từ'), 'Mã sư đệ' (KHÔNG dùng 'Sư đệ Mã'), 'Sân lão' (KHÔNG dùng 'Lão Sân'), 'Tiêu trưởng lão', 'Triệu sư tỷ', v.v.\n"
    "3. GIỮ NGUYÊN Ý NGHĨA & THỰC THỂ: Giữ nguyên 100% các mã bảo vệ §PREFIX_XXXX§. Không thêm thắt tình tiết ngoài văn bản gốc. Giữ đúng các thực thể đã tra từ điển.\n"
    "4. TỐI ƯU HÁN VIỆT: Chỉ giữ từ Hán-Việt cho thực thể đặc trưng. Các hành động sinh hoạt, mô tả thường ngày phải biên tập sang tiếng Việt tự nhiên và thuần Việt (ví dụ: sửa 'thu thây' thành 'người thu xác')."
)

CONTEXT_PROFILES = {
    "urban": URBAN_PROFILE,
    "xianxia": XIANXIA_PROFILE,
    "wuxia": WUXIA_PROFILE
}

def normalize_profile_key(profile_key: str) -> str:
    if not profile_key:
        return "xianxia"
    
    pk = profile_key.lower().strip()
    
    # Kiểm tra substring cho võ hiệp / wuxia
    if any(k in pk for k in ["wuxia", "võ hiệp", "kiếm hiệp", "giang hồ"]):
        return "wuxia"
        
    # Kiểm tra substring cho đô thị / urban / hiện đại
    if any(k in pk for k in ["urban", "đô thị", "hiện đại", "ngôn tình hiện đại", "hào môn", "giải trí", "vườn trường", "modern_urban"]):
        return "urban"
        
    # Mặc định tất cả các thể loại huyền huyễn, tu tiên, lịch sử, hệ thống... về xianxia để xưng hô chuẩn cổ phong
    return "xianxia"

def get_context_editor_prompt(profile_key: str) -> str:
    """Trả về chuỗi JSON và Common Rules để nhúng vào Prompt cho luồng Biên tập"""
    normalized_key = normalize_profile_key(profile_key)
    profile = CONTEXT_PROFILES.get(normalized_key)
    if not profile:
        return ""
        
    return f"=== CẤU HÌNH NGỮ CẢNH TRUYỆN ({normalized_key.upper()}) ===\n{profile['description']}\n\n=== QUY TẮC BIÊN TẬP QUAN TRỌNG ===\n{COMMON_RULES}"

import json

# Context Profiles cho LLM
# Các thông tin JSON này sẽ được parse và gửi vào prompt để hướng dẫn LLM xưng hô.

URBAN_PROFILE = {
    "description": (
        "- Bối cảnh: Hiện đại / Đô thị.\n"
        "- Lời dẫn ngôi thứ ba (narrator): TUYỆT ĐỐI KHÔNG dùng 'cậu' hoặc 'anh' để gọi nam chính. Hãy dùng 'hắn', 'y', 'gã' để chuẩn văn phong tiểu thuyết.\n"
        "- Lời thoại & Suy nghĩ: Sử dụng đại từ hiện đại tự nhiên ('tôi', 'bạn', 'anh', 'em', 'cậu', 'cô') tùy theo mối quan hệ, tuổi tác và cảm xúc nhân vật."
    )
}

XIANXIA_PROFILE = {
    "description": (
        "- Bối cảnh: Tu tiên, huyền huyễn, cổ phong.\n"
        "- Ngôi thứ ba (narrator) & Lời thoại: TUYỆT ĐỐI KHÔNG dùng từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô').\n"
        "- Xưng hô dẫn chuyện: Dùng 'hắn', 'nàng', 'y', 'gã', 'ông', 'lão', 'tiểu tử'... (ví dụ: dùng 'hắn' hoặc 'y' cho Từ Tiểu Thụ, cấm dùng 'cậu').\n"
        "- Xưng hô đối thoại: Sử dụng hệ từ cổ phong kiếm hiệp chuẩn xác: 'ta - ngươi', 'ta - hắn/y', 'đệ tử - sư tôn/sư phụ', 'sư huynh - sư đệ', 'tiền bối - vãn bối', 'huynh - đệ', 'tỷ - muội'."
    )
}

WUXIA_PROFILE = {
    "description": (
        "- Bối cảnh: Kiếm hiệp, võ lâm, giang hồ truyền thống.\n"
        "- Ngôi thứ ba (narrator) & Lời thoại: TUYỆT ĐỐI KHÔNG dùng từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô').\n"
        "- Xưng hô dẫn chuyện: Dùng 'hắn', 'nàng', 'y', 'gã', 'lão', 'ông'... để chỉ nhân vật.\n"
        "- Xưng hô đối thoại: Tuân thủ quy tắc giang hồ kiếm hiệp: 'ta - ngươi', 'ta - y/hắn', 'huynh - đệ', 'tỷ - muội', 'chưởng môn', 'các hạ', 'tiền bối - vãn bối'."
    )
}

COMMON_RULES = (
    "1. VỀ DANH XƯNG & BỐI PHẬN: Luôn dịch theo cấu trúc [Tên riêng] + [Bối phận/Danh xưng] (Tên trước, chức danh sau). Ví dụ: 'Tang lão' (KHÔNG dùng 'Lão Tang'), 'Từ huynh' (KHÔNG dùng 'Huynh Từ'), 'Mã sư đệ' (KHÔNG dùng 'Sư đệ Mã'), 'Sân lão' (KHÔNG dùng 'Lão Sân'), 'Tiêu trưởng lão', 'Triệu sư tỷ', v.v.\n"
    "2. KHÔNG DỊCH MÁY: Đọc hiểu ngữ cảnh trước sau để dịch mượt mà, tự nhiên và nhất quán trong toàn bộ chương.\n"
    "3. HẠN CHẾ HÁN-VIỆT THÔNG THƯỜNG: Chỉ dùng từ Hán-Việt cho thực thể đặc trưng (Tên riêng, địa danh, tông môn, chiêu thức, bảo vật). Toàn bộ từ miêu tả hành động sinh hoạt, mô tả thường ngày phải dịch sang tiếng Việt tự nhiên, thuần Việt (ví dụ: dùng 'người thu xác' thay vì 'thu thây').\n"
    "4. GIỮ NGUYÊN NỘI DUNG: Không tự ý thêm bớt tình tiết, hội thoại ngoài bản gốc."
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

def get_context_profile_prompt(profile_key: str) -> str:
    """Trả về chuỗi JSON và Common Rules để nhúng vào Prompt"""
    normalized_key = normalize_profile_key(profile_key)
    profile = CONTEXT_PROFILES.get(normalized_key)
    if not profile:
        return ""
        
    return f"=== CẤU HÌNH NGỮ CẢNH TRUYỆN ({normalized_key.upper()}) ===\n{profile['description']}\n\n=== QUY TẮC DỊCH THUẬT QUAN TRỌNG ===\n{COMMON_RULES}"

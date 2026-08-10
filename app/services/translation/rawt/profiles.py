import json

# Context Profiles cho LLM
# Các thông tin JSON này sẽ được parse và gửi vào prompt để hướng dẫn LLM xưng hô.

URBAN_PROFILE = {
    "description": (
        "Bối cảnh: Hiện đại / Đô thị.\n"
        "Dẫn chuyện ngôi 3: Dùng 'hắn/y/gã', CẤM 'cậu/anh'.\n"
        "Thoại: Đại từ hiện đại tự nhiên theo quan hệ/tuổi/cảm xúc."
    )
}

XIANXIA_PROFILE = {
    "description": (
        "Bối cảnh: Tu tiên / Huyền huyễn / Cổ phong.\n"
        "Dẫn chuyện ngôi 3 & Thoại: CẤM từ hiện đại (cậu/tôi/bạn/anh/em/cô).\n"
        "Dẫn chuyện: Dùng 'hắn/y/gã/nàng/lão'. Xen kẽ nhịp nhàng, tránh lặp.\n"
        "Đối thoại: Hệ cổ phong: ta-ngươi, sư phụ-đệ tử, huynh-đệ, tỷ-muội, tiền bối-vãn bối."
    )
}

WUXIA_PROFILE = {
    "description": (
        "Bối cảnh: Kiếm hiệp / Võ lâm / Giang hồ.\n"
        "Dẫn chuyện ngôi 3 & Thoại: CẤM từ hiện đại (cậu/tôi/bạn/anh/em/cô).\n"
        "Dẫn chuyện: Dùng 'hắn/y/gã/nàng/lão/ông'.\n"
        "Đối thoại: Quy tắc giang hồ: ta-ngươi, huynh-đệ, tỷ-muội, chưởng môn, các hạ."
    )
}

COMMON_RULES = (
    "1. TÊN THỰC THỂ:\n"
    "   - Có trong Từ điển → dùng ĐÚNG 100%, CẤM tự ý đổi.\n"
    "   - Chưa có → dịch âm Hán-Việt chuẩn cổ phong. CẤM dịch nghĩa đen bình dân.\n"
    "   - Trật tự: [Họ/Tên] + [Danh xưng] (Kiều trưởng lão, Tang lão, Từ huynh). CẤM đảo ngược.\n"
    "2. VĂN PHONG:\n"
    "   - Ngữ pháp thuần Việt mượt mà, CẤM giữ cấu trúc Hán-Việt thô (đem..., đối với... mà nói, dưới một cái...).\n"
    "   - Thêm sắc thái hóm hỉnh nhẹ ở suy nghĩ/độc thoại nội tâm nhân vật khi phù hợp, CẤM thay đổi ý gốc.\n"
    "3. THUẬT NGỮ & SỐ ĐẾM:\n"
    "   - Cảnh giới/Tầng: BẮT BUỘC số Hán-Việt (Nhất→Thập). CẤM 'thứ ba', 'thứ 4'.\n"
    "   - Giữ nguyên thuật ngữ tu tiên (Khí Hải, Thần Thức, Pháp Bảo, Công Pháp...).\n"
    "4. XƯNG HÔ: Nhất quán theo bối phận (Sư phụ-Đệ tử, Sư huynh-Sư đệ). CẤM đảo ngược.\n"
    "5. GIỮ NGUYÊN nội dung, không thêm bớt tình tiết."
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
        
    return f"[BỐI CẢNH]\n{profile['description']}\n\n[QUY TẮC]\n{COMMON_RULES}"

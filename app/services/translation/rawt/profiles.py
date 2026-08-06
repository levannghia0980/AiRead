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
    "1. NGỮ PHÁP & VĂN PHONG THUẦN VIỆT — XUẤT AUDIOBOOK (TUYỆT ĐỐI BẮT BUỘC):\n"
    "   - Dịch thoát ý Hán-Việt thô cứng ở CẤU TRÚC CÂU. Diễn đạt bằng ngữ pháp và văn phong tiếng Việt tự nhiên, mượt mà, giàu nhịp điệu.\n"
    "   - TUYỆT ĐỐI KHÔNG dịch bám sát cấu trúc Hán-Việt gượng ép (như 'đem...', 'đối với... mà nói', 'trong lòng có chút...', 'dưới một cái...', 'sau khi...'). Hãy chuyển đổi thành câu văn thuần Việt cuốn hút ('lập tức', 'liền', 'chợt', 'vốn dĩ', 'đối với...').\n"
    "2. PHÂN TÍCH NGỮ CẢNH CẢNH TRUYỆN & QUAN HỆ NHÂN VẬT (YÊU CẦU NGỮ CẢNH BẮT BUỘC):\n"
    "   - BẮT BUỘC cảm nhận BẦU KHÔNG KHÍ của từng phân cảnh (giao tranh dồn dập, thương lượng ngầm, hài hước trêu đùa, hay độc thoại nội tâm u uất) để điều chỉnh nhịp câu và sắc thái từ ngữ (Tone & Mood) phù hợp.\n"
    "   - BẮT BUỘC xác định NGỮ CẢNH MỐI QUAN HỆ & THÁI ĐỘ giữa các nhân vật (Sư đồ kính cẩn, Huynh đệ tri kỷ, Kẻ thù đối đầu, Bề trên trêu chọc đệ tử). Giọng điệu và xưng hô phải linh hoạt theo thái độ cảm xúc (giận dữ, khiêu khích, trêu đùa hay tôn kính).\n"
    "3. NHẤT QUÁN XƯNG HÔ & THÂN TỘC TƯƠNG ỨNG:\n"
    "   - Phải xác định đúng AI ĐANG NÓI VỚI AI trong từng đoạn hội thoại.\n"
    "   - Khi 2 nhân vật giao tiếp có quan hệ thân tộc hoặc bối phận (như Mẹ - Con, Cha - Con, Sư phụ - Đệ tử, Ông - Cháu, Huynh - Đệ, Sư huynh - Sư đệ, Sư tỷ - Sư muội, Chủ - Tớ), xưng hô phải TUYỆT ĐỐI NHẤT QUÁN THEO CẶP TƯƠNG ỨNG từ đầu đến cuối chương.\n"
    "   - CẤM ĐẢO NGƯỢC CẶP XƯNG HÔ: Ví dụ nếu A là Mẹ và B là Con: A phải xưng 'Mẹ' (hoặc 'Nương/Mẫu thân') gọi B là 'Con' (hoặc 'Nhi tử'); B phải gọi A là 'Mẹ/Mẫu thân' xưng 'Con'. KHÔNG ĐƯỢC đảo ngược ở các câu tiếp theo thành B gọi A là 'Con' hay A gọi B là 'Mẹ', cũng KHÔNG ĐƯỢC tự ý nhảy sang 'ta - ngươi'.\n"
    "4. DANH XƯNG, BỐI PHẬN & TRẬT TỰ TÊN (TUYỆT ĐỐI BẮT BUỘC ĐỒNG BỘ NGUYÊN BẢN TỪ ĐIỂN):\n"
    "   - Khi nhân vật gọi nhau hoặc dẫn chuyện bằng danh xưng/chức danh (như 乔长老, 桑老, 徐兄, 肖七修, 穆师姐...):\n"
    "   - BẮT BUỘC dịch theo đúng trật tự Hán-Việt cổ phong chuẩn sắc thái truyện Trung: [Tên/Họ] + [Danh xưng/Chức danh/Lão/Huynh/Tỷ/Đệ/Muội/Trưởng lão].\n"
    "   - VÍ DỤ CỤ THỂ BẮT BUỘC: Dịch là 'Kiều trưởng lão' (TUYỆT ĐỐI KHÔNG đảo thành 'Trưởng lão Kiều'), 'Tang lão' (KHÔNG đảo thành 'Lão Tang'), 'Từ huynh' (KHÔNG đảo thành 'Huynh Từ'), 'Tiêu trưởng lão', 'Mục sư tỷ'.\n"
    "   - Nếu một tên/danh xưng ĐÃ CÓ TRONG TỪ ĐIỂN THỰC THỂ bên dưới (ví dụ 乔长老 = 'Kiều trưởng lão'), bạn BẮT BUỘC PHẢI DỊCH Y NGUYÊN là 'Kiều trưởng lão' trong toàn bộ văn bản dịch, NGHIÊM CẤM TỰ Ý ĐẢO THÀNH 'Trưởng lão Kiều'.\n"
    "5. QUY TẮC BẢO TỒN THUẬT NGỮ & SỐ ĐẾM HÁN-VIỆT CHUẨN (TUYỆT ĐỐI BẮT BUỘC):\n"
    "   - SỐ ĐẾM CẢNH GIỚI TU LUYỆN: TUYỆT ĐỐI KHÔNG dùng số thứ tự thuần Việt / bình dân ('thứ ba', 'thứ 4', 'thứ tư', 'tầng thứ 4', 'tầng thứ ba'). BẮT BUỘC DÙNG SỐ HÁN-VIỆT (Nhất, Nhị, Tam, Tứ, Ngũ, Lục, Thất, Bát, Cửu, Thập...):\n"
    "     + 'Cảnh giới thứ ba' / 'Cảnh giới thứ 3' → BẮT BUỘC DỊCH THÀNH: 'Tam Cảnh' hoặc 'Tam Trọng'.\n"
    "     + 'Luyện Linh tầng thứ 4' / 'Luyện Linh tầng thứ tư' → BẮT BUỘC DỊCH THÀNH: 'Luyện Linh Tứ Cảnh' hoặc 'Luyện Linh Tứ Trọng' (hoặc 'Luyện Linh Tầng Tứ').\n"
    "     + 'Luyện Linh cảnh mười tầng' / 'Luyện Linh mười tầng' → BẮT BUỘC DỊCH THÀNH: 'Luyện Linh Cảnh Thập Trọng' hoặc 'Luyện Linh Thập Cảnh'.\n"
    "     + 'Tầng thứ năm' → 'Ngũ Trọng' / 'Ngũ Cảnh', 'Tầng thứ tám' → 'Bát Cảnh' / 'Bát Trọng'.\n"
    "   - NGUYÊN TẮC PHÂN BIỆT VÀNG: Cấu trúc câu ngữ pháp phải MƯỢT MÀ THUẦN VIỆT, nhưng THUẬT NGỮ HÁN-VIỆT CHUYÊN NGÀNH & SỐ ĐẾM CẢNH GIỚI trong thế giới Tu Tiên / Huyền Huyễn / Kiếm Hiệp (như Cảnh giới tu luyện, Càn Khôn, Khí Hải, Thần Thức, Pháp Bảo, Linh Dược, Thần Thông, Công Pháp, Tâm Pháp, Thân Pháp, Khí Tràng, Linh Trận, Trận Pháp, Sát Khí, Ma Khí, Yêu Thú, Thần Thú, Tùy Thân Không Gian, Bát Cảnh, Linh Lực...) BẮT BUỘC PHẢI BẢO TỒN NGUYÊN BẢN HÁN-VIỆT CHUẨN TRANG TRỌNG.\n"
    "   - NGHIÊM CẤM tự ý dịch các thuật ngữ Hán-Việt quen thuộc này thành từ thuần Việt nông thôn / bình dân / nghĩa đen đời thường làm mất đi cái hay, khí thế và chất truyện võ hiệp/tiên hiệp đặc trưng!\n"
    "     + 'Khí hải' (KHÔNG dịch 'Biển khí'), 'Thần thức' (KHÔNG dịch 'Nhận thức thần kỳ').\n"
    "     + 'Công pháp' (KHÔNG dịch 'Cách làm'), 'Pháp bảo' (KHÔNG dịch 'Món đồ phép / Bảo vật phép thuật').\n"
    "     + 灌注 / 灌透 / 贯透: Dịch là 'quán chú', 'quán thấu', 'rót vào', 'truyền vào' (TUYỆT ĐỐI KHÔNG dịch 'tưới tiêu').\n"
    "     + 修炼: Dịch là 'tu luyện' (KHÔNG dịch 'tập thể dục').\n"
    "     + 渡劫 / 劫难: Dịch là 'độ kiếp' / 'kiếp nạn' (KHÔNG dịch 'vượt thảm họa / vượt thử thách').\n"
    "     + 破境 / 突破: Dịch là 'phá cảnh' / 'đột phá'.\n"
    "   - Động từ, tính từ miêu tả xuất chiêu, vung kiếm, vận công, phá cảnh phải giữ khí thế dũng mãnh, trang trọng của văn phong võ hiệp/tiên hiệp.\n"
    "6. GIỮ NGUYÊN NỘI DUNG: Không tự ý thêm bớt tình tiết, hội thoại ngoài bản gốc."
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

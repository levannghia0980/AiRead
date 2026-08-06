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
    "1. NGỮ PHÁP & VĂN PHONG THUẦN VIỆT — XUẤT AUDIOBOOK ÊM TAI, TRUYỀN CẢM (TUYỆT ĐỐI BẮT BUỘC):\n"
    "   - Biên tập mượt mà, biến câu từ dịch thô cứng thành ngữ pháp và văn phong tiếng Việt tự nhiên, truyền cảm, giàu hình tượng.\n"
    "   - TUYỆT ĐỐI KHÔNG giữ các câu trúc dịch thô bị cứng (như 'đem...', 'đối với... mà nói', 'trong lòng có chút...', 'dưới một cái...', 'sau khi...'). Chuyển hẳn sang cách diễn đạt thuần Việt cuốn hút ('lập tức', 'liền', 'chợt', 'vốn dĩ', 'đối với...').\n"
    "   - Ưu tiên các từ thuần Việt gợi hình, gợi cảm trong các đoạn tả cảnh, cử chỉ, tâm trạng nhân vật để khi phát Audio TTS nghe vô cùng truyền cảm và mượt mà.\n"
    "2. PHÂN TÍCH NGỮ CẢNH CẢNH TRUYỆN & QUAN HỆ NHÂN VẬT (YÊU CẦU NGỮ CẢNH BẮT BUỘC):\n"
    "   - BẮT BUỘC cảm nhận BẦU KHÔNG KHÍ của từng phân cảnh (giao tranh dồn dập, thương lượng ngầm, hài hước trêu đùa, hay độc thoại nội tâm u uất) để biên tập nhịp câu và sắc thái từ ngữ (Tone & Mood) phù hợp.\n"
    "   - BẮT BUỘC xác định NGỮ CẢNH MỐI QUAN HỆ & THÁI ĐỘ giữa các nhân vật (Sư đồ kính cẩn, Huynh đệ tri kỷ, Kẻ thù đối đầu, Bề trên trêu chọc đệ tử). Giọng điệu và xưng hô phải linh hoạt theo thái độ cảm xúc (giận dữ, khiêu khích, trêu đùa hay tôn kính).\n"
    "3. NHẤT QUÁN XƯNG HÔ, THÂN TỘC & BỐI PHẬN (TUYỆT ĐỐI BẮT BUỘC):\n"
    "   - Phải tham chiếu kĩ danh sách Thực thể nhân vật (bao gồm Giới tính & Vai trò/Bối phận) để xác định đúng AI ĐANG NÓI VỚI AI trong từng đoạn hội thoại.\n"
    "   - Khi 2 nhân vật giao tiếp có quan hệ thân tộc hoặc bối phận (như Mẹ - Con, Cha - Con, Sư phụ - Đệ tử, Ông - Cháu, Huynh - Đệ, Sư huynh - Sư đệ, Sư tỷ - Sư muội, Chủ - Tớ), xưng hô phải TUYỆT ĐỐI NHẤT QUÁN THEO CẶP TƯƠNG ỨNG từ đầu đến cuối chương.\n"
    "   - CẤM ĐẢO NGƯỢC CẶP XƯNG HÔ: Ví dụ nếu A là Mẹ và B là Con: A phải xưng 'Mẹ' (hoặc 'Nương/Mẫu thân') gọi B là 'Con' (hoặc 'Nhi tử'); B phải gọi A là 'Mẹ/Mẫu thân' xưng 'Con'. KHÔNG ĐƯỢC đảo ngược ở các câu tiếp theo thành B gọi A là 'Con' hay A gọi B là 'Mẹ'.\n"
    "   - Nếu bản dịch Google bị dịch ngô nghê hoặc bị lộn xưng hô giữa các câu, BẠN PHẢI TỰ ĐỘNG SỬA LẠI TOÀN BỘ CHO NHẤT QUÁN VỚI CẶP XƯNG HÔ ĐÚNG BAN ĐẦU.\n"
    "4. QUY TẮC ĐỘC THOẠI NỘI TÂM & SUY NGHĨ NHÂN VẬT (BẮT BUỘC):\n"
    "   - Khi một nhân vật tự nhủ trong đầu (độc thoại nội tâm, lời nghĩ suy), BẠN BẮT BUỘC PHẢI CĂN CỨ VÀO VAI TRÒ & BỐI PHẬN của nhân vật đó để chỉnh sửa đại từ xưng hô tự xưng.\n"
    "   - TUYỆT ĐỐI KHÔNG để lộn xưng hô do lỗi Google Dịch (ví dụ: người Mẹ tự nghĩ trong đầu nhưng Google Dịch nhầm thành 'Con định bị...' $\rightarrow$ BẮT BUỘC PHẢI SỬA THÀNH 'Mẹ định bị...' hoặc 'Cô định bị...' hoặc 'Mình định bị...').\n"
    "   - Nhận diện lời dẫn suy nghĩ: Nếu trước đó có các cụm 'trong lòng cô...', 'nàng nghĩ...', 'y thầm nghĩ...', đại từ tự xưng trong câu thoại nội tâm liền sau phải đổi về đúng ngôi của nhân vật (Mẹ / Cô / Ta / Mình).\n"
    "5. SỬA RÁC DỊCH THÔ CỦA GOOGLE TRANSLATE:\n"
    "   - Quét và sửa triệt để các từ tiếng nước ngoài do Google Dịch đoán nhầm ngôn ngữ đầu câu (ví dụ: sửa 'Setelah' thành 'Sau khi' hoặc 'Nghe xong').\n"
    "   - Sửa các cụm từ dịch ngô nghê như 'dưới một cái' $\rightarrow$ 'lập tức / tức thì', 'có chút' $\rightarrow$ 'hơi / hơi chút'.\n"
    "6. BIÊN TẬP XƯNG HÔ & PHỤC HỒI CHỦ NGỮ: Khôi phục các chủ ngữ ẩn bị mất từ Google Dịch. Thay đổi đại từ xưng hô generic (như bạn, tôi, anh ấy, cô ấy) thành xưng hô chuẩn của ngữ cảnh.\n"
    "7. DANH XƯNG & BỐI PHẬN: Luôn dùng cấu trúc [Tên riêng] + [Bối phận/Danh xưng] (Tên trước, chức danh sau). Sửa lại cấu trúc ngược của Google Dịch thành: 'Tang lão', 'Từ huynh', 'Mã sư đệ', 'Tiêu trưởng lão', 'Triệu sư tỷ', v.v.\n"
    "8. GIỮ NGUYÊN Ý NGHĨA & THỰC THỂ: Giữ nguyên 100% các mã bảo vệ §PREFIX_XXXX§. Không thêm thắt tình tiết ngoài văn bản gốc. Giữ đúng các thực thể đã tra từ điển.\n"
    "9. BẢO TỒN NGUYÊN BẢN THUẬT NGỮ & SỐ ĐẾM HÁN-VIỆT CHUẨN (TUYỆT ĐỐI BẮT BUỘC):\n"
    "   - SỐ ĐẾM CẢNH GIỚI TU LUYỆN: BẮT BUỘC DÙNG SỐ HÁN-VIỆT (Nhất, Nhị, Tam, Tứ, Ngũ, Lục, Thất, Bát, Cửu, Thập...). Sửa các lỗi dịch thô dùng số thứ tự thuần Việt ('thứ ba', 'thứ 4', 'tầng thứ 4', 'tầng thứ ba') thành 'Tam Cảnh', 'Tứ Cảnh', 'Luyện Linh Tứ Cảnh', 'Luyện Linh Thập Cảnh'.\n"
    "   - Giữ nguyên 100% các THUẬT NGỮ HÁN-VIỆT CHUẨN đã quen thuộc trong giới Tiên Hiệp / Võ Hiệp (như Cảnh giới tu luyện, Tiên Thiên, Tông Sư, Khí Hải, Thần Thức, Pháp Bảo, Linh Dược, Thần Thông, Công Pháp, Tâm Pháp, Thân Pháp, Khí Tràng, Linh Trận, Trận Pháp, Sát Khí, Ma Khí, Yêu Thú, Tùy Thân Không Gian...).\n"
    "   - TUYỆT ĐỐI KHÔNG biên tập thành tiếng Việt thuần gốc nông thôn / bình dân / nghĩa đen (như 'Cõi rèn luyện tinh thần 3', 'Biển khí', 'Món đồ phép thuật', 'Vượt thử thách', 'Tập thể dục').\n"
    "   - Sửa triệt để các từ dịch sai nghĩa đen đời thường của Google Translate trong ngữ cảnh tu luyện/chiến đấu:\n"
    "     + 灌注 / 灌透 / 贯透: Biên tập lại thành 'quán chú', 'quán thấu', 'rót vào', 'truyền vào' (TUYỆT ĐỐI KHÔNG để 'tưới tiêu').\n"
    "     + 修炼: Biên tập lại thành 'tu luyện' (KHÔNG để 'tập thể dục').\n"
    "     + 渡劫 / 劫难: Biên tập lại thành 'độ kiếp' / 'kiếp nạn' (KHÔNG để 'vượt thảm họa / vượt thử thách').\n"
    "     + 破境 / 突破: Biên tập lại thành 'phá cảnh' / 'đột phá'.\n"
    "   - Động từ, tính từ miêu tả xuất chiêu, vung kiếm, vận công phải thể hiện đúng khí thế dũng mãnh, trang trọng của văn phong võ hiệp/tiên hiệp."
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

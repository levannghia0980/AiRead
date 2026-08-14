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
    "1. BẢO TỒN TUYỆT ĐỐI DANH TỪ BẢN SẮC TRUYỆN TRUNG & QUY TẮC DỊCH TÊN THỰC THỂ:\n"
    "   - ĐỐI VỚI CÁC THỰC THỂ ĐÃ CÓ TRONG TỪ ĐIỂN THỰC THỂ (DICTIONARY MAPPING): Bạn BẮT BUỘC phải dùng ĐÚNG 100% từ đã chuẩn hóa trong từ điển. TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ Ý ĐỔI HOẶC SỬA BẤT KỲ TÊN/THỰC THỂ NÀO ĐÃ CÓ TRONG TỪ ĐIỂN.\n"
    "   - ĐỐI VỚI TÊN THỰC THỂ MỚI (Tên nhân vật, chiêu thức, địa danh, môn phái, bảo vật, cảnh giới...) CHƯA CÓ TRONG TỪ ĐIỂN: BẮT BUỘC biên tập/dịch theo âm HÁN-VIỆT CHUẨN CỔ PHONG TIÊN HIỆP/KIẾM HIỆP (Ví dụ: Từ Tiểu Thụ, Thiên Tang Linh Cung, Luyện Linh cảnh, Hô Hấp Chi Pháp, Phong Vân Tranh Bá, Hắc Sắc Chuyển Bàn...). TUYỆT ĐỐI KHÔNG DỊCH THÀNH TIẾNG VIỆT BÌNH DÂN / NÔNG THÔN / NGHĨA ĐEN ĐỜI THƯỜNG (CẤM biên tập 'Hô Hấp Chi Pháp' thành 'Phương pháp hít thở', CẤM biên tập 'Thiên Tang Linh Cung' thành 'Cung điện tâm linh Thiên Tang', CẤM biên tập 'Hắc Sắc Chuyển Bàn' thành 'Cái đĩa xoay màu đen').\n"
    "   - CẤU TRÚC DANH XƯNG CHUẨN TRUYỆN TRUNG: BẮT BUỘC giữ đúng trật tự [Tên/Họ] + [Danh xưng/Chức danh/Lão/Huynh/Tỷ/Sư đệ/Trưởng lão] (Ví dụ: Kiều trưởng lão, Tang lão, Từ huynh, Mã sư đệ, Tiêu trưởng lão). Sửa lại cấu trúc đảo ngược của Google Dịch thành đúng chuẩn Hán-Việt cổ phong (TUYỆT ĐỐI KHÔNG đảo ngược thành 'Trưởng lão Kiều' hay 'Lão Tang').\n"
    "2. NGỮ PHÁP & VĂN PHONG THUẦN VIỆT — THOÁT CÂU CỤT HÁN-VIỆT:\n"
    "   - Biên tập thoát ý Hán-Việt thô cứng ở cấu trúc câu. Diễn đạt bằng ngữ pháp tiếng Việt thuần thục, mượt mà, câu văn gãy gọn tự nhiên.\n"
    "   - KHÔNG GIỮ CÂU CỤT NGỦN THEO VĂN TRUNG: Cấm giữ lại các câu trúc thô cụt từ Google Translate (ví dụ 'Xuyên không không đau' -> BẮT BUỘC biên tập thành câu diễn đạt tự nhiên 'Xuyên không mà lại không đau đớn chút nào ư?' hoặc 'Xuyên không mà lại chẳng thấy đau đớn tí nào sao?').\n"
    "   - Sửa triệt để các rác dịch thô của Google Translate (như 'đem...', 'đối với... mà nói', 'trong lòng có chút...', 'dưới một cái...', 'sau khi...').\n"
    "3. SẮC THÁI HÀI HƯỚC, THỰC TẾ & KHẨU NGỮ MIỀN BẮC NHẸ NHÀNG:\n"
    "   - Thêm chút sắc thái sinh động, thực tế, hóm hỉnh nhẹ nhàng với chất khẩu ngữ miền Bắc (ví dụ: 'nghía qua', 'có gu', 'bóp dại', 'đi vào lòng đất', 'chán chả buồn nói', 'lộn ruột lộn gan'...) ở những đoạn phù hợp (đặc biệt là suy nghĩ nhân vật, độc thoại nội tâm, đối thoại trêu chọc).\n"
    "   - TUYỆT ĐỐI KHÔNG LÀM THAY ĐỔI CÂU TỪ, TÌNH TIẾT HAY Ý NGHĨA NGUYÊN TÁC CỦA CÂU VĂN.\n"
    "4. NHỊP ĐIỆU DẪN CHUYỆN NGÔI THỨ BA (XEN KẼ 'Y' VÀ 'HẮN'):\n"
    "   - Trong lời dẫn chuyện/kể chuyện (ngôi thứ ba): BẮT BUỘC xen kẽ nhịp nhàng, linh hoạt giữa 'y', 'hắn' và 'tên nhân vật' (như Từ Tiểu Thụ) để mạch văn không bị lặp từ thô cứng ('hắn... hắn... hắn...'), nhưng cũng không hoán đổi quá giật cục thô gượng.\n"
    "5. QUY TẮC BẢO TỒN THUẬT NGỮ & SỐ ĐẾM HÁN-VIỆT CHUẨN:\n"
    "   - SỐ ĐẾM CẢNH GIỚI TU LUYỆN: BẮT BUỘC DÙNG SỐ HÁN-VIỆT (Nhất, Nhị, Tam, Tứ, Ngũ, Lục, Thất, Bát, Cửu, Thập...). Sửa các lỗi dịch thô số thuần Việt ('thứ ba', 'thứ 4') thành 'Tam Cảnh', 'Luyện Linh Tứ Cảnh' / 'Tứ Trọng'.\n"
    "   - Giữ nguyên các thuật ngữ tu tiên Hán-Việt quen thuộc (Khí Hải, Thần Thức, Pháp Bảo, Công Pháp, Thần Thông, Độ Kiếp, Phá Cảnh, Quán Chú...).\n"
    "6. NHẤT QUÁN XƯNG HÔ, THÂN TỘC & ĐỘC THOẠI NỘI TÂM:\n"
    "   - Phải xác định đúng AI ĐANG NÓI VỚI AI. Xưng hô thân tộc/bối phận phải nhất quán theo cặp, CẤM đảo ngược.\n"
    "7. GIỮ NGUYÊN Ý NGHĨA & THỰC THỂ: Giữ nguyên 100% các mã bảo vệ §PREFIX_XXXX§ nếu có. Không thêm thắt tình tiết ngoài văn bản gốc.\n"
    "8. DỊCH CHUẨN XÁC TỪ XƯNG HÔ / BỐI PHẬN TIẾNG TRUNG ĐƯỢC BẢO VỆ:\n"
    "   - Bản dịch thô có các từ xưng hô/bối phận/thân tộc tiếng Trung được giữ nguyên gốc (ví dụ: 他, 她, 你, 我, 妈妈, 爸爸, 哥哥, 师兄, 师父, 道友, 陛下, 朕, 本王, 本座...).\n"
    "   - BẮT BUỘC dịch tất cả sang tiếng Việt CHUẨN XÁC dựa trên ngữ cảnh ai đang nói, nói với ai và mối quan hệ gì.\n"
    "   - '他'/'她' trong lời kể chuyện: dịch thành 'hắn'/'y'/'gã'/'nàng'/'cô ta' (tu tiên, kiếm hiệp) hoặc 'anh ta'/'cậu ta'/'cô ấy' (hiện đại).\n"
    "   - '你'/'您': dịch đúng bối phận xưng hô (ví dụ mẹ nói với con: '你' -> 'con'; con nói với mẹ: '您' -> 'mẹ/người'; sư tôn nói với đồ đệ: 'ngươi'; đồ đệ với sư tôn: 'sư tôn/sư phụ').\n"
    "   - '妈妈'/'母亲' = mẹ (TUYỆT ĐỐI KHÔNG dịch thành 'mẹ chồng'). '爸爸'/'父亲' = bố/cha. '儿子' = con trai. '女儿' = con gái.\n"
    "   - '师兄' = sư huynh, '师父' = sư phụ, '道友' = đạo hữu, '前辈' = tiền bối, '朕' = trẫm, '本王' = bản vương, '本座' = bản tọa.\n"
    "   - TUYỆT ĐỐI KHÔNG để sót bất kỳ ký tự tiếng Trung nào trong bản dịch cuối cùng. Phải trả về 100% tiếng Việt tự nhiên.\n"
    "9. TỰ ĐỘNG PHÁT HIỆN & SỬA TRIỆT ĐỂ MỌI TÊN TIẾNG ANH / PINYIN CÒN SÓT LẠI:\n"
    "   - Nếu trong bản dịch thô còn sót bất kỳ tên tiếng Anh (David, Peter...), Pinyin (Xiao Fan, Lin Chen, Chu Ning...), hoặc từ phiên âm ngoại lai nào chưa được làm sạch, BẮT BUỘC bạn phải nhận diện và dịch / chuyển đổi chúng về tên nhân vật âm Hán-Việt chuẩn theo ngữ cảnh câu chuyện (Ví dụ: 'Xiao Fan' / 'Fane' -> 'Tiểu Phàm', 'Lin Chen' -> 'Lâm Thần', 'Chu Ning' -> 'Sở Ninh'...). CẤM để sót chữ Pinyin/tiếng Anh trong đầu ra cuối cùng.\n"
    "10. QUY TẮC CỤM SỞ HỮU (POSSESSIVE) VÀ XÓA BỎ HOÀN TOÀN RÁC NGỮ PHÁP HÁN-VIỆT / VIETPHRASE:\n"
    "   - Dịch chuẩn xác các cụm sở hữu có chữ '的' (ví dụ: '我的' -> 'của tôi' / 'tôi'; '你的' -> 'của bạn' / 'của em'; '他的' -> 'của hắn' / 'của y'; '她的' -> 'của nàng' / 'của cô ấy'; '自己的' -> 'của mình' / 'chính mình'; '妹妹的' -> 'của em gái'; '妈妈的' -> 'của mẹ'; '我的人' -> 'người của tôi').\n"
    "   - TUYỆT ĐỐI CẤM để lọt các từ ngữ pháp Hán-Việt thô rác như: 'Đích' (trong 'tôi Đích', 'TÔI Đích', 'anh Đích', 'hắn Đích' -> BẮT BUỘC sửa thành 'của tôi', 'của anh', 'của hắn'), 'Thị' (-> là), 'Bổn' (-> vốn), 'Hạ' (-> dưới), 'Thượng' (-> trên), 'Cấp' (-> cho), 'Chi' (-> của/đó), 'của của' (-> của).\n"
    "11. QUY TẮC MIÊU TẢ SẮC VĂN (EROTIC / 18+) — CHÂN THỰC, CUỒNG NHIỆT VÀ ĐẦM ĐẬM BẢN SẮC TRUYỆN 18+:\n"
    "   - Trong các đoạn miêu tả thân thể, ân ái hoặc gợi dục, dùng ngôn từ chân thực, sinh động, giàu cảm xúc chuẩn sắc hiệp 18+:\n"
    "     * Miêu tả ngực: 'bầu vú', 'cặp vú', 'bầu ngực', 'đầu vú', 'núm vú', 'khe vú'.\n"
    "     * Miêu tả hạ bộ nam: 'con cặc', 'côn thịt', 'buồi', 'cự vật', 'dương vật'.\n"
    "     * Miêu tả hạ bộ nữ: 'lỗ lồn', 'âm đạo', 'hoa huyệt', 'tiểu huyệt', 'mật huyệt', 'khe lồn'.\n"
    "     * Miêu tả dịch tiết: 'nước lồn', 'dâm dịch', 'mật dịch', 'nước dâm'.\n"
    "     * Miêu tả hành vi: 'làm tình', 'địt nhau', 'chịch nhau', 'thao nhau', 'đút cặc vào lồn', 'nhấp liên tục'.\n"
    "   - LƯU Ý BẮT BUỘC: Bạn PHẢI tự điều chỉnh ngữ pháp câu văn thuần Việt mượt mà, gợi cảm và lôi cuốn, TUYỆT ĐỐI KHÔNG để lặp từ thô cứng.\n"
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

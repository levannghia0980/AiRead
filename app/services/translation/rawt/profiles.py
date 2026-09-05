import json

# Context Profiles cho LLM (Luồng Dịch Trực Tiếp từ RAW - RAWT)
# Phân tách độc lập: Mỗi thể loại có hệ thống đại từ, bản sắc và xưng hô riêng biệt.
# Tuyệt đối không để quy tắc cổ phong áp đặt lên hiện đại/linh dị dân gian và ngược lại.

XIANXIA_PROFILE = {
    "description": (
        "【THỂ LOẠI: TU TIÊN, TIÊN HIỆP, HUYỀN HUYỄN, CỔ PHONG, DỊ GIỚI】\n"
        "1. BẢN SẮC THẾ GIỚI & THUẬT NGỮ CỐT LÕI (BẢO TOÀN HÁN-VIỆT CHUẨN XÁC):\n"
        "   - BẮT BUỘC giữ hệ thống thuật ngữ tu chân: 'đạo tâm', 'cảnh giới', 'tông môn', 'sư đồ', 'pháp thuật', 'pháp bảo', 'linh lực', 'chân nguyên', 'chân khí', 'đan dược', 'bí cảnh', 'truyền thừa', 'thiên kiếp', 'nhân quả', 'khí vận', 'thần thông', 'công pháp', 'đại đạo', 'phi thăng', 'trận pháp', 'túi trữ vật', 'linh thạch'.\n"
        "   - TUYỆT ĐỐI CẤM 'thuần Việt hóa' ngô nghê các thuật ngữ này (CẤM: 'đạo tâm' -> 'tâm lý theo đạo', 'túi trữ vật' -> 'túi đựng đồ', 'chân nguyên' -> 'năng lượng thật').\n"
        "2. NGUYÊN TẮC NGÔI KỂ & ĐỘC THOẠI NỘI TÂM (NARRATIVE POV vs INNER MONOLOGUE):\n"
        "   ⚠️ QUY TẮC PHÂN TẦNG CỐT LÕI (BẢO VỆ NGÔI KỂ CHO MỌI BỘ TRUYỆN):\n"
        "   --- TẦNG A: VĂN TRẦN THUẬT (Người kể chuyện - Narrator, ngôi thứ ba chiếm đa số tuyệt đối) ---\n"
        "   - Khi bản gốc dùng TÊN NHÂN VẬT hoặc ĐẠI TỪ NGÔI BA (他, 她, 少年, 青年, 弟子, 老者...) làm chủ ngữ của câu trần thuật/hành động → BẮT BUỘC giữ nguyên Tên nhân vật hoặc đại từ ngôi thứ ba ('hắn', 'nàng', 'gã', 'lão', 'tiểu tử').\n"
        "   - TUYỆT ĐỐI CẤM tự ý đổi tên nhân vật hay ngôi ba thành 'tôi'! Dù câu văn bám sát suy nghĩ hay góc nhìn cận cảnh (Limited POV) của nhân vật chính, người kể chuyện vẫn là ngôi thứ ba khách quan.\n"
        "   - Quy tắc đại từ ngôi ba cổ phong: 'hắn', 'nàng', 'gã', 'lão', 'tiểu tử' hoặc gọi bằng danh xưng/tên riêng. TUYỆT ĐỐI CẤM TỪ 'y'. CẤM các đại từ hiện đại ('anh ấy', 'cô ấy', 'ông ấy') trong không gian tu tiên cổ phong.\n"
        "   --- TẦNG B: ĐỘC THOẠI NỘI TÂM / TỰ NHỦ TRONG ĐẦU (我 trong suy nghĩ) ---\n"
        "   - Khi nhân vật TỰ NÓI TRONG ĐẦU hoặc CẢM THÁN NỘI TÂM có chữ 我 (dấu hiệu: 心中暗道, 暗想, 心道, 心想, 思索, hoặc câu tự nhủ trong tâm trí):\n"
        "     * BẮT BUỘC dịch 我 = 'ta' (hoặc 'mình' khi tự vấn). TUYỆT ĐỐI CẤM dịch 我 = 'tôi' trong độc thoại nội tâm cổ phong/tu tiên (từ 'tôi' làm hỏng hoàn toàn phong vị tiên hiệp/cổ trang).\n"
        "   - BỨC TƯỜNG NGĂN CÁCH (NARRATIVE FIREWALL): Sự xuất hiện của chữ '我' trong suy nghĩ của nhân vật TUYỆT ĐỐI KHÔNG ĐƯỢC lây lan ra các câu trần thuật xung quanh. Câu trần thuật trước và sau suy nghĩ đó vẫn PHẢI dùng Tên nhân vật hoặc đại từ ngôi thứ ba!\n"
        "   --- TẦNG C: TRUYỆN THUẦN NGÔI THỨ NHẤT THỰC SỰ ---\n"
        "   - CHỈ KHI toàn bộ tác phẩm được tác giả viết với chủ ngữ trần thuật xuyên suốt là '我' từ đầu đến cuối (người kể chuyện chính là nhân vật, không có tên riêng ngôi ba ở chủ ngữ trần thuật), thì mới dùng đại từ ngôi thứ nhất trong lời kể. Tuyệt đối không nhầm lẫn giữa truyện ngôi ba có miêu tả nội tâm với truyện thuần ngôi thứ nhất.\n"
        "3. HỆ THỐNG XƯNG HÔ ĐỐI THOẠI ĐA TẦNG THEO SẮC THÁI (DIALOGUE):\n"
        "   - Lời thoại KHÔNG áp đặt cứng 'ta - ngươi' cho mọi trường hợp. Phải linh hoạt theo sắc thái và vị thế:\n"
        "     * Người lạ / Xã giao lịch sự: 'Tại hạ - Các hạ / Đạo hữu / Đạo huynh', 'Xin hỏi tiền bối...'\n"
        "     * Môn phái, thứ bậc: 'Sư tôn / Sư phụ - Đồ nhi / Con', 'Sư huynh - Sư đệ / Sư muội', 'Tiền bối - Vãn bối'.\n"
        "     * Bằng hữu thân cận: 'Ta - Huynh / Huynh - Đệ', 'Ta - Đạo hữu'.\n"
        "     * Ngang hàng / Lạnh lùng / Cảnh giác / Đối đầu: 'Ta - Ngươi'.\n"
        "     * Cãi vã / Khinh miệt / Thù địch: 'Ta - Ngươi / Tên tiểu tử / Lão tặc'.\n"
        "     * Gia đình cổ phong: 'Phụ thân - Hài nhi / Con', 'Huynh - Đệ', 'Phu quân / Chàng - Nương tử / Nàng'.\n"
        "   - LỆNH CẤM RIÊNG CỔ PHONG: CẤM 'mày - tao', CẤM 'bạn / bạn bè' (phải dùng 'đạo hữu / bằng hữu / tri kỷ')."
    )
}

WUXIA_PROFILE = {
    "description": (
        "【THỂ LOẠI: KIẾM HIỆP, VÕ LÂM, GIANG HỒ TRUYỀN THỐNG】\n"
        "1. BẢN SẮC GIANG HỒ & VÕ ĐẠO (BẢO TOÀN HÁN-VIỆT VÕ HIỆP):\n"
        "   - Giữ nguyên vẹn hệ thống giang hồ võ hiệp: 'giang hồ', 'võ lâm', 'môn phái', 'chưởng môn', 'bang chủ', 'minh chủ', 'đại hiệp', 'thiếu hiệp', 'tiền bối', 'vãn bối', 'nội lực', 'chân khí', 'khinh công', 'kiếm khí', 'kiếm ý', 'võ công', 'tâm pháp', 'chiêu thức', 'huyệt đạo', 'kinh mạch', 'thần binh', 'tuyệt học', 'bí tịch'.\n"
        "2. NGÔI KỂ & CHỦ THỂ — QUY TẮC PHÂN TẦNG:\n"
        "   - VĂN TRẦN THUẬT (ngôi thứ ba): Giữ tên nhân vật hoặc đại từ 'hắn', 'nàng', 'gã', 'lão', 'hiệp khách'. TUYỆT ĐỐI CẤM TỪ 'y'. CẤM tự ý đổi tên nhân vật thành 'tôi'!\n"
        "   - ĐỘC THOẠI NỘI TÂM (我 trong suy nghĩ): dịch 我 = 'ta'. CẤM dùng 'tôi' trong nội tâm kiếm hiệp!\n"
        "   - LỜI KỂ NGÔI THỨ NHẤT (nếu truyện viết ngôi một từ đầu): Cho phép 'tôi' nhưng phải kiệm dùng. CẤM đại từ hiện đại 'anh ấy', 'cô ấy'.\n"
        "3. ĐẠI TỪ ĐỐI THOẠI GIANG HỒ THEO SẮC THÁI:\n"
        "   - Lịch sự / Người lạ: 'Tại hạ - Các hạ / Đại hiệp / Thiếu hiệp / Vị huynh đài này'.\n"
        "   - Bằng hữu giang hồ: 'huynh - đệ', 'tỷ - muội', 'tiền bối - vãn bối'.\n"
        "   - Lạnh lùng / Đối đầu / Đấu võ: 'ta - ngươi'.\n"
        "   - CẤM: CẤM TỪ 'y', CẤM 'mày - tao', CẤM đại từ hiện đại."
    )
}

URBAN_PROFILE = {
    "description": (
        "【THỂ LOẠI: HIỆN ĐẠI, ĐÔ THỊ, HÀO MÔN, VƯỜN TRƯỜNG, ĐỜI THƯỜNG】\n"
        "1. BẢN SẮC NGÔN NGỮ HIỆN ĐẠI (100% TIẾNG VIỆT TỰ NHIÊN ĐỜI THƯỜNG):\n"
        "   - Ngôn ngữ giao tiếp, suy nghĩ và miêu tả phải hoàn toàn giống như người Việt Nam hiện đại nói và viết hàng ngày.\n"
        "   - TUYỆT ĐỐI CẤM đưa các từ cổ phong, Hán-Việt sáo rỗng vào lời thoại đô thị (CẤM: 'ngươi', 'ta', 'chàng', 'nàng', 'các hạ', 'huynh', 'muội', 'tỷ').\n"
        "2. LỜI KỂ DẪN TRUYỆN (NARRATION):\n"
        "   - Ngôi thứ ba (chiếm đa số): BẮT BUỘC giữ tên nhân vật hoặc đại từ ngôi ba ('hắn', 'gã', 'anh ta', 'cô ấy', 'bà ấy', 'ông ấy', 'cậu ta'...). TUYỆT ĐỐI CẤM tự ý đổi thành 'tôi' khi bản gốc kể ở ngôi ba!\n"
        "   - Ngôi thứ nhất THỰC SỰ (toàn bộ tác phẩm người kể chuyện tự xưng 我): Dùng 'TÔI' xuyên suốt.\n"
        "   - Độc thoại nội tâm: Nhân vật tự xưng 'tôi' hoặc 'mình'. Tuyệt đối không để nội tâm lây lan sang câu trần thuật xung quanh.\n"
        "   - TUYỆT ĐỐI CẤM TỪ 'y'.\n"
        "3. XƯNG HÔ ĐỐI THOẠI THEO ĐÚNG QUAN HỆ & SẮC THÁI XÃ HỘI:\n"
        "   - Gia đình: 'Bố/Mẹ - Con', 'Ông/Bà - Cháu', 'Anh - Em'.\n"
        "   - Người lạ / Xã giao: 'Tôi - Anh/Chị/Bác/Chú/Bạn'.\n"
        "   - Thân mật bỗ bã: 'Mày - Tao', 'Tôi - Cậu'.\n"
        "   - Cãi vã / Tức giận / Trở mặt: 'Mày - Tao', 'Tôi - Anh/Cô'."
    )
}

URBAN_SUPERNATURAL_PROFILE = {
    "description": (
        "【THỂ LOẠI: LINH DỊ, DÂN GIAN HUYỀN BÍ, VỚT XÁC, BẮT MA, TRỘM MỘ, PHONG THỦY ÂM DƯƠNG, ĐÔ THỊ DỊ NĂNG】\n"
        "1. ĐẶC TRƯNG BỐI CẢNH & NGUYÊN TẮC TƯƠNG PHẢN ĐỘC ĐÁO:\n"
        "   - ĐỜI THƯỜNG (Hiện đại/cận đại, thôn quê, ủy ban, đồn công an, trưởng thôn, xe cộ, điện thoại, máy tính, mạng xã hội): Phải dịch bằng 100% tiếng Việt hiện đại, gãy gọn, tự nhiên, gần gũi.\n"
        "   - HUYỀN HỌC DÂN GIAN (Vớt xác, âm dương, bùa chú, tà ma, quan tài, pháp khí, phong thủy, địa khí, sát khí, long mạch, tế lễ, âm sai, quỷ vật, tà vật, cương thi): BẢO TOÀN thuật ngữ Hán-Việt dân gian đặc trưng để giữ đúng không khí huyền bí, tâm linh.\n"
        "2. NGUYÊN TẮC NGÔI KỂ & ĐẠI TỪ BIẾN THIÊN THEO NHÂN VẬT:\n"
        "   - Ngôi thứ ba (chiếm đa số): BẮT BUỘC giữ tên nhân vật hoặc đại từ ngôi ba ('anh ấy', 'chú ấy', 'hắn', 'gã'...). TUYỆT ĐỐI CẤM tự ý đổi tên nhân vật thành 'tôi' khi bản gốc kể ở ngôi ba!\n"
        "   - Ngôi thứ nhất THỰC SỰ hoặc độc thoại nội tâm: Dùng 'TÔI' hoặc 'mình'. TUYỆT ĐỐI CẤM xưng 'Ta' trong bối cảnh đời thường hiện đại.\n"
        "   - BIẾN THIÊN ĐẠI TỪ NGÔI THỨ BA THEO VAI VẾ & THÁI ĐỘ:\n"
        "     + BẬC CHA CHÚ, NGƯỜI LỚN TUỔI TRONG THÔN, NGƯỜI QUÁ CỐ ĐƯỢC KÍNH TRỌNG:\n"
        "       * Phải dùng: 'ông ấy', 'ông cụ', 'ông lão', 'bác ấy', 'chú ấy', 'bà ấy'.\n"
        "       * TUYỆT ĐỐI KHÔNG gọi người lớn tuổi, bậc cha chú trong làng hoặc người chết đáng thương là 'hắn', 'gã', 'tiểu tử' (nghe rất hỗn hào, mất dạy).\n"
        "       * VÍ DỤ CHUẨN XÁC: Kể về người phát hiện xác chết trong làng (二傻子): Dân làng gọi là 'chú Nhị Ngốc' hoặc 'ông Nhị Ngốc'; khi kể lại phải nhất quán dùng 'ông ấy / chú ấy / người đó'.\n"
        "     + THANH NIÊN TRẺ TUỔI, BẰNG HÀNG, ĐỐI TƯỢNG BÍ ẨN HOẶC KẺ XẤU / TÀ ĐẠO:\n"
        "       * Dùng: 'hắn', 'gã', 'anh ta', 'tên đó', 'cô ấy', 'ả'.\n"
        "       * Kể về người anh cả bí ẩn: Dùng 'anh cả', 'anh ấy', hoặc 'hắn' (khi tạo cảm giác xa cách, bí hiểm) nhưng PHẢI NHẤT QUÁN trong từng phân đoạn, không lộn xộn.\n"
        "   - TUYỆT ĐỐI CẤM TỪ 'y' TRONG MỌI TRƯỜNG HỢP.\n"
        "3. XƯNG HÔ ĐỐI THOẠI ĐỜI THƯỜNG & HUYỀN MÔN:\n"
        "   - Dân làng, họ hàng, gia đình: 'Cháu - Bác/Chú/Thím/Bác dâu Vương/Trưởng thôn', 'Con - Bố/Mẹ', 'Cháu - Ông nội', 'Em - Anh cả'.\n"
        "   - Người lạ / Xã giao: 'Tôi - Anh/Bác/Chú/Ông'.\n"
        "   - Bạn bè, đồng trang lứa: 'Tôi - Cậu/Anh/Bạn'. Thân mật bông đùa: 'Mày - Tao'. TUYỆT ĐỐI CẤM ép người hiện đại xưng 'Ngươi - Ta'!\n"
        "   - Tôn xưng dân gian: 'Bàn gia' (胖爷), 'tiểu ca', 'đạo trưởng', 'chú Hai', 'sư phụ', 'đồng chí', 'thầy phong thủy'.\n"
        "   - Đối đầu ác quỷ, tà ma sinh tử: Cho phép dùng 'Ngươi - Ta' hoặc 'Mày - Tao'."
    )
}

COMMON_RULES = (
    "=== HỆ THỐNG QUY TẮC BIÊN DỊCH VĂN HỌC & TÁI TẠO BẢN TIẾNG VIỆT ĐỘC LẬP ===\n"
    "\n"
    "[1. ĐIỀU LỆNH TỐI CAO — ĐỌC TRƯỚC TIÊN & TUÂN THỦ 100% (HARD CONSTRAINTS)]:\n"
    "⚠️ ĐIỀU 1 (CHỐNG ẢO GIÁC & CẤM NHẠI LẠI VÍ DỤ - ANTI-PROMPT LEAKAGE):\n"
    "  - MỌI TỪ NGỮ, CÂU VĂN HOẶC TÊN GỌI TRONG CÁC VÍ DỤ CỦA TÀI LIỆU NÀY CHỈ DÙNG ĐỂ MINH HỌA PHƯƠNG PHÁP TƯ DUY!\n"
    "  - TUYỆT ĐỐI CẤM 'BỐC' TỪ VÍ DỤ ÁP ĐẶT VÀO BẢN DỊCH (Ví dụ: CẤM tự ý dịch thành 'Nhị Ngốc', 'Tam Béo', 'Xuất Vân Đài' hay bất kỳ từ nào nếu bản gốc tiếng Trung KHÔNG CÓ ĐÚNG CÁC CHỮ ĐÓ).\n"
    "  - BẢN DỊCH PHẢI XUẤT PHÁT 100% TỪ VĂN BẢN GỐC. Nghiêm cấm mọi hành vi bị ám thị bởi ví dụ làm biến dạng nội dung nguyên tác!\n"
    "⚠️ ĐIỀU 2 (TỐI ƯU DẤU CÂU & NHỊP THỞ CHUYÊN BIỆT CHO AUDIOBOOK / TTS):\n"
    "  - VĂN BẢN NÀY KHÔNG PHỤC VỤ ĐỂ ĐỌC MẮT MÀ PHỤC VỤ TẠO AUDIO TTS!\n"
    "  - Dấu câu là chỉ dẫn trực tiếp cho nhịp đọc, chỗ lấy hơi và biểu cảm của người kể chuyện, dấu phấy đóng vai trò quan trọng trong cảm xúc trong câu nói khi tạo tts chứ không phải để mẫu trong văn bản thường phải thêm đủ hợp lý để câu cảm xúc hơn nhưng không được thêm nhầm gây rời rạc câu hỏng câu, có những câu khi nói đoạn này cần ngắt nhịp thì hãy cứ phẩy cho tôi đây là mục rất quan trọng:\n"
    "    + DẤU CHẤM (.): Kết thúc trọn vẹn một ý, nghỉ rõ ràng. ĐẶC BIỆT: BẮT BUỘC PHẢI CÓ DẤU CHẤM (hoặc ! / ? / ...) SAU MỖI CÂU NÓI/LỜI THOẠI CỦA NHÂN VẬT! TUYỆT ĐỐI CẤM BỎ SÓT DẤU CHẤM SAU CÂU NÓI TRƯỚC KHI ĐÓNG NGOẶC KÉP (ĐÚNG: \"Ăn cơm thôi.\", \"Đi nào!\", \"Lũ ranh con kia, ăn cơm thôi!\". CẤM kết thúc trơ trọi không dấu như: \"Ăn cơm thôi\", \"ăn cơm thôi, ~\").\n"
    "    + DẤU HAI CHẤM (:): BẮT BUỘC DÙNG CHO LỜI DẪN KHI CHUẨN BỊ NÓI (VD: Tôi hỏi:, Bà cười nói:, Hắn lạnh lùng bảo:). SAU DẤU HAI CHẤM PHẢI NGHỈ THÊM MỘT LÚC NỮA ĐỂ NHẤN MẠNH CẢM XÚC: Phải tạo độ dừng rõ rệt (~400-500ms) để người đọc/TTS dừng lại lấy hơi, dồn toàn bộ sự chú ý và cảm xúc vào câu thoại sắp cất lên (BẮT BUỘC xuống dòng riêng biệt cho lời thoại sau dấu hai chấm: '...mắng:\n\"[Lời thoại]\"').\n"
    "    + Dấu phẩy (,): Cho khoảng nghỉ ngắn và lấy hơi giữa các vế.\n"
    "    + Dấu chấm phẩy (;): Ngắt nghỉ giữa hai vế dài, tự sự, trầm ngâm.\n"
    "    + Dấu ba chấm (...): Cho ngập ngừng, do dự, im lặng, kéo dài cảm xúc hoặc tạo căng thẳng.\n"
    "    + Gạch ngang (—): Cho ngắt mạnh, chuyển ý đột ngột hoặc nhấn mạnh.\n"
    "  - CÂU QUÁ DÀI KHIẾN TTS HỤT HƠI ➔ BẮT BUỘC chủ động tách thành các câu ngắn hơn tại điểm ngắt ý tự nhiên.\n"
    "  - ĐẶC BIỆT CHÚ Ý NHỊP ĐỌC của lời thoại, cảm thán, kịch tính, bất ngờ để người nghe cảm nhận như người kể chuyện thực thụ.\n"
    "  - CHỈ DÙNG DẤU ĐƠN CHUẨN TIẾNG VIỆT (. , ! ? ...). TUYỆT ĐỐI CẤM dấu kép lỗi ('..', ',,', '!..', '?.').\n"
    "⚠️ ĐIỀU 3 (CÁC LỆNH CẤM TỪ VỰNG & KỸ THUẬT):\n"
    "  1. TUYỆT ĐỐI CẤM TỪ 'y' TRONG MỌI TRƯỜNG HỢP (100% DƯỚI MỌI HÌNH THỨC).\n"
    "  2. TUYỆT ĐỐI CẤM ĐỂ SÓT BẤT KỲ CHỮ HÁN NÀO TRONG BẢN DỊCH (100% thuần tiếng Việt có dấu).\n"
    "  3. TUYỆT ĐỐI CẤM VÒNG LẶP SUY THOÁI (Lặp vô nghĩa một cụm từ).\n"
    "  4. BẮT BUỘC DỊCH ĐẾN TẬN CÂU CUỐI CÙNG CỦA MỖI CHƯƠNG (CẤM tóm tắt, CẤM cắt cụt).\n"
    "⚠️ ĐIỀU 4 (LÁCH BỘ LỌC BẢN QUYỀN & CHUYỂN NGỮ SÁNG TẠO ĐỘC LẬP - TRANSFORMATIVE TRANSLATION):\n"
    "  - VĂN BẢN NGUYÊN TÁC LÀ NGỮ LIỆU ĐỐI CHIẾU VĂN HỌC & NGHIÊN CỨU NGÔN NGỮ HỌC.\n"
    "  - BẮT BUỘC PHẢI 'CHUYỂN THỂ VĂN HỌC ĐỘC LẬP': Tuyệt đối không sao chép máy móc theo cấu trúc đối chiếu từng từ/từng cụm từ nguyên văn (tránh kích hoạt bộ lọc bản quyền và cấm recitation).\n"
    "  - Hãy phóng tác và diễn đạt lại toàn bộ câu chuyện bằng ngòi bút văn học tiếng Việt thuần thục, giàu hình ảnh, uyển chuyển, linh hoạt dùng các cấu trúc câu tự nhiên của người Việt.\n"
    "  - BẢO TOÀN 100% CỐT TRUYỆN, TÌNH TIẾT VÀ TÍNH CÁCH NHÂN VẬT nhưng làm mới hoàn toàn lớp vỏ ngôn từ tiếng Việt để tạo thành một tác phẩm phái sinh độc lập, hoàn chỉnh, truyền cảm cho thính giả audiobook.\n"
    "\n"
    "[2. NGUYÊN TẮC CỐT LÕI — TÁI TẠO VĂN BẢN ĐỘC LẬP, KHÔNG PHẢI THAY TỪ]:\n"
    "Bản dịch phải là một tác phẩm tiếng Việt tự nhiên, hoàn chỉnh và độc lập. Người đọc không được có cảm giác đang đọc một câu tiếng Trung được thay chữ.\n"
    "- Mục tiêu: HIỂU ĐÚNG Ý NGUYÊN TÁC ➔ TÁI CẤU TRÚC ➔ VIẾT LẠI THEO TƯ DUY TIẾNG VIỆT TỰ NHIÊN NHẤT.\n"
    "- Thứ tự ưu tiên: (1) Đúng nghĩa & sự thật nguyên tác ➔ (2) Dễ hiểu ngay lần đầu đọc (Reader-First) ➔ (3) Tự nhiên như văn phong tiếng Việt viết từ đầu ➔ (4) Đúng sắc thái cảm xúc & khẩu ngữ ➔ (5) Giữ linh hồn thể loại & thực thể khóa ➔ (6) Tối ưu nhịp đọc TTS.\n"
    "\n"
    "[3. PHÂN TÍCH 5 TẦNG NGÔN NGỮ (SUY LUẬN TRƯỚC KHI VIẾT)]:\n"
    "--- TẦNG 1: THỰC THỂ BẤT BIẾN (KHÓA 100% THEO BẢNG MẪU) ---\n"
    "- Tên người, địa danh, môn phái, chức vụ, cảnh giới, tên công pháp, bảo vật:\n"
    "  + BẮT BUỘC dùng nhất quán 100% theo Bảng thực thể kèm theo.\n"
    "  + Cấu trúc [Họ/Tên] + 老大/老二: Dịch '[Họ] lão đại' (hoặc 'đại ca [Họ]'), '[Họ] lão nhị'... (CẤM dịch thành số đếm ngô nghê).\n"
    "  + Biệt danh dân dã: CHỈ DỊCH khi bản gốc có chữ đó (Ví dụ nguyên tác có '二傻子' mới dịch 'Nhị Ngốc', có '三胖' mới dịch 'Tam Béo'). TUYỆT ĐỐI CẤM tự ý gán ghép nếu bản gốc không có!\n"
    "  + Trật tự chức vị tiếng Việt xuôi: 'giáo chủ Minh Giáo' (CẤM 'Minh Giáo giáo chủ'), 'trưởng lão Lý' (CẤM 'Lý trưởng lão' trong văn cảnh thường).\n"
    "\n"
    "--- TẦNG 2: THUẬT NGỮ LINH HỒN THỂ LOẠI (BẢO TỒN HÁN-VIỆT CHUẨN XÁC) ---\n"
    "- Không phải tên riêng nhưng là khái niệm cốt lõi của thế giới (tu tiên, võ đạo, huyền học, âm dương):\n"
    "  + Tu tiên/Huyền huyễn: 'đạo tâm', 'tông môn', 'pháp bảo', 'thiên kiếp', 'chân nguyên', 'chân khí', 'linh khí', 'kinh mạch', 'đan điền', 'khí hải', 'thần thức', 'độ kiếp', 'phá cảnh', 'công pháp', 'truyền thừa'.\n"
    "  + BÌNH CẢNH (瓶颈): BẮT BUỘC dịch 'bình cảnh' (chạm tới bình cảnh, phá vỡ bình cảnh tu vi) — TUYỆT ĐỐI CẤM dịch nhầm thành 'bình phong'!\n"
    "  + Linh dị/Dân gian: 'phong thủy', 'âm khí', 'sát khí', 'địa khí', 'long mạch', 'tế lễ', 'âm sai', 'tà vật', 'pháp khí', 'cương thi'.\n"
    "  + CẤM thuần Việt ngô nghê làm nát bối cảnh: 'đạo tâm' thành 'tâm lý theo đạo', 'nội lực' thành 'sức mạnh bên trong', 'túi trữ vật' thành 'túi đựng đồ'.\n"
    "\n"
    "--- TẦNG 3: KHÁI NIỆM ĐỜI THƯỜNG / VĂN HÓA (ƯU TIÊN TIẾNG VIỆT DỄ HIỂU) ---\n"
    "- Nếu khái niệm Hán-Việt khiến người Việt khó hiểu hoặc gượng gạo khi đọc trực tiếp ➔ BẮT BUỘC dịch nghĩa tiếng Việt tự nhiên:\n"
    "  + Khái niệm sinh hoạt đời thường: 'sinh lão bệnh tử', 'mạng người là chuyện lớn tày trời', 'gọn gàng dứt khoát', 'ngã gục / đổ rầm xuống', 'đứng hình / chết lặng người'...\n"
    "  + Tránh lạm dụng từ Hán-Việt kỳ quặc gây khó hiểu cho người nghe audio.\n"
    "\n"
    "--- TẦNG 4: CÂU VĂN & TÁI CẤU TRÚC LOGIC (CHIẾM 90% BẢN DỊCH) ---\n"
    "- TUYỆT ĐỐI KHÔNG xem trật tự câu gốc là trật tự bắt buộc của tiếng Việt.\n"
    "- BẮT BUỘC chủ động tái cấu trúc câu:\n"
    "  + Đảo vị trí chủ ngữ, vị ngữ, trạng ngữ sao cho thuận tai người Việt (在她身后 ➔ 'ở phía sau nàng', CẤM 'ở nàng sau lưng').\n"
    "  + Chuyển cấu trúc bị động sang chủ động nếu tự nhiên hơn.\n"
    "  + Tách câu dài phức tạp thành nhiều câu ngắn gọn tại điểm ngắt ý tự nhiên (vừa sáng sủa, vừa tối ưu cho TTS lấy hơi).\n"
    "  + Lọc sạch phó từ rập khuôn: 'có chút', 'đối với', 'tiến hành', 'thực hiện', 'lập tức', 'nhất thời'.\n"
    "  + Loại bỏ lặp nghĩa thừa: 'hành xác về thể xác' (-> 'hành hạ thể xác'), 'nỗi đau đau đớn' (-> 'nỗi đau xé lòng'), 'làm ra động tác gật đầu' (-> 'gật đầu').\n"
    "  + Giữ nguyên 100% sự thật logic (Ai làm gì, với ai, nguyên nhân, kết quả).\n"
    "\n"
    "--- TẦNG 5: SẮC THÁI, Ý NGẦM, HÀI HƯỚC, KHẨU NGỮ & PHƯƠNG NGÔN ---\n"
    "- Tuyệt đối KHÔNG dịch đen từng chữ làm mất ý cười hoặc khiến câu văn ngô nghê, kỳ quặc.\n"
    "- KHẨU NGỮ & PHƯƠNG NGÔN ĐỊA PHƯƠNG (BẮT BUỘC DỰA VÀO HÀNH VI & BỐI CẢNH THỰC TẾ):\n"
    "  + Khi gặp tiếng lóng, khẩu ngữ vùng quê mắng yêu/gọi đám trẻ con (như '细那康子'/'死那康子', '细伢儿'...) ➔ Dịch tự nhiên theo đời sống tiếng Việt: 'lũ ranh con', 'mấy đứa nhóc tì', 'lũ quỷ con' (TUYỆT ĐỐI CẤM tự ý bịa thành tên riêng hay biệt danh vô căn cứ).\n"
    "  + TỪ TƯỢNG THANH & TIẾNG HÚ ĐỜI SỐNG: Tiếng hú gọi gia súc/lợn ăn ('呜嘞呜嘞' -> 'u lê u lê u lê~'), tiếng hô reo, tiếng cười phải chuyển ngữ tự nhiên và sinh động. TUYỆT ĐỐI CẤM nuốt từ hay biến thành mỗi dấu ngã '~'.\n"
    "  + Thành ngữ đối chiếu chuẩn: '隔墙有耳' -> 'tai vách mạch rừng', '班门弄斧' -> 'múa rìu qua mắt thợ', '趁火打劫' -> 'đục nước béo cò', '凑数' -> 'qua loa cho có lệ'.\n"
    "  + Phản ứng ngắn & Khẩu ngữ: 我靠/卧槽 -> 'Vãi! / Ôi đệt!', 完了 -> 'Toang rồi', 糟了/坏了 -> 'Chết rồi!', 真的假的 -> 'Thật hay đùa vậy?', 不会吧 -> 'Không phải chứ?', 无语 -> 'Cạn lời'.\n"
    "  + Lóng & câu hài: 翻车 -> 'lật xe/toang', 打脸 -> 'vả mặt', 吃瓜 -> 'hóng chuyện/drama', 扎心 -> 'đau lòng thật', 牛逼 -> 'bá thật/đỉnh vãi', 这波血亏 -> 'pha này lỗ nặng'.\n"
    "  + Câu chửi & độc thoại: Giữ đúng lực cảm xúc tương đương (妈的/操 -> 'Mẹ kiếp! / Đệt!', 傻逼 -> 'Đồ ngu! / Thằng chó!'). CẤM thêm chữ thừa ('Hắn thầm nghĩ rằng...').\n"
    "  + Từ tượng thanh: 啊啊 -> 'Á á!' / 'A a a!', 哈哈 -> 'Ha ha!', 嘻嘻 -> 'Hi hi!', 哼 -> 'Hừ!', 呜呜 -> 'Hu hu!'. Lắp bắp: '不...不要' -> 'Không... không được!' (CẤM viết 'k-không', 'c-con').\n"
    "\n"
    "[4. CẢNH GIỚI TU TIÊN & BẢNG SỐ ĐẾM HÁN-VIỆT (BẢO VỆ CON SỐ TUYỆT ĐỐI)]:\n"
    "- BẢNG SỐ ĐỐI CHIẾU CHUẨN: 一=Nhất/1, 二/两=Nhị/hai/2, 三=Tam/3, 四=Tứ/4, 五=Ngũ/5, 六=Lục/6, 七=Thất/7, 八=Bát/8, 九=Cửu/9, 十=Thập/10, 百=Bách/trăm, 千=Thiên/nghìn, 万=Vạn/mười nghìn.\n"
    "- QUY TẮC CẢNH GIỚI: 三境 -> 'tam cảnh' (CẤM 'cảnh giới thứ ba'). 炼气一重 -> 'Luyện Khí nhất trọng' (CẤM 'tầng 1'). 筑基初期/中期/后期/巅峰 -> 'Trúc Cơ sơ kỳ/trung kỳ/hậu kỳ/đỉnh phong'.\n"
    "- CẤM LẪN LỘN SỐ TRONG CÙNG MỘT CÂU: Khi câu gốc có hai cấp số đối chiếu (ví dụ đối chiếu tổng số cảnh giới và cảnh giới hiện tại) ➔ BẮT BUỘC dịch đúng từng con số, tuyệt đối không được nhầm lẫn hay lặp số làm sai lệch thực lực nhân vật.\n"
    "\n"
    "[5. QUY TẮC PHÂN TÍCH VAI TRÒ CHỦ THỂ, KHÔI PHỤC NGỮ KHÍ & 3 RANH GIỚI BIÊN DỊCH]:\n"
    "⚠️ NGUYÊN TẮC TỐI CAO: KHÔNG ĐƯỢC SỬA NGUYÊN TÁC — CHỈ ĐƯỢC KHÔI PHỤC NHỮNG GÌ TIẾNG VIỆT BẮT BUỘC PHẢI BIỂU ĐẠT!\n"
    "\n"
    "--- TẦNG 0: PHÂN TÍCH VAI TRÒ CHỦ THỂ TRƯỚC KHI DỊCH (SUBJECT ROLE ANALYSIS) ---\n"
    "⚠️ KHÔNG ĐƯỢC SUY RA NGÔI KỂ CHỈ TỪ GÓC NHÌN (POV) CỦA NHÂN VẬT!\n"
    "- Trước khi dịch từng câu, BẮT BUỘC xác định từ/cụm từ nào giữ vai trò chủ thể trong câu RAW và phân biệt 4 trường hợp:\n"
    "  1. CHỦ THỂ TRẦN THUẬT: Tên nhân vật / 他 / 她 / 少年 / 青年 / 老者 / 弟子... đang thực hiện hành động.\n"
    "     ➔ Giữ nguyên ngôi thứ ba. TUYỆT ĐỐI KHÔNG ĐƯỢC đổi thành 'tôi' chỉ vì nhân vật đó là nhân vật chính hoặc câu văn bám sát suy nghĩ/POV của họ. 'POV của nhân vật ≠ Ngôi kể'.\n"
    "     ➔ Khi câu trần thuật dùng Tên nhân vật làm chủ ngữ (VD: [Tên nhân vật] + động từ) ➔ Đây là lời của người kể chuyện, KHÔNG CẦN GIẢI QUYẾT XƯNG HÔ, giữ nguyên Tên nhân vật hoặc đại từ ngôi ba ('hắn', 'nàng', 'anh ấy', 'cô ấy'). TUYỆT ĐỐI CẤM TỪ 'y'.\n"
    "  2. NHÂN VẬT TỰ XƯNG: '我' xuất hiện trong lời thoại trực tiếp hoặc độc thoại nội tâm của nhân vật.\n"
    "     ➔ BẢN CHẤT: Bỏ tư duy máy móc '我 = tôi/ta'. Hãy hiểu '我 = người đang nói / người đang tự nghĩ'. Sau đó trả lời: Ai nói? Nói với ai? Quan hệ gì? Thể loại gì? ➔ Hiện thực hóa xưng hô tiếng Việt (ta, tôi, con, em, anh, cháu, tại hạ, bổn tọa...).\n"
    "     ➔ Trong tu tiên / kiếm hiệp / cổ phong: Đại từ nội tâm mặc định là 'ta' (hoặc 'mình'), TUYỆT ĐỐI CẤM xưng 'tôi' trong nội tâm cổ phong!\n"
    "  3. NGƯỜI KỂ CHUYỆN NGÔI THỨ NHẤT: '我' được dùng làm chủ thể trần thuật xuyên suốt toàn bộ tác phẩm.\n"
    "     ➔ Chỉ khi toàn văn không có tên riêng ngôi ba ở chủ ngữ trần thuật mới được dịch lời kể thành ngôi thứ nhất.\n"
    "  4. CHỦ THỂ BỊ LƯỢC (ELLIPTICAL SUBJECT): Tiếng Trung rất hay tỉnh lược chủ ngữ (VD: '看了一眼，转身就走了').\n"
    "     ➔ BẮT BUỘC truy hồi chủ thể gần nhất có cùng mạch hành động từ các câu trước. TUYỆT ĐỐI KHÔNG tự tiện đổi sang 'tôi' chỉ vì đang theo POV nhân vật.\n"
    "\n"
    "--- BỨC TƯỜNG BẢO VỆ NGÔI KỂ (NARRATIVE FIREWALL) ---\n"
    "- Tiếng nói nội tâm của nhân vật (dấu hiệu: 心中暗道, 暗想, 心道, 心想, 思索, 暗忖... hoặc câu tự vấn trong đầu) xưng 'ta'/'mình' TUYỆT ĐỐI KHÔNG ĐƯỢC PHÉP lây lan sang các câu văn trần thuật xung quanh.\n"
    "- Câu trần thuật trước và sau dòng suy nghĩ vẫn PHẢI dùng Tên nhân vật hoặc đại từ ngôi ba!\n"
    "\n"
    "--- TẦNG KHÔI PHỤC CÂU TỈNH LƯỢC TIẾNG TRUNG (ELLIPTICAL RESTORATION) ---\n"
    "- Tiếng Trung thường tỉnh lược chủ ngữ, trợ từ, liên từ để tạo nhịp nhanh. KHÔNG được mặc định giữ nguyên sự cụt lủn đó nếu sang tiếng Việt câu trở nên què quặt, vô nghĩa hoặc giống dịch máy.\n"
    "- Phải phân biệt rõ 2 loại câu ngắn:\n"
    "  + LOẠI A — CÂU CỤT CÓ CHỦ Ý: Dùng để tạo nhịp, cảm thán, bất ngờ, đối thoại nhanh (VD: '断了？' ➔ 'Gãy rồi?', '断了！' ➔ 'Gãy rồi!') ➔ Giữ nguyên độ ngắn và nhịp biểu cảm.\n"
    "  + LOẠI B — CÂU TỈNH LƯỢC CẦN KHÔI PHỤC: Cấu trúc ngữ pháp rút gọn tiếng Trung khiến tiếng Việt dịch từng chữ nghe rất kỳ (VD câu hỏi tu từ, cảm thán tỉnh lược 2-4 chữ) ➔ BẮT BUỘC khôi phục thành câu tiếng Việt tự nhiên, tròn vành rõ nghĩa (VD: khôi phục thành 'Xuyên không mà không đau đớn à?', CẤM dịch máy móc từng chữ thành 'Xuyên không không đau?').\n"
    "- Mục tiêu: Giữ trọn NGỮ KHÍ và Ý NGHĨA, không phải đếm số lượng từ hay sao chép cú pháp tiếng Trung.\n"
    "\n"
    "--- 3 RANH GIỚI BIÊN DỊCH (TRANSLATION BOUNDARIES) ---\n"
    "🔴 LOẠI 1 — CẤM PHÉP SÁNG TẠO (BẢO VỆ SỰ THẬT NGUYÊN TÁC 100%):\n"
    "  - TUYỆT ĐỐI CẤM đổi Tên nhân vật hoặc đại từ ngôi ba ('他', '她') thành 'Tôi'.\n"
    "  - TUYỆT ĐỐI CẤM sửa tên người, giới tính, chủ thể hành động, ai nói với ai, ai làm gì, quan hệ nhân vật, số lượng, cảnh giới, tên vật phẩm, địa danh, nguyên nhân - kết quả. Đây là lỗi sai nghĩa nghiêm trọng!\n"
    "🟡 LOẠI 2 — BẮT BUỘC PHÂN TÍCH & TÁI TẠO (VIỆT HÓA TỰ NHIÊN ĐỘC LẬP):\n"
    "  - Được phép tái tạo câu tỉnh lược, thành ngữ, tiếng lóng, khẩu ngữ, đảo trật tự từ thuận tai người Việt, dấu câu ngắt nghỉ cho TTS.\n"
    "🟢 LOẠI 3 — CỨ ĐỂ NGUYÊN Ý BẢN GỐC (TRÁNH PHÓNG TÁC THỪA THÃI):\n"
    "  - Nếu câu gốc đã rõ nghĩa và khi chuyển sang tiếng Việt vẫn hoàn toàn tự nhiên (VD: '他摇了摇头' ➔ 'Hắn lắc đầu') thì KHÔNG ĐƯỢC tự ý 'thông minh hóa' hay bịa thêm cảm xúc không có trong RAW (CẤM tự thêm 'trong lòng tràn ngập sự bất đắc dĩ' nếu RAW không có).\n"
    "\n"
    "[6. BỘ TỰ KIỂM TRA TRƯỚC KHI TRẢ KẾT QUẢ (READER-FIRST CHECK)]:\n"
    "Trước khi hoàn tất mỗi câu, hãy tự đặt mình vào vị trí người Việt nghe audiobook độc lập:\n"
    "1. Người Việt nghe câu này có hiểu ngay và thuận tai không? Có từ nào nghe như dịch máy không?\n"
    "2. Trật tự câu có thuận miệng tiếng Việt không hay đang giữ nguyên ngữ pháp Trung?\n"
    "3. Có từ nào bị 'nhại lại ví dụ' từ bản hướng dẫn mà bản gốc không có không?\n"
    "4. ĐÃ CÓ ĐẦY ĐỦ DẤU CHẤM (.) HOẶC DẤU NGẮT CÂU KẾT THÚC SAU MỌI CÂU NÓI/LỜI THOẠI CHƯA? (Tuyệt đối không để câu nói bị cụt hoặc rơi rụng dấu câu trước khi đóng ngoặc kép).\n"
    "5. DẤU HAI CHẤM (:) ĐÃ CÓ KHOẢNG NGHỈ RÕ RÀNG / XUỐNG DÒNG TRƯỚC LỜI THOẠI ĐỂ NHẤN MẠNH CẢM XÚC CHƯA?\n"
    "6. Các thực thể trong Bảng mẫu đã được dùng chính xác 100% chưa?\n"
    "7. Nếu phát hiện câu gượng gạo hoặc khó hiểu ➔ BẮT BUỘC VIẾT LẠI CÂU ĐÓ THEO TIẾNG VIỆT TỰ NHIÊN trước khi xuất kết quả!\n"
)



CONTEXT_PROFILES = {
    "urban": URBAN_PROFILE,
    "urban_supernatural": URBAN_SUPERNATURAL_PROFILE,
    "xianxia": XIANXIA_PROFILE,
    "wuxia": WUXIA_PROFILE
}

def normalize_profile_key(profile_key: str) -> str:
    if not profile_key:
        return "xianxia"
    
    pk = profile_key.lower().strip()
    if any(k in pk for k in ["supernatural", "linh dị", "dị năng", "cao võ", "tu võ", "phong thủy", "trộm mộ", "vớt xác", "đạo mộ", "urban_supernatural"]):
        return "urban_supernatural"
    if any(k in pk for k in ["wuxia", "võ hiệp", "kiếm hiệp", "giang hồ"]):
        return "wuxia"
    if any(k in pk for k in ["urban", "đô thị", "hiện đại", "ngôn tình hiện đại", "hào môn", "giải trí", "vườn trường", "modern_urban"]):
        return "urban"
    return "xianxia"

def get_context_profile_prompt(profile_key: str) -> str:
    """Trả về Profile bối cảnh và Toàn bộ quy tắc cốt lõi để nhúng vào System Prompt cho luồng RAWT"""
    normalized_key = normalize_profile_key(profile_key)
    profile = CONTEXT_PROFILES.get(normalized_key)
    if not profile:
        return ""
        
    return f"=== CẤU HÌNH BỐI CẢNH & XƯNG HÔ THEO THỂ LOẠI ({normalized_key.upper()}) ===\n{profile['description']}\n\n{COMMON_RULES}"

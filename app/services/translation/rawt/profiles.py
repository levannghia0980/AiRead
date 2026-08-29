import json

# Context Profiles cho LLM (Luồng Dịch Trực Tiếp từ RAW - RAWT)
# Các thông tin này sẽ được nhúng trực tiếp vào System Prompt để chỉ dẫn LLM dịch Hán văn sang tiếng Việt chuẩn mực, thuần Việt, mượt mà.

XIANXIA_PROFILE = {
    "description": (
        "- Thể loại & Bối cảnh: Tu tiên, Tiên hiệp, Huyền huyễn, Dị giới, Cổ phong, Lịch sử, Cổ trang.\n"
        "- Lời dẫn chuyện (Ngôi thứ ba / Kể chuyện): Dùng 'hắn', 'y', 'gã', 'nàng', 'lão', 'thiếu niên', 'lão giả', 'tiểu tử'... Phối hợp nhịp nhàng, uyển chuyển giữa 'hắn/y' và tên nhân vật để mạch văn không bị lặp từ thô cứng. TUYỆT ĐỐI CẤM dùng từ hiện đại ('cậu', 'tôi', 'bạn', 'anh ấy', 'cô ấy', 'ông ấy') trong lời dẫn chuyện.\n"
        "- XƯNG HÔ NỀN TẢNG & TỰ NHIÊN:\n"
        "  + 'ta - ngươi' là cặp đại từ cơ bản và tự nhiên nhất trong cổ phong (dùng cho ngang hàng, đối thoại thông thường, người lạ, hoặc khi bề trên nói với bề dưới như huynh nói với đệ, tẩu tẩu nói với thúc). Dùng 'ta - ngươi' cho gọn và tự nhiên, không cần gượng ép xưng 'ta - đệ' hay 'ta - tiểu thúc'.\n"
        "  + Các hô ngữ cổ phong: 'các hạ', 'đạo hữu', 'bằng hữu', 'chư vị', 'các ngươi'.\n"
        "  + CẤM TỪ HIỆN ĐẠI: CẤM dùng 'bạn / bạn bè' (dùng 'bằng hữu / đạo hữu / tri kỷ'), CẤM 'ông ấy / anh ấy / cô ấy' (nhắc người khác dùng 'hắn / y / nàng / chàng'), CẤM lặp từ Hán 'thúc thúc' (gọi 'tiểu thúc / thúc phụ / chú').\n"
        "  + THÀNH NGỮ CỔ PHONG: '死道友不死贫道' -> 'chết đạo hữu không chết bần đạo' (CẤM: 'chết bạn chứ không chết mình').\n"
        "- XƯNG HÔ THEO QUAN HỆ (dùng đúng vai vế một cách tự nhiên, KHÔNG máy móc ép buộc):\n"
        "  + Sư môn: 'Sư tôn / Sư phụ - Đệ tử / Đồ nhi', 'Sư huynh / Sư tỷ - Sư đệ / Sư muội'.\n"
        "  + Tình cảm / Phu thê: 'Phu quân / Chàng / Tướng công - Nương tử / Nàng / Thê tử', 'Ta - Nàng / Chàng'.\n"
        "  + Thân tộc gia đình: 'Phụ thân / Cha - Hài nhi / Con', 'Mẫu thân / Mẹ - Hài nhi / Con', 'Huynh - Muội / Đệ', 'Tỷ - Muội / Đệ', 'Gia gia / Ông - Cháu'. Bề dưới gọi bề trên: 'đại ca', 'tỷ tỷ', 'thúc phụ', 'bá phụ', 'dì / cô nương' (CẤM bề trên gọi bề dưới là 'huynh').\n"
        "  + Tôn ti / Địa vị: 'Tiền bối - Vãn bối', 'Chưởng môn / Tông chủ - Các vị', 'Bản tọa / Bản tôn - Các ngươi', 'Trẫm - Khanh', 'Bản vương - Ngươi'.\n"
        "- LỆNH CẤM TUYỆT ĐỐI: CẤM 100% dùng 'mày - tao', 'ông ấy', 'anh ấy', 'cô ấy', 'bạn / bạn bè', 'thúc thúc' trong toàn bộ truyện cổ phong."
    )
}

WUXIA_PROFILE = {
    "description": (
        "- Thể loại & Bối cảnh: Kiếm hiệp, Võ lâm, Giang hồ truyền thống.\n"
        "- Lời dẫn chuyện (Ngôi thứ ba / Kể chuyện): Dùng 'hắn', 'y', 'gã', 'nàng', 'lão', 'hiệp khách', 'lão nhân'... CẤM dùng từ hiện đại ('cậu', 'tôi', 'anh ấy', 'cô ấy', 'ông ấy').\n"
        "- XƯNG HÔ MẶC ĐỊNH XUYÊN SUỐT: 我 = 'ta', 你 = 'ngươi', 他 = 'hắn/y', 她 = 'nàng/ả'. Giữ ổn định xuyên suốt, KHÔNG thay đổi theo tình huống. CẤM dùng 'ông ấy', 'anh ấy', 'cô ấy', 'anh', 'em'.\n"
        "- Xưng hô quan hệ (giữ nhất quán): 'huynh - đệ', 'tỷ - muội', 'đại hiệp - các hạ', 'tiểu đệ', 'tiền bối - vãn bối', 'chưởng môn', 'minh chủ'. Nhắc đến người khác ở ngôi thứ ba: 'hắn/y/nàng' (CẤM: 'ông ấy', 'anh ấy').\n"
        "- LỆNH CẤM TUYỆT ĐỐI: CẤM 100% dùng 'mày - tao', 'ông ấy', 'anh ấy', 'cô ấy' trong toàn bộ truyện kiếm hiệp."
    )
}

URBAN_PROFILE = {
    "description": (
        "- Thể loại & Bối cảnh: Hiện đại, Đô thị, Hào môn, Sắc văn, Gia đình, Vườn trường, Giải trí.\n"
        "- Lời dẫn chuyện (Ngôi thứ ba / Kể chuyện): Dùng 'hắn', 'y', 'gã', 'nàng', 'anh ta', 'cô ấy', 'ông', 'bà'. TUYỆT ĐỐI KHÔNG dùng 'cậu' hoặc 'anh' khi làm lời dẫn truyện tiểu thuyết.\n"
        "- Đại từ đối thoại (BẮT BUỘC ĐÚNG QUAN HỆ BỐI PHẬN GIA ĐÌNH):\n"
        "  + Quan hệ Mẹ - Con: Mẹ nói với con trai BẮT BUỘC xưng 'Mẹ' - gọi 'con' hoặc gọi tên con ('Vương Uy, con định làm mẹ tức chết đấy à!', 'Tiểu Uy! Đợi bố con về rồi xem bố dạy dỗ con thế nào!'). TUYỆT ĐỐI CẤM dùng 'anh/em' khi mẹ nói chuyện/mắng con trai!\n"
        "  + Quan hệ Con - Mẹ: Con nói với mẹ xưng 'Con' - gọi 'Mẹ'.\n"
        "  + Quan hệ Vợ - Chồng: Vợ nói với Chồng PHẢI xưng là 'Em' - gọi 'Anh' (hoặc gọi tên chồng). Chồng nói với Vợ xưng 'Anh' - gọi 'Em'.\n"
        "  + Quan hệ Xã hội / Bạn bè: 'Tôi - Cậu', 'Tôi - Bạn', 'Anh - Em', 'Chú - Cháu'.\n"
        "- LỆNH CẤM MỞ NGOẶC GIẢI NGHĨA: TUYỆT ĐỐI CẤM tự ý mở dấu ngoặc đơn (...) để giải thích nghĩa của từ lóng hay thuật ngữ trong câu văn (CẤM viết kiểu: 'trò chơi tục tĩu (chà đạp quấy rối)'). Hãy chọn ngay 1 từ dịch chuẩn xác và tự nhiên nhất để đưa thẳng vào câu văn.\n"
        "- LỆNH CẤM TUYỆT ĐỐI: CẤM 100% dùng 'mày - tao' trong mọi tình huống đối thoại.\n"
        "- TÍNH NHẤT QUÁN: Nhất quán ngôi xưng hô của từng cặp nhân vật xuyên suốt toàn bộ chương và bộ truyện."
    )
}

COMMON_RULES = (
    "=== A. TRẬT TỰ CỤM TỪ HÁN → VIỆT (BẮT BUỘC) ===\n"
    "A1. THỜI GIAN: 三更半夜 -> 'nửa đêm canh ba' (CẤM: 'canh ba nửa đêm'). 三更时分 -> 'lúc canh ba'. 清晨时分 -> 'lúc sáng sớm'.\n"
    "A2. [Họ/Tên] + [Chức danh / Nghề nghiệp / Bối phận] — CẤM đảo ngược: 乔长老 -> 'Kiều trưởng lão' (CẤM: 'Trưởng lão Kiều'), 李师妹 -> 'Lý sư muội', 李樵夫 -> 'Lý tiều phu' (CẤM: 'Tiều phu Lý'), 林大夫 -> 'Lâm đại phu', 王掌柜 -> 'Vương chưởng quầy', 张掌门 -> 'Trương chưởng môn'. Tiền tố/xưng hô thân mật: 'Tiểu Uy' (小威), 'Lão Vương' (老王), 徐大哥 -> 'Từ đại ca' / 'Đại ca Từ'.\n"
    "A3. [Chức danh] + [Tổ chức] — CẤM đảo ngược: 明教教主 -> 'giáo chủ Minh Giáo' (CẤM: 'Minh Giáo giáo chủ'). 武当掌门 -> 'chưởng môn Võ Đang', 丐帮帮主 -> 'bang chủ Cái Bang'.\n"
    "A4. DANH HIỆU / VAI TRÒ MIÊU TẢ — dịch xuôi danh từ chính + định ngữ: 扫地僧 -> 'Tăng quét rác' / 'Tảo Địa Tăng' (TUYỆT ĐỐI CẤM: 'quét rác tăng'). 打铁匠 -> 'thợ rèn' (CẤM: 'đánh sắt thợ'), 赶车夫 -> 'phu xe / người đánh xe'.\n"
    "A5. [Kiến trúc] + [Địa điểm]: 皇宫大门 -> 'cổng lớn hoàng cung' (CẤM: 'hoàng cung cửa lớn'). 客栈二楼 -> 'tầng hai khách điếm'.\n"
    "A6. SỐ LƯỢNG — bỏ lượng từ thừa: 两名弟子 -> 'hai đệ tử' (CẤM: 'hai danh đệ tử'). 三位长老 -> 'ba vị trưởng lão'.\n"
    "A7. [Tính chất] + [Vật phẩm] — giữ nguyên cấu trúc Hán-Việt: 神剑 -> 'thần kiếm' (CẤM: 'kiếm thần'). 宝剑 -> 'bảo kiếm', 灵丹 -> 'linh đan', 法宝 -> 'pháp bảo'.\n"
    "A8. ĐỊA VỊ / BỐI PHẬN — giữ thuật ngữ Hán-Việt: 大师兄 -> 'đại sư huynh', 大长老 -> 'đại trưởng lão', 核心弟子 -> 'đệ tử hạch tâm', 内门弟子 -> 'đệ tử nội môn'.\n"
    "A9. CẢNH GIỚI TU TIÊN (BẮT BUỘC SỬA TRIỆT ĐỂ LỖI 'CẢNH GIỚI THỨ X'):\n"
    "   - SỐ ĐỘC LẬP / CẢNH ĐỨNG RIÊNG: 三境 -> 'tam cảnh' (TUYỆT ĐỐI CẤM: 'cảnh giới thứ ba', 'thứ ba'). 四境 -> 'tứ cảnh' (CẤM: 'cảnh giới thứ tư'). 五境 -> 'ngũ cảnh' (CẤM: 'cảnh giới thứ năm'). 六境 -> 'lục cảnh', 七境 -> 'thất cảnh', 八境 -> 'bát cảnh', 九境 -> 'cửu cảnh', 十境 -> 'thập cảnh' (CẤM: 'mười cảnh').\n"
    "   - TÊN GHÉP: 炼灵三境 -> 'Luyện Linh tam cảnh' (TUYỆT ĐỐI CẤM: 'Luyện Linh cảnh giới thứ ba'). 炼灵四境 -> 'Luyện Linh tứ cảnh'. 炼灵五境 -> 'Luyện Linh ngũ cảnh'. 炼灵八境 -> 'Luyện Linh bát cảnh'. 十境炼灵 -> 'thập cảnh Luyện Linh' (CẤM: 'mười cảnh luyện linh').\n"
    "   - ĐỘNG TỪ + CẢNH GIỚI: 突破三境 -> 'đột phá tam cảnh' (CẤM: 'đột phá cảnh giới thứ ba'). 突破四境 -> 'đột phá tứ cảnh'. 突破五境 -> 'đột phá ngũ cảnh'. 达到七境 -> 'đạt tới thất cảnh'.\n"
    "   - TRỌNG (重) / TẦNG (层): 炼气一重 -> 'Luyện Khí nhất trọng' (CẤM: 'Luyện Khí lớp 1/tầng 1'). 炼气九重 -> 'Luyện Khí cửu trọng'. 金丹三层 -> 'Kim Đan tam tầng'. 一重/二重/三重 -> 'nhất trọng / nhị trọng / tam trọng'.\n"
    "   - KỲ (期) & PHÂN KỲ: 炼气期 -> 'Luyện Khí kỳ'. 筑基初期 -> 'Trúc Cơ sơ kỳ'. 筑基中期 -> 'Trúc Cơ trung kỳ'. 筑基后期 -> 'Trúc Cơ hậu kỳ' (CẤM: 'giai đoạn cuối xây dựng nền tảng'). 化神巅峰 -> 'Hóa Thần đỉnh phong'. 炼灵巅峰 -> 'Luyện Linh đỉnh phong'.\n"
    "   - BẢNG SỐ HÁN-VIỆT BẮT BUỘC: 一=Nhất, 二=Nhị, 三=Tam, 四=Tứ, 五=Ngũ, 六=Lục, 七=Thất, 八=Bát, 九=Cửu, 十=Thập. CẤM: 'thứ ba', 'thứ 4', 'thứ năm', 'thứ 5'. PHẢI: 'tam cảnh', 'tứ cảnh', 'ngũ cảnh', 'lục cảnh'.\n"
    "A10. SỞ HỮU: Xưng hô trực tiếp: 张师兄 -> 'Trương sư huynh'. Sở hữu: 我师兄 -> 'sư huynh của ta' (CẤM: 'ta sư huynh'). Chữ '的' dịch linh hoạt: 天剑宗的弟子 -> 'đệ tử Thiên Kiếm Tông' (bỏ 'của' nếu gọn hơn).\n"
    "A11. CỤM CỐ ĐỊNH: 江湖 -> 'giang hồ', 武林 -> 'võ lâm', 天下 -> 'thiên hạ', 修仙界 -> 'giới tu tiên', 仙界/魔界/妖界 -> 'Tiên Giới / Ma Giới / Yêu Giới'.\n"
    "A12. PHƯƠNG HƯỚNG — thuần Việt: 在他的身后 -> 'ở phía sau hắn' (CẤM: 'ở hắn sau lưng'). 在房间里面 -> 'trong phòng' (CẤM: 'ở trong phòng bên trong').\n"
    "\n"
    "=== B. THỰC THỂ & DANH XƯNG ===\n"
    "B1. THỰC THỂ TRONG BẢNG: BẮT BUỘC dùng đúng 100% từ đã chuẩn hóa trong bảng tham khảo.\n"
    "B2. THỰC THỂ MỚI: Bảng chỉ là tham khảo, không bao quát toàn bộ. LLM PHẢI chủ động nhận diện tên nhân vật, địa danh, môn phái mới và phiên âm Hán-Việt chuẩn. CẤM ép gán nhầm tên mới vào tên cũ trong bảng. CẤM dịch tên người thành nghĩa đen (VD: 白云 là tên người -> 'Bạch Vân', CẤM 'mây trắng').\n"
    "B3. XƯNG HÔ THEO THỂ LOẠI:\n"
    "   - CỔ PHONG: [Họ/Tên] + [Chức danh / Nghề nghiệp / Bối phận]: 'Kiều trưởng lão' (乔长老), 'Lý sư muội' (李师妹), 'Lý tiều phu' (李樵夫), 'Lâm đại phu' (林大夫), 'Tiêu tông chủ' (萧宗主). CẤM đảo thô: 'Trưởng lão Kiều', 'Tiều phu Lý'. Danh hiệu miêu tả dịch xuôi: 扫地僧 -> 'Tăng quét rác' (CẤM: 'quét rác tăng').\n"
    "   - HIỆN ĐẠI: Thân tộc TRƯỚC tên: 'Chú Vương' (王叔), 'Dì Lý' (李阿姨). Chức vụ/Vai vế SAU tên: 'Vương tổng' (王总), 'Lý giám đốc' (李经理), 'Nguyên ca' (源哥).\n"
    "B4. VÕ CÔNG, CHIÊU THỨC, BÍ TỊCH, DƯỢC LIỆU & ĐẠO CỤ (CHUẨN HÁN-VIỆT VÕ HIỆP / THUẦN VIỆT DỄ HIỂU):\n"
    "   - Phiên âm Hán-Việt chuẩn phong vị kiếm hiệp hoặc thuần Việt giàu hình tượng, TUYỆT ĐỐI CẤM dịch nghĩa đen ngô nghê từng chữ (Ví dụ: CẤM 'Huyết Lùn Lật' -> PHẢI dịch là 'Huyết Nham Lật' / 'Huyết Lật' / 'Hạt dẻ đỏ').\n"
    "   - Với các sự vật đời thường/danh từ chung: Ưu tiên dịch nghĩa tiếng Việt thuần túy, dễ hiểu thay vì gượng ép ghép âm Hán-Việt tối nghĩa.\n"
    "   - Chuẩn hóa hậu tố võ học: 拳 -> 'Quyền' (CẤM 'đấm'), 掌 -> 'Chưởng' (CẤM 'lòng bàn tay'), 指 -> 'Chỉ', 爪/抓 -> 'Trảo' (CẤM 'móng/bắt'), 腿 -> 'Cước', 剑/刀/枪/棍/杖/鞭 -> 'Kiếm / Đao / Thương / Côn / Trượng / Tiên'. 阵/圈 -> 'Trận / Quyển' (金刚伏魔圈 -> 'Kim Cương Phục Ma Trận / Quyển', CẤM: 'Kim Cương Phục Ma Khuyên'). 功/神功 -> 'Công / Thần Công', 经/真经 -> 'Kinh / Chân Kinh', 诀/决 -> 'Quyết', 谱/秘籍/宝典 -> 'Phổ / Bí Tịch / Bảo Điển', 步/身法 -> 'Bộ / Thân Pháp' (Lăng Ba Vi Bộ).\n"
    "B5. QUY TẮC XƯNG HÔ:\n"
    "   - NỀN TẢNG CỔ PHONG: 'ta - ngươi' là xưng hô cơ bản và tự nhiên cho giao tiếp thông thường, đối đầu, người lạ, hoặc khi bề trên nói với bề dưới (huynh với đệ, tẩu tẩu với thúc...). Tránh gượng ép máy móc như 'ta - đệ', 'ta - tiểu thúc'. Giữ ổn định ngôi xưng, không tự ý nhảy qua lại.\n"
    "   - XƯNG HÔ THEO QUAN HỆ: Khi có quan hệ rõ ràng, xưng hô tự nhiên theo bối cảnh (Huynh - Muội, Sư phụ - Đồ nhi, Phu quân / Chàng - Nương tử / Nàng, Phụ thân - Con). CẤM bề trên gọi bề dưới là 'huynh'.\n"
    "   - CẤM TỪ HIỆN ĐẠI: CẤM 'bạn / bạn bè' (dùng 'bằng hữu / đạo hữu'), CẤM 'ông ấy / anh ấy / cô ấy' (nhắc người khác dùng 'hắn / y / nàng / chàng'). '死道友不死贫道' -> 'chết đạo hữu không chết bần đạo'.\n"
    "   - CẤM DỊCH 'BỐ GIÀ' / 'MẸ GIÀ': '老娘' -> 'mẹ/mẫu thân', '老爹' -> 'cha/bố/phụ thân'.\n"
    "B6. TỔ CHỨC & ĐỊA DANH (DANH TỪ RIÊNG — PHẢI VIẾT HOA, CẤM DỊCH NGHĨA ĐEN):\n"
    "   - TÊN TỔ CHỨC là danh từ riêng VIẾT HOA: 丐帮 -> 'Cái Bang' (CẤM: 'cái bang'), 明教 -> 'Minh Giáo', 天地会 -> 'Thiên Địa Hội', 日月神教 -> 'Nhật Nguyệt Thần Giáo', 全真教 -> 'Toàn Chân Giáo', 武当派 -> 'Võ Đang phái', 少林派 -> 'Thiếu Lâm phái', 峨眉派 -> 'Nga Mi phái', 华山派 -> 'Hoa Sơn phái', 逍遥派 -> 'Tiêu Dao phái'.\n"
    "   - HẬU TỐ TỔ CHỨC: 帮=Bang, 派=Phái, 教=Giáo, 宗=Tông, 门=Môn, 会=Hội, 盟=Minh, 阁=Các, 殿=Điện, 谷=Cốc, 堡=Bảo, 庄=Trang, 院=Viện. Khi gặp cụm [2-4 chữ Hán] + [hậu tố tổ chức] -> phiên âm Hán-Việt viết hoa.\n"
    "   - CHỨC DANH + TỔ CHỨC: 丐帮帮主 -> 'bang chủ Cái Bang' (CẤM: 'Cái Bang bang chủ'), 明教教主 -> 'giáo chủ Minh Giáo', 武当掌门 -> 'chưởng môn Võ Đang'.\n"
    "   - ĐỊA DANH: 少林寺 -> 'Thiếu Lâm Tự', 武当山 -> 'Võ Đang sơn', 华山 -> 'Hoa Sơn', 昆仑山 -> 'Côn Lôn sơn', 藏经阁 -> 'Tàng Kinh Các', 太和殿 -> 'Thái Hòa Điện', 冰火岛 -> 'Băng Hỏa Đảo'.\n"
    "\n"
    "=== C. VĂN PHONG & THÀNH NGỮ ===\n"
    "C1. BIẾN TẤU THOÁT HÁN & TRẬT TỰ TỰ NHIÊN TIẾNG VIỆT:\n"
    "   - HỎI DANH TÍNH: '不知姑娘芳名 / 不知姑娘贵姓' -> BẮT BUỘC dịch xuôi: 'không biết quý danh của cô nương' / 'danh tính cô nương'. TUYỆT ĐỐI CẤM dịch ngược kiểu Hán 'không biết cô nương quý danh'.\n"
    "   - TRẬT TỰ ĐỊNH NGỮ TIẾNG VIỆT (Danh từ trước, Định ngữ sau):\n"
    "     + '关门弟子' -> 'đệ tử quan môn' / 'đệ tử chân truyền cuối cùng' (TUYỆT ĐỐI CẤM: 'quan môn đệ tử').\n"
    "     + '入室弟子' -> 'đệ tử nhập thất' (CẤM: 'nhập thất đệ tử').\n"
    "     + '闭关弟子' -> 'đệ tử bế quan' (CẤM: 'bế quan đệ tử').\n"
    "     + '开山大弟子' -> 'đại đệ tử khai sơn' (CẤM: 'khai sơn đại đệ tử').\n"
    "   - Biến đổi kết cấu câu tự nhiên (VD: 'vác kiếm đi dọc suốt đường đi, có người quen cũng có người lạ' -> 'vác kiếm rảo bước dọc đường, gặp cả người quen lẫn kẻ lạ').\n"
    "   - NGUYÊN TẮC VÀNG CHO CÂU MIÊU TẢ & KỂ CHUYỆN THÔNG THƯỜNG: Ở các câu miêu tả ngoại hình, cảnh vật, hành động, cảm xúc — được phép và NÊN diễn đạt uyển chuyển theo văn phong tiểu thuyết Việt (CÁC QUY TẮC CẤM chỉ áp dụng cho thuật ngữ, tên riêng, xưng hô, cảnh giới). Ví dụ:\n"
    "     + 瘦小的身躯 -> 'thân hình gầy gò' / 'tấm thân nhỏ bé' (CẤM dịch thô: 'cái xác gầy nhỏ', 'bản thân cái xác gầy nhỏ').\n"
    "     + 一双明亮的眼睛 -> 'đôi mắt sáng ngời' (CẤM: 'một đôi con mắt sáng').\n"
    "     + 他的心里很不舒服 -> 'trong lòng hắn khó chịu vô cùng' (CẤM: 'bên trong tâm lý của hắn rất không thoải mái').\n"
    "     + 用尽了全身的力气 -> 'dồn hết sức bình sinh' / 'rướn toàn bộ sức lực' (CẤM: 'dùng hết lực lượng toàn thân').\n"
    "     + 她的脸上露出了笑容 -> 'nàng nở nụ cười' / 'gương mặt nàng rạng rỡ' (CẤM: 'trên mặt cô ấy lộ ra nụ cười').\n"
    "     + 一个长得很好看的女人 -> 'một mỹ nhân xinh đẹp' / 'một người phụ nữ tuyệt sắc' (CẤM: 'một cái mọc rất đẹp đẽ nữ nhân').\n"
    "     + 他转过身 -> 'hắn quay người lại' (CẤM: 'hắn xoay chuyển thân thể').\n"
    "     + 他跑得很快 -> 'hắn lao đi như gió' / 'hắn chạy nhanh như bay' (CẤM: 'hắn chạy được rất nhanh').\n"
    "   - TÓM LẠI: Với thuật ngữ, tên riêng, cảnh giới, xưng hô → PHẢI tuân thủ quy tắc cứng ở các mục A, B. Với câu miêu tả, kể chuyện, đối thoại thông thường → NÊN viết lại cho mượt mà, giàu hình ảnh, đúng văn phong tiểu thuyết Việt. Câu dịch hay = đúng nghĩa gốc + đọc lên nghe thuận tai tiếng Việt.\n"
    "C2. CHUẨN CHÍNH TẢ & TỐI ƯU CHO GIỌNG ĐỌC TTS EDGE (BẮT BUỘC):\n"
    "   - TUYỆT ĐỐI VIẾT ĐÚNG 100% CHÍNH TẢ PHỔ THÔNG TIẾNG VIỆT, đúng dấu thanh. CẤM lỗi sai dấu, lỗi đánh máy, lỗi dính chữ thiếu khoảng trắng (CẤM: 'hắnquay', 'nàngnhìn' -> PHẢI: 'hắn quay', 'nàng nhìn').\n"
    "   - CẤM VIẾT TẮT, CẤM TEENCODE: Cấm viết 'k', 'đc', 'vs', 'j', 'ko', 'bt' -> BẮT BUỘC viết đầy đủ: 'không', 'được', 'với', 'gì', 'biết'.\n"
    "   - CẤM TỪ ĐỊA PHƯƠNG LỆCH CHUẨN: Cấm 'chợ giời', 'trển', 'trỏng' -> Dùng 'khu chợ', 'trên', 'trong'.\n"
    "   - NGẮT NGHỈ BẰNG DẤU PHẨY HỢP LÝ CHO TTS EDGE (BẮT BUỘC):\n"
    "     + Chủ động thêm dấu phẩy ',' ngắt các vế câu dài, sau trạng từ/trạng ngữ chỉ thời gian, địa điểm, tâm trạng, và giữa các hành động liên tiếp để tạo nhịp thở tự nhiên (~200ms) cho giọng đọc AI Edge-TTS.\n"
    "     + Tránh câu văn dài lê thê không có dấu ngắt khiến giọng đọc TTS bị dồn dập, hụt hơi hoặc nuốt chữ.\n"
    "   - BỎ DẤU NGOẶC KÉP TRONG CÂU VĂN XUÔI (BẮT BUỘC):\n"
    "     + TUYỆT ĐỐI KHÔNG dùng dấu ngoặc kép \"\" hoặc “” bao quanh các danh từ, thuật ngữ, tên sự kiện, chiêu thức, kỹ năng, suy nghĩ nằm TRONG câu văn xuôi (Ví dụ CẤM: 'đối phó với \"Phong Vân Tranh Bá\"', 'nhận được \"Hệ thống bị động\"', 'lý do để \"đăng xuất\"', 'kỹ năng \"Pháp hô hấp\"' -> PHẢI VIẾT: 'đối phó với Phong Vân Tranh Bá', 'nhận được Hệ thống bị động', 'lý do để đăng xuất', 'kỹ năng Pháp hô hấp').\n"
    "     + CHỈ dùng dấu ngoặc kép khi là lời thoại đối thoại trực tiếp độc lập giữa các nhân vật.\n"
    "   - TRÁNH CÁC KIỂU VIẾT KHIẾN TTS EDGE KHÓ ĐỌC / ĐỌC SAI ÂM:\n"
    "     + LẮP BẮP: CẤM viết kiểu cộc lốc tiếng Anh như 'k-không', 'c-con', 't-tôi', 'đ-được' (khiến Edge-TTS đọc từng chữ cái tiếng Anh 'kây', 'xi'...). BẮT BUỘC viết từ trọn vẹn: 'Không... không', 'Con... con', 'Tôi... tôi'.\n"
    "     + KÝ TỰ LẠ & BIỂU TƯỢNG: CẤM chèn các ký tự trang trí '~', '^', '*', '#', '★', '◆' vào giữa câu chữ khiến TTS đọc thành 'dấu ngã', 'dấu hoa thị' hoặc ngắc ngứ vấp giọng.\n"
    "     + SỐ VÀ ĐƠN VỊ: Viết rõ nghĩa bằng chữ thay vì ký hiệu toán học/viết tắt khó hiểu ('phần trăm' thay vì '%', 'cấp 5' thay vì 'Lv.5', 'lớn hơn' thay vì '>').\n"
    "C3. KHÔNG QUÁ VIỆT HÓA: Giữ nguyên phong vị và thuật ngữ đặc trưng thể loại (Linh Sự Các, Chấp sự, Sư tôn, Tông chủ...). CẤM dùng từ lóng đời thường hiện đại làm mất chất truyện.\n"
    "C4. THÀNH NGỮ — đối chiếu Trung-Việt, CẤM dịch thô: '隔墙有耳' -> 'tai vách mạch rừng'. '班门弄斧' -> 'múa rìu qua mắt thợ'. '趁火打劫' -> 'đục nước béo cò'. '凑数' -> 'qua loa cho có lệ' (CẤM: 'cho có tụ').\n"
    "C5. ĐỐI THOẠI, PHẢN ỨNG NGẮN & CẢM THÁN (NGẮN GỌN + TỰ NHIÊN + ĐÚNG LỰC):\n"
    "   - Phản ứng ngắn: 我靠/卧槽 -> 'Vãi! / Ôi đệt!', 完了 -> 'Toang rồi', 糟了/坏了 -> 'Chết rồi!', 真的假的 -> 'Thật hay đùa vậy?', 不会吧 -> 'Không phải chứ?', 真服了 -> 'Bó tay thật', 无语 -> 'Cạn lời', 怎么回事/什么情况 -> 'Chuyện gì vậy? / Gì vậy?'. CẤM tự kéo dài câu.\n"
    "   - Lóng & câu hài (giữ độ duyên, không dịch chết chữ): 戴绿帽子 -> 'đội nón xanh', 翻车 -> 'lật xe/toang', 打脸 -> 'vả mặt', 吃瓜 -> 'hóng chuyện/drama', 扎心 -> 'đau lòng thật', 牛逼 -> 'bá thật/đỉnh vãi', 他整个人都傻了 -> 'Hắn đơ luôn', 这波血亏 -> 'Pha này lỗ nặng'.\n"
    "   - Câu chửi & độc thoại: Giữ đúng lực cảm xúc tương đương (妈的/操 -> 'Mẹ kiếp! / Đệt!', 傻逼 -> 'Đồ ngu! / Thằng chó!'). CẤM thêm chữ thừa ('Hắn thầm nghĩ rằng...').\n"
    "   - CÔNG THỨC: Đúng nghĩa + Ngắn + Khẩu ngữ chuẩn + Đúng độ hài/lực − Chữ thừa.\n"
    "\n"
    "=== D. DỊCH ĐẦY ĐỦ & BẢO TOÀN ===\n"
    "D1. Dịch đầy đủ 100% nội dung, không cắt xén, không tóm tắt. TUYỆT ĐỐI CẤM để sót chữ Hán trong bản dịch (trừ thẻ §...§). CẤM giữ chữ Hán rồi mở ngoặc giải nghĩa (CẤM: '玲珑有致 (tinh xảo)' -> PHẢI dịch thẳng 'Linh Lung Hữu Trí' hoặc 'thon thả', CẤM: '登门造访 (đến thăm)' -> dịch thẳng 'đến thăm', CẤM: '舍下 (nhà ta)' -> dịch thẳng 'tệ xá'). CẤM dính chữ Hán vào từ tiếng Việt.\n"
    "D2. BẢO TOÀN THẺ MARKUP: Giữ nguyên 100% mã thẻ §PREFIX_XXXX§ đúng vị trí ngữ pháp. CHỈ khi câu có thẻ §...§: CẤM chêm từ đồng nghĩa NGAY SÁT CẠNH thẻ đó ('thân xác §THẺ§', 'người vợ §THẺ§') vì gây lặp khi giải mã. Ở các câu KHÔNG có thẻ §...§: được TỰ DO diễn đạt uyển chuyển bình thường.\n"
    "D3. TỪ KHÓ / TỐI NGHĨA: Nếu không chắc chắn, phiên âm Hán-Việt chuẩn xác nhất để bảo toàn cấu trúc.\n"
    "D4. GIỮ NGUYÊN Ý TÁC GIẢ: Truyền tải trọn vẹn diễn biến. Được phép trau chuốt từ ngữ, CẤM bịa thêm tình tiết, CẤM chèn câu hỏi tu từ thừa ('...không đau đớn ư?', 'sao?').\n"
    "D5. THUẬT NGỮ TU TIÊN: Giữ nguyên Khí Hải, Đan Điền, Thần Thức, Pháp Bảo, Công Pháp, Linh Khí, Độ Kiếp, Phá Cảnh, Bình Cảnh (CẤM nhầm thành 'bình phong'), Quán Chú...\n"
    "\n"
    "=== E. TỪ TƯỢNG THANH & CẢM XÚC ===\n"
    "CẤM xóa bỏ / cắt cụt từ tượng thanh, tiếng cười khóc rên rỉ. BẮT BUỘC chuẩn hóa sang tiếng Việt tự nhiên:\n"
    "   - 啊啊/啊啊啊 -> 'Á á!' / 'A a a!'. 哈哈 -> 'Ha ha!', 嘻嘻 -> 'Hi hi!', 哼 -> 'Hừ!'\n"
    "   - 呜呜 -> 'Hu hu!'. 嗯嗯/唔 -> 'Ư ư...', 'Ừm ừm...'\n"
    "   - Lắp bắp: '不...不要' -> 'Không... không được!' (CẤM viết 'k-không', 'c-con' — phải viết 'Con... con', 'Mẹ... mẹ').\n"
    "   - Giữ trọn cảm xúc nhân vật, CẤM viết chuỗi lặp vô nghĩa (>10 chữ lặp).\n"
    "\n"
    "=== F. DẤU CÂU & ĐỊNH DẠNG ===\n"
    "F1. CHẤM CÂU DỨT KHOÁT: Hết ý/hết sự việc -> dùng dấu chấm '.'. CẤM lạm dụng dấu phẩy ',' nối dài dằng dặc cả đoạn theo văn phong Hán khiến TTS hụt hơi.\n"
    "F2. DẤU PHẨY đúng vị trí: Ngắt vế câu sau trạng ngữ, giữa vế câu ghép, giữa liệt kê theo ngữ pháp Việt.\n"
    "F3. CẤM chuỗi dấu lộn xộn: '!?!?', '??!!', ',,,,', '....', '~~~', '— — —'.\n"
    "F4. CẤM ký hiệu trang trí ('★', '◆', '※', '^', '~', ngoặc vuông lạ). Viết thẳng câu văn xuôi. Viết đầy đủ viết tắt (EXP -> điểm kinh nghiệm, HP -> lượng máu, Lv -> cấp độ).\n"
    "F5. GIỮ MẠCH ĐOẠN VĂN: Ghép câu miêu tả liên tục thành đoạn hoàn chỉnh. CẤM xuống dòng sau từng câu đơn lẻ.\n"
    "\n"
    "=== G. DỌN RÁC ===\n"
    "G1. Giữ nguyên dòng 'Hết chương' ở cuối mỗi chương. Loại bỏ ghi chú tác giả ngoài lề, quảng cáo.\n"
    "G2. Xóa sạch watermark trang web Trung Quốc ('Mì nấm phải thêm trứng', '15619 Chữ', số từ...).\n"
    "\n"
    "=== H. ĐỐI SOÁT TỰ KIỂM & BẢO TOÀN TỪ NGHĨA CHÍNH XÁC (CROSS-CHECK & VERIFICATION) ===\n"
    "H1. ĐỐI SOÁT TỪNG CÂU VỚI VĂN BẢN GỐC (BẮT BUỘC): Sau khi dịch xong mỗi câu/đoạn, PHẢI tự động đối chiếu lại từng câu với bản gốc tiếng Trung để đảm bảo TUYỆT ĐỐI KHÔNG SAI TỪ, KHÔNG SAI SỐ LƯỢNG, KHÔNG LẪN LỘN SỐ ĐẾM/CẢNH GIỚI VÀ KHÔNG LÀM SAI LỆCH Ý NGHĨA.\n"
    "H2. BẢO VỆ CON SỐ & ĐẲNG CẤP/CẢNH GIỚI (CẤM NHẦM LẪN SỐ TRONG CÙNG CÂU):\n"
    "   - TUYỆT ĐỐI CẤM bị lẫn lộn giữa các con số khác nhau trong cùng một câu (Ví dụ gốc: '十境炼灵才修炼到三境' -> BẮT BUỘC DỊCH ĐÚNG 'thập cảnh Luyện Linh mà mới tu luyện đến tam cảnh' hoặc 'mười cảnh Luyện Linh mới tu luyện đến tam cảnh', TUYỆT ĐỐI CẤM dịch ngáo lặp số thành 'Luyện Linh tam cảnh mà mới tu luyện đến tam cảnh').\n"
    "   - Bảng số đối chiếu chuẩn: 一 (nhất/1), 二/两 (nhị/hai/2), 三 (tam/3), 四 (tứ/4), 五 (ngũ/5), 六 (lục/6), 七 (thất/7), 八 (bát/8), 九 (cửu/9), 十 (thập/10), 百 (bách/trăm), 千 (thiên/nghìn), 万 (vạn/mười nghìn).\n"
    "H3. BẢO TOÀN NGHĨA VÀ LOGIC NGUYÊN TÁC: CẤM bịa thêm/bỏ bớt tình tiết, CẤM sai lệch logic nhân quả, số đếm, quan hệ nhân vật. Nhưng ĐƯỢC PHÉP VÀ NÊN diễn đạt lại câu văn cho mượt mà, tự nhiên theo tiếng Việt — miễn là giữ đúng 100% ý nghĩa gốc. Dịch hay ≠ dịch sát từng chữ."
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
    """Trả về chuỗi JSON và Common Rules để nhúng vào Prompt cho luồng Dịch RAW (RAWT)"""
    normalized_key = normalize_profile_key(profile_key)
    profile = CONTEXT_PROFILES.get(normalized_key)
    if not profile:
        return ""
        
    return f"=== CẤU HÌNH BỐI CẢNH & XƯNG HÔ ({normalized_key.upper()}) ===\n{profile['description']}\n\n=== QUY TẮC DỊCH THUẬT TIẾNG VIỆT BẮT BUỘC ===\n{COMMON_RULES}"

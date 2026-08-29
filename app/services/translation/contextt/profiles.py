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
        "- Đại từ cấm: TUYỆT ĐỐI KHÔNG để sót các đại từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô', 'ông ấy', 'anh ấy', 'cô ấy', 'bạn bè') trong cả lời dẫn và lời thoại.\n"
        "- Lời kể chuyện ngôi thứ ba: Sửa thành 'hắn', 'nàng', 'y', 'gã', 'ông', 'lão', 'tiểu tử'... CẤM dùng 'ông ấy', 'anh ấy', 'cô ấy'.\n"
        "- XƯNG HÔ NỀN TẢNG & TỰ NHIÊN:\n"
        "  + 'ta - ngươi' là cặp đại từ cơ bản và tự nhiên nhất trong cổ phong (dùng cho ngang hàng, đối thoại thông thường, người lạ, hoặc khi bề trên nói với bề dưới như huynh nói với đệ, tẩu tẩu nói với thúc). Dùng 'ta - ngươi' cho gọn và tự nhiên, không cần gượng ép xưng 'ta - đệ' hay 'ta - tiểu thúc'.\n"
        "  + CẤM 'bạn / bạn bè' trong cổ phong: PHẢI dùng 'bằng hữu / đạo hữu / tri kỷ'. '死道友不死贫道' -> 'chết đạo hữu không chết bần đạo' (CẤM: 'chết bạn chứ không chết mình').\n"
        "- XƯNG HÔ THEO QUAN HỆ (dùng đúng vai vế một cách tự nhiên, KHÔNG máy móc ép buộc): 'ta - ngươi', 'đệ tử - sư tôn / sư phụ', 'sư huynh - sư đệ', 'huynh - muội', 'tiền bối - vãn bối', 'phu quân / chàng - nương tử / nàng'. CẤM bề trên gọi bề dưới là 'huynh'."
    )
}

WUXIA_PROFILE = {
    "description": (
        "- Bối cảnh: Kiếm hiệp, võ lâm, giang hồ truyền thống.\n"
        "- Đại từ cấm: TUYỆT ĐỐI KHÔNG để sót các đại từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô', 'ông ấy', 'anh ấy', 'cô ấy') trong cả lời dẫn và lời thoại.\n"
        "- Lời kể ngôi thứ ba: Sửa thành 'hắn', 'y', 'gã', 'nàng', 'lão', 'hiệp khách'... CẤM dùng 'ông ấy', 'anh ấy', 'cô ấy'.\n"
        "- XƯNG HÔ MẶC ĐỊNH XUYÊN SUỐT: 我 = 'ta', 你 = 'ngươi', 他 = 'hắn/y', 她 = 'nàng/ả'. Giữ ổn định, KHÔNG thay đổi theo tình huống. CẤM dùng 'ông ấy', 'anh ấy', 'cô ấy', 'anh', 'em'.\n"
        "- Xưng hô quan hệ (giữ nhất quán): 'ta - ngươi', 'huynh - đệ', 'tỷ - muội', 'đại hiệp - các hạ', 'tiểu đệ', 'tiền bối - vãn bối', 'chưởng môn', 'minh chủ'. Nhắc người khác ở ngôi thứ ba: 'hắn/y/nàng' (CẤM: 'ông ấy', 'anh ấy')."
    )
}

COMMON_RULES = (
    "=== A. TRẬT TỰ CỤM TỪ HÁN -> VIỆT (BẮT BUỘC SỬA) ===\n"
    "A1. THỜI GIAN: 三更半夜 -> 'nửa đêm canh ba' (CẤM: 'canh ba nửa đêm'). 三更时分 -> 'lúc canh ba'. 清晨时分 -> 'lúc sáng sớm'.\n"
    "A2. [Họ/Tên] + [Chức danh / Nghề nghiệp / Bối phận] -- CẤM đảo ngược: 乔长老 -> 'Kiều trưởng lão' (CẤM: 'Trưởng lão Kiều'), 李师妹 -> 'Lý sư muội', 李樵夫 -> 'Lý tiều phu' (CẤM: 'Tiều phu Lý'), 林大夫 -> 'Lâm đại phu', 王掌柜 -> 'Vương chưởng quầy', 张掌门 -> 'Trương chưởng môn'. Tiền tố/xưng hô thân mật: 'Tiểu Uy' (小威), 'Lão Vương' (老王), 徐大哥 -> 'Từ đại ca' / 'Đại ca Từ'.\n"
    "A3. [Chức danh] + [Tổ chức] -- CẤM đảo ngược: 明教教主 -> 'giáo chủ Minh Giáo' (CẤM: 'Minh Giáo giáo chủ'). 武当掌门 -> 'chưởng môn Võ Đang', 丐帮帮主 -> 'bang chủ Cái Bang'.\n"
    "A4. DANH HIỆU / VAI TRÒ MIÊU TẢ -- dịch xuôi danh từ chính + định ngữ: 扫地僧 -> 'Tăng quét rác' / 'Tảo Địa Tăng' (TUYỆT ĐỐI CẤM: 'quét rác tăng'). 打铁匠 -> 'thợ rèn' (CẤM: 'đánh sắt thợ'), 赶车夫 -> 'phu xe / người đánh xe'.\n"
    "A5. [Kiến trúc] + [Địa điểm]: 皇宫大门 -> 'cổng lớn hoàng cung' (CẤM: 'hoàng cung cửa lớn'). 客栈二楼 -> 'tầng hai khách điếm'.\n"
    "A6. SỐ LƯỢNG -- bỏ lượng từ thừa: 两名弟子 -> 'hai đệ tử' (CẤM: 'hai danh đệ tử'). 三位长老 -> 'ba vị trưởng lão'.\n"
    "A7. [Tính chất] + [Vật phẩm] -- giữ nguyên cấu trúc Hán-Việt: 神剑 -> 'thần kiếm' (CẤM: 'kiếm thần'). 宝剑 -> 'bảo kiếm', 灵丹 -> 'linh đan', 法宝 -> 'pháp bảo'.\n"
    "A8. ĐỊA VỊ / BỐI PHẬN -- giữ thuật ngữ Hán-Việt: 大师兄 -> 'đại sư huynh', 大长老 -> 'đại trưởng lão', 核心弟子 -> 'đệ tử hạch tâm', 内门弟子 -> 'đệ tử nội môn'.\n"
    "A9. CẢNH GIỚI TU TIÊN (BẮT BUỘC SỬA TRIỆT ĐỂ LỖI GG 'CẢNH GIỚI THỨ X'):\n"
    "   - SỐ ĐỘC LẬP / CẢNH ĐỨNG RIÊNG: 三境 -> 'tam cảnh' (TUYỆT ĐỐI CẤM: 'cảnh giới thứ ba', 'thứ ba'). 四境 -> 'tứ cảnh' (CẤM: 'cảnh giới thứ tư'). 五境 -> 'ngũ cảnh' (CẤM: 'cảnh giới thứ năm'). 六境 -> 'lục cảnh', 七境 -> 'thất cảnh', 八境 -> 'bát cảnh', 九境 -> 'cửu cảnh', 十境 -> 'thập cảnh' (CẤM: 'mười cảnh').\n"
    "   - TÊN GHÉP: 炼灵三境 -> 'Luyện Linh tam cảnh' (TUYỆT ĐỐI CẤM: 'Luyện Linh cảnh giới thứ ba'). 炼灵四境 -> 'Luyện Linh tứ cảnh'. 炼灵五境 -> 'Luyện Linh ngũ cảnh'. 炼灵八境 -> 'Luyện Linh bát cảnh'. 十境炼灵 -> 'thập cảnh Luyện Linh' (CẤM: 'mười cảnh luyện linh').\n"
    "   - ĐỘNG TỪ + CẢNH GIỚI: 突破三境 -> 'đột phá tam cảnh' (CẤM: 'đột phá cảnh giới thứ ba'). 突破四境 -> 'đột phá tứ cảnh'. 突破五境 -> 'đột phá ngũ cảnh'. 达到七境 -> 'đạt tới thất cảnh'.\n"
    "   - TRỌNG (重) / TẦNG (层): 炼气一重 -> 'Luyện Khí nhất trọng' (CẤM: 'Luyện Khí lớp 1/tầng 1'). 炼气九重 -> 'Luyện Khí cửu trọng'. 金丹三层 -> 'Kim Đan tam tầng'. 一重/二重/三重 -> 'nhất trọng / nhị trọng / tam trọng'.\n"
    "   - KỲ (期) & PHÂN KỲ: 炼气期 -> 'Luyện Khí kỳ'. 筑基初期 -> 'Trúc Cơ sơ kỳ'. 筑基中期 -> 'Trúc Cơ trung kỳ'. 筑基后期 -> 'Trúc Cơ hậu kỳ' (CẤM: 'giai đoạn cuối xây dựng nền tảng'). 化神巅峰 -> 'Hóa Thần đỉnh phong'. 炼灵巅峰 -> 'Luyện Linh đỉnh phong'.\n"
    "   - BẢNG SỐ HÁN-VIỆT BẮT BUỘC: 一=Nhất, 二=Nhị, 三=Tam, 四=Tứ, 五=Ngũ, 六=Lục, 七=Thất, 八=Bát, 九=Cửu, 十=Thập. CẤM: 'thứ ba', 'thứ 4', 'thứ năm', 'thứ 5'. PHẢI: 'tam cảnh', 'tứ cảnh', 'ngũ cảnh', 'lục cảnh'.\n"
    "A10. SỞ HỮU: Xưng hô trực tiếp: 张师兄 -> 'Trương sư huynh'. Sở hữu: 我师兄 -> 'sư huynh của ta' (CẤM: 'ta sư huynh'). Chữ '的' dịch linh hoạt: 天剑宗的弟子 -> 'đệ tử Thiên Kiếm Tông' (bỏ 'của' nếu gọn hơn).\n"
    "A11. CỤM CỐ ĐỊNH: 江湖 -> 'giang hồ', 武林 -> 'võ lâm', 天下 -> 'thiên hạ', 修仙界 -> 'giới tu tiên', 仙界/魔界/妖界 -> 'Tiên Giới / Ma Giới / Yêu Giới'.\n"
    "A12. PHƯƠNG HƯỚNG -- thuần Việt: 在他的身后 -> 'ở phía sau hắn' (CẤM: 'ở hắn sau lưng'). 在房间里面 -> 'trong phòng' (CẤM: 'ở trong phòng bên trong').\n"
    "\n"
    "=== B. THỰC THỂ & DANH XƯNG ===\n"
    "B1. THỰC THỂ TRONG BẢNG: BẮT BUỘC dùng đúng 100% từ đã chuẩn hóa trong bảng tham khảo.\n"
    "B2. THỰC THỂ MỚI: Bảng chỉ là tham khảo. Chủ động nhận diện tên nhân vật, địa danh, môn phái, chiêu thức mới và biên tập/dịch theo âm Hán-Việt chuẩn. CẤM ép gán nhầm tên mới vào tên cũ. CẤM dịch tên người thành nghĩa đen.\n"
    "B3. XƯNG HÔ THEO THỂ LOẠI:\n"
    "   - CỔ PHONG: [Họ/Tên] + [Chức danh / Nghề nghiệp / Bối phận]: 'Kiều trưởng lão' (乔长老), 'Lý sư muội' (李师妹), 'Lý tiều phu' (李樵夫), 'Lâm đại phu' (林大夫), 'Tiêu tông chủ' (萧宗主). CẤM đảo thô: 'Trưởng lão Kiều', 'Tiều phu Lý'. Danh hiệu miêu tả dịch xuôi: 扫地僧 -> 'Tăng quét rác' (CẤM: 'quét rác tăng').\n"
    "   - HIỆN ĐẠI: Thân tộc TRƯỚC tên: 'Chú Vương' (王叔). Chức vụ/Vai vế SAU tên: 'Vương tổng' (王总), 'Nguyên ca' (源哥).\n"
    "B4. VÕ CÔNG, CHIÊU THỨC, BÍ TỊCH, DƯỢC LIỆU & ĐẠO CỤ (CHUẨN HÁN-VIỆT VÕ HIỆP / THUẦN VIỆT DỄ HIỂU):\n"
    "   - Phiên âm Hán-Việt chuẩn phong vị kiếm hiệp hoặc thuần Việt giàu hình tượng, TUYỆT ĐỐI CẤM dịch nghĩa đen ngô nghê từng chữ (Ví dụ: CẤM 'Huyết Lùn Lật' -> PHẢI dịch là 'Huyết Nham Lật' / 'Huyết Lật' / 'Hạt dẻ đỏ').\n"
    "   - Với các sự vật đời thường/danh từ chung: Ưu tiên dịch nghĩa tiếng Việt thuần túy, dễ hiểu thay vì gượng ép ghép âm Hán-Việt tối nghĩa.\n"
    "B5. QUY TẮC XƯNG HÔ:\n"
    "   - NỀN TẢNG CỔ PHONG: 'ta - ngươi' là xưng hô cơ bản và tự nhiên cho giao tiếp thông thường, đối đầu, người lạ, hoặc khi bề trên nói với bề dưới (huynh với đệ, tẩu tẩu với thúc...). Tránh gượng ép máy móc như 'ta - đệ', 'ta - tiểu thúc'. Giữ ổn định ngôi xưng, không tự ý nhảy qua lại.\n"
    "   - XƯNG HÔ THEO QUAN HỆ: Khi có quan hệ rõ ràng, xưng hô tự nhiên theo bối cảnh (Huynh - Muội, Sư phụ - Đồ nhi, Phu quân / Chàng - Nương tử / Nàng, Phụ thân - Con). CẤM bề trên gọi bề dưới là 'huynh'.\n"
    "   - CẤM TỪ HIỆN ĐẠI: CẤM 'bạn / bạn bè' (dùng 'bằng hữu / đạo hữu'), CẤM 'ông ấy / anh ấy / cô ấy' (nhắc người khác dùng 'hắn / y / nàng / chàng'). '死道友不死贫道' -> 'chết đạo hữu không chết bần đạo'.\n"
    "   - CẤM DỊCH 'BỐ GIÀ' / 'MẸ GIÀ': '老娘' -> 'mẹ/mẫu thân', '老爹' -> 'cha/bố/phụ thân'.\n"
    "B6. TỔ CHỨC & ĐỊA DANH (DANH TỪ RIÊNG — PHẢI VIẾT HOA, CẤM DỊCH NGHĨA ĐEN):\n"
    "   - TÊN TỔ CHỨC là danh từ riêng VIẾT HOA: 丐帮 -> 'Cái Bang' (CẤM: 'cái bang'), 明教 -> 'Minh Giáo', 天地会 -> 'Thiên Địa Hội', 日月神教 -> 'Nhật Nguyệt Thần Giáo', 全真教 -> 'Toàn Chân Giáo', 武当派 -> 'Võ Đang phái', 少林派 -> 'Thiếu Lâm phái', 峨眉派 -> 'Nga Mi phái', 逍遥派 -> 'Tiêu Dao phái'.\n"
    "   - HẬU TỐ TỔ CHỨC: 帮=Bang, 派=Phái, 教=Giáo, 宗=Tông, 门=Môn, 会=Hội, 盟=Minh, 阁=Các, 殿=Điện, 谷=Cốc, 堡=Bảo, 庄=Trang, 院=Viện.\n"
    "   - CHỨC DANH + TỔ CHỨC: 丐帮帮主 -> 'bang chủ Cái Bang' (CẤM: 'Cái Bang bang chủ'), 明教教主 -> 'giáo chủ Minh Giáo', 武当掌门 -> 'chưởng môn Võ Đang'.\n"
    "   - ĐỊA DANH: 少林寺 -> 'Thiếu Lâm Tự', 武当山 -> 'Võ Đang sơn', 华山 -> 'Hoa Sơn', 藏经阁 -> 'Tàng Kinh Các', 太和殿 -> 'Thái Hòa Điện'.\n"
    "\n"
    "=== C. DỊCH TỪ XƯNG HÔ TIẾNG TRUNG CÒN SÓT (ĐẶC THÙ BIÊN TẬP) ===\n"
    "C1. Bản dịch thô có từ xưng hô/bối phận tiếng Trung còn nguyên gốc (他, 她, 你, 我, 妈妈, 师兄, 朕, 本王...). BẮT BUỘC dịch tất cả sang tiếng Việt chuẩn xác theo ngữ cảnh ai nói với ai.\n"
    "C2. '他'/'她' lời kể chuyện: 'hắn'/'y'/'gã'/'nàng' (cổ phong, CẤM 'ông ấy'/'anh ấy'/'cô ấy') hoặc 'anh ta'/'cô ấy' (hiện đại). '你'/'您': dịch đúng bối phận (mẹ->con: '你'='con'; đồ đệ->sư tôn: '您'='người'; ngang hàng cổ phong: 'ngươi').\n"
    "C3. '妈妈'/'母亲' = mẹ (CẤM dịch 'mẹ chồng'). '爸爸'/'父亲' = bố/cha. '师兄' = sư huynh, '师父' = sư phụ, '道友' = đạo hữu, '朕' = trẫm, '本王' = bản vương.\n"
    "C4. TUYỆT ĐỐI CẤM để sót bất kỳ ký tự tiếng Trung nào trong bản dịch cuối cùng -- phải 100% tiếng Việt. CẤM giữ chữ Hán rồi mở ngoặc giải nghĩa (CẤM: '玲珑有致 (tinh xảo)' -> PHẢI dịch thẳng 'Linh Lung Hữu Trí' hoặc 'thon thả', CẤM: '登门造访 (đến thăm)' -> dịch thẳng 'đến thăm', CẤM: '舍下 (nhà ta)' -> dịch thẳng 'tệ xá'). CẤM dính chữ Hán vào từ tiếng Việt.\n"
    "\n"
    "=== D. SỬA PINYIN, RÁC HÁN-VIỆT & CỤM SỞ HỮU (ĐẶC THÙ BIÊN TẬP) ===\n"
    "D1. SỬA PINYIN/TIẾNG ANH CÒN SÓT: 'Xiao Fan' -> 'Tiểu Phàm', 'Lin Chen' -> 'Lâm Thần'. CẤM để sót Pinyin/tiếng Anh.\n"
    "D2. XÓA RÁC HÁN-VIỆT: 'tôi Đích' -> 'của tôi', 'hắn Đích' -> 'của hắn'. Sửa triệt để: 'Thị' -> 'là', 'Cấp' -> 'cho', 'Chi' -> 'của/đó', 'của của' -> 'của'.\n"
    "D3. CỤM SỞ HỮU: '我的' -> 'của tôi', '她的' -> 'của nàng', '自己的' -> 'của mình', '妈妈的' -> 'của mẹ'.\n"
    "\n"
    "=== E. VĂN PHONG & TINH GỌN ===\n"
    "E1. BIẾN TẤU THOÁT HÁN & TRẬT TỰ TỰ NHIÊN TIẾNG VIỆT:\n"
    "   - HỎI DANH TÍNH: '不知姑娘芳名 / 不知姑娘贵姓' -> BẮT BUỘC dịch xuôi: 'không biết quý danh của cô nương' / 'danh tính cô nương'. TUYỆT ĐỐI CẤM dịch ngược kiểu Hán 'không biết cô nương quý danh'.\n"
    "   - TRẬT TỰ ĐỊNH NGỮ TIẾNG VIỆT (Danh từ trước, Định ngữ sau):\n"
    "     + '关门弟子' -> 'đệ tử quan môn' / 'đệ tử chân truyền cuối cùng' (TUYỆT ĐỐI CẤM: 'quan môn đệ tử').\n"
    "     + '入室弟子' -> 'đệ tử nhập thất' (CẤM: 'nhập thất đệ tử').\n"
    "     + '闭关弟子' -> 'đệ tử bế quan' (CẤM: 'bế quan đệ tử').\n"
    "     + '开山大弟子' -> 'đại đệ tử khai sơn' (CẤM: 'khai sơn đại đệ tử').\n"
    "   - Biến đổi kết cấu câu tự nhiên (VD: 'vác kiếm đi dọc suốt đường đi' -> 'vác kiếm rảo bước dọc đường').\n"
    "   - NGUYÊN TẮC VÀNG CHO CÂU MIÊU TẢ & KỂ CHUYỆN: Ở các câu miêu tả ngoại hình, cảnh vật, hành động, cảm xúc — NÊN viết lại uyển chuyển theo văn phong tiểu thuyết Việt (CÁC QUY TẮC CẤM chỉ áp dụng cho thuật ngữ, tên riêng, xưng hô, cảnh giới). Ví dụ:\n"
    "     + '瘦小的身躯' -> 'thân hình gầy gò' / 'tấm thân nhỏ bé' (CẤM dịch thô: 'cái xác gầy nhỏ').\n"
    "     + '一双明亮的眼睛' -> 'đôi mắt sáng ngời' (CẤM: 'một đôi con mắt sáng').\n"
    "     + '用尽了全身的力气' -> 'dồn hết sức bình sinh' (CẤM: 'dùng hết lực lượng toàn thân').\n"
    "     + '她的脸上露出了笑容' -> 'nàng nở nụ cười' (CẤM: 'trên mặt cô ấy lộ ra nụ cười').\n"
    "     + '他跑得很快' -> 'hắn lao đi như gió' (CẤM: 'hắn chạy được rất nhanh').\n"
    "   - TÓM LẠI: Thuật ngữ, tên riêng, cảnh giới → tuân thủ quy tắc cứng. Câu miêu tả, kể chuyện → viết lại cho mượt mà, đúng văn phong tiểu thuyết Việt.\n"
    "E2. VIỆT HÓA CÂU NGẮN & THÁN TỪ: Bổ sung trợ từ cho tự nhiên: '疼！' -> 'Đau quá!' (CẤM: 'Đau!'). '救命！' -> 'Cứu với!'. '闭嘴！' -> 'Im đi!' (CẤM: 'Đóng miệng!'). Tiết chế vừa đủ, CẤM lạm dụng khiến câu sến xẩm.\n"
    "E4. CHUẨN CHÍNH TẢ & TỐI ƯU CHO GIỌNG ĐỌC TTS EDGE (BẮT BUỘC):\n"
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
    "E6. THÀNH NGỮ -- đối chiếu Trung-Việt: '隔墙有耳' -> 'tai vách mạch rừng'. '班门弄斧' -> 'múa rìu qua mắt thợ'. CẤM dịch thô từng chữ.\n"
    "E7. Sửa triệt để rác Google Translate: bỏ 'đem...', 'đối với... mà nói', 'trong lòng có chút...', 'dưới một cái...', 'sau khi...'.\n"
    "E8. CẤM bịa thêm tình tiết, CẤM chèn câu hỏi tu từ ngoài văn bản gốc.\n"
    "E9. ĐỐI THOẠI, PHẢN ỨNG NGẮN & CẢM THÁN (NGẮN GỌN + TỰ NHIÊN + ĐÚNG LỰC):\n"
    "   - Phản ứng ngắn: 我靠/卧槽 -> 'Vãi! / Ôi đệt!', 完了 -> 'Toang rồi', 糟了/坏了 -> 'Chết rồi!', 真的假的 -> 'Thật hay đùa vậy?', 不会吧 -> 'Không phải chứ?', 真服了 -> 'Bó tay thật', 无语 -> 'Cạn lời', 怎么回事/什么情况 -> 'Chuyện gì vậy? / Gì vậy?'. CẤM tự kéo dài câu.\n"
    "   - Lóng & câu hài (giữ độ duyên, không dịch chết chữ): 戴绿帽子 -> 'đội nón xanh', 翻车 -> 'lật xe/toang', 打脸 -> 'vả mặt', 吃瓜 -> 'hóng chuyện/drama', 扎心 -> 'đau lòng thật', 牛逼 -> 'bá thật/đỉnh vãi', 他整个人都傻了 -> 'Hắn đơ luôn', 这波血亏 -> 'Pha này lỗ nặng'.\n"
    "   - Câu chửi & độc thoại: Giữ đúng lực cảm xúc tương đương (妈的/操 -> 'Mẹ kiếp! / Đệt!', 傻逼 -> 'Đồ ngu! / Thằng chó!'). CẤM thêm chữ thừa ('Hắn thầm nghĩ rằng...').\n"
    "   - CÔNG THỨC: Đúng nghĩa + Ngắn + Khẩu ngữ chuẩn + Đúng độ hài/lực − Chữ thừa.\n"
    "\n"
    "\n"
    "=== F. NHỊP DẪN CHUYỆN & ĐẠI TỪ 'Y' ===\n"
    "F1. NHỊP DẪN: Xen kẽ nhịp nhàng giữa 'y', 'hắn' và tên nhân vật để mạch văn không lặp ('hắn... hắn... hắn...'), cũng không hoán đổi giật cục.\n"
    "F2. KHOẢNG TRẮNG ĐẠI TỪ 'Y': BẮT BUỘC có dấu cách 2 phía (' y ', 'nhìn y', 'y đã'). CẤM viết dính ('yđã', 'ngườiy').\n"
    "F3. NHẤT QUÁN XƯNG HÔ: Xác định đúng AI nói VỚI AI. Xưng hô bối phận nhất quán theo cặp, CẤM đảo ngược.\n"
    "\n"
    "=== G. THUẬT NGỮ & BẢO TOÀN ===\n"
    "G1. SỐ ĐẾM & CẢNH GIỚI TU TIÊN: BẮT BUỘC 100% dùng số Hán-Việt (Nhất, Nhị, Tam, Tứ, Ngũ, Lục, Thất, Bát, Cửu, Thập). TUYỆT ĐỐI CẤM: 'thứ ba', 'thứ 4', 'cảnh giới thứ năm', 'cảnh giới thứ tám'. PHẢI SỬA THÀNH: 'tam cảnh', 'tứ cảnh', 'ngũ cảnh', 'lục cảnh', 'thất cảnh', 'bát cảnh', 'cửu cảnh', 'thập cảnh', 'Luyện Linh tam cảnh', 'Luyện Linh tứ cảnh', 'Luyện Linh ngũ cảnh', 'Luyện Khí nhất trọng'.\n"
    "G2. Giữ nguyên thuật ngữ tu tiên: Khí Hải, Thần Thức, Pháp Bảo, Công Pháp, Độ Kiếp, Phá Cảnh, Quán Chú...\n"
    "G3. Giữ nguyên 100% mã bảo vệ §PREFIX_XXXX§ nếu có (CHỈ CẤM chêm từ đồng nghĩa NGAY SÁT CẠNH thẻ §...§ để tránh lặp khi giải mã, CÒN LẠI được tự do diễn đạt uyển chuyển bình thường). Không thêm thắt tình tiết ngoài văn bản gốc.\n"
    "\n"
    "=== H. TỪ TƯỢNG THANH & CẢM XÚC ===\n"
    "CẤM xóa bỏ / cắt cụt từ tượng thanh, tiếng cười khóc rên rỉ. BẮT BUỘC chuẩn hóa sang tiếng Việt tự nhiên:\n"
    "   - 啊啊/啊啊啊 -> 'Á á!' / 'A a a!'. 哈哈 -> 'Ha ha!', 嘻嘻 -> 'Hi hi!', 哼 -> 'Hừ!'\n"
    "   - 呜呜 -> 'Hu hu!'. 嗯嗯/唔 -> 'Ư ư...', 'Ừm ừm...'\n"
    "   - Lắp bắp: '不...不要' -> 'Không... không được!' (CẤM viết 'k-không', 'c-con' -- phải viết 'Con... con').\n"
    "   - Giữ trọn cảm xúc nhân vật, CẤM chuỗi lặp vô nghĩa (>10 chữ lặp).\n"
    "\n"
    "=== I. DẤU CÂU & ĐỊNH DẠNG (TỐI ƯU CHO TTS AUDIOBOOK) ===\n"
    "I1. CHẤM CÂU DỨT KHOÁT: Hết ý/hết sự việc -> dấu chấm '.'. CẤM lạm dụng nối dài cả đoạn theo văn phong Hán khiến TTS hụt hơi.\n"
    "I2. THÊM DẤU PHẨY NGẮT NHỊP TỰ NHIÊN: Chủ động ngắt vế câu sau trạng ngữ, giữa các vế câu ghép, giữa các hành động nối tiếp và liệt kê để câu văn có nhịp thở ngắt nghỉ (~200ms) chuẩn mực cho giọng đọc TTS Edge.\n"
    "I3. KHÔNG DÙNG NGOẶC KÉP TRONG CÂU: Bỏ ngoặc kép \"\" quanh tên kỹ năng, danh từ, từ nhấn mạnh nằm trong câu văn xuôi. Chỉ giữ ngoặc kép cho câu đối thoại trực tiếp.\n"
    "I4. CẤM chuỗi dấu lộn xộn: '!?!?', '??!!', ',,,,', '....', '~~~'.\n"
    "I5. CẤM ký hiệu trang trí ('★', '◆', '※', '^', '~'). Viết thẳng câu văn xuôi. Viết đầy đủ viết tắt (EXP -> điểm kinh nghiệm, HP -> lượng máu).\n"
    "I6. GIỮ MẠCH ĐOẠN VĂN: Ghép câu miêu tả liên tục thành đoạn hoàn chỉnh. CẤM xuống dòng sau từng câu đơn lẻ.\n"
    "\n"
    "=== J. DỌN RÁC ===\n"
    "J1. Giữ nguyên dòng 'Hết chương' ở cuối mỗi chương. Loại bỏ ghi chú tác giả ngoài lề, quảng cáo.\n"
    "J2. Xóa sạch watermark trang web Trung Quốc ('Mì nấm phải thêm trứng', '15619 Chữ', số từ...).\n"
    "\n"
    "=== K. ĐỐI SOÁT TỰ KIỂM & BẢO TOÀN TỪ NGHĨA CHÍNH XÁC (CROSS-CHECK & VERIFICATION) ===\n"
    "K1. ĐỐI SOÁT TỪNG CÂU VỚI VĂN BẢN GỐC (BẮT BUỘC): Sau khi biên tập/dịch xong mỗi câu/đoạn, PHẢI tự động đối chiếu lại từng câu với văn bản gốc để đảm bảo TUYỆT ĐỐI KHÔNG SAI TỪ, KHÔNG SAI SỐ LƯỢNG, KHÔNG LẪN LỘN SỐ ĐẾM/CẢNH GIỚI VÀ KHÔNG LÀM SAI LỆCH Ý NGHĨA.\n"
    "K2. BẢO VỆ CON SỐ & ĐẲNG CẤP/CẢNH GIỚI (CẤM NHẦM LẪN SỐ TRONG CÙNG CÂU):\n"
    "   - TUYỆT ĐỐI CẤM bị lẫn lộn giữa các con số khác nhau trong cùng một câu (Ví dụ gốc: '十境炼灵才修炼到三境' -> BẮT BUỘC DỊCH ĐÚNG 'thập cảnh Luyện Linh mà mới tu luyện đến tam cảnh' hoặc 'mười cảnh Luyện Linh mới tu luyện đến tam cảnh', TUYỆT ĐỐI CẤM dịch ngáo lặp số thành 'Luyện Linh tam cảnh mà mới tu luyện đến tam cảnh').\n"
    "   - Bảng số đối chiếu chuẩn: 一 (nhất/1), 二/两 (nhị/hai/2), 三 (tam/3), 四 (tứ/4), 五 (ngũ/5), 六 (lục/6), 七 (thất/7), 八 (bát/8), 九 (cửu/9), 十 (thập/10), 百 (bách/trăm), 千 (thiên/nghìn), 万 (vạn/mười nghìn).\n"
    "K3. BẢO TOÀN NGHĨA VÀ LOGIC NGUYÊN TÁC: CẤM bịa thêm/bỏ bớt tình tiết, CẤM sai lệch logic nhân quả, số đếm, quan hệ nhân vật. Nhưng ĐƯỢC PHÉP VÀ NÊN diễn đạt lại câu văn cho mượt mà, tự nhiên theo tiếng Việt — miễn là giữ đúng 100% ý nghĩa gốc. Dịch hay ≠ dịch sát từng chữ."
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

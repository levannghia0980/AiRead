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
    "1. BẢO TỒN THỰC THỂ & DỊCH TỰ NHIÊN THEO NGỮ CẢNH — THUẦN HÓA TOÀN BỘ NGỮ PHÁP TIẾNG VIỆT:\n"
    "   - ĐỐI VỚI CÁC THỰC THỂ ĐÃ CÓ TRONG BẢNG THAM KHẢO (DICTIONARY MAPPING): Bạn BẮT BUỘC phải dùng ĐÚNG 100% từ đã chuẩn hóa trong bảng khi xuất hiện trong văn bản.\n"
    "   - ĐỐI VỚI TÊN NHÂN VẬT & THỰC THỂ MỚI CHƯA CÓ TRONG BẢNG: Bảng thực thể chỉ là danh sách tham khảo các từ đã biết, KHÔNG PHẢI danh sách duy nhất bao quát toàn bộ. BẮT BUỘC chủ động nhận diện tên nhân vật, chiêu thức, địa danh, môn phái theo ngữ cảnh và biên tập/dịch theo âm HÁN-VIỆT CHUẨN CỔ PHONG (Ví dụ: Từ Tiểu Thụ, Thiên Tang Linh Cung, Luyện Linh Cảnh, Hô Hấp Chi Pháp, Phong Vân Tranh Bá, Hắc Sắc Chuyển Bàn...). TUYỆT ĐỐI KHÔNG ÉP GÁN NHẦM tên người sang nhân vật khác trong bảng và TUYỆT ĐỐI KHÔNG DỊCH THÀNH TIẾNG VIỆT BÌNH DÂN / NÔNG THÔN / NGHĨA ĐEN ĐỜI THƯỜNG.\n"
    "   - QUY TẮC TRẬT TỰ DANH XƯNG & XƯNG HÔ THEO THỂ LOẠI (BẮT BUỘC TUÂN THỦ 100%):\n"
    "     + TRONG TRUYỆN TU TIÊN, HUYỀN HUYỄN, KIẾM HIỆP, CỔ PHONG:\n"
    "       * Hậu tố danh xưng/chức danh/bối phận BẮT BUỘC ĐỨNG SAU [Tên/Họ]: Cấu trúc [Họ/Tên] + [Sư huynh / Sư đệ / Sư tỷ / Sư muội / Trưởng lão / Tông chủ / Chưởng môn / Tiền bối / Huynh / Tỷ / Đệ / Muội / Lão / Đạo hữu...].\n"
    "       * Ví dụ chuẩn xác: 'Văn sư huynh' (文师兄), 'Từ sư huynh' (徐师兄), 'Mã sư đệ' (马师弟), 'Triệu sư muội' (赵师妹), 'Kiều trưởng lão' (乔长老), 'Tiêu tông chủ' (萧宗主), 'Tang lão' (桑老), 'Từ huynh' (徐兄), 'Trương đạo hữu' (张道友), 'Mặc tiền bối' (墨前辈).\n"
    "       * Sửa triệt để các lỗi Google Translate dịch ngược thành: CẤM 'Sư huynh Văn', CẤM 'Sư huynh Từ', CẤM 'Trưởng lão Kiều', CẤM 'Lão Tang', CẤM 'Sư muội Triệu', CẤM 'Tông chủ Tiêu'.\n"
    "       * Tiền tố thân mật ĐỨNG TRƯỚC TÊN: 'Tiểu Uy' (小威), 'Tiểu Từ' (小徐), 'Lão Vương' (老王), 'A Lượng' (阿亮), 'Đại Ngưu' (大牛).\n"
    "     + TRONG TRUYỆN ĐÔ THỊ, HIỆN ĐẠI:\n"
    "       * Danh xưng gia đình / vai vế xã hội đặt TRƯỚC tên: 'Chú Vương' (王叔), 'Dì Lý' (李阿姨), 'Bác Trương' (张伯), 'Cô Hoa', 'Bố', 'Mẹ'.\n"
    "       * Chức vụ / danh vị công sở đặt SAU họ/tên: 'Vương tổng' (王总), 'Lý giám đốc' (李经理), 'Trương giáo sư' (张教授), 'Nguyên ca' (源哥), 'Nhã tỷ' (雅姐).\n"
    "2. NGỮ PHÁP & VĂN PHONG THUẦN VIỆT — ĐỐI CHIẾU THÀNH NGỮ TỤC NGỮ TRUNG - VIỆT:\n"
    "   - KHÔNG DỊCH CONVERT CỨNG NHẮC TỪNG CHỮ: Phải chủ động biến đổi linh hoạt kết cấu câu Trung - Việt sao cho tự nhiên, mượt mà, đúng chuẩn văn học tiểu thuyết (Ví dụ: 'vác kiếm đi dọc suốt đường đi, có người quen cũng có người lạ' -> 'vác kiếm rảo bước dọc đường, gặp cả người quen lẫn kẻ lạ'; 'dẫu sao hắn thâm niên cũng cao, chẳng cần phải gọi người ta làm gì, chỉ cần gật đầu là được' -> 'dẫu sao thâm niên của hắn cũng thuộc hàng lão làng, chẳng cần cất tiếng chào hỏi ai, chỉ khẽ gật đầu là đủ'; 'cửa sự vụ' -> 'quầy sự vụ' / 'bàn tiếp nhận'; 'sinh ra mất mặt' -> 'ngại mất mặt / sợ bẽ mặt').\n"
    "   - CHUẨN CHÍNH TẢ TIẾNG VIỆT 100%: Tuyệt đối chuẩn chính tả phổ thông, không dùng từ địa phương lệch chuẩn làm vỡ mạch văn (CẤM 'chợ giời' -> dịch là 'khu chợ' / 'chợ phiên' / 'như vỡ tổ / náo nhiệt như một phiên chợ'; CẤM 'chỡ vỡ' / 'vỡ chỡ' -> sửa thành 'như vỡ tổ' / 'náo nhiệt tấp nập'; CẤM các lỗi sai dấu, lỗi đánh máy).\n"
    "   - TUYỆT ĐỐI KHÔNG QUÁ VIỆT HÓA: Biến tấu câu văn cho thuần Việt, trôi chảy nhưng BẮT BUỘC giữ nguyên khí chất và phong vị Tiên hiệp, Huyền huyễn, Kiếm hiệp, Cổ phong cổ trang. Giữ nguyên độ ngầu, phong thái Kiếm tu, Tu chân giả, danh xưng môn phái, địa danh, thuật ngữ tu luyện (như Linh Sự Các, Thiên Tang Linh Cung, Phong Vân Tranh Bá, Luyện Linh Cảnh, Chấp sự, Sư tôn, Tông chủ...). TUYỆT ĐỐI CẤM dùng từ lóng đời thường hiện đại, tiếng bồi hay ngôn ngữ nông thôn làm mất chất tiên hiệp.\n"
    "   - ĐỐI CHIẾU THÀNH NGỮ, TỤC NGỮ, QUÁN DỤNG NGỮ TRUNG - VIỆT: Khi gặp thành ngữ, tục ngữ, quán ngữ, BẮT BUỘC đối chiếu sang thành ngữ/tục ngữ/cách nói tương đương trong tiếng Việt (Ví dụ: '凑数 / 凑热闹' -> 'qua loa cho có lệ / làm lấy lệ / góp vui', CẤM 'cho có tụ'; '隔墙有耳' -> 'tai vách mạch rừng'; '班门弄斧' -> 'múa rìu qua mắt thợ'; '趁火打劫' -> 'đục nước béo cò / cháy nhà hôi của').\n"
    "   - TUYỆT ĐỐI KHÔNG tự ý bịa thêm câu ngắn/tình tiết ngoài truyện, không tự tiện chèn câu hỏi tu từ ngoài văn bản gốc.\n"
    "   - Sửa triệt để các rác dịch thô của Google Translate (như 'đem...', 'đối với... mà nói', 'trong lòng có chút...', 'dưới một cái...', 'sau khi...').\n"
    "3. NHỊP ĐIỆU DẪN CHUYỆN NGÔI THỨ BA & QUY TẮC ĐẠI TỪ 'Y':\n"
    "   - Trong lời dẫn chuyện/kể chuyện (ngôi thứ ba): BẮT BUỘC xen kẽ nhịp nhàng, linh hoạt giữa 'y', 'hắn' và 'tên nhân vật' (như Từ Tiểu Thụ) để mạch văn không bị lặp từ thô cứng ('hắn... hắn... hắn...'), nhưng cũng không hoán đổi quá giật cục thô gượng.\n"
    "   - QUY TẮC KHOẢNG TRẮNG ĐẠI TỪ 'Y': Khi dịch danh xưng / đại từ xưng hô là 'y', BẮT BUỘC phải có dấu cách (khoảng trắng) rõ ràng ở cả hai phía (ví dụ: ' y ', 'y đã', 'nhìn y', 'thấy y'), TUYỆT ĐỐI KHÔNG viết dính liền chữ (CẤM: 'yđã', 'yđi', 'yvào', 'ngườiy').\n"
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
    "11. QUY TẮC TINH GỌN CÂU VĂN & MIÊU TẢ SẮC VĂN (EROTIC / 18+) — ĐẶT ĐÚNG VỊ TRÍ TỪ LÓNG:\n"
    "   - ĐƯỢC PHÉP TINH GỌN & BỎ BỚT TỪ THỪA / TRỢ TỪ LẶP LẠI: Bạn ĐƯỢC PHÉP VÀ KHUYẾN KHÍCH lược bỏ bớt từ thừa, gọt giũa câu văn cho gãy gọn, tự nhiên, dễ hiểu (Ví dụ: '我的好妈妈呀' -> CẤM dịch rườm rà 'Mẹ hiền ơi của ta ơi', BẮT BUỘC tinh gọn thành 'Mẹ yêu ơi!' / 'Mẹ hiền của con ơi!' / 'Mẹ ơi!').\n"
    "   - NGUYÊN TẮC NGÔN TỪ 18+ / SẮC VĂN TỰ NHIÊN & ĐẶT ĐÚNG VỊ TRÍ TỪ LÓNG:\n"
    "     * Sử dụng từ ngữ chân thực, sinh động, đúng ngữ pháp tiếng Việt. TUYỆT ĐỐI CẤM ghép lẩu thập cẩm từ lóng nhẹ + từ lóng tục làm dị dạng câu văn:\n"
    "     * CẤM 'lồn tử cung' -> BẮT BUỘC dịch là 'sâu trong tử cung' hoặc 'sâu trong lồn' / 'hoa huyệt'.\n"
    "     * CẤM dính chữ lặp rơi vãi như 'cu cuối cùng' -> BẮT BUỘC sửa thành 'cuối cùng'.\n"
    "     * CẤM dịch thô 'con gà trống' (cock/鸡巴) -> BẮT BUỘC dịch là 'côn thịt' / 'cự vật' / 'con cặc' / 'dương vật'.\n"
    "     * CẤM 'địtt' (lặp chữ t) -> sửa thành 'địt'.\n"
    "     * CẤM 'nước trái cây' (khi miêu tả dâm dục) -> BẮT BUỘC dịch là 'nước dâm' / 'dâm dịch' / 'mật dịch'.\n"
    "     * CẤM dịch 'đánh mình' khi nói về cuộc gọi điện thoại (打过来) -> BẮT BUỘC dịch là 'gọi điện cho mình' / 'gọi tới'.\n"
    "     * Miêu tả ngực: 'bầu vú', 'cặp vú', 'bầu ngực', 'đầu vú', 'núm vú', 'khe vú'.\n"
    "     * Miêu tả hạ bộ nam: 'con cặc', 'côn thịt', 'buồi', 'cự vật', 'dương vật'.\n"
    "     * Miêu tả hạ bộ nữ: 'lỗ lồn', 'âm đạo', 'hoa huyệt', 'tiểu huyệt', 'mật huyệt', 'khe lồn'.\n"
    "     * Miêu tả dịch tiết: 'nước lồn', 'dâm dịch', 'mật dịch', 'nước dâm'.\n"
    "     * Miêu tả hành vi: 'làm tình', 'địt nhau', 'chịch nhau', 'thao nhau', 'đút cặc vào lồn', 'nhấp liên tục'.\n"
    "   - LƯU Ý BẮT BUỘC: Bạn PHẢI tự điều chỉnh ngữ pháp câu văn thuần Việt mượt mà, gợi cảm và lôi cuốn, TUYỆT ĐỐI KHÔNG để lặp từ thô cứng.\n"
    "12. BẢO TỒN DÒNG HẾT CHƯƠNG — BỎ THÔNG BÁO RÁC:\n"
    "   - Bắt buộc giữ nguyên dòng 'Hết chương' ở cuối mỗi chương để người nghe/người đọc biết chương đã kết thúc trọn vẹn và đủ nội dung. Loại bỏ các ghi chú tác giả ngoài lề, quảng cáo trang web rác. Chỉ tập trung 100% vào nội dung diễn biến truyện chính.\n"
    "13. BẢO TỒN ĐẦY ĐỦ TỪ TƯỢNG THANH, LA HÉT, RÊN RỈ, CƯỜI CỢT — CHUẨN HÓA TIẾNG VIỆT TỰ NHIÊN:\n"
    "   - TUYỆT ĐỐI KHÔNG TỰ Ý XÓA BỎ hoặc cắt cụt các từ tượng thanh, tiếng rên rỉ, tiếng cười khóc trong lời thoại và miêu tả của tác giả.\n"
    "   - BẮT BUỘC dịch và chuẩn hóa sang từ tượng thanh tiếng Việt tự nhiên (lặp 2-3 từ, có dấu câu rõ ràng):\n"
    "     * Tiếng la hét: '啊啊' / '啊啊啊' -> Dịch thành 'Á á!' / 'Á... á!' / 'A a a!'.\n"
    "     * Tiếng cười: '哈哈' -> 'Ha ha!', '哈哈哈' -> 'Ha ha ha!', '嘻嘻' -> 'Hi hi!', '呵呵'/'嘿嘿' -> 'Hì hì!' / 'Hê hê!'.\n"
    "     * Tiếng khóc: '呜呜' -> 'Hu hu!', 'Hu hu hu!'.\n"
    "     * Tiếng rên rỉ / thở dốc: '嗯嗯'/'唔' -> 'Ư ư...', 'Ưm ưm...', 'Ừm ừm...', 'ô ô...', 'hộc hộc...'.\n"
    "     * Tiếng cảm thán / hậm hực: '哼'/'哼哼' -> 'Hừ!', 'Hừ hừ!'.\n"
    "     * Tiếng lắp bắp / hoảng loạn: '不...不要' -> 'Không... không được!' / 'Đừng... đừng mà!', 'c... con' -> 'Con... con', 'm... mẹ' -> 'Mẹ... mẹ' (TUYỆT ĐỐI CẤM viết cộc lốc kiểu 'k-không', 'c-con').\n"
    "   - Giữ trọn vẹn cảm xúc nhân vật, tránh viết chuỗi lê thê vô nghĩa (như hơn 10 chữ lặp lại).\n"
    "14. CHUẨN HÓA DẤU CHẤM PHẨY THEO ĐÚNG NGỮ PHÁP TIẾNG VIỆT — TẠO NHỊP THỞ TTS HOÀN HẢO:\n"
    "   - CHẤM CÂU DỨT KHOÁT: Khi diễn đạt trọn vẹn một ý, một hành động hay sự việc hoàn chỉnh, BẮT BUỘC dùng dấu chấm '.' để kết thúc câu. TUYỆT ĐỐI KHÔNG lạm dụng dấu phẩy ',' nối dài dằng dặc cả đoạn theo văn phong tiếng Hán khiến giọng đọc Edge-TTS bị hụt hơi, đọc dồn dập không có nhịp ngắt.\n"
    "   - DẤU PHẨY ĐÚNG VỊ TRÍ: Dùng dấu phẩy ngắt vế câu sau trạng ngữ, giữa các vế câu ghép, giữa các thành phần liệt kê theo đúng chuẩn ngữ pháp tiếng Việt để tạo nhịp thở ngắt nghỉ mượt mà, truyền cảm.\n"
    "   - KHÔNG ĐỂ CHUỖI DẤU LỘN XỘN: Không dùng các chuỗi dấu lộn xộn như '!?!?', '??!!', ',,,,', '....', '~~~', '— — —'.\n"
    "15. KHÔNG DÙNG KÝ HIỆU ĐẶC BIỆT — VIẾT THẲNG LỜI VĂN XUÔI:\n"
    "   - TUYỆT ĐỐI KHÔNG lạm dụng ký hiệu trang trí hay ký tự lạ ('★', '◆', '※', '^', '_', '~', ngoặc vuông lạ, ngoặc đơn mở ra chú thích giải nghĩa). Mọi nội dung, thông số hay miêu tả đều PHẢI viết thẳng thành câu văn xuôi tiếng Việt tự nhiên, gãy gọn.\n"
    "   - Viết đầy đủ 100% tất cả các từ/ký tự viết tắt (EXP -> điểm kinh nghiệm, HP -> lượng máu, MP -> năng lượng, Lv/Level -> cấp độ, NPC -> nhân vật phụ, VIP -> khách quý, TP.HCM -> Thành phố Hồ Chí Minh...). Phải viết hoàn chỉnh ra chữ tiếng Việt để Edge-TTS phát âm chuẩn xác.\n"
    "16. GIỮ NGUYÊN MẠCH ĐOẠN VĂN TIỂU THUYẾT — TRÁNH XUỐNG DÒNG VỤN VẶT:\n"
    "   - Ghép nối các câu miêu tả diễn biến liên tục thành đoạn văn hoàn chỉnh, mượt mà. TUYỆT ĐỐI KHÔNG xuống dòng sau từng câu đơn lẻ làm ngắt nát văn bản của truyện!\n"
    "17. LOẠI BỎ CHỮ RÁC WATERMARK TRANG WEB:\n"
    "   - Tự động loại bỏ hoàn toàn các chữ rác watermark của trang web Trung Quốc như 'Mì nấm phải thêm trứng', '15619 Chữ', số từ."
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

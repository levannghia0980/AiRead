import json

# Context Profiles cho LLM (Luồng Dịch Trực Tiếp từ RAW - RAWT)
# Các thông tin này sẽ được nhúng trực tiếp vào System Prompt để chỉ dẫn LLM dịch Hán văn sang tiếng Việt chuẩn mực, thuần Việt, mượt mà.

XIANXIA_PROFILE = {
    "description": (
        "- Thể loại & Bối cảnh: Tu tiên, Tiên hiệp, Huyền huyễn, Dị giới, Cổ phong, Lịch sử, Cổ trang.\n"
        "- Lời dẫn chuyện (Ngôi thứ ba / Kể chuyện): Dùng 'hắn', 'y', 'gã', 'nàng', 'lão', 'thiếu niên', 'lão giả', 'tiểu tử'... Phối hợp nhịp nhàng, uyển chuyển giữa 'hắn/y' và tên nhân vật để mạch văn không bị lặp từ thô cứng. TUYỆT ĐỐI CẤM dùng từ hiện đại ('cậu', 'tôi', 'bạn', 'anh', 'em', 'cô') trong lời dẫn chuyện.\n"
        "- Đại từ đối thoại (Nhân vật nói chuyện):\n"
        "  + Đối thoại ngang hàng / Người lạ / Kẻ địch / Tranh chấp: Dùng 'ta - ngươi', 'các hạ', 'đạo hữu', 'chư vị', 'các ngươi'.\n"
        "  + Quan hệ Sư môn: 'Sư tôn / Sư phụ - Đệ tử / Đồ nhi', 'Sư huynh / Sư tỷ - Sư đệ / Sư muội'.\n"
        "  + Quan hệ Thân tộc / Gia đình: 'Phụ thân / Cha - Hài nhi / Con', 'Mẫu thân / Mẹ - Hài nhi / Con', 'Huynh - Đệ', 'Tỷ - Muội', 'Gia gia / Ông - Cháu', 'Lão tổ - Hậu bối'.\n"
        "  + Quan hệ Phu thê / Tình cảm: 'Phu quân / Tướng công - Nương tử / Thê tử / Ái thê', 'Ta - Nàng / Chàng'.\n"
        "  + Quan hệ Tôn ti / Địa vị: 'Tiền bối - Vãn bối', 'Chưởng môn / Tông chủ - Các vị', 'Bản tọa / Bản tôn - Các ngươi', 'Trẫm - Khanh / Ái khanh', 'Bản vương - Ngươi'.\n"
        "- LỆNH CẤM TUYỆT ĐỐI: CẤM 100% dùng 'mày - tao' trong toàn bộ truyện (kể cả lúc đánh nhau, tức giận, khinh bỉ hay chửi bới).\n"
        "- TÍNH NHẤT QUÁN: Xưng hô giữa các nhân vật phải xuyên suốt, ổn định từ đầu đến cuối một chương và cả bộ truyện, không được thay đổi tùy tiện."
    )
}

WUXIA_PROFILE = {
    "description": (
        "- Thể loại & Bối cảnh: Kiếm hiệp, Võ lâm, Giang hồ truyền thống.\n"
        "- Lời dẫn chuyện (Ngôi thứ ba / Kể chuyện): Dùng 'hắn', 'y', 'gã', 'nàng', 'lão', 'hiệp khách', 'lão nhân'... CẤM dùng từ hiện đại ('cậu', 'tôi', 'anh', 'em').\n"
        "- Đại từ đối thoại: Mang đậm chất hào khí võ lâm giang hồ: 'ta - ngươi', 'huynh - đệ', 'tỷ - muội', 'đại hiệp - các hạ', 'tiểu đệ', 'tiền bối - vãn bối', 'chưởng môn', 'minh chủ'.\n"
        "- LỆNH CẤM TUYỆT ĐỐI: CẤM 100% dùng 'mày - tao' trong mọi tình huống đối thoại.\n"
        "- TÍNH NHẤT QUÁN: Giữ nguyên bối phận và xưng hô xuyên suốt cả một chương và toàn bộ tác phẩm."
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
    "1. BẢO TỒN THỰC THỂ & DỊCH TỰ NHIÊN THEO NGỮ CẢNH — THUẦN HÓA TOÀN BỘ NGỮ PHÁP TIẾNG VIỆT:\n"
    "   - VỀ THỰC THỂ (Tên nhân vật, địa danh, môn phái, công pháp, cảnh giới, bảo vật, chiêu thức):\n"
    "     + ĐỐI VỚI THỰC THỂ ĐÃ CÓ TRONG BẢNG THAM KHẢO: BẮT BUỘC dùng đúng 100% từ đã chuẩn hóa trong bảng khi xuất hiện trong văn bản để đảm bảo tính nhất quán.\n"
    "     + ĐỐI VỚI TÊN NHÂN VẬT & THỰC THỂ MỚI CHƯA CÓ TRONG BẢNG:\n"
    "       * Bảng thực thể chỉ là danh sách tham khảo các từ đã biết, KHÔNG PHẢI danh sách duy nhất bao quát toàn bộ (thuật toán trích xuất có thể bỏ sót nhiều tên nhân vật trong tác phẩm).\n"
    "       * LLM PHẢI chủ động nhận diện tên nhân vật, danh xưng, địa danh, môn phái mới theo ngữ cảnh mạch truyện và dịch/phiên âm sang âm HÁN-VIỆT CHUẨN CỔ PHONG (Ví dụ: Từ Tiểu Thụ, Trương Tam, Thiên Tang Linh Cung, Luyện Linh Cảnh, Hô Hấp Chi Pháp, Hắc Sắc Luân Bàn...).\n"
    "       * TUYỆT ĐỐI KHÔNG ÉP GÁN NHẦM: Không được ép các tên nhân vật mới/chưa có trong bảng về một tên có sẵn trong bảng nếu chúng là các nhân vật khác nhau. TUYỆT ĐỐI CẤM dịch tên người thành nghĩa đen đời thường (CẤM biến tên người thành động từ/đồ vật bình dân).\n"
    "     + QUY TẮC TRẬT TỰ DANH XƯNG & XƯNG HÔ THEO THỂ LOẠI (BẮT BUỘC TUÂN THỦ 100%):\n"
    "       * TRONG TRUYỆN TU TIÊN, HUYỀN HUYỄN, KIẾM HIỆP, CỔ PHONG:\n"
    "         - Hậu tố danh xưng/chức danh/bối phận BẮT BUỘC ĐỨNG SAU [Tên/Họ]: Cấu trúc [Họ/Tên] + [Sư huynh / Sư đệ / Sư tỷ / Sư muội / Trưởng lão / Tông chủ / Chưởng môn / Tiền bối / Huynh / Tỷ / Đệ / Muội / Lão / Đạo hữu...].\n"
    "         - Ví dụ chuẩn xác: 'Văn sư huynh' (文师兄), 'Từ sư huynh' (徐师兄), 'Mã sư đệ' (马师弟), 'Triệu sư muội' (赵师妹), 'Kiều trưởng lão' (乔长老), 'Tiêu tông chủ' (萧宗主), 'Tang lão' (桑老), 'Từ huynh' (徐兄), 'Trương đạo hữu' (张道友), 'Mặc tiền bối' (墨前辈).\n"
    "         - TUYỆT ĐỐI CẤM dịch ngược kiểu Tây phương hay Google dịch thô: CẤM 'Sư huynh Văn', CẤM 'Sư huynh Từ', CẤM 'Trưởng lão Kiều', CẤM 'Lão Tang', CẤM 'Sư muội Triệu', CẤM 'Tông chủ Tiêu'.\n"
    "         - Tiền tố thân mật ĐỨNG TRƯỚC TÊN: 'Tiểu Uy' (小威), 'Tiểu Từ' (小徐), 'Lão Vương' (老王), 'A Lượng' (阿亮), 'Đại Ngưu' (大牛).\n"
    "       * TRONG TRUYỆN ĐÔ THỊ, HIỆN ĐẠI:\n"
    "         - Danh xưng gia đình / vai vế xã hội đặt TRƯỚC tên: 'Chú Vương' (王叔), 'Dì Lý' (李阿姨), 'Bác Trương' (张伯), 'Cô Hoa', 'Bố', 'Mẹ'.\n"
    "         - Chức vụ / danh vị công sở đặt SAU họ/tên: 'Vương tổng' (王总), 'Lý giám đốc' (李经理), 'Trương giáo sư' (张教授), 'Nguyên ca' (源哥), 'Nhã tỷ' (雅姐).\n"
    "   + KHUYẾN KHÍCH BIẾN TẤU TỪ NGỮ THOÁT HÁN — TỰ NHIÊN, GÃY GỌN NHƯNG TUYỆT ĐỐI KHÔNG QUÁ VIỆT HÓA:\n"
    "       * KHÔNG DỊCH CONVERT CỨNG NHẮC TỪNG CHỮ: Phải chủ động biến đổi linh hoạt kết cấu câu Trung - Việt sao cho tự nhiên, mượt mà, đúng chuẩn văn học tiểu thuyết (Ví dụ: 'vác kiếm đi dọc suốt đường đi, có người quen cũng có người lạ' -> biến tấu thành 'vác kiếm rảo bước dọc đường, gặp cả người quen lẫn kẻ lạ'; 'dẫu sao hắn thâm niên cũng cao, chẳng cần phải gọi người ta làm gì, chỉ cần gật đầu là được' -> 'dẫu sao thâm niên của hắn cũng thuộc hàng lão làng, chẳng cần cất tiếng chào hỏi ai, chỉ khẽ gật đầu là đủ'; 'cửa sự vụ' -> 'quầy sự vụ' / 'bàn tiếp nhận'; 'sinh ra mất mặt' -> 'ngại mất mặt / sợ bẽ mặt').\n"
    "       * CHUẨN CHÍNH TẢ TIẾNG VIỆT 100%: Tuyệt đối chuẩn chính tả phổ thông, không dùng từ địa phương lệch chuẩn làm vỡ mạch văn (CẤM 'chợ giời' -> dịch là 'khu chợ' / 'chợ phiên' / 'như vỡ tổ / náo nhiệt như một phiên chợ'; CẤM 'chỡ vỡ' / 'vỡ chỡ' -> sửa thành 'như vỡ tổ' / 'náo nhiệt tấp nập'; CẤM các lỗi sai dấu, lỗi đánh máy).\n"
    "       * TUYỆT ĐỐI KHÔNG QUÁ VIỆT HÓA: Biến tấu câu văn cho thuần Việt, trôi chảy nhưng BẮT BUỘC giữ nguyên khí chất và phong vị Tiên hiệp, Huyền huyễn, Kiếm hiệp, Cổ phong cổ trang. Giữ nguyên độ ngầu, phong thái Kiếm tu, Tu chân giả, danh xưng môn phái, địa danh, thuật ngữ tu luyện (như Linh Sự Các, Thiên Tang Linh Cung, Phong Vân Tranh Bá, Luyện Linh Cảnh, Chấp sự, Sư tôn, Tông chủ...). TUYỆT ĐỐI CẤM dùng từ lóng đời thường hiện đại, tiếng bồi hay ngôn ngữ nông thôn làm mất chất tiên hiệp.\n"
    "   - VỀ CHỌN TỪ & ĐỐI CHIẾU THÀNH NGỮ, TỤC NGỮ, QUÁN NGỮ TRUNG - VIỆT (BẮT BUỘC DỄ HIỂU, ĐÚNG NGHĨA PHỔ THÔNG):\n"
    "     + ĐỐI CHIẾU THÀNH NGỮ, TỤC NGỮ, QUÁN DỤNG NGỮ TRUNG - VIỆT (CHỐNG DỊCH THÔ TỪNG CHỮ):\n"
    "       * Khi gặp các thành ngữ (成语), tục ngữ (俗语), yết hậu ngữ hoặc quán dụng ngữ tiếng Trung, BẮT BUỘC phải đối chiếu và chuyển ngữ sang thành ngữ / tục ngữ / cách diễn đạt tương đương trong tiếng Việt sao cho mượt mà, tự nhiên và hợp lý nhất theo ngữ cảnh.\n"
    "       * Ví dụ: '凑数 / 凑热闹' -> 'qua loa cho có lệ / làm lấy lệ / cho đủ quân số / góp vui' (TUYỆT ĐỐI CẤM dịch thô 'cho có tụ'); '隔墙有耳' -> 'tai vách mạch rừng / tường có tai'; '班门弄斧' -> 'múa rìu qua mắt thợ'; '画蛇添足' -> 'vẽ rắn thêm chân / thừa giấy vẽ voi'; '井底之蛙' -> 'ếch ngồi đáy giếng'; '趁火打劫' -> 'đục nước béo cò / cháy nhà hôi của'; '半斤八两' -> 'kẻ tám lạng người nửa cân'; '八字没一撇' -> 'việc chưa đâu vào đâu / chưa có manh mối gì'; '赶鸭子上架' -> 'bắt vịt lên giàn / ép làm chuyện quá sức'.\n"
    "     + KHUYẾN KHÍCH BIẾN TẤU TỪ NGỮ CHO THUẦN VIỆT, TỰ NHIÊN: Không thêm thắt tình tiết ngoài truyện, nhưng BẮT BUỘC PHẢI BIẾN TẤU cách dùng từ tiếng Hán sang cách diễn đạt tiếng Việt tự nhiên, dễ hiểu. Tuyệt đối KHÔNG dịch dập khuôn cứng nhắc từng chữ.\n"
    "     + BẮT BUỘC KIỂM TRA TÍNH HỢP LÝ CỦA TỪ NGỮ: Phải cân nhắc kỹ xem từ ngữ được chọn có hợp lý, tự nhiên và có nghĩa trong ngữ cảnh câu văn hay không.\n"
    "     + TUYỆT ĐỐI CẤM TỪ GHÉP TỐI NGHĨA / HOA MỸ SAI NGỮ CẢNH:\n"
    "       * CẤM dùng từ hoa mỹ gượng gạo, vô lý (CẤM: 'mơn man da chết trên môi' -> BẮT BUỘC dịch là 'mân mê lớp da khô / bờ môi nứt nẻ').\n"
    "       * CẤM dùng từ vô nghĩa, dịch ẩu (CẤM: 'ngã quấy xuống' -> BẮT BUỘC dịch là 'ngã quỵ xuống / gục ngã / trút hơi thở cuối cùng').\n"
    "   - VỀ NGỮ PHÁP CÂU VĂN (BẮT BUỘC THUẦN VIỆT 100% — THOÁT HÁN TOÀN DIỆN):\n"
    "     + CHỐNG DỊCH NGƯỢC TRẬT TỰ CÂU: Tiếng Trung thường đặt cụm định ngữ/tính từ dài trước danh từ, hoặc đặt trạng ngữ chỉ nơi chốn/thời gian trước động từ. Khi dịch sang tiếng Việt, PHẢI ĐẢO LẠI trật tự tự nhiên của tiếng Việt (Danh từ đứng trước, cụm tính từ/định ngữ bổ nghĩa đứng sau; Chủ ngữ - Vị ngữ - Bổ ngữ rõ ràng, mạch lạc). CẤM dịch ngược kiểu Hán văn.\n"
    "     + CHỐNG DỊCH NGƯỢC CẤU TRÚC ĐỊNH NGỮ CÓ TÊN NHÂN VẬT ([Hành động/Miêu tả] + 的 + [Tên nhân vật]):\n"
    "       * Tiếng Trung: '提前下班回家准备给乖儿子一个惊喜的莫雅仪'\n"
    "       * Tiếng Việt BẮT BUỘC: 'Mạc Nhã Nghi tan làm sớm về nhà để tạo bất ngờ cho cậu con trai ngoan'. TUYỆT ĐỐI CẤM dịch ngược thành 'tạo bất ngờ cho cậu con ngoan Mạc Nhã Nghi' (làm biến Mạc Nhã Nghi thành con)!\n"
    "     + CHỐNG CÂU CỤT NGỦN, CỘC LỐC: Tiếng Trung thường ngắt câu ngắn hoặc tỉnh lược. Khi dịch sang tiếng Việt, BẮT BUỘC chuẩn hóa ngữ pháp câu văn tròn vành rõ chữ, đúng cấu trúc tiếng Việt (Chủ ngữ - Vị ngữ) gãy gọn, tự nhiên. TUYỆT ĐỐI KHÔNG tự ý bịa thêm tình tiết ngoài nguyên tác.\n"
    "     + XÓA BỎ HOÀN TOÀN CÁC CẤU TRÚC HÁN THÔ CỨNG:\n"
    "       * Cấu trúc 'Đem [vật] [hành động]' (把...) -> Thay bằng câu chủ động tự nhiên (ví dụ: 'đem kiếm rút ra' -> 'rút phắt thanh trường kiếm ra', 'đem cửa đẩy mở' -> 'đẩy toang cánh cửa').\n"
    "       * Cấu trúc 'Đối với... mà nói' (对于...来说) -> Thay bằng 'Với...', 'Xét về...', 'Đối với...'.\n"
    "       * Cấu trúc 'Ở dưới một khắc / Dưới một cái' (下一刻 / 一下) -> Thay bằng 'Khoảnh khắc kế tiếp', 'Ngay sau đó', 'Chớp mắt một cái'.\n"
    "       * Cấu trúc 'Bị... cho...' (被...给...) -> Thay bằng 'Bị...', 'Đã bị...'.\n"
    "       * 'Có chút...' (有些 / 有点) -> Thay bằng 'Hơi...', 'Có phần...', 'Chút nào...'.\n"
    "       * CẤM để sót rác từ ngữ pháp Hán-Việt: 'Đích' (của), 'Thị' (là), 'Chi' (của/đó), 'Hạ' (dưới), 'Thượng' (trên), 'Cấp' (cho).\n"
    "2. TUYỆT ĐỐI CẤM 'MÀY - TAO' & ĐÚNG QUAN HỆ XƯNG HÔ GIA ĐÌNH / BỐI PHẬN:\n"
    "   - CẤM 100% sử dụng đại từ 'mày - tao' trong toàn bộ văn bản dịch.\n"
    "   - XƯNG HÔ GIA ĐÌNH & PHU THÊ CHUẨN XÁC: Vợ nói chuyện với chồng BẮT BUỘC xưng 'Em' (CẤM nhầm thành 'Con'). Mẹ nói chuyện với con BẮT BUỘC xưng 'Mẹ - Con' (CẤM nhầm thành 'Anh/Em'). Chồng nói với vợ xưng 'Anh - Em'.\n"
    "   - Truyện Tiên hiệp / Cổ trang: Luôn luôn dùng 'ta - ngươi', 'các ngươi', hoặc xưng hô bối phận phù hợp.\n"
    "   - Xưng hô phải NHẤT QUÁN xuyên suốt cả một chương và toàn bộ bộ truyện, không được đảo lộn hay thay đổi tùy tiện giữa chừng.\n"
    "3. NGHỆ THUẬT DẪN CHUYỆN NGÔI THỨ BA (VĂN DẪN) & QUY TẮC ĐẠI TỪ 'Y':\n"
    "   - Lời dẫn chuyện phải uyển chuyển, giàu cảm xúc, đúng phong cách văn học tiểu thuyết.\n"
    "   - Linh hoạt xen kẽ giữa 'hắn', 'y', 'gã', 'nàng', 'lão', 'thiếu niên' và tên nhân vật để tránh lặp từ thô cứng ('hắn... hắn... hắn...'), tạo nhịp điệu sinh động cuốn hút. TUYỆT ĐỐI CẤM dùng từ 'cậu' trong lời kể chuyện tiên hiệp/cổ phong.\n"
    "   - QUY TẮC KHOẢNG TRẮNG ĐẠI TỪ 'Y': Nếu dịch danh xưng / đại từ xưng hô là 'y', BẮT BUỘC phải có dấu cách (khoảng trắng) rõ ràng ở cả hai phía (ví dụ: ' y ', 'y đã', 'nhìn y', 'thấy y'), TUYỆT ĐỐI CẤM viết dính liền chữ ('yđã', 'yđi', 'yvào', 'ngườiy').\n"
    "4. TRUYỀN TẢI ĐÚNG Ý NGHĨA NGUYÊN TÁC — ĐƯỢC PHÉP BỎ BỚT TỪ THỪA CHO CÂU VĂN GÃY GỌN, DỄ HIỂU:\n"
    "   - ĐƯỢC PHÉP BỎ BỚT TỪ & TINH GỌN MỌI CẤU TRÚC RƯỜM RÀ: Tiếng Trung thường có thói quen dùng nhiều trợ từ, từ đệm, động từ kép hoặc các cụm từ kéo dài khi dịch từng chữ sang tiếng Việt sẽ rất lủng củng, khó hiểu. Bạn ĐƯỢC PHÉP VÀ KHUYẾN KHÍCH lược bỏ từ thừa, gọt giũa câu chữ sao cho thuần Việt, tự nhiên và gãy gọn nhất theo đúng ý nghĩa câu văn:\n"
    "     + CẢM THÁN / THAN THỞ / CHỬI THỀ: Dịch thoát ý theo đúng khẩu ngữ tiếng Việt tự nhiên (Ví dụ: '我的妈呀' / '我的好妈妈呀' -> BẮT BUỘC dịch là 'Ôi mẹ ơi!' / 'Ối mẹ ơi!' / 'Mẹ ơi!' / 'Mẹ kiếp!' tùy ngữ cảnh — TUYỆT ĐỐI CẤM dịch nghĩa đen 'Mẹ hiền ơi của ta ơi'; '我的天啊' -> 'Trời đất ơi!'; '你大爷的' -> 'Mẹ kiếp!' / 'Đồ khốn!').\n"
    "     + HÀNH ĐỘNG / ĐỘNG TỪ KÉP RƯỜM RÀ: Lược bỏ các từ đệm hành vi thừa thãi (Ví dụ: '做出了一个点头的动作' -> dịch gọn là 'gật đầu', CẤM 'làm ra động tác gật đầu'; '伸出手来去拿' -> 'với tay lấy'; '朝着门的方向走了过去' -> 'đi về phía cửa').\n"
    "     + TÂM LÝ / SUY NGHĨ / CẢM GIÁC THỪA CHỮ: Gọt giũa gãy gọn (Ví dụ: '在内心深处默默地想道' -> dịch gọn là 'thầm nghĩ' / 'trong lòng tự nhủ', CẤM 'ở chỗ sâu trong nội tâm âm thầm nghĩ rằng'; '感觉到了有一股力量' -> 'cảm nhận một luồng sức mạnh').\n"
    "     + QUAN HỆ / NGUYÊN NHÂN / DẪN DẮT DÍNH CHỮ: Tinh gọn từ nối (Ví dụ: '因为...的缘故 / 的原因' -> dịch gọn là 'vì...', CẤM 'bởi vì nguyên nhân của...'; '对于这件事情来说' -> 'về chuyện này' / 'đối với việc này').\n"
    "   - Truyền tải trọn vẹn diễn biến và thông điệp của tác giả. Được phép và khuyến khích trau chuốt, biến đổi từ ngữ để câu văn tiếng Việt giàu hình ảnh, biểu cảm và tự nhiên.\n"
    "   - TUYỆT ĐỐI KHÔNG tự ý bịa thêm câu ngắn/tình tiết ngoài truyện, không tự ý chèn các câu hỏi tu từ hoặc từ cảm thán cộc cằn thừa thãi (như '...không đau đớn ư?', 'sao?', 'ư?', 'rồi sao?').\n"
    "5. BẢO TỒN THUẬT NGỮ TU TIÊN & SỐ ĐẾM HÁN-VIỆT CHUẨN:\n"
    "   - Cảnh giới / Tầng / Trọng: BẮT BUỘC dùng số Hán-Việt (Nhất, Nhị, Tam, Tứ, Ngũ, Lục, Thất, Bát, Cửu, Thập...). CẤM dùng 'thứ ba', 'thứ 4'.\n"
    "   - Giữ nguyên các thuật ngữ tu chân: Khí Hải, Đan Điền, Thần Thức, Pháp Bảo, Công Pháp, Linh Khí, Độ Kiếp, Phá Cảnh, Bình Cảnh (CẤM nhầm thành bình phong), Quán Chú...\n"
    "6. DỊCH ĐẦY ĐỦ 100%, XUẤT RA TIẾNG VIỆT THUẦN TÚY & XỬ LÝ TỪ KHÓ HỢP LÝ:\n"
    "   - Dịch đầy đủ 100% diễn biến nội dung, không cắt xén, không tóm tắt.\n"
    "   - TUYỆT ĐỐI CẤM để sót chữ Hán rơi vãi trong văn bản xuất ra (trừ các mã thẻ §...§ đã được bọc bảo vệ).\n"
    "   - XỬ LÝ TỪ KHÓ/TỐI NGHĨA: Dịch đúng nghĩa, không ép buộc suy diễn bậy bạ làm biến dạng câu văn (khiến hậu xử lý không nhận ra để sửa). Nếu gặp từ hiếm, từ cổ hoặc tên riêng tối nghĩa không chắc chắn, hãy phiên âm theo âm Hán-Việt chuẩn xác nhất để bảo toàn cấu trúc văn bản và hỗ trợ hậu xử lý vá lại khi cần.\n"
    "7. BẢO TỒN DÒNG HẾT CHƯƠNG — BỎ THÔNG BÁO RÁC:\n"
    "   - Bắt buộc giữ nguyên dòng 'Hết chương' ở cuối mỗi chương để người nghe/người đọc biết chương đã kết thúc trọn vẹn và đủ nội dung. Loại bỏ ghi chú tác giả ngoài lề, quảng cáo trang web rác.\n"
    "8. BẢO TỒN ĐẦY ĐỦ TỪ TƯỢNG THANH, LA HÉT, RÊN RỈ, CƯỜI CỢT — CHUẨN HÓA TIẾNG VIỆT TỰ NHIÊN:\n"
    "   - TUYỆT ĐỐI KHÔNG TỰ Ý XÓA BỎ hoặc cắt cụt các từ tượng thanh, tiếng rên rỉ, tiếng cười khóc trong lời thoại và miêu tả của tác giả.\n"
    "   - BẮT BUỘC dịch và chuẩn hóa sang từ tượng thanh tiếng Việt tự nhiên (lặp 2-3 từ, có dấu câu rõ ràng):\n"
    "     * Tiếng la hét: '啊啊' / '啊啊啊' -> Dịch thành 'Á á!' / 'Á... á!' / 'A a a!'.\n"
    "     * Tiếng cười: '哈哈' -> 'Ha ha!', '哈哈哈' -> 'Ha ha ha!', '嘻嘻' -> 'Hi hi!', '呵呵'/'嘿嘿' -> 'Hì hì!' / 'Hê hê!'.\n"
    "     * Tiếng khóc: '呜呜' -> 'Hu hu!', 'Hu hu hu!'.\n"
    "     * Tiếng rên rỉ / thở dốc: '嗯嗯'/'唔' -> 'Ư ư...', 'Ưm ưm...', 'Ừm ừm...', 'ô ô...', 'hộc hộc...'.\n"
    "     * Tiếng cảm thán / hậm hực: '哼'/'哼哼' -> 'Hừ!', 'Hừ hừ!'.\n"
    "     * Tiếng lắp bắp / hoảng loạn: '不...不要' -> 'Không... không được!' / 'Đừng... đừng mà!', 'c... con' -> 'Con... con', 'm... mẹ' -> 'Mẹ... mẹ' (TUYỆT ĐỐI CẤM viết cộc lốc kiểu 'k-không', 'c-con').\n"
    "   - Giữ trọn vẹn cảm xúc nhân vật, tránh viết chuỗi lê thê vô nghĩa (như hơn 10 chữ lặp lại).\n"
    "9. CHUẨN HÓA DẤU CHẤM PHẨY THEO ĐÚNG NGỮ PHÁP TIẾNG VIỆT — TẠO NHỊP THỞ TTS HOÀN HẢO:\n"
    "   - CHẤM CÂU DỨT KHOÁT: Khi diễn đạt trọn vẹn một ý, một hành động hay sự việc hoàn chỉnh, BẮT BUỘC dùng dấu chấm '.' để kết thúc câu. TUYỆT ĐỐI KHÔNG lạm dụng dấu phẩy ',' nối dài dằng dặc cả đoạn theo văn phong tiếng Hán khiến giọng đọc Edge-TTS bị hụt hơi, đọc dồn dập không có nhịp ngắt.\n"
    "   - DẤU PHẨY ĐÚNG VỊ TRÍ: Dùng dấu phẩy ngắt vế câu sau trạng ngữ, giữa các vế câu ghép, giữa các thành phần liệt kê theo đúng chuẩn ngữ pháp tiếng Việt để tạo nhịp thở ngắt nghỉ mượt mà, truyền cảm.\n"
    "   - KHÔNG ĐỂ CHUỖI DẤU LỘN XỘN: Không dùng các chuỗi dấu lộn xộn như '!?!?', '??!!', ',,,,', '....', '~~~', '— — —'.\n"
    "10. KHÔNG DÙNG KÝ HIỆU ĐẶC BIỆT — VIẾT THẲNG LỜI VĂN XUÔI:\n"
    "    - TUYỆT ĐỐI KHÔNG lạm dụng ký hiệu trang trí hay ký tự lạ ('★', '◆', '※', '^', '_', '~', ngoặc vuông lạ, ngoặc đơn mở ra chú thích giải nghĩa). Mọi nội dung, thông số hay miêu tả đều PHẢI viết thẳng thành câu văn xuôi tiếng Việt tự nhiên, gãy gọn.\n"
    "    - Viết đầy đủ 100% tất cả các từ/ký tự viết tắt (EXP -> điểm kinh nghiệm, HP -> lượng máu, MP -> năng lượng, Lv/Level -> cấp độ, NPC -> nhân vật phụ, VIP -> khách quý...). Viết hoàn chỉnh ra chữ tiếng Việt để Edge-TTS phát âm chuẩn xác.\n"
    "11. GIỮ NGUYÊN MẠCH ĐOẠN VĂN TIỂU THUYẾT — TRÁNH XUỐNG DÒNG VỤN VẶT:\n"
    "    - Ghép nối các câu miêu tả diễn biến liên tục thành đoạn văn hoàn chỉnh, mượt mà. TUYỆT ĐỐI KHÔNG xuống dòng sau từng câu đơn lẻ làm ngắt nát văn bản của truyện!\n"
    "12. LOẠI BỎ CHỮ RÁC WATERMARK TRANG WEB:\n"
    "    - Tự động loại bỏ hoàn toàn các chữ rác watermark của trang web Trung Quốc như 'Mì nấm phải thêm trứng', '15619 Chữ', số từ."
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

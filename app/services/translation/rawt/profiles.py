"""
app/services/translation/rawt/profiles.py
Quản lý các Profiles dịch thuật đặc thù theo từng thể loại truyện (Context-Aware Profiles)
và Bộ Quy Tắc Chuyển Ngữ Cốt Lõi Toàn Dự Án (Core Translation Philosophy).
"""
import logging

logger = logging.getLogger(__name__)

# =====================================================================
# 1. TIÊN HIỆP / HUYỀN HUYỄN / TU CHÂN / DỊ GIỚI
# =====================================================================
XIANXIA_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: TU TIÊN / TIÊN HIỆP / HUYỀN HUYỄN / CỔ PHONG / DỊ GIỚI / CAO VÕ】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Cảnh giới tu vi:\n"
        "     * 炼灵十层 dịch thành Luyện Linh thập tầng / mười tầng (Luyện Linh tam tầng, tứ tầng...)\n"
        "     * 筑基 / 金丹 / 元婴 / 化神 / 炼虚 / 合体 / 大乘 / 渡劫 dịch thành Trúc Cơ / Kim Đan / Nguyên Anh / Hóa Thần / Luyện Hư / Hợp Thể / Đại Thừa / Độ Kiếp\n"
        "     * 瓶颈 dịch thành bình cảnh / nút thắt cảnh giới\n"
        "     * 突破 / 顿悟 dịch thành đột phá / đốn ngộ\n"
        "     * 一层 / Sơ kỳ / Trung kỳ / Hậu kỳ / Đỉnh phong / Viên mãn / Đại viên mãn\n"
        "     * 半步... dịch thành Bán bộ... (Bán bộ Trúc Cơ, Bán bộ Kim Đan)\n"
        "   - Từ ngữ giang hồ & tu chân thông dụng:\n"
        "     * 好汉 dịch thành hảo hán (TUYỆT ĐỐI CẤM dịch thành 'hảo hạng')\n"
        "     * 结交好汉 dịch thành kết giao hảo hán\n"
        "   - Khái niệm & Hiện tượng tu luyện:\n"
        "     * 闭关 / 闭死关 dịch thành bế quan / bế tử quan\n"
        "     * 渡劫 / 天劫 / 雷劫 dịch thành độ kiếp / thiên kiếp / lôi kiếp\n"
        "     * 心魔 / 走火入魔 / 夺舍 / 陨落 dịch thành tâm ma / tẩu hỏa nhập ma / đoạt xá / ngã xuống (vẫn lạc)\n"
        "     * 丹田 / 识海 / 神识 / 灵气 / 灵根 / 极品灵根 dịch thành đan điền / thức hải / thần thức / linh khí / linh căn / cực phẩm linh căn\n"
        "     * 真元 / 法力 / 道心 / 道韵 / 法则 dịch thành chân nguyên / pháp lực / đạo tâm / đạo vận / pháp tắc\n"
        "   - Tiền tệ & Tài nguyên tu tiên:\n"
        "     * 灵钱 dịch thành linh tiền (Ví dụ: hai quan linh tiền, mấy trăm linh tiền)\n"
        "     * 灵石 dịch thành linh thạch (Hạ phẩm, Trung phẩm, Thượng phẩm, Cực phẩm linh thạch)\n"
        "     * 丹药 / 灵草 / 符箓 / 法宝 / 灵宝 dịch thành đan dược / linh thảo / phù lục / pháp bảo / linh bảo\n"
        "   - Môn phái & Chức phận:\n"
        "     * 宗门 / 圣地 / 洞府 / 灵宫 dịch thành tông môn / thánh địa / động phủ / Linh Cung (Thiên Tang Linh Cung)\n"
        "     * 外门/内门弟子 / 真传弟子 dịch thành ngoại môn / nội môn đệ tử / chân truyền đệ tử\n"
        "     * 执事 / 长老 / 峰主 / 宗主 / 掌门 / 老祖 dịch thành chấp sự / trưởng lão / phong chủ / tông chủ / chưởng môn / lão tổ\n"
        "     * 藏经阁 / 药园 / 擂台 / 秘境 / 试炼之地 dịch thành Tàng Kinh Các / Dược Viên / lôi đài / bí cảnh / nơi thí luyện\n"
        "   - Phân nhánh tu sĩ:\n"
        "     * 散修 / 体修 / 剑修 / 丹修 / 符修 / 阵修 / 魔修 / 妖修 / 鬼修 / 道侣 dịch thành tán tu / thể tu / kiếm tu / đan tu / phù tu / trận tu / ma tu / yêu tu / quỷ tu / đạo lữ\n"
        "   - Tên ngoại tộc / Dị giới: Phiên âm Hán-Việt chuẩn mực (Đặc Lý, Thác Bạt, Thái Lạp...)\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI TU TIÊN / TIÊN HIỆP (RÕ RÀNG, ĐÚNG THỜI ĐẠI, CẤM LỆCH LẠC):\n"
        "   - CẤM TUYỆT ĐỐI CÁC ĐẠI TỪ HIỆN ĐẠI / TEEN / PHỐ THỊ VƯỢT THỜI ĐẠI:\n"
        "     * TUYỆT ĐỐI CẤM: 'tao - mày', 'anh - em', 'chú - cháu', 'chú mày', 'ông - bà', 'tôi - bạn', 'cậu - tớ', 'tụi em', 'bọn em', 'tụi mình'!\n"
        "     * CẤM đệ tử gọi sư phụ là 'thầy', cấm xưng 'em' với sư phụ / sư huynh / sư tỷ.\n"
        "     * CẤM độc thoại nội tâm xưng 'tôi' hay 'tao' (BẮT BUỘC dùng 'ta' hoặc 'mình').\n"
        "   - BẮT BUỘC DÙNG CÁC CẶP XƯNG HÔ CHUẨN MỰC BẢN SẮC TU TIÊN:\n"
        "     * Trật tự danh xưng: [Họ/Tên] + [Chức vụ/Thân phận] (Kiều trưởng lão, Từ sư thúc, Vương chưởng môn, Triệu sư huynh, Liễu sư tỷ, Bạch tiền bối)\n"
        "     * Sư đồ: Đệ tử thưa 'Sư tôn / Sư phụ' — xưng 'Đồ nhi / Đệ tử'; Sư phụ gọi 'Đồ nhi / Ngươi / [Tên]' — xưng 'Vi sư / Ta'\n"
        "     * Đồng môn môn phái: 'Sư huynh — Sư đệ / Sư muội', 'Sư tỷ — Sư đệ / Sư muội'\n"
        "     * Bề dưới thưa Chưởng môn / Trưởng lão / Tiền bối: 'Bẩm Chưởng môn / Trưởng lão / Tiền bối' — xưng 'Đệ tử / Vãn bối / Thuộc hạ' (tập thể: 'Chúng đệ tử / Chúng thuộc hạ')\n"
        "     * Bề trên gọi kẻ dưới: 'Ngươi / Tiểu tử / Vãn bối / Các ngươi' — xưng 'Bản tọa / Lão phu / Ta'\n"
        "     * Giao tiếp ngang hàng / Người lạ / Giao chiến: 'Ta — Ngươi' (tập thể: 'chúng ta', 'các ngươi', 'bọn họ')\n"
        "     * Khẩu ngữ ngông nghênh tu chân: 'Lão tử / Ông đây / Gia gia ngươi — Tên nhãi ranh / Mạng chó của ngươi / Nghiệt súc'\n"
        "     * Tình cảm tu đạo lứa đôi: 'Chàng — Nàng / Phu quân — Nương tử / Đạo lữ', huynh muội tình thâm 'Huynh — Muội'\n"
        "     * Trần thuật ngôi ba: Dùng tên nhân vật hoặc đại từ cổ phong 'hắn, nàng, y, gã, lão giả, thiếu niên'\n"
        "     * Độc thoại nội tâm: BẮT BUỘC dùng 'ta' hoặc 'mình'\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ & DANH TỪ TRUNG TÍNH:\n"
        "     * Khóa chặt cặp đại từ: Đã chọn cặp đại từ nào trong phân đoạn thoại (ví dụ 'Ta — Ngươi' hay 'Huynh — Đệ') thì BẮT BUỘC giữ vững nhất quán 100%, TUYỆT ĐỐI CẤM nhảy đại từ lộn xộn giữa các câu thoại.\n"
        "     * Dùng danh từ chung an toàn: Khi chưa rõ vai vế của người nghe, dùng danh từ chung trung tính ('Tiền bối', 'Người lớn', 'Vị đạo hữu này'...) thay vì đoán mò đại từ cá nhân.\n"
    )
}

# =====================================================================
# 2. VÕ HIỆP / KIẾM HIỆP / GIANG HỒ TRUYỀN THỐNG / DÃ SỬ
# =====================================================================
WUXIA_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: KIẾM HIỆP / VÕ LÂM / GIANG HỒ TRUYỀN THỐNG / LỤC LÂM HẢO HÁN / THỦY HỬ / DÃ SỬ SA TRƯỜNG】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Từ vựng & Quán ngữ giang hồ:\n"
        "     * 朴刀 dịch thành phác đao (Binh khí lục lâm kinh điển, bắt buộc dịch 'phác đao', tuyệt đối cấm dịch 'bạt đao' hay 'bắp đao')\n"
        "     * 北宋 dịch thành Bắc Tống (Triều đại lịch sử, bắt buộc dịch 'Bắc Tống', cấm viết nhầm 'Bắc Sơ' hay 'Bắc Song')\n"
        "     * 好汉 dịch thành hảo hán (Ví dụ: hảo hán Lương Sơn, các vị hảo hán, hảo hán tha mạng, kết giao hảo hán — bắt buộc dịch là 'hảo hán', TUYỆT ĐỐI CẤM dịch thành 'hảo hạng' hay 'người tốt')\n"
        "     * 结交好汉 dịch thành kết giao hảo hán\n"
        "     * 火拼 dịch thành hỏa bính / thanh trừng nội bộ\n"
        "     * 矮壮 dịch thành thấp lùn vạm vỡ / lùn chắc\n"
        "     * 放...一条生路 dịch thành tha cho một đường sống / mở cho một con đường sống\n"
        "     * 牵马坠蹬 dịch thành dắt ngựa dâng yên / theo hầu trước sau\n"
        "     * 踢到铁板 dịch thành đá phải tấm sắt / đụng trúng đá tảng\n"
        "     * 灵钱 dịch thành linh tiền (hai quan linh tiền)\n"
        "     * 灵石 dịch thành linh thạch (Hạ phẩm, Trung phẩm, Thượng phẩm linh thạch)\n"
        "   - Thứ bậc cao thủ:\n"
        "     * 三流 / 二流 / 一流高手 dịch thành tam lưu / nhị lưu / nhất lưu cao thủ\n"
        "     * 顶峰 / 绝顶高手 dịch thành đỉnh phong / tuyệt đỉnh cao thủ\n"
        "     * 后天 / 先天 / 化境 / 宗师 / 大宗师 dịch thành Hậu thiên / Tiên thiên / Hóa Cảnh / Tông Sư / Đại Tông Sư\n"
        "     * 入门 / 小成 / 大成 / 圆满 dịch thành nhập môn / tiểu thành / đại thành / viên mãn\n"
        "     * 第一式 / 第一层 / 九重天 dịch thành thức thứ nhất / tầng thứ nhất / Cửu trùng thiên\n"
        "   - Kinh mạch, huyệt đạo & Chiêu thức:\n"
        "     * 任督二脉 / 气海 / 丹田 / 百会 / 涌泉 dịch thành Nhâm Đốc nhị mạch / khí hải / đan điền / Bách hội / Dũng tuyền\n"
        "     * 打通经脉 / 点穴 / 解穴 / 闭气 dịch thành đả thông kinh mạch / điểm huyệt / giải huyệt / bế khí\n"
        "     * 走火入魔 / 内力 / 真气 / 劲道 dịch thành tẩu hỏa nhập ma / nội lực / chân khí / kình đạo\n"
        "   - Cơ cấu sơn trại, bang phái & Lục lâm:\n"
        "     * 山寨 / 聚义厅 dịch thành sơn trại / tụ nghĩa sảnh\n"
        "     * 大当家 / 二当家 / 寨主 / 头领 / 先锋 / 教头 dịch thành Đại đương gia / Nhị đương gia / Trại chủ / Đầu lĩnh / Tiên phong / Giáo đầu\n"
        "     * 帮主 / 舵主 / 堂主 / 护法 / 镖局 / 镖头 dịch thành Bang chủ / Đà chủ / Đường chủ / Hộ pháp / Tiêu cục / Tiêu đầu\n"
        "     * 绿林 / 好汉聚义 / 喽啰 dịch thành lục lâm / hảo hán tụ nghĩa / tiểu lâu la\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI VÕ HIỆP / KIẾM HIỆP / LỤC LÂM / DÃ SỬ (CẤM LAI TẠP ĐƯỜNG PHỐ HIỆN ĐẠI):\n"
        "   - CẤM TUYỆT ĐỐI CÁC ĐẠI TỪ HIỆN ĐẠI VƯỢT THỜI ĐẠI:\n"
        "     * TUYỆT ĐỐI CẤM: 'tao - mày', 'anh - em', 'chú mày', 'tụi em', 'bọn em', 'tụi mình', 'ông - tôi', 'bạn'!\n"
        "     * CẤM lâu la báo cáo trại chủ / đầu lĩnh xưng 'bọn em / tụi em' (phải xưng 'chúng thuộc hạ', 'chúng tiểu nhân', 'tiểu nhân', 'thuộc hạ').\n"
        "     * CẤM hảo hán giang hồ gọi nhau là 'anh - em' kiểu hiện đại (phải gọi 'Đại ca - Hiền đệ / Tam đệ', 'Huynh - Đệ', 'Ca ca - Huynh đệ').\n"
        "     * CẤM độc thoại nội tâm xưng 'tôi' hay 'tao' (BẮT BUỘC dùng 'ta' hoặc 'mình').\n"
        "   - BẮT BUỘC DÙNG CÁC CẶP XƯNG HÔ BẢN SẮC GIANG HỒ / LỤC LÂM / SA TRƯỜNG:\n"
        "     * Trật tự danh xưng: [Họ/Tên] + [Chức vụ/Thân phận] (Tiêu bang chủ, Chu trại chủ, Vương đà chủ, Lý đại đương gia, Lâm giáo đầu, Trương tướng quân)\n"
        "     * Lâu la / Thuộc hạ thưa Trại chủ / Đầu lĩnh / Bang chủ: Thưa 'Trại chủ / Bang chủ / Đầu lĩnh / Đại ca' — Xưng 'Thuộc hạ / Tiểu nhân / Chúng thuộc hạ / Chúng tiểu nhân / Chúng tôi'\n"
        "     * Đầu lĩnh / Trại chủ gọi thuộc hạ: 'Ngươi / Các ngươi / Đám tiểu tử'\n"
        "     * Hảo hán xưng hùng / Khẩu ngữ ngông nghênh (你家爷爷, 你家老爷, 老子): 'Tống gia gia các ngươi / Gia gia các ngươi / Ông đây / Lão tử — Tên giặc cỏ / Thất phu / Các ngươi / Ngươi / Mạng chó của các ngươi' (TUYỆT ĐỐI CẤM 'mày - tao - tụi mày' trong bối cảnh cổ trang, võ hiệp, lục lâm).\n"
        "     * Tướng cướp / Lục lâm chặn đường kinh điển (此山是我开...): Dùng xưng hô giang hồ hào sảng: 'Đường này do ta mở, cây này do ta trồng... tha cho các ngươi một con đường sống... xem đại đao của Tống gia gia các ngươi / ông đây'. TUYỆT ĐỐI CẤM dịch 'Đường này là tao mở' hay 'tao tha cho tụi mày'!\n"
        "     * Quán ngữ & Số lượng nhân xưng: '俩 / 还俩 / 还他妈俩' dịch thành 'hai người / cả hai người / lại còn mẹ nó cả hai đứa nữa chứ / lại còn cả hai tên nữa chứ' (TUYỆT ĐỐI KHÔNG dịch nhầm sang 'giới tính').\n"
        "     * Giao chiến / Đối địch: 'Ta — Ngươi'\n"
        "     * Quan quân sa trường: Tướng soái gọi 'Bản tướng / Ta' — Binh sĩ thưa 'Tướng quân / Đại nhân' xưng 'Mạt tướng / Ty chức / Thuộc hạ'\n"
        "     * Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, gã, y, lão, hảo hán, hán tử, tráng sĩ'\n"
        "     * Độc thoại nội tâm: BẮT BUỘC dùng 'ta' hoặc 'mình'\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ & DANH TỪ TRUNG TÍNH:\n"
        "     * Khóa chặt cặp đại từ: Đã chọn cặp đại từ nào trong phân đoạn thoại (ví dụ 'Ta — Ngươi' hay 'Huynh — Đệ') thì BẮT BUỘC giữ vững nhất quán 100%, TUYỆT ĐỐI CẤM nhảy đại từ lộn xộn giữa các câu thoại.\n"
        "     * Dùng danh từ chung an toàn: Khi chưa rõ vai vế người nghe, dùng danh từ chung trung tính ('Bằng hữu', 'Huynh đài', 'Hảo hán'...) thay vì đoán mò đại từ cá nhân.\n"
    )
}

# =====================================================================
# 3. ĐÔ THỊ / HIỆN ĐẠI / THƯƠNG CHIẾN / VƯỜN TRƯỜNG / HÀO MÔN
# =====================================================================
URBAN_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: HIỆN ĐẠI / ĐÔ THỊ / ĐỜI THƯỜNG / VƯỜN TRƯỜNG / HÀO MÔN / THƯƠNG TRƯỜNG】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Doanh nghiệp & Thương trường:\n"
        "     * 董事长 dịch thành Chủ tịch Hội đồng quản trị (HĐQT) / Chủ tịch\n"
        "     * 总经理 / CEO dịch thành Tổng giám đốc\n"
        "     * 副总 / 部门总监 dịch thành Phó tổng / Giám đốc bộ phận\n"
        "     * 助理 / 秘书 dịch thành Trợ lý / Thư ký\n"
        "     * 股东 / 董事会 / 竞标 / 签约 dịch thành cổ đông / hội đồng quản trị / đấu thầu / ký hợp đồng\n"
        "   - Tầng lớp xã hội & Đời sống:\n"
        "     * 豪门世家 / 世家望族 dịch thành hào môn thế gia / thế gia vọng tộc\n"
        "     * 富二代 / 太子爷 dịch thành phú nhị đại (con nhà giàu) / thái tử gia\n"
        "     * 少爷 / 小姐 dịch thành thiếu gia / tiểu thư\n"
        "   - Vườn trường & Học đường:\n"
        "     * 班长 / 辅导员 dịch thành lớp trưởng / cố vấn học tập\n"
        "     * 系主任 / 校花 / 学霸 dịch thành chủ nhiệm khoa / hoa khôi trường / học bá\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI HIỆN ĐẠI / ĐÔ THỊ (TỰ NHIÊN, ĐÚNG VAI VẾ XÃ HỘI HIỆN ĐẠI):\n"
        "   - CẤM TUYỆT ĐỐI GƯỢNG GẠO CỔ TRANG TRONG HIỆN ĐẠI:\n"
        "     * TUYỆT ĐỐI CẤM: bê đại từ cổ trang vào đời thường hiện đại ('ta - ngươi', 'tại hạ - các hạ', 'huynh đài', 'bản tọa', 'tiểu nữ', 'lão phu', 'vi sư') trừ trường hợp nhân vật cố tình nói đùa, châm biếm hoặc đóng kịch.\n"
        "   - BẮT BUỘC DÙNG CÁC CẶP XƯNG HÔ CHUẨN MỰC HIỆN ĐẠI:\n"
        "     * Trật tự danh xưng: [Danh xưng/Vai vế] + [Tên] (Anh Nam, Chị Mai, Bác Hùng, Chú Tuấn, Cô Lan, Giám đốc Vương, Chủ tịch Trương)\n"
        "     * Công sở & Xã giao lịch thiệp: 'Tôi — Anh / Chị / Bạn / Sếp / Giám đốc'\n"
        "     * Bạn bè cùng trang lứa / Vườn trường: 'Cậu — Tớ', 'Mình — Cậu'\n"
        "     * Bạn bè thân thiết suồng sã hoặc cãi vã / xung đột đường phố: 'Mày — Tao'\n"
        "     * Tình cảm yêu đương hiện đại: 'Anh — Em'\n"
        "     * Quan hệ gia đình: 'Bố / Mẹ — Con', 'Ông / Bà — Cháu', 'Anh / Chị — Em'\n"
        "     * Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'anh ấy, cô ấy, cậu ấy, ông ấy, bà ấy, hắn, gã'\n"
        "     * Độc thoại nội tâm: BẮT BUỘC dùng 'tôi' hoặc 'mình'\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ:\n"
        "     * Khóa chặt cặp đại từ: Đã chọn cặp xưng hô nào giữa hai nhân vật (như 'Tôi — Anh', 'Cậu — Tớ', 'Mày — Tao') thì giữ nhất quán xuyên suốt phân đoạn, không nhảy lộn xộn.\n"
        "     * Dùng danh từ chung an toàn: Khi chưa rõ vị thế người đối thoại, dùng danh từ chức vị hoặc danh xưng trung tính lịch thiệp ('Anh', 'Chị', 'Bác', 'Vị khách này'...) thay vì xưng hô bừa bãi.\n"
    )
}

# =====================================================================
# 4. LINH DỊ / TÂM LINH / PHONG THỦY / ĐẠO MỘ / CAO VÕ HIỆN ĐẠI
# =====================================================================
URBAN_SUPERNATURAL_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: LINH DỊ / TÂM LINH DÂN GIAN / VỚT XÁC / ĐẠO MỘ / PHONG THỦY ÂM DƯƠNG / CAO VÕ / DỊ NĂNG】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Phong tục thôn dã & Ma chay lễ hiếu:\n"
        "     * 响器班 / 吹打班 dịch thành đội kèn trống ma chay / ban nhạc hiếu\n"
        "     * 办席 / 吃席 dịch thành làm cỗ / ăn cỗ / dự tiệc hiếu\n"
        "     * 出殡 / 白事 dịch thành đưa tang / việc hiếu / tang ma\n"
        "     * 老人走 dịch thành người già qua đời / quy tiên\n"
        "   - Tâm linh, nghề vớt xác & Huyền thuật:\n"
        "     * 捞尸人 dịch thành người vớt xác / thợ vớt xác\n"
        "     * 死倒 dịch thành tử đảo (thuật ngữ bản sắc nghề vớt xác chỉ xác trôi sông / xác chết đuối)\n"
        "     * 浮尸 / 沉尸 dịch thành xác trôi / xác chìm\n"
        "     * 水鬼 / 怨念 / 替死鬼 dịch thành thủy quỷ (ma nước) / oán niệm / kẻ thế mạng\n"
        "     * 开坛 / 画符 / 辟邪 / 镇煞 dịch thành khai đàn / vẽ bùa / trừ tà / trấn sát\n"
        "     * 风水 / 阴阳八卦 / 罗盘 dịch thành phong thủy / âm dương bát quái / la bàn\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI LINH DỊ / TÂM LINH / DÂN GIAN / THÔN DÃ (ĐẬM CHẤT ĐỜI THƯỜNG DÂN DÃ):\n"
        "   - CẤM TUYỆT ĐỐI: Cấm dùng xưng hô tiên hiệp cung đình xa vời ('bản tọa', 'vi thần', 'bản cung') cũng như cách gọi công sở phương Tây ('sếp', 'CEO') trong bối cảnh thôn dã/nghề cổ truyền.\n"
        "   - BẮT BUỘC DÙNG CÁC CẶP XƯNG HÔ BẢN SẮC DÂN GIAN:\n"
        "     * Quy tắc trật tự thôn dã: [Danh xưng/Vai vế] + [Tên] (Chú Tam Giang, Bác Lý, Bà Liễu, Bà Lưu, Anh Viễn Hầu, Thím Bảy, Thầy Tứ)\n"
        "     * Mẫu [Tên] + 哥哥 / 姐姐: 'Anh [Tên]', 'Chị [Tên]' (Anh Viễn Hầu, Chị A Ly)\n"
        "     * Kính trọng bậc thầy phong thủy / thợ vớt xác: Thưa 'Thầy / Chú / Bác / Tiền bối' — Xưng 'Cháu / Con / Tôi'\n"
        "     * Thợ thuyền / Bạn đường đạo mộ: 'Anh — Tôi / Em', 'Chú — Tôi / Cháu'; khi sinh tử khẩn cấp hoặc đùa cợt thô mộc dùng 'Mày — Tao'\n"
        "     * Vợ chồng lớn tuổi thôn quê: 'Bà — Tôi', 'Ông — Tôi', 'Bố nó — Mẹ nó'\n"
        "     * Làng xóm, họ hàng: 'Bác / Chú / Thím — Tôi / Cháu'\n"
        "     * Bề trên với con cháu: 'Mày / Cháu / Con' — Con cháu thưa 'Con / Cháu'\n"
        "     * Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'ông ấy, bà ấy, hắn, gã, lão nhân, thiếu niên'\n"
        "     * Độc thoại nội tâm: BẮT BUỘC dùng 'mình' hoặc 'ta' / 'tôi'\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ:\n"
        "     * Khóa chặt cặp đại từ: Đã chọn cặp xưng hô nào trong cảnh thôn dã/sinh tử (như 'Bác — Cháu', 'Anh — Tôi', 'Mày — Tao') thì giữ nhất quán 100%, không nhảy đại từ lộn xộn.\n"
        "     * Dùng danh xưng thôn quê an toàn: Dùng danh xưng theo vai vế hoặc tuổi tác ('Bác', 'Chú', 'Thím', 'Thầy').\n"
    )
}

# =====================================================================
# 5. NGÔN TÌNH / CỔ ĐẠI / ĐIỀN VĂN / CUNG ĐẤU / GIA ĐẤU / TRẠCH ĐẤU
# =====================================================================
ROMANCE_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: NGÔN TÌNH / CỔ ĐẠI / ĐIỀN VĂN / CUNG ĐẤU / GIA ĐẤU / TRẠCH ĐẤU】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Hoàng thất & Hậu cung:\n"
        "     * 太后 / 皇后 / 皇贵妃 / 贵妃 / 妃 / 嫔 / 贵人 / 常在 / 答应 dịch thành Thái hậu / Hoàng hậu / Hoàng quý phi / Quý phi / Phi / Tần / Quý nhân / Thường tại / Đáp ứng\n"
        "     * 亲王 / 郡王 / 贝勒 / 世子 / 郡主 / 格格 dịch thành Thân vương / Quận vương / Bối lặc / Thế tử / Quận chúa / Cách cách\n"
        "   - Thế gia vọng tộc & Trạch viện:\n"
        "     * 老太君 / 老夫人 dịch thành Lão thái quân / Lão phu nhân\n"
        "     * 大爷 / 二爷 / 大夫人 / 姨娘 dịch thành Đại gia / Nhị gia / Đại phu nhân / Di nương\n"
        "     * 嫡子 / 庶子 / 嫡女 / 庶女 dịch thành Đích tử / Thứ tử / Đích nữ / Thứ nữ\n"
        "     * 通房丫鬟 / 陪嫁 dịch thành Thông phòng nha hoàn / Của hồi môn\n"
        "   - Hôn nhân & Lễ nghi:\n"
        "     * 三书六礼 / 八字 / 聘礼 / 定亲 / 分家 dịch thành tam thư lục lễ / bát tự / sính lễ / đính hôn / phân gia\n"
        "   - Điền văn nông thôn:\n"
        "     * 家境贫寒 / 耕作 / 庄稼 / 赶集 dịch thành gia cảnh bần hàn / cày cấy / mùa màng / đi chợ phiên\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI CUNG ĐÌNH & KHUÊ CÁC PHONG KIẾN (CỰC KỲ KHẮC KHE VỀ TÔN TI TRẬT TỰ):\n"
        "   - CẤM TUYỆT ĐỐI CÁC ĐẠI TỪ HIỆN ĐẠI BÌNH DÂN:\n"
        "     * TUYỆT ĐỐI CẤM: Hạ nhân xưng 'em', xưng 'tôi', gọi chủ tử là 'anh / chị'.\n"
        "     * TUYỆT ĐỐI CẤM: Phu thê cổ trang/hoàng thất xưng 'anh — em' kiểu thế kỷ 21.\n"
        "     * TUYỆT ĐỐI CẤM: 'tao — mày', 'tụi em', 'bọn em', 'tụi mình' trong bối cảnh cung đình trạch môn.\n"
        "   - BẮT BUỘC DÙNG CÁC CẶP XƯNG HÔ CHUẨN MỰC TÔN TI PHONG KIẾN:\n"
        "     * Hoàng thất: Hoàng đế xưng 'Trẫm' — gọi bề tôi 'Khanh', gọi phi tử 'Ái phi / [Phong hiệu]'; Phi tử thưa 'Bệ hạ / Hoàng thượng' — xưng 'Thần thiếp / Thiếp thân'; Hoàng tử/Công chúa thưa 'Phụ hoàng / Mẫu hậu' — xưng 'Nhi thần'\n"
        "     * Chủ bộc trạch môn: Chủ tử xưng 'Bản cung / Ta' — Nha hoàn, hạ nhân thưa 'Chủ tử / Lão phu nhân / Phu nhân / Đại gia / Tiểu thư' — xưng 'Nô tỳ / Nô tài / Tiểu nhân / Lão nô'\n"
        "     * Phu thê khuê các: 'Chàng — Nàng / Phu quân — Nương tử / Thiếp thân' (điền văn nông thôn: 'Bố nó — Mẹ nó / Mình — Tôi')\n"
        "     * Huynh muội gia tộc: 'Huynh — Muội' hoặc 'Ca ca — Muội muội'\n"
        "     * Trật tự gia tộc: [Họ/Tên] + [Danh xưng/Thân phận] (Thẩm ma ma, Cố thái phó, Lục hầu gia, Tiết di nương)\n"
        "     * Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, nàng, cô nương, tiểu thư, thiếu gia'\n"
        "     * Độc thoại nội tâm: BẮT BUỘC dùng 'ta' hoặc 'mình'\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ:\n"
        "     * Khóa chặt cặp xưng hô tôn ti: Đã chọn cặp xưng hô phong kiến nào (như 'Trẫm — Ái phi', 'Bản cung — Nô tỳ', 'Chàng — Nàng') thì BẮT BUỘC giữ vững nhất quán 100%, tuyệt đối cấm nhảy lộn xộn giữa các câu thoại.\n"
    )
}

# =====================================================================
# 6. HỆ THỐNG / TRỌNG SINH / XUYÊN NHANH / VÔ ĐỊCH LƯU
# =====================================================================
SYSTEM_REINCARNATION_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: HỆ THỐNG / TRỌNG SINH / XUYÊN KHÔNG / KHOÁI XUYÊN / VÔ ĐỊCH LƯU】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Giao diện Hệ Thống & Game hóa:\n"
        "     * 【系统提示...】 dịch thành 【Hệ thống nhắc nhở... / Hệ thống thông báo...】\n"
        "     * 【被动系统加载中...】 dịch thành 【Hệ thống bị động đang tải...】\n"
        "     * 被动技能 / 主动技能 dịch thành Kỹ năng bị động / Kỹ năng chủ động\n"
        "     * 转盘 / 抽奖 / 指针 dịch thành Vòng quay / Rút thưởng / Kim chỉ\n"
        "     * 被动点 / 积分 / 新手礼包 dịch thành Điểm bị động / Điểm tích lũy / Gói quà tân thủ\n"
        "     * 属性面板 / 力量 / 敏捷 / 体质 / 精神 dịch thành Bảng thuộc tính / Sức mạnh / Nhanh nhẹn / Thể chất / Tinh thần\n"
        "     * 后天 Lv.1 / 先天 / 黄阶 / 玄阶 / 地阶 / 天阶 dịch thành Hậu Thiên Lv.1 / Tiên Thiên / Hoàng giai / Huyền giai / Địa giai / Thiên giai\n"
        "   - Bối cảnh thế giới bên ngoài: Áp dụng chuẩn thuật ngữ Hán-Việt tương ứng (Tu tiên: Luyện Linh thập tầng, Trúc Cơ, Kim Đan, bình cảnh, Thiên Tang Linh Cung; Hiện đại: Giám đốc, Trường học...)\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI HỆ THỐNG & XUYÊN KHÔNG (PHÂN MINH THEO THẾ GIỚI ĐÍCH):\n"
        "   - Giao tiếp giữa Hệ Thống & Ký chủ:\n"
        "     * Hệ Thống: Tự xưng 'Bản hệ thống / Hệ thống' — gọi người dùng là 'Ký chủ / Túc chủ'\n"
        "     * Ký chủ gọi Hệ Thống: 'Hệ thống / Ngươi' (hoặc 'mày' nếu bực bội chửi hệ thống)\n"
        "   - Bối cảnh thế giới bên ngoài (BẮT BUỘC TUÂN THỦ THEO THỜI ĐẠI CỦA THẾ GIỚI ĐÓ):\n"
        "     * NẾU XUYÊN VÀO CỔ ĐẠI / TU TIÊN / KIẾM HIỆP: Áp dụng 100% quy tắc CỔ ĐẠI ('Ta — Ngươi', 'Sư huynh — Sư đệ', 'Tiền bối — Vãn bối'). CẤM mang xưng hô 'anh - em', 'tao - mày', 'tụi em' vào giao tiếp với nhân vật bản địa cổ đại.\n"
        "     * NẾU BỐI CẢNH HIỆN ĐẠI: Áp dụng 100% quy tắc HIỆN ĐẠI ('Tôi — Cậu', 'Anh — Em', 'Mày — Tao').\n"
        "   - Trần thuật nhân vật chính: Dùng tên nhân vật hoặc 'hắn, gã'\n"
        "   - Độc thoại nội tâm: Dùng 'ta' (nếu ở cổ đại) hoặc 'mình / tôi' (nếu ở hiện đại)\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ:\n"
        "     * Khóa chặt cặp đại từ: Giữ nhất quán 100% cặp xưng hô đã chọn xuyên suốt phân đoạn, không nhảy lộn xộn đại từ giữa các câu thoại.\n"
    )
}

# =====================================================================
# 7. MẠT THẾ / KHOA HUYỄN / TINH TẾ / CƠ GIÁP / VIỄN TƯỞNG / ZOMBIE
# =====================================================================
SCI_FI_APOCALYPSE_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: MẠT THẾ / TẬN THẾ ZOMBIE / KHOA HUYỄN / TINH TẾ / CƠ GIÁP / VIỄN TƯỞNG】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Tận thế Zombie & Biến dị sinh học:\n"
        "     * 丧尸 / 丧尸潮 / 丧尸王 dịch thành Tang thi / Zombie (triều tang thi / đợt sóng zombie, Tang thi vương)\n"
        "     * 变异兽 / 晶核 / 能量晶核 dịch thành thú biến dị / tinh hạch / tinh hạch năng lượng\n"
        "     * 基因药剂 / 抗体血清 dịch thành thuốc biến đổi gen / huyết thanh kháng thể\n"
        "   - Dị năng & Cấp bậc sinh tồn:\n"
        "     * 一阶 / 二阶 / 三阶 / 四阶 dịch thành Nhất giai / Nhị giai / Tam giai / Tứ giai (hoặc Cấp 1, Cấp 2, Cấp 3...)\n"
        "     * 雷系 / 火系 / 冰系 / 空间系 / 精神系 dịch thành Hệ Lôi / Hệ Hỏa / Hệ Băng / Hệ Không Gian / Hệ Tinh Thần\n"
        "     * 觉醒者 / 异能者 dịch thành Người thức tỉnh / Dị năng giả\n"
        "   - Khoa học viễn tưởng & Tinh tế không gian:\n"
        "     * 星际战舰 / 机甲 / 空间跃迁 dịch thành chiến hạm không gian / cơ giáp (mecha) / bước nhảy không gian\n"
        "     * 光脑 / 终端 / 能量护盾 dịch thành quang não / thiết bị đầu cuối / khiên năng lượng\n"
        "     * 离子炮 / 等离子武器 dịch thành pháo ion / vũ khí plasma\n"
        "\n"
        "2. QUY TẮC XƯNG HÔ THỜI ĐẠI MẠT THẾ / KHOA HUYỄN (DỨT KHOÁT, QUÂN PHONG, SINH TỒN):\n"
        "   - CẤM: Cấm ủy mị, cấm lạm dụng đại từ cổ trang kiếm hiệp ('tại hạ', 'các hạ', 'bản tọa') trong quân đội hoặc căn cứ khoa học viễn tưởng.\n"
        "   - BẮT BUỘC DÙNG CÁC CẶP XƯNG HÔ QUÂN SỰ & SINH TỒN:\n"
        "     * Chỉ huy / Đội trưởng: Xưng 'Tôi / Ta' — gọi cấp dưới 'Cậu / Chiến sĩ / [Tên] / Các đồng chí'\n"
        "     * Cấp dưới thưa cấp trên: 'Báo cáo Chỉ huy / Đội trưởng' — xưng 'Tôi / Thuộc cấp'; Mệnh lệnh dứt khoát: 'Rõ!', 'Tuân lệnh!'\n"
        "     * Đồng đội sinh tồn ngang hàng: 'Đội trưởng — Tôi', 'Anh — Em / Tôi', 'Cậu — Tớ'\n"
        "     * Xung đột khốc liệt / Băng nhóm cướp bóc: 'Mày — Tao'\n"
        "     * Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, gã, anh ta, cô ta'\n"
        "     * Độc thoại nội tâm: BẮT BUỘC dùng 'tôi' hoặc 'mình'\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ:\n"
        "     * Khóa chặt cặp đại từ quân sự/sinh tồn: Giữ nhất quán 100% cặp xưng hô đã chọn ('Chỉ huy — Tôi', 'Đội trưởng — Thuộc cấp', 'Cậu — Tớ', 'Mày — Tao'), không nhảy lộn xộn đại từ giữa các câu thoại.\n"
    )
}

# =====================================================================
# BỘ QUY TẮC CỐT LÕI TOÀN DỰ ÁN (COMMON RULES - ÁP DỤNG CHO MỌI THỂ LOẠI)
# (LƯU Ý: QUY TẮC XƯNG HÔ ĐÃ ĐƯỢC TÁCH BIỆT & QUY ĐỊNH RIÊNG Ở TỪNG THỂ LOẠI
#  PHÍA TRÊN. YÊU CẦU CHUNG TUYỆT ĐỐI KHÔNG QUY ĐỊNH LẠI XƯNG HÔ)
# =====================================================================
COMMON_RULES = (
    "=== BỘ QUY TẮC DỊCH THUẬT CỐT LÕI & TIÊU CHUẨN AUDIOBOOK ===\n"
    "(Các quy tắc được sắp xếp theo đúng thứ tự ưu tiên từ cao xuống thấp. Mô hình tuân thủ nghiêm ngặt theo phân cấp ưu tiên này):\n"
    "\n"
    "1. CẤP ĐỘ 1 (ƯU TIÊN CAO NHẤT) — BẢO VỆ TÊN RIÊNG & DỊCH THẲNG MỘT CHIỀU:\n"
    "   - KHÓA 100% TÊN RIÊNG THEO BẢNG THỰC THỂ: Dùng thẳng duy nhất tên tiếng Việt trong Bảng thực thể ngay từ lần đầu tiên xuất hiện (ví dụ: 'Giang Hồng Phi', 'Đỗ Thiên', 'Vương Luân'). TUYỆT ĐỐI CẤM viết tên kèm ngoặc đơn đối chiếu hay để sót chữ Hán (cấm viết dạng 'Giang鸿飞 (Giang Hồng Phi)' hay 'Đỗ迁 (Đỗ Thiên)').\n"
    "   - THỰC THỂ MỚI CHƯA CÓ TRONG BẢNG: Giữ đúng âm Hán-Việt văn học quen thuộc; tuyệt đối không bẻ nghĩa đen ngô nghê.\n"
    "   - NGUYÊN TẮC CHUYỂN NGỮ THẲNG MỘT CHIỀU — KHÔNG MỞ NGOẶC ĐỐI CHIẾU:\n"
    "     * Mỗi cụm từ và tên riêng chỉ chuyển sang duy nhất một bản dịch tiếng Việt hoàn chỉnh, hòa nhập tự nhiên vào dòng chảy câu văn.\n"
    "     * Tuyệt đối không mở ngoặc đơn để chú thích nghĩa, phiên âm hay đối chiếu chữ Hán trong thân bài dịch.\n"
    "\n"
    "2. CẤP ĐỘ 2 (ƯU TIÊN VĂN PHONG) — NGUYÊN TẮC CHUYỂN NGỮ CỐT LÕI (VĂN PHONG & VIỆT HÓA CHUẨN MỰC):\n"
    "   - Ưu tiên cách diễn đạt tiếng Việt tự nhiên và đúng ngữ cảnh theo vốn từ, cách Việt hóa và lối hành văn thực tế đang được sử dụng trong phim Trung lồng tiếng, truyện Trung dịch sang tiếng Việt và văn học mạng Việt Nam; không chỉ giới hạn ở từ ngữ đời thường hay từ phổ biến, mà phải nhận diện và Việt hóa cả các từ/cụm từ ít phổ biến, thuật ngữ đặc thù thể loại và những cách diễn đạt tiếng Trung mà người Việt cần chuyển ngữ theo lối văn học mới hiểu đúng, tránh bỏ sót hoặc giữ nguyên kiểu Convert chỉ vì chúng không thuộc vốn từ thông dụng.\n"
    "   - Câu văn gãy gọn, mạch lạc, xuôi tai, trung thực với ngữ cảnh và tinh thần tác phẩm của tác giả, không tự ý phóng tác hay bịa đặt thêm bớt làm sai lệch câu chuyện.\n"
    "\n"
    "3. CẤP ĐỘ 3 — THÀNH NGỮ, TỤC NGỮ, QUÁN NGỮ & KHẨU NGỮ:\n"
    "   - THÀNH NGỮ & TỤC NGỮ PHẢI DÙNG NGUỒN TỪ DỊCH THUẬT QUEN THUỘC: Tuyệt đối không dịch convert cơ học từng chữ. Bắt buộc dùng đúng các cụm thành ngữ, tục ngữ đã được cộng đồng đọc truyện và xem phim dịch tại Việt Nam tiếp nhận quen thuộc từ trước đến nay, hoặc dịch thoát ý bằng từ ngữ thuần Việt phổ thông dễ hiểu nhất cho người đọc.\n"
    "   - THÀNH NGỮ LẠ HOẶC KHÓ HIỂU -> DỊCH THUẦN VIỆT THEO NGHĨA BÓNG: Khi gặp thành ngữ, quán ngữ, câu ví von Hán tự lạ hoắc hoặc khó hiểu, TUYỆT ĐỐI CẤM DỊCH CƠ HỌC TỪNG CHỮ TRẦN TRỤI (như các nghĩa đen trần trụi: trâu, ngựa, chó, đá...). Bắt buộc dịch thoát ý bằng từ ngữ thuần Việt thông dụng, dễ hiểu theo đúng ngữ cảnh câu chuyện để câu văn xuôi tai, đúng sắc thái nhân vật.\n"
    "   - KHẨU NGỮ, CÂU CHỬI & CÀ KHỊA HÀI HƯỚC: Đối với các câu khẩu ngữ giang hồ, câu chửi tục, chửi thề, xưng hùng xưng bá hài hước mang bản sắc truyện (như 'mẹ kiếp', 'bà nội nó', 'mẹ nó chứ', 'Tống gia gia các ngươi', 'mạng chó', 'lão tử', 'ông đây'...): Cứ dịch tự nhiên, sống động, đúng khẩu khí và sắc thái thể loại. TUYỆT ĐỐI CẤM dùng 'tao - mày - tụi mày' trong bối cảnh cổ trang / kiếm hiệp / tiên hiệp.\n"
    "   - TỪ LÓNG MẠNG (ví dụ: '装逼' = làm màu / ra oai / lên hương; '抱大腿' = bám người quyền thế / tìm chỗ dựa): Bắt buộc dịch thoát ý tự nhiên theo ngữ cảnh, tuyệt đối không để nguyên chữ Hán.\n"
    "\n"
    "4. CẤP ĐỘ 4 — TIÊU CHUẨN CON SỐ & TIỀN TỆ CHO AUDIOBOOK (TTS):\n"
    "   - QUY TẮC VIẾT BẰNG CHỮ CHO CON SỐ TRONG VĂN BẢN ĐỌC: Các con số trong câu trần thuật, đối thoại, suy nghĩ, ước tính, số tiền tệ, thời gian BẮT BUỘC VIẾT HẲN BẰNG CHỮ TIẾNG VIỆT (ví dụ: 'chín trăm đến một nghìn tám trăm', 'hai quan tiền', 'ba vạn sáu nghìn', 'vài ba người'). Điều này giúp đầu đọc TTS phát âm chuẩn ngữ điệu tiếng Việt tự nhiên.\n"
    "   - TUYỆT ĐỐI CẤM VIẾT NỬA CHỮ NỬA SỐ LAI TẠP: Nghiêm cấm các dạng lai tạp cẩu thả như 'một,800', '2 trăm'... Dạng này đầu đọc TTS sẽ phát âm sai hoặc ngắt quãng.\n"
    "   - SỐ THỨ TỰ & NĂM THÁNG: Tiêu đề chương số hoặc năm tháng cụ thể có thể dùng số Ả Rập nguyên vẹn (ví dụ: 'Chương 1', 'năm 1800').\n"
    "   - TÍNH TOÁN CHUẨN XÁC: 1 vạn = 10.000, 100 vạn = 1.000.000, không dịch nhầm bậc số lượng.\n"
    "\n"
    "5. CẤP ĐỘ 5 — TIÊU CHUẨN CHÍNH TẢ, VIẾT HOA & DẤU CÂU CHO AUDIOBOOK (TTS):\n"
    "   - CHUẨN CHÍNH TẢ TIẾNG VIỆT 100%: Viết đúng chính tả tiếng Việt, chuẩn ngữ pháp, câu văn gãy gọn mạch lạc, không có lỗi gõ phím.\n"
    "   - KHOẢNG CÁCH TỪ & VIẾT HOA CHUẨN MỰC: Mỗi từ phân cách bằng đúng MỘT dấu cách chuẩn mực. Viết hoa đúng chuẩn tên riêng nhân vật, địa danh và chữ cái đầu câu. Không chèn chữ hoa tùy tiện ở giữa từ làm hỏng từ.\n"
    "   - DẤU CÂU CHUẨN MỰC TẠO NHỊP NGẮT NGHỈ TỰ NHIÊN: Đặt dấu câu (chấm, phẩy, hai chấm, hỏi, than) sát ngay sau từ phía trước và cách từ tiếp theo đúng 1 dấu cách. Không lạm dụng dấu phẩy vụn vặt làm giọng đọc TTS bị giật cục.\n"
    "   - SẠCH 100% CHỮ HÁN GỐC & PINYIN: Toàn bộ văn bản phải sạch hoàn toàn chữ Hán và Pinyin, bản dịch phải là 100% tiếng Việt hoàn chỉnh để đầu đọc TTS phát âm trôi chảy.\n"
)

CONTEXT_PROFILES = {
    "xianxia": XIANXIA_PROFILE,
    "wuxia": WUXIA_PROFILE,
    "urban": URBAN_PROFILE,
    "modern_urban": URBAN_PROFILE,
    "urban_supernatural": URBAN_SUPERNATURAL_PROFILE,
    "romance": ROMANCE_PROFILE,
    "system_reincarnation": SYSTEM_REINCARNATION_PROFILE,
    "sci_fi_apocalypse": SCI_FI_APOCALYPSE_PROFILE,
}

def normalize_profile_key(profile_key: str) -> str:
    """
    Chuẩn hóa key thể loại từ bất kỳ chuỗi đầu vào nào (UI, Database, code, tiếng Việt có/không dấu).
    """
    if not profile_key:
        return "xianxia"

    pk = profile_key.lower().strip()

    # 1. Linh Dị / Tâm Linh / Phong Thủy / Đạo Mộ / Vớt Xác / Cao Võ Hiện Đại / Dị Năng
    if any(k in pk for k in [
        "linh dị", "linh di", "vớt xác", "vot xac", "trộm mộ", "trom mo",
        "đạo mộ", "dao mo", "phong thủy", "phong thuy", "urban_supernatural",
        "bắt ma", "bat ma", "cương thi", "cuong thi", "supernatural", "dị năng", "di nang",
        "灵异", "悬疑", "盗墓", "风水", "捉鬼", "僵尸"
    ]):
        return "urban_supernatural"

    # 2. Hệ Thống / Trọng Sinh / Xuyên Không / Khoái Xuyên / Vô Địch Lưu
    if any(k in pk for k in [
        "system_reincarnation", "system", "hệ thống", "he thong", "trọng sinh", "trong sinh",
        "xuyên không", "xuyen khong", "xuyên nhanh", "xuyen nhanh", "khoái xuyên", "khoai xuyen",
        "vô địch", "vo dich", "系统", "快穿", "重生", "无敌"
    ]):
        return "system_reincarnation"

    # 3. Mạt Thế / Khoa Huyễn / Tinh Tế / Cơ Giáp / Viễn Tưởng / Zombie
    if any(k in pk for k in [
        "sci_fi_apocalypse", "apocalypse", "sci_fi", "sci-fi", "mạt thế", "mat the",
        "tận thế", "tan the", "khoa huyễn", "khoa huyen", "viễn tưởng", "vien tuong",
        "tinh tế", "tinh te", "cơ giáp", "co giap", "zombie", "tang thi",
        "末世", "科幻", "星际", "机甲", "丧尸"
    ]):
        return "sci_fi_apocalypse"

    # 4. Ngôn Tình / Cổ Đại / Điền Văn / Cung Đấu / Gia Đấu / Trạch Đấu
    if any(k in pk for k in [
        "romance", "ngôn tình", "ngon tinh", "điền văn", "dien van", "cung đấu", "cung dau",
        "gia đấu", "gia dau", "trạch đấu", "trach dau", "nữ cường", "nu cuong",
        "thanh xuân", "thanh xuan", "hào môn thế gia", "hao mon the gia",
        "言情", "古言", "种田", "宫斗", "宅斗", "甜宠", "女频"
    ]):
        return "romance"

    # 5. Võ Lâm / Kiếm Hiệp / Giang Hồ Truyền Thống / Thủy Hử / Lục Lâm / Dã Sử
    if any(k in pk for k in [
        "wuxia", "võ hiệp", "vo hiep", "kiếm hiệp", "kiem hiep", "giang hồ", "giang ho", "võ lâm", "vo lam",
        "thủy hử", "thuy hu", "hảo hán", "hao han", "lục lâm", "luc lam", "dã sử", "da su", "sa trường", "sa truong",
        "武侠", "传统武侠", "江湖", "水浒", "梁山", "绿林"
    ]):
        return "wuxia"

    # 6. Đô Thị / Hiện Đại / Thương Chiến / Vườn Trường / Hào Môn
    if any(k in pk for k in [
        "modern_urban", "urban", "đô thị", "do thi", "hiện đại", "hien dai",
        "thương trường", "thuong truong", "thương chiến", "thuong chien",
        "vườn trường", "vuon truong", "giải trí", "giai tri", "đời thường", "doi thuong",
        "都市", "现代", "商战", "校园", "娱乐"
    ]):
        return "urban"

    # 7. Tiên Hiệp / Tu Chân / Huyền Huyễn / Cổ Phong / Dị Giới / Cao Võ Cổ Đại
    if any(k in pk for k in [
        "cao võ", "cao vo", "tu võ", "tu vo", "xianxia", "tu tiên", "tu tien",
        "tiên hiệp", "tien hiep", "huyền huyễn", "huyen huyen", "cổ phong", "co phong",
        "dị giới", "di gioi", "tu chân", "tu chan",
        "修真", "仙侠", "玄幻", "修仙", "古风", "异界", "高武"
    ]):
        return "xianxia"

    logger.warning(f"[CANH BAO] profile_key '{profile_key}' khong khop the loai nao, dang dung mac dinh 'xianxia'.")
    return "xianxia"

def get_context_profile_prompt(profile_key: str) -> str:
    normalized_key = normalize_profile_key(profile_key)
    profile = CONTEXT_PROFILES.get(normalized_key)
    if not profile:
        profile = CONTEXT_PROFILES["xianxia"]
        normalized_key = "xianxia"

    return (
        f"=== THỂ LOẠI ĐANG DỊCH: {normalized_key.upper()} ===\n"
        f"{profile['description']}\n\n{COMMON_RULES}"
    )

def get_era_pronoun_guard_prompt(profile_key: str) -> str:
    """
    Quy chuẩn chống nhầm lẫn xưng hô giữa 2 thời đại (Cổ đại vs Hiện đại).
    Gọn gàng 3-4 dòng, chống loãng prompt ở Lượt 2, giúp LLM dồn 95% sự chú ý
    vào việc quét sạch chữ Hán sót, sửa các câu dịch sai nghĩa và chuẩn hóa chính tả/số đếm.
    Áp dụng chuẩn xác cho mọi thể loại (Tiên hiệp, Võ hiệp, Đô thị, Linh dị, Ngôn tình, Hệ thống, Mạt thế...).
    """
    normalized_key = normalize_profile_key(profile_key)

    if normalized_key in ["urban", "modern_urban"]:
        return (
            "=== QUY CHUẨN XƯNG HÔ: CẤM TUYỆT ĐỐI LỆCH SANG CỔ TRANG (BỐI CẢNH HIỆN ĐẠI) ===\n"
            "- TUYỆT ĐỐI CẤM bê đại từ cổ trang vào đời thường hiện đại: Cấm 'ta - ngươi', 'tại hạ - các hạ', 'huynh đài', 'bản tọa', 'tiểu nữ', 'lão phu', 'vi sư'.\n"
            "- Dùng xưng hô đời thường, tự nhiên theo quan hệ hiện đại: 'Tôi — Anh / Chị / Bạn / Sếp', 'Cậu — Tớ', xung đột/đường phố dùng 'Mày — Tao'."
        )
    elif normalized_key in ["sci_fi_apocalypse"]:
        return (
            "=== QUY CHUẨN XƯNG HÔ: CẤM TUYỆT ĐỐI LỆCH SANG CỔ TRANG (BỐI CẢNH KHOA HUYỄN / MẠT THẾ) ===\n"
            "- TUYỆT ĐỐI CẤM đại từ cổ trang kiếm hiệp: Cấm 'tại hạ - các hạ', 'huynh đài', 'bản tọa', 'tiểu nữ'.\n"
            "- Dùng xưng hô dứt khoát quân phong & sinh tồn: 'Chỉ huy / Đội trưởng — Tôi', 'Tôi — Cậu / Chiến sĩ', xung đột dùng 'Mày — Tao'."
        )
    elif normalized_key in ["urban_supernatural"]:
        return (
            "=== QUY CHUẨN XƯNG HÔ: BẢN SẮC DÂN GIAN / THÔN DÃ (CẤM CÔNG SỞ & CỔ TRANG CUNG ĐÌNH) ===\n"
            "- CẤM đại từ cung đình xa vời ('bản tọa', 'vi thần') và cấm cách gọi công sở hiện đại ('sếp', 'CEO').\n"
            "- Dùng xưng hô mộc mạc dân dã: [Danh xưng/Vai vế] + [Tên] (Chú Tam, Bác Lý, Anh Viễn, Thím Bảy), 'Anh — Tôi', 'Bác — Cháu', suồng sã dùng 'Mày — Tao'."
        )
    elif normalized_key in ["system_reincarnation"]:
        return (
            "=== QUY CHUẨN XƯNG HÔ: HỆ THỐNG & ĐÚNG BỐI CẢNH THẾ GIỚI ===\n"
            "- Hệ thống tự xưng 'Bản hệ thống / Hệ thống' — gọi người dùng là 'Ký chủ / Túc chủ'.\n"
            "- Bối cảnh thế giới bên ngoài: Nếu là thế giới cổ đại/tu chân ➔ Áp dụng nghiêm ngặt xưng hô CỔ ĐẠI (cấm 'anh - em', 'tao - mày', 'tụi em'). Nếu là hiện đại ➔ Áp dụng xưng hô HIỆN ĐẠI (cấm 'ta - ngươi')."
        )
    else:  # xianxia, wuxia, romance (cổ đại / cung đình), etc.
        return (
            "=== QUY CHUẨN XƯNG HÔ: CẤM TUYỆT ĐỐI LỆCH THỜI ĐẠI SANG HIỆN ĐẠI (BỐI CẢNH CỔ PHONG) ===\n"
            "- TUYỆT ĐỐI CẤM các đại từ hiện đại / teen / bình dân thế kỷ 21: Cấm 'tao - mày', cấm 'anh - em' (kiểu hiện đại), cấm 'chú mày', 'tụi em', 'bọn em', 'tụi mình', 'ông - tôi'!\n"
            "- Giữ xưng hô cổ phong đúng vai vế: Huynh đệ ('Đại ca — Hiền đệ / Huynh — Đệ'), môn phái/sư đồ ('Sư tôn — Đồ nhi', 'Sư huynh — Sư đệ'), kẻ dưới thưa 'Thuộc hạ / Tiểu nhân', đối thoại 'Ta — Ngươi'."
        )


# =====================================================================
# HỆ THỐNG XÂY DỰNG PROMPT TẬP TRUNG (CENTRALIZED PROMPT BUILDERS)
# ĐẢM BẢO THỐNG NHẤT MỘT NGUỒN CHUẨN DUY NHẤT (SINGLE SOURCE OF TRUTH)
# CẢ DỊCH THƯỜNG & DỊCH SIÊU CẤP ĐỀU DÙNG CHUNG BỘ QUY TẮC NÀY
# =====================================================================

def build_standard_system_prompt(
    profile_key: str,
    prev_context_block: str = "",
    entity_prompt_block: str = "",
    custom_prompt_block: str = "",
    erotic_prompt_block: str = "",
    chap_count: int = 1,
    chap_list_str: str = ""
) -> str:
    """
    Xây dựng System Instruction chuẩn cho chế độ Dịch Thường (Single Pass).
    Tập trung toàn bộ cấu trúc phân tầng ưu tiên, bối cảnh thể loại và phân chương XML.
    """
    context_profile_prompt = get_context_profile_prompt(profile_key)
    return f"""🔴 VAI TRÒ: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- Ngôn ngữ nguồn: Tiếng Trung (RAW).
- Ngôn ngữ đầu ra: 100% Tiếng Việt hoàn chỉnh, sạch chữ Hán, câu văn trôi chảy chuẩn âm hưởng audiobook.
- Không trả lời câu hỏi hay trò chuyện ngoài lề, chỉ tập trung dịch toàn bộ nội dung.

{context_profile_prompt}
{prev_context_block}
{entity_prompt_block}
{custom_prompt_block}
{erotic_prompt_block}

=== CẤU TRÚC PHÂN CHƯƠNG XML ({chap_count} CHƯƠNG: {chap_list_str}) ===
Dịch đầy đủ lần lượt cả {chap_count} chương: {chap_list_str}.
Mỗi chương bọc trong đúng cặp thẻ XML số chương tương ứng:

<chapter_X>
Chương X: [Tên chương dịch chuẩn Tiếng Việt]

(Nội dung thân truyện đầy đủ của chương X)
</chapter_X>

Quy tắc phân chương:
1. Đối ứng 1:1 chính xác: Mỗi thẻ <chapter_X> trong bản gốc sinh ra đúng một thẻ <chapter_X> tương ứng trong bản dịch, số X trùng khớp 100%. Không gộp chương, không nhảy cóc.
2. Không cắt đôi chương: Trong một chương, dù gặp dấu chấm lửng '……' hay chuyển cảnh, tiếp tục dịch đầy đủ cho đến hết chương rồi mới đóng thẻ </chapter_X>.
3. Tiêu đề: Đứng độc lập ở dòng đầu tiên sau thẻ mở ('Chương X: [Tên chương]'), cách 1 dòng trống rồi mới đến nội dung truyện.

=== MỆNH LỆNH TỰ KIỂM TRA BẮT BUỘC TRƯỚC KHI TRẢ KẾT QUẢ (SELF-VERIFICATION) ===
Trước khi trả kết quả và đóng thẻ </chapter_X>, tự kiểm tra toàn bộ bản dịch theo đúng thứ tự ưu tiên:
- Không được sót chữ hoặc cụm tiếng Trung;
- Tên riêng tuân thủ chính xác theo Bảng thực thể;
- Câu văn tự nhiên, thuần Việt, đúng văn phong thể loại, không giữ nguyên từ convert tối nghĩa;
- Không được bỏ ý, không được tự thêm ý;
- Giữ nguyên nghĩa tác giả, câu văn trôi chảy cho Audiobook.
"""


def build_super_refine_req1_prompt(
    profile_key: str,
    chap_count: int,
    chap_list_str: str
) -> str:
    """
    Xây dựng System Instruction cho Request 1 của chế độ Dịch Siêu Cấp (Bóc tách thực thể + Dịch Demo).
    Đồng bộ 100% nguyên tắc chuyển ngữ cốt lõi chuẩn mực.
    """
    return f"""🔴 VAI TRÒ: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- Ngôn ngữ nguồn: Tiếng Trung (RAW).
- Ngôn ngữ đầu ra: 100% Tiếng Việt hoàn chỉnh, sạch chữ Hán.
- Thực hiện 2 nhiệm vụ song song trong 1 lần trả về:

PHẦN 1: BÓC TÁCH THỰC THỂ MỚI (NEW ENTITIES)
Trích xuất toàn bộ thực thể mới xuất hiện trong đoạn văn bản vào cặp thẻ <entities>:
<entities>
Tên gốc chữ Hán => Tên dịch tiếng Việt chuẩn mực
</entities>
Quy tắc:
- Chỉ lấy: Danh từ riêng (Tên người, tên địa danh, môn phái, chức vị cụ thể, công pháp, bảo vật...).
- Tuyệt đối cấm lấy: Danh từ chung, từ ngữ đời thường, số lượng, động từ, tính từ thông dụng.
- Nếu không có thực thể mới nào: Trả về <entities></entities> rỗng.

PHẦN 2: BẢN DỊCH TOÀN VĂN (VĂN PHONG & VIỆT HÓA CHUẨN MỰC):
- Dịch đầy đủ {chap_count} chương: {chap_list_str}.
- NGUYÊN TẮC CHUYỂN NGỮ CỐT LÕI:
  * Ưu tiên cách diễn đạt tiếng Việt tự nhiên và đúng ngữ cảnh theo vốn từ, cách Việt hóa và lối hành văn thực tế đang được sử dụng trong phim Trung lồng tiếng, truyện Trung dịch sang tiếng Việt và văn học mạng Việt Nam; không chỉ giới hạn ở từ ngữ đời thường hay từ phổ biến, mà phải nhận diện và Việt hóa cả các từ/cụm từ ít phổ biến, thuật ngữ đặc thù thể loại và những cách diễn đạt tiếng Trung mà người Việt cần chuyển ngữ theo lối văn học mới hiểu đúng, tránh bỏ sót hoặc giữ nguyên kiểu Convert chỉ vì chúng không thuộc vốn từ thông dụng.
  * Câu văn gãy gọn, mạch lạc, xuôi tai, trung thực với ngữ cảnh và tinh thần tác phẩm của tác giả, không tự ý phóng tác hay bịa đặt thêm bớt làm sai lệch câu chuyện.
- Mỗi chương bọc trong đúng cặp thẻ XML số chương tương ứng:

<chapter_X>
Chương X: [Tên chương dịch chuẩn Tiếng Việt]

(Nội dung thân truyện đầy đủ của chương X)
</chapter_X>
"""


def build_super_refine_req2_prompt(
    profile_key: str,
    req2_entity_block: str = "",
    prev_context_block: str = "",
    custom_prompt_block: str = "",
    erotic_prompt_block: str = "",
    chap_count: int = 1,
    chap_list_str: str = "",
    demo_text: str = "",
    first_chap_no: int = 1
) -> tuple:
    """
    Xây dựng System Instruction và User Prompt cho Request 2 của chế độ Dịch Siêu Cấp (Hiệu đính & Làm sạch).
    Sắp xếp các quy tắc hiệu đính theo đúng thứ tự ưu tiên từ cao xuống thấp (1 -> 5).
    """
    context_profile_prompt = get_context_profile_prompt(profile_key)

    req2_system_instruction = f"""🔴 VAI TRÒ: BẠN LÀ BIÊN TẬP VIÊN HIỆU ĐÍNH TIỂU THUYẾT TRUNG - VIỆT.
Nhiệm vụ của bạn là tiếp nhận bản dịch demo từ Lượt 1, sau đó tiến hành HIỆU ĐÍNH: SỬA CÁC CÂU DỊCH CONVERT / MÁY THÔ / THÀNH NGỮ LẠ BỊ DỊCH NGHĨA ĐEN THÀNH CÂU TIẾNG VIỆT TỰ NHIÊN, THUẦN VIỆT DỄ HIỂU; QUÉT SẠCH CHỮ HÁN SÓT; KHÓA THỰC THỂ VÀ GIỮ NGUYÊN 100% CÁC CÂU CHỮ ĐANG ĐÚNG.

=== THỂ LOẠI & BẢN SẮC TRUYỆN ===
{context_profile_prompt}

=== BẢNG THỰC THỂ CẦN KHÓA CHẶT 100% (ĐỐI CHIẾU THEO PHÂN NHÓM) ===
{req2_entity_block}
{prev_context_block}
{custom_prompt_block}
{erotic_prompt_block}

=== CẤU TRÚC PHÂN CHƯƠNG XML ({chap_count} CHƯƠNG: {chap_list_str}) ===
Biên tập và hoàn thiện đầy đủ lần lượt cả {chap_count} chương: {chap_list_str}.
Mỗi chương bọc trong đúng cặp thẻ XML số chương tương ứng:

<chapter_X>
Chương X: [Tên chương dịch chuẩn Tiếng Việt]

(Nội dung thân truyện hoàn thiện của chương X)
</chapter_X>

Quy tắc phân chương:
1. Đối ứng 1:1 chính xác: Mỗi thẻ <chapter_X> trong bản demo sinh ra đúng một thẻ <chapter_X> tương ứng trong bản dịch, số X trùng khớp 100%. Không gộp chương, không nhảy cóc.
2. Không cắt đôi chương: Dù gặp dấu chấm lửng '……' hay chuyển cảnh, tiếp tục biên tập đầy đủ cho đến hết chương rồi mới đóng thẻ </chapter_X>.
3. Tiêu đề: Đứng độc lập ở dòng đầu tiên sau thẻ mở ('Chương X: [Tên chương]'), cách 1 dòng trống rồi mới đến nội dung truyện.

=== BỘ QUY TẮC HIỆU ĐÍNH CỐT LÕI (SẮP XẾP THEO THỨ TỰ ƯU TIÊN TỪ CAO XUỐNG THẤP) ===

1. CẤP ĐỘ 1 (ƯU TIÊN CAO NHẤT) — QUÉT SẠCH 100% CHỮ HÁN SÓT & NGOẶC ĐỐI CHIẾU RÁC:
- Dịch sạch hoàn toàn các chữ Hán, thành ngữ hoặc từ ngữ dở dang còn sót. Toàn bộ văn bản phải là 100% tiếng Việt hoàn chỉnh.
- Xóa bỏ mọi ngoặc đơn chú thích phiên âm, giải nghĩa song ngữ hay chữ Hán trong thân bài.
- TUYỆT ĐỐI CẤM chèn bất kỳ từ tiếng Anh ngoại lai nào (như 'coarser', 'two'...).

2. CẤP ĐỘ 2 — PHÁT HIỆN CÂU DỊCH MÁY THÔ / TỪ LẠ KHÓ HIỂU & VIẾT LẠI THUẦN VIỆT DỄ HIỂU:
- Bất kỳ câu nào bị dịch máy cơ học (ghép từng từ Hán vụn vặt làm câu văn cụt lủn, cấn tai) hoặc thành ngữ, quán ngữ lạ bị dịch sát nghĩa đen trần trụi:
  ➔ BẮT BUỘC quan sát ngữ cảnh để VIẾT LẠI NGUYÊN CẢ CÂU ĐÓ thành câu văn tiếng Việt tự nhiên, thuần Việt gãy gọn, dễ hiểu theo đúng ngữ cảnh câu chuyện, nghe là hiểu ngay tức thì.
- Ưu tiên cách diễn đạt tiếng Việt tự nhiên và đúng ngữ cảnh theo vốn từ, cách Việt hóa và lối hành văn thực tế đang được sử dụng trong phim Trung lồng tiếng, truyện Trung dịch sang tiếng Việt và văn học mạng Việt Nam; không chỉ giới hạn ở từ ngữ đời thường hay từ phổ biến, mà phải nhận diện và Việt hóa cả các từ/cụm từ ít phổ biến, thuật ngữ đặc thù thể loại và những cách diễn đạt tiếng Trung mà người Việt cần chuyển ngữ theo lối văn học mới hiểu đúng, tránh bỏ sót hoặc giữ nguyên kiểu Convert chỉ vì chúng không thuộc vốn từ thông dụng.
- Câu văn gãy gọn, tự nhiên, xuôi tai, đúng nghĩa, không hoa mỹ màu mè hay gượng ép đao to búa lớn.

3. CẤP ĐỘ 3 — BẢO TOÀN NGUYÊN VẸN CÁC PHẦN ĐANG ĐÚNG (TUYỆT ĐỐI CẤM LÀM HỎNG CHỮ):
- Những câu trần thuật và đối thoại đã viết mượt mà, tự nhiên: BẮT BUỘC GIỮ NGUYÊN VẸN 100%, không xáo trộn vô ích.
- TUYỆT ĐỐI CẤM cắt rụng chữ đầu câu hoặc cuối câu (giữ nguyên vẹn mọi từ chỉ thời gian, địa điểm, trạng thái như 'Trên đường', 'phía sau'...).
- TUYỆT ĐỐI CẤM tự ý đổi tên nhân vật đã đúng trong bản demo.
- TUYỆT ĐỐI CẤM chèn dấu ngoặc kép thừa thãi vào cuối câu văn trần thuật không có hội thoại.

4. CẤP ĐỘ 4 — KHÓA 100% THỰC THỂ & XƯNG HÔ ĐÚNG THỜI ĐẠI:
- Giữ đúng tên riêng trong Bảng thực thể, không để méo mó.
- Đọc kỹ quan hệ đối thoại để sửa các câu bị đảo lộn ngôi xưng hô (kẻ mắng không để lộn thành tự mắng mình).

5. CẤP ĐỘ 5 — CHÍNH TẢ & SỐ ĐẾM AUDIOBOOK:
- Viết đúng chính tả tiếng Việt 100%, không dính lỗi gõ phím hay sai dấu.
- Các con số trong lời kể, hội thoại, tiền tệ viết bằng chữ tiếng Việt để đầu đọc Audiobook phát âm chuẩn ngữ điệu.

=== MỆNH LỆNH TỰ KIỂM TRA BẮT BUỘC TRƯỚC KHI TRẢ KẾT QUẢ ===
Trước khi đóng thẻ </chapter_X>:
- Đảm bảo 100% sạch chữ Hán và không có từ tiếng Anh;
- Mọi câu dịch máy thô / thành ngữ lạ / nghĩa đen đều đã được viết lại thành câu tiếng Việt tự nhiên, thuần Việt gãy gọn, dễ hiểu;
- Giữ nguyên cốt truyện, không cắt xén, không làm rụng mất từ ngữ của nguyên tác.
"""

    req2_user_prompt = (
        f"Dưới đây là BẢN DỊCH DEMO của các chương truyện. Hãy đóng vai trò Biên tập viên để hiệu đính: phát hiện và viết lại toàn bộ các câu dịch máy thô/nghĩa đen ngô nghê thành câu tiếng Việt tự nhiên, thuần Việt gãy gọn, dễ hiểu, quét sạch chữ Hán sót, giữ nguyên 100% các câu chữ đang đúng, không làm rụng từ và không chèn từ tiếng Anh:\n\n"
        f"<ban_dich_demo>\n{demo_text}\n</ban_dich_demo>\n\n"
        f"Trọng tâm thực thi Lượt 2 theo đúng thứ tự ưu tiên:\n"
        f"1. QUÉT SẠCH VÀ DỊCH LẠI 100% CHỮ HÁN SÓT: Dịch lại toàn bộ các chữ Hán còn sót, xóa bỏ ngoặc đối chiếu rác, không chèn từ tiếng Anh.\n"
        f"2. PHÁT HIỆN & VIẾT LẠI CÂU DỊCH MÁY THÔ / TỪ LẠ KHÓ HIỂU: Rà soát toàn bộ văn bản, bất kỳ câu nào bị dịch máy ngô nghê, chắp vá cơ học hoặc thành ngữ bị dịch nghĩa đen vô nghĩa ➔ Viết lại nguyên cả câu cho trôi chảy, nhận diện và Việt hóa các từ ít phổ biến, thuật ngữ đặc thù thể loại theo lối văn học, tránh giữ nguyên convert.\n"
        f"3. BẢO TOÀN CÁC PHẦN ĐANG ĐÚNG: Giữ nguyên các câu từ đã mượt mà, tuyệt đối không làm rụng chữ đầu/cuối câu, không đổi tên nhân vật đã đúng, không chèn ngoặc kép thừa.\n"
        f"4. SỬA LỖI ĐẢO LỘN NGÔI ĐỐI THOẠI & KHÓA THỰC THỂ: Giữ đúng tên riêng theo Bảng thực thể và đúng vai vế xưng hô.\n"
        f"5. CHÍNH TẢ & SỐ ĐẾM AUDIOBOOK: Viết chữ cho các con số để đầu đọc Audiobook phát âm chuẩn xác.\n"
        f"6. Xuất đủ từng chương trong {chap_list_str}, mỗi chương bọc trong đúng cặp thẻ XML <chapter_X> tương ứng.\n"
        f"7. Bắt đầu ngay từ thẻ <chapter_{first_chap_no}>:"
    )

    return req2_system_instruction, req2_user_prompt

"""
app/services/translation/rawt/profiles.py
Quản lý các Profiles dịch thuật đặc thù theo từng thể loại truyện (Context-Aware Profiles)
và Bộ Quy Tắc Chuyển Ngữ Cốt Lõi Toàn Dự Án (Core Translation Philosophy).
"""
import logging

logger = logging.getLogger(__name__)

# =====================================================================
# TIÊU CHUẨN CHUYỂN NGỮ MẪU (DỄ HIỂU, TỰ NHIÊN, CHUẨN XÁC)
# =====================================================================
BENCHMARK_ERROR_EXAMPLES = (
    "   - TIÊU CHUẨN CHUYỂN NGỮ MẪU (DỄ HIỂU, TỰ NHIÊN, CHUẨN XÁC):\n"
    "     * Tiêu chí DỄ HIỂU LUÔN LÀ CAO NHẤT: Đối với lời văn trần thuật, miêu tả, hành động, hay thành ngữ thông thường, hãy dịch bằng từ ngữ tiếng Việt thông dụng, tự nhiên, dễ hiểu nhất thay vì cố ép từ Hán-Việt khó hiểu.\n"
    "     * Thành ngữ & Khẩu ngữ: Dịch thoát ý mạch lạc, đúng sắc thái câu chuyện và khẩu khí nhân vật; khẩu ngữ giang hồ phóng khoáng, sinh động, không dịch cơ học từng chữ.\n"
    "     * Trung thực nghĩa gốc: Dịch chuẩn xác theo ngữ cảnh của tác giả, không tự ý phóng tác hay thêm bớt làm sai lệch câu chuyện.\n"
    "     * Bản dịch 100% tiếng Việt hoàn chỉnh: Văn bản sạch chữ Hán, số trong câu trần thuật viết bằng chữ tiếng Việt để đầu đọc audiobook (TTS) phát âm tự nhiên, trôi chảy.\n"
)

# =====================================================================
# 1. TIÊN HIỆP / HUYỀN HUYỄN / TU CHÂN / DỊ GIỚI
# =====================================================================
XIANXIA_PROFILE = {
    "description": (
        "【BẢN SẮC THỂ LOẠI: TU TIÊN / TIÊN HIỆP / HUYỀN HUYỄN / CỔ PHONG / DỊ GIỚI / CAO VÕ】\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC (THEO PHÂN LOẠI):\n"
        "   - Cảnh giới tu vi:\n"
        "     * 炼灵十层 -> Luyện Linh thập tầng / mười tầng (Luyện Linh tam tầng, tứ tầng...)\n"
        "     * 筑基 / 金丹 / 元婴 / 化神 / 炼虚 / 合体 / 大乘 / 渡劫 -> Trúc Cơ / Kim Đan / Nguyên Anh / Hóa Thần / Luyện Hư / Hợp Thể / Đại Thừa / Độ Kiếp\n"
        "     * 瓶颈 -> bình cảnh / nút thắt cảnh giới\n"
        "     * 突破 / 顿悟 -> đột phá / đốn ngộ\n"
        "     * 一层 / Sơ kỳ / Trung kỳ / Hậu kỳ / Đỉnh phong / Viên mãn / Đại viên mãn\n"
        "     * 半步... -> Bán bộ... (Bán bộ Trúc Cơ, Bán bộ Kim Đan)\n"
        "   - Khái niệm & Hiện tượng tu luyện:\n"
        "     * 闭关 / 闭死关 -> bế quan / bế tử quan\n"
        "     * 渡劫 / 天劫 / 雷劫 -> độ kiếp / thiên kiếp / lôi kiếp\n"
        "     * 心魔 / 走火入魔 / 夺舍 / 陨落 -> tâm ma / tẩu hỏa nhập ma / đoạt xá / ngã xuống (vẫn lạc)\n"
        "     * 丹田 / 识海 / 神识 / 灵气 / 灵根 / 极品灵根 -> đan điền / thức hải / thần thức / linh khí / linh căn / cực phẩm linh căn\n"
        "     * 真元 / 法力 / 道心 / 道韵 / 法则 -> chân nguyên / pháp lực / đạo tâm / đạo vận / pháp tắc\n"
        "   - Tiền tệ & Tài nguyên tu tiên:\n"
        "     * 灵钱 -> linh tiền (Ví dụ: hai quan linh tiền, mấy trăm linh tiền)\n"
        "     * 灵石 -> linh thạch (Hạ phẩm, Trung phẩm, Thượng phẩm, Cực phẩm linh thạch)\n"
        "     * 丹药 / 灵草 / 符箓 / 法宝 / 灵宝 -> đan dược / linh thảo / phù lục / pháp bảo / linh bảo\n"
        "   - Môn phái & Chức phận:\n"
        "     * 宗门 / 圣地 / 洞府 / 灵宫 -> tông môn / thánh địa / động phủ / Linh Cung (Thiên Tang Linh Cung)\n"
        "     * 外门/内门弟子 / 真传弟子 -> ngoại môn / nội môn đệ tử / chân truyền đệ tử\n"
        "     * 执事 / 长老 / 峰主 / 宗主 / 掌门 / 老祖 -> chấp sự / trưởng lão / phong chủ / tông chủ / chưởng môn / lão tổ\n"
        "     * 藏经阁 / 药园 / 擂台 / 秘境 / 试炼之地 -> Tàng Kinh Các / Dược Viên / lôi đài / bí cảnh / nơi thí luyện\n"
        "   - Phân nhánh tu sĩ:\n"
        "     * 散修 / 体修 / 剑修 / 丹修 / 符修 / 阵修 / 魔修 / 妖修 / 鬼修 / 道侣 -> tán tu / thể tu / kiếm tu / đan tu / phù tu / trận tu / ma tu / yêu tu / quỷ tu / đạo lữ\n"
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
        "     * 朴刀 -> phác đao (Binh khí lục lâm kinh điển, bắt buộc dịch 'phác đao', tuyệt đối cấm dịch 'bạt đao' hay 'bắp đao')\n"
        "     * 北宋 -> Bắc Tống (Triều đại lịch sử, bắt buộc dịch 'Bắc Tống', cấm viết nhầm 'Bắc Sơ' hay 'Bắc Song')\n"
        "     * 好汉 -> hảo hán (Ví dụ: hảo hán Lương Sơn, các vị hảo hán, hảo hán tha mạng, kết giao hảo hán — bắt buộc dịch là 'hảo hán', không dịch thành 'người tốt')\n"
        "     * 火拼 -> hỏa bính / thanh trừng nội bộ\n"
        "     * 矮壮 -> thấp lùn vạm vỡ / lùn chắc\n"
        "     * 放...一条生路 -> tha cho một đường sống / mở cho một con đường sống\n"
        "     * 牵马坠蹬 -> dắt ngựa dâng yên / theo hầu trước sau\n"
        "     * 踢到铁板 -> đá phải tấm sắt / đụng trúng đá tảng\n"
        "     * 灵钱 -> linh tiền (hai quan linh tiền)\n"
        "     * 灵石 -> linh thạch (Hạ phẩm, Trung phẩm, Thượng phẩm linh thạch)\n"
        "   - Thứ bậc cao thủ:\n"
        "     * 三流 / 二流 / 一流高手 -> tam lưu / nhị lưu / nhất lưu cao thủ\n"
        "     * 顶峰 / 绝顶高手 -> đỉnh phong / tuyệt đỉnh cao thủ\n"
        "     * 后天 / 先天 / 化境 / 宗师 / 大宗师 -> Hậu thiên / Tiên thiên / Hóa Cảnh / Tông Sư / Đại Tông Sư\n"
        "     * 入门 / 小成 / 大成 / 圆满 -> nhập môn / tiểu thành / đại thành / viên mãn\n"
        "     * 第一式 / 第一层 / 九重天 -> thức thứ nhất / tầng thứ nhất / Cửu trùng thiên\n"
        "   - Kinh mạch, huyệt đạo & Chiêu thức:\n"
        "     * 任督二脉 / 气海 / 丹田 / 百会 / 涌泉 -> Nhâm Đốc nhị mạch / khí hải / đan điền / Bách hội / Dũng tuyền\n"
        "     * 打通经脉 / 点穴 / 解穴 / 闭气 -> đả thông kinh mạch / điểm huyệt / giải huyệt / bế khí\n"
        "     * 走火入魔 / 内力 / 真气 / 劲道 -> tẩu hỏa nhập ma / nội lực / chân khí / kình đạo\n"
        "   - Cơ cấu sơn trại, bang phái & Lục lâm:\n"
        "     * 山寨 / 聚义厅 -> sơn trại / tụ nghĩa sảnh\n"
        "     * 大当家 / 二当家 / 寨主 / 头领 / 先锋 / 教头 -> Đại đương gia / Nhị đương gia / Trại chủ / Đầu lĩnh / Tiên phong / Giáo đầu\n"
        "     * 帮主 / 舵主 / 堂主 / 护法 / 镖局 / 镖头 -> Bang chủ / Đà chủ / Đường chủ / Hộ pháp / Tiêu cục / Tiêu đầu\n"
        "     * 绿林 / 好汉聚义 / 喽啰 -> lục lâm / hảo hán tụ nghĩa / tiểu lâu la\n"
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
        "     * Quán ngữ & Số lượng nhân xưng: '俩 / 还俩 / 还他妈俩' -> 'hai người / cả hai người / lại còn mẹ nó cả hai đứa nữa chứ / lại còn cả hai tên nữa chứ' (TUYỆT ĐỐI KHÔNG dịch nhầm sang 'giới tính').\n"
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
        "     * 董事长 -> Chủ tịch Hội đồng quản trị (HĐQT) / Chủ tịch\n"
        "     * 总经理 / CEO -> Tổng giám đốc\n"
        "     * 副总 / 部门总监 -> Phó tổng / Giám đốc bộ phận\n"
        "     * 助理 / 秘书 -> Trợ lý / Thư ký\n"
        "     * 股东 / 董事会 / 竞标 / 签约 -> cổ đông / hội đồng quản trị / đấu thầu / ký hợp đồng\n"
        "   - Tầng lớp xã hội & Đời sống:\n"
        "     * 豪门世家 / 世家望族 -> hào môn thế gia / thế gia vọng tộc\n"
        "     * 富二代 / 太子爷 -> phú nhị đại (con nhà giàu) / thái tử gia\n"
        "     * 少爷 / 小姐 -> thiếu gia / tiểu thư\n"
        "   - Vườn trường & Học đường:\n"
        "     * 班长 / 辅导员 -> lớp trưởng / cố vấn học tập\n"
        "     * 系主任 / 校花 / 学霸 -> chủ nhiệm khoa / hoa khôi trường / học bá\n"
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
        "     * 响器班 / 吹打班 -> đội kèn trống ma chay / ban nhạc hiếu\n"
        "     * 办席 / 吃席 -> làm cỗ / ăn cỗ / dự tiệc hiếu\n"
        "     * 出殡 / 白事 -> đưa tang / việc hiếu / tang ma\n"
        "     * 老人走 -> người già qua đời / quy tiên\n"
        "   - Tâm linh, nghề vớt xác & Huyền thuật:\n"
        "     * 捞尸人 -> người vớt xác / thợ vớt xác\n"
        "     * 死倒 -> tử đảo (thuật ngữ bản sắc nghề vớt xác chỉ xác trôi sông / xác chết đuối)\n"
        "     * 浮尸 / 沉尸 -> xác trôi / xác chìm\n"
        "     * 水鬼 / 怨念 / 替死鬼 -> thủy quỷ (ma nước) / oán niệm / kẻ thế mạng\n"
        "     * 开坛 / 画符 / 辟邪 / 镇煞 -> khai đàn / vẽ bùa / trừ tà / trấn sát\n"
        "     * 风水 / 阴阳八卦 / 罗盘 -> phong thủy / âm dương bát quái / la bàn\n"
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
        "     * 太后 / 皇后 / 皇贵妃 / 贵妃 / 妃 / 嫔 / 贵人 / 常在 / 答应 -> Thái hậu / Hoàng hậu / Hoàng quý phi / Quý phi / Phi / Tần / Quý nhân / Thường tại / Đáp ứng\n"
        "     * 亲王 / 郡王 / 贝勒 / 世子 / 郡主 / 格格 -> Thân vương / Quận vương / Bối lặc / Thế tử / Quận chúa / Cách cách\n"
        "   - Thế gia vọng tộc & Trạch viện:\n"
        "     * 老太君 / 老夫人 -> Lão thái quân / Lão phu nhân\n"
        "     * 大爷 / 二爷 / 大夫人 / 姨娘 -> Đại gia / Nhị gia / Đại phu nhân / Di nương\n"
        "     * 嫡子 / 庶子 / 嫡女 / 庶女 -> Đích tử / Thứ tử / Đích nữ / Thứ nữ\n"
        "     * 通房丫鬟 / 陪嫁 -> Thông phòng nha hoàn / Của hồi môn\n"
        "   - Hôn nhân & Lễ nghi:\n"
        "     * 三书六礼 / 八字 / 聘礼 / 定亲 / 分家 -> tam thư lục lễ / bát tự / sính lễ / đính hôn / phân gia\n"
        "   - Điền văn nông thôn:\n"
        "     * 家境贫寒 / 耕作 / 庄稼 / 赶集 -> gia cảnh bần hàn / cày cấy / mùa màng / đi chợ phiên\n"
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
        "     * 【系统提示...】 -> 【Hệ thống nhắc nhở... / Hệ thống thông báo...】\n"
        "     * 【被动系统加载中...】 -> 【Hệ thống bị động đang tải...】\n"
        "     * 被动技能 / 主动技能 -> Kỹ năng bị động / Kỹ năng chủ động\n"
        "     * 转盘 / 抽奖 / 指针 -> Vòng quay / Rút thưởng / Kim chỉ\n"
        "     * 被动点 / 积分 / 新手礼包 -> Điểm bị động / Điểm tích lũy / Gói quà tân thủ\n"
        "     * 属性面板 / 力量 / 敏捷 / 体质 / 精神 -> Bảng thuộc tính / Sức mạnh / Nhanh nhẹn / Thể chất / Tinh thần\n"
        "     * 后天 Lv.1 / 先天 / 黄阶 / 玄阶 / 地阶 / 天阶 -> Hậu Thiên Lv.1 / Tiên Thiên / Hoàng giai / Huyền giai / Địa giai / Thiên giai\n"
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
        "     * 丧尸 / 丧尸潮 / 丧尸王 -> Tang thi / Zombie (triều tang thi / đợt sóng zombie, Tang thi vương)\n"
        "     * 变异兽 / 晶核 / 能量晶核 -> thú biến dị / tinh hạch / tinh hạch năng lượng\n"
        "     * 基因药剂 / 抗体血清 -> thuốc biến đổi gen / huyết thanh kháng thể\n"
        "   - Dị năng & Cấp bậc sinh tồn:\n"
        "     * 一阶 / 二阶 / 三阶 / 四阶 -> Nhất giai / Nhị giai / Tam giai / Tứ giai (hoặc Cấp 1, Cấp 2, Cấp 3...)\n"
        "     * 雷系 / 火系 / 冰系 / 空间系 / 精神系 -> Hệ Lôi / Hệ Hỏa / Hệ Băng / Hệ Không Gian / Hệ Tinh Thần\n"
        "     * 觉醒者 / 异能者 -> Người thức tỉnh / Dị năng giả\n"
        "   - Khoa học viễn tưởng & Tinh tế không gian:\n"
        "     * 星际战舰 / 机甲 / 空间跃迁 -> chiến hạm không gian / cơ giáp (mecha) / bước nhảy không gian\n"
        "     * 光脑 / 终端 / 能量护盾 -> quang não / thiết bị đầu cuối / khiên năng lượng\n"
        "     * 离子炮 / 等离子武器 -> pháo ion / vũ khí plasma\n"
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
    "\n"
    "1. NGUYÊN TẮC DỊCH THUẬT: DỄ HIỂU TRONG TRẦN THUẬT, CHUẨN XÁC NGHĨA GỐC & TỰ NHIÊN:\n"
    "   - LỜI VĂN TRẦN THUẬT & MIÊU TẢ ➔ DỄ HIỂU LUÔN LÀ TIÊU CHÍ CAO NHẤT: Đối với lời văn trần thuật, hành động, miêu tả, động từ, tính từ thông thường: TIÊU CHÍ DỄ HIỂU LUÔN LÀ CAO NHẤT. Bắt buộc dịch bằng tiếng Việt thuần túy, tự nhiên, dễ hiểu; tuyệt đối không lạm dụng Hán-Việt nửa mùa làm câu văn gượng gạo, khó hiểu.\n"
    "   - KHI GẶP TỪ TRẦN THUẬT KHÔNG CHẮC CHẮN ➔ DỊCH DỄ HIỂU BẰNG TỪ PHỔ BIẾN: Khi bạn không biết hoặc không chắc chắn một từ ngữ trần thuật / miêu tả có phải là từ bản sắc hay không, CỨ DỊCH DỄ HIỂU BẰNG TỪ NGỮ TIẾNG VIỆT THÔNG DỤNG, PHỔ BIẾN LÀ ĐƯỢC. Tuyệt đối không cần cố gắng convert hay ép chữ khó hiểu.\n"
    "   - DỊCH THEO NGHĨA BÓNG & Ý ĐỊNH THỰC TẾ TRONG VĂN CẢNH: Rất nhiều từ ngữ, tiếng lóng hay thành ngữ có cả nghĩa đen và nghĩa bóng. Bắt buộc dịch theo ngữ cảnh và hàm ý thực tế của tác giả, không bám chấp nghĩa đen của từng chữ Hán làm câu văn tối nghĩa.\n"
    "   - TRUNG THỰC VỚI NGHĨA GỐC: Bản gốc viết gì thì dịch chuẩn xác nghĩa đó. Tuyệt đối cấm tự ý phóng tác, bịa đặt, suy diễn lung tung hay thay đổi hình ảnh gốc của tác giả.\n"
    "   - GIỚI HẠN THÊM TỪ: Chỉ được phép thêm từ nối tối thiểu khi câu gốc tiếng Trung bị cộc lốc/cụt lủn để câu văn thành câu hoàn chỉnh; ngoài ra không tự tiện thêm thắt từ ngữ làm sai lệch ý câu.\n"
    "   - TIÊU CHUẨN AUDIOBOOK: Câu từ rõ ràng, xuôi tai, nhịp điệu tự nhiên, người nghe audiobook nghe một lần là hiểu trọn vẹn nội dung.\n"
    "\n"
    "2. TIÊU CHUẨN CHÍNH TẢ, VIẾT HOA & DẤU CÂU CHO AUDIOBOOK (TTS):\n"
    "   - CHUẨN CHÍNH TẢ TIẾNG VIỆT 100%: Viết đúng chính tả tiếng Việt, chuẩn ngữ pháp, câu văn gãy gọn mạch lạc, không có lỗi gõ phím.\n"
    "   - KHOẢNG CÁCH TỪ & VIẾT HOA CHUẨN MỰC: Mỗi từ phân cách bằng đúng MỘT dấu cách chuẩn mực. Viết hoa đúng chuẩn tên riêng nhân vật, địa danh và chữ cái đầu câu. Không chèn chữ hoa tùy tiện ở giữa từ làm hỏng từ.\n"
    "   - DẤU CÂU CHUẨN MỰC TẠO NHỊP NGẮT NGHỈ TỰ NHIÊN: Đặt dấu câu (chấm, phẩy, hai chấm, hỏi, than) sát ngay sau từ phía trước và cách từ tiếp theo đúng 1 dấu cách. Không lạm dụng dấu phẩy vụn vặt làm giọng đọc TTS bị giật cục.\n"
    "   - SẠCH 100% CHỮ HÁN GỐC & PINYIN: Toàn bộ văn bản phải sạch hoàn toàn chữ Hán và Pinyin, bản dịch phải là 100% tiếng Việt hoàn chỉnh để đầu đọc TTS phát âm trôi chảy.\n"
    "\n"
    "3. TIÊU CHUẨN CON SỐ & TIỀN TỆ CHO AUDIOBOOK (TTS):\n"
    "   - QUY TẮC VIẾT BẰNG CHỮ CHO CON SỐ TRONG VĂN BẢN ĐỌC: Các con số trong câu trần thuật, đối thoại, suy nghĩ, ước tính, số tiền tệ, thời gian BẮT BUỘC VIẾT HẲN BẰNG CHỮ TIẾNG VIỆT (ví dụ: 'chín trăm đến một nghìn tám trăm', 'hai quan tiền', 'ba vạn sáu nghìn', 'vài ba người'). Điều này giúp đầu đọc TTS phát âm chuẩn ngữ điệu tiếng Việt tự nhiên.\n"
    "   - TUYỆT ĐỐI CẤM VIẾT NỬA CHỮ NỬA SỐ LAI TẠP: Nghiêm cấm các dạng lai tạp cẩu thả như 'một,800', '2 trăm'... Dạng này đầu đọc TTS sẽ phát âm sai hoặc ngắt quãng.\n"
    "   - SỐ THỨ TỰ & NĂM THÁNG: Tiêu đề chương số hoặc năm tháng cụ thể có thể dùng số Ả Rập nguyên vẹn (ví dụ: 'Chương 1', 'năm 1800').\n"
    "   - TÍNH TOÁN CHUẨN XÁC: 1 vạn = 10.000, 100 vạn = 1.000.000, không dịch nhầm bậc số lượng.\n"
    "\n"
    "4. NGUYÊN TẮC BẢO VỆ TÊN RIÊNG & THỰC THỂ CỐ ĐỊNH:\n"
    "   - KHÓA 100% TÊN RIÊNG THEO BẢNG THỰC THỂ: Dùng thẳng duy nhất tên tiếng Việt trong Bảng thực thể ngay từ lần đầu tiên xuất hiện (ví dụ: 'Giang Hồng Phi', 'Đỗ Thiên', 'Vương Luân'). TUYỆT ĐỐI CẤM viết tên kèm ngoặc đơn đối chiếu hay để sót chữ Hán (cấm viết dạng 'Giang鸿飞 (Giang Hồng Phi)' hay 'Đỗ迁 (Đỗ Thiên)').\n"
    "   - THỰC THỂ MỚI CHƯA CÓ TRONG BẢNG: Giữ đúng âm Hán-Việt văn học quen thuộc; tuyệt đối không bẻ nghĩa đen ngô nghê.\n"
    "\n"
    "5. THÀNH NGỮ, TỤC NGỮ, QUÁN NGỮ & KHẨU NGỮ:\n"
    "   - THÀNH NGỮ & TỤC NGỮ DỊCH DỄ HIỂU BẰNG TỪ NGỮ PHỔ THÔNG: Ở thành ngữ, tục ngữ thì nên dịch thoát ý dễ hiểu bằng từ ngữ phổ thông. Chỉ giữ lại dạng Hán-Việt đối với những thành ngữ đã quá quen thuộc sâu rộng trong tiếng Việt (như 'vào sinh ra tử', 'ôm cây đợi thỏ'). Khi không chắc chắn từ này có phải bản sắc quen thuộc không, CỨ DỊCH DỄ HIỂU BẰNG TỪ PHỔ BIẾN LÀ ĐƯỢC.\n"
    "   - KHẨU NGỮ, CÂU CHỬI & CÀ KHỊA HÀI HƯỚC: Đối với các câu khẩu ngữ giang hồ, câu chửi tục, chửi thề, xưng hùng xưng bá hài hước mang bản sắc truyện (như 'mẹ kiếp', 'bà nội nó', 'mẹ nó chứ', 'Tống gia gia các ngươi', 'mạng chó', 'lão tử', 'ông đây'...): Cứ dịch tự nhiên, sống động, đúng khẩu khí và sắc thái thể loại. TUYỆT ĐỐI CẤM dùng 'tao - mày - tụi mày' trong bối cảnh cổ trang / kiếm hiệp / tiên hiệp.\n"
    "   - TỪ LÓNG MẠNG (ví dụ: '装逼' = làm màu / ra oai / lên hương; '抱大腿' = bám người quyền thế / tìm chỗ dựa): Bắt buộc dịch thoát ý tự nhiên theo ngữ cảnh, tuyệt đối không để nguyên chữ Hán.\n"
    "\n"
    "6. NGUYÊN TẮC CHUYỂN NGỮ THẲNG MỘT CHIỀU — KHÔNG MỞ NGOẶC ĐỐI CHIẾU:\n"
    "   - Mỗi cụm từ và tên riêng chỉ chuyển sang duy nhất một bản dịch tiếng Việt hoàn chỉnh, hòa nhập tự nhiên vào dòng chảy câu văn.\n"
    "   - Tuyệt đối không mở ngoặc đơn để chú thích nghĩa, phiên âm hay đối chiếu chữ Hán trong thân bài dịch.\n"
)

# Bảng ánh xạ Context Profiles
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

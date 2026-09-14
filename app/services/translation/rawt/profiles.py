"""
app/services/translation/rawt/profiles.py
Quản lý các Profiles dịch thuật đặc thù theo từng thể loại truyện (Context-Aware Profiles)
và Bộ Quy Tắc Chuyển Ngữ Cốt Lõi Toàn Dự Án (Core Translation Philosophy).

Đặc điểm kiến trúc:
- Mỗi profile độc lập và đầy đủ: Khi dịch chỉ chọn 1 profile duy nhất, nên mỗi profile
  chứa trọn vẹn Bảng thuật ngữ chuyên ngành + Bảng đối chiếu nhanh xưng hô Trung -> Việt.
- Ưu tiên Cổ đại: Bắt buộc 2 âm tiết Hán-Việt/danh xưng cổ phong, cấm tự ý rút thành một chữ hiện đại.
- Hiện đại tự nhiên: Linh hoạt theo quan hệ và tuổi tác, vẫn giữ được 'ta - ngươi' hay 'mày - tao' khi giao đấu/trào phúng.
- Khóa chặt trật tự danh xưng: [Họ/Tên] + [Chức vụ/Thân phận] ở Cổ đại (Kiều trưởng lão, Lâm giáo đầu).
- Phân định rõ Tự xưng vs Cách gọi đối phương (Khóa chặt xưng 'con').
"""
import logging

logger = logging.getLogger(__name__)

# =====================================================================
# 1. TIÊN HIỆP / HUYỀN HUYỄN / TU CHÂN / DỊ GIỚI / CAO VÕ
# =====================================================================
XIANXIA_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: TU TIÊN / TIÊN HIỆP / HUYỀN HUYỄN / CỔ PHONG / DỊ GIỚI / CAO VÕ ===\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC:\n"
        "   - Cảnh giới tu vi:\n"
        "     * 炼灵十层 dịch thành Luyện Linh thập tầng / mười tầng (Luyện Linh tam tầng, tứ tầng...)\n"
        "     * 筑基 / 金丹 / 元婴 / 化神 / 炼虚 / 合体 / 大乘 / 渡劫 dịch thành Trúc Cơ / Kim Đan / Nguyên Anh / Hóa Thần / Luyện Hư / Hợp Thể / Đại Thừa / Độ Kiếp\n"
        "     * 瓶颈 dịch thành bình cảnh / nút thắt cảnh giới | 突破 / 顿悟 dịch thành đột phá / đốn ngộ\n"
        "     * 一层 / Sơ kỳ / Trung kỳ / Hậu kỳ / Đỉnh phong / Viên mãn / Đại viên mãn | 半步... dịch thành Bán bộ... (Bán bộ Kim Đan)\n"
        "   - Khái niệm & Hiện tượng tu luyện:\n"
        "     * 闭关 / 闭死关 dịch thành bế quan / bế tử quan | 渡劫 / 天劫 / 雷劫 dịch thành độ kiếp / thiên kiếp / lôi kiếp\n"
        "     * 心魔 / 走火入魔 / 夺舍 / 陨落 dịch thành tâm ma / tẩu hỏa nhập ma / đoạt xá / ngã xuống (vẫn lạc)\n"
        "     * 丹田 / 识海 / 神识 / 灵气 / 灵根 / 极品灵根 dịch thành đan điền / thức hải / thần thức / linh khí / linh căn / cực phẩm linh căn\n"
        "     * 真元 / 法力 / 道心 / 道韵 / 法则 dịch thành chân nguyên / pháp lực / đạo tâm / đạo vận / pháp tắc\n"
        "   - Tiền tệ & Tài nguyên tu tiên:\n"
        "     * 灵钱 dịch thành linh tiền (hai quan linh tiền) | 灵石 dịch thành linh thạch (Hạ phẩm, Trung phẩm, Thượng phẩm, Cực phẩm linh thạch)\n"
        "     * 丹药 / 灵草 / 符箓 / 法宝 / 灵宝 dịch thành đan dược / linh thảo / phù lục / pháp bảo / linh bảo\n"
        "   - Môn phái & Chức phận:\n"
        "     * 宗门 / 圣地 / 洞府 / 灵宫 dịch thành tông môn / thánh địa / động phủ / Linh Cung (Thiên Tang Linh Cung)\n"
        "     * 外门/内门弟子 / 真传弟子 dịch thành ngoại môn / nội môn đệ tử / chân truyền đệ tử\n"
        "     * 执事 / 长老 / 峰主 / 宗主 / 掌门 / 老祖 dịch thành chấp sự / trưởng lão / phong chủ / tông chủ / chưởng môn / lão tổ\n"
        "     * 藏经阁 / 药园 / 擂台 / 秘境 / 试炼之地 dịch thành Tàng Kinh Các / Dược Viên / lôi đài / bí cảnh / nơi thí luyện\n"
        "   - Phân nhánh tu sĩ: 散修 (tán tu), 体修 (thể tu), 剑修 (kiếm tu), 丹修 (đan tu), 符修 (phù tu), 阵修 (trận tu), 魔修 (ma tu), 妖修 (yêu tu), 鬼修 (quỷ tu), 道侣 (đạo lữ)\n"
        "   - Tên ngoại tộc / Dị giới: Phiên âm Hán-Việt chuẩn mực (Đặc Lý, Thác Bạt, Thái Lạp...)\n"
        "\n"
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG CỔ ĐẠI (TRÁNH ÉP BUỘC MÁY MÓC, TRÁNH NHẦM SÓT):\n"
        "   🔴 BỐI CẢNH NÀY LÀ CỔ ĐẠI — BẮT BUỘC DÙNG TẬP TỪ NGỮ CỔ PHONG, TUYỆT ĐỐI CẤM MỌI TỪ NGỮ HIỆN ĐẠI!\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Danh sách xưng hô dưới đây là các mẫu ví dụ phong cách tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô mang phong cách cổ đại phù hợp khác mà tôi chưa liệt kê hết được. NHƯNG các xưng hô hiện đại tôi đã cấm (và mọi từ ngữ hiện đại tương tự) thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG để tránh nhầm lẫn bối cảnh truyện!\n"
        "\n"
        "   🟢 VÙNG XƯNG HÔ CỔ ĐẠI (NÊN DÙNG — LINH HOẠT CHỌN THEO ĐÚNG NGỮ CẢNH & VAI VẾ):\n"
        "   - Đại từ & Ngôi thứ: ta, ngươi, tại hạ, các hạ, chư vị, các vị, đạo hữu, hắn, nàng, y, gã, bọn họ, chúng ta, bọn ta...\n"
        "   - Tự xưng theo thân phận: tại hạ, vãn bối, bỉ nhân, tiểu sinh, tiểu nữ, tiểu nhân, lão phu, lão hủ, bản tọa, bản tôn, vi sư, bản tông, bản tướng, mạt tướng, ty chức, thần, vi thần, hạ quan, thiếp thân, thần thiếp, nô tỳ, nô tài, bần đạo, bần tăng...\n"
        "   - Thân tộc (Ưu tiên 2 âm tiết Hán-Việt cổ phong): phụ thân, mẫu thân, nương, bá phụ, bá mẫu, thúc phụ, thúc mẫu, cô mẫu, cô phụ, cô cô, di mẫu, cữu phụ, cữu mẫu, cữu cữu, tổ phụ, tổ mẫu, ngoại tổ phụ, ngoại tổ mẫu, huynh trưởng, ca ca, đại ca, tỷ tỷ, đệ đệ, muội muội, huynh đệ, tỷ muội, phu quân, trượng phu, tướng công, thê tử, nương tử, phu nhân, nhi tử, nữ nhi, hài tử, tôn tử, tôn nữ, chất tử, chất nữ, ngoại sinh... (⚠️ Riêng thiếp/vợ lẽ: bắt buộc dùng 'di nương', cấm dịch là dì!).\n"
        "   - Sư môn & Đồng đạo: sư phụ, sư tôn, đồ nhi, đệ tử, sư huynh, sư đệ, sư tỷ, sư muội, sư thúc, sư bá, sư tổ, sư thúc tổ, chưởng môn, tông chủ, phong chủ, trưởng lão, chấp sự, tiền bối, vãn bối...\n"
        "   - Bằng hữu & Tôn xưng xã hội: huynh đài, lão huynh, hiền đệ, hiền huynh, hiền muội, tiểu huynh đệ, công tử, cô nương, thiếu gia, lão trượng, lão bá, lão giả, tráng sĩ, đạo hữu...\n"
        "   - Khẩu ngữ ngông nghênh cổ phong: Lão tử, ông đây, gia gia ngươi, tên nhãi ranh, nghiệt súc, mạng chó...\n"
        "\n"
        "   🔴 VÙNG TỪ HIỆN ĐẠI (TUYỆT ĐỐI CẤM DÙNG TRONG BỐI CẢNH CỔ ĐẠI NÀY):\n"
        "   - CẤM đại từ hiện đại: tôi, bạn, cậu, tớ, mình, anh ấy, chị ấy, mấy người, các bạn, chúng mình, tụi mình, tụi em, bọn em, tụi tao, chú mày...\n"
        "   - CẤM cách gọi thân tộc đời thường: bố, ba, mẹ, má, chú, bác, dì, cô, cậu, thím, mợ, dượng, ông nội, bà nội, ông ngoại, bà ngoại, anh, chị, em trai, em gái, chồng, vợ, con trai, con gái, cháu trai, cháu gái...\n"
        "   - CẤM gọi sư phụ là 'thầy', cấm xưng 'em' với sư phụ / sư huynh / sư tỷ.\n"
        "\n"
        "   🔴 NGUYÊN TẮC RÀ SOÁT & CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI:\n"
        "   - TRẬT TỰ DANH XƯNG BẮT BUỘC: [Họ/Tên] + [Chức vụ/Thân phận] (Kiều trưởng lão, Lâm giáo đầu, Từ sư thúc, Vương chưởng môn). TUYỆT ĐỐI CẤM đảo ngược!\n"
        "   - KHÓA CHẶT 'CON': Chỉ con ruột thưa cha mẹ mới xưng 'con'. Thưa sư phụ xưng 'đồ nhi / đệ tử', thưa tiền bối xưng 'vãn bối' (TUYỆT ĐỐI CẤM xưng 'con')!\n"
        "   - 1. TRÁNH DỊCH NHẦM TỪ CHUNG BỐI PHẬN / CHUNG GIỚI TÍNH: Bắt buộc nhìn vào từ gốc tiếng Trung trong câu để xác định đúng giới tính và vai vế thực tế (tránh nhầm nam/nữ, tránh nhầm bề trên thành ngang hàng hoặc ngược lại).\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA HOẶC CẢNH 3 NGƯỜI TRỞ LÊN: Khi hai người đang nói chuyện mà nhắc đến một người thứ ba, hoặc khi có nhiều người cùng đối thoại, phải bám chắc từ gốc để phân định rõ ai đang nói với ai và ai là người thứ ba được nhắc tới. Tuyệt đối không được nhầm đại từ của người thứ ba thành người đang đối thoại trực tiếp.\n"
        "   - 3. ĐỒNG BẬC GIỮ ĐÚNG SẮC THÁI BÌNH ĐẲNG: Đồng môn, bằng hữu cùng trang lứa xưng hô tự nhiên bình đẳng ('huynh — đệ', 'tỷ — muội', 'ta — ngươi'). Tránh khách sáo quá mức làm biến dạng quan hệ bình đẳng.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch chuẩn xác theo đúng bối cảnh CỔ ĐẠI của tác phẩm!"
    )
}

# =====================================================================
# 2. VÕ HIỆP / KIẾM HIỆP / GIANG HỒ / LỤC LÂM / THỦY HỬ / DÃ SỬ
# =====================================================================
WUXIA_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: KIẾM HIỆP / VÕ LÂM / GIANG HỒ TRUYỀN THỐNG / LỤC LÂM HẢO HÁN / THỦY HỬ / DÃ SỬ SA TRƯỜNG ===\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC:\n"
        "   - Từ vựng & Quán ngữ giang hồ kinh điển:\n"
        "     * 朴刀 dịch thành phác đao (Binh khí lục lâm kinh điển, bắt buộc dịch 'phác đao', tuyệt đối cấm dịch 'bút đao' hay 'bắp đao')\n"
        "     * 北宋 dịch thành Bắc Tống (Triều đại lịch sử, bắt buộc dịch 'Bắc Tống', cấm viết nhầm 'Bắc Sơ' hay 'Bắc Song')\n"
        "     * 汉 dịch thành hảo hán (Ví dụ: hảo hán Lương Sơn, các vị hảo hán, hảo hán tha mạng — TUYỆT ĐỐI CẤM dịch 'hảo hống' hay 'người tốt')\n"
        "     * 结纳汉 dịch thành kết giao hảo hán | 和平 dịch thành hòa bình / thanh trừng nội bộ\n"
        "     * 坐把交椅 dịch thành thắp lấn vòm vẽ / lấn chức | 使得好枪棒 dịch thành đả phái tâm sắt / đổng tráng đả từng\n"
        "     * 饶...一条性命 dịch thành tha cho một đường sống / mở cho một con đường sống\n"
        "     * 备鞍 dịch thành dắt ngựa dâng yên / theo hầu trước sau\n"
        "     * 灵钱 dịch thành linh tiền (hai quan linh tiền) | 灵石 dịch thành linh thạch\n"
        "   - Thứ bậc cao thủ:\n"
        "     * 三流 / 二流 / 一流高手 dịch thành tam lưu / nhị lưu / nhất lưu cao thủ | 巅峰 / 绝顶高手 dịch thành đỉnh phong / tuyệt đỉnh cao thủ\n"
        "     * 后天 / 先天 / 化境 / 宗师 / 大宗师 dịch thành Hậu thiên / Tiên thiên / Hóa Cảnh / Tông Sư / Đại Tông Sư\n"
        "     * 入门 / 小成 / 大成 / 圆满 dịch thành nhập môn / tiểu thành / đại thành / viên mãn\n"
        "     * 招式 / 重 / 九重天 dịch thành chiêu thức / tầng thức / Cửu trùng thiên\n"
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
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG CỔ ĐẠI (TRÁNH ÉP BUỘC MÁY MÓC, TRÁNH NHẦM SÓT):\n"
        "   🔴 BỐI CẢNH NÀY LÀ CỔ ĐẠI — BẮT BUỘC DÙNG TẬP TỪ NGỮ CỔ PHONG, TUYỆT ĐỐI CẤM MỌI TỪ NGỮ HIỆN ĐẠI!\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Danh sách xưng hô dưới đây là các mẫu ví dụ phong cách tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô mang phong cách cổ đại phù hợp khác mà tôi chưa liệt kê hết được. NHƯNG các xưng hô hiện đại tôi đã cấm (và mọi từ ngữ hiện đại tương tự) thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG để tránh nhầm lẫn bối cảnh truyện!\n"
        "\n"
        "   🟢 VÙNG XƯNG HÔ CỔ ĐẠI (NÊN DÙNG — LINH HOẠT CHỌN THEO ĐÚNG NGỮ CẢNH & VAI VẾ):\n"
        "   - Đại từ & Ngôi thứ: ta, ngươi, tại hạ, các hạ, chư vị, các vị, huynh đài, hắn, gã, y, lão, nàng, bọn họ, chúng ta, bọn ta...\n"
        "   - Bằng hữu & Hảo hán giang hồ: huynh đài, lão huynh, hiền đệ, hiền huynh, hiền muội, đại ca, nhị ca, tam ca, đại tỷ, tiểu huynh đệ, công tử, cô nương, thiếu gia, thiếu hiệp, tráng sĩ, hảo hán, lão trượng, lão bá, lão giả...\n"
        "   - Tự xưng thân phận & Sa trường: tại hạ, tại chức, tiểu nhân, lão phu, lão hủ, mạt tướng, ty chức, bản tướng, thuộc hạ, tiểu lâu la, bần đạo, bần tăng...\n"
        "   - Thân tộc (Ưu tiên 2 âm tiết Hán-Việt cổ phong): phụ thân, mẫu thân, bá phụ, bá mẫu, thúc phụ, thúc mẫu, cô mẫu, cô phụ, di mẫu, cữu phụ, cữu mẫu, tổ phụ, tổ mẫu, nhạc phụ, nhạc mẫu, huynh trưởng, ca ca, tỷ tỷ, đệ đệ, muội muội, phu quân, trượng phu, thê tử, nương tử, nhi tử, nữ nhi, hài tử... (⚠️ Riêng thiếp/vợ lẽ: bắt buộc dùng 'di nương', cấm dịch là dì!).\n"
        "   - Hảo hán xưng hùng & Chặn đường kinh điển (此山是我开...): Dùng xưng hô giang hồ hào sảng: Lão tử, ông đây, Tống gia gia các ngươi, gia gia các ngươi, tên giặc cỏ, thất phu, mạng chó... (Chặn đường: 'Đường này do ta mở, cây này do ta trồng... tha cho các ngươi một con đường sống... xem đại đao của Tống gia gia các ngươi / ông đây'. TUYỆT ĐỐI CẤM dịch 'Đường này là tao mở' hay 'tao tha cho tụi mày'!).\n"
        "   - Quán ngữ & Số lượng nhân xưng: '俩 / 还俩 / 还他妈俩' dịch thành 'hai người / cả hai người / lại còn mẹ nó cả hai đứa nữa chứ / lại còn cả hai tên nữa chứ' (TUYỆT ĐỐI KHÔNG dịch nhầm sang 'giới tính').\n"
        "   - Giao chiến / Đối địch: 'Ta — Ngươi'.\n"
        "   - Quan quân sa trường: Tướng soái gọi 'Bản tướng / Ta' — Binh sĩ thưa 'Tướng quân / Đại nhân' xưng 'Mạt tướng / Ty chức / Thuộc hạ'.\n"
        "   - Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, gã, y, lão, hảo hán, hán tử, tráng sĩ'.\n"
        "   - Độc thoại nội tâm: BẮT BUỘC dùng 'ta' hoặc 'mình'.\n"
        "\n"
        "   🔴 VÙNG TỪ HIỆN ĐẠI (TUYỆT ĐỐI CẤM DÙNG TRONG BỐI CẢNH CỔ ĐẠI NÀY):\n"
        "   - TUYỆT ĐỐI CẤM: 'tao - mày', 'anh - em', 'chú mày', 'tụi em', 'bọn em', 'tụi mình', 'ông - tôi', 'bạn'!\n"
        "   - CẤM lâu la báo cáo trại chủ / đầu lĩnh xưng 'bọn em / tụi em' (phải xưng 'chúng thuộc hạ', 'chúng tiểu nhân', 'tiểu nhân', 'thuộc hạ').\n"
        "   - CẤM hảo hán giang hồ gọi nhau là 'anh - em' kiểu hiện đại (phải gọi 'Đại ca - Hiền đệ / Tam đệ', 'Huynh - Đệ', 'Ca ca - Huynh đệ').\n"
        "   - CẤM độc thoại nội tâm xưng 'tôi' hay 'tao' (BẮT BUỘC dùng 'ta' hoặc 'mình').\n"
        "\n"
        "   🔴 NGUYÊN TẮC RÀ SOÁT & CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI:\n"
        "   - TRẬT TỰ DANH XƯNG BẮT BUỘC: [Họ/Tên] + [Chức vụ/Thân phận] (Tiêu bang chủ, Chu trại chủ, Vương đà chủ, Lý đại đương gia, Lâm giáo đầu, Trương tướng quân).\n"
        "   - NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ & DANH TỪ TRUNG TÍNH:\n"
        "     * Khóa chặt cặp đại từ: Đã chọn cặp đại từ nào trong phân đoạn thoại (ví dụ 'Ta — Ngươi' hay 'Huynh — Đệ') thì BẮT BUỘC giữ vững nhất quán 100%, TUYỆT ĐỐI CẤM nhảy đại từ lộn xộn giữa các câu thoại.\n"
        "     * Dùng danh từ chung an toàn: Khi chưa rõ vai vế người nghe, dùng danh từ chung trung tính ('Bằng hữu', 'Huynh đài', 'Hảo hán'...) thay vì đoán mò đại từ cá nhân.\n"
        "   - 1. TRÁNH DỊCH NHẦM TỪ CHUNG BỐI PHẬN / CHUNG GIỚI TÍNH: Bắt buộc nhìn vào từ gốc tiếng Trung trong câu để xác định đúng giới tính và vai vế thực tế (tránh nhầm nam/nữ, tránh nhầm bề trên thành ngang hàng hoặc ngược lại).\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA HOẶC CẢNH 3 NGƯỜI TRỞ LÊN: Khi hai người đang nói chuyện mà nhắc đến một người thứ ba, hoặc khi có nhiều người cùng đối thoại, phải bám chắc từ gốc để phân định rõ ai đang nói với ai và ai là người thứ ba được nhắc tới. Tuyệt đối không được nhầm đại từ của người thứ ba thành người đang đối thoại trực tiếp.\n"
        "   - 3. ĐỒNG BẬC GIỮ ĐÚNG SẮC THÁI BÌNH ĐẲNG: Đồng môn, huynh đệ hảo hán xưng hô tự nhiên bình đẳng ('huynh — đệ', 'ta — ngươi'). Tránh khách sáo quá mức làm biến dạng quan hệ bình đẳng.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch chuẩn xác theo đúng bối cảnh CỔ ĐẠI / VÕ HIỆP của tác phẩm!"
    )
}

# =====================================================================
# 3. ĐÔ THỊ / HIỆN ĐẠI / THƯƠNG CHIẾN / VƯỜN TRƯỜNG / HÀO MÔN
# =====================================================================
URBAN_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: HIỆN ĐẠI / ĐÔ THỊ / ĐỜI THƯỜNG / VƯỜN TRƯỜNG / HÀO MÔN / THƯƠNG TRƯỜNG ===\n"
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
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG HIỆN ĐẠI (TRÁNH ÉP BUỘC MÁY MÓC, TRÁNH NHẦM SÓT):\n"
        "   🔴 BỐI CẢNH NÀY LÀ HIỆN ĐẠI — BẮT BUỘC DÙNG TẬP TỪ NGỮ ĐỜI THƯỜNG HIỆN ĐẠI, TUYỆT ĐỐI CẤM GƯỢNG ÉP ĐẠI TỪ CỔ PHONG TRONG SINH HOẠT!\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Danh sách dưới đây là các mẫu ví dụ đời thường tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô hiện đại tự nhiên phù hợp khác mà tôi chưa liệt kê hết được. NHƯNG các xưng hô cổ trang kiếm hiệp đã bị cấm (và mọi từ ngữ tương tự) thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG vào sinh hoạt đời thường để tránh nhầm lẫn bối cảnh truyện!\n"
        "\n"
        "   🟢 VÙNG XƯNG HÔ HIỆN ĐẠI (NÊN DÙNG — LINH HOẠT CHỌN THEO QUAN HỆ & TUỔI TÁC):\n"
        "   - Đại từ & Ngôi thứ đời thường: tôi, mình, tớ, em, cháu, anh, chị, bạn, cậu, chú, bác, cô, dì, mọi người, chúng tôi, chúng ta, chúng mình, các bạn, các anh, các chị...\n"
        "   - Xung đột đường phố / cãi vã thô bạo: mày — tao.\n"
        "   - Gia đình hiện đại: bố, ba, mẹ, má, ông, bà, chú, bác, cô, dì, cậu, thím, mợ, dượng, anh, chị, em, con, cháu. Vợ chồng: chồng, ông xã, vợ, bà xã, mình...\n"
        "   - Học đường & Công sở: thầy, cô, bạn, bạn học, học trò, sếp, giám đốc, chủ tịch, phó tổng, trưởng phòng, trợ lý, thư ký, đồng nghiệp, đối tác, ngài, ông, bà, cô, tiểu thư...\n"
        "   - TRẬT TỰ DANH XƯNG HIỆN ĐẠI: [Danh xưng/Vai vế] + [Tên] (Anh Nam, Chị Mai, Bác Hùng, Chú Tuấn, Giám đốc Vương, Chủ tịch Trương).\n"
        "\n"
        "   🔴 VÙNG TỪ CỔ TRANG (TUYỆT ĐỐI CẤM GƯỢNG ÉP VÀO SINH HOẠT CÔNG SỞ, ĐỜI THƯỜNG HIỆN ĐẠI):\n"
        "   - CẤM đại từ cổ phong trong đời thường: ta — ngươi, tại hạ, các hạ, huynh đài, bản tọa, bản tôn, tiểu nữ, lão phu, vi sư, bần đạo, thiếp thân...\n"
        "   - NGOẠI LỆ ĐẶC BIỆT: Trong các phân cảnh tỉ thí võ thuật, cao võ hiện đại, đấu kiếm hoặc trào phúng châm biếm, nhân vật VẪN CÓ THỂ dùng 'Ta — Ngươi' hoặc xưng hô võ thuật nếu phù hợp tính cách.\n"
        "\n"
        "   🔴 NGUYÊN TẮC RÀ SOÁT & CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI:\n"
        "   - 1. TRÁNH DỊCH NHẦM TỪ CHUNG BỐI PHẬN / CHUNG GIỚI TÍNH: Bắt buộc nhìn vào từ gốc tiếng Trung trong câu để xác định đúng giới tính và vai vế thực tế (tránh nhầm nam/nữ, tránh nhầm bề trên thành ngang hàng hoặc ngược lại).\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA HOẶC CẢNH 3 NGƯỜI TRỞ LÊN: Khi hai người đang nói chuyện mà nhắc đến một người thứ ba, hoặc khi có nhiều người cùng đối thoại trong phòng/công ty, phải bám chắc từ gốc để phân định rõ ai đang nói với ai và ai là người thứ ba được nhắc tới. Tuyệt đối không được nhầm đại từ của người thứ ba thành người đang đối thoại trực tiếp.\n"
        "   - 3. ĐỒNG BẬC GIỮ ĐÚNG SẮC THÁI BÌNH ĐẲNG: Đồng nghiệp, bạn bè cùng trang lứa thì xưng hô tự nhiên bình đẳng ('tôi — bạn', 'cậu — tớ', 'anh — em'). Tránh khách sáo quá mức làm biến dạng quan hệ bình đẳng.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch chuẩn xác theo đúng bối cảnh HIỆN ĐẠI của tác phẩm!"
    )
}

# =====================================================================
# 4. LINH DỊ / TÂM LINH / PHONG THỦY / ĐẠO MỘ / CAO VÕ HIỆN ĐẠI
# =====================================================================
URBAN_SUPERNATURAL_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: LINH DỊ / TÂM LINH DÂN GIAN / VỚT XÁC / ĐẠO MỘ / PHONG THỦY ÂM DƯƠNG / CAO VÕ / DỊ NĂNG ===\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC:\n"
        "   - Phong tục thôn dã & Ma chay lễ hiếu:\n"
        "     * 响器班 / 吹打班 dịch thành đội kèn trống ma chay / ban nhạc hiếu | 办席 / 吃席 dịch thành làm cỗ / ăn cỗ / dự tiệc hiếu\n"
        "     * 出殡 / 白事 dịch thành đưa tang / việc hiếu / tang ma | 老人走 dịch thành người già qua đời / quy tiên\n"
        "   - Tâm linh, nghề vớt xác & Huyền thuật:\n"
        "     * 捞尸人 dịch thành người vớt xác / thợ vớt xác | 死倒 dịch thành tử đảo (thuật ngữ nghề chỉ xác trôi sông / xác chết đuối)\n"
        "     * 浮尸 / 沉尸 dịch thành xác trôi / xác chìm | 水鬼 / 怨念 / 替死鬼 dịch thành thủy quỷ (ma nước) / oán niệm / kẻ thế mạng\n"
        "     * 开坛 / 画符 / 辟邪 / 镇煞 dịch thành khai đàn / vẽ bùa / trừ tà / trấn sát | 风水 / 阴阳八卦 / 罗盘 dịch thành phong thủy / âm dương bát quái / la bàn\n"
        "\n"
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG DÂN GIAN / THÔN DÃ / HUYỀN THUẬT (TRÁNH ÉP BUỘC MÁY MÓC, TRÁNH NHẦM SÓT):\n"
        "   🔴 BỐI CẢNH DÂN GIAN THÔN DÃ / ĐẠO MỘ / HUYỀN THUẬT: MỘC MẠC, ĐỜI THƯỜNG, ĐẬM CHẤT NÔNG THÔN TRUYỀN THỐNG:\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Danh sách dưới đây là các mẫu ví dụ mộc mạc dân gian tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ theo các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô dân gian phù hợp khác mà tôi chưa liệt kê hết được. NHƯNG các xưng hô cung đình/tiên hiệp hay công sở xa vời đã bị cấm thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG để tránh nhầm lẫn bối cảnh truyện!\n"
        "\n"
        "   🟢 VÙNG XƯNG HÔ DÂN GIAN THÔN DÃ (NÊN DÙNG — LINH HOẠT CHỌN THEO ĐÚNG VAI VẾ):\n"
        "   - Xưng hô làng xóm & thợ thuyền: Chú, Bác, Cô, Dì, Thím, Thầy, Cậu, Anh, Chị, Em, Cháu, Tôi, Tao, Mày...\n"
        "   - TRẬT TỰ THÔN DÃ BẮT BUỘC: [Danh xưng/Vai vế] + [Tên] (Chú Tam Giang, Bác Lý, Bà Liễu, Bà Lưu, Anh Viễn Hầu, Thím Bảy, Thầy Tứ).\n"
        "   - Kính trọng thầy phong thủy / thợ vớt xác: Thưa 'Thầy / Chú / Bác / Tiền bối' — Xưng 'Cháu / Tôi' (hoặc 'Con' nếu là con cháu trong nhà/đã bái sư).\n"
        "   - Bạn đường đạo mộ / thợ thuyền sinh tồn: 'Anh — Tôi / Em', 'Chú — Tôi / Cháu'; lúc hiểm nguy hoặc thô mộc dùng 'Mày — Tao'.\n"
        "   - Trần thuật: ông ấy, bà ấy, hắn, gã, lão nhân, thiếu niên. Độc thoại: 'mình' hoặc 'ta' / 'tôi'.\n"
        "\n"
        "   🔴 VÙNG TỪ CẤM (TUYỆT ĐỐI CẤM TRONG THÔN DÃ / HUYỀN THUẬT DÂN GIAN):\n"
        "   - CẤM đại từ cung đình xa vời ('bản tọa', 'vi thần', 'bản cung', 'trẫm') và cấm danh xưng công sở ('sếp', 'CEO', 'giám đốc') trong bối cảnh thôn dã, phường thợ cổ truyền.\n"
        "\n"
        "   🔴 NGUYÊN TẮC RÀ SOÁT & CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI:\n"
        "   - 1. TRÁNH DỊCH NHẦM TỪ CHUNG BỐI PHẬN / CHUNG GIỚI TÍNH: Bắt buộc nhìn vào từ gốc tiếng Trung trong câu để xác định đúng vai vế và giới tính (tránh nhầm cô/chú, thím/bác, bề trên/ngang hàng).\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA HOẶC CẢNH 3 NGƯỜI TRỞ LÊN: Khi hai người đang nói chuyện mà nhắc đến một người thứ ba, hoặc khi nhiều người cùng đối thoại quanh hiện trường/thôn xóm, phải bám chắc từ gốc để phân định rõ ai đang nói với ai và ai là người thứ ba được nhắc tới.\n"
        "   - 3. ĐỒNG BẬC GIỮ ĐÚNG BÌNH ĐẲNG: Bạn đồng hành, thợ ngang hàng xưng hô sòng phẳng ('anh — em', 'tôi — anh', 'mày — tao'), không khúm núm hạ mình quá mức làm biến dạng bối phận.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch theo đúng ngữ cảnh mộc mạc dân gian!"
    )
}

# =====================================================================
# 5. NGÔN TÌNH / CỔ ĐẠI / ĐIỀN VĂN / CUNG ĐẤU / GIA ĐẤU / TRẠCH ĐẤU
# =====================================================================
ROMANCE_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: NGÔN TÌNH / CỔ ĐẠI / ĐIỀN VĂN / CUNG ĐẤU / GIA ĐẤU / TRẠCH ĐẤU ===\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC:\n"
        "   - Hoàng thất & Hậu cung:\n"
        "     * 太后 / 皇后 / 皇贵妃 / 贵妃 / 妃 / 嫔 / 贵人 / 常在 / 答应 dịch thành Thái hậu / Hoàng hậu / Hoàng quý phi / Quý phi / Phi / Tần / Quý nhân / Thường tại / Đáp ứng\n"
        "     * 亲王 / 郡王 / 贝勒 / 世子 / 郡主 / 格格 dịch thành Thân vương / Quận vương / Bối lặc / Thế tử / Quận chúa / Cách cách\n"
        "   - Thế gia vọng tộc & Trạch viện:\n"
        "     * 老太君 / 老夫人 dịch thành Lão thái quân / Lão phu nhân | 大爷 / 二爷 / 大夫人 dịch thành Đại gia / Nhị gia / Đại phu nhân\n"
        "     * 姨娘 dịch thành Di nương (vợ lẽ/thiếp — TUYỆT ĐỐI CẤM dịch 'di nương' thành 'dì'!)\n"
        "     * 嫡子 / 庶子 / 嫡女 / 庶女 dịch thành Đích tử / Thứ tử / Đích nữ / Thứ nữ\n"
        "     * 通房丫鬟 / 陪嫁 dịch thành Thông phòng nha hoàn / Của hồi môn\n"
        "   - Hôn nhân & Lễ nghi: 三书六礼 (tam thư lục lễ), 八字 (bát tự), 聘礼 (sính lễ), 定亲 (đính hôn), 分家 (phân gia)\n"
        "   - Điền văn nông thôn: 家境贫寒 (gia cảnh bần hàn), 耕作 (cày cấy), 庄稼 (mùa màng), 赶集 (đi chợ phiên)\n"
        "\n"
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG CỔ ĐẠI (TRÁNH ÉP BUỘC MÁY MÓC, TRÁNH NHẦM SÓT):\n"
        "   🔴 BỐI CẢNH NÀY LÀ CỔ ĐẠI — BẮT BUỘC DÙNG TẬP TỪ NGỮ CỔ PHONG, TUYỆT ĐỐI CẤM MỌI TỪ NGỮ HIỆN ĐẠI!\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Danh sách xưng hô dưới đây là các mẫu ví dụ phong cách tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô mang phong cách cổ đại phù hợp khác mà tôi chưa liệt kê hết được. NHƯNG các xưng hô hiện đại tôi đã cấm (và mọi từ ngữ hiện đại tương tự) thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG để tránh nhầm lẫn bối cảnh truyện!\n"
        "\n"
        "   🟢 VÙNG XƯNG HÔ CỔ ĐẠI (NÊN DÙNG — LINH HOẠT CHỌN THEO ĐÚNG NGỮ CẢNH & VAI VẾ):\n"
        "   - Hoàng thất & Triều đình: Trẫm, Bệ hạ, Thánh thượng, Bản cung, Thần thiếp, Thiếp thân, Nhi thần, Thần, Vi thần, Hạ quan, Điện hạ, Vương gia, Vương phi, Quý phi, Công chúa, Thế tử...\n"
        "   - Chủ bộc & Hạ nhân: Nha hoàn, ma ma, thái giám, thị vệ xưng 'Nô tỳ / Nô tài / Tiểu nhân' (thưa Chủ tử, Lão phu nhân, Phu nhân, Thiếu gia, Tiểu thư). TUYỆT ĐỐI CẤM xưng 'em, tôi'.\n"
        "   - Thân tộc & Khuê các (Ưu tiên 2 âm tiết Hán-Việt cổ phong): phụ thân, mẫu thân, nương, bá phụ, bá mẫu, thúc phụ, thúc mẫu, cô mẫu, cô phụ, di mẫu, cữu phụ, cữu mẫu, tổ phụ, tổ mẫu, lão thái quân, lão phu nhân, huynh trưởng, ca ca, đại ca, tỷ tỷ, đệ đệ, muội muội, nhi tử, nữ nhi, hài tử, tôn tử, tôn nữ... (⚠️ Riêng thiếp/vợ lẽ: bắt buộc dùng 'di nương', cấm dịch là dì!).\n"
        "   - Phu thê khuê các: chàng — nàng, phu quân / tướng công — nương tử / phu nhân / thiếp thân (Điền văn: Bố nó — Mẹ nó / Mình — Tôi). TUYỆT ĐỐI CẤM xưng 'anh — em' kiểu thế kỷ 21.\n"
        "\n"
        "   🔴 VÙNG TỪ HIỆN ĐẠI (TUYỆT ĐỐI CẤM DÙNG TRONG BỐI CẢNH CỔ ĐẠI NÀY):\n"
        "   - CẤM đại từ hiện đại: tôi, bạn, cậu, tớ, mình, anh ấy, chị ấy, mấy người, các bạn, chúng mình, tụi mình, tụi em, bọn em, chú mày...\n"
        "   - CẤM cách gọi thân tộc đời thường: bố, ba, mẹ, má, chú, bác, dì, cô, cậu, thím, mợ, dượng, ông nội, bà nội, anh, chị, em trai, em gái, chồng, vợ, con trai, con gái...\n"
        "   - CẤM cách xưng hô khuê các hiện đại: 'anh — em' giữa đôi lứa phong kiến, 'em — tôi' giữa hạ nhân với chủ tử.\n"
        "\n"
        "   🔴 NGUYÊN TẮC RÀ SOÁT & CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI:\n"
        "   - TRẬT TỰ GIA TỘC BẮT BUỘC: [Họ/Tên] + [Danh xưng/Thân phận] (Thẩm ma ma, Cố thái phó, Lục hầu gia, Tiết di nương). TUYỆT ĐỐI CẤM đảo!\n"
        "   - KHÓA CHẶT 'CON': Chỉ con ruột thưa cha mẹ mới xưng 'con'. Thưa quan trên/bề trên xưng 'tiểu nhân / hạ dân / thảo dân / thảo nữ / dân nữ'.\n"
        "   - NẾU LÀ NGÔN TÌNH HIỆN ĐẠI (Đô thị / Hào môn hiện đại): Tự động chuyển sang xưng hô HIỆN ĐẠI: 'Tôi — Anh / Em / Cậu / Sếp', 'Anh — Em'.\n"
        "   - 1. TRÁNH DỊCH NHẦM TỪ CHUNG BỐI PHẬN / CHUNG GIỚI TÍNH: Bắt buộc nhìn vào từ gốc tiếng Trung trong câu để xác định đúng giới tính và bối phận thực tế; nếu không để ý từ gốc mà cứ biến đổi suy diễn sẽ rất dễ dịch nhầm bối phận (nhầm bề trên thành đồng bậc, đích mẫu thành di nương) hoặc nhầm lẫn giới tính nhân vật.\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA HOẶC CẢNH 3 NGƯỜI TRỞ LÊN: Khi hai người đang nói chuyện mà nhắc đến một người thứ ba (tha nhân), hoặc khi có từ 3 người trở lên cùng đối thoại trong phòng/trạch viện, phải bám chắc từ gốc để phân định rõ ai đang nói với ai và ai là người thứ ba được nhắc tới. Tuyệt đối không được nhầm đại từ của người thứ ba thành người đang đối thoại trực tiếp làm đảo lộn tôn ti.\n"
        "   - 3. ĐỒNG BẬC KHÔNG ĐƯỢC QUÁ LỊCH SỰ LÀM LỆCH BỐI PHẬN: Các quan hệ ngang hàng (tỷ muội trong nhà, biểu huynh đệ) xưng hô đúng mực đồng bậc ('tỷ — muội', 'huynh — muội'). Cấm xưng hô khúm núm hạ mình quá mức làm biến tướng thành quan hệ chủ — tớ hay bề dưới — bề trên.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch chuẩn xác theo đúng bối cảnh CỔ ĐẠI của tác phẩm!"
    )
}

# =====================================================================
# 6. HỆ THỐNG / TRỌNG SINH / XUYÊN KHÔNG / KHOÁI XUYÊN / VÔ ĐỊCH LƯU
# =====================================================================
SYSTEM_REINCARNATION_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: HỆ THỐNG / TRỌNG SINH / XUYÊN KHÔNG / KHOÁI XUYÊN / VÔ ĐỊCH LƯU ===\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC:\n"
        "   - Cơ chế Hệ thống & Trò chơi hóa:\n"
        "     * 系统 / 宿主 dịch thành Hệ thống / Ký chủ (hoặc Túc chủ)\n"
        "     * 叮! / 提示: ... dịch thành Đinh! / Nhắc nhở: ... (hoặc Thông báo: ...)\n"
        "     * 任务发布 / 任务完成 / 任务失败 dịch thành phát hành nhiệm vụ / hoàn thành nhiệm vụ / nhiệm vụ thất bại\n"
        "     * 抽奖 / 积分 / 属性面板 dịch thành rút thưởng / điểm tích lũy / bảng thuộc tính\n"
        "     * 力量 / 敏捷 / 智力 / 精神 / 体质 dịch thành Sức mạnh / Nhanh nhẹn / Trí lực / Tinh thần / Thể chất\n"
        "     * 空间背包 / 储物空间 / 新手礼包 dịch thành ba lô không gian / không gian trữ vật / gói quà tân thủ\n"
        "   - Trọng sinh & Xuyên không:\n"
        "     * 重生 / 穿越 / 穿书 / 快穿 dịch thành trọng sinh / xuyên không / xuyên sách / khoái xuyên\n"
        "     * 金手指 / 金光 dịch thành ngón tay vàng (bàn tay vàng) / kim quang\n"
        "     * 前世 / 今生 / 逆天改命 dịch thành kiếp trước / kiếp này / nghịch thiên cải mệnh\n"
        "     * 降维打击 / 扮猪吃虎 dịch thành đòn giáng hạ chiều / giả heo ăn thịt hổ\n"
        "\n"
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG THEO THỜI ĐẠI THẾ GIỚI XUYÊN VÀO (TRÁNH ÉP BUỘC MÁY MÓC, TRÁNH NHẦM SÓT):\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Mẫu xưng hô dưới đây chỉ là ví dụ phong cách tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô phù hợp khác chưa được liệt kê. NHƯNG khi thế giới xuyên vào là Cổ đại thì các xưng hô hiện đại tôi cấm (và mọi từ ngữ tương tự) CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG để tránh nhầm bối cảnh truyện; ngược lại khi ở Hiện đại thì tuyệt đối không dùng đại từ cổ phong gượng ép vào đời thường!\n"
        "   - Giao tiếp Hệ thống: Hệ thống tự xưng 'Bản hệ thống / Hệ thống' — gọi người dùng là 'Ký chủ / Túc chủ'. Ký chủ gọi 'Hệ thống / Ngươi' (bực tức dùng 'mày').\n"
        "   - THẾ GIỚI BÊN NGOÀI (TUÂN THỦ 100% THEO THỜI ĐẠI CỦA THẾ GIỚI ĐÓ):\n"
        "     * 🔴 NẾU XUYÊN VÀO CỔ ĐẠI / TU TIÊN / KIẾM HIỆP: Áp dụng 100% QUY CHUẨN CỔ PHONG:\n"
        "       + Đại từ: 'Ta — Ngươi', 'Tại hạ — Các hạ', 'Bọn ta — Các ngươi'.\n"
        "       + Thân tộc 2 âm tiết: 'Phụ thân — Mẫu thân', 'Bá phụ — Bá mẫu', 'Thúc phụ — Thúc mẫu', 'Cô mẫu — Cô phụ', 'Di mẫu' (⚠️ '姨娘' là di nương, cấm dịch là dì!), 'Cữu phụ — Cữu mẫu', 'Huynh trưởng — Tỷ tỷ — Đệ đệ — Muội muội'.\n"
        "       + Trật tự danh xưng: [Họ/Tên] + [Chức vụ] (Kiều trưởng lão, Lâm giáo đầu). CẤM dịch ngược!\n"
        "       + Khóa chặt 'con': Chỉ con ruột thưa cha mẹ mới xưng 'con'. Thưa sư phụ xưng 'đồ đệ', thưa tiền bối xưng 'vãn bối' (TUYỆT ĐỐI CẤM xưng 'con')!\n"
        "       + CẤM đại từ hiện đại: CẤM 'tôi-bạn', 'cậu-tớ', 'anh-em', 'chú mày', 'tụi em'!\n"
        "     * 🔵 NẾU BỐI CẢNH HIỆN ĐẠI: Áp dụng 100% quy tắc HIỆN ĐẠI ('Tôi — Cậu / Anh / Sếp', 'Mày — Tao').\n"
        "   🔴 CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI KHI DỊCH XƯNG HÔ:\n"
        "   - 1. BẮT BUỘC NHÌN VÀO TỪ GỐC để xác định đúng giới tính và bối phận; cấm tự ý biến đổi làm nhầm lẫn vai vế hoặc giới tính.\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA: Tuyệt đối không nhầm đại từ của người thứ ba thành người đang đối thoại trực tiếp.\n"
        "   - 3. ĐỒNG BẬC GIỮ ĐÚNG BÌNH ĐẲNG: Không khách sáo khúm núm làm biến dạng quan hệ ngang hàng.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch theo đúng bối cảnh thế giới xuyên vào!"
    )
}

# =====================================================================
# 7. MẠT THẾ / KHOA HUYỄN / TINH TẾ / CƠ GIÁP / VIỄN TƯỞNG / ZOMBIE
# =====================================================================
SCI_FI_APOCALYPSE_PROFILE = {
    "description": (
        "=== BẢN SẮC THỂ LOẠI: MẠT THẾ / TẬN THẾ ZOMBIE / KHOA HUYỄN / TINH TẾ / CƠ GIÁP / VIỄN TƯỞNG ===\n"
        "\n"
        "1. BẢNG TRA CỨU THUẬT NGỮ & TỪ KHÓA BẢN SẮC:\n"
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
        "2. QUY CHUẨN XƯNG HÔ: KHOANH VÙNG TỪ VỰNG MẠT THẾ / KHOA HUYỄN (DỨT KHOÁT, QUÂN PHONG, SINH TỒN):\n"
        "   🔴 BỐI CẢNH NÀY LÀ MẠT THẾ / KHOA HUYỄN — TÍNH CHẤT SINH TỒN, KỶ LUẬT QUÂN ĐỘI HOẶC BĂNG ĐẢNG ĐƯỜNG PHỐ:\n"
        "   ⚠️ LƯU Ý VỀ MẪU VÍ DỤ & NGUYÊN TẮC KHOANH VÙNG: Danh sách xưng hô dưới đây là các mẫu ví dụ tham khảo, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ này, mà tùy theo từng trường hợp bạn hoàn toàn có thể dùng các xưng hô dứt khoát phù hợp khác mà tôi chưa liệt kê hết được. NHƯNG các xưng hô cổ trang kiếm hiệp đã bị cấm (và mọi từ ngữ tương tự) thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG vào bối cảnh khoa huyễn súng đạn chiến hạm để tránh nhầm lẫn bối cảnh truyện!\n"
        "\n"
        "   🟢 VÙNG XƯNG HÔ NÊN DÙNG (DỨT KHOÁT, TỰ NHIÊN, SINH TỒN):\n"
        "   - Quân đội / Căn cứ / Chỉ huy: Chỉ huy, Đội trưởng, Thuyền trưởng, Quân đoàn trưởng, Binh sĩ, Chiến sĩ, Đồng chí, Thuộc cấp... (Xưng 'Tôi', thưa 'Báo cáo Chỉ huy / Đội trưởng'). Mệnh lệnh: 'Rõ!', 'Tuân lệnh!'.\n"
        "   - Đồng đội sinh tồn ngang hàng: Tôi, Cậu, Tớ, Anh, Em, Chúng ta, Mọi người, Đồng đội...\n"
        "   - Băng nhóm cướp bóc / Sinh tử đối đầu: Mày — Tao, Thằng khốn, Lũ chúng mày...\n"
        "\n"
        "   🔴 VÙNG TỪ CẤM (TUYỆT ĐỐI CẤM TRONG MẠT THẾ / KHOA HUYỄN):\n"
        "   - CẤM lạm dụng đại từ cổ trang kiếm hiệp ('tại hạ', 'các hạ', 'huynh đài', 'bản tọa', 'tiểu nữ', 'lão phu', 'vi sư') vào bối cảnh tàu không gian, chiến hạm hay sinh tồn súng đạn.\n"
        "\n"
        "   🔴 NGUYÊN TẮC RÀ SOÁT & CÁC LỖI KINH ĐIỂN CẦN TRÁNH TUYỆT ĐỐI:\n"
        "   - 1. TRÁNH DỊCH NHẦM TỪ CHUNG BỐI PHẬN / CHUNG GIỚI TÍNH: Bắt buộc nhìn vào từ gốc tiếng Trung trong câu để xác định đúng chức vụ, cấp bậc và giới tính nhân vật.\n"
        "   - 2. TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA HOẶC CHIẾN ĐẤU NHIỀU NGƯỜI: Khi hội đàm bộ đàm, chỉ huy chiến thuật hay nhắc tới mục tiêu/đồng đội thứ ba, phải bám chắc từ gốc để phân định rõ người phát ngôn, người nhận lệnh và đối tượng được nhắc đến.\n"
        "   - 3. ĐỒNG BẬC GIỮ ĐÚNG TÁC PHONG: Đồng cấp, đồng đội sinh tồn giữ đúng quan hệ ngang hàng, không khúm núm xưng hô hạ mình.\n"
        "   - 4. MỆNH LỆNH CỐT LÕI: ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG CÂU, xác định đúng vai vế và nhân vật, rồi dịch dứt khoát theo đúng bối cảnh mạt thế / khoa huyễn!"
    )
}

# =====================================================================
# BỘ QUY TẮC CỐT LÕI TOÀN DỰ ÁN (COMMON RULES - ÁP DỤNG CHO MỌI THỂ LOẠI)
# =====================================================================
COMMON_RULES = (
    "=== BỘ QUY TẮC DỊCH THUẬT CỐT LÕI & TIÊU CHUẨN AUDIOBOOK ===\n"
    "(Các quy tắc được sắp xếp theo đúng thứ tự ưu tiên từ cao xuống thấp. Mô hình tuân thủ nghiêm ngặt theo phân cấp ưu tiên này):\n"
    "\n"
    "0. CẤP ĐỘ 0 (MỆNH LỆNH TỐI CAO TUYỆT ĐỐI) — NGÔN NGỮ ĐẦU RA BẮT BUỘC 100% TIẾNG VIỆT (VIETNAMESE ONLY):\n"
    "   - TOÀN BỘ CHỮ VIẾT TRONG BẢN DỊCH BẮT BUỘC PHẢI LÀ 100% TIẾNG VIỆT HOÀN CHỈNH, CHUẨN MỰC.\n"
    "   - 🛑 TUYỆT ĐỐI CẤM TIẾNG ANH: Tuyệt đối cấm sử dụng bất kỳ từ tiếng Anh nào trong bản dịch (đặc biệt cấm các từ như 'But', 'And', 'So', 'Or'...). Toàn bộ câu từ đều phải diễn đạt bằng 100% tiếng Việt tự nhiên.\n"
    "   - 🛑 SẠCH 100% CHỮ HÁN: Mọi đoạn trích dẫn nhật ký, thư từ, văn bia, lời thoại, thơ ca trong nguyên tác BẮT BUỘC PHẢI DỊCH HẾT SANG TIẾNG VIỆT, TUYỆT ĐỐI CẤM COPY NGUYÊN HOẶC ĐỂ SÓT LẠI BẤT KỲ ĐOẠN CHỮ HÁN GỐC NÀO TRONG BẢN DỊCH!\n"
    "\n"
    "1. CẤP ĐỘ 1 (ƯU TIÊN CAO) — BẢO VỆ TÊN RIÊNG & DỊCH THẲNG MỘT CHIỀU:\n"
    "   - KHÓA 100% TÊN RIÊNG THEO BẢNG THỰC THỂ: Toàn bộ danh từ riêng, ngoại hiệu, tên nhân vật, địa danh, thuật ngữ đã có trong Bảng thực thể BẮT BUỘC dùng đúng 100% bản dịch tiếng Việt tương ứng ngay từ lần đầu xuất hiện. TUYỆT ĐỐI KHÔNG tự ý dịch lại, không suy đoán thay đổi làm sai lệch tên hoặc sót chữ Hán. TUYỆT ĐỐI CẤM viết tên kèm ngoặc đơn đối chiếu song ngữ hay để sót chữ Hán gốc.\n"
    "   - THỰC THỂ MỚI CHƯA CÓ TRONG BẢNG: Giữ đúng âm Hán-Việt quen thuộc; tuyệt đối không dịch bẻ nghĩa đen ngô nghê.\n"
    "   - NGUYÊN TẮC CHUYỂN NGỮ THẲNG MỘT CHIỀU: Mỗi cụm từ và tên riêng chỉ chuyển sang duy nhất một bản dịch tiếng Việt hoàn chỉnh, hòa nhập tự nhiên vào dòng chảy câu văn. Tuyệt đối cấm mở ngoặc đơn để chú thích nghĩa, phiên âm hay đối chiếu chữ Hán trong thân bài.\n"
    "\n"
    "2. CẤP ĐỘ 2 (ƯU TIÊN VĂN PHONG) — NGUYÊN TẮC CHUYỂN NGỮ CỐT LÕI: DÙNG TIẾNG VIỆT THUẦN VIỆT & PHỔ THÔNG DỄ HIỂU:\n"
    "   - TIÊU CHÍ BẮT BUỘC LÀ DỄ HIỂU BẰNG TIẾNG VIỆT PHỔ THÔNG: Toàn bộ câu văn phải được diễn đạt bằng từ ngữ tiếng Việt phổ thông, thuần Việt, thông dụng, gãy gọn, tự nhiên và dễ hiểu nhất để bất kỳ ai nghe hoặc đọc cũng hiểu ngay tức thì. Dịch đúng nghĩa, rõ ràng bằng tiếng Việt phổ thông của thể loại truyện là đạt chuẩn.\n"
    "   - 🔴 TỪ NGỮ ĐỜI THƯỜNG, ẨM THỰC & SINH HOẠT THƯỜNG BỊ DỊCH MÁY MÓC SANG HÁN-VIỆT: BẮT BUỘC DÙNG TỪ THUẦN VIỆT GẦN GŨI VỚI ĐỘC GIẢ VIỆT NAM:\n"
    "     * Các từ ngữ chỉ cuộc sống thường ngày, món ăn, thức uống, cây cỏ, đồ dùng gia đình thông thường, nguyên liệu nấu nướng... vốn là từ đời thường nhưng hay bị dịch cơ học sang âm Hán-Việt khô cứng, tối nghĩa: BẮT BUỘC KHÔNG ĐƯỢC DỊCH HÁN-VIỆT mà phải chuyển ngữ bằng từ ngữ thuần Việt gần gũi, quen thuộc với người đọc Việt Nam theo phong cách phổ thông của thể loại truyện Trung dịch Việt (ví dụ: '蘑菇炖鸡' -> 'nấm hầm thịt gà', cấm dịch 'Ma Cô Độn Kê').\n"
    "     * ⚠️ PHÂN BIỆT RÕ VỚI TÊN RIÊNG & TÊN CHỦNG LOÀI BẢN SẮC CỦA CON VẬT, YÊU THÚ, DỊ THÚ, LINH THÚ, BẢO VẬT: Tuyệt đối CẤM dịch nôm na thuần Việt các tên riêng của con vật cưng, tên riêng của đồ vật hay tên chủng loài yêu thú mang bản sắc truyện Trung! Dù là tên riêng (tiểu hắc, đại hoàng, bạch vũ...) hay tên chủng loài bản sắc (ví dụ: Hắc Sí Đại Bàng, Cửu Vĩ Thiên Hồ, Bích Nhãn Kim Tinh Thú, Hỏa Diễm Tước...) thì ĐÂY LÀ TÊN BẢN SẮC CỦA TRUYỆN, BẮT BUỘC GIỮ ĐÚNG ÂM HÁN-VIỆT VĂN HỌC BẢN SẮC, TUYỆT ĐỐI CẤM dịch thuần Việt nôm na (CẤM dịch Hắc Sí Đại Bàng thành 'đại bàng cánh đen'!).\n"
    "     * Tuyệt đối cấm để các từ đời thường biến thành tên chiêu thức võ công hay danh từ Hán-Việt quái dị làm người đọc không hiểu được nhân vật đang ăn gì, dùng gì hay làm việc gì.\n"
    "   - 🔴 LINH HOẠT CHUYỂN NGỮ THEO ĐỐI TƯỢNG THỰC TẾ TRONG NGỮ CẢNH: Tiếng Trung hay dùng chung từ ngữ mang nghĩa dành cho con người để áp lên đối tượng khác bản chất (động vật, linh thú, đồ vật, hiện tượng, thế lực trừu tượng...). Khi chuyển ngữ, BẮT BUỘC nhận diện đúng bản chất đối tượng đang được nói đến rồi chọn cách diễn đạt tiếng Việt phù hợp — KHÔNG áp khuôn dịch cứng. Nguyên tắc này áp dụng toàn diện cho mọi trường hợp lệch bản chất, không chỉ giới hạn giữa người và vật.\n"
    "   - TUYỆT ĐỐI KHÔNG CỐ GẮNG 'DỊCH CHO HAY' HOẶC GƯỢNG ÉP HÁN-VIỆT: Cấm cố gượng ép dùng từ Hán-Việt lạ lẫm hoặc câu cú bóng bẩy để ra vẻ hoa mỹ. Việc lạm dụng Hán-Việt khi không nắm vững sẽ biến câu văn thành văn convert thô cứng, tối nghĩa và sai lệch hoàn toàn so với tiếng Việt thực tế. Cứ có cách diễn đạt bằng từ ngữ thuần Việt hoặc tiếng Việt phổ thông, dễ hiểu thì BẮT BUỘC DÙNG TIẾNG VIỆT PHỔ THÔNG.\n"
    "   - TUYỆT ĐỐI CẤM DỊCH CONVERT THEO TỪNG CHỮ HÁN: Cấm dịch cơ học bám theo cấu tạo từng chữ Hán hay từ điển Hán-Việt. Phải nắm bắt trọn vẹn ý nghĩa của câu trong ngữ cảnh rồi diễn đạt lại bằng câu văn tiếng Việt tự nhiên, thuần Việt, dễ hiểu, tránh nhầm lẫn mức độ hoặc hiểu sai ý của tác giả.\n"
    "   - XỬ LÝ CÂU NGẮN & TRÁNH CỤT CÂU (NHẤN MẠNH: CHỈ MỘT TÝ, TRÁNH LAN MAN, TRÁNH SUY NGHĨ NHIỀU):\n"
    "     * Đối với những câu ngắn hoặc cách diễn đạt vắn tắt của tiếng Trung, nếu dịch sát từng chữ khiến câu tiếng Việt bị cụt ngủn, hụt hơi, cộc lốc hoặc thiếu liên kết tự nhiên: ĐƯỢC PHÉP thêm chút liên từ, trợ từ hoặc từ đệm tiếng Việt để câu văn tròn trịa, xuôi tai, liền mạch.\n"
    "     * NHẤN MẠNH ĐẶC BIỆT LÀ CHỈ THÊM MỘT TÝ ĐỦ ĐỂ TRÁNH CỤT CÂU: TUYỆT ĐỐI CẤM LAN MAN, TRÁNH SUY NGHĨ NHIỀU, TUYỆT ĐỐI KHÔNG PHÓNG TÁC KÉO DÀI DÒNG DÃ, KHÔNG TỰ Ý BỊA ĐẶT THÊM TÌNH TIẾT HOẶC Ý NGHĨA NGOÀI NGUYÊN TÁC.\n"
    "   - CÂU VĂN MẠCH LẠC, XUÔI TAI, TRUNG THỰC: Câu văn gãy gọn, xuôi tai, trung thực với ngữ cảnh và tinh thần tác phẩm của tác giả; không tự ý phóng tác, bịa đặt thêm bớt hoặc làm sai lệch nội dung.\n"
    "   - NGUYÊN LÝ ĐỊNH VỊ THỜI ĐẠI & CÁC LỖI KINH ĐIỂN VỀ XƯNG HÔ:\n"
    "     * Trước khi dịch mỗi đoạn thoại, mô hình tự định vị: Đây là thời đại nào? (Cổ đại hay Hiện đại?). Sắc thái xưng hô của thời đại đó là gì? (Cổ phong trang nghiêm, tôn ti trật tự hay Hiện đại tự nhiên đời thường?).\n"
    "     * LƯU Ý VỀ MẪU VÍ DỤ THAM KHẢO & KHÔNG ÉP BUỘC CỨNG NHẮC: Danh sách các từ xưng hô trong từng profile chỉ mang tính chất định hình phong cách bối cảnh, TÔI KHÔNG ÉP BUỘC bạn phải dịch chuẩn cứng nhắc chỉ duy nhất các từ mẫu đó, mà tùy từng trường hợp bạn hoàn toàn có thể linh hoạt dùng các xưng hô mang phong cách cổ đại phù hợp khác chưa được liệt kê. NHƯNG CÁC XƯNG HÔ HIỆN ĐẠI ĐÃ BỊ CẤM (và mọi từ ngữ hiện đại tương tự) thì CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG khi ở bối cảnh Cổ đại để tránh nhầm lẫn thời đại tác phẩm!\n"
    "     * ƯU TIÊN NHÌN VÀO TỪ GỐC TRONG NGUYÊN TÁC: Bắt buộc nhìn vào từ gốc tiếng Trung để xác định đúng đối tượng, giới tính và bối phận thực tế; nếu không để ý từ gốc mà tự ý suy diễn biến đổi sẽ rất dễ dịch nhầm bối phận (nhầm bề trên thành ngang hàng hoặc ngược lại) hoặc nhầm lẫn giới tính nhân vật.\n"
    "     * TRÁNH LOẠN XƯNG HÔ KHI CÓ NGƯỜI THỨ BA: Khi hai người đang nói chuyện mà nhắc đến một người thứ ba (tha nhân), hoặc phân cảnh có từ 3 người trở lên, phải bám chắc từ gốc để phân định rõ ai đang nói với ai và ai là người thứ ba được nhắc tới, tuyệt đối không nhầm đại từ của người thứ ba thành người đang đối thoại trực tiếp làm đảo lộn mạch truyện.\n"
    "     * ĐỒNG BẬC KHÔNG QUÁ LỊCH SỰ: Các quan hệ ngang hàng (đồng môn, bằng hữu, đồng nghiệp) phải giữ đúng mực xưng hô đồng bậc; cấm khúm núm hạ mình quá mức làm biến tướng thành quan hệ bề dưới — bề trên.\n"
    "     * KHÓA CHẶT 'CON': Tôn kính gọi người khác bằng danh xưng cao quý KHÔNG CÓ NGHĨA tự xưng là 'con' (chỉ con ruột thưa cha mẹ mới xưng 'con').\n"
    "\n"
    "3. CẤP ĐỘ 3 — THÀNH NGỮ, TỤC NGỮ, QUÁN NGỮ & KHẨU NGỮ: DỊCH THOÁT Ý DỄ HIỂU, KHÔNG CỐ DỊCH HAY:\n"
    "   - THÀNH NGỮ, TỤC NGỮ, QUÁN NGỮ: Không cần cố tìm thành ngữ hoa mỹ hay đối chữ cho hay. Nắm bắt trọn vẹn đại ý rồi diễn đạt thẳng bằng lời lẽ tiếng Việt phổ thông, mộc mạc, dễ hiểu nhất theo đúng ngữ cảnh. Tuyệt đối cấm dịch cơ học bám sát nghĩa đen từng chữ Hán ngô nghê.\n"
    "   - KHẨU NGỮ, CÂU CHỬI, CẢM THÁN: Dịch bằng khẩu ngữ tiếng Việt phổ thông, tự nhiên, đúng sắc thái nhân vật. Trong bối cảnh cổ trang, kiếm hiệp, tiên hiệp, tuyệt đối cấm dùng các đại từ đường phố hiện đại lai tạp.\n"
    "   - TỪ LÓNG & BỐI CẢNH MẠNG: Dịch thoát ý thẳng nghĩa bằng từ ngữ tiếng Việt phổ thông, dễ hiểu theo ngữ cảnh. Tuyệt đối không để sót chữ Hán.\n"
    "   - THÀNH NGỮ VĂN HÓA ĐẶC THÙ: Khi nguyên tác sử dụng thành ngữ, tục ngữ, ca dao mang đậm nét văn hóa đặc thù Trung Quốc mà nếu dịch thoát ý thuần túy vẫn còn xa lạ hoặc khó cảm nhận đối với người Việt, NÊN tìm thành ngữ, tục ngữ, cách nói dân gian tương đương trong tiếng Việt có cùng hàm ý để thay thế, giúp người đọc/nghe Việt Nam cảm nhận được ngay thần thái và ý nghĩa mà tác giả muốn truyền tải. Nếu không tìm được tương đương phù hợp tự nhiên, thì diễn đạt thẳng nghĩa bằng lời lẽ tiếng Việt dễ hiểu theo ngữ cảnh — KHÔNG cố ép đối chữ cho hay.\n"
    "\n"
    "4. CẤP ĐỘ 4 — TIÊU CHUẨN CON SỐ & TIỀN TỆ CHO AUDIOBOOK (TTS):\n"
    "   - VIẾT BẰNG CHỮ CHO CON SỐ TRONG VĂN BẢN ĐỌC: Các con số trong câu trần thuật, đối thoại, suy nghĩ, ước tính, số lượng, tiền tệ, thời gian BẮT BUỘC VIẾT HOÀN TOÀN BẰNG CHỮ TIẾNG VIỆT để đầu đọc TTS phát âm chuẩn ngữ điệu tự nhiên.\n"
    "   - TUYỆT ĐỐI CẤM VIẾT NỬA CHỮ NỬA SỐ LAI TẠP: Nghiêm cấm các dạng viết lai tạp cẩu thả giữa số và chữ làm hỏng nhịp đọc TTS.\n"
    "   - SỐ THỨ TỰ & NĂM THÁNG: Tiêu đề số chương hoặc mốc năm tháng cụ thể có thể giữ nguyên số Ả Rập.\n"
    "   - TÍNH TOÁN BẬC SỐ LƯỢNG CHUẨN XÁC: Quy đổi chính xác các cấp bậc số lượng trong tiếng Trung sang tiếng Việt, không dịch nhầm hàng vạn, hàng triệu.\n"
    "\n"
    "5. CẤP ĐỘ 5 — TIÊU CHUẨN CHÍNH TẢ, VIẾT HOA & DẤU CÂU CHO AUDIOBOOK (TTS):\n"
    "   - CHUẨN CHÍNH TẢ TIẾNG VIỆT 100%: Viết đúng chính tả tiếng Việt, chuẩn ngữ pháp, câu văn gãy gọn mạch lạc, không có lỗi gõ phím.\n"
    "   - KHOẢNG CÁCH TỪ & VIẾT HOA CHUẨN MỰC: Mỗi từ phân cách bằng đúng một dấu cách. Viết hoa đúng chuẩn tên riêng nhân vật, địa danh và đầu câu. Không chèn chữ hoa tùy tiện ở giữa từ.\n"
    "   - DẤU CÂU TẠO NHỊP NGẮT NGHỈ TỰ NHIÊN: Đặt dấu câu sát ngay sau từ phía trước và cách từ tiếp theo đúng một dấu cách. Không lạm dụng dấu phẩy vụn vặt làm giọng đọc TTS bị giật cục.\n"
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
    return "xianxia"


def get_context_profile_prompt(profile_key: str) -> str:
    """
    Lấy nội dung Profile đặc thù thể loại kết hợp với Bộ quy tắc cốt lõi toàn dự án.
    """
    normalized_key = normalize_profile_key(profile_key)
    profile_data = CONTEXT_PROFILES.get(normalized_key, XIANXIA_PROFILE)
    description = profile_data.get("description", "")

    return f"""{description}

{COMMON_RULES}"""


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
            "- TUYỆT ĐỐI CẤM đại từ cổ trang: Cấm 'ta - ngươi', 'tại hạ', 'các hạ', 'bản tọa', 'vi sư' trong sinh tồn công nghệ cao/súng đạn.\n"
            "- Dùng xưng hô dứt khoát quân phong hoặc sinh tồn: 'Tôi — Đồng chí / Chỉ huy / Đội trưởng', 'Tôi — Cậu / Anh', xung đột dùng 'Mày — Tao'."
        )
    elif normalized_key in ["urban_supernatural"]:
        return (
            "=== QUY CHUẨN XƯNG HÔ: ĐỜI THƯỜNG DÂN GIAN (BỐI CẢNH LINH DỊ / THÔN DÃ) ===\n"
            "- TUYỆT ĐỐI CẤM: Không dùng đại từ tiên hiệp cung đình ('bản tọa', 'vi thần') và không dùng danh xưng công sở ('sếp', 'CEO').\n"
            "- Dùng xưng hô mộc mạc làng xóm/thợ thuyền: [Danh xưng] + [Tên] ('Bác Lý', 'Chú Tam Giang', 'Thầy Tứ'), 'Anh — Em', 'Chú — Cháu', 'Mày — Tao'."
        )
    else:
        # Xianxia, Wuxia, Romance (Cổ trang/Cung đấu), System (mặc định cổ phong)
        return (
            "=== QUY CHUẨN XƯNG HÔ: CẤM TUYỆT ĐỐI LỆCH SANG HIỆN ĐẠI (BỐI CẢNH CỔ ĐẠI) ===\n"
            "- TUYỆT ĐỐI CẤM đại từ hiện đại: Cấm 'tôi - bạn', 'cậu - tớ', 'anh - em' (trừ phu thê), 'chú - cháu', 'ông - tôi', 'chú mày', 'tụi em', 'bọn em', 'tụi mình'.\n"
            "- BẮT BUỘC dùng đại từ cổ phong: 'Ta — Ngươi', 'Huynh — Đệ / Muội', 'Tại hạ — Các hạ'. Thân tộc 2 âm tiết ('Phụ thân', 'Mẫu thân', 'Huynh trưởng'). Trật tự: [Tên] + [Chức vụ] (Kiều trưởng lão, Lâm giáo đầu). Khóa chặt 'con' (chỉ con ruột thưa cha mẹ mới xưng 'con')."
        )


# =====================================================================
# HỆ THỐNG XÂY DỰNG PROMPT TẬP TRUNG (CENTRALIZED PROMPT BUILDERS)
# ĐẢM BẢO THỐNG NHẤT MỘT NGUỒN CHUẨN DUY NHẤT (SINGLE SOURCE OF TRUTH)
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
    return f"""🔴 MỆNH LỆNH TỐI CAO: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- NGÔN NGỮ NGUỒN: TIẾNG TRUNG (RAW).
- NGÔN NGỮ ĐẦU RA BẮT BUỘC: 100% TIẾNG VIỆT HOÀN CHỈNH (VIETNAMESE ONLY). CHỮ VIẾT ĐỀU LÀ TIẾNG VIỆT, TUYỆT ĐỐI KHÔNG ĐƯỢC LẪN BẤT KỲ NGÔN NGỮ NÀO KHÁC.
- 🛑 CẤM TUYỆT ĐỐI TIẾNG ANH: Tuyệt đối không dùng bất kỳ từ tiếng Anh nào (cấm các từ như 'But', 'And', 'So'...). Toàn bộ câu từ bắt buộc phải là 100% tiếng Việt.
- 🛑 CẤM SÓT CHỮ HÁN HOẶC PINYIN: Mọi trích dẫn nhật ký, thư từ, văn bia, lời thoại, thơ ca đều phải dịch sạch 100% sang tiếng Việt, không để sót bất kỳ chữ Hán nào chưa dịch.
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
- KIỂM TRA NGÔN NGỮ ĐẦU RA (100% TIẾNG VIỆT): Đảm bảo toàn bộ chữ viết là tiếng Việt hoàn chỉnh. Rà soát tuyệt đối KHÔNG có từ tiếng Anh nào (đặc biệt kiểm tra không có chữ 'But' thay cho 'Nhưng'), sạch 100% chữ Hán và Pinyin (mọi trích dẫn/nhật ký đều đã dịch hết sang tiếng Việt);
- Tên riêng và thuật ngữ BẮT BUỘC tuân thủ chính xác 100% theo Bảng thực thể đã cung cấp (đối chiếu chuẩn xác các cụm tên 【...】 đối ứng, TUYỆT ĐỐI KHÔNG để lệch âm, không sót chữ Hán lai tạp);
- Kiểm tra xưng hô đúng bối cảnh (Tra cứu Bảng xưng hô; ưu tiên nhìn từ gốc tiếng Trung để không nhầm bối phận hay giới tính; suy luận theo đúng tôn ti thời đại; mẫu ví dụ chỉ để định hình phong cách và không ép buộc máy móc chỉ dùng duy nhất các từ đó, có thể linh hoạt dùng các xưng hô cổ đại khác phù hợp, nhưng các xưng hô hiện đại đã cấm và tương tự là CHẮC CHẮN TUYỆT ĐỐI KHÔNG ĐƯỢC ÁP DỤNG tránh nhầm bối cảnh):
  * Nếu CỔ ĐẠI: Giữ đúng trật tự [Họ/Tên] + [Chức vụ] (Kiều trưởng lão, Lâm giáo đầu); Giữ đúng 2 âm tiết Hán-Việt ('phụ thân', 'mẫu thân', 'bá phụ', 'thúc phụ', 'di mẫu', 'huynh trưởng'); CẤM rút thành 'chú, bác, dì, cô, cậu, cha, mẹ'; CẤM xưng 'con' với sư phụ/tiền bối (chỉ con ruột với cha mẹ mới xưng 'con'); CẤM đại từ hiện đại ('tôi - bạn', 'cậu - tớ', 'chú mày', 'tụi em').
  * Nếu HIỆN ĐẠI: Tiếng Việt tự nhiên theo tuổi tác & quan hệ ('Tôi — Anh / Chị / Bạn', 'Cậu — Tớ', 'Mày — Tao'); CẤM gượng ép cổ trang trong sinh hoạt thường nhật.
  * Phân biệt rõ người đang đối thoại trực tiếp vs người thứ ba được nhắc tới; Đồng bậc giữ đúng mực xưng hô ngang hàng, không quá khách sáo làm lệch bối phận.
- Không được sót chữ hoặc cụm tiếng Trung nào trong bản dịch;
- Câu văn tự nhiên, diễn đạt phổ thông dễ hiểu theo đúng thể loại truyện, không giữ nguyên từ convert tối nghĩa;
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
    return f"""🔴 MỆNH LỆNH TỐI CAO: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- NGÔN NGỮ NGUỒN: TIẾNG TRUNG (RAW).
- NGÔN NGỮ ĐẦU RA BẮT BUỘC: 100% TIẾNG VIỆT HOÀN CHỈNH (VIETNAMESE ONLY). CHỮ VIẾT ĐỀU LÀ TIẾNG VIỆT, TUYỆT ĐỐI KHÔNG ĐƯỢC LẪN TIẾNG ANH (CẤM 'BUT') HAY BẤT KỲ NGÔN NGỮ NÀO KHÁC. SẠCH 100% CHỮ HÁN VÀ PINYIN.
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

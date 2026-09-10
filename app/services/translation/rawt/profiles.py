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
        "【THỂ LOẠI: TU TIÊN / TIÊN HIỆP / HUYỀN HUYỄN / CỔ PHONG / DỊ GIỚI / CAO VÕ】\n"
        "\n"
        "1. BẢN SẮC CẢNH GIỚI & TU VI (BẮT BUỘC DÙNG THUẬT NGỮ TU CHÂN HÁN-VIỆT):\n"
        "   - THỨ BẬC CẢNH GIỚI: Giữ đúng nguyên vẹn thuật ngữ tu chân Hán-Việt, không dịch thành số thứ tự đời thường hay học đường:\n"
        "     * Hệ thống cảnh giới: 'Luyện Linh thập cảnh' (hoặc 'Thập cảnh Luyện Linh'), 'Nhất cảnh', 'Nhị cảnh', 'Tam cảnh', 'Tứ cảnh'...\n"
        "       (Ví dụ: 'Luyện Linh tam cảnh', 'Luyện Linh tứ cảnh').\n"
        "     * Tầng thứ tu luyện: 'Tầng một / Nhất tầng', 'Tầng hai / Nhị tầng', 'Tầng chín / Cửu tầng'.\n"
        "     * Phân đoạn cảnh giới: 'Sơ kỳ', 'Trung kỳ', 'Hậu kỳ', 'Đỉnh phong', 'Viên mãn', 'Đại viên mãn', 'Bán bộ' (Bán bộ Trúc Cơ, Bán bộ Nguyên Anh).\n"
        "     * Đột phá tu vi - 'Bình cảnh' (瓶颈): Ngưỡng nghẽn trước khi đột phá bắt buộc dịch là 'bình cảnh' hoặc 'nút thắt cảnh giới' (ví dụ: 'chạm tới bình cảnh', 'đột phá bình cảnh'). Không để sót chữ Hán.\n"
        "     * Các đại cảnh giới kinh điển: Luyện Khí, Trúc Cơ, Kim Đan, Nguyên Anh, Hóa Thần, Luyện Hư, Hợp Thể, Đại Thừa, Độ Kiếp...\n"
        "   - HÀNH VI & HIỆN TƯỢNG TU LUYỆN:\n"
        "     * 'Bế quan', 'Bế tử quan' (đóng cửa tu luyện đến chết hoặc đột phá mới ra; giữ nguyên sắc thái tu chân trang nghiêm).\n"
        "     * 'Đột phá', 'Độ kiếp', 'Thiên kiếp', 'Tâm ma', 'Khí huyết nghịch chuyển', 'Tẩu hỏa nhập ma', 'Đoạt xá', 'Vẫn lạc'.\n"
        "     * 'Đan điền', 'Thức hải', 'Thần thức', 'Linh khí', 'Linh căn', 'Chân nguyên', 'Pháp lực', 'Đạo tâm', 'Đạo vận', 'Pháp tắc'.\n"
        "     * Phân nhánh tu sĩ: 'Tán tu', 'Thể tu', 'Kiếm tu', 'Đan tu', 'Phù tu', 'Trận tu', 'Ma tu', 'Yêu tu', 'Quỷ tu', 'Đạo lữ'.\n"
        "\n"
        "2. BẢN SẮC MÔN PHÁI & THAO TRƯỜNG TU TIÊN:\n"
        "   - Cơ cấu tổ chức: 'Linh Cung', 'Tông môn', 'Thánh địa', 'Động phủ', 'Phúc địa', 'Ngoại viện / Ngoại môn đệ tử', 'Nội viện / Nội môn đệ tử',\n"
        "     'Chân truyền đệ tử', 'Ký danh đệ tử', 'Chấp sự', 'Trưởng lão', 'Phong chủ', 'Đường chủ', 'Tông chủ', 'Chưởng môn', 'Thái thượng trưởng lão', 'Lão tổ'.\n"
        "   - Địa điểm & sự kiện: 'Tàng Kinh Các', 'Luyện Đan Điện', 'Chấp Sự Điện', 'Dược Viên', 'Lôi đài', 'Thí luyện chi địa', 'Đại bỉ môn phái', 'Bí cảnh', 'Phong Vân Tranh Bá'...\n"
        "   - Không ví von hay kéo về ngôn ngữ trường học/công sở hiện đại (không dịch đại bỉ/tranh bá thành 'kỳ thi cuối kỳ', 'thi học kỳ').\n"
        "   - Tên nhân vật, địa danh dù thuộc tộc ngoại, Tây Vực hay dị giới: Phiên âm 100% Hán-Việt chuẩn mực (Đặc Lý, Thác Bạt, Thái Lạp...). Không phiên âm tên tiếng Anh/tên Tây.\n"
        "\n"
        "3. PHONG THÁI XƯNG HÔ CỔ ĐẠI (TU TIÊN / CỔ PHONG):\n"
        "   - Trật tự xưng hô tu tiên: [Họ / Tên] + [Chức vụ / Danh xưng / Thân phận] (Ví dụ: Kiều trưởng lão, Từ sư thúc, Vương chưởng môn, Lý phong chủ, Triệu sư huynh, Liễu sư tỷ, Bạch tiền bối).\n"
        "   - Đại từ chung & an toàn: Dùng 'Ta — Ngươi' khi đối thoại ngang hàng, người lạ, giao chiến; đại từ tập thể trung tính: 'bọn họ', 'chúng nhân', 'đám người'.\n"
        "   - Hệ thống tông môn & đồng đạo rõ ràng theo vai vế:\n"
        "     * Sư đồ: Đệ tử thưa Sư tôn/Sư phụ xưng 'Đồ nhi / Đệ tử'; Sư phụ gọi đệ tử là 'Đồ nhi / Ngươi / [Tên]'. Không xưng hô kiểu trường học hiện đại ('thầy - em') hay đại từ teen ('tụi em').\n"
        "     * Đồng môn: 'Sư huynh — Sư đệ / Sư muội', 'Sư tỷ — Sư đệ / Sư muội'.\n"
        "     * Cấp dưới thưa Chưởng môn/Trưởng lão: Xưng 'Thuộc hạ / Đệ tử / Chúng đệ tử'.\n"
        "     * Đạo lữ / Tình cảm: 'Chàng — Nàng / Phu quân — Nương tử'.\n"
        "   - Đúng giới tính người nghe: Nữ gọi 'Nàng', 'Nương tử', 'Cô nương', 'Sư muội', 'Sư tỷ'; Nam gọi 'Chàng', 'Phu quân', 'Huynh', 'Sư huynh', 'Sư đệ'.\n"
        "   - Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, nàng, y, gã, lão giả'. Tuyệt đối không dùng đại từ học đường hiện đại ('cậu ấy, anh ấy').\n"
        "   - Độc thoại nội tâm: Dùng 'ta' hoặc 'mình'.\n"
    )
}

# =====================================================================
# 2. VÕ HIỆP / KIẾM HIỆP / GIANG HỒ TRUYỀN THỐNG / DÃ SỬ
# =====================================================================
WUXIA_PROFILE = {
    "description": (
        "【THỂ LOẠI: KIẾM HIỆP / VÕ LÂM / GIANG HỒ TRUYỀN THỐNG / LỤC LÂM HẢO HÁN / THỦY HỬ / DÃ SỬ SA TRƯỜNG】\n"
        "\n"
        "1. BẢN SẮC CẢNH GIỚI VÕ HỌC, GIANG HỒ & LỤC LÂM HẢO HÁN:\n"
        "   - Thứ bậc cao thủ: 'Tam lưu cao thủ', 'Nhị lưu', 'Nhất lưu', 'Đỉnh phong', 'Tuyệt đỉnh cao thủ', 'Hậu thiên', 'Tiên thiên', 'Hóa Cảnh', 'Tông Sư', 'Đại Tông Sư'.\n"
        "   - Thức & tầng võ công: 'Thức thứ nhất', 'Thức thứ hai'; 'Tầng thứ nhất', 'Tầng thứ chín' (Cửu Dương thần công tầng chín, Cửu trùng thiên...); 'Nhập môn', 'Tiểu thành', 'Đại thành', 'Viên mãn'.\n"
        "   - Hệ thống huyệt đạo & kinh mạch: 'Nhâm Đốc nhị mạch', 'Khí hải', 'Đan điền', 'Bách hội', 'Dũng tuyền', 'Đả thông kinh mạch', 'Tẩu hỏa nhập ma', 'Bế khí', 'Điểm huyệt', 'Giải huyệt'.\n"
        "   - Thuật ngữ võ học (nội lực, chân khí, khinh công, kiếm khí, đao pháp, quyền cước, tâm pháp): Dịch sang từ Hán-Việt tương ứng quen thuộc.\n"
        "   - Tổ chức, sơn trại, quân doanh & sa trường: 'Danh môn chính phái', 'Tiêu cục', 'Bang hội' (Bang chủ, Đà chủ), 'Sơn trại / Lục lâm' (Đại đương gia, Nhị đương gia, Trại chủ, Đầu lĩnh, Tiên phong, Giáo đầu, Hảo hán tụ nghĩa, Tiểu lâu la).\n"
        "\n"
        "2. PHONG THÁI XƯNG HÔ CỔ ĐẠI (GIANG HỒ / LỤC LÂM / SA TRƯỜNG):\n"
        "   - Trật tự xưng hô giang hồ: [Họ / Tên] + [Chức vụ / Danh xưng / Thân phận] (Ví dụ: Tiêu bang chủ, Chu trại chủ, Vương đà chủ, Lý đại đương gia, Lâm giáo đầu).\n"
        "   - Hệ thống xưng hô sơn trại & lục lâm:\n"
        "     * Bộ hạ, tiểu lâu la thưa với Trại chủ / Bang chủ / Đầu lĩnh: BẮT BUỘC xưng 'Chúng tôi / Chúng tiểu nhân / Thuộc hạ / Tiểu nhân', gọi 'Trại chủ / Bang chủ / Đầu lĩnh / Đại ca'. TUYỆT ĐỐI CẤM dùng 'bọn em', 'tụi em', 'tụi con'!\n"
        "     * Đại từ tiểu lâu la tự xưng (俺 / 俺几个): Dịch là 'Chúng tôi / Đám chúng tôi / Chúng tiểu nhân / Ta'.\n"
        "     * Huynh đệ kết nghĩa: Đại ca gọi 'Tam đệ / Hiền đệ / Đệ'; Đệ gọi 'Đại ca / Ca ca'; khi trò chuyện thân tình xưng 'Huynh — Đệ' hoặc 'Ta — Đệ'.\n"
        "   - Khẩu ngữ giang hồ ngông nghênh & hào sảng:\n"
        "     * Khẩu ngữ ngông nghênh (你家爷爷, 你家老爷): BẮT BUỘC dịch thoát nghĩa theo đúng khí thế lấn lướt là 'Gia gia mày đây / Ông mày đây / Ông nội mày đây', 'Lão gia mày đây'. Tuyệt đối cấm dịch thô máy móc thành 'ngươi gia đây'.\n"
        "     * Hào sảng xưng hô: 'Gia gia đây / Ông đây — Chúng mày / Ngươi'.\n"
        "   - Đại từ chung: Cặp 'Ta — Ngươi' dùng giữa hảo hán giang hồ, giao đấu sa trường, tra hỏi, người lạ.\n"
        "   - Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, gã, y, lão, tráng sĩ, hán tử, hảo hán'. Tránh dùng 'cậu ấy, anh ấy'.\n"
        "   - Độc thoại nội tâm: Dùng 'ta' hoặc 'mình'.\n"
    )
}

# =====================================================================
# 3. ĐÔ THỊ / HIỆN ĐẠI / THƯƠNG CHIẾN / VƯỜN TRƯỜNG / HÀO MÔN
# =====================================================================
URBAN_PROFILE = {
    "description": (
        "【THỂ LOẠI: HIỆN ĐẠI / ĐÔ THỊ / ĐỜI THƯỜNG / VƯỜN TRƯỜNG / HÀO MÔN / THƯƠNG TRƯỜNG】\n"
        "\n"
        "1. BẢN SẮC ĐỜI THƯỜNG & THỜI ĐẠI:\n"
        "   - Tổ chức & chức danh: 'Chủ tịch Hội đồng quản trị (HĐQT)', 'Tổng giám đốc (CEO)', 'Phó tổng', 'Giám đốc bộ phận', 'Trợ lý', 'Thư ký', 'Cổ đông', 'Tiệc rượu', 'Đấu giá', 'Hợp đồng'...\n"
        "   - Tầng lớp xã hội: 'Hào môn thế gia', 'Thế gia vọng tộc', 'Thái tử gia', 'Phú nhị đại' (con nhà siêu giàu), 'Thiếu gia', 'Tiểu thư'.\n"
        "   - Văn phong tiếng Việt hiện đại, tự nhiên, nhịp sống thời đại như người Việt giao tiếp hằng ngày. Không dùng từ ngữ cổ phong, kiếm hiệp lạc lõng (ngươi, ta, chàng, thiếp, các hạ).\n"
        "\n"
        "2. PHONG THÁI XƯNG HÔ HIỆN ĐẠI (ĐÔ THỊ / CÔNG SỞ / ĐỜI THƯỜNG):\n"
        "   - Trật tự xưng hô: [Danh xưng / Vai vế] + [Tên riêng] (Ví dụ: Anh Nam, Chị Mai, Bác Hùng, Chú Tuấn, Cô Lan, Giám đốc Vương, Chủ tịch Trương).\n"
        "   - Giao tiếp công sở dùng 'Tôi — Anh / Chị / Sếp / Bạn'; bạn bè dùng 'Mình — Cậu / Tớ — Cậu'; tình cảm lứa đôi dùng 'Anh — Em'.\n"
        "   - Cãi vã, xô xát đường phố dùng 'Mày — Tao'.\n"
        "   - Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'anh ấy, cô ấy, cậu ấy, ông ấy, bà ấy, hắn, gã'.\n"
        "   - Độc thoại nội tâm: Dùng 'tôi' hoặc 'mình'.\n"
    )
}

# =====================================================================
# 4. LINH DỊ / TÂM LINH / PHONG THỦY / ĐẠO MỘ / CAO VÕ HIỆN ĐẠI
# =====================================================================
URBAN_SUPERNATURAL_PROFILE = {
    "description": (
        "【THỂ LOẠI: LINH DỊ / TÂM LINH DÂN GIAN / VỚT XÁC / ĐẠO MỘ / PHONG THỦY ÂM DƯƠNG / CAO VÕ / DỊ NĂNG】\n"
        "\n"
        "1. PHÂN BIỆT RẠCH RÒI 2 TẦNG NGÔN NGỮ:\n"
        "   - TẦNG SINH HOẠT ĐỜI THƯỜNG THÔN DÃ (100% THUẦN VIỆT ĐẠI CHÚNG):\n"
        "     * Mọi hoạt động sinh hoạt gia đình, quan hệ họ hàng, làng xóm, đồ gia dụng, công cụ lao động BẮT BUỘC dùng từ ngữ tiếng Việt phổ thông, mộc mạc, dễ hiểu nhất.\n"
        "     * Việc ma chay, tang tế dùng đúng quán ngữ văn hóa dân gian: 'đội kèn trống ma chay / tang lễ / ban nhạc hiếu', 'làm cỗ', 'ăn cỗ', 'dự cỗ', 'tang ma', 'người già qua đời'. Tuyệt đối không nhầm sang việc mừng/hỷ sự.\n"
        "   - TẦNG TÂM LINH & HUYỀN THUẬT DÂN GIAN:\n"
        "     * Thuật ngữ pháp sự, hiện tượng tâm linh, tà ma và hệ thống huyền thuật dịch sang từ ngữ văn học tương ứng (xác trôi, oán niệm, thế mạng, thủy quỷ, khai đàn, phù chú) để duy trì không khí kỳ bí, trang nghiêm.\n"
        "\n"
        "2. HỆ THỐNG XƯNG HÔ THÔN QUÊ DÂN GIAN (RÀNG BUỘC ĐỘ TUỔI & VAI VẾ):\n"
        "   - Trật tự xưng hô: [Danh xưng / Vai vế] + [Tên riêng] (Ví dụ: Chú Tam Giang, Bác Lý, Bà Liễu, Bà Lưu, Anh Viễn Hầu, Thím Bảy; không dịch đảo ngược kiểu tiếng Trung như 'Tam Giang chú', 'Liễu bà bà').\n"
        "   - QUY TẮC CHUYỂN NGỮ [Tên] + 哥哥 / 姐姐: Dịch thành 'Anh [Tên]', 'Chị [Tên]' (Ví dụ: Anh Viễn Hầu, Chị A Ly; cấm giữ âm cổ trang 'ca ca', 'tỷ tỷ').\n"
        "   - VỢ CHỒNG LỚN TUỔI THÔN QUÊ:\n"
        "     * Xưng hô dân dã theo vai vế đời thực: 'Bà — Tôi', 'Ông — Tôi', 'Bố nó — Mẹ nó', khi bực bội cãi cọ dùng 'Mày — Tao'.\n"
        "     * TUYỆT ĐỐI CẤM dùng cặp đại từ tình cảm lứa đôi trẻ ('Anh — Em') cho vợ chồng già thôn quê!\n"
        "     * Đã chọn cặp xưng hô nào thì giữ nhất quán 100% từ đầu đến cuối cảnh, tuyệt đối không câu trước gọi 'em', câu sau gọi 'mày'.\n"
        "   - NHÂN VẬT CAO TUỔI (BẬC MẸ, BẬC BÀ, BẬC ÔNG):\n"
        "     * Khi trần thuật ngôi thứ ba về phụ nữ đã có tuổi (đã làm mẹ, làm bà): BẮT BUỘC dùng 'Bà' hoặc tên nhân vật; TUYỆT ĐỐI CẤM trần thuật bằng 'cô / cô ta'!\n"
        "     * Khi trần thuật ngôi thứ ba về đàn ông cao tuổi: BẮT BUỘC dùng 'Ông' hoặc tên nhân vật; TUYỆT ĐỐI CẤM trần thuật bằng 'anh / anh ta'!\n"
        "   - QUAN HỆ TRONG GIA ĐÌNH & LÀNG XÓM:\n"
        "     * Bề trên gọi con cháu: Dùng 'Cháu / Con / Mày / Lũ ranh con'.\n"
        "     * Con cháu thưa với bề trên: Luôn xưng 'Cháu / Con' và gọi 'Ông / Bà / Bác / Chú / Cô / Dì'.\n"
        "     * Quan hệ làng xóm, bạn bè hàng xóm chuyện trò: Dùng 'Bác / Chú / Thím / Thím nó / Tôi — Bác / Tao — Mày' nhất quán từ đầu đến cuối cảnh.\n"
        "   - Độc thoại nội tâm: Dùng 'mình' hoặc 'ta'.\n"
    )
}

# =====================================================================
# 5. NGÔN TÌNH / CỔ ĐẠI / ĐIỀN VĂN / CUNG ĐẤU / GIA ĐẤU / TRẠCH ĐẤU
# =====================================================================
ROMANCE_PROFILE = {
    "description": (
        "【THỂ LOẠI: NGÔN TÌNH / CỔ ĐẠI / ĐIỀN VĂN / CUNG ĐẤU / GIA ĐẤU / TRẠCH ĐẤU】\n"
        "\n"
        "1. BẢN SẮC KHUÊ PHÒNG, GIA TỘC & CUNG ĐÌNH:\n"
        "   - Tôn ti hậu cung phong kiến: 'Thái hậu', 'Hoàng hậu', 'Hoàng quý phi', 'Quý phi', 'Phi', 'Tần', 'Quý nhân', 'Thường tại', 'Đáp ứng'.\n"
        "   - Tước vị hoàng thất & quý tộc: 'Thân vương', 'Quận vương', 'Bối lặc', 'Thế tử', 'Quận chúa', 'Cách cách'.\n"
        "   - Thế gia vọng tộc & trạch viện: 'Lão thái quân / Lão phu nhân', 'Đại gia', 'Nhị gia', 'Đại phu nhân', 'Di nương' (vợ lẽ),\n"
        "     'Đích tử' (con trai bà cả), 'Thứ tử' (con trai bà lẽ), 'Đích nữ', 'Thứ nữ', 'Thông phòng nha hoàn'.\n"
        "   - Hôn nhân & lễ nghi: 'Tam thư lục lễ', 'Bát tự', 'Sính lễ', 'Của hồi môn', 'Đính hôn', 'Phân gia'.\n"
        "   - Điền văn nông thôn: Gia cảnh bần hàn, cày cấy, vụ mùa, đời sống thôn dã mộc mạc, chân chất, ấm áp.\n"
        "\n"
        "2. PHONG THÁI XƯNG HÔ CỔ ĐẠI KHUÊ CÁC & CUNG ĐÌNH:\n"
        "   - Trật tự xưng hô cổ đại gia tộc: [Họ / Tên] + [Danh xưng / Thân phận] (Ví dụ: Thẩm ma ma, Cố thái phó, Lục hầu gia, Tiết di nương).\n"
        "   - Tôn ti chủ bộc & hoàng thất: Hoàng thất xưng 'Trẫm — Khanh / Ái phi', 'Thần thiếp — Bệ hạ'. Chủ bộc: Chủ tử xưng 'Bản cung / Ta — Nô tỳ / Ngươi'. Nha hoàn, gia nhân thưa chủ xưng 'Nô tỳ / Nô tài / Tiểu nhân', tuyệt đối cấm xưng 'con / tụi con' với chủ.\n"
        "   - Phu thê tình cảm: 'Chàng — Nàng / Phu quân — Nương tử'. Điền văn nông thôn xưng 'Chàng — Thiếp' hoặc 'Cha nó — Nương nó'.\n"
        "   - Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, nàng, tiểu thư, cô nương'.\n"
        "   - Độc thoại nội tâm: Dùng 'ta' hoặc 'mình'.\n"
    )
}

# =====================================================================
# 6. HỆ THỐNG / TRỌNG SINH / XUYÊN NHANH / VÔ ĐỊCH LƯU
# =====================================================================
SYSTEM_REINCARNATION_PROFILE = {
    "description": (
        "【THỂ LOẠI: HỆ THỐNG / TRỌNG SINH / XUYÊN KHÔNG / KHOÁI XUYÊN / VÔ ĐỊCH LƯU】\n"
        "\n"
        "1. ĐẶC QUYỀN KHI HỆ THỐNG XUYÊN VÀO THẾ GIỚI TU TIÊN / CỔ PHONG:\n"
        "   - Toàn bộ bối cảnh thế giới bên ngoài (cảnh giới tu vi, môn phái, đan dược, pháp bảo, chiêu thức, xưng hô) BẮT BUỘC tuân thủ 100% bản sắc Tu Tiên / Cổ Phong như thể loại Xianxia.\n"
        "   - CẢNH GIỚI TU VI: Bắt buộc dùng thuật ngữ tu chân Hán-Việt chuẩn mực ('Luyện Linh thập cảnh', 'Luyện Linh tam cảnh', 'Luyện Linh tứ cảnh', 'Trúc Cơ', 'Kim Đan'...), không dịch thành số thứ tự đời thường.\n"
        "   - ĐỘT PHÁ TU VI: Ngưỡng nghẽn trước khi đột phá (瓶颈) dịch là 'bình cảnh' hoặc 'nút thắt cảnh giới'.\n"
        "   - Môn phái: 'Thiên Tang Linh Cung', 'Ngoại viện', 'Nội viện', 'Trưởng lão', 'Bế quan', 'Bế tử quan', 'Phong Vân Tranh Bá'...\n"
        "\n"
        "2. BẢN SẮC CƠ GIỚI & GIAO DIỆN HỆ THỐNG:\n"
        "   - Giọng điệu Hệ Thống máy móc chuẩn xác trong ngoặc vuông: 【Hệ thống đang tải...】, 【Hệ thống bị động khởi động...】.\n"
        "   - Thuật ngữ game hóa: 'Kỹ năng bị động', 'Kỹ năng chủ động', 'Bàn quay / Vòng quay', 'Kim chỉ', 'Điểm bị động / Điểm tích lũy', 'Gói quà tân thủ', 'Bảng thuộc tính'.\n"
        "   - Cấp bậc kỹ năng: 'Hậu Thiên cấp 1 / Hậu Thiên Lv.1', 'Tiên Thiên', 'Phẩm giai'.\n"
        "\n"
        "3. PHONG THÁI XƯNG HÔ:\n"
        "   - Khi ở bối cảnh Tu Tiên / Cổ phong: Xưng hô cổ phong 'Ta — Ngươi', 'Huynh — Đệ'. Tuyệt đối cấm các đại từ hiện đại/teen ('tụi mình', 'tụi em') trong đối thoại và suy nghĩ của tu sĩ!\n"
        "   - Trần thuật nam chính: Dùng tên nhân vật hoặc 'hắn, gã', tuyệt đối không dùng 'cậu, cậu ấy'.\n"
        "   - Hệ Thống tự xưng: Dùng 'Bản hệ thống' hoặc 'Hệ thống'; gọi người dùng là 'Ký chủ' hoặc 'Túc chủ'.\n"
        "   - Độc thoại nội tâm: Dùng 'ta' (cổ phong) hoặc 'tôi/mình' (hiện đại).\n"
    )
}

# =====================================================================
# 7. MẠT THẾ / KHOA HUYỄN / TINH TẾ / CƠ GIÁP / VIỄN TƯỞNG / ZOMBIE
# =====================================================================
SCI_FI_APOCALYPSE_PROFILE = {
    "description": (
        "【THỂ LOẠI: MẠT THẾ / TẬN THẾ ZOMBIE / KHOA HUYỄN / TINH TẾ / CƠ GIÁP / VIỄN TƯỞNG】\n"
        "\n"
        "1. BẢN SẮC MẠT THẾ SINH TỒN & KHOA HỌC VIỄN TƯỞNG:\n"
        "   - Cấp bậc dị năng & sức mạnh: Dị năng giả ('Nhất giai', 'Nhị giai', 'Tam giai'... hoặc 'Cấp 1', 'Cấp 2'... 'Cấp S', 'SS', 'SSS'); Hệ dị năng: 'Hệ Lôi', 'Hệ Hỏa', 'Hệ Băng', 'Hệ Không Gian', 'Hệ Tinh Thần'...\n"
        "   - Sinh vật đột biến: 'Tang thi / Zombie' (Cấp 1, Cấp 2, Tang thi biến dị, Thi triều, Thi vương), 'Thú biến dị', 'Tinh hạch năng lượng', 'Huyết thanh kháng virus'.\n"
        "   - Khoa học & Viễn tưởng tinh tế: 'Chiến hạm không gian', 'Cơ giáp', 'Bước nhảy không gian', 'Quang não', 'Thiết bị đầu cuối', 'Khiên năng lượng', 'Vũ khí plasma'.\n"
        "\n"
        "2. PHONG THÁI XƯNG HÔ THỰC DỤNG (MẠT THẾ / TINH TẾ):\n"
        "   - Tranh đoạt sinh tồn khốc liệt, xô xát giữa các phe dùng 'Mày — Tao'; đồng đội tin cậy dùng 'Đội trưởng — Tôi / Cậu', 'Anh — Em'.\n"
        "   - Quân sự, căn cứ: 'Chỉ huy / Đội trưởng / Trưởng quan' — 'Chiến sĩ / Cậu / Tôi'. Khẩu lệnh dứt khoát: 'Rõ!', 'Tuân lệnh!'.\n"
        "   - Trần thuật ngôi ba: Dùng tên nhân vật hoặc 'hắn, gã, anh ta, cô ta'.\n"
        "   - Độc thoại nội tâm: Dùng 'tôi' hoặc 'mình'.\n"
    )
}

# =====================================================================
# BỘ QUY TẮC CỐT LÕI TOÀN DỰ ÁN (COMMON RULES - BẮT BUỘC CHO MỌI THỂ LOẠI)
# =====================================================================
COMMON_RULES = (
    "=== QUY CHUẨN DỊCH THUẬT VĂN HỌC & TIÊU CHUẨN AUDIOBOOK (BẮT BUỘC 100%) ===\n"
    "\n"
    "1. ĐƠN VỊ DỊCH THUẬT LÀ CẢ CỤM TỪ / MỆNH ĐỀ (CHỐNG DỊCH BẺ TỪ):\n"
    "   - Đơn vị chuyển ngữ nhỏ nhất là CẢ MỆNH ĐỀ hoặc CẢ CỤM TỪ có nghĩa hoàn chỉnh trong ngữ cảnh; TUYỆT ĐỐI KHÔNG dịch ghép cơ học từng từ đơn lẻ.\n"
    "   - Nghiêm cấm hành vi: thay thế MỘT từ đơn lẻ bên trong một cụm từ/quán ngữ có sẵn, chèn thêm từ vào giữa cụm từ gốc, hoặc bỏ bớt từ làm vỡ cấu trúc cụm từ.\n"
    "   - Khi một cụm từ cần chuyển ngữ, bắt buộc hiểu trọn vẹn ý nghĩa của cả cụm trong câu rồi diễn đạt lại bằng cụm tiếng Việt tự nhiên, mạch lạc.\n"
    "\n"
    "2. NGUYÊN LÝ GIẢI NGHĨA HƯ TỪ, LIÊN TỪ & PHÓ TỪ CÚ PHÁP (CHỐNG RÁC CONVERT):\n"
    "   - Phân biệt rạch ròi: Chỉ tên riêng và thuật ngữ thế giới quan mới giữ âm Hán-Việt. Toàn bộ các hư từ, phó từ chỉ ngữ khí, liên từ chuyển hướng và trạng từ nối câu là thành phần phụ trợ cú pháp, KHÔNG PHẢI danh từ riêng.\n"
    "   - Bắt buộc chuyển hóa 100% các thành phần phụ trợ cú pháp sang từ nối và quán ngữ tiếng Việt thuần thục, đúng bản chất ngữ dụng của câu (ngược lại, trái lại, hóa ra, chẳng qua, dẫu sao, nào ngờ...).\n"
    "   - CẤM TUYỆT ĐỐI việc phiên âm cơ học mặt chữ của các phó từ nối câu hay trợ từ ngữ khí đặt thô thiển vào giữa câu văn hoặc nhầm lẫn thành tên riêng/tước xưng.\n"
    "\n"
    "3. NGUYÊN TẮC KHÓA CHẶT CẶP ĐẠI TỪ LIÊN TỤC (TÍNH NHẤT QUÁN TOÀN CẢNH):\n"
    "   - Trong suốt một phân đoạn giao tiếp giữa hai nhân vật, cặp xưng hô đã thiết lập bắt buộc phải duy trì nhất quán 100% từ đầu đến cuối cảnh, tuyệt đối không tráo đổi hoặc nhảy đại từ giữa các câu thoại liền kề.\n"
    "   - Ngôi kể trần thuật thứ ba cho mỗi nhân vật phải giữ vững một đại từ xuyên suốt cả phân đoạn, tương xứng với độ tuổi và vị thế nhân vật.\n"
    "\n"
    "4. TOÀN VẸN CHÍNH TẢ & TRÒN VÀNH RÕ CHỮ (TIÊU CHUẨN AUDIOBOOK):\n"
    "   - Mọi từ ngữ trong bản dịch — bao gồm cả từ tượng thanh, tiếng thở dài, cảm thán, mắng chửi — đều phải được viết tròn vành, rõ chữ, đầy đủ âm tiết và dấu câu, mang nghĩa chuẩn xác trong tiếng Việt.\n"
    "   - Nghiêm cấm tuyệt đối tình trạng rụng chữ, cắt cụt âm tiết dở dang hoặc để sót các ký tự lỗi phím làm hư hỏng câu văn.\n"
    "   - Sạch 100% chữ Hán gốc (U+4E00 đến U+9FFF) và Pinyin trong toàn bộ văn bản dịch.\n"
    "\n"
    "5. ĐỒNG NHẤT KHÔNG GIAN BỐI CẢNH (CHỐNG LỆCH THỜI ĐẠI & LÓNG BỒI):\n"
    "   - Ngôn ngữ miêu tả đồ vật, công cụ, sinh hoạt và xưng hô phải tương thích tuyệt đối với thời đại của bối cảnh tác phẩm.\n"
    "   - Tuyệt đối cấm đem tiếng lóng mạng internet, ngôn ngữ ngoại lai hoặc tiếng bồi làm vẩn đục văn phong văn học tiếng Việt chuẩn mực.\n"
    "\n"
    "6. NGUYÊN TẮC PHÂN ĐỊNH: THỰC THỂ / TÊN RIÊNG vs. VĂN BẢN TRẦN THUẬT ĐỜI THƯỜNG:\n"
    "   - PHẦN 1: THỰC THỂ & TÊN RIÊNG (Nhân vật, Địa danh, Môn phái, Cảnh giới, Công pháp, Chiêu thức, Pháp bảo & Điển cố thành ngữ kinh điển):\n"
    "     * Toàn bộ các danh xưng, thuật ngữ thế giới quan và điển cố ước lệ này thuộc hệ thống THỰC THỂ: BẮT BUỘC giữ đúng âm Hán-Việt văn học trang trọng quen thuộc (hoặc theo đúng BẢNG THỰC THỂ cung cấp), tuyệt đối KHÔNG 'thuần Việt hóa' ngô nghê làm mất đi khí chất hào sảng của nguyên tác (giữ trọn vẹn phong vị như các tuyệt kỹ, thần thông, thành ngữ điển cố kinh điển).\n"
    "   - PHẦN 2: TỪ NGỮ MIÊU TẢ, CỬ CHỈ & KHẨU NGỮ ĐỜI THƯỜNG (CHỐNG RÁC CONVERT TỐI NGHĨA):\n"
    "     * Toàn bộ các từ ngữ KHÔNG PHẢI thực thể (cử chỉ ánh mắt, nét mặt nụ cười, động tác sinh hoạt, tiếng thở dài, tiếng mắng chửi, liên từ nối câu, hư từ phó từ):\n"
    "     * BẮT BUỘC chuyển ngữ sang tiếng Việt toàn dân tự nhiên, mượt mà, dễ hiểu tức thì cho người nghe audio.\n"
    "     * TUYỆT ĐỐI CẤM dịch nghĩa đen từng chữ hoặc để nguyên âm Hán-Việt thô cứng (kiểu convert) cho các cử chỉ, khẩu ngữ đời thường khi tiếng Việt đã có cách diễn đạt sống động, chuẩn xác.\n"
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

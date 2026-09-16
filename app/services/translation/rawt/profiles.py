# -*- coding: utf-8 -*-
"""
app/services/translation/rawt/profiles.py
=========================================
BỘ PROFILE VĂN PHONG VÀ BẢN SẮC THỂ LOẠI CHO TRANSLATOR RAWT

Cung cấp các quy chuẩn dịch thuật chuyên biệt cho từng thể loại truyện:
1. Tiên Hiệp, Tu Chân, Huyền Huyễn
2. Kiếm Hiệp, Võ Lâm Giang Hồ, Lục Lâm Hảo Hán, Sa Trường
3. Đô Thị Hiện Đại, Thương Trường, Học Đường, Giới Giải Trí
4. Đô Thị Linh Dị, Phong Thủy, Vớt Xác, Bắt Ma, Đạo Mộ
5. Ngôn Tình, Cổ Đại, Điền Văn, Cung Đấu, Trạch Đấu
6. Hệ Thống, Trọng Sinh, Xuyên Không, Khoái Xuyên, Vô Địch Lưu
7. Mạt Thế, Tận Thế Zombie, Khoa Huyễn, Tinh Tế, Cơ Giáp
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# =====================================================================
# 1. TIÊN HIỆP, TU CHÂN, HUYỀN HUYỄN
# =====================================================================
XIANXIA_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI TIÊN HIỆP, TU CHÂN, HUYỀN HUYỄN\n"
        "1. THUẬT NGỮ BẢN SẮC TU TIÊN & CHỨC DANH NGHỀ NGHIỆP:\n"
        "   - Cảnh giới & thứ bậc tu vi: Luyện Khí, Trúc Cơ, Kim Đan, Nguyên Anh, Hóa Thần, Luyện Hư, Hợp Thể, Đại Thừa, Độ Kiếp. Nút thắt gọi là bình cảnh. Đột phá hoặc đốn ngộ. Phân cấp gồm sơ kỳ, trung kỳ, hậu kỳ, đỉnh phong, viên mãn, đại viên mãn, bán bộ (như Bán bộ Kim Đan).\n"
        "   - Tu luyện và tài nguyên: Bế quan, bế tử quan, độ kiếp, thiên kiếp, lôi kiếp, tâm ma, tẩu hỏa nhập ma, đoạt xá, ngã xuống (vẫn lạc), đan điền, thức hải, thần thức, linh khí, linh căn, cực phẩm linh căn, chân nguyên, pháp lực, đạo tâm, đạo vận, pháp tắc, linh thạch (hạ, trung, thượng, cực phẩm linh thạch), đan dược, linh thảo, phù lục, pháp bảo, linh bảo.\n"
        "   - Môn phái, chức danh và tu sĩ: Tông môn, thánh địa, động phủ, Linh Cung, đệ tử (ngoại môn, nội môn, chân truyền), chấp sự, trưởng lão, phong chủ, tông chủ, chưởng môn, lão tổ, Tàng Kinh Các, Dược Viện, lôi đài, bí cảnh, nơi thí luyện; tán tu, thể tu, kiếm tu, đan tu, phù tu, trận tu, ma tu, yêu tu, quỷ tu, đạo lữ.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ NÊN DÙNG (BỐI PHẬN, CHỨC DANH, TÊN NHÂN VẬT & TIÊN GIA):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + CHỨC NĂNG / CHỨC VỤ / BỐI PHẬN / NGHỀ NGHIỆP: Bắt buộc giữ âm Hán-Việt cổ phong chuẩn xác khi kết hợp họ/tên nhân vật với chức danh, bối phận hoặc nghề nghiệp (ví dụ: Tạ Trưởng lão, Lâm Tông chủ, Vương Chưởng môn, Kiều Trưởng lão, Tiêu Phong chủ, Trương Tiên sư, Nam Cung Tiên tử, Tạ ca ca, Lâm tỷ tỷ, Dương sư huynh, Mặc sư đệ...).\n"
        "   - Đại từ nhân xưng: Ta và Ngươi; Tại hạ và Các hạ; Chư vị, đạo hữu, hắn, nàng, y, gã, bọn họ, chúng ta...\n"
        "   - Tự xưng theo bối phận và thân phận: Bổn tọa, bổn tôn, bổn tiên, bổn tông, vi sư, đồ nhi, đệ tử, vãn bối, bỉ nhân, tiểu sinh, tiểu nữ, tiểu nhân, lão phu, lão hủ, thần, vi thần, hạ quan, thiếp thân, nô tỳ, nô tài, bần đạo, bần tăng.\n"
        "   - Xưng hô tôn xưng, chức danh tu sĩ & sư môn: Đạo hữu, Chân quân, Tiên tôn, Tiên sư, Tiên gia, Tiên trưởng, Đạo trưởng, Tiền bối, Vãn bối, Cao nhân, Đại lão, Sư phụ, Sư tôn, Sư huynh, Sư đệ, Sư tỷ, Sư muội, Sư thúc, Sư bá, Sư tổ, Tông chủ, Trưởng lão, Chưởng môn.\n"
        "   - Xưng hô người lạ và xã giao: Lão trượng, lão bà, lão ca, huynh đài, hiền huynh, hiền đệ, hiền muội, tiểu huynh đệ, vị tiểu ca này, công tử, cô nương, thiếu gia, tráng sĩ.\n"
        "   - Quan hệ bối phận thân tộc cổ phong: Phụ thân, mẫu thân, cha, mẹ, cha mẹ, nương, bá phụ, bá mẫu, thúc phụ, thúc mẫu, cô mẫu, di mẫu, cữu phụ, tằng phụ, tằng mẫu, huynh trưởng, ca ca, đại ca, tỷ tỷ, đệ đệ, muội muội, phu quân, tướng công, thê tử, nương tử, phu nhân, nhi tử, nữ nhi, hài tử. Vợ lẽ hoặc thiếp bắt buộc dịch thành di nương. Đối với dì (em gái của mẹ / 小姨), BẮT BUỘC dịch thành 'Tiểu di' (TUYỆT ĐỐI CẤM dịch thành 'dì nhỏ' hoặc 'dì' theo khẩu ngữ đời thường).\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Cấm đại từ hiện đại: Tuyệt đối cấm các từ tôi, bạn, cậu, tớ, mình, anh ấy, chị ấy, bọn em, tụi em, tụi mình, chú mày, ông - tôi.\n"
        "   - Cấm gọi người lạ kiểu hiện đại: Tuyệt đối cấm gọi người lạ bằng từ hiện đại như ông lão, cụ già, bác ơi, chú ơi, anh trai này, cậu em này, chú mày, em trai này, cô em, cháu ơi. Bắt buộc dùng xưng hô cổ phong như lão trượng, lão bà, huynh đài, tiểu huynh đệ, vị tiểu ca này, công tử, cô nương.\n"
        "   - Cấm xưng cháu hoàn toàn và cấm xưng con tùy tiện: Tuyệt đối CẤM xưng 'cháu' với bất kỳ ai trong bối cảnh cổ đại (cấm xưng cháu với tiền bối, người lạ, ông bà, sư phụ). Xưng 'con' chỉ được châm chước cho con ruột thưa cha mẹ hoặc đồ nhi thưa sư phụ. Thưa tiền bối/người lớn tuổi bắt buộc xưng vãn bối hoặc tiểu nhân (cấm xưng con hay cháu).\n"
        "   - Cấm cách gọi đời thường hiện đại: Cấm gọi bố, ba, má, thím, mợ, dượng, dì nhỏ (BẮT BUỘC CHỈ DÙNG 'Tiểu di'), anh, chị, em trai, em gái, con trai, con gái trong bối cảnh tu tiên (cho phép dùng cha, mẹ, cha mẹ, phụ thân, mẫu thân, ca ca, tỷ tỷ, đệ đệ, muội muội, nhi tử, nữ nhi). Cấm gọi sư phụ là thầy, cấm xưng em với sư phụ, sư huynh hoặc sư tỷ."
    )
}

# =====================================================================
# 2. VÕ HIỆP, KIẾM HIỆP, GIANG HỒ, LỤC LÂM, THỦY HỬ, DÃ SỬ
# =====================================================================
WUXIA_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI KIẾM HIỆP, VÕ LÂM, GIANG HỒ TRUYỀN THỐNG, LỤC LÂM HẢO HÁN, THỦY HỬ, DÃ SỬ SA TRƯỜNG\n"
        "1. THUẬT NGỮ BẢN SẮC VÕ HIỆP GIANG HỒ & CHỨC DANH SA TRƯỜNG:\n"
        "   - Quán ngữ giang hồ: 朴刀 dịch thành phác đao (cấm dịch thành bát đao hay bắp đao); 汴京 dịch thành Biện Kinh; 好汉 dịch thành hảo hán (cấm dịch thành hảo hồng hay người tốt); 结交好汉 dịch thành kết giao hảo hán; 火并 hoặc 火拼 dịch thành hỏa tịnh hoặc thanh trừng nội bộ; 纳头便拜 hoặc 拜倒 dịch thành sụp lạy rụp hoặc lạy phục; 铁布衫 hoặc 金钟罩 dịch thành Thiết Bố Sam hoặc Kim Chung Tráo; 饶一条性命 dịch thành tha cho một đường sống hoặc mở một con đường sống; 勒住马缰 dịch thành ghì ngựa dừng cương hoặc theo hầu trước sau.\n"
        "   - Thứ bậc cao thủ: Tam lưu, nhị lưu, nhất lưu cao thủ; đỉnh phong, tuyệt đỉnh cao thủ; Hậu thiên, Tiên thiên, Hóa Cảnh, Tông Sư, Đại Tông Sư; nhập môn, tiểu thành, đại thành, viên mãn; Nhâm Đốc nhị mạch, khí hải, đan điền, Bách Hội, điểm huyệt, giải huyệt, nội lực, chân khí, kình đạo.\n"
        "   - Sơn trại, chức danh nghề nghiệp & sa trường: Sơn trại, tụ nghĩa sảnh, Đại đương gia, Nhị đương gia, Trại chủ, Đầu lĩnh, Tiên phong, Giáo đầu, Bang chủ, Đà chủ, Đường chủ, Hộ pháp, Tiêu cục, Tiêu đầu, tiểu lâu la. Quân quan: Tướng quân, Mạt tướng, Ty chức, Thuộc hạ.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ NÊN DÙNG (BỐI PHẬN, CHỨC DANH, TÊN NHÂN VẬT & GIANG HỒ LỤC LÂM):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + CHỨC NĂNG / CHỨC VỤ / BỐI PHẬN / NGHỀ NGHIỆP: Bắt buộc giữ nguyên trật tự Hán-Việt cổ phong chuẩn xác khi gọi kết hợp họ/tên nhân vật với chức vụ, nghề nghiệp hoặc bối phận (ví dụ: Lâm Trại chủ, Vương Bang chủ, Dương Tiêu đầu, Lý Tướng quân, Kiều Trưởng lão, Lâm Đại đương gia, Tiêu Giáo đầu, Tạ ca ca, Lâm tỷ tỷ...).\n"
        "   - Quan hệ bối phận thân tộc cổ phong: BẮT BUỘC dịch 小姨 thành 'Tiểu di' (TUYỆT ĐỐI CẤM dịch thành 'dì nhỏ' hay 'dì' kiểu hiện đại). Bắt buộc dùng phụ thân, mẫu thân, cha, mẹ, nương, ca ca, tỷ tỷ, đệ đệ, muội muội, nhi tử, nữ nhi.\n"
        "   - Giang hồ hảo hán và huynh đệ lục lâm: Ca ca, Hiền đệ, Tiểu đệ, Đại ca, Nhị ca, Huynh đệ, Chúng huynh đệ, Lão đệ, Chư vị huynh đệ, Sơn trại huynh đệ; xưng hô ngang hàng dùng Ta - Ngươi hoặc Huynh - Đệ.\n"
        "   - Tôn xưng & chức danh giang hồ: Trại chủ, Đại đương gia, Tiêu đầu, Tổng tiêu đầu, Bang chủ, Hảo hán, Lão anh ca, Tráng sĩ, Đại hiệp, Thiếu hiệp, Nữ hiệp, Anh hùng, Lão trượng, Cô nương.\n"
        "   - Tự xưng tôn ti, bối phận & khiêm xưng: Tiểu nhân, Thảo dân, Mạt tướng, Ty chức, Tại hạ, Vãn bối, Bất tài, Tiêu đệ, Đồ nhi; Lão tử (khi giận dữ xưng Ông đây hoặc Lão tử).\n"
        "   - Đối thoại sa trường và quan trường: Mạt tướng bái kiến Tướng quân; Thuộc hạ tuân lệnh; Ty chức hiểu rõ; Khởi bẩm Đại nhân.\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Cấm đại từ hiện đại: Tuyệt đối cấm xưng hô tôi - bạn, cậu - tớ, anh ấy, chị ấy, bọn em, tụi em, tụi mình, chú mày trong giang hồ lục lâm.\n"
        "   - Cấm xưng hô gia đình hiện đại: Cấm xưng hô bố, ba, má, thím, mợ, dượng, dì nhỏ (BẮT BUỘC CHỈ DÙNG 'Tiểu di'), anh trai, em gái, con trai, con gái trong bối cảnh kiếm hiệp.\n"
        "   - Cấm tuyệt đối xưng 'cháu': Bắt buộc xưng vãn bối hoặc tiểu nhân. Tuyệt đối không xưng cháu với tiền bối hay người lớn tuổi."
    )
}

# =====================================================================
# 3. ĐÔ THỊ HIỆN ĐẠI, THƯƠNG TRƯỜNG, HỌC ĐƯỜNG, GIỚI GIẢI TRÍ
# =====================================================================
URBAN_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI ĐÔ THỊ HIỆN ĐẠI, THƯƠNG TRƯỜNG, HỌC ĐƯỜNG, GIỚI GIẢI TRÍ\n"
        "1. THUẬT NGỮ BẢN SẮC & CHỨC DANH NGHỀ NGHIỆP:\n"
        "   - Thương trường và công sở: Tập đoàn, Chủ tịch Hội đồng quản trị, Tổng Giám đốc (Tổng tài / CEO), Giám đốc điều hành, Trợ lý, Thư ký, Hợp đồng, Đấu thầu, Rót vốn, Cổ phần, Thị trường chứng khoán, Thâu tóm, Phá sản.\n"
        "   - Học đường và giới trẻ: Bạn học, Lớp trưởng, Giáo viên chủ nhiệm, Hiệu trưởng, Căn tin, Ký túc xá, Học bá, Học tra, Hoa khôi trường, Nam thần trường, Thi đại học, Điểm chuẩn.\n"
        "   - Giới giải trí và mạng xã hội: Giới giải trí, Showbiz, Minh tinh, Đỉnh lưu, Ảnh đế, Ảnh hậu, Đạo diễn, Biên kịch, Nhà sản xuất, Người đại diện, Trợ lý, Hot search, Bảng xếp hạng, Người hâm mộ (Fan), Thủy quân, Scandal, Tẩy trắng.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ NÊN DÙNG (BỐI PHẬN, CHỨC DANH, TÊN NHÂN VẬT & HIỆN ĐẠI):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + CHỨC DỤNG / NGHỀ NGHIỆP: Giám đốc Lý, Thư ký Vương, Trợ lý Trương, Thầy Trần, Cô Lâm, Bác sĩ Vương, Luật sư Trương...\n"
        "   - Đời thường và bạn bè: Tôi - Bạn, Cậu - Tớ, Mình - Cậu; Anh - Em, Chị - Em; Mày - Tao (khi thân mật suồng sã hoặc cãi vã).\n"
        "   - Công sở và đối tác: Chủ tịch, Tổng Giám đốc, Giám đốc Lý, Thư ký Vương, Trợ lý Trương; Tôi - Anh/Chị, Tôi - Ngài.\n"
        "   - Gia đình bối phận hiện đại: Bố, Ba, Mẹ, Má, Bác, Chú, Cô, Dì, Cậu, Thím, Anh trai, Chị gái, Em trai, Em gái, Con trai, Con gái, Cháu.\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Cấm đại từ cổ trang: Tuyệt đối cấm xưng hô cổ trang như ta - ngươi, tại hạ, các hạ, huynh đệ, bản tọa, tiểu nữ, lão phu trong bối cảnh đô thị hiện đại đời thường."
    )
}

# =====================================================================
# 4. ĐÔ THỊ LINH DỊ, PHONG THỦY, VỚT XÁC, BẮT MA, ĐẠO MỘ
# =====================================================================
URBAN_SUPERNATURAL_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI ĐÔ THỊ LINH DỊ, PHONG THỦY, VỚT XÁC, BẮT MA, ĐẠO MỘ\n"
        "1. THUẬT NGỮ BẢN SẮC & CHỨC DANH NGHỀ NGHIỆP:\n"
        "   - Bắt ma và phong thủy: Mao Sơn, Đạo sĩ, Thiên sư, Phong thủy sư, Âm dương tiên sinh, La bàn, Chu sa, Bùa đào mộc kiếm, Bát quái kính; Âm khí, Dương khí, Sát khí, Tà khí, Oán khí, Cương thi, Lệ quỷ, Ma đói, Ma da; Vớt xác, Người vớt xác, Âm dương đò, Khắc chết, Trùng tang, Hóa giải, Siêu độ.\n"
        "   - Trộm mộ và đạo mộ: Đạo mộ, Mô kim hiệu úy, Phát khâu trung lang tướng; Đấu lớn, Đấu nhỏ, Minh khí, Bánh quy (chỉ bánh chưng/thây ma biến dị), Bật nắp quan tài, Cơ quan, Cạm bẫy.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ NÊN DÙNG (BỐI PHẬN, CHỨC DANH NGHỀ NGHIỆP & TÊN NHÂN VẬT):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + NGHỀ NGHIỆP / XƯNG HÔ DÂN GIAN: Cửu thúc, Nhị gia, Bát gia, Chú Ba, Anh Hai, Lâm Đạo trưởng, Vương Thiên sư, Trương Phong thủy sư, Thần y Tạ...\n"
        "   - Nghề nghiệp và sư môn: Sư phụ - Đồ đệ (hoặc Thầy - Trò), Đạo trưởng, Thiên sư, Lão tiên sinh; xưng hô nghề nghiệp như Cửu thúc, Nhị gia, Bát gia, Chú Ba, Anh Hai.\n"
        "   - Xã hội nông thôn và huyền bí: Tôi - Bác, Cháu - Chú, Tôi - Cậu, Chú - Cháu; khi trừ tà đối đầu quỷ ma dùng Ta - Ngươi, Nghiệt súc, Yêu nghiệt.\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Cấm từ tiên hiệp cung đình và công sở: Không dùng đại từ tiên hiệp cung đình như bản tọa, vi thần, thần thiếp hay danh xưng công sở như sếp, CEO vào bối cảnh dân gian thôn dã."
    )
}

# =====================================================================
# 5. NGÔN TÌNH, CỔ ĐẠI, ĐIỀN VĂN, CUNG ĐẤU, TRẠCH ĐẤU
# =====================================================================
ROMANCE_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI NGÔN TÌNH, CỔ ĐẠI, ĐIỀN VĂN, CUNG ĐẤU, GIA ĐẤU, TRẠCH ĐẤU\n"
        "1. THUẬT NGỮ BẢN SẮC & CHỨC DANH HẬU CUNG TRẠCH ĐẤU:\n"
        "   - Hoàng thất và hậu cung: Thái hậu, Hoàng hậu, Hoàng quý phi, Quý phi, Phi, Tần, Quý nhân, Thường tại, Đáp ứng; Thân vương, Quận vương, Bối lặc, Thế tử, Quận chúa, Cách cách; Hoàng thượng, Bệ hạ, Điện hạ, Nương nương, Tiểu chủ; Ma ma (nghĩa là nhũ mẫu hoặc cung nữ lớn tuổi), Cô cô (nghĩa là nữ quan), Cung nữ, Thái giám, Công công.\n"
        "   - Phủ đệ và trạch đấu: Hầu phủ, Quốc công phủ, Tướng phủ, Lão phu nhân, Thái phu nhân, Đại lão gia, Nhị gia, Tam gia, Đại phu nhân, Nhị phu nhân, Di nương (nghĩa là vợ lẽ hoặc thiếp - bắt buộc dùng di nương, cấm dịch thành dì), Đích nữ, Thứ nữ, Đích tử, Thứ tử, Thông phòng, Nha hoàn thông phòng, Đại nha hoàn, Nha hoàn chải đầu, Nha đầu.\n"
        "   - Tình cảm và sắc thái ngôn tình: Thanh mai trúc mã, Nước chảy hoa trôi, Tương tư, Nhớ nhung, Vấn vương, Động lòng, Rung động, Cưng chiều, Sủng ái, Ngọt ngào, Tình cảm thắm thiết, Hờn dỗi, Nũng nịu, Tờn bỡn, Ăn giấm, Ghen tuông.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ NÊN DÙNG (BỐI PHẬN, CHỨC DANH, TÊN NHÂN VẬT & GIA ĐẤU):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + BỐI PHẬN / CHỨC VỤ / TÔN XƯNG: Bắt buộc giữ âm Hán-Việt cổ phong khi gọi tên/họ nhân vật kết hợp bối phận hoặc chức vị (ví dụ: Lâm Lão phu nhân, Tạ Thái phu nhân, Vương Nhị gia, Nam Cung Quận chúa, Lâm di nương, Tạ ca ca, Lâm tỷ tỷ, Tô nương tử...).\n"
        "   - Phu thê và tình nhân: Phu quân - Thê tử hoặc Nương tử, Tướng công - Nương tử; Chàng - Thiếp (thể hiện ngọt ngào tình tứ); Ta - Nàng (nam tự xưng ta, gọi nữ là nàng).\n"
        "   - Hoàng gia và chủ tớ: Bệ hạ - Thần thiếp, Trẫm - Ái phi; Nô tỳ hoặc Nô tài - Chủ tử hoặc Nương nương.\n"
        "   - Trạch viện gia đấu & bối phận: Phụ thân, Mẫu thân, Lão thái quân, Tổ mẫu, Huynh trưởng, Đại ca, Tỷ tỷ, Đệ đệ, Muội muội...\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Cấm đại từ hiện đại: Tuyệt đối cấm xưng hô hiện đại như anh - em đời thường, tôi - cô, chồng - vợ đời thường, tôi - bạn, cậu - tớ, chúng mình, tụi em trong bối cảnh cung đấu hoặc trạch đấu cổ đại.\n"
        "   - Cấm xưng cháu hoàn toàn và cấm xưng con tùy tiện: Cấm nha hoàn, thái giám hay bề dưới tự xưng con hoặc cháu với chủ tử, thái hậu hay hoàng thượng. Tuyệt đối CẤM xưng 'cháu' với bất kỳ ai. Chỉ có con ruột thưa cha mẹ hoặc ông bà người thân ruột thịt mới được xưng con. Bề dưới thưa chủ tử bắt buộc tự xưng nô tỳ, nô tài hoặc thần thiếp."
    )
}

# =====================================================================
# 6. HỆ THỐNG, TRỌNG SINH, XUYÊN KHÔNG, KHOÁI XUYÊN, VÔ ĐỊCH LƯU
# =====================================================================
SYSTEM_REINCARNATION_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI HỆ THỐNG, TRỌNG SINH, XUYÊN KHÔNG, KHOÁI XUYÊN, VÔ ĐỊCH LƯU\n"
        "1. THUẬT NGỮ BẢN SẮC:\n"
        "   - Cơ chế Hệ thống: Hệ thống và Ký chủ (hoặc Túc chủ); Đinh! hoặc Nhắc nhở: ... (hoặc Thông báo: ...); Phát hành nhiệm vụ, hoàn thành nhiệm vụ, thất bại nhiệm vụ; Phần thưởng nhiệm vụ, gói quà tân thủ; Điểm tích lũy, điểm danh vọng, điểm phản diện; Thăng cấp, cộng điểm thuộc tính; Bảng điều khiển thuộc tính, giao diện trạng thái; Thương thành hệ thống, đổi đạo cụ; Rút thưởng, mười lần rút liên tiếp.\n"
        "   - Trọng sinh và xuyên không: Trọng sinh, tái sinh; Xuyên không, xuyên việt; Khoái xuyên, xuyên nhanh; Hệ thống vô địch, vô địch lưu; Ngón tay vàng, bàn tay vàng (kim thủ chỉ); Nhân vật phản diện, bia đỡ đạn.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ NÊN DÙNG (BỐI PHẬN, CHỨC DANH, TÊN NHÂN VẬT & HỆ THỐNG):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + CHỨC VỤ / BỐI PHẬN: Tuân thủ nghiêm ngặt cách gọi kết hợp tên/họ với chức vụ hoặc bối phận theo thời đại thế giới xuyên vào (ví dụ: Tạ Trưởng lão, Lâm Trại chủ, Vương Giám đốc...).\n"
        "   - Giao tiếp Hệ thống: Hệ thống tự xưng Bản hệ thống hoặc Hệ thống - gọi người dùng là Ký chủ hoặc Túc chủ. Ký chủ gọi Hệ thống hoặc Ngươi (khi bực tức dùng mày).\n"
        "   - Thế giới bên ngoài: Tuân thủ nghiêm ngặt theo thời đại thế giới xuyên vào. Nếu xuyên vào Cổ đại hoặc Tu chân thì dùng 100% xưng hô cổ phong Ta - Ngươi, thân tộc cổ phong. Nếu xuyên vào Hiện đại thì dùng đại từ hiện đại Tôi - Cậu hoặc Anh.\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Khi xuyên vào bối cảnh cổ đại hoặc tu chân: Tuyệt đối cấm xưng hô hiện đại như tôi - bạn, cậu - tớ, anh - em, tụi em, bọn em, tụi mình, chú mày. Cấm tuyệt đối xưng 'cháu', cấm xưng 'con' với sư phụ hay tiền bối."
    )
}

# =====================================================================
# 7. MẠT THẾ, TẬN THẾ ZOMBIE, KHOA HUYỄN, TINH TẾ, CƠ GIÁP
# =====================================================================
SCI_FI_APOCALYPSE_PROFILE = {
    "description": (
        "YÊU CẦU DỊCH THỂ LOẠI MẠT THẾ, TẬN THẾ ZOMBIE, KHOA HUYỄN, TINH TẾ, CƠ GIÁP, VIỄN TƯỞNG\n"
        "1. THUẬT NGỮ BẢN SẮC & CHỨC DANH QUÂN ĐỘI:\n"
        "   - Zombie và biến dị: Tang thi hoặc Zombie (triều tang thi, đợt sóng zombie, Tang thi vương); Thú biến dị, tinh hạch, tinh hạch năng lượng; Thuốc biến đổi gen, huyết thanh kháng thể.\n"
        "   - Dị năng và cấp bậc: Nhất giai, Nhị giai, Tam giai, Tứ giai (hoặc Cấp 1, Cấp 2...); Hệ Lôi, Hỏa, Băng, Không Gian, Tinh Thần; Người thức tỉnh, Dị năng giả.\n"
        "   - Tinh tế và khoa huyễn: Chiến hạm không gian, cơ giáp, bước nhảy không gian; Quang não, thiết bị đầu cuối, khiên năng lượng; Pháo ion, vũ khí plasma.\n"
        "2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):\n"
        "   - DẠNG ĐẢO TRẬT TỰ TIẾNG VIỆT THUẦN (TUYỆT ĐỐI CHỈ ÁP DỤNG CHO HƯỚNG ĐỊA LÝ & NGÕ NGÁCH ĐỜI THƯỜNG): CHỈ DUY NHẤT từ chỉ phương hướng/vị trí địa lý (đông, tây, nam, bắc, ngoại ô...) hoặc ngõ ngách đường nhỏ đời thường mới được đảo trật tự để dễ hiểu (ví dụ: 幽州以北 -> phía bắc U Châu, 丹阳城郊 -> ngoại ô Đan Dương Thành, 城东 -> phía đông thành, 青云巷 -> ngõ Thanh Vân, 柳条巷 -> ngõ Liễu Điều...). Tất cả các dạng địa danh khác (núi non, sông biển, thành trì, bí cảnh, môn phái) BẮT BUỘC giữ nguyên trật tự Hán-Việt chuẩn bản sắc cổ phong (Thái Hòa Sơn, Lạc Hà Phong, Tử Cấm Thành, Thiếu Lâm Tự, Trường An Thành, Lạc Dương Thành...)!\n"
        "3. QUY CHUẨN XƯNG HÔ MẠT THẾ VÀ KHOA HUYỄN (BỐI PHẬN, CHỨC DANH, TÊN NHÂN VẬT):\n"
        "   - KẾT HỢP TÊN NHÂN VẬT + CHỨC VỤ QUÂN ĐỘI: Chỉ huy Trương, Đội trưởng Lâm, Thuyền trưởng Lý, Quân đoàn trưởng Tạ...\n"
        "   - Quân đội và căn cứ: Chỉ huy, Đội trưởng, Thuyền trưởng, Quân đoàn trưởng, Binh sĩ, Chiến sĩ, Đồng chí... Tự xưng Tôi, thưa Báo cáo Chỉ huy hoặc Báo cáo Đội trưởng. Khẩu lệnh dùng Rõ! hoặc Tuân lệnh!.\n"
        "   - Đồng đội sinh tồn: Tôi, Cậu, Tớ, Anh, Em, Chúng ta, Mọi người, Đồng đội...\n"
        "   - Xung đột và băng đảng: Mày - Tao, Thằng khốn, Lũ chúng mày...\n"
        "4. QUY CHUẨN XƯNG HÔ CẤM (TUYỆT ĐỐI KHÔNG SỬ DỤNG):\n"
        "   - Cấm đại từ cổ trang: Cấm dùng đại từ kiếm hiệp như tại hạ, các hạ, huynh đài, bản tọa, tiểu nữ, lão phu, vi sư trên tàu vũ trụ, chiến hạm hay sinh tồn súng đạn."
    )
}

# =====================================================================
# BỘ QUY TẮC CHUYỂN NGỮ CỐT LÕI (COMMON RULES CHO TOÀN DỰ ÁN)
# =====================================================================
COMMON_RULES = (
    "BỘ QUY TẮC DỊCH THUẬT CỐT LÕI VÀ TIÊU CHUẨN AUDIOBOOK:\n"
    "1. BẢO VỆ TÊN RIÊNG & THỰC THỂ KHÓA CỨNG (BẢNG DỊCH HÁN):\n"
    "   - Khóa 100% theo Bảng thực thể: Bắt buộc dùng đúng 100% bản dịch đã quy định từ Bảng thực thể ở trên cho toàn bộ danh từ riêng, tên nhân vật, địa danh, tông môn, võ học, yêu thú, bảo vật và thuật ngữ. Tuyệt đối cấm tự ý đổi tên, cấm bẻ nghĩa và cấm để sót chữ Hán.\n"
    "   - Dịch thẳng một chiều & CẤM TUYỆT ĐỐI ngoặc song ngữ: Mỗi từ và tên riêng chỉ xuất hiện duy nhất một bản dịch tiếng Việt mượt mà hòa vào câu văn. Dù từ Hán đó khó dịch, BẮT BUỘC phải chọn 1 bản dịch chuẩn mực nhất, TUYỆT ĐỐI CẤM xuất ra dạng 'Chữ Hán (Bản dịch tiếng Việt)' (như 哼 (Hừ!) hay 大摔碑手 (Đại Toại Bi Thủ)), cấm lặp từ trong ngoặc, không mở ngoặc chú thích nghĩa trong thân bài.\n"
    "2. NGÔN NGỮ 100% TIẾNG VIỆT, DIỄN ĐẠT THOÁT Ý & CẤM CONVERT THÔ:\n"
    "   - Bản dịch bắt buộc 100% tiếng Việt hoàn chỉnh, chuẩn ngữ pháp tự nhiên. Tuyệt đối cấm phiên âm Hán Việt cơ học từng chữ (Vietphrase thô).\n"
    "     * Phó từ và quán ngữ convert thô: cấm cánh nhiên hoặc cánh nhiên như thử (dịch thành vậy mà, lại có thể...), cấm một tưởng đáo (dịch thành không ngờ, nào ngờ), cấm bất quý thị (dịch thành xứng danh là, không hổ danh), cấm khẩn tiếp trước (dịch thành ngay tiếp theo, liền sau đó), cấm ngạnh trước đầu bì (dịch thành cắn răng chịu đựng, bấm bụng, đánh bạo), cấm liêu liêu vô cơ (dịch thành ít ỏi, đếm trên đầu ngón tay), cấm nhất đán (dịch thành một khi...).\n"
    "   - CẤM TUYỆT ĐỐI TIẾNG ANH: Không dùng từ tiếng Anh như But, And, So, Or, If, No, OK, Yeah, Brother, Sir... Các liên từ tiếng Trung như 但, 但是, 可是, 不过, 然而 bắt buộc dịch thành Nhưng, Thế nhưng, Tuy nhiên, Song, Có điều...\n"
    "   - SẠCH 100% CHỮ HÁN VÀ PINYIN: Trích dẫn nhật ký, thư từ, văn bia, lời thoại, thơ ca, chú thích chữ Hán bắt buộc dịch sạch sang tiếng Việt, tuyệt đối không để sót chữ Hán nào.\n"
    "3. VĂN PHONG THUẦN VIỆT VÀ TÍNH TRUNG THỰC:\n"
    "   - Tiếng Việt phổ thông, dễ hiểu: Diễn đạt bằng từ ngữ thuần Việt, thông dụng để người đọc hoặc người nghe hiểu ngay tức thì. Không gượng ép Hán Việt lạ lẫm làm câu văn tối nghĩa.\n"
    "   - Dịch thoát ý cả câu & Thấu hiểu nghĩa bóng/hàm ý ngữ cảnh: Tuyệt đối không dịch cứng nhắc bám theo nghĩa đen mặt chữ. Bắt buộc liên kết ý nghĩa của các câu liền trước và liền sau để nhận diện chính xác nghĩa bóng, ẩn dụ, mỉa mai châm biếm, khẩu khí hay hàm ý ngầm của tác giả; từ đó chủ động biến đổi toàn bộ câu từ, cụm từ sang cách diễn đạt tiếng Việt thuần túy, mượt mà và khớp 100% logic diễn biến ngữ cảnh (con người, linh thú, đồ vật hay hiện tượng).\n"
    "   - Trung thực, không phóng tác: Mạch lạc, trung thực với ngữ cảnh tác phẩm (Điều 5). Cấm tự ý bịa đặt, thêm bớt tình tiết hay làm sai lệch nội dung.\n"
    "   - Xử lý câu ngắn: Được phép thêm chút từ nối hoặc từ đệm để câu không bị cộc lốc hay cụt ngủn; nhưng chỉ thêm vừa đủ tránh cụt câu, tuyệt đối cấm lan man kéo dài dòng.\n"
    "4. THÀNH NGỮ, TỤC NGỮ, QUÁN NGỮ VÀ KHẨU NGỮ:\n"
    "   - Nắm bắt trọn vẹn đại ý rồi diễn đạt bằng tiếng Việt phổ thông, mộc mạc, dễ hiểu. Cấm dịch đen từng chữ Hán ngô nghê.\n"
    "   - Thành ngữ văn hóa Trung Quốc đặc thù: Tìm thành ngữ, tục ngữ, cách nói dân gian tương đương trong tiếng Việt; nếu không có tương đương tự nhiên thì diễn đạt thẳng nghĩa dễ hiểu, không ép đối chữ hoa mỹ.\n"
    "   - Khẩu ngữ, cảm thán, chửi thề: Dịch tự nhiên đúng sắc thái nhân vật. Trong bối cảnh cổ phong hoặc kiếm hiệp, tuyệt đối cấm dùng từ lóng đường phố hiện đại lai tạp.\n"
    "5. TIÊU CHUẨN CON SỐ VÀ TIỀN TỆ CHO AUDIOBOOK (TTS):\n"
    "   - Viết bằng chữ cho con số: Số trong lời kể, đối thoại, suy nghĩ, số lượng, tiền tệ, thời gian bắt buộc viết hoàn toàn bằng chữ tiếng Việt để TTS đọc chuẩn ngữ điệu tự nhiên. Tiêu đề số chương và mốc năm tháng cụ thể được giữ số Ả Rập.\n"
    "   - Cấm viết lai tạp nửa số nửa chữ (cấm 100 vạn, 3 ngày, 50 lượng...). Quy đổi chính xác bậc số lượng tiếng Trung (vạn là mười nghìn, ức là một trăm triệu).\n"
    "6. TIÊU CHUẨN ĐỊNH DẠNG VÀ CHÍNH TẢ AUDIOBOOK (TTS):\n"
    "   - CẤM FORMAT MARKDOWN: Tuyệt đối cấm dùng dấu in đậm hoặc in nghiêng. Toàn bộ là chữ thường tự nhiên.\n"
    "   - CẤM DẤU NGOẶC KÉP CHO THOẠI: Lời thoại dùng gạch đầu dòng -- hoặc diễn đạt tự nhiên, cấm bọc ngoặc kép quanh thoại hay suy nghĩ.\n"
    "   - CẤM DÒNG TRỐNG THỪA VÀ NGẮT DÒNG VỤN VẶT: Mỗi đoạn văn chỉ xuống dòng 1 lần khi hết đoạn, cấm chèn dòng trống thừa giữa các câu làm gián đoạn nhịp đọc TTS.\n"
    "   - Chuẩn chính tả, viết hoa và dấu câu tiếng Việt: Mỗi từ cách đúng một dấu cách, dấu câu đặt sát từ trước, viết hoa đúng tên riêng và đầu câu.\n"
    "7. LOẠI BỎ LỜI TÁC GIẢ Ở CUỐI CHƯƠNG (ĐỐI CHIẾU DỊCH HÁN FINDER):\n"
    "   - Tự động bỏ qua các câu nhắn phụ cuối chương của tác giả như xin phiếu, cảm ơn đại lão, donate, P.S...\n"
    "   - Khi có danh sách 'DANH SÁCH LỜI TÁC GIẢ Ở CUỐI CHƯƠNG ĐÃ ĐƯỢC NHẬN DIỆN TRƯỚC' do bước Dịch Hán quét tìm được đi kèm, bắt buộc đối chiếu và LOẠI BỎ 100% các câu đó khỏi bản dịch tiếng Việt.\n"
    "   - MỆNH LỆNH BẢO TOÀN NỘI DUNG: Chỉ xóa đúng các câu nhắn ngoài lề tác giả, TUYỆT ĐỐI CẤM xóa nhầm bất kỳ lời thoại, suy nghĩ hay diễn biến truyện nào!"
)

# =====================================================================
# BẢNG TẬP HỢP TẤT CẢ CONTEXT PROFILES
# =====================================================================
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

    if any(k in pk for k in [
        "linh dị", "linh di", "vớt xác", "vot xac", "trộm mộ", "trom mo",
        "đạo mộ", "dao mo", "phong thủy", "phong thuy", "urban_supernatural",
        "bắt ma", "bat ma", "cương thi", "cuong thi", "supernatural", "dị năng", "di nang",
        "灵异", "悬疑", "盗墓", "风水", "捉鬼", "僵尸"
    ]):
        return "urban_supernatural"

    if any(k in pk for k in [
        "system_reincarnation", "system", "hệ thống", "he thong", "trọng sinh", "trong sinh",
        "xuyên không", "xuyen khong", "khoái xuyên", "khoai xuyen", "vô địch", "vo dich",
        "dị giới", "di gioi", "ngón tay vàng", "bàn tay vàng",
        "系统", "重生", "穿越", "快穿", "无敌"
    ]):
        return "system_reincarnation"

    if any(k in pk for k in [
        "sci_fi_apocalypse", "sci-fi", "scifi", "khoa huyễn", "khoa huyen",
        "mạt thế", "mat the", "tận thế", "tan the", "zombie", "tang thi",
        "tinh tế", "tinh te", "cơ giáp", "co giap", "viễn tưởng", "vien tuong",
        "科幻", "末世", "机甲", "星际", "丧尸"
    ]):
        return "sci_fi_apocalypse"

    if any(k in pk for k in [
        "romance", "ngôn tình", "ngon tinh", "cung đấu", "cung dau", "trạch đấu", "trach dau",
        "điền văn", "dien van", "nữ cường", "nu cuong", "hậu cung", "hau cung", "gia đấu", "gia dau",
        "言情", "宫斗", "宅斗", "种田", "女强"
    ]):
        return "romance"

    if any(k in pk for k in [
        "wuxia", "võ hiệp", "vo hiep", "kiếm hiệp", "kiem hiep", "giang hồ", "giang ho",
        "lục lâm", "luc lam", "hảo hán", "hao han", "thủy hử", "thuy hu", "dã sử", "da su", "sa trường",
        "武侠", "江湖", "水浒", "传统武侠"
    ]):
        return "wuxia"

    if any(k in pk for k in [
        "urban", "modern_urban", "đô thị", "do thi", "hiện đại", "hien dai",
        "học đường", "hoc duong", "thương trường", "thuong truong", "thương chiến",
        "giới giải trí", "gioi giai tri", "vườn trường", "vuon truong",
        "都市", "现言", "现代", "商战", "娱乐"
    ]):
        return "urban"

    return "xianxia"


def get_profile_by_genre(genre_name: Optional[str]) -> dict:
    """Lấy profile theo thể loại truyện."""
    key = normalize_profile_key(genre_name or "xianxia")
    return CONTEXT_PROFILES.get(key, XIANXIA_PROFILE)


def build_standard_system_prompt(genre: Optional[str] = None, author_notes_block: str = "") -> str:
    """
    Tạo System Prompt CHUẨN DUY NHẤT cho toàn bộ hệ thống dịch.
    """
    prof = get_profile_by_genre(genre)
    genre_rules = prof.get("description", "")
    author_section = f"\n\n{author_notes_block.strip()}" if author_notes_block and author_notes_block.strip() else ""

    return (
        f"Bạn là DỊCH GIẢ VĂN HỌC & TIỂU THUYẾT CAO CẤP TRUNG - VIỆT.\n"
        f"Nhiệm vụ của bạn là chuyển ngữ văn bản tiếng Trung sang tiếng Việt mượt mà, thuần Việt, giàu cảm xúc, đúng văn phong thể loại và đạt chuẩn ngữ điệu Audiobook (TTS).\n\n"
        f"=== QUY TẮC CỐT LÕI TOÀN DỰ ÁN ===\n"
        f"{COMMON_RULES}"
        f"{author_section}\n\n"
        f"=== QUY CHUẨN THỂ LOẠI ===\n"
        f"{genre_rules}"
    )


def build_user_translation_prompt(
    raw_text: str,
    entity_table_text: str,
    genre: Optional[str] = None,
    author_notes_block: str = ""
) -> str:
    """
    Tạo User Prompt CHUẨN DUY NHẤT cho LLM Translator.
    Thứ tự sắp xếp Recency Attention tối ưu:
    1. VĂN BẢN GỐC RAW
    2. BẢNG THỰC THỂ KHÓA TÊN RIÊNG
    3. YÊU CẦU CHUNG
    4. YÊU CẦU THỂ LOẠI (BẢN SẮC & QUY CHUẨN XƯNG HÔ - ĐẶT Ở CUỐI CÙNG)
    """
    prof = get_profile_by_genre(genre)
    genre_rules = prof.get("description", "")
    author_section = f"\n\n{author_notes_block.strip()}" if author_notes_block and author_notes_block.strip() else ""

    return f"""{raw_text.strip()}

{entity_table_text.strip()}

=== YÊU CẦU DỊCH THUẬT VÀ TIÊU CHUẨN AUDIOBOOK ===
{COMMON_RULES}{author_section}

=== YÊU CẦU THỂ LOẠI (BẢN SẮC & QUY CHUẨN XƯNG HÔ) ===
{genre_rules}

BẮT ĐẦU DỊCH NGAY BÂY GIỜ. Hãy dịch toàn bộ các chương trong văn bản gốc ở trên sang tiếng Việt hoàn chỉnh, chuẩn xác 100% theo các quy chuẩn đã nêu."""


def get_profile_description(genre: Optional[str] = None) -> str:
    """Lấy nội dung mô tả quy chuẩn thể loại."""
    return get_profile_by_genre(genre).get("description", "")


def get_common_rules() -> str:
    """Lấy quy tắc chung."""
    return COMMON_RULES


def get_supreme_command() -> str:
    """Mệnh lệnh tối cao chống sót Hán."""
    return (
        "MỆNH LỆNH BẢO VỆ ĐỘ TOÀN VẸN: Dịch sạch 100% sang tiếng Việt, tuyệt đối không để sót chữ Hán hay Pinyin nào trong bản dịch."
    )


def get_xml_structure_instruction(chap_count: int = 1, chap_list_str: str = "") -> str:
    """Quy chuẩn cấu trúc thẻ XML phân chia chương."""
    chap_info = f" ({chap_count} chương: {chap_list_str})" if chap_list_str else ""
    return (
        f"BẢO LƯU TOÀN BỘ CẤU TRÚC THẺ XML{chap_info}:\n"
        "- Giữ nguyên chính xác các thẻ phân tách chương: <chapter_N>...<chapter_N> tương ứng với từng chương trong văn bản gốc."
    )


def get_context_profile_prompt(genre: Optional[str] = None) -> str:
    """Hàm tương thích ngược."""
    return get_profile_description(genre)

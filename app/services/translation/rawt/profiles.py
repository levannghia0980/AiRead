# -*- coding: utf-8 -*-
"""
app/services/translation/rawt/profiles.py
=========================================
BỘ PROFILE VĂN PHONG VÀ BẢN SẮC THỂ LOẠI CHO TRANSLATOR RAWT

CẤU TRÚC CHUẨN MỰC (v3):
1. YÊU CẦU BẢN SẮC & LỜI DẪN TRUYỆN (Ngôi thứ 3 - CẤM TUYỆT ĐỐI DÙNG 'Y').
2. DANH SÁCH CẤM TUYỆT ĐỐI TOÀN BỘ XƯNG HÔ HIỆN ĐẠI (Không phân loại để tránh AI hiểu nhầm chỉ cấm trong nhà).
3. NGUYÊN TẮC THAY THẾ CHỐNG Ô NHIỄM (Bề trên/người già khó chọn từ thì bắt buộc dùng "Ta").
4. BẢNG XƯNG HÔ CỔ ĐẠI NÊN DÙNG / BẮT BUỘC DÙNG (Kèm ví dụ đối chiếu trực quan).
5. THUẬT NGỮ BẢN SẮC THỂ LOẠI & QUY CHUẨN ĐỊA DANH.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# =====================================================================
# KHỐI QUY TẮC XƯNG HÔ CỔ PHONG DÙNG CHUNG
# =====================================================================

def _co_phong_addressing_block(vi_du_dac_thu: str, bang_xung_ho_dac_thu: str) -> str:
    """Khung xưng hô cổ phong chuẩn mực kết hợp danh sách cấm tuyệt đối và ví dụ đối chiếu."""
    return f"""3. QUY CHUẨN XƯNG HÔ CỔ PHONG (YÊU CẦU - DANH SÁCH CẤM - VÍ DỤ ĐỐI CHIẾU - DANH XƯNG NÊN DÙNG):

   a. YÊU CẦU BẢN SẮC CỔ TRANG & LỜI DẪN TRUYỆN:
      - Bối cảnh cổ phong/tu chân/kiếm hiệp. Toàn bộ lời dẫn truyện, suy nghĩ nội tâm và đối thoại nhân vật BẮT BUỘC mang đậm phong vị cổ đại, chuẩn mực tôn ti trật tự.
      - LỜI DẪN TRUYỆN (NGÔI THỨ 3): Dùng hắn, gã, nàng, thị, đối phương, người nọ, thiếu niên, lão giả, tiểu tử, tráng hán. TUYỆT ĐỐI CẤM DÙNG "Y" TRONG LỜI DẪN TRUYỆN.

   b. DANH SÁCH CÁC XƯNG HÔ HIỆN ĐẠI CẤM TUYỆT ĐỐI TRONG TOÀN BỘ VĂN BẢN (KHÔNG CÓ NGOẠI LỆ):
      - CẤM TOÀN BỘ các từ ngữ, đại từ xưng hô hiện đại sau đây trong mọi hoàn cảnh (kể cả nói chuyện gia đình, giang hồ, thường dân hay độc thoại):
        * CẤM: tôi, bạn, cậu, tớ, mình, chúng mình, bọn em, tụi em, tụi mình, các bạn, tụi mày, chú mày, anh ấy, chị ấy, cô ấy, cậu ấy, chú ấy.
        * CẤM: anh - em kiểu hiện đại (trừ ca ca - muội muội/đệ đệ cổ phong), anh trai, em gái, em trai, con trai, con gái, cháu trai, cháu gái.
        * CẤM TUYỆT ĐỐI "CHÚ - CHÁU", "BÁC - CHÁU", "ÔNG - CHÁU": Dù là người già, lái đò, phu thuyền, thường dân hay bề trên, CẤM TUYỆT ĐỐI tự xưng "chú/bác/ông" kiểu hiện đại; cấm gọi người trẻ là "cháu"; cấm người trẻ xưng "cháu" với bất kỳ ai (ông già, tiền bối, sư phụ).
        * CẤM: bố, ba, má, thím, mợ, dượng, dì nhỏ (BẮT BUỘC CHỈ DÙNG "Tiểu di").
        * CẤM: thầy (gọi sư phụ), cấm xưng em với sư phụ, sư huynh, sư tỷ.
        * CẤM: ông lão, cụ già, bác ơi, chú ơi, anh trai này, cậu em này, cô em, cháu ơi.

   c. NGUYÊN TẮC THAY THẾ CHỐNG Ô NHIỄM XƯNG HÔ KHI GẶP TỪ GỐC HIỆN ĐẠI:
      - Khi nhân vật là bề trên, người lớn tuổi, phu thuyền, lão bản, thôn dân mà từ gốc tiếng Trung có đại từ chung/hiện đại hoặc không rõ danh xưng: BẮT BUỘC dùng các từ cổ phong tương ứng để thay thế (như: Ta, Lão phu, Lão hán, Tiểu lão nhi...).
      - NẾU PHÂN VÂN HOẶC KHÔNG NGHĨ ĐƯỢC TỪ CỤ THỂ, BẮT BUỘC DÙNG NGAY TỪ 'TA' để chống ô nhiễm xưng hô.

   d. VÍ DỤ ĐỐI CHIẾU SAI/ĐÚNG:
      SAI (hiện đại): "Không phải chú không giúp hậu sinh ngươi, chỉ là chuyện này khó nói."
      ĐÚNG (cổ phong): "Không phải ta không giúp hậu sinh ngươi, chỉ là chuyện này khó nói."

      SAI (hiện đại): "Chú ơi, cháu muốn hỏi đường tới trấn trên."
      ĐÚNG (cổ phong): "Lão trượng, vãn bối muốn hỏi đường tới trấn trên."

      SAI (hiện đại): "Cậu là ai? Sao cậu lại biết chuyện này?"
      ĐÚNG (cổ phong): "Ngươi là ai? Sao ngươi lại biết chuyện này?"
{vi_du_dac_thu}
   e. CÁC XƯNG HÔ CỔ ĐẠI BẮT BUỘC DÙNG / NÊN DÙNG (HOẶC DÙNG TỪ TƯƠNG TỰ PHÙ HỢP THỂ LOẠI):
{bang_xung_ho_dac_thu}"""


# =====================================================================
# 1. TIÊN HIỆP, TU CHÂN, HUYỀN HUYỄN
# =====================================================================
XIANXIA_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI TIÊN HIỆP, TU CHÂN, HUYỀN HUYỄN
1. THUẬT NGỮ BẢN SẮC TU TIÊN & CHỨC DANH NGHỀ NGHIỆP:
   - Cảnh giới & thứ bậc tu vi: Luyện Khí, Trúc Cơ, Kim Đan, Nguyên Anh, Hóa Thần, Luyện Hư, Hợp Thể, Đại Thừa, Độ Kiếp (kèm sơ/trung/hậu kỳ, đỉnh phong, viên mãn, đại viên mãn, bán bộ). Nút thắt gọi là bình cảnh; đột phá hoặc đốn ngộ.
   - Tu luyện & tài nguyên: bế quan, độ kiếp, thiên kiếp, lôi kiếp, tâm ma, tẩu hỏa nhập ma, đoạt xá, vẫn lạc, đan điền, thức hải, thần thức, linh khí, linh căn, cực phẩm linh căn, chân nguyên, pháp lực, đạo tâm, linh thạch, đan dược, linh thảo, phù lục, pháp bảo, linh bảo.
   - Môn phái & chức danh: Tông môn, thánh địa, động phủ, Linh Cung, đệ tử (ngoại môn/nội môn/chân truyền), chấp sự, trưởng lão, phong chủ, tông chủ, chưởng môn, lão tổ, Tàng Kinh Các, thể tu, kiếm tu, đan tu, phù tu, trận tu, ma tu, yêu tu, quỷ tu, đạo lữ.
2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):
   - Chỉ đảo trật tự cho hướng địa lý / ngõ ngách đời thường (phía bắc U Châu, ngoại ô Đan Dương Thành, ngõ Thanh Vân, ngõ Liễu Điều).
   - Núi non, sông biển, thành trì, bí cảnh, môn phái BẮT BUỘC GIỮ NGUYÊN trật tự Hán-Việt cổ phong (Thái Hòa Sơn, Tử Cấm Thành, Trường An Thành, Thiếu Lâm Tự).
"""
        + _co_phong_addressing_block(
            vi_du_dac_thu=(
                "      SAI (hiện đại): \"Đồ đệ, con đã luyện xong công pháp chưa?\"\n"
                "      ĐÚNG (tu tiên): \"Đồ nhi, ngươi đã luyện xong công pháp chưa?\"\n"
            ),
            bang_xung_ho_dac_thu=(
                "      - Đối thoại thông thường, tranh luận, đối đầu: Ta - Ngươi.\n"
                "      - Kẻ mạnh, thị uy: Tự xưng Lão tử (Ông đây), Bổn tọa, Bổn tôn, Ta đây, Lão phu.\n"
                "      - Khách khí, khiêm nhường, ngang hàng: Tự xưng Tại hạ / Bần đạo / Vãn bối / Kẻ hèn này / Tiểu nhân ↔ Gọi đối phương Đạo hữu / Chư vị đạo hữu / Các hạ / Huynh đài / Hiền huynh / Hiền đệ / Công tử / Cô nương / Tráng sĩ.\n"
                "      - Bề trên nói với người trẻ: Tự xưng Ta / Lão phu / Lão hán / Tiểu lão nhi ↔ Gọi Tiểu hữu / Hậu sinh / Công tử / Cô nương / Thiếu hiệp.\n"
                "      - Thưa người lớn tuổi: Lão trượng, Lão tiên sinh, Tiền bối, Lão nhân gia, Tiên trưởng, Đạo trưởng, Cao nhân, Đại lão.\n"
                "      - Thường dân, phu thuyền, tiểu nhị: Tự xưng Ta / Tiểu nhân / Tiểu lão nhi / Lão hán / Thảo dân ↔ Gọi khách Công tử / Cô nương / Khách quan / Thiếu hiệp / Đại gia.\n"
                "      - Sư môn & Tu chân: Sư phụ tự xưng Vi sư / Ta ↔ gọi đồ đệ Đồ nhi / Ngươi; Đồ đệ tự xưng Đồ nhi / Đệ tử ↔ thưa Sư phụ / Sư tôn. Đồng môn dùng: Sư huynh, Sư đệ, Sư tỷ, Sư muội, Sư thúc, Sư bá, Sư tổ.\n"
                "      - Tôn xưng chức vị: Tông chủ, Trưởng lão, Phong chủ, Chưởng môn, Tiên tôn, Chân quân.\n"
                "      - Tán tu, Dã tu (tu sĩ tự do): Khiêm xưng Nhất giới tán tu / Sơn dã tán tu / Dã tu / Tán nhân / Tại hạ. Gọi tôn trọng Tán tu đạo hữu / Đạo hữu. CẤM dịch [散装道友 / 散修] thành 'đạo hữu bán lẻ'.\n"
                "      - Thân tộc cổ phong: Phụ thân, mẫu thân, cha, mẹ, nương, ca ca, đại ca, tỷ tỷ, đệ đệ, muội muội, phu quân, tướng công, thê tử, nương tử, phu nhân, nhi tử, nữ nhi. BẮT BUỘC dịch 小姨 thành 'Tiểu di'.\n"
                "      - Đại từ số nhiều: Phe mình = Chúng ta / Huynh đệ chúng ta / Chúng đệ tử / Bổn tông; Phe đối diện = Các ngươi / Chư vị / Các vị đạo hữu.\n"
                "      - Tên + chức vụ giữ Hán-Việt: Tạ Trưởng lão, Lâm Tông chủ, Vương Chưởng môn, Tiêu Phong chủ, Nam Cung Tiên tử, Tạ ca ca, Lâm tỷ tỷ, Dương sư huynh, Mặc sư đệ."
            ),
        )
    )
}


# =====================================================================
# 2. VÕ HIỆP, KIẾM HIỆP, GIANG HỒ, LỤC LÂM, THỦY HỬ, DÃ SỬ
# =====================================================================
WUXIA_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI KIẾM HIỆP, VÕ LÂM, GIANG HỒ TRUYỀN THỐNG, LỤC LÂM HẢO HÁN, THỦY HỬ, DÃ SỬ SA TRƯỜNG
1. THUẬT NGỮ BẢN SẮC VÕ HIỆP GIANG HỒ & CHỨC DANH SA TRƯỜNG:
   - Chiêu thức & nội lực: đan điền, huyệt đạo, kinh mạch (nhâm đốc nhị mạch), nội lực, chân khí, kình lực, ám kình, hóa kình, kiếm khí, đao phong, chưởng lực, thân pháp, bộ pháp, khẩu quyết, tâm pháp, bí kíp võ công, tuyệt học trấn phái.
   - Bối cảnh Giang hồ Lục lâm & Sơn trại: Hắc đạo, Bạch đạo, Lục lâm, Thảo mãng, Sơn trại, Thủy trại, Tiêu cục, Phân đà, Tổng đàn, Võ lâm minh chủ, Đại hội võ lâm, Tỷ võ chiêu thân, luận kiếm, hiệp khách, lãng khách, du hiệp, khoái đao, kiếm khách.
   - Bối cảnh Sa trường & Quân đội Cổ đại: Soái kỳ, trung quân, tiền phong, kỵ binh, thiết kỵ, bộ binh, cung tiễn thủ, trảm mã đao, giáo thương, giáp trụ, chiến mã, lương thảo, binh phù, hổ phù, cấm quân, tuần bộ, bộ khoái, nha môn.
2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):
   - Chỉ đảo trật tự cho hướng địa lý / ngõ ngách đời thường (phía bắc U Châu, ngoại ô Đan Dương Thành, ngõ Thanh Vân).
   - Núi non, sông biển, thành trì, bí cảnh, môn phái BẮT BUỘC GIỮ NGUYÊN trật tự Hán-Việt cổ phong (Thái Hòa Sơn, Tử Cấm Thành, Trường An Thành, Thiếu Lâm Tự).
"""
        + _co_phong_addressing_block(
            vi_du_dac_thu=(
                "      SAI (hiện đại): \"Đại ca, tụi mình đi cứu huynh đệ thôi!\"\n"
                "      ĐÚNG (giang hồ): \"Đại ca, chúng ta đi cứu huynh đệ thôi!\"\n"
            ),
            bang_xung_ho_dac_thu=(
                "      - Đối thoại thông thường, tranh luận, đối đầu: Ta - Ngươi.\n"
                "      - Kẻ mạnh, thị uy: Tự xưng Lão tử (Ông đây), Bản trại chủ, Bản tọa, Ta đây.\n"
                "      - Khách khí, ngang hàng: Tự xưng Tại hạ / Vãn bối / Kẻ hèn này / Tiểu nhân ↔ Gọi đối phương Huynh đài / Các hạ / Hảo hán / Chư vị / Bằng hữu / Du hiệp / Hiền huynh / Hiền đệ.\n"
                "      - Bề trên nói với người trẻ: Tự xưng Ta / Lão phu / Lão hán / Tiểu lão nhi ↔ Gọi Tiểu hữu / Hậu sinh / Công tử / Cô nương / Thiếu hiệp.\n"
                "      - Thưa người lớn tuổi: Lão trượng, Lão tiên sinh, Tiền bối, Lão gia, Trại chủ, Tiêu đầu.\n"
                "      - Thường dân, phu thuyền, tiểu nhị: Tự xưng Ta / Tiểu nhân / Tiểu lão nhi / Lão hán / Thảo dân ↔ Gọi khách Công tử / Cô nương / Khách quan / Đại gia / Thiếu hiệp.\n"
                "      - Huynh đệ Lục lâm, Sơn trại: Ca ca, Hiền đệ, Tiểu đệ, Đại ca, Nhị ca, Huynh đệ, Chúng huynh đệ, Lão đệ; ngang hàng dùng Huynh - Đệ hoặc Ta - Ngươi.\n"
                "      - Sa trường & Quan trường: Tướng quân, Mạt tướng, Ty chức, Thuộc hạ ('Mạt tướng bái kiến Tướng quân; Thuộc hạ tuân lệnh; Ty chức hiểu rõ; Khởi bẩm Đại nhân'). Khiêm xưng bề dưới: Tiểu nhân, Thảo dân, Mạt tướng, Ty chức, Tại hạ, Vãn bối.\n"
                "      - Du hiệp, Lãng khách: Tự xưng Nhất giới du hiệp / Giang hồ lãng tử / Kẻ phiêu bạt này / Tại hạ. Gọi tôn trọng Du hiệp / Huynh đài / Giang hồ bằng hữu.\n"
                "      - Chức danh Giang hồ: Trại chủ, Đại đương gia, Nhị đương gia, Đầu lĩnh, Tiên phong, Giáo đầu, Bang chủ, Đà chủ, Đường chủ, Hộ pháp, Tiêu cục, Tiêu đầu, Tổng tiêu đầu, Hảo hán, Lão anh ca, Tráng sĩ, Đại hiệp, Thiếu hiệp, Nữ hiệp, Anh hùng, Lão trượng, Cô nương.\n"
                "      - Thân tộc cổ phong: Phụ thân, mẫu thân, cha, mẹ, nương, ca ca, tỷ tỷ, đệ đệ, muội muội, nhi tử, nữ nhi. BẮT BUỘC dịch 小姨 thành 'Tiểu di'.\n"
                "      - Đại từ số nhiều: Phe mình = Chúng ta / Huynh đệ chúng ta / Sơn trại chúng ta / Chúng thuộc hạ; Phe đối diện = Các ngươi / Chư vị huynh đệ / Chư vị hảo hán.\n"
                "      - Tên + chức vụ giữ Hán-Việt: Lâm Trại chủ, Vương Bang chủ, Dương Tiêu đầu, Lý Tướng quân, Kiều Trưởng lão, Lâm Đại đương gia, Tiêu Giáo đầu, Tạ ca ca, Lâm tỷ tỷ."
            ),
        )
    )
}


# =====================================================================
# 3. ĐÔ THỊ HIỆN ĐẠI, THƯƠNG TRƯỜNG, HỌC ĐƯỜNG, GIỚI GIẢI TRÍ
# =====================================================================
URBAN_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI ĐÔ THỊ HIỆN ĐẠI, THƯƠNG TRƯỜNG, HỌC ĐƯỜNG, GIỚI GIẢI TRÍ
1. THUẬT NGỮ BẢN SẮC & CHỨC DANH NGHỀ NGHIỆP:
   - Thương trường & công sở: Tập đoàn, Chủ tịch HĐQT, Tổng Giám đốc (Tổng tài / CEO), Giám đốc điều hành, Trợ lý, Thư ký, Hợp đồng, Đấu thầu, Rót vốn, Cổ phần, Thâu tóm, Phá sản.
   - Học đường: Bạn học, Lớp trưởng, Giáo viên chủ nhiệm, Hiệu trưởng, Căn tin, Ký túc xá, Học bá, Học tra, Hoa khôi trường, Thi đại học, Điểm chuẩn.
   - Giới giải trí & MXH: Showbiz, Minh tinh, Đỉnh lưu, Ảnh đế, Ảnh hậu, Đạo diễn, Biên kịch, Người đại diện, Hot search, Fan, Thủy quân, Scandal, Tẩy trắng.
2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):
   - Đảo trật tự cho hướng địa lý/ngõ ngách đời thường (phía đông thành, ngõ Liễu Điều...).
3. QUY CHUẨN XƯNG HÔ HIỆN ĐẠI:
   - YÊU CẦU: Bối cảnh là đời sống hiện đại nên BẮT BUỘC dùng đại từ đời thường, TUYỆT ĐỐI CẤM dùng xưng hô cổ trang (huynh đài, tại hạ, bản tọa, tiểu nữ...).
   - VÍ DỤ ĐỐI CHIẾU:
     SAI (cổ trang): "Tại hạ không ngờ các hạ lại là Tổng Giám đốc."
     ĐÚNG (hiện đại): "Tôi không ngờ anh lại là Tổng Giám đốc."
   - BẢNG XƯNG HÔ NÊN DÙNG:
     * Bạn bè, đời thường: Tôi - Bạn, Cậu - Tớ, Mình - Cậu; Anh - Em, Chị - Em; Mày - Tao (thân mật hoặc cãi vã).
     * Công sở, đối tác: Chủ tịch, Tổng Giám đốc, Giám đốc Lý, Thư ký Vương, Trợ lý Trương; Tôi - Anh/Chị, Tôi - Ngài.
     * Gia đình: Bố, Ba, Mẹ, Má, Bác, Chú, Cô, Dì, Cậu, Thím, Anh trai, Chị gái, Em trai, Em gái, Con trai, Con gái, Cháu.
     * Tên + chức vụ/nghề nghiệp: Giám đốc Lý, Thư ký Vương, Trợ lý Trương, Thầy Trần, Cô Lâm, Bác sĩ Vương, Luật sư Trương."""
    )
}


# =====================================================================
# 4. ĐÔ THỊ LINH DỊ, PHONG THỦY, VỚT XÁC, BẮT MA, ĐẠO MỘ
# =====================================================================
URBAN_SUPERNATURAL_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI ĐÔ THỊ LINH DỊ, PHONG THỦY, VỚT XÁC, BẮT MA, ĐẠO MỘ
1. THUẬT NGỮ BẢN SẮC:
   - Bắt ma & phong thủy: Mao Sơn, Đạo sĩ, Thiên sư, Phong thủy sư, Âm dương tiên sinh, La bàn, Chu sa, Bùa đào mộc kiếm, Bát quái kính; Âm khí, Dương khí, Sát khí, Tà khí, Oán khí, Cương thi, Lệ quỷ, Ma đói; Vớt xác, Trùng tang, Siêu độ.
   - Trộm mộ: Đạo mộ, Mô kim hiệu úy, Phát khâu trung lang tướng, Đấu lớn/nhỏ, Minh khí, Bật nắp quan tài, Cơ quan, Cạm bẫy.
2. QUY CHUẨN XƯNG HÔ DÂN GIAN & LINH DỊ:
   - Đời thường dân gian: Dùng xưng hô thân thuộc (Tôi - Bác, Cháu - Chú, Tôi - Cậu, Chú Ba, Anh Hai, Cửu thúc, Nhị gia, Lâm Đạo trưởng, Vương Thiên sư, Thần y Tạ).
   - Khi trừ tà, giao chiến quỷ ma: Chuyển sang giọng điệu cổ phong đanh thép: "Ta - Ngươi", "Nghiệt súc", "Yêu nghiệt"."""
    )
}


# =====================================================================
# 5. NGÔN TÌNH, CỔ ĐẠI, ĐIỀN VĂN, CUNG ĐẤU, TRẠCH ĐẤU
# =====================================================================
ROMANCE_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI NGÔN TÌNH, CỔ ĐẠI, ĐIỀN VĂN, CUNG ĐẤU, TRẠCH ĐẤU
1. THUẬT NGỮ BẢN SẮC & CHỨC DANH NGHỀ NGHIỆP:
   - Hậu cung & triều đình: Hoàng thượng (Bệ hạ / Thánh thượng), Hoàng hậu (Nương nương), Hoàng thái hậu, Quý phi, Phi tần, Trắc phi, Thứ phi, Chiêu nghi, Tiệp dư, Mỹ nhân, Tài nhân; Thái tử, Hoàng tử, Công chúa, Quận chúa, Thân vương, Phò mã; Thái giám (Công công), Thượng cung, Cung nữ.
   - Phủ đệ & trạch đấu: Hầu phủ, Quốc công phủ, Tướng phủ, Lão phu nhân, Thái phu nhân, Đại lão gia, Nhị gia, Tam gia, Đại phu nhân, Nhị phu nhân, Di nương (vợ lẽ/thiếp — BẮT BUỘC dùng Di nương, cấm dịch thành dì), Đích nữ, Thứ nữ, Đích tử, Thứ tử, Thông phòng, Đại nha hoàn, Nha hoàn chải đầu, Nha đầu.
   - Sắc thái tình cảm: Thanh mai trúc mã, tương tư, vấn vương, động lòng, rung động, cưng chiều, sủng ái, ngọt ngào, hờn dỗi, nũng nịu, ăn giấm, ghen tuông.
2. QUY CHUẨN TRẬT TỰ ĐỊA DANH (PLACE):
   - Đảo trật tự cho hướng địa lý / ngõ ngách đời thường; giữ nguyên Hán-Việt cho thành trì, cung điện, phủ đệ (Tử Cấm Thành, Khôn Ninh Cung, Dưỡng Tâm Điện...).
"""
        + _co_phong_addressing_block(
            vi_du_dac_thu=(
                "      SAI (hiện đại): \"Cháu là con của phu nhân sao?\"\n"
                "      ĐÚNG (trạch đấu): \"Ngươi/Con là con của phu nhân sao?\" (chỉ con ruột với cha mẹ ruột mới xưng \"con\"; nha hoàn/thái giám/bề dưới KHÔNG BAO GIỜ được xưng \"con\" hay \"cháu\" với chủ tử — phải xưng \"nô tỳ\"/\"nô tài\"/\"thần thiếp\".)\n"
            ),
            bang_xung_ho_dac_thu=(
                "      - Phu thê & Tình nhân: Phu quân - Thê tử / Nương tử, Tướng công - Nương tử; Chàng - Thiếp; Ta - Nàng.\n"
                "      - Hoàng gia & Chủ tớ: Bệ hạ - Thần thiếp, Trẫm - Ái phi; Nô tỳ / Nô tài - Chủ tử / Nương nương / Gia.\n"
                "      - Hoàng thất: Thái hậu, Hoàng hậu, Quý phi, Tần, Thân vương, Thế tử, Cách cách, Nương nương, Ma ma (nhũ mẫu/cung nữ lớn tuổi), Cô cô (nữ quan), Thái giám, Công công.\n"
                "      - Phủ đệ & Thân tộc: Phụ thân, Mẫu thân, Lão thái quân, Tổ mẫu, Huynh trưởng, Đại ca, Tỷ tỷ, Đệ đệ, Muội muội, Tiểu di.\n"
                "      - Tên + bối phận/chức vị giữ Hán-Việt: Lâm Lão phu nhân, Nam Cung Quận chúa, Lâm di nương, Tạ ca ca, Lâm tỷ tỷ, Tô nương tử."
            ),
        )
    )
}


# =====================================================================
# 6. HỆ THỐNG, TRỌNG SINH, XUYÊN KHÔNG, KHOÁI XUYÊN, VÔ ĐỊCH LƯU
# =====================================================================
SYSTEM_REINCARNATION_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI HỆ THỐNG, TRỌNG SINH, XUYÊN KHÔNG, KHOÁI XUYÊN, VÔ ĐỊCH LƯU
1. THUẬT NGỮ BẢN SẮC:
   - Hệ thống: Hệ thống - Ký chủ / Túc chủ; 'Đinh!' / 'Nhắc nhở:...' / 'Thông báo:...'; phát hành / hoàn thành / thất bại nhiệm vụ; điểm tích lũy, điểm danh vọng; thăng cấp, cộng điểm thuộc tính; bảng thuộc tính; thương thành hệ thống, rút thưởng mười lần liên tiếp.
   - Trọng sinh & xuyên không: trọng sinh, xuyên không, khoái xuyên, hệ thống vô địch, ngón tay vàng (kim thủ chỉ), nhân vật phản diện, bia đỡ đạn.
2. QUY CHUẨN XƯNG HÔ THEO THẾ GIỚI XUYÊN VÀO:
   - Nếu xuyên vào CỔ ĐẠI / TU CHÂN: 100% tuân thủ xưng hô Cổ phong (Ta - Ngươi, Lão phu, Tại hạ...), LỜI DẪN TRUYỆN CẤM DÙNG 'Y'; CẤM TOÀN BỘ xưng hô hiện đại (tôi - bạn, cậu - tớ, anh - em, chú - cháu).
   - Nếu xuyên vào HIỆN ĐẠI: Dùng đại từ hiện đại (Tôi - Cậu, Tôi - Bạn, Anh - Em).
   - Giao tiếp với Hệ thống: Hệ thống tự xưng 'Bản hệ thống' / 'Hệ thống' ↔ gọi người dùng là 'Ký chủ' / 'Túc chủ'. Ký chủ gọi lại là 'Ngươi' (bực tức thì 'mày')."""
    )
}


# =====================================================================
# 7. MẠT THẾ, TẬN THẾ ZOMBIE, KHOA HUYỄN, TINH TẾ, CƠ GIÁP
# =====================================================================
SCI_FI_APOCALYPSE_PROFILE = {
    "description": (
        """YÊU CẦU DỊCH THỂ LOẠI MẠT THẾ, TẬN THẾ ZOMBIE, KHOA HUYỄN, TINH TẾ, CƠ GIÁP
1. THUẬT NGỮ BẢN SẮC:
   - Zombie & biến dị: Tang thi / Zombie (triều tang thi, Tang thi vương), thú biến dị, tinh hạch, thuốc biến đổi gen.
   - Dị năng: Nhất giai/Nhị giai... (hoặc Cấp 1/Cấp 2...), hệ Lôi/Hỏa/Băng/Không Gian/Tinh Thần, người thức tỉnh.
   - Tinh tế & khoa huyễn: chiến hạm không gian, cơ giáp, bước nhảy không gian, quang não, khiên năng lượng, pháo ion, vũ khí plasma.
2. QUY CHUẨN XƯNG HÔ:
   - Dùng xưng hô hiện đại và tác phong quân đội/sinh tồn: Tôi, Cậu, Tớ, Anh, Em, Đồng đội; Tự xưng Tôi ↔ Báo cáo Chỉ huy/Đội trưởng (Chỉ huy Trương, Đội trưởng Lâm, Thuyền trưởng Lý). CẤM dùng xưng hô cổ trang kiếm hiệp."""
    )
}


# =====================================================================
# BỘ QUY TẮC CHUYỂN NGỮ CỐT LÕI (COMMON RULES CHO TOÀN DỰ ÁN) — RÚT GỌN
# =====================================================================
COMMON_RULES = (
    "QUY TẮC CỐT LÕI (áp dụng mọi thể loại):\n"
    "1. TÊN RIÊNG: Dùng đúng 100% bản dịch đã có trong Bảng thực thể cho tên nhân vật, địa danh, môn phái, bảo vật. Mỗi từ CHỈ MỘT bản dịch tiếng Việt duy nhất, hòa vào câu văn — CẤM ghi dạng song ngữ kiểu \"Chữ Hán (bản dịch)\", cấm sót chữ Hán/Pinyin.\n"
    "2. NGỮ NGHĨA THEO CỤM TỪ, KHÔNG DỊCH TỪNG CHỮ: Giải mã nghĩa của cả cụm từ/mệnh đề theo ngữ cảnh, không ghép nghĩa đen từng chữ Hán một cách máy móc. Giữ các thuật ngữ Hán-Việt quen thuộc với độc giả thể loại (tu vi, đan điền, tán tu...), không ép thuần Việt hóa gượng gạo. Chủ thể hành động phải đúng bản chất (không gán hành vi người cho thú nuôi, đồ vật).\n"
    "3. NGỮ PHÁP TỰ NHIÊN: Câu dịch phải đúng ngữ pháp, trật tự từ tiếng Việt tự nhiên — dịch đúng từng chữ nhưng đọc lên ngô nghê, trúc trắc là dịch hỏng.\n"
    "4. CẤM CONVERT THÔ: không phiên âm Hán-Việt cơ học kiểu Vietphrase, không dịch nguyên văn các quán ngữ convert (cánh nhiên → \"vậy mà\"; nhất đán → \"một khi\"...). Cấm tiếng Anh (but/and/so → nhưng/thế nhưng).\n"
    "5. ĐỊNH DẠNG AUDIOBOOK (TTS): số/tiền/thời gian viết bằng chữ (trừ số chương và mốc năm cụ thể giữ số Ả Rập; vạn = mười nghìn, ức = một trăm triệu). Không in đậm/nghiêng. Lời thoại dùng gạch đầu dòng, không bọc ngoặc kép. Mỗi đoạn xuống dòng một lần, không chèn dòng trống thừa.\n"
    "6. LOẠI BỎ LỜI TÁC GIẢ CUỐI CHƯƠNG: Tự động phát hiện và loại bỏ các câu xin phiếu, cảm ơn donate, thông báo ngoài lề ở đoạn kết các chương. Khâu Dịch Hán đã bóc tách sẵn các câu này trong danh sách bên dưới — hãy đối chiếu để XÓA SẠCH các câu lời nhắn đó khỏi bản dịch tiếng Việt, TUYỆT ĐỐI KHÔNG xóa nhầm bất kỳ câu thoại hay diễn biến nào của cốt truyện."
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
    """Chuẩn hóa key thể loại từ bất kỳ chuỗi đầu vào nào."""
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


def _rut_gon_nhac_xung_ho(genre_rules: str) -> str:
    """Trích câu quy tắc dương tính đầu tiên của khối xưng hô để nhắc lại ngắn gọn ở cuối prompt."""
    marker = "QUY CHUẨN XƯNG HÔ"
    idx = genre_rules.find(marker)
    if idx == -1:
        return ""
    end = genre_rules.find("\n\n", idx)
    if end == -1:
        end = len(genre_rules)
    return " ".join(genre_rules[idx:end].split())


def build_standard_system_prompt(genre: Optional[str] = None, author_notes_block: str = "") -> str:
    """Tạo System Prompt CHUẨN DUY NHẤT cho toàn bộ hệ thống dịch."""
    prof = get_profile_by_genre(genre)
    genre_rules = prof.get("description", "")
    author_section = f"\n\n{author_notes_block.strip()}" if author_notes_block and author_notes_block.strip() else ""

    return (
        f"Bạn là DỊCH GIẢ VĂN HỌC & TIỂU THUYẾT CAO CẤP TRUNG - VIỆT.\n"
        f"Nhiệm vụ: chuyển ngữ văn bản tiếng Trung sang tiếng Việt mượt mà, "
        f"thuần Việt, giàu cảm xúc, đúng văn phong thể loại và chuẩn ngữ điệu "
        f"Audiobook (TTS).\n\n"
        f"=== QUY CHUẨN THỂ LOẠI (ĐỌC TRƯỚC — QUY TẮC XƯNG HÔ Ở ĐÂY QUAN "
        f"TRỌNG NHẤT) ===\n"
        f"{genre_rules}\n\n"
        f"=== QUY TẮC CỐT LÕI TOÀN DỰ ÁN ===\n"
        f"{COMMON_RULES}"
        f"{author_section}"
    )


def build_user_translation_prompt(
    raw_text: str,
    entity_table_text: str,
    genre: Optional[str] = None,
    author_notes_block: str = ""
) -> str:
    """Tạo User Prompt CHUẨN DUY NHẤT cho LLM Translator."""
    prof = get_profile_by_genre(genre)
    genre_rules = prof.get("description", "")
    author_section = f"\n\n{author_notes_block.strip()}" if author_notes_block and author_notes_block.strip() else ""
    nhac_lai_xung_ho = _rut_gon_nhac_xung_ho(genre_rules)
    nhac_lai_block = f"\nNHẮC LẠI: {nhac_lai_xung_ho}\n" if nhac_lai_xung_ho else ""

    return f"""=== QUY CHUẨN THỂ LOẠI (BẢN SẮC & QUY TẮC XƯNG HÔ — ƯU TIÊN HÀNG ĐẦU) ===
{genre_rules}{author_section}

=== VĂN BẢN GỐC CẦN DỊCH ===
{raw_text.strip()}

=== BẢNG THỰC THỂ KHÓA TÊN RIÊNG ===
{entity_table_text.strip()}

=== QUY TẮC CHUNG TOÀN DỰ ÁN ===
{COMMON_RULES}
{nhac_lai_block}
BẮT ĐẦU DỊCH NGAY BÂY GIỜ. Dịch toàn bộ các chương trong văn bản gốc ở trên
sang tiếng Việt hoàn chỉnh, đúng quy chuẩn thể loại và xưng hô đã nêu."""


def get_profile_description(genre: Optional[str] = None) -> str:
    """Lấy nội dung mô tả quy chuẩn thể loại."""
    return get_profile_by_genre(genre).get("description", "")


def get_common_rules() -> str:
    """Lấy quy tắc chung."""
    return COMMON_RULES


def get_supreme_command() -> str:
    """Mệnh lệnh tối cao chống sót Hán."""
    return (
        "MỆNH LỆNH BẢO VỆ ĐỘ TOÀN VẸN: Dịch sạch 100% sang tiếng Việt, tuyệt "
        "đối không để sót chữ Hán hay Pinyin nào trong bản dịch."
    )


def get_xml_structure_instruction(chap_count: int = 1, chap_list_str: str = "") -> str:
    """Quy chuẩn cấu trúc thẻ XML phân chia chương."""
    chap_info = f" ({chap_count} chương: {chap_list_str})" if chap_list_str else ""
    return (
        f"BẢO LƯU TOÀN BỘ CẤU TRÚC THẺ XML{chap_info}:\n"
        "- Giữ nguyên chính xác các thẻ phân tách chương: <chapter_N>...<chapter_N> "
        "tương ứng với từng chương trong văn bản gốc."
    )


def get_context_profile_prompt(genre: Optional[str] = None) -> str:
    """Hàm tương thích ngược."""
    return get_profile_description(genre)

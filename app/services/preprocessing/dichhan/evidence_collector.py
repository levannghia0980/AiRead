import os
import json
from typing import Dict, Any, List
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, NovelEntity
from app.services.preprocessing.dichhan.entity_extractor import extract_ner_branch
from app.services.preprocessing.dichhan.entity_sanitizer import extract_gg_clean_branch
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

SYSTEM_PROMPT_INSTRUCTION = (
    "Nhiệm vụ của bạn là nhận diện và dịch âm Hán-Việt cổ phong / dịch nghĩa chuẩn xác các danh từ riêng, tên nhân vật, danh xưng xưng hô, chiêu thức, tên kiếm, bảo vật, địa danh từ văn bản tiếng Trung.\n\n"
    "CÁC QUY TẮC PHÂN LOẠI THỰC THỂ (entity_type):\n"
    "- 'NAME': Tên nhân vật, biệt danh thân mật & danh xưng xưng hô kèm chức danh/bối phận (ví dụ: 王威 -> Vương Uy, 小威 -> Tiểu Uy, 莫雅仪 -> Mạc Nhã Nghi, 乔长老 -> Kiều trưởng lão, 桑老 -> Tang lão, 源哥 -> Nguyên ca, 小王 -> Tiểu Vương, 王叔 -> Chú Vương / Vương thúc).\n"
    "- 'SKILL': Chiêu thức, tuyệt kỹ, công pháp, võ học, thân pháp, kỹ năng hệ thống/bị động (ví dụ: 一步登天 -> Nhất Bộ Đăng Thiên / Đăng Thiên Bộ (CẤM 'một bước lên trời'), 平步青云 -> Bình Bộ Thanh Vân, 缩地成寸 -> Súc Địa Thành Thốn, 凌波微步 -> Lăng Ba Vi Bộ, 踏雪无痕 -> Đạp Tuyết Vô Ngấn, 移形换位 -> Di Hình Hoán Vị, 偷天换日 -> Thâu Thiên Hoán Nhật, 雷神之息 -> Lôi Thần Chi Tức, 九天落雷 -> Cửu Thiên Lạc Lôi, 呼吸之法 -> Hô Hấp Chi Pháp, 太极拳 -> Thái Cực Quyền, 剑诀 -> Kiếm Quyết, 强壮/健壮 -> Cường Tráng / Thể Phách Cường Tráng (CẤM 'kỹ năng khỏe mạnh'), 疾风步 -> Tật Phong Bộ, 不死身 -> Bất Tử Thân, 破甲 -> Phá Giáp, 洞察 -> Động Sát). TUYỆT ĐỐI CẤM dịch nôm na theo nghĩa đen thành ngữ dân gian hoặc từ ngữ giao tiếp đời thường ngô nghê.\n"
    "- 'ITEM': Kiếm, bảo vật, pháp bảo, thần khí, trang bị, đan dược, dược liệu, thảo mộc (ví dụ: 紫光雷翼 -> Tử Quang Lôi Dực, 藏剑 -> Tàng Kiếm, 黑色轮盘 -> Hắc Sắc Luân Bàn, 赤血参 -> Xích Huyết Sâm).\n"
    "- 'PLACE': Địa danh, linh cung, thành phố, sông núi, điện thờ (ví dụ: 天桑灵宫 -> Thiên Tang Linh Cung, 望海市 -> Vọng Hải thị, 少林寺 -> Thiếu Lâm Tự, 武当山 -> Võ Đang sơn, 华山 -> Hoa Sơn, 昆仑山 -> Côn Lôn sơn, 藏经阁 -> Tàng Kinh Các, 太和殿 -> Thái Hòa Điện, 冰火岛 -> Băng Hỏa Đảo, 天牢 -> Thiên Lao).\n"
    "- 'SECT': Tông môn, ma phái, tổ chức, thế lực, bang hội. ĐÂY LÀ DANH TỪ RIÊNG, VIẾT HOA (ví dụ: 丐帮 -> Cái Bang (CẤM viết thường 'cái bang'), 明教 -> Minh Giáo, 天地会 -> Thiên Địa Hội, 日月神教 -> Nhật Nguyệt Thần Giáo, 全真教 -> Toàn Chân Giáo, 武当派 -> Võ Đang phái, 少林派 -> Thiếu Lâm phái, 峨眉派 -> Nga Mi phái, 华山派 -> Hoa Sơn phái, 逍遥派 -> Tiêu Dao phái, 青云宗 -> Thanh Vân Tông, 星辰宗 -> Tinh Thần Tông, 血魔宗 -> Huyết Ma Tông, 天刀门 -> Thiên Đao Môn, 圣奴 -> Thánh Nô, 驰越集团 -> Trì Việt Tập Đoàn).\n"
    "- 'OTHER': Các thuật ngữ chuyên biệt khác (cảnh giới: Luyện Khí, Trúc Cơ, Kim Đan...; phẩm giai: Hoàng phẩm, Huyền phẩm, Địa phẩm, Thiên phẩm...).\n\n"
    "HƯỚNG DẪN DỊCH VÀ SỬ DỤNG BẰNG CHỨNG THAM KHẢO:\n"
    "1. VAI TRÒ CỦA DỮ LIỆU GỢI Ý (BẮT BUỘC DỊCH HAY, KHÔNG CỐ DỰA VÀO VÍ DỤ BÊN CẠNH CỦA HÁN):\n"
    "   - Các trường gợi ý 'suggested_hanviet_example', 'db_example', 'gg_error' CHỈ LÀ THAM KHẢO THÔ BẬC THẤP.\n"
    "   - Bạn là chuyên gia dịch thuật đỉnh cao: BẮT BUỘC PHẢI DỊCH THẬT HAY, ĐẶT TÊN BÓNG BẨY, MỸ CẢM VÀ TỰ NHIÊN cho tên thực thể, chiêu thức võ công, kỹ năng hệ thống, bảo vật, dược liệu, quái vật.\n"
    "   - TUYỆT ĐỐI CẤM cố dựa dẫm máy móc vào các ví dụ nhỏ bên cạnh của Hán/Google dịch. Nếu ví dụ bên cạnh là dịch thô từng chữ ngô nghê (như 'Huyết Lùn Lật', 'Thịt Cây', 'Đầu Mọc Sừng Rồng Lùn'...), bạn PHẢI CHỦ ĐỘNG BỎ QUA VÍ DỤ ĐÓ và tự mình chuyển ngữ sang tên Hán-Việt bóng bẩy kiếm hiệp/tiên hiệp (như 'Huyết Nham Lật' / 'Huyết Lật') HOẶC thuần Việt giàu hình tượng, dễ hiểu ('Hạt dẻ đỏ').\n"
    "   - Với các danh từ đồ vật, khái niệm đời thường thông dụng: ƯU TIÊN DỊCH NGHĨA TIẾNG VIỆT THUẦN TÚY DỄ HIỂU thay vì gượng ép phiên âm Hán-Việt tối nghĩa.\n"
    "2. ĐỒNG BỘ VỚI TỪ ĐIỂN ĐÃ LƯU: Nếu một từ Hán gốc ĐÃ CÓ trong danh sách từ điển các chương trước ('existing_db_entities'), hãy ưu tiên giữ sự nhất quán xuyên suốt bộ truyện.\n"
    "3. PHÂN TÍCH BỐI PHẬN / VAI TRÒ VÀ GIỚI TÍNH CHÍNH XÁC: Phân tích ngữ cảnh đoạn văn để xác định đúng vai trò ('role') và giới tính ('gender': 'male', 'female', hoặc null).\n"
    "4. DỊCH CHUẨN HÁN-VIỆT CHO TỪ MỚI — ĐÚNG ÂM VÀ DẤU THANH:\n"
    "   - Với thực thể mới chưa có trong từ điển, hãy đối chiếu từng chữ Hán gốc để dịch theo âm Hán-Việt chuẩn xác.\n"
    "   - Phân biệt các chữ đồng âm/hình thái: 佐 = 'Tá' (Chu Tá), 修 = 'Tu' (Thất Tu), 事 = 'Sự' (Linh Sự Các), 浅 = 'Thiển' (Tô Thiển Thiển), 阁 = 'Các' (Linh Pháp Các), 震 = 'Chấn' (Lưu Chấn).\n"
    "   - TUYỆT ĐỐI NGHIÊM CẤM TÊN DÍNH CHỮ HÁN LAI TẠP: Cấm chép lại các tên lỗi dở dang của Google Dịch (CẤM 'Tô T浅浅', CẤM 'Linh Pháp C阁', CẤM 'L岚'). Đầu ra vietnamese_name và correct_vietnamese BẮT BUỘC là 100% tiếng Việt có dấu thanh.\n"
    "5. ⚠️ PHÂN BIỆT RÕ RÀNG TIỀN TỐ VÀ HẬU TỐ THEO TỪNG BỐI CẢNH:\n"
    "   - TIỀN TỐ (Đứng TRƯỚC tên/họ): 小威 -> 'Tiểu Uy', 小徐 -> 'Tiểu Từ', 小王 -> 'Tiểu Vương', 老王 -> 'Lão Vương', 阿亮 -> 'A Lượng'.\n"
    "   - HẬU TỐ CỔ PHONG / TU TIÊN: 文师兄 -> 'Văn sư huynh' (CẤM 'Sư huynh Văn'), 徐师兄 -> 'Từ sư huynh', 赵师妹 -> 'Triệu sư muội', 桑老 -> 'Tang lão' (CẤM 'Lão Tang'), 乔长老 -> 'Kiều trưởng lão', 萧宗主 -> 'Tiêu tông chủ', 徐兄 -> 'Từ huynh', 穆师妹 -> 'Mục sư muội'.\n"
    "   - HẬU TỐ ĐÔ THỊ / HIỆN ĐẠI: 源哥 -> 'Nguyên ca', 雅姐 -> 'Nhã tỷ', 王叔 -> 'Chú Vương' (hoặc 'Vương thúc'), 王总 -> 'Vương tổng', 李经理 -> 'Lý giám đốc'.\n\n"
    "6. ⚠️ PHÂN BIỆT DANH TỪ RIÊNG (TỔ CHỨC / ĐỊA DANH) VỚI CHỨC DANH / TỪ THÔNG THƯỜNG:\n"
    "   Đây là các trường hợp LLM HAY NHẦM NHẤT. BẮT BUỘC nhận diện ĐÚNG và trả về làm thực thể:\n"
    "   a) TÊN TỔ CHỨC (SECT) là DANH TỪ RIÊNG, VIẾT HOA:\n"
    "      丐帮 -> 'Cái Bang' (CẤM: 'cái bang'), 明教 -> 'Minh Giáo', 天地会 -> 'Thiên Địa Hội',\n"
    "      日月神教 -> 'Nhật Nguyệt Thần Giáo', 全真教 -> 'Toàn Chân Giáo',\n"
    "      武当派 -> 'Võ Đang phái', 峨眉派 -> 'Nga Mi phái', 华山派 -> 'Hoa Sơn phái',\n"
    "      逍遥派 -> 'Tiêu Dao phái', 星辰宗 -> 'Tinh Thần Tông', 血魔宗 -> 'Huyết Ma Tông'.\n"
    "   b) HẬU TỐ TỔ CHỨC cần nhận diện: 帮=Bang, 派=Phái, 教=Giáo, 宗=Tông, 门=Môn, 会=Hội, 盟=Minh, 阁=Các, 殿=Điện, 谷=Cốc, 堡=Bảo, 庄=Trang, 院=Viện, 族=Tộc.\n"
    "   c) CHỨC DANH đi kèm tổ chức (KHÔNG phải thực thể riêng): 帮主=bang chủ, 教主=giáo chủ, 宗主=tông chủ, 掌门=chưởng môn, 门主=môn chủ, 盟主=minh chủ.\n"
    "   d) CỤM KẾT HỢP [Chức danh + Tổ chức]: 丐帮帮主 -> 'bang chủ Cái Bang' (CẤM: 'Cái Bang bang chủ'), 明教教主 -> 'giáo chủ Minh Giáo', 武当掌门 -> 'chưởng môn Võ Đang'.\n\n"
    "7. ⚠️ BẮT BUỘC NHẬN DIỆN ĐẦY ĐỦ, KHÔNG BỎ SÓT:\n"
    "   - Quét TOÀN BỘ văn bản, KHÔNG bỏ sót bất kỳ tên nhân vật, tổ chức, địa danh, chiêu thức, vật phẩm nào.\n"
    "   - Mỗi thực thể chỉ cần xuất hiện 1 LẦN trong văn bản là PHẢI được nhận diện và trả về.\n"
    "   - Ưu tiên nhận diện các cụm 2-4 chữ Hán có chứa hậu tố tổ chức/địa danh (宗/门/派/帮/教/山/城/宫/殿/谷/寺/阁).\n"
    "   - Các danh xưng kép: 张三丰 -> 'Trương Tam Phong', 令狐冲 -> 'Lệnh Hồ Xung', 独孤求败 -> 'Độc Cô Cầu Bại'.\n\n"
    "Yêu cầu trả về kết quả dưới dạng JSON:\n"
    "{\n"
    '  "entities": [\n'
    '    {"chinese_name": "王威", "vietnamese_name": "Vương Uy", "entity_type": "NAME", "role": "con trai", "gender": "male"},\n'
    '    {"chinese_name": "丐帮", "vietnamese_name": "Cái Bang", "entity_type": "SECT", "role": null, "gender": null},\n'
    '    {"chinese_name": "明教", "vietnamese_name": "Minh Giáo", "entity_type": "SECT", "role": null, "gender": null},\n'
    '    {"chinese_name": "苏浅浅", "vietnamese_name": "Tô Thiển Thiển", "entity_type": "NAME", "role": "sư muội", "gender": "female"},\n'
    '    {"chinese_name": "灵法阁", "vietnamese_name": "Linh Pháp Các", "entity_type": "PLACE", "role": null, "gender": null},\n'
    '    {"chinese_name": "桑老", "vietnamese_name": "Tang lão", "entity_type": "NAME", "role": "tiền bối", "gender": "male"},\n'
    '    {"chinese_name": "莫雅仪", "vietnamese_name": "Mạc Nhã Nghi", "entity_type": "NAME", "role": "mẹ", "gender": "female"},\n'
    '    {"chinese_name": "乔长老", "vietnamese_name": "Kiều trưởng lão", "entity_type": "NAME", "role": "trưởng lão", "gender": "male"},\n'
    '    {"chinese_name": "雷神之息", "vietnamese_name": "Lôi Thần Chi Tức", "entity_type": "SKILL", "role": null, "gender": null},\n'
    '    {"chinese_name": "天桑灵宫", "vietnamese_name": "Thiên Tang Linh Cung", "entity_type": "PLACE", "role": null, "gender": null}\n'
    "  ],\n"
    '  "corrections": [\n'
    '    {"gg_error": "Xiao Fan", "correct_vietnamese": "Tiểu Phàm"},\n'
    '    {"gg_error": "Fane", "correct_vietnamese": "Tiểu Phàm"}\n'
    '  ]\n'
    "}"
)

async def collect_chapter_entities(chapter_id: int) -> Dict[str, Any]:
    """
    HỢP NHẤT BẰNG CHỨNG 2 NHÁNH GỬI LLM (Unified 2-Branch Evidence Collector)
    - Nhánh 1 (NER): Bóc tách từ Hán nghi vấn + ngữ cảnh (`context_han`) + ví dụ trong DB (`db_example`).
    - Nhánh 2 (Làm sạch GG): Bóc tách từ lỗi Google Translate (`gg_error`) + từ Hán gốc + ngữ cảnh (`context_han`).
    """
    async with AsyncSessionLocal() as session:
        stmt_ch = select(Chapter).where(Chapter.id == chapter_id)
        res_ch = await session.execute(stmt_ch)
        chapter = res_ch.scalar_one_or_none()
        
        if not chapter:
            raise Exception(f"Không tìm thấy Chapter ID {chapter_id} trong cơ sở dữ liệu.")
            
        novel_id = chapter.novel_id
        
        stmt_ver = select(ChapterVersion).where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.version_type.in_(["RAW", "GG"])
        )
        res_ver = await session.execute(stmt_ver)
        versions = res_ver.scalars().all()

        stmt_ent = select(NovelEntity).where(NovelEntity.novel_id == novel_id)
        res_ent = await session.execute(stmt_ent)
        db_entities = res_ent.scalars().all()
        
    raw_path = None
    gg_path = None
    
    for ver in versions:
        if ver.version_type == "RAW":
            raw_path = ver.file_path
        elif ver.version_type == "GG":
            gg_path = ver.file_path

    raw_text = ""
    if raw_path and os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
        raw_text = sanitize_chinese_raw_text(raw_text)

    gg_text = ""
    if gg_path and os.path.exists(gg_path):
        with open(gg_path, "r", encoding="utf-8", errors="ignore") as f:
            gg_text = f.read()

    # 1. Thu thập Nhánh 1 (NER Branch)
    ner_raw = await extract_ner_branch(novel_id, raw_text) if raw_text else []

    # 2. Thu thập Nhánh 2 (GG Clean Filter Branch)
    gg_raw = await extract_gg_clean_branch(raw_text, gg_text, db_entities) if (raw_text and gg_text) else []

    # 3. Gói dữ liệu từ điển đã lưu của Novel để nạp vào prompt cho LLM Extractor
    existing_db_dict = {
        e.chinese_name: {
            "vietnamese_name": e.rough_translation,
            "entity_type": e.entity_type or "NAME"
        }
        for e in db_entities
        if e.chinese_name and e.rough_translation and e.entity_type != "CORRECTION"
    }

    # 4. Gói dữ liệu gửi LLM (Kèm cặp song song: Chữ Hán gốc & Bản dịch gợi ý tra cứu)
    from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name
    branch_1_llm_payload = [
        {
            "original_han": item["han"],
            "suggested_hanviet_example": item.get("db_example") or build_hanviet_name(item["han"]),
            "context_han": item.get("context_han", item["han"])
        }
        for item in ner_raw
    ]

    branch_2_llm_payload = [
        {
            "original_han": item["original_han"],
            "suggested_hanviet_example": build_hanviet_name(item["original_han"]),
            "gg_error": item["gg_error"],
            "context_han": item.get("context_han", item["original_han"]),
            "context_gg": item.get("context_gg", "")
        }
        for item in gg_raw
    ]

    return {
        "chapter_id": chapter_id,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "existing_db_entities": existing_db_dict,
        "branch_1_ner_candidates": branch_1_llm_payload,
        "branch_2_gg_errors_to_clean": branch_2_llm_payload,
        "_internal_ner_details": ner_raw,
        "_internal_gg_details": gg_raw
    }

async def collect_batch_entities(chapter_ids: List[int]) -> Dict[str, Any]:
    """
    Gom bằng chứng của nhiều chương lại với nhau thành 1 payload duy nhất gửi LLM.
    Trả về Dict chứa các mảng đã gộp và chi tiết nội bộ theo từng chapter_id.
    """
    combined_branch_1 = []
    combined_branch_2 = []
    internal_details = {}
    
    novel_id = None
    
    for cid in chapter_ids:
        try:
            res = await collect_chapter_entities(cid)
            if novel_id is None:
                novel_id = res["novel_id"]
            
            combined_branch_1.extend(res["branch_1_ner_candidates"])
            combined_branch_2.extend(res["branch_2_gg_errors_to_clean"])
            
            internal_details[cid] = {
                "ner": res["_internal_ner_details"],
                "gg": res["_internal_gg_details"]
            }
        except Exception as e:
            print(f"Error collecting evidence for chapter {cid}: {e}")
            
    # Xoá trùng lặp (Deduplicate) để tiết kiệm token
    # Dedup branch 1 by 'original_han'
    b1_seen = set()
    b1_unique = []
    for item in combined_branch_1:
        k = item.get("original_han") or item.get("han")
        if k not in b1_seen:
            b1_seen.add(k)
            b1_unique.append(item)
            
    # Dedup branch 2 by 'gg_error' + 'original_han'
    b2_seen = set()
    b2_unique = []
    for item in combined_branch_2:
        k = (item["original_han"], item["gg_error"])
        if k not in b2_seen:
            b2_seen.add(k)
            b2_unique.append(item)

    existing_db_dict = {}
    if novel_id and chapter_ids:
        async with AsyncSessionLocal() as session:
            from app.models.schema import ChapterEntityLink
            stmt_ent = select(NovelEntity).join(ChapterEntityLink).where(
                ChapterEntityLink.chapter_id.in_(chapter_ids),
                NovelEntity.entity_type != "CORRECTION"
            )
            res_ent = await session.execute(stmt_ent)
            for e in res_ent.scalars():
                if e.chinese_name and e.rough_translation:
                    existing_db_dict[e.chinese_name] = {
                        "vietnamese_name": e.rough_translation,
                        "entity_type": e.entity_type or "NAME"
                    }

    return {
        "chapter_ids": chapter_ids,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "existing_db_entities": existing_db_dict,
        "branch_1_ner_candidates": b1_unique,
        "branch_2_gg_errors_to_clean": b2_unique,
        "_internal_batch_details": internal_details
    }

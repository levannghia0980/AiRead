import os
from typing import Dict, List, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, NovelEntity
from app.services.preprocessing.dichhan.entity_extractor import extract_ner_branch
from app.services.preprocessing.dichhan.entity_sanitizer import extract_gg_clean_branch
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

SYSTEM_PROMPT_INSTRUCTION = (
    "Nhiệm vụ của bạn là nhận diện và dịch âm Hán-Việt cổ phong / dịch nghĩa chuẩn xác các danh từ riêng, tên nhân vật, danh xưng xưng hô, chiêu thức, tên kiếm, bảo vật, địa danh từ văn bản tiếng Trung.\n\n"
    "CÁC QUY TẮC PHÂN LOẠI THỰC THỂ (entity_type):\n"
    "- 'NAME': Tên nhân vật & danh xưng xưng hô kèm chức danh (ví dụ: 王威 -> Vương Uy, 莫雅仪 -> Mạc Nhã Nghi, 徐小受 -> Từ Tiểu Thụ, 乔长老 -> Kiều trưởng lão, 桑老 -> Tang lão, 徐兄 -> Từ huynh).\n"
    "- 'SKILL': Chiêu thức, tuyệt kỹ, công pháp, võ học (ví dụ: 雷神之息 -> Lôi Thần Chi Sức, 九天落雷 -> Cửu Thiên Lạc Lôi, 呼吸之法 -> Hô Hấp Chi Pháp, 太极拳 -> Thái Cực Quyền, 剑诀 -> Kiếm Quyết).\n"
    "- 'ITEM': Kiếm, bảo vật, pháp bảo, thần khí, trang bị, đan dược (ví dụ: 紫光雷翼 -> Tử Quang Lôi Dực, 藏剑 -> Tàng Kiếm, 黑色轮盘 -> Hắc Sắc Chuyển Bàn).\n"
    "- 'PLACE': Địa danh, linh cung, thành phố, sông núi, điện thờ (ví dụ: 天桑灵宫 -> Thiên Tang Linh Cung, 望海市 -> Vọng Hải thị).\n"
    "- 'SECT': Tông môn, ma phái, tổ chức, thế lực, bang hội (ví dụ: 圣奴 -> Thánh Nô, 青云宗 -> Thanh Vân Tông, 驰越集团 -> Trì Việt Tập Đoàn).\n"
    "- 'OTHER': Các thuật ngữ chuyên biệt khác.\n\n"
    "CÁC QUY TẮC BẮT BUỘC ĐỂ ĐỒNG BỘ VÀ DỊCH CHUẨN XƯNG HÔ / TÊN THỰC THỂ:\n"
    "1. ĐỒNG BỘ TUYỆT ĐỐI VỚI TỪ ĐIỂN ĐÃ CÓ: Nếu một từ Hán gốc ĐÃ CÓ trong danh sách từ điển các chương trước được cung cấp, bạn BẮT BUỘC phải tuân thủ cách dịch đã có đó, KHÔNG ĐƯỢC tự ý đổi thành cách dịch khác.\n"
    "2. DỊCH CHUẨN HÁN-VIỆT CỔ PHONG CHO THỰC THỂ MỚI: Với tên nhân vật, chiêu thức, tên kiếm, bảo vật, địa danh CHƯA CÓ trong từ điển, BẮT BUỘC dịch theo âm Hán-Việt chuẩn trang trọng (Tiên Hiệp/Võ Hiệp). TUYỆT ĐỐI KHÔNG dịch thành tiếng Việt bình dân / nghĩa đen đời thường (Ví dụ: CẤM dịch '呼吸之法' thành 'Phương pháp hít thở', CẤM dịch '黑色轮盘' thành 'Bàn xoay màu đen', CẤM dịch '天桑灵宫' thành 'Cung điện tâm linh Thiên Tang').\n"
    "3. BỎ QUA HOÀN TOÀN đại từ nhân xưng đứng một mình (hắn, y, nàng, ngươi, ta...) hoặc các từ tiếng Việt thông dụng.\n"
    "4. NHÁNH 2 (Google Translate Errors): Nếu có lỗi do Google dịch sai (như để nguyên Pinyin/Tiếng Anh 'Serena', 'Wang Wei', 'Yayi' HOẶC dịch sai âm Hán-Việt đồng âm như Vương Vi -> Vương Uy), bạn PHẢI dịch lại từ tiếng Trung gốc sang Hán-Việt chuẩn và đưa vào 'corrections'.\n"
    "5. XỬ LÝ TIỀN TỐ/HẬU TỐ XƯNG HÔ MẬT THIẾT: Các từ xưng hô kèm tên như Tiểu (小), Lão (老), A (阿), Đại (大), Ca (哥), Tỷ (姐)... Phải gắn liền với tên. Ví dụ: 小威 -> 'Tiểu Uy', 阿亮 -> 'A Lượng'.\n"
    "6. ⚠️ NGUYÊN TẮC VÀNG — GIỮ NGUYÊN TRẬT TỰ HÁN-VIỆT CỔ PHONG TRUYỆN TRUNG CHO TÊN + XƯNG HÔ / CHỨC DANH: Khi trích xuất tên nhân vật có chức danh/bối phận/chức vụ (như 长老 -> Trưởng lão, 宗主 -> Tông chủ, 门主 -> Môn chủ, 师兄 -> Sư huynh, 师姐 -> Sư tỷ, 师父 -> Sư phụ, 城主 -> Thành chủ, 殿主 -> Điện chủ, 峰主 -> Phong chủ, 老 -> Lão, 兄 -> Huynh...):\n"
    "   BẮT BUỘC giữ nguyên trật tự Hán-Việt cổ phong: [Tên/Họ] + [Danh xưng/Chức danh/Lão/Huynh/Tỷ/Muội/Đệ/Trưởng lão].\n"
    "   Ví dụ BẮT BUỘC: 乔长老 -> 'Kiều trưởng lão' (TUYỆT ĐỐI KHÔNG DỊCH LÀ 'Trưởng lão Kiều'), 桑老 -> 'Tang lão' (KHÔNG DỊCH LÀ 'Lão Tang'), 徐兄 -> 'Từ huynh' (KHÔNG DỊCH LÀ 'Huynh Từ'), 李宗主 -> 'Lý tông chủ', 张师兄 -> 'Trương sư huynh', 穆师姐 -> 'Mục sư tỷ'.\n\n"
    "Yêu cầu trả về kết quả dưới dạng JSON:\n"
    "{\n"
    '  "entities": [\n'
    '    {"chinese_name": "乔长老", "vietnamese_name": "Kiều trưởng lão", "entity_type": "NAME"},\n'
    '    {"chinese_name": "莫雅仪", "vietnamese_name": "Mạc Nhã Nghi", "entity_type": "NAME"},\n'
    '    {"chinese_name": "雷神之息", "vietnamese_name": "Lôi Thần Chi Sức", "entity_type": "SKILL"},\n'
    '    {"chinese_name": "紫光雷翼", "vietnamese_name": "Tử Quang Lôi Dực", "entity_type": "ITEM"},\n'
    '    {"chinese_name": "天桑灵宫", "vietnamese_name": "Thiên Tang Linh Cung", "entity_type": "PLACE"},\n'
    '    {"chinese_name": "圣奴", "vietnamese_name": "Thánh Nô", "entity_type": "SECT"}\n'
    "  ],\n"
    '  "corrections": [\n'
    '    {"gg_error": "Xiao Fan", "correct_vietnamese": "Tiểu Phàm"},\n'
    '    {"gg_error": "Fane", "correct_vietnamese": "Tiểu Phàm"}\n'
    "  ]\n"
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

    # 4. Gói dữ liệu gửi LLM (Kèm ngữ cảnh context_han, loại bỏ positions rườm rà)
    branch_1_llm_payload = [
        {
            "han": item["han"],
            "context_han": item.get("context_han", item["han"]),
            "db_example": item["db_example"]
        }
        for item in ner_raw
    ]

    branch_2_llm_payload = [
        {
            "original_han": item["original_han"],
            "context_han": item.get("context_han", item["original_han"]),
            "context_gg": item.get("context_gg", ""),
            "gg_error": item["gg_error"]
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
    Gom bang chung cua nhieu chuong lai voi nhau thanh 1 payload duy nhat goi LLM.
    Tra ve Dict chua cac mang da gop va chi tiet noi bo theo tung chapter_id.
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
            
    # Xoá trùng l?p (Deduplicate) d? ti?t ki?m token
    # Dedup branch 1 by 'han'
    b1_seen = set()
    b1_unique = []
    for item in combined_branch_1:
        if item["han"] not in b1_seen:
            b1_seen.add(item["han"])
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

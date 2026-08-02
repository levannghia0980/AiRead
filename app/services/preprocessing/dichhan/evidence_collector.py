import os
from typing import Dict, List, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, NovelEntity
from app.services.preprocessing.dichhan.entity_extractor import extract_ner_branch
from app.services.preprocessing.dichhan.entity_sanitizer import extract_gg_clean_branch

SYSTEM_PROMPT_INSTRUCTION = (
    "Nhiệm vụ của bạn là nhận diện và dịch âm Hán-Việt chuẩn các danh từ riêng từ văn bản tiếng Trung.\n\n"
    "CÁC QUY TẮC PHÂN LOẠI THỰC THỂ (entity_type):\n"
    "- 'NAME': Tên nhân vật (ví dụ: 王威 -> Vương Uy, 莫雅仪 -> Mạc Nhã Nghi, 许若昕 -> Hứa Nhược Hân, 林渊 -> Lâm Uyên).\n"
    "- 'PLACE': Địa danh, thành phố, sông núi, đảo, địa điểm (ví dụ: 望海市 -> Vọng Hải thị).\n"
    "- 'SECT': Tông môn, ma phái, bang hội, tập đoàn, công ty (ví dụ: 驰越集团 -> Trì Việt Tập Đoàn, 青云宗 -> Thanh Vân Tông).\n"
    "- 'ITEM': Vật phẩm, bảo vật, thuốc, chế dược, thiết bị (ví dụ: 驰越制药 -> Trì Việt Chế Dược, 驰越重工 -> Trì Việt Trọng Công, 驰越电子 -> Trì Việt Điện Tử).\n"
    "- 'SKILL': Chiêu thức, võ kỹ, công pháp, khí công (ví dụ: 太极拳 -> Thái Cực Quyền, 剑诀 -> Kiếm Quyết).\n"
    "- 'OTHER': Các từ ngữ/thuật ngữ chuyên biệt khác.\n\n"
    "CÁC QUY TẮC BẮT BUỘC:\n"
    "1. KHÔNG sao chép nguyên `db_example` nếu nó mâu thuẫn với ngữ cảnh mới. Hãy luôn tự dịch từ tiếng Trung gốc sang âm Hán Việt chuẩn.\n"
    "2. BỎ QUA HOÀN TOÀN các đại từ nhân xưng (hắn, y, nàng, ngươi, ta...) hoặc các từ tiếng Việt thông dụng.\n"
    "3. NHÁNH 2 (Google Translate Errors): Nếu có lỗi do Google dịch sai (như để nguyên Pinyin/Tiếng Anh 'Serena', 'Wang Wei', 'Yayi' HOẶC dịch sai âm Hán-Việt đồng âm như Vương Vi -> Vương Uy), bạn PHẢI dịch lại từ tiếng Trung gốc sang Hán-Việt chuẩn và đưa vào 'corrections'.\n"
    "4. XỬ LÝ TIỀN TỐ/HẬU TỐ XƯNG HÔ: Các từ xưng hô kèm tên như Tiểu (小), Lão (老), A (阿), Đại (大), Ca (哥), Tỷ (姐)... Phải gắn liền với tên. Ví dụ: 小威 -> 'Tiểu Uy'.\n\n"
    "Yêu cầu trả về kết quả dưới dạng JSON:\n"
    "{\n"
    '  "entities": [\n'
    '    {"chinese_name": "莫雅仪", "vietnamese_name": "Mạc Nhã Nghi", "entity_type": "NAME"},\n'
    '    {"chinese_name": "望海市", "vietnamese_name": "Vọng Hải thị", "entity_type": "PLACE"},\n'
    '    {"chinese_name": "驰越集团", "vietnamese_name": "Trì Việt Tập Đoàn", "entity_type": "SECT"},\n'
    '    {"chinese_name": "驰越制药", "vietnamese_name": "Trì Việt Chế Dược", "entity_type": "ITEM"}\n'
    "  ],\n"
    '  "corrections": [\n'
    '    {"gg_error": "Mo Yayi", "correct_vietnamese": "Mạc Nhã Nghi"},\n'
    '    {"gg_error": "Serena", "correct_vietnamese": "Mạc Nhã Nghi"}\n'
    "  ]\n"
    "}"
)

async def collect_chapter_entities(chapter_id: int) -> Dict[str, Any]:
    """
    Há»¢P NHáº¤T Báº°NG CHá»¨NG 2 NHÃNH Gá»¬I LLM (Unified 2-Branch Evidence Collector)
    - NhÃ¡nh 1 (NER): BÃ³c tÃ¡ch tá»« HÃ¡n nghi váº¥n + ngá»¯ cáº£nh (`context_han`) + vÃ­ dá»¥ trong DB (`db_example`).
    - NhÃ¡nh 2 (LÃ m sáº¡ch GG): BÃ³c tÃ¡ch tá»« lá»—i Google Translate (`gg_error`) + tá»« HÃ¡n gá»‘c + ngá»¯ cáº£nh (`context_han`).
    - Lá»c tá»« nÃ³ng/nháº¡y cáº£m qua Unblock API.
    - Giá»¯ vá»‹ trÃ­ xuáº¥t hiá»‡n trong `_internal_gg_details` phá»¥c vá»¥ backend thay tháº¿ vÄƒn báº£n chÃ­nh xÃ¡c.
    """
    async with AsyncSessionLocal() as session:
        stmt_ch = select(Chapter).where(Chapter.id == chapter_id)
        res_ch = await session.execute(stmt_ch)
        chapter = res_ch.scalar_one_or_none()
        
        if not chapter:
            raise Exception(f"KhÃ´ng tÃ¬m tháº¥y Chapter ID {chapter_id} trong cÆ¡ sá»Ÿ dá»¯ liá»‡u.")
            
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

    gg_text = ""
    if gg_path and os.path.exists(gg_path):
        with open(gg_path, "r", encoding="utf-8", errors="ignore") as f:
            gg_text = f.read()

    # 1. Thu tháº­p NhÃ¡nh 1 (NER Branch)
    ner_raw = await extract_ner_branch(novel_id, raw_text) if raw_text else []

    # 2. Thu tháº­p NhÃ¡nh 2 (GG Clean Filter Branch)
    gg_raw = await extract_gg_clean_branch(raw_text, gg_text, db_entities) if (raw_text and gg_text) else []

    # 3. GÃ³i dá»¯ liá»‡u gá»­i LLM (KÃ¨m ngá»¯ cáº£nh context_han, loáº¡i bá» positions rÆ°á»m rÃ )
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
        "branch_1_ner_candidates": branch_1_llm_payload,
        "branch_2_gg_errors_to_clean": branch_2_llm_payload,
        # LÆ°u trá»¯ ná»™i bá»™ vá»‹ trÃ­ xuáº¥t hiá»‡n chi tiáº¿t cho backend thay tháº¿ sau khi LLM pháº£n há»“i
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

    return {
        "chapter_ids": chapter_ids,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "branch_1_ner_candidates": b1_unique,
        "branch_2_gg_errors_to_clean": b2_unique,
        "_internal_batch_details": internal_details
    }

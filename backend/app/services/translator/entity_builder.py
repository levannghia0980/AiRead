"""
Module Tự Động Trích Xuất & Lưu Persistent Tên Riêng, Quan Hệ Nhân Vật (Data-Driven Entity & Relationship Builder)
Dành cho Hệ Thống Dịch Thuật AiRead v2.
"""
import re
import os
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Glossary, Novel

logger = logging.getLogger(__name__)

# Từ điển Hán-Việt cơ bản offline fallback
_OFFLINE_HANVIET_MAP = {
    "宁毅": "Ninh Dịch",
    "苏檀儿": "Tô Đàn Nhi",
    "小婵": "Tiểu Thiền",
    "娟儿": "Quyên Nhi",
    "杏儿": "Hạnh Nhi",
    "苏家": "Tô gia",
    "秦淮": "Tần Hoài",
    "秦老": "Tần lão",
    "康老": "Khang lão",
    "陆红提": "Lục Hồng Đề",
    "云竹": "Vân Trúc",
    "锦儿": "Cẩm Nhi",
    "武朝": "Vũ Triều",
    "江宁": "Giang Ninh",
    "临安": "Lâm An",
}

def scan_candidate_entities(raw_chinese: str) -> List[str]:
    """
    Quét văn bản Hán gốc bằng Heuristic để tìm các cụm danh từ riêng / tên nhân vật / địa danh nghi vấn
    (cụm 2-4 chữ Hán xuất hiện lặp lại nhiều lần).
    """
    if not raw_chinese:
        return []
        
    # Tìm tất cả cụm 2-4 chữ Hán
    matches = re.findall(r"[\u4e00-\u9fff]{2,4}", raw_chinese)
    freq = {}
    for m in matches:
        freq[m] = freq.get(m, 0) + 1
        
    # Lấy các cụm lặp lại >= 2 lần
    candidates = [word for word, count in freq.items() if count >= 2]
    return candidates[:30]


async def extract_and_build_entities(
    raw_chinese: str,
    novel_id: int,
    db: AsyncSession,
    client: Optional[Any] = None,
    novel_title: str = ""
) -> Dict[str, Any]:
    """
    Trích xuất Tên riêng & Quan hệ nhân vật persistent trước khi dịch.
    Tự động lưu vào SQLite DB (Glossary) và ghi file characters.json.
    """
    if not raw_chinese:
        return {"glossary_map": {}, "relationship_map": {}}

    # 1. Tải danh sách Glossary đã có sẵn trong DB cho bộ truyện này
    stmt = select(Glossary).where((Glossary.novel_id == novel_id) | (Glossary.novel_id == None))
    res = await db.execute(stmt)
    existing_glossaries = res.scalars().all()
    
    existing_zh = {g.chinese_term: g.vietnamese_term for g in existing_glossaries}
    relationship_map = {}
    
    # Gom thông tin xưng hô/quan hệ nhân vật nếu có
    for g in existing_glossaries:
        notes = getattr(g, 'notes', None)
        if notes and "role:" in notes:
            role = notes.replace("role:", "").strip()
            relationship_map[g.vietnamese_term] = role

    # 2. Quét các từ nghi vấn chưa có trong DB
    candidates = scan_candidate_entities(raw_chinese)
    new_candidates = [c for c in candidates if c not in existing_zh]
    
    # Tự động tra từ điển Hán-Việt 0 Token, 0 Latency cho các từ mới trước tiên
    from app.services.translator.hanviet_data import convert_to_hanviet_name
    unresolved_candidates = []
    new_offline_entries = []
    
    for c in new_candidates:
        hv_trans = convert_to_hanviet_name(c)
        if hv_trans and hv_trans != c:
            existing_zh[c] = hv_trans
            new_offline_entries.append(
                Glossary(
                    novel_id=novel_id,
                    chinese_term=c,
                    vietnamese_term=hv_trans,
                    category="NAME",
                    notes="0-Token Offline HanViet Dict"
                )
            )
        else:
            unresolved_candidates.append(c)

    if new_offline_entries:
        db.add_all(new_offline_entries)
        await db.commit()
        logger.info(f"⚡ 0-Token Offline Lookup: Đã tra cứu tự động {len(new_offline_entries)} tên Hán-Việt thành công mà không tốn LLM token!")

    # 3. Chỉ gọi LLM Batch 1 lần duy nhất cho các từ thực sự phức tạp chưa tra được hoặc để trích quan hệ nhân vật ở Chương 1
    if unresolved_candidates and client:
        try:
            logger.info(f"🔍 Pre-Translation Scanner: Phát hiện {len(unresolved_candidates)} từ cần phân tích quan hệ. Đang batch-call qua AI...")
            sys_prompt = (
                "Bạn là một chuyên gia ngôn ngữ Hán-Việt và biên tập tiểu thuyết. "
                "Hãy phân tích danh sách các từ tiếng Trung sau và trích xuất Tên nhân vật, Địa danh, Môn phái kèm phiên âm Hán-Việt chuẩn và Vai trò/Quan hệ nhân vật (nếu có).\n"
                "Trả về DUY NHẤT một chuỗi JSON array có định dạng:\n"
                "[\n"
                "  {\"chinese_term\": \"宁毅\", \"vietnamese_term\": \"Ninh Dịch\", \"category\": \"NAME\", \"role\": \"Nam chính, con rể/Cô gia nhà họ Tô\"},\n"
                "  {\"chinese_term\": \"苏檀儿\", \"vietnamese_term\": \"Tô Đàn Nhi\", \"category\": \"NAME\", \"role\": \"Nữ chính, tiểu thư/thê tử nhà họ Tô\"}\n"
                "]"
            )
            user_prompt = f"Phân tích các cụm từ sau trong bối cảnh tiểu thuyết:\nTừ vựng nghi vấn: {', '.join(unresolved_candidates)}\nĐoạn văn tham khảo: {raw_chinese[:1500]}"
            
            res_ai = await client.translate(user_prompt, sys_prompt)
            ai_text = res_ai.get("text", "").strip()
            
            # Trích xuất JSON từ phản hồi của AI
            json_match = re.search(r"\[.*\]", ai_text, re.DOTALL)
            if json_match:
                items = json.loads(json_match.group(0))
                new_db_terms = []
                for item in items:
                    zh = item.get("chinese_term", "").strip()
                    vi = item.get("vietnamese_term", "").strip()
                    cat = item.get("category", "NAME").strip()
                    role = item.get("role", "").strip()
                    
                    if zh and vi:
                        existing_zh[zh] = vi
                        if role:
                            relationship_map[vi] = role
                        new_db_terms.append(
                            Glossary(
                                novel_id=novel_id,
                                chinese_term=zh,
                                vietnamese_term=vi,
                                category=cat,
                                notes=f"role:{role}" if role else None
                            )
                        )
                if new_db_terms:
                    db.add_all(new_db_terms)
                    await db.commit()
                    logger.info(f"🎉 Đã lưu persistent {len(new_db_terms)} tên riêng/thuật ngữ mới vào DB!")
        except Exception as e:
            logger.warning(f"⚠️ Pre-Translation AI Entity Scanner thất bại: {e}.")

    # 4. Fallback tra từ điển Hán-Việt offline cho các cụm từ quen thuộc nếu AI chưa quét
    new_offline_terms = []
    for zh, vi in _OFFLINE_HANVIET_MAP.items():
        if zh in raw_chinese and zh not in existing_zh:
            existing_zh[zh] = vi
            new_offline_terms.append(
                Glossary(
                    novel_id=novel_id,
                    chinese_term=zh,
                    vietnamese_term=vi,
                    category="NAME",
                    notes="Offline HanViet Dictionary"
                )
            )
    if new_offline_terms:
        db.add_all(new_offline_terms)
        await db.commit()

    # 5. Xuất file characters.json vào thư mục output của bộ truyện
    if novel_title:
        try:
            invalid_chars = '<>:"/\\|?*\r\n\t'
            safe_title = "".join(c for c in novel_title if c not in invalid_chars).strip().replace("  ", " ")
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            novel_folder = os.path.join(BASE_DIR, "output", safe_title)
            os.makedirs(novel_folder, exist_ok=True)
            
            char_json_path = os.path.join(novel_folder, "characters.json")
            with open(char_json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "glossary": existing_zh,
                    "relationships": relationship_map
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Không thể ghi file characters.json: {e}")

    return {
        "glossary_map": existing_zh,
        "relationship_map": relationship_map
    }

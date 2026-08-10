import json
import os
import httpx
import re
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.config import get_active_setting
from app.models.schema import Novel, Chapter, ChapterVersion, NovelEntity
from app.services.storage.file_storage import sanitize_filename
from app.services.translation.rawt.profiles import get_context_profile_prompt
from app.core.llm_client import post_gemini_with_retry
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

async def translate_chapter_llm(chapter_id: int) -> Dict[str, Any]:
    """
    Dịch 1 chương lẻ bằng cách chuyển vị trí sang hàm dịch lô (batch_size=1).
    Đảm bảo 100% nhất quán logic và không trùng lặp code.
    """
    return await translate_batch_llm([chapter_id])


async def get_previous_chapter_context(session, novel_id: int, current_first_chapter_no: int) -> str:
    """Lấy ~500 ký tự cuối của chương liền trước để làm ngữ cảnh nối tiếp mạch truyện"""
    if current_first_chapter_no <= 1:
        return ""
    
    stmt_prev = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_no == current_first_chapter_no - 1
    )
    res_prev = await session.execute(stmt_prev)
    prev_ch = res_prev.scalar_one_or_none()
    if not prev_ch:
        return ""
        
    for v_type in ["FINAL", "GG", "RAW"]:
        stmt_v = select(ChapterVersion).where(
            ChapterVersion.chapter_id == prev_ch.id,
            ChapterVersion.version_type == v_type
        )
        res_v = await session.execute(stmt_v)
        ver = res_v.scalar_one_or_none()
        if ver:
            content = ""
            if ver.content:
                content = ver.content
            elif ver.file_path and os.path.exists(ver.file_path):
                try:
                    with open(ver.file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    pass
            if content and content.strip():
                snippet = content.strip()[-500:]
                return f"Chương {prev_ch.chapter_no}: \"...{snippet}\""
    return ""


async def translate_batch_llm(chapter_ids: List[int], enable_names_dict: bool = True, **kwargs) -> Dict[str, Any]:
    """
    Dịch gộp N chương từ RAW sang Tiếng Việt bằng LLM.
    Trả về nội dung raw và mapping_table cho luồng Hậu xử lý.
    """
    if not chapter_ids:
        return {}
        
    async with AsyncSessionLocal() as session:
        stmt_ch = select(Chapter).where(Chapter.id == chapter_ids[0])
        res_ch = await session.execute(stmt_ch)
        first_ch = res_ch.scalar_one_or_none()
        if not first_ch:
            raise Exception("Không tìm thấy chương trong batch.")
            
        stmt_n = select(Novel).where(Novel.id == first_ch.novel_id)
        res_n = await session.execute(stmt_n)
        novel = res_n.scalar_one_or_none()
        if not novel:
            raise Exception("Không tìm thấy tiểu thuyết.")
            
        if not novel.context_profile:
            novel.context_profile = (novel.genres or "XIANXIA").lower()
            session.add(novel)
            await session.commit()
            
        # Lấy ngữ cảnh đoạn kết của chương liền trước
        prev_context = await get_previous_chapter_context(session, novel.id, first_ch.chapter_no)
            
        combined_text = ""
        chapter_map = {}
        
        for cid in chapter_ids:
            stmt = select(Chapter).where(Chapter.id == cid)
            res = await session.execute(stmt)
            chap = res.scalar_one_or_none()
            if not chap: continue
            
            chapter_map[cid] = chap.chapter_no
            
            stmt_raw = select(ChapterVersion).where(
                ChapterVersion.chapter_id == cid,
                ChapterVersion.version_type == "RAW"
            )
            res_raw = await session.execute(stmt_raw)
            ver_raw = res_raw.scalar_one_or_none()
            if not ver_raw: continue
                
            if ver_raw.content:
                raw_text = ver_raw.content
            elif ver_raw.file_path and os.path.exists(ver_raw.file_path):
                with open(ver_raw.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()
            else:
                continue
                
            raw_text = sanitize_chinese_raw_text(raw_text)
            combined_text += f"\n=== [BẮT ĐẦU CHƯƠNG {chap.chapter_no}] ===\n{raw_text}\n=== [KẾT THÚC CHƯƠNG {chap.chapter_no}] ===\n"

        dict_mapping = {}
        if enable_names_dict:
            novel_title = novel.title_rough or novel.title_raw

            # === RAWT CHỈ DÙNG ENTITIES — KHÔNG DÙNG CORRECTIONS ===
            # Thử load từ cache JSON trước (nhanh, không query DB)
            from app.services.storage.metadata_cache import (
                load_novel_entities_fast, load_chapter_entities_fast, get_metadata_entities_path
            )

            entities_cache_path = get_metadata_entities_path(novel_title)
            cache_available = entities_cache_path.exists()

            if cache_available:
                # Bước 1: Lấy entities đã linked với chapters từ cache per-chapter
                ch_entity_ids: set = set()
                chapter_entity_list = []
                for cid in chapter_ids:
                    stmt_ch_no = select(Chapter).where(Chapter.id == cid)
                    res_ch_no = await session.execute(stmt_ch_no)
                    ch_obj = res_ch_no.scalar_one_or_none()
                    if ch_obj:
                        ch_ents = load_chapter_entities_fast(novel_title, ch_obj.chapter_no)
                        for e in ch_ents:
                            if e["id"] not in ch_entity_ids:
                                ch_entity_ids.add(e["id"])
                                chapter_entity_list.append(e)

                # Bước 2: Scan toàn bộ entities của novel nếu từ Hán xuất hiện trong văn bản
                all_novel_entities = load_novel_entities_fast(novel_title)
                for e in all_novel_entities:
                    if e["id"] not in ch_entity_ids:
                        cn = e.get("chinese_name", "")
                        if cn and cn in combined_text:
                            chapter_entity_list.append(e)
                            ch_entity_ids.add(e["id"])

                for e in chapter_entity_list:
                    cn = e.get("chinese_name", "")
                    rt = e.get("rough_translation", "")
                    etype = e.get("entity_type") or "NAME"
                    if cn and rt and etype != "CORRECTION":
                        dict_mapping[cn] = f"{rt} [{etype}]"

            else:
                # Fallback: Query DB chính (khi chưa có cache)
                from app.models.schema import ChapterEntityLink
                stmt_linked = select(NovelEntity).join(ChapterEntityLink).where(
                    ChapterEntityLink.chapter_id.in_(chapter_ids),
                    NovelEntity.entity_type != "CORRECTION"
                )
                res_linked = await session.execute(stmt_linked)
                linked_entities = list(res_linked.scalars().all())

                stmt_all = select(NovelEntity).where(
                    NovelEntity.novel_id == novel.id,
                    NovelEntity.entity_type != "CORRECTION"
                )
                res_all = await session.execute(stmt_all)
                all_novel_entities_db = res_all.scalars().all()

                seen_ids = {e.id for e in linked_entities}
                for e in all_novel_entities_db:
                    if e.id not in seen_ids and e.chinese_name and e.chinese_name in combined_text:
                        linked_entities.append(e)

                for e in linked_entities:
                    if e.chinese_name and e.rough_translation:
                        dict_mapping[e.chinese_name] = f"{e.rough_translation} [{e.entity_type or 'NAME'}]"

    context_profile_prompt = get_context_profile_prompt(novel.context_profile)
    dict_json = json.dumps(dict_mapping, ensure_ascii=False, indent=2)
    
    prev_context_block = ""
    if prev_context:
        prev_context_block = f"""
=== NGỮ CẢNH ĐOẠN KẾT CHƯƠNG TRƯỚC (CHỈ THAM KHẢO NỐI MẠCH TRUYỆN/XƯNG HÔ - KHÔNG DỊCH LẠI ĐOẠN NÀY) ===
{prev_context}
========================================================================================
"""
    
    system_prompt = f"""Bạn là một dịch giả đại sư chuyên dịch tiểu thuyết Trung - Việt.
Dịch Hán văn sang tiếng Việt mượt mà, thuần Việt, chuẩn phong cách audiobook.

{context_profile_prompt}
{prev_context_block}
=== TỪ ĐIỂN THỰC THỂ ===
{dict_json}

=== YÊU CẦU ĐẦU RA ===
- Giữ nguyên cặp thẻ phân chương ở đầu ra: === [BẮT ĐẦU CHƯƠNG X] === và === [KẾT THÚC CHƯƠNG X] ===.
- Dịch đầy đủ 100% nội dung từng chương đến tận CÂU CUỐI CÙNG, không bỏ câu, không tóm tắt, không ngắt giữa chừng.
- BẢO TỒN DÒNG KẾT CHƯƠNG: Đảm bảo dịch đầy đủ đoạn kết. Nếu văn bản gốc có dòng "(Hết chương / 本章完)" hoặc ghi chú kết thúc chương, BẮT BUỘC giữ trọn vẹn ở cuối mỗi chương.
"""

    enable_unblock = kwargs.get("enable_unblock", True)
    if enable_unblock:
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, get_unblock_prompt_enforcer
        masked_text, mapping_table, _ = await mask_text_with_dictionary(combined_text)
        enforcer_prompt = "\n" + get_unblock_prompt_enforcer() if mapping_table else ""
    else:
        masked_text = combined_text
        mapping_table = {}
        enforcer_prompt = ""

    model = await get_active_setting("AIREAD_MODEL")
    api_key = await get_active_setting("AIREAD_API_KEYS")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    full_prompt = (
        system_prompt + enforcer_prompt +
        "\n\n=== VĂN BẢN CẦN DỊCH ===\n" + masked_text +
        "\n\n=== NHẮC LẠI: Dịch đủ 100% các chương, bọc đúng thẻ === [BẮT ĐẦU CHƯƠNG X] === và === [KẾT THÚC CHƯƠNG X] === cho từng chương! ==="
    )
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": 0.4, 
            "topK": 40, 
            "topP": 0.95,
            "maxOutputTokens": 65536
        },
        "safetySettings": safety_settings
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await post_gemini_with_retry(client, url, headers, payload)
        
    if resp.status_code != 200:
        raise Exception(f"Gemini API Error: {resp.text}")
        
    res_json = resp.json()
    candidate = res_json.get("candidates", [{}])[0]
    
    if candidate.get("finishReason") in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK"] or not candidate.get("content"):
        raise Exception(f"Bị chặn bởi Gemini Safety Policy: {resp.text}")

    translated_text = candidate["content"]["parts"][0]["text"].strip()

    return {
        "status": "success",
        "translated_text_masked": translated_text,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

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

async def translate_chapter_llm(chapter_id: int) -> Dict[str, Any]:
    """
    Dịch 1 chương lẻ bằng cách chuyển vị trí sang hàm dịch lô (batch_size=1).
    Đảm bảo 100% nhất quán logic và không trùng lặp code.
    """
    return await translate_batch_llm([chapter_id])


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
                
            combined_text += f"\n=== [BEGIN_CHAPTER_{cid}] ===\n{raw_text}\n=== [END_CHAPTER_{cid}] ===\n"

        dict_mapping = {}
        if enable_names_dict:
            from app.models.schema import ChapterEntityLink
            # Lấy các thực thể liên kết với các chương trong batch
            stmt_linked = select(NovelEntity).join(ChapterEntityLink).where(
                ChapterEntityLink.chapter_id.in_(chapter_ids),
                NovelEntity.entity_type != "CORRECTION"
            )
            res_linked = await session.execute(stmt_linked)
            linked_entities = res_linked.scalars().all()
            
            # Nếu chưa có liên kết trong DB, fallback lọc từ NovelEntity những từ có trong combined_text
            if not linked_entities:
                stmt_ent = select(NovelEntity).where(
                    NovelEntity.novel_id == novel.id,
                    NovelEntity.entity_type != "CORRECTION"
                )
                res_ent = await session.execute(stmt_ent)
                all_entities = res_ent.scalars().all()
                linked_entities = [e for e in all_entities if e.chinese_name and e.chinese_name in combined_text]
                
            dict_mapping = {e.chinese_name: e.rough_translation for e in linked_entities if e.chinese_name and e.rough_translation}

    context_profile_prompt = get_context_profile_prompt(novel.context_profile)
    dict_json = json.dumps(dict_mapping, ensure_ascii=False, indent=2)
    
    system_prompt = f"""
Bạn là một dịch giả tiểu thuyết Trung - Việt xuất sắc.
Nhiệm vụ của bạn là dịch văn bản sau đây sang tiếng Việt một cách tự nhiên, mượt mà và chuẩn xác nhất.

{context_profile_prompt}

=== YÊU CẦU DỊCH VĂN PHONG ===
1. Dịch tự nhiên, ưu tiên các cách diễn đạt tiếng Việt thuần thục và mượt mà.
2. Giảm lạm dụng các từ Hán-Việt gượng ép hoặc khó hiểu, nhưng vẫn đảm bảo giữ đúng ý nghĩa và tính thống nhất của thuật ngữ.
3. Thống nhất sử dụng danh sách Từ điển Thực thể dưới đây, có thể dịch việt hóa khác với từ điển nếu nó khó hiểu với người đọc.

=== TỪ ĐIỂN THỰC THỂ (TÊN/ĐỊA DANH/TÔNG MÔN/BẢO VẬT/CHIÊU THỨC) ===
{dict_json}

=== YÊU CẦU ĐẦU RA ===
Văn bản đầu vào chứa nhiều chương được ngăn cách bởi thẻ === [BEGIN_CHAPTER_X] === và === [END_CHAPTER_X] ===.
Bạn BẮT BUỘC PHẢI giữ nguyên y hệt các thẻ này ở đầu ra để hệ thống có thể cắt file. Không được dịch hoặc bỏ sót các thẻ này.
Chỉ trả về nội dung bản dịch tiếng Việt, không giải thích. Giữ nguyên định dạng xuống dòng.
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
    full_prompt = system_prompt + enforcer_prompt + "\n\n=== VĂN BẢN CẦN DỊCH ===\n" + masked_text
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.4, "topK": 40, "topP": 0.95},
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

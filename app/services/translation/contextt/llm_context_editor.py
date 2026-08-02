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
from app.services.translation.contextt.profiles import get_context_editor_prompt
from app.core.llm_client import post_gemini_with_retry

async def edit_chapter_context_llm(chapter_id: int, enable_unblock: bool = False) -> Dict[str, Any]:
    """
    Biên tập 1 chương lẻ bằng cách điều hướng sang hàm biên tập lô edit_context_batch_llm (batch_size=1).
    Đảm bảo 100% nhất quán logic và không trùng lặp code.
    """
    from app.services.unblock.unblock_pipeline import unmask_text_with_dictionary
    result = await edit_context_batch_llm([chapter_id], enable_unblock=enable_unblock)
    
    edited_text_masked = result["translated_text_masked"]
    mapping_table = result["mapping_table"]
    
    edited_text = unmask_text_with_dictionary(edited_text_masked, mapping_table) if mapping_table else edited_text_masked
    
    return {"status": "success", "edited_text": edited_text}


async def edit_context_batch_llm(chapter_ids: List[int], enable_names_dict: bool = True, **kwargs) -> Dict[str, Any]:
    """
    Biên tập gộp N chương từ bản dịch GG bằng Gemini theo lô.
    Trả về nội dung masked và mapping_table cho luồng Hậu xử lý.
    """
    if not chapter_ids:
        return {}
        
    async with AsyncSessionLocal() as session:
        stmt_chap = select(Chapter).where(Chapter.id == chapter_ids[0])
        res_chap = await session.execute(stmt_chap)
        first_chap = res_chap.scalar_one_or_none()
        if not first_chap:
            raise Exception("Không tìm thấy chương.")
            
        stmt_nov = select(Novel).where(Novel.id == first_chap.novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        
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
            
            stmt_gg = select(ChapterVersion).where(
                ChapterVersion.chapter_id == cid,
                ChapterVersion.version_type == "GG"
            )
            res_gg = await session.execute(stmt_gg)
            ver_gg = res_gg.scalar_one_or_none()
            if not ver_gg: continue
                
            if ver_gg.content:
                gg_text = ver_gg.content
            elif ver_gg.file_path and os.path.exists(ver_gg.file_path):
                with open(ver_gg.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    gg_text = f.read()
            else:
                continue
                
            combined_text += f"\n=== [BEGIN_CHAPTER_{cid}] ===\n{gg_text}\n=== [END_CHAPTER_{cid}] ===\n"

        from app.models.schema import ChapterEntityLink, ChapterCorrection

        entities_mapping = {}
        corrections_mapping = {}

        if enable_names_dict:
            # 1. Lấy thực thể liên kết với các chương trong batch hiện tại
            stmt_linked = select(NovelEntity).join(ChapterEntityLink).where(
                ChapterEntityLink.chapter_id.in_(chapter_ids),
                NovelEntity.entity_type != "CORRECTION"
            )
            res_linked = await session.execute(stmt_linked)
            linked_entities = res_linked.scalars().all()

            if not linked_entities:
                stmt_ent = select(NovelEntity).where(
                    NovelEntity.novel_id == novel.id,
                    NovelEntity.entity_type != "CORRECTION"
                )
                res_ent = await session.execute(stmt_ent)
                all_entities = res_ent.scalars().all()
                linked_entities = [e for e in all_entities if e.chinese_name and e.chinese_name in combined_text]

            entities_mapping = {e.chinese_name: e.rough_translation for e in linked_entities if e.chinese_name and e.rough_translation}

            # 2. Lấy danh sách lỗi dịch GG riêng cho các chương trong batch hiện tại
            stmt_corr = select(ChapterCorrection).where(ChapterCorrection.chapter_id.in_(chapter_ids))
            res_corr = await session.execute(stmt_corr)
            corrections = res_corr.scalars().all()
            corrections_mapping = {c.wrong_text: c.correct_text for c in corrections if c.wrong_text and c.correct_text}

    context_profile_prompt = get_context_editor_prompt(novel.context_profile)
    entities_json = json.dumps(entities_mapping, ensure_ascii=False, indent=2)
    corrections_json = json.dumps(corrections_mapping, ensure_ascii=False, indent=2)
    
    system_prompt = f"""
Bạn là Biên tập viên văn học tiểu thuyết chuyên nghiệp.
Nhiệm vụ chính của bạn là sửa đổi, chuẩn hóa xưng hô và phục hồi các chủ ngữ ẩn bị mất từ bản dịch Google Translate để tạo ra bản dịch tiếng Việt tự nhiên và trôi chảy.

{context_profile_prompt}

=== YÊU CẦU BIÊN TẬP & PHỤC HỒI NGỮ CẢNH ===
1. Khôi phục chủ ngữ ẩn & xưng hô thích hợp dựa trên ngữ cảnh xung quanh và các nhân vật hoạt động trong chương.
2. Sửa đại từ xưng hô generic (bạn/tôi, anh/cô) thành từ ngữ đúng bối cảnh truyện (như ta, ngươi, hắn, nàng, v.v.).
3. RÀ SOÁT VÀ ÁP DỤNG danh sách TỪ ĐIỂN THỰC THỂ và LỖI SỬA ĐỔI (CORRECTION) dưới đây.
4. Tuyệt đối giữ nguyên các thẻ bảo vệ Placeholder §PREFIX_XXXX§ (nếu có), chỉ điều chỉnh từ ngữ và ngữ pháp xung quanh chúng để câu văn tự nhiên nhất.

=== TỪ ĐIỂN THỰC THỂ (TÊN/ĐỊA DANH/TÔNG MÔN/BẢO VẬT/CHIÊU THỨC) ===
{entities_json}

=== DANH SÁCH LỖI GOOGLE TRANSLATE BẮT BUỘC SỬA (CORRECTION) ===
{corrections_json}

=== YÊU CẦU ĐẦU RA ===
Văn bản đầu vào chứa nhiều chương được ngăn cách bởi thẻ === [BEGIN_CHAPTER_X] === và === [END_CHAPTER_X] ===.
Bạn BẮT BUỘC PHẢI giữ nguyên y hệt các thẻ này ở đầu ra để hệ thống có thể cắt file. Không được dịch hoặc bỏ sót các thẻ này.
Chỉ trả về nội dung đã biên tập, không giải thích. Giữ nguyên định dạng xuống dòng.
"""

    model = await get_active_setting("AIREAD_MODEL")
    api_key = await get_active_setting("AIREAD_API_KEYS")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    enable_unblock = kwargs.get("enable_unblock", True)
    if enable_unblock:
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, get_unblock_prompt_enforcer
        masked_text, mapping_table, _ = await mask_text_with_dictionary(combined_text)
        enforcer_prompt = "\n" + get_unblock_prompt_enforcer() if mapping_table else ""
    else:
        masked_text = combined_text
        mapping_table = {}
        enforcer_prompt = ""
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": system_prompt + enforcer_prompt + "\n\n=== BẢN DỊCH THÔ (CẦN BIÊN TẬP) ===\n" + masked_text}]}],
        "generationConfig": {"temperature": 0.3, "topK": 40, "topP": 0.95},
        "safetySettings": safety_settings
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await post_gemini_with_retry(client, url, headers, payload)
        
    if resp.status_code != 200:
        raise Exception(f"Gemini API Error: {resp.text}")
        
    res_json = resp.json()
    candidate = res_json.get("candidates", [{}])[0]
    if candidate.get("finishReason") in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK"] or not candidate.get("content"):
        raise Exception(f"Bị chặn bởi Gemini: {resp.text}")
    
    edited_text_masked = candidate["content"]["parts"][0]["text"].strip()

    return {
        "status": "success",
        "translated_text_masked": edited_text_masked,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

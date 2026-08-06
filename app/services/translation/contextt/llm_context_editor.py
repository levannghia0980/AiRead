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
            
        # Lấy ngữ cảnh đoạn kết của chương liền trước
        prev_context = await get_previous_chapter_context(session, novel.id, first_chap.chapter_no)
            
        combined_text = ""
        combined_raw_text = ""
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
                
            stmt_raw = select(ChapterVersion).where(
                ChapterVersion.chapter_id == cid,
                ChapterVersion.version_type == "RAW"
            )
            res_raw = await session.execute(stmt_raw)
            ver_raw = res_raw.scalar_one_or_none()
            raw_text = ""
            if ver_raw:
                if ver_raw.content:
                    raw_text = ver_raw.content
                elif ver_raw.file_path and os.path.exists(ver_raw.file_path):
                    with open(ver_raw.file_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw_text = f.read()
                        
            combined_text += f"\n=== [BEGIN_CHAPTER_{cid}] ===\n{gg_text}\n=== [END_CHAPTER_{cid}] ===\n"
            if raw_text:
                combined_raw_text += f"\n=== [RAW_CHAPTER_{cid}] ===\n{raw_text}\n=== [END_RAW_CHAPTER_{cid}] ===\n"

        from app.models.schema import ChapterEntityLink, ChapterCorrection

        entities_mapping = {}
        corrections_mapping = {}

        if enable_names_dict:
            novel_title = novel.title_rough or novel.title_raw

            # === CONTEXT DÙNG CẢ ENTITIES + CORRECTIONS của chương ===
            from app.services.storage.metadata_cache import (
                load_novel_entities_fast, load_chapter_entities_fast,
                load_chapter_corrections_fast, get_metadata_entities_path
            )

            entities_cache_path = get_metadata_entities_path(novel_title)
            cache_available = entities_cache_path.exists()

            if cache_available:
                # Bước 1: Entities linked với từng chương từ cache
                ch_entity_ids: set = set()
                chapter_entity_list = []
                all_ch_corrections = {}

                for cid in chapter_ids:
                    stmt_ch_no = select(Chapter).where(Chapter.id == cid)
                    res_ch_no = await session.execute(stmt_ch_no)
                    ch_obj = res_ch_no.scalar_one_or_none()
                    if ch_obj:
                        # Entities của chương này
                        ch_ents = load_chapter_entities_fast(novel_title, ch_obj.chapter_no)
                        for e in ch_ents:
                            if e["id"] not in ch_entity_ids:
                                ch_entity_ids.add(e["id"])
                                chapter_entity_list.append(e)
                        # Corrections của chương này
                        ch_corrs = load_chapter_corrections_fast(novel_title, ch_obj.chapter_no)
                        for c in ch_corrs:
                            wt = c.get("wrong_text", "")
                            ct = c.get("correct_text", "")
                            if wt and ct:
                                all_ch_corrections[wt] = ct

                # Bước 2: Scan toàn bộ entities nếu từ Hán xuất hiện trong văn bản dịch
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
                        desc = f"{rt} [{etype}]"
                        details = []
                        if e.get("gender"):
                            gender_vi = "Nam" if e["gender"] == "male" else "Nữ" if e["gender"] == "female" else e["gender"]
                            details.append(f"Giới tính: {gender_vi}")
                        if e.get("role"):
                            details.append(f"Vai trò: {e['role']}")
                        if details:
                            desc += f" - ({', '.join(details)})"
                        entities_mapping[cn] = desc

                corrections_mapping = all_ch_corrections

            else:
                # Fallback: Query DB chính (khi chưa có cache)
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
                        desc = f"{e.rough_translation} [{e.entity_type or 'NAME'}]"
                        details = []
                        if getattr(e, "gender", None):
                            gender_vi = "Nam" if e.gender == "male" else "Nữ" if e.gender == "female" else e.gender
                            details.append(f"Giới tính: {gender_vi}")
                        if getattr(e, "role", None):
                            details.append(f"Vai trò: {e.role}")
                        if details:
                            desc += f" - ({', '.join(details)})"
                        entities_mapping[e.chinese_name] = desc

                stmt_corr = select(ChapterCorrection).where(ChapterCorrection.chapter_id.in_(chapter_ids))
                res_corr = await session.execute(stmt_corr)
                corrections = res_corr.scalars().all()
                corrections_mapping = {c.wrong_text: c.correct_text for c in corrections if c.wrong_text and c.correct_text}

    context_profile_prompt = get_context_editor_prompt(novel.context_profile)
    entities_json = json.dumps(entities_mapping, ensure_ascii=False, indent=2)
    corrections_json = json.dumps(corrections_mapping, ensure_ascii=False, indent=2)
    
    prev_context_block = ""
    if prev_context:
        prev_context_block = f"""
=== NGỮ CẢNH ĐOẠN KẾT CHƯƠNG TRƯỚC (CHỈ THAM KHẢO NỐI MẠCH TRUYỆN/XƯNG HÔ - KHÔNG BIÊN TẬP LẠI ĐOẠN NÀY) ===
{prev_context}
========================================================================================
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

    system_prompt = f"""
Bạn là một BIÊN TẬP VIÊN văn học chuyên nghiệp, đang chỉnh sửa bản dịch thô (từ Google Translate) của một tiểu thuyết mạng Trung Quốc.
Nhiệm vụ của bạn KHÔNG PHẢI là dịch, mà là BIÊN TẬP LẠI bản dịch thô dựa trên các quy tắc sau:

{context_profile_prompt}
1. Dựa vào ngữ cảnh câu chuyện để xác định ai đang nói chuyện với ai, qua đó điều chỉnh đại từ nhân xưng cho chuẩn xác và mượt mà (ví dụ: hắn -> cậu, cô ta -> bà, anh ta -> hắn...).
2. CẢNH BÁO: TUYỆT ĐỐI KHÔNG sử dụng văn phong Hán Việt (VietPhrase).
3. TUYỆT ĐỐI KHÔNG giữ lại bất kỳ ký tự tiếng Trung nào trong bản dịch. Bạn phải trả về 100% tiếng Việt tự nhiên.
4. BẮT BUỘC GIỮ NGUYÊN các thẻ phân cách chương (=== [BEGIN_CHAPTER_X] === và === [END_CHAPTER_X] ===) như bản gốc. Hệ thống sẽ bị LỖI NGHIÊM TRỌNG nếu bạn vứt bỏ các thẻ này khỏi đầu ra!
5. Nối tiếp mạch truyện: Đọc phần NGỮ CẢNH ĐOẠN KẾT CHƯƠNG TRƯỚC (nếu có) để nắm bắt xưng hô.
{prev_context_block}
=== TỪ ĐIỂN THỰC THỂ BẮT BUỘC ĐỒNG BỘ ===
{entities_json}

=== DANH SÁCH LỖI GOOGLE TRANSLATE BẮT BUỘC SỬA ===
{corrections_json}
"""

    model = await get_active_setting("AIREAD_MODEL")
    api_key = await get_active_setting("AIREAD_API_KEYS")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": system_prompt + enforcer_prompt + f"\n\n<ban_dich_tho_can_sua>\n{masked_text}\n</ban_dich_tho_can_sua>\n\nLỜI NHẮC CUỐI CÙNG BẮT BUỘC: Bạn PHẢI trả về nội dung được bọc trong các thẻ === [BEGIN_CHAPTER_X] === và === [END_CHAPTER_X] === y như đầu vào. Nếu thiếu các thẻ này, hệ thống sẽ sập!"}]}],
        "generationConfig": {"temperature": 0.3, "topK": 40, "topP": 0.95},
        "safetySettings": safety_settings
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await post_gemini_with_retry(client, url, headers, payload)
        
    edited_text_masked = None
    if resp.status_code == 200:
        res_json = resp.json()
        candidates = res_json.get("candidates", [])
        if candidates and candidates[0].get("content") and candidates[0].get("finishReason") not in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK"]:
            edited_text_masked = candidates[0]["content"]["parts"][0]["text"].strip()

    # Nếu bị Gemini chặn PROHIBITED_CONTENT / SAFETY: tiến hành Retry Masking bổ sung
    if not edited_text_masked:
        print(f"[LLM-CONTEXT-EDITOR] Cảnh báo: Gemini chặn bộ lọc PROHIBITED_CONTENT. Tiến hành che từ nhạy cảm bổ sung và thử lại...")
        # Mã hóa bổ sung các từ nhạy cảm tiếng Trung & Việt
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
        re_masked_text, extra_mapping, _ = await mask_text_with_dictionary(masked_text, aggressive=True)
        mapping_table.update(extra_mapping)
        
        retry_payload = {
            "contents": [{"role": "user", "parts": [{"text": system_prompt + enforcer_prompt + f"\n\n<ban_dich_tho_can_sua>\n{re_masked_text}\n</ban_dich_tho_can_sua>\n\nLỜI NHẮC CUỐI CÙNG BẮT BUỘC: Giữ nguyên các thẻ === [BEGIN_CHAPTER_X] === và === [END_CHAPTER_X] ==="}]}],
            "generationConfig": {"temperature": 0.3, "topK": 40, "topP": 0.95},
            "safetySettings": safety_settings
        }
        
        async with httpx.AsyncClient(timeout=600.0) as client:
            retry_resp = await post_gemini_with_retry(client, url, headers, retry_payload)
            if retry_resp.status_code == 200:
                retry_json = retry_resp.json()
                retry_cands = retry_json.get("candidates", [])
                if retry_cands and retry_cands[0].get("content"):
                    edited_text_masked = retry_cands[0]["content"]["parts"][0]["text"].strip()

    # Nếu vẫn bị chặn sau Retry: Fallback an toàn dùng trực tiếp bản dịch thô đã mask để không làm sập batch dịch
    if not edited_text_masked:
        print(f"[LLM-CONTEXT-EDITOR] ⚠️ Không thể vượt qua bộ lọc an toàn của Gemini cho lô này. Sử dụng bản dịch thô Google làm fallback để duy trì tiến trình.")
        edited_text_masked = masked_text

    return {
        "status": "success",
        "translated_text_masked": edited_text_masked,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

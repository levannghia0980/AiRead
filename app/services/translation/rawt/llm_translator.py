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
from app.core.llm_client import post_gemini_with_retry, post_openrouter_with_retry
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
                try:
                    from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
                    masked_snippet, _, _ = await mask_text_with_dictionary(snippet, flow="contextt")
                    return f"Chương {prev_ch.chapter_no}: \"...{masked_snippet}\""
                except Exception:
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

            from app.services.storage.metadata_cache import (
                load_chapter_entities_fast
            )

            chapter_entity_list = []
            ch_entity_ids = set()

            # 1. Đọc trực tiếp từ file JSON metadata của từng chương (Output/06_Metadata/.../chapters/*.json)
            for cid in chapter_ids:
                stmt_ch_no = select(Chapter).where(Chapter.id == cid)
                res_ch_no = await session.execute(stmt_ch_no)
                ch_obj = res_ch_no.scalar_one_or_none()
                if ch_obj:
                    ch_ents = load_chapter_entities_fast(novel_title, ch_obj.chapter_no)
                    if ch_ents:
                        for e in ch_ents:
                            eid = e.get("id")
                            cn = e.get("chinese_name")
                            if eid and eid not in ch_entity_ids:
                                ch_entity_ids.add(eid)
                                chapter_entity_list.append(e)
                            elif not eid and cn:
                                chapter_entity_list.append(e)

            # 2. Nạp fallback từ DB chính ChapterEntityLink nếu thiếu
            if not chapter_entity_list:
                from app.models.schema import ChapterEntityLink
                stmt_linked = select(NovelEntity).join(ChapterEntityLink).where(
                    ChapterEntityLink.chapter_id.in_(chapter_ids),
                    NovelEntity.entity_type != "CORRECTION"
                )
                res_linked = await session.execute(stmt_linked)
                for e in res_linked.scalars().all():
                    if e.id not in ch_entity_ids and e.chinese_name and e.rough_translation:
                        ch_entity_ids.add(e.id)
                        chapter_entity_list.append({
                            "id": e.id,
                            "chinese_name": e.chinese_name,
                            "rough_translation": e.rough_translation,
                            "entity_type": e.entity_type or "NAME",
                            "gender": getattr(e, "gender", None),
                            "role": getattr(e, "role", None)
                        })

            # 3. Đưa danh sách thực thể vào dict_mapping (Khớp thông minh: exact + substring + rough_translation)
            from app.services.translation.entity_matcher import build_entity_dict
            dict_mapping = build_entity_dict(chapter_entity_list, combined_text, corrections=None, include_details=False)

            # 4. Dự phòng: Nếu dict_mapping vẫn trống, nạp từ toàn bộ Novel
            if not dict_mapping:
                stmt_all_entities = select(NovelEntity).where(
                    NovelEntity.novel_id == novel.id,
                    NovelEntity.entity_type != "CORRECTION"
                ).order_by(NovelEntity.id.asc())
                res_all_entities = await session.execute(stmt_all_entities)
                all_entity_list = [
                    {
                        "chinese_name": e.chinese_name,
                        "rough_translation": e.rough_translation,
                        "entity_type": e.entity_type or "NAME",
                        "role": e.role
                    }
                    for e in res_all_entities.scalars().all()
                    if e.chinese_name and e.rough_translation
                ]
                dict_mapping = build_entity_dict(all_entity_list, combined_text, corrections=None, include_details=False)

    context_profile_prompt = get_context_profile_prompt(novel.context_profile)
    dict_json = json.dumps(dict_mapping, ensure_ascii=False, indent=2)
    
    prev_context_block = ""
    if prev_context:
        prev_context_block = f"""
=== NGỮ CẢNH ĐOẠN KẾT CHƯƠNG TRƯỚC (CHỈ THAM KHẢO NỐI MẠCH TRUYỆN/XƯNG HÔ - KHÔNG DỊCH LẠI ĐOẠN NÀY) ===
{prev_context}
========================================================================================
"""
    
    custom_prompt_val = kwargs.get("custom_prompt") or os.environ.get("AIREAD_CUSTOM_PROMPT") or await get_active_setting("AIREAD_CUSTOM_PROMPT") or ""
    custom_prompt_block = f"\n=== CHỈ DẪN BỔ SUNG CỦA NGƯỜI DÙNG ===\n{custom_prompt_val.strip()}\n" if custom_prompt_val and custom_prompt_val.strip() else ""

    system_prompt = f"""Bạn là một đại sư dịch giả văn học chuyên ngữ Hán - Việt đỉnh cao.
Nhiệm vụ: Dịch Hán văn sang tiếng Việt mượt mà, thuần Việt 100%, câu văn gãy gọn, giàu nhạc điệu, chuẩn phong cách audiobook / tiểu thuyết xuất bản.

{context_profile_prompt}
{prev_context_block}
=== BẢNG THAM KHẢO THỰC THỂ ĐÃ CHUẨN HÓA (DÙNG ĐÚNG KHI XUẤT HIỆN TRONG VĂN BẢN) ===
{dict_json}

{custom_prompt_block}
=== MỆNH LỆNH BẮT BUỘC ===
1. Giữ nguyên cặp thẻ phân chương ở đầu ra: === [BẮT ĐẦU CHƯƠNG X] === và === [KẾT THÚC CHƯƠNG X] ===.
2. Dịch đầy đủ 100% diễn biến nội dung, không bỏ câu, không tóm tắt, giữ dòng 'Hết chương' ở cuối mỗi chương.
3. Bản dịch đầu ra là 100% tiếng Việt thuần túy, sạch sẽ, không để sót chữ Hán rơi vãi (trừ các mã thẻ §...§ đã được bọc bảo vệ).
4. QUY TẮC ĐẠI TỪ 'Y' & CHÍNH TẢ: Khi dùng đại từ dẫn chuyện 'y', BẮT BUỘC có dấu cách (khoảng trắng) rõ ràng ở cả hai phía (' y ', 'y đã', 'nhìn y', 'thấy y'). TUYỆT ĐỐI CẤM viết dính liền chữ sai chính tả ('yđã', 'yđi', 'yvào', 'ngườiy', 'thấyy').
"""

    enable_unblock = kwargs.get("enable_unblock", True)
    if enable_unblock:
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, get_unblock_prompt_enforcer
        masked_text, mapping_table, _ = await mask_text_with_dictionary(combined_text, flow="rawt")
        enforcer_prompt = "\n" + get_unblock_prompt_enforcer() if mapping_table else ""
    else:
        masked_text = combined_text
        mapping_table = {}
        enforcer_prompt = ""

    provider_val = os.environ.get("AIREAD_PROVIDER") or await get_active_setting("AIREAD_PROVIDER") or "gemini"
    provider = str(provider_val).lower().strip()
    model = (os.environ.get("AIREAD_MODEL") or await get_active_setting("AIREAD_MODEL") or "gemini-3.5-flash-lite").strip()
    raw_api_key = os.environ.get("AIREAD_API_KEYS") or await get_active_setting("AIREAD_API_KEYS") or ""
    api_key = raw_api_key.split(',')[0].strip() if raw_api_key else ""
    
    print(f"[LLM-TRANSLATOR DEBUG] provider_val='{provider_val}' | provider='{provider}' | model='{model}' | has_slash={'/' in model}")
    
    unblock_final_reminder = " BẮT BUỘC GIỮ NGUYÊN 100% TẤT CẢ CÁC MÃ PLACEHOLDER §PREFIX_XXXX§ (như §BDY_..., §ACT_..., §SCN_...) XUẤT HIỆN TRONG VĂN BẢN! TUYỆT ĐỐI KHÔNG ĐƯỢC XÓA!" if (enable_unblock and mapping_table) else ""

    full_system_instruction = system_prompt + enforcer_prompt
    is_openrouter = (provider == "openrouter") or ("/" in model) or ("qwen" in model.lower()) or ("openrouter" in model.lower())
    print(f"[LLM-TRANSLATOR DEBUG] is_openrouter={is_openrouter}")

    # === CHỈ TỰ ĐỘNG CHIA ĐÔI KHI LÔ CÓ 1 CHƯƠNG DUY NHẤT VÀ VƯỢT NGƯỠNG AN TOÀN (> 45.000 ký tự) ===
    # Các chương như Chương 11 (42k), Chương 13 (37k) vẫn đủ 1 request an toàn và KHÔNG BỊ CHIA.
    # Riêng các chương như Chương 14 (58k), Chương 15 (52k) sẽ tự động chia đôi thành 2 phần cân bằng.
    def split_text_into_halves(text: str) -> List[str]:
        mid = len(text) // 2
        # Tìm vị trí xuống dòng gần điểm chính giữa nhất để cắt đôi văn bản mượt mà
        split_pos = text.find('\n', mid)
        if split_pos == -1:
            split_pos = text.rfind('\n', 0, mid)
        if split_pos != -1:
            return [text[:split_pos].strip(), text[split_pos:].strip()]
        return [text]

    is_single_chapter = (len(chapter_map) <= 1)
    if is_single_chapter and len(masked_text) > 45000:
        text_chunks = split_text_into_halves(masked_text)
    elif not is_single_chapter and len(masked_text) > 35000:
        err_msg = f"❌ [QUÁ DUNG LƯỢNG LÔ] Lô gồm {len(chapter_map)} chương (Chương {list(chapter_map.values())}) có tổng độ dài ({len(masked_text)} ký tự) vượt quá giới hạn an toàn. Vui lòng giảm Số chương/Lô (Batch Size) xuống 1 chương trong Cài đặt và dịch lại!"
        print(f"[LLM-TRANSLATOR] {err_msg}")
        try:
            from app.api.translation_router import add_system_log
            add_system_log(err_msg, "error")
        except Exception:
            pass
        raise ValueError(err_msg)
    else:
        text_chunks = [masked_text]

    translated_parts = []

    for chunk_idx, chunk_text in enumerate(text_chunks):
        if len(text_chunks) > 1:
            cno = list(chapter_map.values())[0] if chapter_map else ""
            chunk_msg = f"📄 [CHIA ĐÔI CHƯƠNG {cno}] Đang dịch Phần {chunk_idx + 1}/2 ({len(chunk_text)} ký tự)..."
            print(chunk_msg)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(chunk_msg, "pre")
            except Exception:
                pass

        user_task_prompt = (
            f"=== VĂN BẢN CẦN DỊCH ===\n{chunk_text}\n\n"
            f"=== NHẮC LẠI: Dịch đủ 100% nội dung đoạn văn trên, câu văn thuần Việt mượt mà!{unblock_final_reminder} ==="
        )

        if is_openrouter:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "AiRead"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": full_system_instruction},
                    {"role": "user", "content": user_task_prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 16384
            }
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await post_openrouter_with_retry(client, url, headers, payload)
            if resp.status_code == 200:
                res_json = resp.json()
                translated_parts.append(res_json["choices"][0]["message"]["content"].strip())
            else:
                raise Exception(f"OpenRouter API Error (HTTP {resp.status_code}): {resp.text}")
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
            ]
            payload = {
                "system_instruction": {"parts": [{"text": full_system_instruction}]},
                "contents": [{"role": "user", "parts": [{"text": user_task_prompt}]}],
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

            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            candidate = candidates[0] if candidates else {}
            prompt_block = res_json.get("promptFeedback", {}).get("blockReason")
            finish_reason = candidate.get("finishReason")
            
            # Nếu bị chặn bởi Gemini Safety Policy -> Xóa cache Trie, dọn sạch system prompt và thử lại
            if prompt_block or finish_reason in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK", "OTHER"] or not candidate.get("content"):
                err_cause = prompt_block or finish_reason or "NO_CONTENT"
                print(f"[LLM-TRANSLATOR] Cảnh báo: Gemini chặn bộ lọc safety ({err_cause}). Tiến hành che từ nhạy cảm bổ sung và tối ưu prompt...")
                from app.services.unblock.rawt.rawt_pipeline import clear_rawt_trie_cache
                clear_rawt_trie_cache()
                from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
                re_masked_text, extra_mapping, _ = await mask_text_with_dictionary(chunk_text, flow="rawt")
                
                # System prompt tối giản sạch sẽ để không bị dính từ nhạy cảm từ ngữ cảnh cũ
                clean_system_instruction = f"""Bạn là một đại sư dịch giả văn học chuyên ngữ Hán - Việt.
Nhiệm vụ: Dịch Hán văn sang tiếng Việt mượt mà, thuần Việt 100%, câu văn gãy gọn.

{context_profile_prompt}

=== MỆNH LỆNH BẮT BUỘC ===
1. Giữ nguyên cặp thẻ phân chương: === [BẮT ĐẦU CHƯƠNG X] === và === [KẾT THÚC CHƯƠNG X] ===.
2. Dịch đầy đủ 100% nội dung, không bỏ câu. Giữ nguyên 100% các mã §PREFIX_XXXX§.
"""
                
                retry_user_prompt = (
                    f"=== VĂN BẢN CẦN DỊCH ===\n{re_masked_text}\n\n"
                    f"=== NHẮC LẠI: Dịch đủ 100% nội dung đoạn văn trên, giữ nguyên các mã §PREFIX_XXXX§! ==="
                )
                
                retry_payload = {
                    "system_instruction": {"parts": [{"text": clean_system_instruction}]},
                    "contents": [{"role": "user", "parts": [{"text": retry_user_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4, 
                        "topK": 40, 
                        "topP": 0.95,
                        "maxOutputTokens": 65536
                    },
                    "safetySettings": safety_settings
                }
                
                async with httpx.AsyncClient(timeout=600.0) as client:
                    retry_resp = await post_gemini_with_retry(client, url, headers, retry_payload)
                
                retry_json = retry_resp.json()
                retry_cands = retry_json.get("candidates", [])
                retry_cand = retry_cands[0] if retry_cands else {}
                retry_prompt_block = retry_json.get("promptFeedback", {}).get("blockReason")
                retry_finish_reason = retry_cand.get("finishReason")
                
                if not retry_prompt_block and retry_finish_reason not in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK", "OTHER"] and retry_cand.get("content"):
                    candidate = retry_cand
                    mapping_table.update(extra_mapping)
                else:
                    # Fallback chia đôi đoạn văn để giảm mật độ từ khóa và vượt qua bộ lọc
                    print(f"[LLM-TRANSLATOR] Thử nghiệm chia nhỏ đoạn văn để vượt qua bộ lọc Gemini Safety...")
                    mid = len(re_masked_text) // 2
                    split_idx = re_masked_text.rfind("\n", 0, mid + 200)
                    if split_idx == -1 or split_idx < mid - 500:
                        split_idx = mid
                    part1_text = re_masked_text[:split_idx]
                    part2_text = re_masked_text[split_idx:]
                    
                    sub_outs = []
                    for sub_idx, sub_t in enumerate([part1_text, part2_text]):
                        sub_payload = {
                            "system_instruction": {"parts": [{"text": clean_system_instruction}]},
                            "contents": [{"role": "user", "parts": [{"text": f"=== VĂN BẢN CẦN DỊCH (Phần {sub_idx+1}/2) ===\n{sub_t}\n\n=== Dịch đủ 100% nội dung, giữ nguyên mã §...§ ==="}]}],
                            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 32768},
                            "safetySettings": safety_settings
                        }
                        async with httpx.AsyncClient(timeout=600.0) as client:
                            sub_resp = await post_gemini_with_retry(client, url, headers, sub_payload)
                        sub_j = sub_resp.json()
                        sub_c = sub_j.get("candidates", [{}])[0]
                        if sub_c.get("content") and sub_c.get("finishReason") not in ["SAFETY", "PROHIBITED_CONTENT"]:
                            sub_outs.append(sub_c["content"]["parts"][0]["text"].strip())
                    
                    if len(sub_outs) == 2:
                        candidate = {"content": {"parts": [{"text": "\n\n".join(sub_outs)}]}, "finishReason": "STOP"}
                        mapping_table.update(extra_mapping)
                    else:
                        err_block = retry_prompt_block or retry_finish_reason or "PROHIBITED_CONTENT"
                        raise Exception(f"Bị chặn bởi Gemini Safety Policy ({err_block}): {retry_resp.text}")

            finish_reason = candidate.get("finishReason")
            if finish_reason == "MAX_TOKENS":
                if not is_single_chapter:
                    err_max_tok = f"❌ [TRÀN TỐI ĐA TOKEN GEMINI] Lô Chương {list(chapter_map.values())} bị ngắt dở do chạm giới hạn token đầu ra tối đa của Gemini (MAX_TOKENS). Vui lòng giảm số chương/lô (Batch Size) xuống 1 chương!"
                    print(f"[LLM-TRANSLATOR] {err_max_tok}")
                    raise ValueError(err_max_tok)
                elif not candidate.get("content"):
                    err_max_tok = f"❌ [TRÀN TỐI ĐA TOKEN GEMINI] Đoạn văn chương {list(chapter_map.values())} bị ngắt dở do chạm giới hạn token đầu ra."
                    print(f"[LLM-TRANSLATOR] {err_max_tok}")
                    raise ValueError(err_max_tok)

            chunk_out = candidate["content"]["parts"][0]["text"].strip() if (candidate.get("content") and candidate["content"].get("parts")) else ""
            translated_parts.append(chunk_out)

    translated_text = "\n\n".join(translated_parts).strip()
    
    # Đảm bảo các thẻ chương bao bọc toàn bộ văn bản nếu bị thiếu
    for cid, cno in chapter_map.items():
        start_tag = f"=== [BẮT ĐẦU CHƯƠNG {cno}] ==="
        end_tag = f"=== [KẾT THÚC CHƯƠNG {cno}] ==="
        if start_tag not in translated_text:
            translated_text = f"{start_tag}\n" + translated_text
        if end_tag not in translated_text:
            translated_text = translated_text + f"\n{end_tag}"

    # === KIỂM TRA & KHÔI PHỤC THẺ PLACEHOLDER ===
    if enable_unblock and mapping_table:
        from app.services.unblock.unblock_pipeline import validate_placeholders, build_placeholder_reminder
        
        check = validate_placeholders(translated_text, mapping_table)
        pct = round(check["found"] / check["total"] * 100) if check["total"] > 0 else 100
        
        if not check["is_valid"]:
            missing_count = len(check["missing"])
            log_warn = f"⚠️ [UNBLOCK RAWT] Lô Chương {list(chapter_map.values())}: Phát hiện {missing_count}/{check['total']} thẻ bị LLM xóa trên TỔNG LÔ ({pct}% giữ được). Đang retry với prompt nhắc cụ thể..."
            print(log_warn)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(log_warn, "warning")
            except Exception:
                pass
            
            # === RETRY 1 LẦN với prompt nhắc cụ thể thẻ nào thiếu ===
            reminder = build_placeholder_reminder(check["missing"], mapping_table)
            retry_prompt = user_task_prompt + "\n\n" + reminder
            
            try:
                if is_openrouter:
                    payload_retry = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": full_system_instruction},
                            {"role": "user", "content": retry_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 16384
                    }
                    async with httpx.AsyncClient(timeout=600.0) as client:
                        resp2 = await post_openrouter_with_retry(client, url, headers, payload_retry)
                    if resp2.status_code == 200:
                        retry_text = resp2.json()["choices"][0]["message"]["content"].strip()
                        check2 = validate_placeholders(retry_text, mapping_table)
                        if check2["found"] > check["found"]:
                            translated_text = retry_text
                            pct2 = round(check2["found"] / check2["total"] * 100)
                            print(f"✅ [UNBLOCK RAWT RETRY] Lô Chương {list(chapter_map.values())} Cải thiện: {check['found']}→{check2['found']}/{check2['total']} thẻ trên TỔNG LÔ ({pct2}%)")
                        else:
                            print(f"ℹ️ [UNBLOCK RAWT RETRY] Lô Chương {list(chapter_map.values())} Không cải thiện, giữ bản gốc ({pct}%)")
                else:
                    payload["contents"] = [{"role": "user", "parts": [{"text": retry_prompt}]}]
                    async with httpx.AsyncClient(timeout=600.0) as client:
                        resp2 = await post_gemini_with_retry(client, url, headers, payload)
                    res2 = resp2.json()
                    c2 = res2.get("candidates", [{}])[0]
                    if c2.get("content") and c2.get("content", {}).get("parts"):
                        retry_text = c2["content"]["parts"][0]["text"].strip()
                        check2 = validate_placeholders(retry_text, mapping_table)
                        if check2["found"] > check["found"]:
                            translated_text = retry_text
                            pct2 = round(check2["found"] / check2["total"] * 100)
                            print(f"✅ [UNBLOCK RAWT RETRY] Lô Chương {list(chapter_map.values())} Cải thiện: {check['found']}→{check2['found']}/{check2['total']} thẻ trên TỔNG LÔ ({pct2}%)")
                        else:
                            print(f"ℹ️ [UNBLOCK RAWT RETRY] Lô Chương {list(chapter_map.values())} Không cải thiện, giữ bản gốc ({pct}%)")
            except Exception as e:
                print(f"⚠️ [UNBLOCK RAWT RETRY] Retry thất bại: {e}.")
                
        check_final = validate_placeholders(translated_text, mapping_table)
        pct_final = round(check_final["found"] / check_final["total"] * 100) if check_final["total"] > 0 else 100
        tier_desc = check_final.get("tier_desc", "")
        
        if not check_final["is_valid"]:
            err_msg = f"❌ [LỖI MẤT THẺ HÀNG LOẠT] Lô Chương {list(chapter_map.values())} bị mất nhiều thẻ nhạy cảm ({check_final['found']}/{check_final['total']} thẻ trên TỔNG LÔ = {pct_final}%). {tier_desc}. HỦY BỎ LƯU BÀI để chạy lại lô này!"
            print(f"[LLM-TRANSLATOR] {err_msg}")
            try:
                from app.api.translation_router import add_system_log
                add_system_log(err_msg, "error")
            except Exception:
                pass
            return {"error": err_msg}
        else:
            msg_ok = f"✅ [UNBLOCK RAWT] Lô Chương {list(chapter_map.values())}: {tier_desc} - Đạt chuẩn lưu đĩa!"
            print(msg_ok)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(msg_ok, "pre")
            except Exception:
                pass
            from app.api.translation_router import add_system_log
            add_system_log(msg_ok, "pre")
        except Exception:
            pass

    return {
        "status": "success",
        "translated_text_masked": translated_text,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

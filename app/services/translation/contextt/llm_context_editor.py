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
from app.core.llm_client import post_gemini_with_retry, post_openrouter_with_retry

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
    """Lấy 1-2 câu cuối của chương liền trước để làm ngữ cảnh nối tiếp mạch truyện"""
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
                clean_c = content.strip()
                tail = clean_c[-150:]
                first_punct = re.search(r'[.!?\n]', tail)
                if first_punct and first_punct.start() < len(tail) - 20:
                    snippet = tail[first_punct.start() + 1:].strip()
                else:
                    snippet = tail.strip()
                try:
                    from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
                    masked_snippet, _, _ = await mask_text_with_dictionary(snippet, flow="contextt")
                    return f"Chương {prev_ch.chapter_no}: \"...{masked_snippet}\""
                except Exception:
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
            
        # Lấy ngữ cảnh đoạn kết 1-2 câu của chương liền trước
        prev_context = await get_previous_chapter_context(session, novel.id, first_chap.chapter_no)
            
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
                
            # Đảm bảo mã thẻ neo là duy nhất (Unique Tag ID) không trùng lặp giữa các chương trong lô
            gg_text_unique_tags = re.sub(r'⟦\s*T(\d+)\s*:', f'⟦C{chap.chapter_no}_T\\1:', gg_text)
            combined_text += f"\n=== [BẮT ĐẦU CHƯƠNG {chap.chapter_no}] ===\n{gg_text_unique_tags}\n=== [KẾT THÚC CHƯƠNG {chap.chapter_no}] ===\n"

        from app.models.schema import ChapterEntityLink, ChapterCorrection

        entities_mapping = {}
        corrections_mapping = {}

        if enable_names_dict:
            novel_title = novel.title_rough or novel.title_raw

            from app.services.storage.metadata_cache import (
                load_chapter_entities_fast,
                load_chapter_corrections_fast
            )

            chapter_entity_list = []
            ch_entity_ids = set()
            all_ch_corrections = {}

            # 1. Đọc trực tiếp từ file JSON metadata của từng chương (Output/06_Metadata/.../chapters/*.json)
            for cid in chapter_ids:
                stmt_ch_no = select(Chapter).where(Chapter.id == cid)
                res_ch_no = await session.execute(stmt_ch_no)
                ch_obj = res_ch_no.scalar_one_or_none()
                if ch_obj:
                    ch_ents = load_chapter_entities_fast(novel_title, ch_obj.chapter_no)
                    ch_corrs = load_chapter_corrections_fast(novel_title, ch_obj.chapter_no)
                    if ch_ents:
                        for e in ch_ents:
                            eid = e.get("id")
                            cn = e.get("chinese_name")
                            if eid and eid not in ch_entity_ids:
                                ch_entity_ids.add(eid)
                                chapter_entity_list.append(e)
                            elif not eid and cn:
                                chapter_entity_list.append(e)
                    if ch_corrs:
                        for c in ch_corrs:
                            wt = c.get("wrong_text", "")
                            ct = c.get("correct_text", "")
                            if wt and ct:
                                all_ch_corrections[wt] = ct

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

            # 3. Đưa danh sách thực thể vào entities_mapping (Khớp thông minh: exact + substring + rough_translation + corrections)
            from app.services.translation.entity_matcher import build_entity_dict
            entities_mapping = build_entity_dict(chapter_entity_list, combined_text, corrections=all_ch_corrections, include_details=True)

            # 4. Dự phòng: Nếu entities_mapping vẫn trống, nạp toàn bộ thực thể của Novel
            if not entities_mapping:
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
                        "gender": getattr(e, "gender", None),
                        "role": getattr(e, "role", None)
                    }
                    for e in res_all_entities.scalars().all()
                    if e.chinese_name and e.rough_translation
                ]
                entities_mapping = build_entity_dict(all_entity_list, combined_text, corrections=all_ch_corrections, include_details=True)

            corrections_mapping = all_ch_corrections

    context_profile_prompt = get_context_editor_prompt(novel.context_profile)
    entities_json = json.dumps(entities_mapping, ensure_ascii=False, indent=2)
    corrections_json = json.dumps(corrections_mapping, ensure_ascii=False, indent=2)
    
    prev_context_block = ""
    if prev_context:
        prev_context_block = f"\n=== NGỮ CẢNH CÂU CUỐI CHƯƠNG TRƯỚC (THAM KHẢO NỐI MẠCH) ===\n{prev_context}\n"
    
    custom_prompt_val = kwargs.get("custom_prompt") or os.environ.get("AIREAD_CUSTOM_PROMPT") or await get_active_setting("AIREAD_CUSTOM_PROMPT") or ""
    custom_prompt_block = f"\n=== CHỈ DẪN BỔ SUNG CỦA NGƯỜI DÙNG ===\n{custom_prompt_val.strip()}\n" if custom_prompt_val and custom_prompt_val.strip() else ""

    enable_unblock = kwargs.get("enable_unblock", True)
    if enable_unblock:
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, get_unblock_prompt_enforcer
        masked_text, mapping_table, _ = await mask_text_with_dictionary(combined_text, flow="contextt")
        enforcer_prompt = "\n" + get_unblock_prompt_enforcer() if mapping_table else ""
    else:
        masked_text = combined_text
        mapping_table = {}
        enforcer_prompt = ""

    chinese_char_count = sum(1 for c in combined_text if '\u4e00' <= c <= '\u9fff')
    raw_fallback_notice = ""
    if len(combined_text) > 0 and (chinese_char_count / len(combined_text)) > 0.15:
        raw_fallback_notice = "\n⚠️ BẢN DỊCH THÔ CHỨA NHIỀU TIẾNG TRUNG: Bắt buộc dịch 100% sang tiếng Việt tự nhiên.\n"

    spec_dict = {
        "ROLE": "CHUYEN_GIA_BIEN_TAP_VAN_HOC_CAO_CAP",
        "NHIEM_VU": "Bien tap ban dich tho Google Translate thanh Tieng Viet 100% tu nhien, thoat y, chau chuot, chuan ngu phap.",
        "MUC_TIEU_BAT_BUOC": [
            "KHONG_DUOC_CAT_GOT: Giu nguyen 100% dung luong va tinh tiet, chuan hoa ngu phap tieng Viet muot ma dung nguyen tac, KHONG tu y them that tu ngu ngoai van ban.",
            "BAM_SAT_NGUYEN_TAC: TUYET DOI KHONG tu y bia them cau ngan, khong tu tien chen cac cau hoi tu tu thua thai (nhu 'sao?', 'u?', 'roi sao?'), khong suy dien them cam xuc hay tinh tiet ngoai van ban goc.",
            "TRAT_TU_DANH_XUNG_XUNG_HO_THEO_BOI_CANH: BAT BUOC tuan thu trat tu danh xung theo the loai:",
            "  * TU TIEN / CO PHONG / KIEM HIEP: Hau to danh xung/chuc vi BAT BUOC DUNG SAU [Ten/Ho] (Vd: Van su huynh, Tu su huynh, Kieu truong lao, Tang lao, Tieu tong chu, Tu huynh, Trieu su muoi, Truong dao huu). CAM dich nguoc thanh 'Su huynh Van', 'Truong lao Kieu', 'Lao Tang'. Tien to dung truoc: 'Tieu Uy', 'Lao Vuong', 'A Luong'.",
            "  * DO THI / HIEN DAI: Danh xung gia dinh dung TRUOC ten (Chu Vuong, Di Ly, Bac Truong). Chuc vu dung SAU ho/ten (Vuong tong, Ly giam doc, Nguyen ca, Nha ty).",
            "NHAN_DIEN_TEN_MOI_CHUA_CO_TRONG_TU_DIEN: Neu trong van ban xuat hien them ten nhan vat, danh xung, dia danh, mon phai MOI chua co trong bang thuc the, LLM BAT BUOC tu dong nhan dien theo ngu canh mach truyen va dich/phien am sang am HAN-VIET CHUAN CO PHONG. TUYET DOI KHONG ep gan nham sang ten khac, CAM dich nghia den doi thuong.",
            "BAO_TOAN_100%_MA_THE_UNBLOCK: Bat buoc giu nguyen 100% tat ca cac ma §PREFIX_XXXX§ (nhu §BDY_..., §ACT_..., §ST_..., §SCN_...). KHONG duoc gop ma, CAM XOA hoac tu y sua ma!",
            "XUNG_HO_THEO_THE_HAN_GOC: The neo ‹Cx_Tn: Cụm_Hán_Gốc› (hoac ⟦Cx_Tn: Cụm_Hán_Gốc⟧) chua truc tiep tu/cum tu Han goc can dich. LLM phai dich tu Han goc nay sang dai tu xung ho / cum so huu Tieng Viet 100% tu nhien, chuan boi phan va van canh truyen, roi go bo the neo khoi van ban.",
            "CAM_XUNG_HO_TAO_MAY: Trong quan he than toc hoac tieu thuyet, TUYET DOI KHONG dung 'tao - may' (dung 'Ta - Nguoi', 'Me - Con', 'Huynh - De'...).",
            "DONG_BO_TEN_THUC_THE: Tra cuu bang TU_DIEN_THUC_THE de sua dung 100% ten thuc the da chuan hoa.",
            "BOC_SACH_THE_NEO: Xoa sach tat ca the ‹...› va ⟦...⟧ khoi van ban cuoi cung, tra ve Tieng Viet thuan muot.",
            "DINH_DANG_CHUONG: Giu nguyen cac the === [BẮT ĐẦU CHƯƠNG X] === va === [KẾT THÚC CHƯƠNG X] ===",
            "BAO_TON_DONG_HET_CHUONG: Bat buoc giu lai dong 'Hết chương' o cuoi moi chuong de biet chuong da ket thuc du noi dung trọn vẹn. Loai bo cac ghi chu ngoai le tac gia va quang cao trang web rac.",
            "LAM_SACH_LA_HET_VA_CAM_THAN: TUYET DOI KHONG de cac chuoi chu la het, cuoi, ren ri lap lai dai vo nghia (nhu 'A a a a a...', 'Ha ha ha ha ha...'). Chuan hoa gon gang thanh tu cam than suc tich (1-3 tu: 'A!', 'Ha ha ha!', 'Á...', 'Ưm...') de AI Edge-TTS phat am tu nhien, khong bi vap hay doc e a.",
            "CHUAN_HOA_DAU_CHAM_PHAY_TIENG_VIET: Cham cau '.' dut khoat khi het mot y tron ven, KHONG lam dung dau phay ',' noi dai ca doan theo van Trung khien TTS bi hut hoi doc don dap. Dung dau phay ngat ve cau hop ly theo ngu phap tieng Viet.",
            "KHONG_DUNG_KY_HIEU_DAC_BIET: KHONG dung ky hieu trang tri la ('★', '◆', '※', '^', '_', '~', ngoac giai nghia thua). Viet thang thanh cau van xuoi tieng Viet hoan chinh.",
            "TUYET_DOI_KHONG_DE_KY_TU_VIET_TAT: Viet day du 100% tat ca cac tu/ky tu viet tat (vi du: EXP -> diem kinh nghiem, HP -> luong mau, MP -> nang luong, Lv/Level -> cap do, NPC -> nhan vat phu, VIP -> khach quy, TP.HCM -> Thanh pho Ho Chi Minh...). Phai viet hoan chinh ra chu tieng Viet de Edge-TTS phat am chuan xac."
        ],
        "TU_DIEN_THUC_THE": entities_mapping,
        "BANG_SUA_LOI_GG": corrections_mapping
    }

    full_system_instruction = f"""{context_profile_prompt}
{prev_context_block}
{custom_prompt_block}
{raw_fallback_notice}
=== BẢNG QUY CHUẨN BIÊN TẬP JSON SPECIFICATION ===
{json.dumps(spec_dict, ensure_ascii=False, indent=2)}
{enforcer_prompt}
"""

    user_task_prompt = (
        f"<ban_dich_tho_google_translate>\n{masked_text}\n</ban_dich_tho_google_translate>\n\n"
        f"LỆNH THỰC THI: Hãy biên tập toàn bộ văn bản thô trên theo đúng chuẩn JSON specification ở trên. Giữ nguyên 100% mã §PREFIX_XXXX§, nắn xưng hô theo thẻ Hán gốc, và trả về văn bản hoàn chỉnh bọc trong các thẻ === [BẮT ĐẦU CHƯƠNG X] === và === [KẾT THÚC CHƯƠNG X] ===."
    )

    provider_val = os.environ.get("AIREAD_PROVIDER") or await get_active_setting("AIREAD_PROVIDER") or "gemini"
    provider = str(provider_val).lower().strip()
    model = (os.environ.get("AIREAD_MODEL") or await get_active_setting("AIREAD_MODEL") or "gemini-3.5-flash-lite").strip()
    raw_api_key = os.environ.get("AIREAD_API_KEYS") or await get_active_setting("AIREAD_API_KEYS") or ""
    api_key = raw_api_key.split(',')[0].strip() if raw_api_key else ""

    is_openrouter = (provider == "openrouter") or ("/" in model) or ("qwen" in model.lower()) or ("openrouter" in model.lower())
    print(f"[LLM-CONTEXT-EDITOR DEBUG] provider_val='{provider_val}' | provider='{provider}' | model='{model}' | is_openrouter={is_openrouter}")

    if is_openrouter:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AiRead"
        }
        safety_settings = []
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

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
    if is_single_chapter and len(masked_text) > 140000:
        text_chunks = split_text_into_halves(masked_text)
    elif not is_single_chapter and len(masked_text) > 120000:
        err_msg = f"❌ [QUÁ DUNG LƯỢNG LÔ CONTEXTT] Lô gồm {len(chapter_map)} chương (Chương {list(chapter_map.values())}) có tổng độ dài ({len(masked_text)} ký tự tiếng Việt) vượt quá giới hạn an toàn 120.000 ký tự. Vui lòng giảm Số chương/Lô (Batch Size) trong Cài đặt và dịch lại!"
        print(f"[LLM-CONTEXT-EDITOR] {err_msg}")
        try:
            from app.api.translation_router import add_system_log
            add_system_log(err_msg, "error")
        except Exception:
            pass
        raise ValueError(err_msg)
    else:
        text_chunks = [masked_text]

    edited_parts = []

    for chunk_idx, chunk_text in enumerate(text_chunks):
        if len(text_chunks) > 1:
            cno = list(chapter_map.values())[0] if chapter_map else ""
            chunk_msg = f"📄 [CHIA ĐÔI CHƯƠNG {cno}] Đang biên tập Phần {chunk_idx + 1}/2 ({len(chunk_text)} ký tự)..."
            print(chunk_msg)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(chunk_msg, "pre")
            except Exception:
                pass

        user_task_prompt = (
            f"<ban_dich_tho_google_translate>\n{chunk_text}\n</ban_dich_tho_google_translate>\n\n"
            f"LỆNH THỰC THI: Hãy biên tập toàn bộ đoạn văn thô trên theo đúng chuẩn JSON specification. Giữ nguyên 100% mã §PREFIX_XXXX§ và nắn xưng hô theo thẻ Hán gốc."
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
                "temperature": 0.2,
                "max_tokens": 16384
            }
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await post_openrouter_with_retry(client, url, headers, payload)
            if resp.status_code == 200:
                res_json = resp.json()
                choices = res_json.get("choices", [])
                if choices and choices[0].get("message"):
                    edited_parts.append(choices[0]["message"]["content"].strip())
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
                    "temperature": 0.2, 
                    "topK": 40, 
                    "topP": 0.95,
                    "maxOutputTokens": 65536
                },
                "safetySettings": safety_settings
            }

            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await post_gemini_with_retry(client, url, headers, payload)
                
            if resp.status_code == 200:
                res_json = resp.json()
                candidates = res_json.get("candidates", [])
                prompt_block = res_json.get("promptFeedback", {}).get("blockReason")
                if candidates and candidates[0].get("finishReason") == "MAX_TOKENS" and not is_single_chapter:
                    err_max_tok = f"❌ [TRÀN TỐI ĐA TOKEN GEMINI] Lô Chương {list(chapter_map.values())} bị ngắt dở do chạm giới hạn token đầu ra tối đa của Gemini (MAX_TOKENS). Vui lòng giảm số chương/lô (Batch Size) xuống 1 chương!"
                    print(f"[LLM-CONTEXT-EDITOR] {err_max_tok}")
                    raise ValueError(err_max_tok)
                if not prompt_block and candidates and candidates[0].get("content") and candidates[0].get("finishReason") not in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK", "OTHER"]:
                    text_cand = candidates[0]["content"]["parts"][0]["text"].strip() if (candidates[0].get("content") and candidates[0]["content"].get("parts")) else ""
                    edited_parts.append(text_cand)

    edited_text_masked = "\n\n".join(edited_parts).strip() if edited_parts else None

    # Đảm bảo các thẻ chương bao bọc toàn bộ văn bản nếu bị thiếu
    if edited_text_masked:
        for cid, cno in chapter_map.items():
            start_tag = f"=== [BẮT ĐẦU CHƯƠNG {cno}] ==="
            end_tag = f"=== [KẾT THÚC CHƯƠNG {cno}] ==="
            if start_tag not in edited_text_masked:
                edited_text_masked = f"{start_tag}\n" + edited_text_masked
            if end_tag not in edited_text_masked:
                edited_text_masked = edited_text_masked + f"\n{end_tag}"

    # Lưu bản lưu tạm của mapping_table ban đầu trước khi thử aggressive
    orig_mapping_table = dict(mapping_table)

    # Nếu bị Gemini chặn PROHIBITED_CONTENT / SAFETY: tiến hành Retry Masking bổ sung
    if not edited_text_masked:
        print(f"[LLM-CONTEXT-EDITOR] Cảnh báo: Gemini chặn bộ lọc safety. Tiến hành xóa cache & che từ nhạy cảm bổ sung và thử lại...")
        from app.services.unblock.contextt.contextt_pipeline import clear_contextt_trie_cache
        clear_contextt_trie_cache()
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
        re_masked_text, extra_mapping, _ = await mask_text_with_dictionary(masked_text, flow="contextt")
        
        retry_user_prompt = (
            f"<ban_dich_tho_google_translate>\n{re_masked_text}\n</ban_dich_tho_google_translate>\n\n"
            f"LỆNH THỰC THI: Hãy biên tập toàn bộ văn bản thô trên theo đúng chuẩn JSON specification ở trên. Giữ nguyên 100% mã §PREFIX_XXXX§, nắn xưng hô theo thẻ Hán gốc, và trả về văn bản hoàn chỉnh bọc trong các thẻ === [BẮT ĐẦU CHƯƠNG X] === và === [KẾT THÚC CHƯƠNG X] ===."
        )

        if is_openrouter:
            retry_payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": full_system_instruction},
                    {"role": "user", "content": retry_user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 16384
            }
            async with httpx.AsyncClient(timeout=600.0) as client:
                retry_resp = await post_openrouter_with_retry(client, url, headers, retry_payload)
            if retry_resp.status_code == 200:
                retry_json = retry_resp.json()
                choices = retry_json.get("choices", [])
                if choices and choices[0].get("message"):
                    edited_text_masked = choices[0]["message"]["content"].strip()
                    mapping_table.update(extra_mapping)
        else:
            retry_payload = {
                "system_instruction": {"parts": [{"text": full_system_instruction}]},
                "contents": [{"role": "user", "parts": [{"text": retry_user_prompt}]}],
                "generationConfig": {
                    "temperature": 0.3, 
                    "topK": 40, 
                    "topP": 0.95,
                    "maxOutputTokens": 65536
                },
                "safetySettings": safety_settings
            }
            
            async with httpx.AsyncClient(timeout=600.0) as client:
                retry_resp = await post_gemini_with_retry(client, url, headers, retry_payload)
                if retry_resp.status_code == 200:
                    retry_json = retry_resp.json()
                    retry_cands = retry_json.get("candidates", [])
                    if retry_cands and retry_cands[0].get("content") and retry_cands[0].get("finishReason") not in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK"]:
                        edited_text_masked = retry_cands[0]["content"]["parts"][0]["text"].strip()
                        mapping_table.update(extra_mapping)

    # NẾU GEMINI CHẶN DỊCH (SAFETY BLOCK): BÁO LỖI HỦY LÔ (Tuyệt đối không dùng bản dịch thô Google Translate)
    if not edited_text_masked:
        err_block = "❌ [GEMINI SAFETY BLOCK] Gemini từ chối xử lý do chính sách nội dung 18+. HỦY BỎ LƯU BÀI (Tuyệt đối không xuất bản dịch thô Google Translate làm đầu ra)."
        print(f"[LLM-CONTEXT-EDITOR] {err_block}")
        try:
            from app.api.translation_router import add_system_log
            add_system_log(err_block, "error")
        except Exception:
            pass
        raise ValueError(err_block)

    # Hậu xử lý dọn dẹp các thẻ neo inline ⟦Tn:...⟧ còn sót lại (nếu có)
    from app.services.translation.contextt.term_anchor_tagger import clean_remaining_anchor_tags
    edited_text_masked = clean_remaining_anchor_tags(edited_text_masked)

    # === KIỂM TRA & KHÔI PHỤC THẺ PLACEHOLDER ===
    if enable_unblock and mapping_table:
        from app.services.unblock.unblock_pipeline import validate_placeholders, build_placeholder_reminder
        
        check = validate_placeholders(edited_text_masked, mapping_table)
        pct = round(check["found"] / check["total"] * 100) if check["total"] > 0 else 100
        
        if not check["is_valid"]:
            missing_count = len(check["missing"])
            log_warn = f"⚠️ [UNBLOCK CONTEXTT] Lô Chương {list(chapter_map.values())}: Phát hiện {missing_count}/{check['total']} thẻ bị LLM xóa trên TỔNG LÔ ({pct}% giữ được). Đang kích hoạt Retry..."
            print(log_warn)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(log_warn, "warning")
            except Exception:
                pass
            
            reminder = build_placeholder_reminder(check["missing"], mapping_table)
            retry_task_prompt = user_task_prompt + "\n\n" + reminder
            
            try:
                if is_openrouter:
                    payload_r = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": full_system_instruction},
                            {"role": "user", "content": retry_task_prompt}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 16384
                    }
                    async with httpx.AsyncClient(timeout=600.0) as client:
                        resp_r = await post_openrouter_with_retry(client, url, headers, payload_r)
                    if resp_r.status_code == 200:
                        retry_text = resp_r.json()["choices"][0]["message"]["content"].strip()
                        check2 = validate_placeholders(retry_text, mapping_table)
                        if check2["found"] > check["found"]:
                            edited_text_masked = clean_remaining_anchor_tags(retry_text)
                            print(f"✅ [UNBLOCK CONTEXTT RETRY] Lô Chương {list(chapter_map.values())} Cải thiện: {check['found']}→{check2['found']}/{check2['total']} thẻ trên TỔNG LÔ")
                else:
                    payload_r = {
                        "system_instruction": {"parts": [{"text": full_system_instruction}]},
                        "contents": [{"role": "user", "parts": [{"text": retry_task_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2, 
                            "topK": 40, 
                            "topP": 0.95,
                            "maxOutputTokens": 65536
                        },
                        "safetySettings": safety_settings
                    }
                    async with httpx.AsyncClient(timeout=600.0) as client:
                        resp_r = await post_gemini_with_retry(client, url, headers, payload_r)
                    res_r = resp_r.json()
                    c_r = res_r.get("candidates", [{}])[0]
                    if c_r.get("content") and c_r.get("content", {}).get("parts"):
                        retry_text = c_r["content"]["parts"][0]["text"].strip()
                        check2 = validate_placeholders(retry_text, mapping_table)
                        if check2["found"] > check["found"]:
                            edited_text_masked = clean_remaining_anchor_tags(retry_text)
                            print(f"✅ [UNBLOCK CONTEXTT RETRY] Lô Chương {list(chapter_map.values())} Cải thiện: {check['found']}→{check2['found']}/{check2['total']} thẻ trên TỔNG LÔ")
            except Exception as e:
                print(f"⚠️ [UNBLOCK CONTEXTT RETRY] Thất bại: {e}")
                
        check_final = validate_placeholders(edited_text_masked, mapping_table)
        pct_final = round(check_final["found"] / check_final["total"] * 100) if check_final["total"] > 0 else 100
        tier_desc = check_final.get("tier_desc", "")
        
        if not check_final["is_valid"]:
            err_msg = f"❌ [LỖI MẤT THẺ HÀNG LOẠT] Lô Chương {list(chapter_map.values())} bị mất nhiều thẻ nhạy cảm ({check_final['found']}/{check_final['total']} thẻ trên TỔNG LÔ = {pct_final}%). {tier_desc}. HỦY BỎ LƯU BÀI để chạy lại lô này!"
            print(f"[LLM-CONTEXT-EDITOR] {err_msg}")
            try:
                from app.api.translation_router import add_system_log
                add_system_log(err_msg, "error")
            except Exception:
                pass
            return {"error": err_msg}
        else:
            msg_ok = f"✅ [UNBLOCK CONTEXTT] Lô Chương {list(chapter_map.values())}: {tier_desc} - Đạt chuẩn lưu đĩa!"
            print(msg_ok)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(msg_ok, "pre")
            except Exception:
                pass

    return {
        "status": "success",
        "translated_text_masked": edited_text_masked,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

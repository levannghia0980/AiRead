import json
import os
import httpx
import re
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.config import get_active_setting
from app.models.schema import Novel, Chapter, ChapterVersion, NovelEntity, ChapterEntityLink
from app.services.storage.file_storage import sanitize_filename
from app.services.translation.rawt.profiles import (
    get_context_profile_prompt,
    build_standard_system_prompt,
)
from app.core.llm_client import post_gemini_with_retry, post_openrouter_with_retry, post_grok_local_with_retry
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

FORBIDDEN_JUNK_WORDS = {
    "倒是", "大家", "大不了", "大声", "好日子", "按人头", "媳妇", "一下子", "出乱子",
    "租子", "日子", "围裙", "勺子", "大包", "磕头", "大梦", "大悟",
    "大礼", "前些日子", "些日子", "不仅日子", "过日子", "自治", "大时间",
    "今天", "明天", "昨天", "几天", "后天", "前天", "那天", "有一天", "精神", "眼神",
    "留神", "回神", "回过神", "门客", "不客", "画蛇", "悲天", "吊炸天", "吃上几天", "一听今天", "日上中天"
}


def dedupe_keep_order(lst: List[Any]) -> List[Any]:
    seen = set()
    res = []
    for item in lst:
        if item not in seen:
            seen.add(item)
            res.append(item)
    return res



async def translate_chapter_llm(chapter_id: int) -> Dict[str, Any]:
    """
    Dịch 1 chương lẻ bằng cách chuyển vị trí sang hàm dịch lô (batch_size=1).
    Đảm bảo 100% nhất quán logic và không trùng lặp code.
    """
    return await translate_batch_llm([chapter_id])


async def get_previous_chapter_context(session, novel_id: int, current_first_chapter_no: int) -> str:
    """
    Lấy 3-5 câu văn cuối cùng hoàn chỉnh (~300-600 ký tự) của chương liền trước
    để làm ngữ cảnh nối tiếp mạch truyện tự nhiên giữa các lô (Seamless Context Continuity).
    """
    if not current_first_chapter_no or current_first_chapter_no <= 1:
        return ""
    
    prev_chap_no = current_first_chapter_no - 1
    stmt_prev = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_no == prev_chap_no
    )
    res_prev = await session.execute(stmt_prev)
    prev_ch = res_prev.scalar_one_or_none()
    if not prev_ch:
        return ""
        
    for v_type in ["FINAL", "LLM", "EDITED", "GG", "RAW"]:
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
                # Loại bỏ các thẻ tag XML/HTML nếu có
                clean_c = re.sub(r'<[^>]*>', '', clean_c)
                clean_c = re.sub(r'^(?:===\s*)?(?:Chương|Chapter)\s*\d+[^\n]*\n', '', clean_c, flags=re.IGNORECASE)
                
                # Lấy đoạn văn đuôi ~800 ký tự
                tail_block = clean_c[-800:] if len(clean_c) > 800 else clean_c
                
                # Tách thành các câu hoàn chỉnh theo dấu kết câu (. ! ? … hoặc xuống dòng)
                sentences = re.split(r'(?<=[.!?…\n])\s+', tail_block)
                sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]
                
                # Lấy từ 3 đến 5 câu cuối cùng trọn vẹn
                selected_sentences = sentences[-5:] if len(sentences) >= 5 else sentences
                snippet = " ".join(selected_sentences).strip()
                if not snippet:
                    snippet = tail_block[-300:].strip()
                
                try:
                    from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
                    masked_snippet, _, _ = await mask_text_with_dictionary(snippet)
                    return f"=== BỐI CẢNH ĐOẠN KẾT CHƯƠNG {prev_chap_no} (ĐỂ NỐI MẠCH TỰ NHIÊN VÀO ĐẦU CHƯƠNG {current_first_chapter_no}) ===\n\"{masked_snippet}\"\n-> Yêu cầu: Hãy dịch phần mở đầu Chương {current_first_chapter_no} nối mạch tự nhiên, liền mạch diễn biến câu chuyện với đoạn kết trên.\n"
                except Exception:
                    return f"=== BỐI CẢNH ĐOẠN KẾT CHƯƠNG {prev_chap_no} (ĐỂ NỐI MẠCH TỰ NHIÊN VÀO ĐẦU CHƯƠNG {current_first_chapter_no}) ===\n\"{snippet}\"\n-> Yêu cầu: Hãy dịch phần mở đầu Chương {current_first_chapter_no} nối mạch tự nhiên, liền mạch diễn biến câu chuyện với đoạn kết trên.\n"
    return ""


async def _execute_single_llm_call(
    user_prompt: str,
    system_instruction: str,
    provider: str,
    model: str,
    api_key: str,
    is_grok_local: bool,
    is_openrouter: bool,
    custom_temp_str: str = "",
    custom_topp_str: str = "",
    custom_topk_str: str = "",
    default_temp: float = 0.7,
    chapter_map: dict = None,
    unblock_final_reminder: str = ""
) -> str:
    """Gọi LLM (Gemini, OpenRouter, Grok Local) và trả về text phản hồi hoàn chỉnh."""
    if is_grok_local:
        grok_url = os.environ.get("AIREAD_GROK_URL") or "http://127.0.0.1:8020/translate-text"
        payload = {
            "text": user_prompt,
            "system_instruction": system_instruction,
            "timeout": 300.0
        }
        async with httpx.AsyncClient(timeout=360.0) as client:
            res_data = await post_grok_local_with_retry(client, grok_url, payload, timeout=300.0)
        trans_text = res_data.get("translated_text", "").strip()
        if not trans_text:
            raise Exception("Grok Local Server không trả về nội dung (kết quả rỗng).")
        return trans_text

    elif is_openrouter:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AiRead"
        }
        use_temp = default_temp
        if custom_temp_str:
            try:
                use_temp = float(custom_temp_str)
            except Exception:
                pass
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": use_temp
        }
        if custom_topp_str:
            try:
                payload["top_p"] = float(custom_topp_str)
            except Exception:
                pass

        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await post_openrouter_with_retry(client, url, headers, payload)
        if resp.status_code == 200:
            res_json = resp.json()
            return res_json["choices"][0]["message"]["content"].strip()
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
        # Cấu hình chuẩn khuyến nghị của Google cho Gemini 3.x / Flash-Lite:
        # temperature: 0.7, topP: 0.9, topK: 40, thinkingConfig: thinkingLevel = "medium"
        use_temp = float(custom_temp_str) if custom_temp_str else (default_temp if default_temp is not None else 0.7)
        use_topp = float(custom_topp_str) if custom_topp_str else 0.9
        use_topk = int(custom_topk_str) if custom_topk_str else 40
        thinking_level = (os.environ.get("AIREAD_THINKING_LEVEL") or "medium").strip().lower()

        gen_config = {
            "temperature": use_temp,
            "topP": use_topp,
            "topK": use_topk,
            "thinkingConfig": {
                "thinkingLevel": thinking_level
            }
        }

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "safetySettings": safety_settings,
            "generationConfig": gen_config
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await post_gemini_with_retry(client, url, headers, payload)

        res_json = resp.json()
        if resp.status_code != 200:
            err_msg = res_json.get("error", {}).get("message", resp.text)
            raise Exception(f"Gemini API Error (HTTP {resp.status_code}): {err_msg}")

        candidates = res_json.get("candidates", [])
        candidate = candidates[0] if candidates else {}
        prompt_block = res_json.get("promptFeedback", {}).get("blockReason")
        finish_reason = candidate.get("finishReason")

        if prompt_block or finish_reason in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK", "OTHER", "RECITATION"] or not candidate.get("content"):
            err_cause = prompt_block or finish_reason or "NO_CONTENT"
            print(f"[LLM-TRANSLATOR] Cảnh báo: Gemini chặn bộ lọc ({err_cause}). Thử lại với prompt độc lập...")
            clean_system_instruction = f"""🔴 MỆNH LỆNH TỐI CAO: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- NGÔN NGỮ NGUỒN: TIẾNG TRUNG.
- NGÔN NGỮ ĐÍCH BẮT BUỘC: 100% TIẾNG VIỆT HOÀN CHỈNH (VIETNAMESE ONLY). CHỮ VIẾT ĐỀU LÀ TIẾNG VIỆT, TUYỆT ĐỐI KHÔNG ĐƯỢC LẪN BẤT KỲ NGÔN NGỮ NÀO KHÁC.
- 🛑 CẤM TUYỆT ĐỐI TIẾNG ANH: Tuyệt đối không dùng bất kỳ từ tiếng Anh nào (cấm các từ như 'But', 'And', 'So'...). Toàn bộ câu từ bắt buộc phải là 100% tiếng Việt.
- 🛑 CẤM SÓT CHỮ HÁN HOẶC PINYIN: Dịch sạch 100% sang tiếng Việt, không bỏ sót chữ Hán.
Nhiệm vụ: Chuyển ngữ từ ngữ liệu sang tác phẩm TIẾNG VIỆT hoàn chỉnh, dễ hiểu, đúng nghĩa và bảo toàn 100% cốt truyện nguyên tác. Mỗi chương bọc trong đúng cặp thẻ XML <chapter_X>. Dòng đầu tiên là 'Chương X: [Tên chương]'.
"""
            retry_payload = {
                "system_instruction": {"parts": [{"text": clean_system_instruction}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.35 if finish_reason == "RECITATION" else default_temp},
                "safetySettings": safety_settings
            }
            async with httpx.AsyncClient(timeout=600.0) as client:
                retry_resp = await post_gemini_with_retry(client, url, headers, retry_payload)
            retry_json = retry_resp.json()
            retry_cands = retry_json.get("candidates", [])
            retry_cand = retry_cands[0] if retry_cands else {}
            if retry_cand.get("content"):
                candidate = retry_cand
            else:
                raise Exception(f"Bị chặn bởi bộ lọc Gemini: {retry_json}")

        return candidate["content"]["parts"][0]["text"].strip() if (candidate.get("content") and candidate["content"].get("parts")) else ""


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
        chapter_raw_len_map = {}
        
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
            if not ver_raw:
                raise ValueError(f"Chương {chap.chapter_no} chưa có bản RAW để dịch. Tạm dừng để cào lại!")
                
            if ver_raw.content:
                raw_text = ver_raw.content
            elif ver_raw.file_path and os.path.exists(ver_raw.file_path):
                with open(ver_raw.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()
            else:
                raise ValueError(f"Tệp RAW của Chương {chap.chapter_no} bị rỗng hoặc không tồn tại trên đĩa. Tạm dừng để cào lại!")
                
            raw_text = sanitize_chinese_raw_text(raw_text)
            chapter_raw_len_map[chap.chapter_no] = len(raw_text)
            combined_text += f"\n<chapter_{chap.chapter_no}>\n{raw_text}\n</chapter_{chap.chapter_no}>\n"

        batch_entities_dict = {}
        if enable_names_dict:
            novel_title = novel.title_rough or novel.title_raw

            from app.services.storage.metadata_cache import load_chapter_entities_fast

            # 1. Đọc CHÍNH XÁC thực thể theo từng chương của lô này (từ Output/06_Metadata/<Truyện>/chapters/XXXXXX.json)
            for cid in chapter_ids:
                stmt_ch_no = select(Chapter).where(Chapter.id == cid)
                res_ch_no = await session.execute(stmt_ch_no)
                ch_obj = res_ch_no.scalar_one_or_none()
                if ch_obj:
                    cached_entities = load_chapter_entities_fast(novel_title, ch_obj.chapter_no)
                    if cached_entities:
                        for item in cached_entities:
                            c_name = (item.get("chinese_name") or "").strip()
                            v_name = (item.get("rough_translation") or item.get("vietnamese_name") or "").strip()
                            e_type = (item.get("entity_type") or "NAME").upper()
                            role = (item.get("role") or "").strip()
                            if c_name and v_name and c_name in combined_text:
                                batch_entities_dict[c_name] = {
                                    "vn": v_name,
                                    "type": e_type,
                                    "role": role
                                }

            # 1b. Tự động nạp trước các thực thể kinh điển từ SPECIAL_ENTITIES_MAP (Gold Standard)
            from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP
            for sp_k, sp_v in SPECIAL_ENTITIES_MAP.items():
                if sp_k in combined_text:
                    batch_entities_dict[sp_k] = {
                        "vn": sp_v,
                        "type": "NAME" if any(x in sp_v for x in ["Tú Sĩ", "Kim Cương", "Thần", "Thiên", "Tiến", "Luân", "Vạn", "Cái", "Mai", "Cấu", "Phi", "Cung", "Vương", "Tẩu", "Trùng", "Hổ", "Thú", "Hành Giả", "Toàn Phong", "Hòa Thượng", "Tòng", "Quỳ", "Thâm"]) else "LORE",
                        "role": ""
                    }

            # 2. Bổ sung các thực thể trong DB có xuất hiện thực tế trong văn bản lô dịch này
            # (Chỉ nạp những từ có trong combined_text để tránh gây nhiễu prompt)
            stmt_novel_ents = select(NovelEntity).where(
                NovelEntity.novel_id == novel.id,
                NovelEntity.entity_type != "CORRECTION"
            )
            res_novel_ents = await session.execute(stmt_novel_ents)
            for ent in res_novel_ents.scalars():
                if ent.chinese_name and ent.rough_translation:
                    c_clean = ent.chinese_name.strip()
                    if c_clean in combined_text:
                        # ƯU TIÊN VÀNG: Nếu có trong SPECIAL_ENTITIES_MAP thì ghi đè ngay bằng chuẩn
                        if c_clean in SPECIAL_ENTITIES_MAP:
                            batch_entities_dict[c_clean] = {
                                "vn": SPECIAL_ENTITIES_MAP[c_clean],
                                "type": (ent.entity_type or "NAME").upper(),
                                "role": (ent.role or "").strip()
                            }
                        elif c_clean not in batch_entities_dict:
                            # Làm sạch bản dịch thô từ DB: gọt bỏ ghi chú trong ngoặc đơn/kép, mũi tên suy luận, chữ Hán sót
                            raw_v = ent.rough_translation.strip()
                            raw_v = re.sub(r'[\(（\[【].*?[\)）\]】]', '', raw_v).strip()
                            if '->' in raw_v:
                                raw_v = raw_v.split('->')[-1].strip()
                            if '=>' in raw_v:
                                raw_v = raw_v.split('=>')[-1].strip()
                            raw_v = re.sub(r'[\u4e00-\u9fff]', '', raw_v).strip()
                            raw_v = re.sub(r'^(?:không có trong bảng|giữ nguyên|hoặc|tạm dịch)[:\s-]*', '', raw_v, flags=re.IGNORECASE).strip()
                            ent_role = (ent.role or "").strip()
                            # Phân loại nhóm từ thường / tham khảo
                            is_common = any(tag in ent_role.upper() for tag in ["TỪ THƯỜNG", "TU THUONG", "THAM KHẢO", "THAM KHAO"])

                            if raw_v:
                                batch_entities_dict[c_clean] = {
                                    "vn": raw_v,
                                    "type": "COMMON" if is_common else (ent.entity_type or "NAME").upper(),
                                    "role": ent_role
                                }

        # Tạo prompt thực thể phân loại: Tên riêng cố định vs Thuật ngữ bản sắc truyện
        entity_prompt_block = ""
        # Tạo prompt thực thể phân loại chi tiết theo từng nhóm & áp dụng Sub-string Suppression
        entity_prompt_block = ""
        if batch_entities_dict:
            from app.services.preprocessing.dichhan.common_lists import CHINESE_SURNAMES, EPITHET_SUFFIXES, LEADING_STRIP_PARTICLES
            from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP

            # 1. LÀM SẠCH THỰC THỂ AN TOÀN: Bảo vệ thực thể thật (như 煤球), loại bỏ chuỗi câu rác
            all_raw_keys = sorted(list(batch_entities_dict.keys()), key=len, reverse=True)
            suppressed_subkeys = set()

            JUNK_PARTICLES = ("确实", "比较", "一伙", "而且", "但是", "如果", "说道", "冷笑", "问道", "大声", "一下", "起来", "由于", "导致")
            for long_k in all_raw_keys:
                if any(jp in long_k for jp in JUNK_PARTICLES):
                    suppressed_subkeys.add(long_k)
                    continue
                if any(long_k.startswith(p) for p in LEADING_STRIP_PARTICLES) or any(long_k.startswith(p) for p in ["可是", "但是", "如果", "让", "但", "便", "就", "又", "也"]) or long_k.endswith("一伙"):
                    suppressed_subkeys.add(long_k)
                    continue

            for i, long_k in enumerate(all_raw_keys):
                if long_k in suppressed_subkeys:
                    continue
                for short_k in all_raw_keys[i + 1:]:
                    if short_k in suppressed_subkeys:
                        continue
                    if short_k in long_k and len(short_k) < len(long_k):
                        # Nếu long_k dài (>= 5 chữ) nuốt thực thể chuẩn 2-4 chữ (như 煤球):
                        # Chuỗi dài long_k là chuỗi câu rác bóc dính -> LOẠI BỎ long_k, BẢO TOÀN short_k!
                        if len(long_k) >= 5 and len(short_k) in (2, 3, 4):
                            suppressed_subkeys.add(long_k)
                            break
                        # Chỉ loại bỏ short_k nếu short_k là phần đuôi bị cụt sứt đầu 1 chữ của danh hiệu dài (như 白衣秀士 -> 衣秀士)
                        elif long_k.endswith(short_k) and len(long_k) - len(short_k) == 1 and short_k not in SPECIAL_ENTITIES_MAP:
                            if not any(short_k.startswith(s) for s in CHINESE_SURNAMES):
                                suppressed_subkeys.add(short_k)

            for sk in suppressed_subkeys:
                if sk in batch_entities_dict:
                    del batch_entities_dict[sk]

            # 2. PHÂN LOẠI THỰC THỂ THEO ĐÚNG DANH MỤC (CATEGORIZED ENTITIES) & KHỬ TRÙNG LẶP TRIỆT ĐỂ
            names_list = []      # Nhân vật, Ngoại hiệu, Danh xưng
            places_list = []     # Địa danh, Sơn trại, Thành trì, Sông núi
            sects_list = []      # Tông môn, Bang phái, Thế lực
            skills_list = []     # Tuyệt kỹ võ công, Chiêu thức, Thần thông
            items_list = []      # Pháp bảo, Binh khí, Đan dược, Đạo cụ
            creatures_list = []  # Yêu thú, Linh thú, Dị thú, Thú cưỡi, Thú cưng bản sắc
            lore_list = []       # Thuật ngữ thế giới quan, Bối cảnh, Phân kỳ
            common_list = []     # Từ ngữ đời thường, đồ dùng, món ăn

            seen_global_entities = set()

            for c_clean, info in batch_entities_dict.items():
                if isinstance(info, dict):
                    v_clean = info.get("vn", "").strip()
                    e_type = (info.get("type") or "NAME").upper()
                else:
                    v_clean = str(info).strip()
                    e_type = "NAME"

                if not c_clean or not v_clean or c_clean == v_clean:
                    continue
                # BẮT BUỘC: Chỉ lấy thực thể THỰC SỰ XUẤT HIỆN trong văn bản của lô này!
                if c_clean not in combined_text:
                    continue
                # Đảm bảo mỗi chữ Hán chỉ xuất hiện DUY NHẤT 1 LẦN trong toàn bộ bảng
                if c_clean in seen_global_entities:
                    continue
                seen_global_entities.add(c_clean)

                # Bỏ qua nếu là từ rác hoặc chứa từ ngữ ngữ pháp vô nghĩa
                if c_clean in FORBIDDEN_JUNK_WORDS or any(bw in c_clean for bw in ("日子", "租子", "乱子", "大声", "大不了", "倒是", "按人头")):
                    continue
                entry_line = f"  * Cụm Hán: 【{c_clean}】 ➔ Gợi ý: 【{v_clean}】"

                # Phân nhóm chuẩn xác
                if e_type == "COMMON":
                    common_list.append(entry_line)
                elif c_clean.endswith("期") or c_clean.endswith("时期") or c_clean in ["花石纲"]:
                    lore_list.append(entry_line)
                elif c_clean.startswith("半步") or c_clean in ["法天象地", "超倍化之术"]:
                    skills_list.append(entry_line)
                elif c_clean in ["水泊梁山", "八百里水泊梁山"] or any(t in e_type for t in ["PLACE", "LOCATION"]):
                    places_list.append(entry_line)
                elif "SECT" in e_type:
                    sects_list.append(entry_line)
                elif "SKILL" in e_type:
                    skills_list.append(entry_line)
                elif "CREATURE" in e_type or c_clean in ["煤球"]:
                    creatures_list.append(entry_line)
                elif "ITEM" in e_type:
                    items_list.append(entry_line)
                elif any(t in e_type for t in ["LORE_TERM", "OTHER"]):
                    lore_list.append(entry_line)
                else:
                    names_list.append(entry_line)

            # Khử trùng lặp trong từng nhóm
            names_list = dedupe_keep_order(names_list)
            places_list = dedupe_keep_order(places_list)
            sects_list = dedupe_keep_order(sects_list)
            skills_list = dedupe_keep_order(skills_list)
            items_list = dedupe_keep_order(items_list)
            creatures_list = dedupe_keep_order(creatures_list)
            lore_list = dedupe_keep_order(lore_list)
            common_list = dedupe_keep_order(common_list)

            all_blocks = []
            if names_list:
                all_blocks.append("【1. DANH SÁCH NHÂN VẬT & NGOẠI HIỆU (KHÓA CỐ ĐỊNH 100%)】:\n" + "\n".join(names_list[:80]))
            if places_list:
                all_blocks.append("【2. ĐỊA DANH, SƠN TRẠI & CĂN CỨ】:\n" + "\n".join(places_list[:40]))
            if sects_list:
                all_blocks.append("【3. TÔNG MÔN, BANG PHÁI & THẾ LỰC】:\n" + "\n".join(sects_list[:30]))
            if skills_list:
                all_blocks.append("【4. VÕ HỌC, TUYỆT KỸ & THẦN THÔNG】:\n" + "\n".join(skills_list[:40]))
            if creatures_list:
                all_blocks.append("【5. YÊU THÚ, LINH THÚ & DỊ THÚ BẢN SẮC (BẮT BUỘC DÙNG TÊN BẢN SẮC, CẤM DỊCH NÔM NA)】:\n" + "\n".join(creatures_list[:30]))
            if items_list:
                all_blocks.append("【6. BẢO VẬT, BINH KHÍ & ĐAN DƯỢC】:\n" + "\n".join(items_list[:30]))
            if lore_list:
                all_blocks.append("【7. THUẬT NGỮ THẾ GIỚI QUAN, TỪ LÓNG & BỐI CẢNH】:\n" + "\n".join(lore_list[:30]))

            if all_blocks:
                entity_prompt_block = (
                    "=== BẢNG THỰC THỂ ĐÃ ĐỐI CHIẾU CHUẨN XÁC TỪ CÁC CHƯƠNG TRƯỚC (BẮT BUỘC KHÓA 1-1) ===\n"
                    "🔴 MỆNH LỆNH TỐI CAO ĐỐI VỚI BẢNG THỰC THỂ:\n"
                    "- Toàn bộ các cụm chữ Hán trong dấu 【...】 từ mục 1 đến mục 7 dưới đây là CÁC TÊN NHÂN VẬT, ĐỊA DANH, MÔN PHÁI, CHIÊU THỨC ĐÃ ĐƯỢC ĐỐI CHIẾU CHUẨN TỪ CÁC CHƯƠNG TRƯỚC.\n"
                    "- Trong quá trình dịch, hễ gặp cụm chữ Hán nào có trong bảng này thì BẮT BUỘC PHẢI THAY THẾ CHÍNH XÁC 100% BẰNG CỤM TÊN TIẾNG VIỆT TƯƠNG ỨNG ĐÃ ĐƯỢC CUNG CẤP!\n"
                    "- TUYỆT ĐỐI CẤM TỰ DỊCH LẠI, CẤM ĐỔI ÂM, CẤM ĐỂ LỆCH DÙ CHỈ 1 KÝ TỰ, CẤM SÓT CHỮ HÁN LAI TẠP (ví dụ: gặp 【谢尽欢】 BẮT BUỘC dịch là 'Tạ Tận Hoan', cấm dịch thành 'Tạ Cận Hoan'; gặp 【杨化仙】 BẮT BUỘC dịch là 'Dương Hóa Tiên', cấm dịch thành 'Dương Hoa Tiên'; gặp 【叶圣】 BẮT BUỘC dịch là 'Diệp Thánh', cấm dịch thành 'Diệp Khốt').\n"
                    "- TUYỆT ĐỐI KHÔNG mở ngoặc đơn chú thích song ngữ hay giải thích trong thân bài dịch.\n\n"
                    + "\n\n".join(all_blocks)
                )

            # Khối bảng từ thường tham khảo (KHÔNG ÉP BUỘC DỊCH CHUẨN, cho phép dịch linh hoạt theo ngữ cảnh cho hay hơn)
            if common_list:
                common_prompt_block = (
                    "\n\n=== BẢNG TỪ ĐỜI THƯỜNG / THAM KHẢO (KHÔNG BẮT BUỘC KHÓA CHẾT, TÙY BIẾN THEO NGỮ CẢNH) ===\n"
                    "- Các từ dưới đây là danh từ chung, món ăn, nông sản hoặc đồ dùng sinh hoạt đời thường.\n"
                    "- CÁC BẢN DỊCH GỢI Ý DƯỚI ĐÂY CHỈ DÙNG LÀM THAM KHẢO, KHÔNG ÉP BUỘC BẠN PHẢI DỊCH CHUẨN THEO 100%.\n"
                    "- Nếu cần, bạn HOÀN TOÀN CÓ THỂ BỎ QUA GỢI Ý ĐỂ DỊCH THOÁT NGHĨA THEO NGỮ CẢNH CHO HAY HƠN, mượt mà và tự nhiên nhất với văn phong tiếng Việt:\n"
                    + "\n".join(common_list[:40])
                )
                if entity_prompt_block:
                    entity_prompt_block += common_prompt_block
                else:
                    entity_prompt_block = common_prompt_block

        # 3. Lấy ngữ cảnh 3-5 câu cuối của chương liền trước (Context Awareness)
        first_chap_no = min(chapter_map.values()) if chapter_map else (first_ch.chapter_no if first_ch else 1)
        prev_context_block = await get_previous_chapter_context(session, novel.id, first_chap_no)

    context_profile_prompt = get_context_profile_prompt(novel.context_profile)
    
    custom_prompt_val = kwargs.get("custom_prompt") or os.environ.get("AIREAD_CUSTOM_PROMPT") or await get_active_setting("AIREAD_CUSTOM_PROMPT") or ""
    custom_prompt_block = f"\n=== CHỈ DẪN BỔ SUNG CỦA NGƯỜI DÙNG ===\n{custom_prompt_val.strip()}\n" if custom_prompt_val and custom_prompt_val.strip() else ""

    chap_nos_list = list(chapter_map.values())
    chap_count = len(chap_nos_list)
    chap_list_str = ", ".join([f"Chương {c}" for c in chap_nos_list])

    enable_erotic = kwargs.get("enable_erotic", False)
    erotic_prompt_block = ""
    if enable_erotic:
        erotic_prompt_block = """
=== CHẾ ĐỘ SẮC VĂN 18+ & TỪ LÓNG (ĐANG BẬT) ===
- Bộ truyện đang được kích hoạt chế độ SẮC VĂN 18+ / TỪ LÓNG.
- Khi gặp các phân cảnh phòng the, ân ái, tiếp xúc da thịt, quan hệ nam nữ hoặc khẩu dâm, hãy dịch chân thực, gợi cảm, táo bạo, đúng chất sắc văn tiếng Việt.
- Giữ trọn vẹn các danh từ, động từ nhạy cảm và các mã placeholder tương ứng.
"""

    system_prompt = build_standard_system_prompt(
        profile_key=novel.context_profile,
        prev_context_block=prev_context_block,
        entity_prompt_block=entity_prompt_block,
        custom_prompt_block=custom_prompt_block,
        erotic_prompt_block=erotic_prompt_block,
        chap_count=chap_count,
        chap_list_str=chap_list_str
    )

    enable_unblock = kwargs.get("enable_unblock", True)
    if enable_unblock:
        from app.services.unblock.rawt.rawt_pipeline import clear_rawt_trie_cache
        clear_rawt_trie_cache()
        from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, get_unblock_prompt_enforcer
        masked_text, mapping_table, _ = await mask_text_with_dictionary(combined_text, flow="rawt", enable_erotic=enable_erotic)
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
    
    custom_temp_str = os.environ.get("AIREAD_TEMPERATURE") or await get_active_setting("AIREAD_TEMPERATURE") or ""
    custom_topp_str = os.environ.get("AIREAD_TOP_P") or await get_active_setting("AIREAD_TOP_P") or ""
    custom_topk_str = os.environ.get("AIREAD_TOP_K") or await get_active_setting("AIREAD_TOP_K") or ""
    
    print(f"[LLM-TRANSLATOR DEBUG] provider_val='{provider_val}' | provider='{provider}' | model='{model}' | has_slash={'/' in model}")
    
    unblock_final_reminder = " BẮT BUỘC GIỮ NGUYÊN TẤT CẢ CÁC MÃ PLACEHOLDER CÓ SẴN (như §BDY_..., §ACT_...) XUẤT HIỆN TRONG VĂN BẢN! TUYỆT ĐỐI CẤM TỰ BỊA THÊM MÃ MỚI NHƯ §PREFIX_...§ HOẶC BỌC TÊN RIÊNG VÀO THẺ!" if (enable_unblock and mapping_table) else ""

    full_system_instruction = system_prompt + enforcer_prompt
    is_grok_local = (provider in ["grok_local", "grok", "grok_web"]) or ("grok-web" in model.lower()) or (model == "grok-web-auto")
    is_openrouter = not is_grok_local and ((provider == "openrouter") or ("/" in model) or ("qwen" in model.lower()) or ("openrouter" in model.lower()))
    print(f"[LLM-TRANSLATOR DEBUG] is_grok_local={is_grok_local} | is_openrouter={is_openrouter}")

    # === LƯU ĐẦU VÀO CHUẨN BỊ VÀO Output/02_ChuanBi_DauVao ===
    try:
        from app.core.config import OUTPUT_DIR
        novel_folder = sanitize_filename(novel.title_rough or novel.title_raw or "Novel")
        in_out_dir = os.path.join(str(OUTPUT_DIR / "02_ChuanBi_DauVao"), novel_folder)
        os.makedirs(in_out_dir, exist_ok=True)
        res_chap_nos = sorted(list(chapter_map.values()))
        batch_tag = "_".join(map(str, res_chap_nos))
        input_log_path = os.path.join(in_out_dir, f"batch_ch{batch_tag}_input.txt")
        with open(input_log_path, "w", encoding="utf-8") as f_in:
            f_in.write(f"=== [ĐẦU VÀO DỊCH LÔ: CHƯƠNG {res_chap_nos}] ===\n")
            f_in.write(f"Tiểu thuyết: {novel.title_rough or novel.title_raw} (ID: {novel.id})\n\n")
            f_in.write("======================================================================\n")
            f_in.write("1. SYSTEM INSTRUCTION (HỒ SƠ DỊCH, BỐI CẢNH & BẢNG THỰC THỂ CỦA LÔ)\n")
            f_in.write("======================================================================\n")
            f_in.write(full_system_instruction)
            f_in.write("\n\n======================================================================\n")
            f_in.write("2. VĂN BẢN GỐC RAW THEO TỪNG CHƯƠNG GỬI CHO LLM\n")
            f_in.write("======================================================================\n")
            f_in.write(masked_text)
        print(f"📝 [1/2 DỊCH AI] Đã lưu ĐẦU VÀO chuẩn bị của lô vào: Output/02_ChuanBi_DauVao/{novel_folder}/batch_ch{batch_tag}_input.txt")
    except Exception as e_in:
        print(f"⚠️ Không thể lưu file đầu vào 02_ChuanBi_DauVao: {e_in}")

    def split_text_into_halves(text: str) -> List[str]:
        mid = len(text) // 2
        split_pos = text.find('\n', mid)
        if split_pos == -1:
            split_pos = text.rfind('\n', 0, mid)
        if split_pos != -1:
            return [text[:split_pos].strip(), text[split_pos:].strip()]
        return [text]

    is_single_chapter = (len(chapter_map) <= 1)
    text_chunks = split_text_into_halves(masked_text) if (is_single_chapter and len(masked_text) > 8000) else [masked_text]

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
            f"Dưới đây là văn bản chương truyện tiếng Trung cần dịch hoàn toàn sang 100% TIẾNG VIỆT theo đúng Hồ sơ thể loại, Bộ quy tắc chuyển ngữ và Bảng thực thể đã cung cấp:\n\n"
            f"<ngu_lieu_nguon>\n{chunk_text}\n</ngu_lieu_nguon>\n\n"
            f"Yêu cầu thực thi:\n"
            f"1. Dịch thoát ý tự nhiên, mạch lạc, dễ hiểu, chuẩn văn phong dịch thuật tiểu thuyết tiếng Việt.\n"
            f"2. Áp dụng chuẩn xác tên riêng theo Bảng thực thể, bản dịch hoàn toàn bằng tiếng Việt sạch chữ Hán.\n"
            f"3. Dịch đủ từng chương trong {chap_list_str}, mỗi chương bọc trong đúng cặp thẻ XML <chapter_X> tương ứng.{unblock_final_reminder}\n"
        )

        chunk_out = await _execute_single_llm_call(
            user_prompt=user_task_prompt,
            system_instruction=full_system_instruction,
            provider=provider,
            model=model,
            api_key=api_key,
            is_grok_local=is_grok_local,
            is_openrouter=is_openrouter,
            custom_temp_str=custom_temp_str,
            custom_topp_str=custom_topp_str,
            custom_topk_str=custom_topk_str,
            default_temp=0.7,
            chapter_map=chapter_map,
            unblock_final_reminder=unblock_final_reminder
        )
        translated_parts.append(chunk_out)

    translated_text = "\n\n".join(translated_parts).strip()
    

    # Đảm bảo các thẻ chương bao bọc toàn bộ văn bản (chỉ áp dụng an toàn cho lô 1 chương duy nhất)
    if len(chapter_map) == 1:
        cno = list(chapter_map.values())[0]
        start_tag = f"<chapter_{cno}>"
        end_tag = f"</chapter_{cno}>"
        if f"<chapter_{cno}>" not in translated_text and f"=== [BẮT ĐẦU CHƯƠNG {cno}] ===" not in translated_text:
            translated_text = f"{start_tag}\n" + translated_text
        if f"</chapter_{cno}>" not in translated_text and f"=== [KẾT THÚC CHƯƠNG {cno}] ===" not in translated_text:
            translated_text = translated_text + f"\n{end_tag}"
    else:
        # Nếu lô nhiều chương, kiểm tra xem LLM có dịch đủ và gán đúng thẻ XML cho từng chương không
        missing_chaps = []
        truncated_chaps = []
        for cid, cno in chapter_map.items():
            has_tag = bool(re.search(rf"<\s*chapter_{cno}\s*>", translated_text, re.IGNORECASE))
            has_header = bool(re.search(rf"^(?:\s*===\s*)?(?:Chương|CHAPTER)\s*{cno}\b", translated_text, re.MULTILINE | re.IGNORECASE))
            if not has_tag and not has_header:
                missing_chaps.append(cno)
            else:
                # Kiểm tra độ dài chương để phát hiện cắt cụt sớm hoặc đứt đoạn
                c_pat = rf"<\s*chapter_{cno}\s*>(.*?)(?:<\s*/\s*chapter_{cno}\s*>|<\s*chapter_|\Z)"
                c_match = re.search(c_pat, translated_text, re.DOTALL | re.IGNORECASE)
                if c_match:
                    chap_body = c_match.group(1).strip()
                    raw_len = chapter_raw_len_map.get(cno, 0)
                    # Tiếng Việt chuẩn luôn dài gấp 2.2 - 3.2 lần chữ Hán raw. Nếu ratio < 1.05 thì chắc chắn bị cắt cụt / ngắt lửng!
                    if raw_len > 600 and len(chap_body) < raw_len * 1.05:
                        truncated_chaps.append(cno)
        
        has_batch_issues = bool(missing_chaps or truncated_chaps)
        if has_batch_issues:
            retry_count = kwargs.get("batch_retry_count", 0)
            max_batch_retries = 2
            issue_desc = []
            if missing_chaps:
                issue_desc.append(f"thiếu thẻ chương {missing_chaps}")
            if truncated_chaps:
                issue_desc.append(f"bị cắt cụt/ngắt lửng cuối chương {truncated_chaps}")
            full_issues_str = "; ".join(issue_desc)
            
            print(f"[LLM-TRANSLATOR DEBUG] Output len={len(translated_text)}, tail={repr(translated_text[-200:])}")
            if retry_count < max_batch_retries:
                warn_msg = f"⚠️ [PHÁT HIỆN LỖI LÔ] AI {full_issues_str}. Tiến hành dịch lại lô với chỉ thị bổ sung (lần {retry_count + 1}/{max_batch_retries})..."
                print(f"[LLM-TRANSLATOR] {warn_msg}")
                try:
                    from app.api.translation_router import add_system_log
                    add_system_log(warn_msg, "warning")
                except Exception:
                    pass
                
                kwargs["batch_retry_count"] = retry_count + 1
                from app.services.unblock.rawt.rawt_pipeline import clear_rawt_trie_cache
                clear_rawt_trie_cache()
                return await translate_batch_llm(chapter_ids, enable_names_dict=enable_names_dict, **kwargs)
            else:
                # Cứu hộ tự động: Nếu sau retries AI vẫn bị lỗi hoặc cắt cụt, tự động dịch từng chương đơn lẻ trong lô
                rescue_msg = f"🔄 [TỰ ĐỘNG CỨU HỘ LÔ] Lô {list(chapter_map.values())} bị {full_issues_str}. Chuyển sang dịch từng chương đơn lẻ..."
                print(f"[LLM-TRANSLATOR] {rescue_msg}")
                try:
                    from app.api.translation_router import add_system_log
                    add_system_log(rescue_msg, "info")
                except Exception:
                    pass
                
                single_results = []
                single_mappings = dict(mapping_table)
                for cid in chapter_ids:
                    s_res = await translate_batch_llm([cid], enable_names_dict=enable_names_dict, **kwargs)
                    if "error" in s_res:
                        return s_res
                    if s_res.get("translated_text_masked"):
                        single_results.append(s_res["translated_text_masked"])
                    if s_res.get("mapping_table"):
                        single_mappings.update(s_res["mapping_table"])
                
                if single_results:
                    return {
                        "translated_text_masked": "\n\n".join(single_results),
                        "mapping_table": single_mappings
                    }
                else:
                    err_missing = f"❌ [LLM DỊCH THIẾU CHƯƠNG] Sau các lần dịch lại toàn bộ lô, AI vẫn bỏ sót các chương: {missing_chaps}."
                    print(f"[LLM-TRANSLATOR] {err_missing}")
                    return {"error": err_missing}

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
            base_prompt = (
                f"Dưới đây là văn bản chương truyện tiếng Trung cần dịch hoàn toàn sang 100% TIẾNG VIỆT theo đúng Hồ sơ thể loại, Bộ quy tắc chuyển ngữ và Bảng thực thể đã cung cấp:\n\n"
                f"<ngu_lieu_nguon>\n{masked_text}\n</ngu_lieu_nguon>\n\n"
                f"Yêu cầu thực thi:\n"
                f"1. Dịch thoát ý tự nhiên, mạch lạc, dễ hiểu, chuẩn văn phong dịch thuật tiểu thuyết tiếng Việt.\n"
                f"2. Áp dụng chuẩn xác tên riêng theo Bảng thực thể, bản dịch hoàn toàn bằng tiếng Việt sạch chữ Hán.\n"
                f"3. Dịch đủ từng chương trong {chap_list_str}, mỗi chương bọc trong đúng cặp thẻ XML <chapter_X> tương ứng.{unblock_final_reminder}\n"
            )
            retry_prompt = base_prompt + "\n\n" + reminder
            sys_inst = full_system_instruction

            try:
                retry_text = await _execute_single_llm_call(
                    user_prompt=retry_prompt,
                    system_instruction=sys_inst,
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    is_grok_local=is_grok_local,
                    is_openrouter=is_openrouter,
                    custom_temp_str=custom_temp_str,
                    custom_topp_str=custom_topp_str,
                    custom_topk_str=custom_topk_str,
                    default_temp=0.25,
                    chapter_map=chapter_map,
                    unblock_final_reminder=unblock_final_reminder
                )
                if retry_text:
                    check2 = validate_placeholders(retry_text, mapping_table)
                    if check2["found"] > check["found"]:
                        translated_text = retry_text
                        pct2 = round(check2["found"] / check2["total"] * 100) if check2["total"] > 0 else 100
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

    return {
        "status": "success",
        "translated_text_masked": translated_text,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

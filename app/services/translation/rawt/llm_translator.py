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
from app.core.llm_client import post_gemini_with_retry, post_openrouter_with_retry, post_grok_local_with_retry
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

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
                    if c_clean in combined_text and c_clean not in batch_entities_dict:
                        batch_entities_dict[c_clean] = {
                            "vn": ent.rough_translation.strip(),
                            "type": (ent.entity_type or "NAME").upper(),
                            "role": (ent.role or "").strip()
                        }

        # Tạo prompt thực thể phân loại: Tên riêng cố định vs Thuật ngữ bản sắc truyện
        entity_prompt_block = ""
        # Tạo prompt thực thể phân loại chi tiết theo từng nhóm & áp dụng Sub-string Suppression
        entity_prompt_block = ""
        if batch_entities_dict:
            FORBIDDEN_JUNK_WORDS = {
                "倒是", "大家", "大不了", "大声", "好日子", "按人头", "媳妇", "一下子", "出乱子",
                "租子", "日子", "围裙", "勺子", "大包", "磕头", "大梦", "大悟",
                "大礼", "前些日子", "些日子", "不仅日子", "过日子", "自治", "大时间",
                "今天", "明天", "昨天", "几天", "后天", "前天", "那天", "有一天", "精神", "眼神",
                "留神", "回神", "回过神", "门客", "不客", "画蛇", "悲天", "吊炸天", "吃上几天", "一听今天", "日上中天"
            }

            from app.services.preprocessing.dichhan.common_lists import CHINESE_SURNAMES, EPITHET_SUFFIXES, LEADING_STRIP_PARTICLES
            from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP

            # 1. SUB-STRING SUPPRESSION AN TOÀN: Loại bỏ các chuỗi rác dính liên từ hoặc mẩu rác cắt xén
            # 1. SUB-STRING SUPPRESSION AN TOÀN: Loại bỏ các chuỗi rác dính liên từ hoặc mẩu rác cắt xén
            # (Ví dụ: nếu đã có 白衣秀士 thì loại ngay 衣秀士; có 云里金刚 thì loại ngay 里金刚; có 沧州小旋风 thì loại ngay 州小旋风)
            # TUYỆT ĐỐI KHÔNG để chuỗi rác (như 让晁盖一伙, 但晁盖) nuốt mất thực thể chuẩn (như 晁盖, 杜迁, 王伦)!
            all_raw_keys = sorted(list(batch_entities_dict.keys()), key=len, reverse=True)
            suppressed_subkeys = set()
            for i, long_k in enumerate(all_raw_keys):
                if long_k in suppressed_subkeys:
                    continue
                # Nếu long_k dính liên từ phía trước hoặc hậu tố rác (như '一伙', '教唆'):
                if any(long_k.startswith(p) for p in LEADING_STRIP_PARTICLES) or any(long_k.startswith(p) for p in ["可是", "但是", "如果", "让", "但", "便", "就", "又", "也"]) or long_k.endswith("一伙"):
                    suppressed_subkeys.add(long_k)
                    continue

                for short_k in all_raw_keys[i + 1:]:
                    if short_k in suppressed_subkeys:
                        continue
                    if short_k in long_k and len(short_k) < len(long_k):
                        # Nếu short_k là phần đuôi/đầu bị cắt vụn (ví dụ: 云里金刚 -> 里金刚, 白衣秀士 -> 衣秀士, 沧州小旋风 -> 州小旋风)
                        # và short_k không có trong SPECIAL_ENTITIES_MAP độc lập thì lập tức loại bỏ
                        if (long_k.endswith(short_k) or long_k.startswith(short_k)) and (short_k not in SPECIAL_ENTITIES_MAP):
                            suppressed_subkeys.add(short_k)
                            continue

                        is_standalone = (
                            short_k in SPECIAL_ENTITIES_MAP or
                            (any(short_k.startswith(s) for s in CHINESE_SURNAMES) and len(short_k) in [2, 3])
                        )
                        if not is_standalone:
                            suppressed_subkeys.add(short_k)

            for sk in suppressed_subkeys:
                if sk in batch_entities_dict:
                    del batch_entities_dict[sk]

            # 2. PHÂN LOẠI THỰC THỂ THEO ĐÚNG DANH MỤC (CATEGORIZED ENTITIES)
            names_list = []      # Nhân vật, Ngoại hiệu, Danh xưng
            places_list = []     # Địa danh, Sơn trại, Thành trì, Sông núi
            sects_list = []      # Tông môn, Bang phái, Thế lực
            skills_list = []     # Tuyệt kỹ võ công, Chiêu thức, Thần thông
            items_list = []      # Pháp bảo, Binh khí, Đan dược, Đạo cụ
            lore_list = []       # Thuật ngữ thế giới quan, Bối cảnh, Phân kỳ

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
                # Bỏ qua nếu là từ rác hoặc chứa từ ngữ ngữ pháp vô nghĩa
                if c_clean in FORBIDDEN_JUNK_WORDS or any(bw in c_clean for bw in ("日子", "租子", "乱子", "大声", "大不了", "倒是", "按人头")):
                    continue

                entry_line = f"- {c_clean} -> {v_clean}"

                # Phân nhóm chuẩn xác: tránh đẩy thuật ngữ tu luyện / phân kỳ / thời kỳ vào bảng nhân vật
                if c_clean.endswith("期") or c_clean.endswith("时期") or c_clean in ["花石纲"]:
                    lore_list.append(entry_line)
                elif c_clean.startswith("半步") or c_clean in ["法天象地", "超倍化之术"]:
                    skills_list.append(entry_line)
                elif c_clean in ["水泊梁山", "八百里水泊梁山"] or any(t in e_type for t in ["PLACE", "LOCATION"]):
                    places_list.append(entry_line)
                elif "SECT" in e_type:
                    sects_list.append(entry_line)
                elif "SKILL" in e_type:
                    skills_list.append(entry_line)
                elif "ITEM" in e_type:
                    items_list.append(entry_line)
                elif any(t in e_type for t in ["LORE_TERM", "OTHER"]):
                    lore_list.append(entry_line)
                else:
                    names_list.append(entry_line)

            sections = []

            # Bảng Tên riêng cố định (Nhân vật, Địa danh, Tông môn)
            fixed_blocks = []
            if names_list:
                fixed_blocks.append("【1. NHÂN VẬT & NGOẠI HIỆU / DANH XƯNG】:\n" + "\n".join(names_list[:80]))
            if places_list:
                fixed_blocks.append("【2. ĐỊA DANH, SƠN TRẠI & CĂN CỨ】:\n" + "\n".join(places_list[:40]))
            if sects_list:
                fixed_blocks.append("【3. TÔNG MÔN, BANG PHÁI & THẾ LỰC】:\n" + "\n".join(sects_list[:30]))

            if fixed_blocks:
                sections.append(
                    "=== PHẦN 1: BẢNG TÊN RIÊNG & ĐỊA DANH CỐ ĐỊNH (KHÓA NHẤT QUÁN 1-1) ===\n"
                    "(Chỉ áp dụng khi từ đó là tên nhân vật / ngoại hiệu / địa danh / môn phái trong câu)\n\n"
                    + "\n\n".join(fixed_blocks)
                    + "\n\n(LƯU Ý: Khi xuất hiện các nhân vật/ngoại hiệu/địa danh trên, bắt buộc dùng đúng tên tiếng Việt trong bảng, dịch trọn vẹn toàn bộ các chữ sang tiếng Việt có dấu, sạch 100% chữ Hán.)"
                )

            # Bảng Thuật ngữ bản sắc (Võ học, Bảo vật, Thế giới quan)
            lore_blocks = []
            if skills_list:
                lore_blocks.append("【4. VÕ HỌC, TUYỆT KỸ & THẦN THÔNG】:\n" + "\n".join(skills_list[:40]))
            if items_list:
                lore_blocks.append("【5. BẢO VẬT, BINH KHÍ & ĐAN DƯỢC】:\n" + "\n".join(items_list[:30]))
            if lore_list:
                lore_blocks.append("【6. THUẬT NGỮ THẾ GIỚI QUAN & BỐI CẢNH】:\n" + "\n".join(lore_list[:30]))

            if lore_blocks:
                sections.append(
                    "=== PHẦN 2: THUẬT NGỮ THẾ GIỚI QUAN, VÕ HỌC & BẢO VẬT ===\n\n"
                    + "\n\n".join(lore_blocks)
                )

            if sections:
                entity_prompt_block = "\n\n".join(sections)

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

    system_prompt = f"""🔴 VAI TRÒ: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- Ngôn ngữ nguồn: Tiếng Trung (RAW).
- Ngôn ngữ đầu ra: 100% Tiếng Việt hoàn chỉnh, sạch chữ Hán, câu văn trôi chảy chuẩn âm hưởng audiobook.
- Không trả lời câu hỏi hay trò chuyện ngoài lề, chỉ tập trung dịch toàn bộ nội dung.

{context_profile_prompt}
{prev_context_block}
{entity_prompt_block}
{custom_prompt_block}
{erotic_prompt_block}

=== CẤU TRÚC PHÂN CHƯƠNG XML ({chap_count} CHƯƠNG: {chap_list_str}) ===
Dịch đầy đủ lần lượt cả {chap_count} chương: {chap_list_str}.
Mỗi chương bọc trong đúng cặp thẻ XML số chương tương ứng:

<chapter_X>
Chương X: [Tên chương dịch chuẩn Tiếng Việt]

(Nội dung thân truyện đầy đủ của chương X)
</chapter_X>

Quy tắc phân chương:
1. Đối ứng 1:1 chính xác: Mỗi thẻ <chapter_X> trong bản gốc sinh ra đúng một thẻ <chapter_X> tương ứng trong bản dịch, số X trùng khớp 100%. Không gộp chương, không nhảy cóc.
2. Không cắt đôi chương: Trong một chương, dù gặp dấu chấm lửng '……' hay chuyển cảnh, tiếp tục dịch đầy đủ cho đến hết chương rồi mới đóng thẻ </chapter_X>.
3. Tiêu đề: Đứng độc lập ở dòng đầu tiên sau thẻ mở ('Chương X: [Tên chương]'), cách 1 dòng trống rồi mới đến nội dung truyện.
"""

    enable_unblock = kwargs.get("enable_unblock", True)
    if enable_unblock:
        from app.services.unblock.rawt.rawt_pipeline import clear_rawt_trie_cache
        clear_rawt_trie_cache()
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
    if is_single_chapter and len(masked_text) > 52000:
        text_chunks = split_text_into_halves(masked_text)
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
            f"Dưới đây là văn bản chương truyện tiếng Trung cần dịch hoàn toàn sang 100% TIẾNG VIỆT theo đúng Hồ sơ thể loại, Bộ quy tắc chuyển ngữ và Bảng thực thể đã cung cấp:\n\n"
            f"<ngu_lieu_nguon>\n{chunk_text}\n</ngu_lieu_nguon>\n\n"
            f"Yêu cầu thực thi:\n"
            f"1. Dịch thoát ý tự nhiên, mạch lạc, dễ hiểu, chuẩn văn phong dịch thuật tiểu thuyết tiếng Việt.\n"
            f"2. Áp dụng chuẩn xác tên riêng theo Bảng thực thể, bản dịch hoàn toàn bằng tiếng Việt sạch chữ Hán.\n"
            f"3. Dịch đủ từng chương trong {chap_list_str}, mỗi chương bọc trong đúng cặp thẻ XML <chapter_X> tương ứng.{unblock_final_reminder}\n"
        )

        if is_grok_local:
            grok_url = os.environ.get("AIREAD_GROK_URL") or "http://127.0.0.1:8020/translate-text"
            grok_msg = f"🚀 [GROK WEB AUTOMATION] Đang gửi yêu cầu dịch sang Grok Server cổng 8020 (Model: {model})..."
            print(grok_msg)
            try:
                from app.api.translation_router import add_system_log
                add_system_log(grok_msg, "pre")
            except Exception:
                pass

            payload = {
                "text": user_task_prompt,
                "system_instruction": full_system_instruction,
                "timeout": 300.0
            }
            async with httpx.AsyncClient(timeout=360.0) as client:
                res_data = await post_grok_local_with_retry(client, grok_url, payload, timeout=300.0)
            
            trans_text = res_data.get("translated_text", "").strip()
            if not trans_text:
                raise Exception("Grok Local Server không trả về nội dung dịch (kết quả rỗng).")
            translated_parts.append(trans_text)
        elif is_openrouter:
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
                ]
            }
            if custom_temp_str:
                try:
                    payload["temperature"] = float(custom_temp_str)
                except Exception:
                    payload["temperature"] = 0.3
            else:
                payload["temperature"] = 0.3
            if custom_topp_str:
                try:
                    payload["top_p"] = float(custom_topp_str)
                except Exception:
                    pass

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
            gen_config = {}
            if custom_temp_str:
                try:
                    gen_config["temperature"] = float(custom_temp_str)
                except Exception:
                    gen_config["temperature"] = 0.3
            else:
                gen_config["temperature"] = 0.3
            if custom_topp_str:
                try:
                    gen_config["topP"] = float(custom_topp_str)
                except Exception:
                    pass
            if custom_topk_str:
                try:
                    gen_config["topK"] = int(custom_topk_str)
                except Exception:
                    pass

            payload = {
                "system_instruction": {"parts": [{"text": full_system_instruction}]},
                "contents": [{"role": "user", "parts": [{"text": user_task_prompt}]}],
                "safetySettings": safety_settings
            }
            if gen_config:
                payload["generationConfig"] = gen_config

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
            print(f"[LLM-TRANSLATOR DEBUG] Main Call: finishReason={finish_reason}, promptBlock={prompt_block}, candidates_count={len(candidates)}")
            
            # Nếu bị chặn bởi Gemini Safety Policy / RECITATION -> Xóa cache Trie, dọn sạch system prompt và thử lại bằng LLM
            if prompt_block or finish_reason in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK", "OTHER", "RECITATION"] or not candidate.get("content"):
                err_cause = prompt_block or finish_reason or "NO_CONTENT"
                print(f"[LLM-TRANSLATOR] Cảnh báo: Gemini chặn bộ lọc ({err_cause}). Tiến hành tối ưu prompt chuyển ngữ sáng tạo và thử lại...")
                from app.services.unblock.rawt.rawt_pipeline import clear_rawt_trie_cache
                clear_rawt_trie_cache()
                from app.services.unblock.unblock_pipeline import mask_text_with_dictionary
                re_masked_text, extra_mapping, _ = await mask_text_with_dictionary(chunk_text, flow="rawt")
                
                # Khi gặp RECITATION (bộ lọc bản quyền), chỉ tăng nhẹ temperature lên 0.35 để tránh sinh token sai chính tả
                retry_temperature = 0.35 if finish_reason == "RECITATION" else 0.25
                
                # System prompt chuyển thể độc lập sạch sẽ, giữ định dạng XML chapter chuẩn
                clean_system_instruction = f"""🔴 VAI TRÒ & MỆNH LỆNH TỐI CAO: BẠN LÀ MÁY DỊCH TIỂU THUYẾT TRUNG - VIỆT (CHINESE TO VIETNAMESE TRANSLATOR).
- NGÔN NGỮ NGUỒN: TIẾNG TRUNG.
- NGÔN NGỮ ĐÍCH BẮT BUỘC: 100% TIẾNG VIỆT HOÀN CHỈNH (VIETNAMESE ONLY).
Nhiệm vụ: Chuyển ngữ sáng tạo độc lập (Transformative Translation) từ ngữ liệu nghiên cứu sang tác phẩm TIẾNG VIỆT mượt mà, thuần Việt 100%, giàu hình ảnh, đúng nghĩa và bảo toàn 100% cốt truyện nguyên tác. Tuyệt đối không đàm thoại, không trả lời câu hỏi, không xuất tiếng Trung hay tiếng Anh. Tái cấu trúc câu từ tự nhiên cho người Việt, thoát ly sao chép thô cứng. Tuyệt đối không dùng từ Hán-Việt xa lạ, tối nghĩa; tuyệt đối không dịch nghĩa đen từng chữ một cách ngô nghê, sượng sùng; cấm mọi từ ngữ kỳ dị làm suy giảm chất lượng văn học.

=== MỆNH LỆNH BẮT BUỘC ===
1. Cấu trúc phân chương & Tiêu đề chương: Mỗi chương BẮT BUỘC bọc trong cặp thẻ XML:
<chapter_X>
Chương X: [Tên chương dịch chuẩn Tiếng Việt]

(Nội dung thân truyện dịch đầy đủ)
</chapter_X>
Dòng đầu tiên ngay sau thẻ <chapter_X> BẮT BUỘC là: 'Chương X: [Tên chương]' nằm trên 1 dòng độc lập riêng biệt, cách dòng trống với thân truyện. Tuyệt đối không dính tiêu đề chương vào câu văn đầu tiên.
2. Dịch đầy đủ 100% nội dung cốt truyện từ đầu đến câu cuối cùng, không cắt xén tình tiết.{unblock_final_reminder}
3. Tối ưu dấu câu cho TTS: Dùng dấu chuẩn (. , : ! ? ...), câu kết thúc hoặc sau lời thoại BẮT BUỘC dùng dấu chấm đơn (.) trước khi đóng ngoặc kép, dùng hai chấm trước lời thoại (: \\n\\"[Lời thoại]\\"). Tuyệt đối cấm tạo dấu kép lỗi ('..', ',,').
"""
                
                retry_user_prompt = (
                    f"=== NGỮ LIỆU NGHIÊN CỨU VĂN HỌC ĐỐI CHIẾU ===\n{re_masked_text}\n\n"
                    f"=== CHỈ DẪN: Chuyển ngữ sáng tạo và biên soạn lại toàn bộ câu chuyện bằng tiếng Việt văn học tự nhiên, uyển chuyển, bảo toàn 100% tình tiết và ý đồ của ngữ liệu trên, bọc đúng thẻ XML <chapter_X>! ==="
                )
                
                retry_gen_config = dict(gen_config)
                
                retry_payload = {
                    "system_instruction": {"parts": [{"text": clean_system_instruction}]},
                    "contents": [{"role": "user", "parts": [{"text": retry_user_prompt}]}],
                    "generationConfig": retry_gen_config,
                    "safetySettings": safety_settings
                }
                
                async with httpx.AsyncClient(timeout=600.0) as client:
                    retry_resp = await post_gemini_with_retry(client, url, headers, retry_payload)
                
                retry_json = retry_resp.json()
                retry_cands = retry_json.get("candidates", [])
                retry_cand = retry_cands[0] if retry_cands else {}
                retry_prompt_block = retry_json.get("promptFeedback", {}).get("blockReason")
                retry_finish_reason = retry_cand.get("finishReason")
                
                if not retry_prompt_block and retry_finish_reason not in ["SAFETY", "PROHIBITED_CONTENT", "BLOCK", "OTHER", "RECITATION"] and retry_cand.get("content"):
                    candidate = retry_cand
                    mapping_table.update(extra_mapping)
                else:
                    err_blocked = f"❌ [BỊ CHẶN BỞI BỘ LỌC GEMINI ({retry_finish_reason or retry_prompt_block})] Lô Chương {list(chapter_map.values())} bị Gemini chặn bản quyền/safety, không chia nhỏ nội dung."
                    print(f"[LLM-TRANSLATOR] {err_blocked}")
                    raise Exception(err_blocked)

            finish_reason = candidate.get("finishReason")
            chunk_out = candidate["content"]["parts"][0]["text"].strip() if (candidate.get("content") and candidate["content"].get("parts")) else ""

            if finish_reason == "MAX_TOKENS":
                if chunk_out and not is_single_chapter:
                    warn_max_tok = f"⚠️ [LLM-TRANSLATOR] Lô Chương {list(chapter_map.values())} chạm giới hạn MAX_TOKENS của Gemini ở phần cuối (đã tạo {len(chunk_out)} ký tự). Vẫn chuyển sang Hậu xử lý để cứu và lưu các chương đầu đủ thẻ!"
                    print(warn_max_tok)
                    add_system_log(warn_max_tok, "warning")
                elif not chunk_out:
                    err_max_tok = f"❌ [TRÀN TỐI ĐA TOKEN GEMINI] Lô Chương {list(chapter_map.values())} bị ngắt do chạm giới hạn token tối đa nhưng không có nội dung trả về."
                    print(f"[LLM-TRANSLATOR] {err_max_tok}")
                    raise ValueError(err_max_tok)

            translated_parts.append(chunk_out)

    translated_text = "\n\n".join(translated_parts).strip()
    
    # Dọn dẹp vòng lặp suy thoái nếu có
    translated_text = re.sub(r'(\b\w+\b)(?:[\s,.]+\1){5,}', r'\1', translated_text)
    translated_text = re.sub(r'(?i)\b(cổng game|casino|nhà cái|nổ hũ|game slot|pagcor|baccarat|uy tín hơn\. Cụ thể).*', '', translated_text, flags=re.DOTALL)
    # Dọn dẹp các ký tự ngoại lai rò rỉ từ tokenizer đa ngữ (như chữ Thái, Hy Lạp, Cyrillic)
    translated_text = re.sub(r'[\u0e00-\u0e7f\u0370-\u03ff\u0400-\u04ff]', '', translated_text)
    # Chuẩn hóa lỗi gõ lặp nguyên âm có dấu lạ do chập token (như bềề -> bề, lêuu -> lêu)
    translated_text = re.sub(r'([àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ])\1+', r'\1', translated_text)
    # Chuẩn hóa xóa khoảng trắng thừa trước dấu câu (ví dụ: "thao tác ?" -> "thao tác?", "nữa chứ !!!" -> "nữa chứ!!!")
    translated_text = re.sub(r'[ \t]+([,.:;?!…])', r'\1', translated_text)

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

    return {
        "status": "success",
        "translated_text_masked": translated_text,
        "mapping_table": mapping_table,
        "chapter_map": chapter_map,
        "novel_id": novel.id
    }

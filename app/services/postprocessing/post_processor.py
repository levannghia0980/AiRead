import re
import os
from typing import Dict, List, Any, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, Novel, NovelEntity
from app.services.unblock.unblock_pipeline import unmask_text_with_dictionary
from app.services.preprocessing.crawler.google_translator import translate_text_via_google
from app.services.storage.file_storage import sanitize_filename

async def sweep_chinese_characters(text: str) -> str:
    """
    Quét và tự động dịch các Hán tự còn sót lại bằng Google Translate.
    Gạch chân xanh dương để đánh dấu ở Frontend.
    """
    # Regex tìm các cụm Hán tự
    pattern = re.compile(r'([\u4e00-\u9fff]+)')
    
    matches = list(set(pattern.findall(text)))
    if not matches:
        return text
        
    if len(matches) > 50:
        print(f"[POST-PROCESS] Cảnh báo: Tìm thấy {len(matches)} cụm Hán tự (>50), bỏ qua tự động dịch để tránh treo hệ thống.")
        return text
        
    # Sắp xếp chuỗi Hán tự dài trước, ngắn sau để tránh thay thế nhầm cụm con trước cụm cha
    sorted_matches = sorted(matches, key=len, reverse=True)

    for chunk in sorted_matches:
        try:
            # Dịch online
            translated = await translate_text_via_google(chunk)
            if translated and translated != chunk:
                # Bọc thẻ gạch chân xanh kèm data-raw để phục vụ LLM batch fix sau này
                highlighted = f'<span style="text-decoration: underline; text-decoration-color: blue;" class="swept-chinese" data-raw="{chunk}">{translated}</span>'
                # Chỉ thay thế chunk khi không nằm trong thuộc tính HTML data-raw hay style
                text = re.sub(rf'(?<!data-raw=")(?<!style=")(?<!class="){re.escape(chunk)}', highlighted, text)
        except Exception as e:
            print(f"[POST-PROCESS] Lỗi dịch Hán tự '{chunk}': {e}")
            
    return text

def sweep_pinyin_english(text: str) -> str:
    """
    Quét và đánh dấu (Bôi đỏ) các cụm từ tiếng Anh / Pinyin lọt lưới.
    Chỉ quét trong phần Text content (không đụng vào HTML tags / attributes).
    Tạm thời vô hiệu hóa để tránh đánh dấu sai các từ tiếng Việt không dấu (thu, thây, ta, v.v.).
    """
    return text



def fix_broken_words(text: str, protected_names: list = None) -> str:
    """
    Phát hiện và sửa lỗi dính chữ từ LLM output (Gemini):
    - Tách đại từ 'y' dính chữ (VD: yđang → y đang, ngươiy → ngươi y, củay → của y, biếty → biết y)
    - Chữ thường dính chữ HOA giữa câu (VD: nhìnKhiếu → nhìn Khiếu)
    - Dấu câu dính chữ liền sau (VD: rồi.Hắn → rồi. Hắn)
    - Chuẩn hóa khoảng trắng thừa
    - BẢO VỆ tên thực thể (protected_names) không bị tách nhầm
    """
    if not text:
        return text
    
    original_text = text
    
    # === BẢO VỆ TÊN THỰC THỂ: Che giấu trước khi xử lý ===
    name_placeholders = {}
    if protected_names:
        # Sắp xếp dài trước ngắn sau để tránh thay thế con trước cha
        sorted_names = sorted(set(protected_names), key=len, reverse=True)
        for idx, name in enumerate(sorted_names):
            if name and name in text:
                placeholder = f"§PROT_{idx:04d}§"
                text = text.replace(name, placeholder)
                name_placeholders[placeholder] = name
    
    # Tập ký tự tiếng Việt đầy đủ (bao gồm ơƠ, ưƯ, đĐ)
    vn_lower = r'a-zàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộơớờởỡợúùủũụưứừửữựỳýỷỹỵđ'
    vn_upper = r'A-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ'
    vn_all = rf'{vn_lower}{vn_upper}'
    
    # Rule 0a: Sửa triệt để rác tiêu đề chương bị dịch nhầm
    text = re.sub(r'(?i)(?:KHÔNG|NO)\s*\.?\s*(\d+)\s*(?:chương|Chương|章)?\s*[:.:-]?\s*', r'Chương \1: ', text)
    text = re.sub(r'第\s*(\d+)\s*章\s*[:.:-]?\s*', r'Chương \1: ', text)
    text = re.sub(r'(?i)(?:Chương\s*(\d+)\s*:\s*){2,}', r'Chương \1: ', text)

    # Rule 0b: Sửa triệt để lỗi tách rời chữ 'y' (VD: vẫ y -> vẫy, lấ y -> lấy, đâ y -> đây, giâ y -> giây)
    text = re.sub(rf'(?<=[{vn_all}])\s+(y)\b', r'\1', text)



    # Rule 1a: Chữ thường tiếng Việt dính chữ HOA giữa từ → tách ra (VD: nhìnKhiếu → nhìn Khiếu)
    text = re.sub(f'([{vn_lower}])([{vn_upper}])', r'\1 \2', text)
    
    # Rule 1b: Tách khoảng trắng bị dính xung quanh thẻ HTML <span>
    text = re.sub(f'([{vn_all}])<span', r'\1 <span', text)
    text = re.sub(f'</span>([{vn_all}])', r'</span> \1', text)

    # Rule 1c: Sửa lỗi lặp chữ HOA đầu từ
    text = re.sub(rf'\b([{vn_upper}])\1+([{vn_upper}][{vn_lower}]+)', r'\1\2', text)
    text = re.sub(rf'\b([{vn_upper}])\1+([{vn_lower}]+)', r'\1\2', text)

    # Rule 2: Dấu câu dính chữ HOA (thiếu khoảng trắng sau dấu câu)
    text = re.sub(f'([.!?;:,])([{vn_upper}])', r'\1 \2', text)
    
    # Rule 3: Chuẩn hóa khoảng trắng thừa (2+ spaces → 1 space)
    text = re.sub(r' {2,}', ' ', text)
    
    # Rule 4: Loại bỏ khoảng trắng thừa trước dấu câu
    text = re.sub(r' +([.!?;:,])', r'\1', text)
    
    # === KHÔI PHỤC TÊN THỰC THỂ ĐÃ BẢO VỆ ===
    for placeholder, original_name in name_placeholders.items():
        text = text.replace(placeholder, original_name)
    
    if text != original_text:
        print("[POST-PROCESS] 🔧 fix_broken_words: Đã tự động chuẩn hóa dính chữ & khoảng trắng.")
    
    return text


async def enforce_entity_names(text: str, novel_id: int) -> str:
    """
    Lưới an toàn cuối cùng: Quét Hán tự còn sót trong bản dịch,
    nếu khớp entity trong DB → thay bằng tên Việt chuẩn.
    Đây là bước bắt lỗi cho trường hợp Gemini bỏ sót không dịch một số tên.
    """
    if not text:
        return text
    
    # Kiểm tra nhanh xem có Hán tự không
    han_pattern = re.compile(r'[\u4e00-\u9fff]+')
    if not han_pattern.search(text):
        return text
    
    async with AsyncSessionLocal() as session:
        stmt = select(NovelEntity).where(
            NovelEntity.novel_id == novel_id,
            NovelEntity.entity_type != "CORRECTION"
        )
        res = await session.execute(stmt)
        entities = res.scalars().all()
    
    if not entities:
        return text
    
    original_text = text
    replaced_count = 0
    
    # Sắp xếp dài trước ngắn sau để tránh thay thế con trước cha
    for e in sorted(entities, key=lambda x: len(x.chinese_name or ""), reverse=True):
        if e.chinese_name and e.rough_translation and e.chinese_name in text:
            text = text.replace(e.chinese_name, e.rough_translation)
            replaced_count += 1
    
    if replaced_count > 0:
        print(f"[POST-PROCESS] 🛡️ enforce_entity_names: Đã thay thế {replaced_count} tên Hán tự sót lại bằng tên Việt chuẩn từ DB.")
    
    return text

def extract_chapter_text(full_text: str, cid: int, next_cid: int = None, chap_no: int = None, next_chap_no: int = None) -> Optional[str]:
    """
    Trích xuất nội dung chương cực kỳ bền bỉ (robust), chịu lỗi tốt.
    CHỈ dùng chapter_no (số chương) để tìm thẻ phân tách — KHÔNG dùng cid (DB ID)
    vì LLM chỉ biết số chương, không biết ID trong database.
    """
    if not full_text or not full_text.strip():
        return None

    ids_to_try = []
    if chap_no is not None:
        ids_to_try.extend([str(chap_no), f"{chap_no:02d}", f"{chap_no:03d}", f"{chap_no:04d}"])
    if not ids_to_try:
        # Fallback cuối: chỉ khi không có chap_no mới dùng cid
        ids_to_try.append(str(cid))

    def clean_extracted(t: str) -> str:
        if not t: return t
        raw_pattern = re.compile(r"(?:===\s*)?(?:\[|\()?RAW_CHAPTER", re.IGNORECASE)
        rmatch = raw_pattern.search(t)
        if rmatch:
            t = t[:rmatch.start()]
        # Loại bỏ các thẻ tag BEGIN/END sót lại ở đầu hoặc cuối
        t = re.sub(
            r"^\s*(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
            "", t, flags=re.IGNORECASE
        ).strip()
        t = re.sub(
            r"(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[^\n\]\)]*(?:\]|\))?(?:\s*===)?\s*$",
            "", t, flags=re.IGNORECASE
        ).strip()
        return t.strip()

    for target_id in ids_to_try:
        # 1. Matching BEGIN tag và END tag mềm dẻo (BẮT BUỘC có target_id ở cả 2 thẻ để tránh khớp nhầm chữ 'kết thúc' trong lời thoại/văn bản)
        pattern_pair = re.compile(
            rf"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?(.*?)(?:===\s*)?(?:\[|\()? \s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
            re.DOTALL | re.IGNORECASE
        )
        match = pattern_pair.search(full_text)
        if match and len(match.group(1).strip()) > 20:
            return clean_extracted(match.group(1))

        # 2. Match từ BEGIN tag của target_id tới BEGIN tag của chương kế tiếp
        next_ids_to_try = []
        if next_chap_no is not None:
            next_ids_to_try.extend([str(next_chap_no), f"{next_chap_no:02d}", f"{next_chap_no:03d}"])

        begin_pattern = re.compile(
            rf"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
            re.IGNORECASE
        )
        begin_match = begin_pattern.search(full_text)
        if begin_match:
            start_idx = begin_match.end()
            for nid in next_ids_to_try:
                next_pattern = re.compile(
                    rf"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{nid}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
                    re.IGNORECASE
                )
                next_match = next_pattern.search(full_text, pos=start_idx)
                if next_match:
                    end_idx = next_match.start()
                    extracted = clean_extracted(full_text[start_idx:end_idx])
                    if len(extracted) > 20:
                        return extracted

            # Nếu là chương cuối lô, lấy đến thẻ KẾT THÚC CHƯƠNG {target_id} hoặc hết text
            remaining = full_text[start_idx:]
            end_tag_pattern = re.compile(
                rf"(?:===\s*)?(?:\[|\()? \s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?.*",
                re.IGNORECASE | re.DOTALL
            )
            remaining = end_tag_pattern.sub("", remaining)
            extracted = clean_extracted(remaining)
            if len(extracted) > 20:
                return extracted

        # 3. Match theo Header "Chương 37: ..." hoặc "Chương 195: ..." nếu LLM quên tag BEGIN_CHAPTER
        heading_pattern = re.compile(
            rf"^(?:\s*===\s*)?(?:Chương|CHAPTER)\s*{target_id}\b[^\n]*\n",
            re.MULTILINE | re.IGNORECASE
        )
        hmatch = heading_pattern.search(full_text)
        if hmatch:
            start_idx = hmatch.start()
            next_h_matched = False
            for nid in next_ids_to_try:
                next_h_pattern = re.compile(
                    rf"^(?:\s*===\s*)?(?:Chương|CHAPTER)\s*{nid}\b[^\n]*\n",
                    re.MULTILINE | re.IGNORECASE
                )
                next_hmatch = next_h_pattern.search(full_text, pos=hmatch.end())
                if next_hmatch:
                    end_idx = next_hmatch.start()
                    extracted = clean_extracted(full_text[start_idx:end_idx])
                    if len(extracted) > 20:
                        return extracted
                    next_h_matched = True
                    break
            if not next_h_matched:
                extracted = clean_extracted(full_text[start_idx:])
                if len(extracted) > 20:
                    return extracted

    return None

async def process_and_split_batch(
    novel_id: int, 
    translated_text_masked: str, 
    mapping_table: Dict[str, Dict[str, str]], 
    chapter_map: Dict[int, int],
    version_type: str
):
    """
    Hậu xử lý toàn bộ:
    1. Unmask (Giải mã từ nhạy cảm)
    2. Split (Tách chương) với đa tầng Fallback siêu bền bỉ
    3. Sweep Chinese (Dịch Hán tự sót)
    4. Sweep Pinyin (Bôi đỏ tiếng Anh/Pinyin)
    5. Lưu vào file và cập nhật DB.
    """
    # 1. Unmask
    print("[POST-PROCESS] Đang giải mã các từ nhạy cảm (Unmasking)...")
    full_text = unmask_text_with_dictionary(translated_text_masked, mapping_table)
    
    # Khởi tạo thư mục
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        
    # Lưu kết quả vào 04_KetQua
    base_dir = r"D:\NENGHIA0980\AIREAD\Output\04_KetQua"
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_dir, novel_folder, "chapters")
    os.makedirs(out_dir, exist_ok=True)
    
    # Lưu output LLM gốc ra file debug để kiểm tra khi có lỗi
    debug_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\03_DichAI_LLM", novel_folder)
    os.makedirs(debug_dir, exist_ok=True)
    batch_label = "_".join([str(v) for v in chapter_map.values()])
    debug_file = os.path.join(debug_dir, f"batch_ch{batch_label}.txt")
    try:
        with open(debug_file, "w", encoding="utf-8") as df:
            df.write(f"=== LLM OUTPUT (sau unmask) — Chương {list(chapter_map.values())} ===\n\n")
            df.write(full_text)
        print(f"[POST-PROCESS] 💾 Đã lưu LLM output debug: {debug_file}")
    except Exception as dbg_err:
        print(f"[POST-PROCESS] ⚠️ Không lưu được debug file: {dbg_err}")
    
    saved_files = []
    
    try:
        async with AsyncSessionLocal() as session:
            cids = list(chapter_map.keys())
            extracted_map: Dict[int, str] = {}
            
            # Tạo map ngược để log: cid -> chap_no
            chap_nos_in_batch = [chapter_map[c] for c in cids]
            print(f"[POST-PROCESS] 📋 Bắt đầu tách {len(cids)} chương: {chap_nos_in_batch}")
            
            # Bước 2a: Thử bóc tách chuẩn / mềm dẻo cho từng chương
            for idx, cid in enumerate(cids):
                chap_no = chapter_map[cid]
                next_cid = cids[idx + 1] if idx + 1 < len(cids) else None
                next_chap_no = chapter_map[next_cid] if next_cid in chapter_map else None
                chap_text = extract_chapter_text(full_text, cid, next_cid, chap_no, next_chap_no)
                if chap_text:
                    extracted_map[cid] = chap_text
                    print(f"[POST-PROCESS] ✅ Tách thành công Chương {chap_no} ({len(chap_text)} ký tự)")
                else:
                    print(f"[POST-PROCESS] ⚠️ Không tìm thấy thẻ phân tách cho Chương {chap_no}")

            # Bước 2b: Fallback khôi phục các chương bị thiếu tag
            missing_cids = [cid for cid in cids if cid not in extracted_map]
            
            if missing_cids:
                missing_nos = [chapter_map[c] for c in missing_cids]
                print(f"[POST-PROCESS] ⚠️ Phát hiện {len(missing_cids)} chương bị thiếu thẻ phân tách: Chương {missing_nos}. Đang khôi phục...")
                
                # Fallback Tier 1: Nếu lô 1 chương mà không thấy tag
                if len(cids) == 1 and full_text and len(full_text.strip()) > 20:
                    cid = cids[0]
                    chap_no = chapter_map[cid]
                    print(f"[POST-PROCESS] 💡 Lô 1 chương không tìm thấy thẻ phân tách, tự động lấy toàn bộ nội dung dịch cho chương {chap_no}.")
                    clean_t = re.sub(r"^(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", "", full_text.strip(), flags=re.IGNORECASE).strip()
                    clean_t = re.sub(r"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER)[^\n\]\)]*(?:\]|\))?(?:\s*===)?$", "", clean_t, flags=re.IGNORECASE).strip()
                    extracted_map[cid] = clean_t
                
                # Fallback Tier 2: Gap Extraction
                for idx, cid in enumerate(cids):
                    if cid in extracted_map:
                        continue
                    chap_no = chapter_map[cid]
                    
                    prev_cid = None
                    for p_idx in range(idx - 1, -1, -1):
                        if cids[p_idx] in extracted_map:
                            prev_cid = cids[p_idx]
                            break
                            
                    next_cid_idx = None
                    for n_idx in range(idx + 1, len(cids)):
                        if cids[n_idx] in extracted_map:
                            next_cid_idx = cids[n_idx]
                            break
                            
                    if prev_cid is not None and extracted_map.get(prev_cid):
                        prev_text = extracted_map[prev_cid]
                        pos_prev = full_text.find(prev_text[:50])
                        if pos_prev != -1:
                            start_gap = pos_prev + len(prev_text)
                            if next_cid_idx is not None and extracted_map.get(next_cid_idx):
                                next_text = extracted_map[next_cid_idx]
                                pos_next = full_text.find(next_text[:50], start_gap)
                                end_gap = pos_next if pos_next != -1 else len(full_text)
                            else:
                                end_gap = len(full_text)
                                
                            gap_content = full_text[start_gap:end_gap].strip()
                            gap_content = re.sub(r"^(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER|BEGIN|END)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", "", gap_content, flags=re.IGNORECASE).strip()
                            gap_content = re.sub(r"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER|BEGIN|END)[^\n\]\)]*(?:\]|\))?(?:\s*===)?$", "", gap_content, flags=re.IGNORECASE).strip()
                            
                            if len(gap_content) > 20:
                                print(f"[POST-PROCESS] 💡 Khôi phục thành công Chương {chap_no} từ khoảng trống giữa các chương trong lô.")
                                extracted_map[cid] = gap_content

            # Fallback Tier 4: Dịch lẻ chương bị thiếu HOẶC bị xén ngắn bất thường
            # ĐẶT NGOÀI if missing_cids để bắt cả chương đã tách nhưng output quá ngắn
            async with AsyncSessionLocal() as raw_session:
                short_cids = []
                for cid in cids:
                    chap_no = chapter_map[cid]
                    chap_text = extracted_map.get(cid, "").strip()
                    
                    # Kiểm tra: thiếu hoàn toàn hoặc quá ngắn so với RAW
                    if not chap_text or len(chap_text) < 100:
                        short_cids.append(cid)
                        continue
                    
                    # So sánh với RAW để phát hiện bị xén
                    stmt_raw = select(ChapterVersion).where(
                        ChapterVersion.chapter_id == cid,
                        ChapterVersion.version_type == "RAW"
                    )
                    res_raw = await raw_session.execute(stmt_raw)
                    ver_raw = res_raw.scalar_one_or_none()
                    if ver_raw:
                        raw_len = len((ver_raw.content or "").strip()) if ver_raw.content else 0
                        if not raw_len and ver_raw.file_path and os.path.exists(ver_raw.file_path):
                            try:
                                with open(ver_raw.file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    raw_len = len(f.read().strip())
                            except Exception:
                                pass
                        if raw_len > 800 and len(chap_text) < raw_len * 0.3:
                            short_cids.append(cid)
                            print(f"[POST-PROCESS] ⚠️ Chương {chap_no} bị xén ngắn bất thường (RAW={raw_len}, Output={len(chap_text)})")
                
                for cid in short_cids:
                    chap_no = chapter_map[cid]
                    print(f"[POST-PROCESS] 🔄 Chương {chap_no} bị thiếu/xén chữ. Tự động dịch lẻ để đảm bảo đầy đủ...")
                    try:
                        if version_type == "LLM":
                            from app.services.translation.rawt.llm_translator import translate_batch_llm
                            single_res = await translate_batch_llm([cid])
                        else:
                            from app.services.translation.contextt.llm_context_editor import edit_context_batch_llm
                            single_res = await edit_context_batch_llm([cid])
                            
                        if single_res and single_res.get("status") == "success":
                            single_masked = single_res["translated_text_masked"]
                            single_table = single_res.get("mapping_table", {})
                            single_full = unmask_text_with_dictionary(single_masked, single_table) if single_table else single_masked
                            clean_single = re.sub(r"(?:===\s*)?(?:\[|\()?\s*(?:BEGIN_CHAPTER|END_CHAPTER|BEGIN|END)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", "", single_full, flags=re.IGNORECASE).strip()
                            if len(clean_single) > 50:
                                extracted_map[cid] = clean_single
                                full_text = full_text + "\n" + single_full
                                print(f"[POST-PROCESS] ✅ Cứu hộ dịch lẻ thành công Chương {chap_no}! ({len(clean_single)} ký tự)")
                            else:
                                print(f"[POST-PROCESS] ⚠️ Dịch lẻ Chương {chap_no} vẫn quá ngắn ({len(clean_single)} ký tự)")
                    except Exception as ex_single:
                        print(f"[POST-PROCESS] ❌ Lỗi cứu hộ dịch Chương {chap_no}: {ex_single}")

            # Bước 3: Kiểm tra NGHIÊM NGẶT — Mỗi chương PHẢI có CẢ thẻ BẮT ĐẦU lẫn KẾT THÚC
            # Một chương hoàn chỉnh = có thẻ BẮT ĐẦU + nội dung + thẻ KẾT THÚC
            async with AsyncSessionLocal() as session:
                for idx, cid in enumerate(cids):
                    chap_no = chapter_map[cid]
                    chap_text = extracted_map.get(cid, "").strip()
                    
                    # 3a. Kiểm tra thẻ BẮT ĐẦU CHƯƠNG trong LLM output
                    begin_tag_pattern = re.compile(
                        rf"(?:===\s*)?\[\s*(?:BEGIN_CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\s+{chap_no}\s*\](?:\s*===)?",
                        re.IGNORECASE
                    )
                    has_begin_tag = bool(begin_tag_pattern.search(full_text))
                    
                    # 3b. Kiểm tra thẻ KẾT THÚC CHƯƠNG trong LLM output
                    end_tag_pattern = re.compile(
                        rf"(?:===\s*)?\[\s*(?:END_CHAPTER|KẾT\s+THÚC\s+CHƯƠNG)\s+{chap_no}\s*\](?:\s*===)?",
                        re.IGNORECASE
                    )
                    has_end_tag = bool(end_tag_pattern.search(full_text))

                    # 3c. Lấy độ dài RAW đầu vào để so sánh tỷ lệ
                    stmt_raw = select(ChapterVersion).where(
                        ChapterVersion.chapter_id == cid,
                        ChapterVersion.version_type == "RAW"
                    )
                    res_raw = await session.execute(stmt_raw)
                    ver_raw = res_raw.scalar_one_or_none()
                    raw_len = 0
                    if ver_raw:
                        if ver_raw.content:
                            raw_len = len(ver_raw.content.strip())
                        elif ver_raw.file_path and os.path.exists(ver_raw.file_path):
                            try:
                                with open(ver_raw.file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    raw_len = len(f.read().strip())
                            except Exception:
                                pass

                    out_len = len(chap_text)
                    
                    # 3d. Kiểm tra tỷ lệ đầu ra / đầu vào bất thường (< 30% so với RAW)
                    is_too_short = (raw_len > 800 and out_len < raw_len * 0.3)
                    
                    # Log trạng thái kiểm tra từng chương
                    tag_status = f"BEGIN={'✅' if has_begin_tag else '❌'} END={'✅' if has_end_tag else '❌'}"
                    len_status = f"RAW={raw_len} → Output={out_len}"
                    print(f"[POST-PROCESS] 🔍 Kiểm tra Chương {chap_no}: {tag_status} | {len_status}")
                    
                    # NGHIÊM NGẶT: Phải có CẢ 2 thẻ BẮT ĐẦU + KẾT THÚC, không bị xén ngắn
                    if not chap_text or not has_begin_tag or not has_end_tag or is_too_short:
                        reason = []
                        if not has_begin_tag:
                            reason.append("thiếu thẻ BẮT ĐẦU CHƯƠNG")
                        if not has_end_tag:
                            reason.append("thiếu thẻ KẾT THÚC CHƯƠNG")
                        if is_too_short:
                            reason.append(f"đầu ra bị xén ngắn (RAW: {raw_len} ký tự, Output: {out_len} ký tự)")
                        if not chap_text:
                            reason.append("không trích xuất được nội dung")
                            
                        reason_str = ", ".join(reason)
                        err_msg = (
                            f"❌ [CHƯƠNG KHÔNG HOÀN CHỈNH] Chương {chap_no} vi phạm: {reason_str}. "
                            f"HỦY BỎ TOÀN BỘ LÔ (Chương {chap_nos_in_batch}), XÓA SẠCH DỮ LIỆU DỞ DANG VÀ DỊCH LẠI!"
                        )
                        print(err_msg)
                        raise ValueError(err_msg)

            # Bước 4: Hậu xử lý từng nội dung và Lưu DB
            # Lấy danh sách tên thực thể Tiếng Việt để bảo vệ không bị tách nhầm
            protected_names = []
            async with AsyncSessionLocal() as name_session:
                stmt_ents = select(NovelEntity).where(NovelEntity.novel_id == novel_id)
                res_ents = await name_session.execute(stmt_ents)
                all_entities = res_ents.scalars().all()
                for ent in all_entities:
                    if ent.rough_translation:
                        protected_names.append(ent.rough_translation)

            for cid in cids:
                chap_no = chapter_map[cid]
                print(f"[POST-PROCESS] Đang xử lý hoàn thiện chương {chap_no}...")
                chap_text = extracted_map[cid]

                # 3a. Sweep Chinese
                chap_text = await sweep_chinese_characters(chap_text)
                
                # 3b. Fix broken words (dính chữ từ LLM output) — có bảo vệ tên thực thể
                chap_text = fix_broken_words(chap_text, protected_names=protected_names)
                
                # 3c. Enforce entity names (lưới an toàn cuối cùng)
                chap_text = await enforce_entity_names(chap_text, novel_id)
                
                # 4. Sweep Pinyin
                chap_text = sweep_pinyin_english(chap_text)
                
                # 5. Lưu file
                file_name = f"{chap_no:06d}.txt"
                file_path = os.path.join(out_dir, file_name)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(chap_text)
                    
                saved_files.append(file_path)
                
                # Cập nhật DB (version_type = FINAL)
                stmt_ver = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == cid, 
                    ChapterVersion.version_type == "FINAL"
                )
                res_ver = await session.execute(stmt_ver)
                ver = res_ver.scalar_one_or_none()
                if ver:
                    ver.file_path = file_path
                    ver.content = chap_text
                else:
                    session.add(ChapterVersion(
                        chapter_id=cid, 
                        version_type="FINAL", 
                        file_path=file_path, 
                        content=chap_text
                    ))
                    
                # Update status
                stmt_chap = select(Chapter).where(Chapter.id == cid)
                res_chap = await session.execute(stmt_chap)
                chap = res_chap.scalar_one_or_none()
                if chap:
                    chap.status = "FINAL_DONE"

                # Xóa cache tệp Audio cũ của chương (nếu có) để ép lần tạo Audio tới phải đọc văn bản mới
                try:
                    mp3_cache_path = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS", novel_folder, "chapters", f"{chap_no:06d}.mp3")
                    if os.path.exists(mp3_cache_path):
                        os.remove(mp3_cache_path)
                        print(f"[POST-PROCESS] 🧹 Đã xóa cache Audio cũ của chương {chap_no}.")
                except Exception:
                    pass

            await session.commit()
    except Exception as e:
        for fp in saved_files:
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                    print(f"[POST-PROCESS CLEANUP] Đã xóa file ghi dở do lỗi: {fp}")
                except Exception as ex:
                    print(f"[POST-PROCESS CLEANUP] Lỗi xóa file {fp}: {ex}")
        raise e
        
    print(f"[POST-PROCESS] Hoàn tất Hậu xử lý cho {len(saved_files)} chương.")
    
    # 6. Tổng hợp file truyện hoàn chỉnh (Full TXT)
    exp_res = await export_full_novel_txt(novel_id)
    full_novel_path = exp_res.get("file_path", "") if isinstance(exp_res, dict) else str(exp_res)
    print(f"[POST-PROCESS] Đã xuất file truyện hoàn chỉnh: {full_novel_path}")
    
    return saved_files


async def export_full_novel_txt(novel_id: int) -> Dict[str, Any]:
    """
    Tổng hợp toàn bộ các chương đã xử lý xong (FINAL) thành một file .txt truyện hoàn chỉnh.
    Ưu tiên đọc trực tiếp từ DB (ver.content) để truy xuất siêu tốc!
    """
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        if not novel:
            return {}
            
        novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
        base_dir = r"D:\NENGHIA0980\AIREAD\Output\04_KetQua"
        out_dir = os.path.join(base_dir, novel_folder)
        os.makedirs(out_dir, exist_ok=True)
        
        full_file_path = os.path.join(out_dir, f"{novel_folder}_Full.txt")
        
        # Lấy tất cả các chương theo thứ tự
        stmt_chaps = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
        res_chaps = await session.execute(stmt_chaps)
        chapters = res_chaps.scalars().all()
        
        with open(full_file_path, "w", encoding="utf-8") as out_f:
            out_f.write(f"=== {novel.title_rough or novel.title_raw} ===\n")
            out_f.write(f"Tác giả: {novel.author}\n\n")
            
            for chap in chapters:
                stmt_ver = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == chap.id,
                    ChapterVersion.version_type == "FINAL"
                )
                res_ver = await session.execute(stmt_ver)
                ver = res_ver.scalar_one_or_none()
                
                if ver:
                    out_f.write(f"\n--- CHƯƠNG {chap.chapter_no}: {chap.title_rough or chap.title_raw} ---\n\n")
                    if ver.content:
                        out_f.write(ver.content.strip())
                    elif ver.file_path and os.path.exists(ver.file_path):
                        with open(ver.file_path, "r", encoding="utf-8", errors="ignore") as in_f:
                            out_f.write(in_f.read().strip())
                    out_f.write("\n\n")
                    
        return {
            "file_path": full_file_path,
            "title": novel.title_rough or novel.title_raw
        }

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
        
    for chunk in matches:
        try:
            # Dịch online
            translated = await translate_text_via_google(chunk)
            if translated and translated != chunk:
                # Bọc thẻ gạch chân xanh kèm data-raw để phục vụ LLM batch fix sau này
                highlighted = f'<span style="text-decoration: underline; text-decoration-color: blue;" class="swept-chinese" data-raw="{chunk}">{translated}</span>'
                text = text.replace(chunk, highlighted)
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


def fix_broken_words(text: str) -> str:
    """
    Phát hiện và sửa lỗi dính chữ từ LLM output (Gemini):
    - Chữ thường dính chữ HOA giữa câu (VD: nhìnKhiếu → nhìn Khiếu)
    - Dấu câu dính chữ liền sau (VD: rồi.Hắn → rồi. Hắn)
    - Chuẩn hóa khoảng trắng thừa
    """
    if not text:
        return text
    
    original_text = text
    
    # Tập ký tự tiếng Việt thường và HOA chuẩn xác (tránh lỗi range 'z-à' trong regex)
    vn_lower = r'a-zàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựỳýỷỹỵ'
    vn_upper = r'A-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰỲÝỶỸỴ'
    
    # Rule 0a: Sửa lỗi tiêu đề chương bị Gemini dịch nhầm "NO.1章" / "第1章" thành "KHÔNG.1chương" hoặc "KHÔNG.1"
    text = re.sub(r'(?i)\bKHÔNG\.?\s*(\d+)\s*chương\b', r'Chương \1', text)
    text = re.sub(r'(?i)\bKHÔNG\.?\s*(\d+)\b', r'Chương \1', text)

    

    # Rule 1a: Chữ thường tiếng Việt dính chữ HOA giữa từ → tách ra
    # "nhìnKhiếu" → "nhìn Khiếu", "độcSữa" → "độc Sữa", "nảyMật" → "nảy Mật"
    text = re.sub(
        f'([{vn_lower}])([{vn_upper}])',
        r'\1 \2',
        text
    )
    
    # Rule 1b: Tách khoảng trắng bị dính xung quanh thẻ HTML <span>
    text = re.sub(f'([{vn_lower}{vn_upper}])<span', r'\1 <span', text)
    text = re.sub(f'</span>([{vn_lower}{vn_upper}])', r'</span> \1', text)

    # Rule 1c: Sửa lỗi lặp chữ HOA đầu từ do LLM/Trans ghép lỗi (VD: CCác → Các, TTrang → Trang, SựCCác → Sự Các)
    text = re.sub(rf'\b([{vn_upper}])\1+([{vn_upper}][{vn_lower}]+)', r'\1\2', text)
    text = re.sub(rf'\b([{vn_upper}])\1+([{vn_lower}]+)', r'\1\2', text)

    # Rule 2: Dấu câu dính chữ HOA (thiếu khoảng trắng sau dấu câu)
    # "rồi.Hắn" → "rồi. Hắn", "đi!Ngươi" → "đi! Ngươi"
    text = re.sub(
        f'([.!?;:,])([{vn_upper}])',
        r'\1 \2',
        text
    )
    
    # Rule 3: Chuẩn hóa khoảng trắng thừa (2+ spaces → 1 space)
    text = re.sub(r' {2,}', ' ', text)
    
    # Rule 4: Loại bỏ khoảng trắng thừa trước dấu câu
    text = re.sub(r' +([.!?;:,])', r'\1', text)
    
    if text != original_text:
        fixes = sum(1 for a, b in zip(original_text, text) if a != b)
        print(f"[POST-PROCESS] 🔧 fix_broken_words: Đã tự động sửa ~{fixes} ký tự dính/thừa/rác.")
    
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
    Trích xuất nội dung chương cực kỳ bền bỉ (robust), chịu lỗi tốt:
    Thử lần lượt với cả Chapter ID (cid) lẫn Chapter No (chap_no)
    """
    if not full_text or not full_text.strip():
        return None

    ids_to_try = [str(cid)]
    if chap_no is not None:
        ids_to_try.append(str(chap_no))
        ids_to_try.append(f"{chap_no:02d}")
        ids_to_try.append(f"{chap_no:03d}")
        ids_to_try.append(f"{chap_no:04d}")

    def clean_extracted(t: str) -> str:
        if not t: return t
        raw_pattern = re.compile(r"(?:===\s*)?(?:\[|\()?RAW_CHAPTER", re.IGNORECASE)
        rmatch = raw_pattern.search(t)
        if rmatch:
            t = t[:rmatch.start()]
        # Loại bỏ các thẻ tag BEGIN/END sót lại ở đầu hoặc cuối
        t = re.sub(
            r"^(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU|KẾT\s+THÚC)[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
            "", t, flags=re.IGNORECASE
        ).strip()
        t = re.sub(
            r"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU|KẾT\s+THÚC)[^\n\]\)]*(?:\]|\))?(?:\s*===)?$",
            "", t, flags=re.IGNORECASE
        ).strip()
        return t.strip()

    for target_id in ids_to_try:
        # 1. Matching BEGIN tag và END tag mềm dẻo
        pattern_pair = re.compile(
            rf"(?:===\s*)?(?:\[|\(|\b)?\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\)|\b)?(?:\s*===)?(.*?)(?:===\s*)?(?:\[|\(|\b)?\s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*(?:{target_id})?\b[^\n\]\)]*(?:\]|\)|\b)?(?:\s*===)?",
            re.DOTALL | re.IGNORECASE
        )
        match = pattern_pair.search(full_text)
        if match and len(match.group(1).strip()) > 20:
            return clean_extracted(match.group(1))

        # 2. Match từ BEGIN tag của target_id tới BEGIN tag của chương kế tiếp
        next_ids_to_try = []
        if next_cid is not None:
            next_ids_to_try.append(str(next_cid))
        if next_chap_no is not None:
            next_ids_to_try.extend([str(next_chap_no), f"{next_chap_no:02d}", f"{next_chap_no:03d}"])

        begin_pattern = re.compile(
            rf"(?:===\s*)?(?:\[|\(|\b)?\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\)|\b)?(?:\s*===)?",
            re.IGNORECASE
        )
        begin_match = begin_pattern.search(full_text)
        if begin_match:
            start_idx = begin_match.end()
            for nid in next_ids_to_try:
                next_pattern = re.compile(
                    rf"(?:===\s*)?(?:\[|\(|\b)?\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{nid}\b[^\n\]\)]*(?:\]|\)|\b)?(?:\s*===)?",
                    re.IGNORECASE
                )
                next_match = next_pattern.search(full_text, pos=start_idx)
                if next_match:
                    end_idx = next_match.start()
                    extracted = clean_extracted(full_text[start_idx:end_idx])
                    if len(extracted) > 20:
                        return extracted

            # Nếu là chương cuối lô, lấy đến hết text
            remaining = full_text[start_idx:]
            end_tag_pattern = re.compile(
                rf"(?:===\s*)?(?:\[|\()? \s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[^\n\]\)]*(?:\]|\))?(?:\s*===)?.*",
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
    
    saved_files = []
    
    try:
        async with AsyncSessionLocal() as session:
            cids = list(chapter_map.keys())
            extracted_map: Dict[int, str] = {}
            
            # Bước 2a: Thử bóc tách chuẩn / mềm dẻo cho từng chương
            for idx, cid in enumerate(cids):
                chap_no = chapter_map[cid]
                next_cid = cids[idx + 1] if idx + 1 < len(cids) else None
                next_chap_no = chapter_map[next_cid] if next_cid in chapter_map else None
                chap_text = extract_chapter_text(full_text, cid, next_cid, chap_no, next_chap_no)
                if chap_text:
                    extracted_map[cid] = chap_text

            # Bước 2b: Fallback khôi phục các chương bị thiếu tag (Multi-tier Fallbacks)
            missing_cids = [cid for cid in cids if cid not in extracted_map]
            
            if missing_cids:
                print(f"[POST-PROCESS] ⚠️ Phát hiện {len(missing_cids)} chương bị thiếu/lỗi thẻ phân tách: {[chapter_map[c] for c in missing_cids]}. Đang tiến hành khôi phục đa tầng...")
                
                # Fallback Tier 1: Nếu lô 1 chương mà không thấy tag
                if len(cids) == 1 and full_text and len(full_text.strip()) > 20:
                    cid = cids[0]
                    chap_no = chapter_map[cid]
                    print(f"[POST-PROCESS] 💡 Lô 1 chương không tìm thấy thẻ phân tách, tự động lấy toàn bộ nội dung dịch cho chương {chap_no}.")
                    clean_t = re.sub(r"^(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", "", full_text.strip(), flags=re.IGNORECASE).strip()
                    clean_t = re.sub(r"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER)[^\n\]\)]*(?:\]|\))?(?:\s*===)?$", "", clean_t, flags=re.IGNORECASE).strip()
                    extracted_map[cid] = clean_t
                
                # Fallback Tier 2: Gap Extraction (Khoảng trống giữa chương trước và chương sau đã được xác định)
                for idx, cid in enumerate(cids):
                    if cid in extracted_map:
                        continue
                    chap_no = chapter_map[cid]
                    
                    # Tìm chương liền trước đã trích xuất thành công
                    prev_cid = None
                    for p_idx in range(idx - 1, -1, -1):
                        if cids[p_idx] in extracted_map:
                            prev_cid = cids[p_idx]
                            break
                            
                    # Tìm chương liền sau đã trích xuất thành công
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
                                print(f"[POST-PROCESS] 💡 Khôi phục thành công chương {chap_no} (ID {cid}) từ khoảng trống giữa các chương trong lô.")
                                extracted_map[cid] = gap_content
                
                # Fallback Tier 3: Tách theo các khối văn bản bất kỳ trong full_text
                still_missing = [cid for cid in cids if cid not in extracted_map]
                if still_missing:
                    blocks = re.split(r"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER|BẮT\s+ĐẦU|KẾT\s+THÚC)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", full_text, flags=re.IGNORECASE)
                    clean_blocks = [b.strip() for b in blocks if b and len(b.strip()) > 30]
                    
                    for idx, cid in enumerate(cids):
                        if cid not in extracted_map and idx < len(clean_blocks):
                            chap_no = chapter_map[cid]
                            print(f"[POST-PROCESS] 💡 Tự động gán khối văn bản {idx + 1} cho chương {chap_no} (ID {cid}).")
                            extracted_map[cid] = clean_blocks[idx]
                
                # Fallback Tier 4 (Cực hạn): Gán toàn bộ hoặc 1 phần full_text cho bất kỳ chương nào vẫn rỗng
                still_missing_final = [cid for cid in cids if cid not in extracted_map or not extracted_map[cid].strip()]
                for cid in still_missing_final:
                    chap_no = chapter_map[cid]
                    print(f"[POST-PROCESS] 🛡️ Cảnh báo: Tự động gán nội dung toàn bộ văn bản cho chương {chap_no} (ID {cid}) để đảm bảo tiến trình dịch không bị ngắt quãng.")
                    clean_full = re.sub(r"(?:===\s*)?(?:\[|\()? \s*(?:BEGIN_CHAPTER|END_CHAPTER)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", "", full_text, flags=re.IGNORECASE).strip()
                    extracted_map[cid] = clean_full if len(clean_full) > 10 else f"Chương {chap_no}"

            # Bước 3: Hậu xử lý từng nội dung và Lưu DB
            for cid in cids:
                chap_no = chapter_map[cid]
                print(f"[POST-PROCESS] Đang xử lý hoàn thiện chương {chap_no}...")
                chap_text = extracted_map[cid]

                # 3a. Sweep Chinese
                chap_text = await sweep_chinese_characters(chap_text)
                
                # 3b. Fix broken words (dính chữ từ LLM output)
                chap_text = fix_broken_words(chap_text)
                
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

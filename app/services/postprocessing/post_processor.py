import re
import os
from typing import Dict, List, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, Novel
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
    
    # Tìm tất cả các cụm (duy nhất để tránh gọi API nhiều lần cho cùng 1 từ)
    matches = list(set(pattern.findall(text)))
    if not matches:
        return text
        
    for chunk in matches:
        try:
            # Dịch online
            translated = await translate_text_via_google(chunk)
            if translated and translated != chunk:
                # Bọc thẻ gạch chân xanh
                highlighted = f'<span style="text-decoration: underline; text-decoration-color: blue;" class="swept-chinese">{translated}</span>'
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

def extract_chapter_text(full_text: str, cid: int, next_cid: int = None) -> str:
    """
    Trích xuất nội dung chương cực kỳ bền bỉ (robust), chịu lỗi tốt:
    1. Quét regex khớp thẻ chuẩn (kèm khoảng trắng tùy ý xung quanh hoặc trong ngoặc)
    2. Nếu không thấy, quét từ thẻ BEGIN_CHAPTER_{cid} đến thẻ END_CHAPTER_{cid} bất kể biến thể
    3. Nếu không có thẻ kết thúc (bị cụt do cạn token), quét từ BEGIN_CHAPTER_{cid} đến BEGIN_CHAPTER_{next_cid}
    """
    # 1. Regex khớp chuẩn tuyệt đối
    pattern_strict = re.compile(rf"===\s*\[BEGIN_CHAPTER_{cid}\]\s*===(.*?)===\s*\[END_CHAPTER_{cid}\]\s*===", re.DOTALL)
    match = pattern_strict.search(full_text)
    if match:
        return match.group(1).strip()

    # 2. Regex khớp mềm dẻo (hỗ trợ mất === hoặc lệch khoảng trắng, hoa/thường)
    pattern_lenient = re.compile(
        rf"(?:===\s*)?\[\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\s*{cid}\s*\](?:\s*===)?(.*?)\[\s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG)\s*{cid}\s*\]",
        re.DOTALL | re.IGNORECASE
    )
    match = pattern_lenient.search(full_text)
    if match:
        return match.group(1).strip()

    # 3. Quét từ BEGIN đến BEGIN chương kế tiếp (hoặc hết văn bản) khi bị mất thẻ END
    begin_pattern = re.compile(rf"(?:===\s*)?\[\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\s*{cid}\s*\](?:\s*===)?", re.IGNORECASE)
    begin_match = begin_pattern.search(full_text)
    if begin_match:
        start_idx = begin_match.end()
        if next_cid is not None:
            next_pattern = re.compile(rf"(?:===\s*)?\[\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\s*{next_cid}\s*\](?:\s*===)?", re.IGNORECASE)
            next_match = next_pattern.search(full_text, pos=start_idx)
            if next_match:
                end_idx = next_match.start()
                return full_text[start_idx:end_idx].strip()
        
        # Nếu là chương cuối lô, lấy đến hết text nhưng loại bỏ các đoạn đuôi nếu có tag END bị lỗi
        remaining = full_text[start_idx:]
        end_tag_pattern = re.compile(rf"(?:===\s*)?\[\s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG)\s*{cid}\s*\](?:\s*===)?.*", re.IGNORECASE | re.DOTALL)
        remaining = end_tag_pattern.sub("", remaining)
        return remaining.strip()

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
    2. Split (Tách chương)
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
            for idx, cid in enumerate(cids):
                chap_no = chapter_map[cid]
                print(f"[POST-PROCESS] Đang xử lý chương {chap_no}...")
                # 2. Split
                next_cid = cids[idx + 1] if idx + 1 < len(cids) else None
                chap_text = extract_chapter_text(full_text, cid, next_cid)
                
                if chap_text is not None:
                    # 3. Sweep Chinese
                    chap_text = await sweep_chinese_characters(chap_text)
                    
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
                else:
                    raise ValueError(f"Không tìm thấy thẻ phân tách cho chương {chap_no} (ID {cid}) trong kết quả dịch. Bản dịch lô này bị lỗi hoặc thiếu.")
                    
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

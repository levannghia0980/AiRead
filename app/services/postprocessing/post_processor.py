import re
import os
import shutil
import logging
from typing import Dict, List, Any, Optional, Union
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, Novel, NovelEntity
from app.services.unblock.unblock_pipeline import unmask_text_with_dictionary
from app.services.storage.file_storage import sanitize_filename
from app.core.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def normalize_chapter_title(text: str, chap_no: int, fallback_title: str = "") -> str:
    """
    Đảm bảo dòng đầu tiên của chương LUÔN LUÔN là Tiêu đề chương độc lập:
    Format: 'Chương {chap_no}: {tên_chương}'
    Theo sau là 1 dòng trống '\\n\\n' để tách biệt hoàn toàn với thân truyện.
    Tuyệt đối không để mất tiền tố 'Chương X:' và không dính tiêu đề vào câu truyện.
    """
    if not text:
        return f"Chương {chap_no}:\n\n"
        
    text = text.strip()
    lines = text.split('\n')
    
    # Tìm dòng đầu tiên có nội dung
    first_idx = -1
    for i, l in enumerate(lines):
        if l.strip():
            first_idx = i
            break
            
    if first_idx == -1:
        return f"Chương {chap_no}:\n\n"
        
    first_line = lines[first_idx].strip()
    rest_body = '\n'.join(lines[first_idx + 1:]).strip()
    
    # Dọn dẹp các ký tự trang trí hoặc ngoặc thừa ở đầu/cuối tiêu đề, bóc sạch HTML khỏi tiêu đề
    clean_first = re.sub(r'^[=\-_*#\s(\[{【（"“]+|[=\-_*#\s)\]}】）"”]+$', '', first_line).strip()
    clean_first = re.sub(r'<[^>]+>', '', clean_first).strip()
    
    # Bắt các mẫu tiêu đề có sẵn: Chương X / Chapter X / Hồi X / Tiết X...
    m = re.match(r'^(?:Quyển\s*\d+\s*)?(?:Chương|Chapter|Hồi|Tiết|Chap|Vol|Volume)\s*(\d*)[\s:.-]*(.*)$', clean_first, re.IGNORECASE)
    
    if m:
        extracted_num = m.group(1).strip()
        raw_tail = m.group(2).strip()
        raw_tail = re.sub(r'<[^>]+>', '', raw_tail).strip()
        
        # Gọt bỏ các thông tin rác trong ngoặc ở tiêu đề (VD: '(cầu hoa tươi)', '(1/3)')
        raw_tail = re.sub(r'[\(（](?:cầu|hết|chương|\d+/\d+).*?[\)）]', '', raw_tail, flags=re.IGNORECASE).strip()
        
        # Nếu đuôi tiêu đề bị dính liền thân truyện (chỉ tách khi có dấu kết câu rõ ràng)
        title_name = raw_tail
        body_lead = ""
        if len(raw_tail) > 60:
            split_m = re.search(r'(?:\!\.\.|\?\.\.|\.\.|\!|\?|\.)\s+', raw_tail)
            if split_m and split_m.start() < 60:
                title_name = raw_tail[:split_m.start() + 1].strip()
                body_lead = raw_tail[split_m.end():].strip()
                
        # Dọn dẹp title_name
        title_name = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', title_name).strip()
        
        if not title_name and fallback_title:
            fb = re.sub(r'^(?:第?\s*\d+\s*章\s*[:.:-]?|Chương\s*\d+\s*[:.:-]?)', '', fallback_title, flags=re.IGNORECASE).strip()
            fb = re.sub(r'<[^>]+>', '', fb).strip()
            title_name = fb
            
        full_title = f"Chương {chap_no}: {title_name}".strip() if title_name else f"Chương {chap_no}:"
        
        parts = [full_title, ""]
        if body_lead:
            parts.append(body_lead)
        if rest_body:
            parts.append(rest_body)
        return '\n'.join(parts)
    else:
        # Nếu dòng đầu không chứa tiền tố 'Chương X', kiểm tra xem nó có phải tên chương không
        if fallback_title:
            clean_fb = re.sub(r'^(?:第?\s*\d+\s*章\s*[:.:-]?|Chương\s*\d+\s*[:.:-]?)', '', fallback_title, flags=re.IGNORECASE).strip()
            clean_fb = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', clean_fb)
            if clean_fb and (clean_first.lower() == clean_fb.lower() or clean_first.lower().startswith(clean_fb.lower())):
                full_title = f"Chương {chap_no}: {clean_fb}"
                remainder = clean_first[len(clean_fb):].strip()
                remainder = re.sub(r'^[.:,\s-]+', '', remainder).strip()
                parts = [full_title, ""]
                if remainder:
                    parts.append(remainder)
                if rest_body:
                    parts.append(rest_body)
                return '\n'.join(parts)
                
        # Nếu không có tên chương: tạo 'Chương {chap_no}:' độc lập
        full_title = f"Chương {chap_no}:"
        return f"{full_title}\n\n{text}"


def strip_chapter_title(text: str, chap_no: int = None, fallback_title: str = "") -> str:
    """Loại bỏ dòng tiêu đề chương ở đầu (dùng khi cần nội dung thuần không có header)."""
    if not text:
        return ""
    lines = text.strip().split('\n')
    first_idx = -1
    for i, l in enumerate(lines):
        if l.strip():
            first_idx = i
            break
    if first_idx == -1:
        return ""
    first_line = lines[first_idx].strip()
    rest_lines = lines[first_idx + 1:]
    clean_line = re.sub(r'^[=\-_*#\s(\[{【（"“]+|[=\-_*#\s)\]}】）"”]+$', '', first_line).strip()
    ch_match = re.match(r'^(?:Quyển\s*\d+\s*)?(?:Chương|Chapter|Hồi|Tiết|Chap|Vol|Volume)\s*\d*[\s:.-]*(.*)$', clean_line, re.IGNORECASE)
    if ch_match:
        return '\n'.join(rest_lines).strip()
    return text.strip()


def fix_broken_words(text: str, protected_names: list = None) -> str:
    """
    Giữ nguyên 100% nguyên văn bản dịch của LLM,
    TUYỆT ĐỐI KHÔNG can thiệp bất kỳ nội dung nào.
    """
    return text.strip() if text else ""


async def realign_entity_names(text: str, novel_id: int, session = None) -> str:
    """
    Hậu kiểm và tự động nắn chuẩn tên nhân vật/thực thể cố định (Entity Consistency & Auto-Reanchoring):
    1. Sửa nhanh các lỗi biến âm tai hại cố định (Diệp Khốt -> Diệp Thánh, Tạ Cận Hoan -> Tạ Tận Hoan, Dương Hoa Tiên -> Dương Hóa Tiên, Diệp Vân Kh迟 -> Diệp Vân Trì...).
    2. Quét đối chiếu danh sách NovelEntity chuẩn của bộ truyện để nắn các lỗi lệch 1 chữ do AI hallucinate.
    """
    if not text:
        return text

    # 1. Các lỗi biến âm phổ biến cố định
    fixed_pairs = [
        (r'\bDiệp\s+Khốt\b', 'Diệp Thánh'),
        (r'\bTạ\s+Cận\s+Hoan\b', 'Tạ Tận Hoan'),
        (r'\bDương\s+Hoa\s+Tiên\b', 'Dương Hóa Tiên'),
        (r'\bDiệp\s+Vân\s*(?:Kh迟|Lịch)\b', 'Diệp Vân Trì'),
        (r'\bCấp\s+Nam\s+Cung\s+Tiên\s+Tử\b', 'Nam Cung Tiên Tử'),
        (r'\bLâm\s+Âm\s+Nghi\b', 'Lâm Uyển Nghi')
    ]
    for pattern, replacement in fixed_pairs:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 2. Đối chiếu với từ điển NovelEntity của tác phẩm
    try:
        from app.models.schema import NovelEntity
        from sqlalchemy import select
        
        async def _query_entities(s):
            stmt = select(NovelEntity.rough_translation).where(
                NovelEntity.novel_id == novel_id,
                NovelEntity.entity_type.in_(["NAME", "PERSON"]),
                NovelEntity.frequency_count >= 2
            ).order_by(NovelEntity.frequency_count.desc()).limit(100)
            res = await s.execute(stmt)
            return [r[0].strip() for r in res if r[0] and len(r[0].strip().split()) in [2, 3, 4]]

        names = []
        if session:
            names = await _query_entities(session)
        else:
            async with AsyncSessionLocal() as s:
                names = await _query_entities(s)

        for canon_name in names:
            words = canon_name.split()
            if len(words) == 3:
                w1, w2, w3 = words
                # Tìm biến thể lệch chữ giữa: "Tạ X Hoan" -> "Tạ Tận Hoan"
                variant_mid_pattern = rf'\b{re.escape(w1)}\s+[A-ZÀ-Ỹa-zà-ỹĐđ]{{2,10}}\s+{re.escape(w3)}\b'
                for m in re.finditer(variant_mid_pattern, text):
                    matched = m.group(0)
                    if matched != canon_name:
                        text = text.replace(matched, canon_name)
    except Exception as e:
        logger.warning(f"[POST-PROCESS] Lỗi realign_entity_names: {e}")

    return text



# === CÁC HÀM TƯƠNG THÍCH NGƯỢC (PASSTHROUGH - KHÔNG SỬA ĐỔI NỘI DUNG) ===
def fix_common_translation_typos(text: str) -> str:
    return text

def format_dialogue_flow(text: str) -> str:
    return text

def sanitize_false_positive_slang(text: str) -> str:
    return text

def clean_pinyin_parentheses_and_bilingual(text: str) -> str:
    return text

def reformat_fragmented_paragraphs(text: str) -> str:
    return text

async def sweep_chinese_characters(text: str) -> str:
    """
    Quét và tự động cứu/dịch vét các Hán tự còn sót lại trong văn bản sang tiếng Việt.
    1. Ưu tiên tra từ điển Unblock / Sắc hiệp.
    2. Tra âm Hán-Việt chuẩn (HanLP/Hán Việt).
    3. Phao cứu sinh cuối cùng: Google Translate (nếu Hán-Việt không ra nghĩa).
    Bọc thẻ gạch chân xanh dương (<span class="swept-chinese" data-raw="...">)
    để Frontend hiển thị và nút "Sửa Đỏ" (batch_fix_swept_errors) gom gửi AI dịch lại theo ngữ cảnh!
    """
    if not text or not re.search(r'[\u4e00-\u9fff]', text):
        return text

    # Bảo vệ các thẻ span đã tồn tại từ trước
    span_placeholders = {}
    def _save_span(m):
        key = f"__SAVED_SPAN_{len(span_placeholders)}__"
        span_placeholders[key] = m.group(0)
        return key

    text = re.sub(r'<span\b[^>]*>.*?</span>', _save_span, text, flags=re.DOTALL | re.IGNORECASE)

    pattern = re.compile(r'([\u4e00-\u9fff]+)')
    matches = list(set(pattern.findall(text)))
    if not matches:
        for ph, orig in span_placeholders.items():
            text = text.replace(ph, orig)
        return text

    if len(matches) > 100:
        logger.warning(f"[POST-PROCESS] Cảnh báo: Tìm thấy {len(matches)} cụm Hán tự (>100), bỏ qua tự động dịch để tránh treo hệ thống.")
        for ph, orig in span_placeholders.items():
            text = text.replace(ph, orig)
        return text

    from app.services.unblock.rawt.rawt_decoder import ZH_TO_EROTIC_VN_MAP
    from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name
    from app.services.preprocessing.crawler.google_translator import translate_text_via_google

    # Dịch tất cả các chunks trước
    chunk_map = {}
    for chunk in sorted(matches, key=len, reverse=True):
        try:
            # 1. Ưu tiên từ điển sắc văn / unblock
            translated = ZH_TO_EROTIC_VN_MAP.get(chunk)

            # 2. Hán-Việt / HanLP chuẩn
            if not translated:
                translated = build_hanviet_name(chunk)

            # 3. Phao cứu sinh Google Translate nếu cần
            if not translated or translated == chunk:
                try:
                    raw_trans = await translate_text_via_google(chunk)
                    if raw_trans:
                        match_paren = re.search(r'\((.*?)\)', raw_trans)
                        if match_paren and match_paren.group(1).strip():
                            translated = match_paren.group(1).strip()
                        else:
                            translated = re.sub(r'\(.*?\)', '', raw_trans).strip()
                except Exception:
                    pass

            if translated and translated != chunk:
                chunk_map[chunk] = translated
        except Exception as e:
            logger.warning(f"[POST-PROCESS] Lỗi cứu từ Hán tự '{chunk}': {e}")

    if not chunk_map:
        for ph, orig in span_placeholders.items():
            text = text.replace(ph, orig)
        return text

    replacement_placeholders = {}
    vn_char = r'[a-zA-Zà-ỹÀ-Ỹ0-9]'
    for chunk in sorted(chunk_map.keys(), key=len, reverse=True):
        translated = chunk_map[chunk]
        escaped_chunk = re.escape(chunk)

        def _smart_replace(m, c=chunk, t=translated):
            pre = m.group(1) or ""
            post = m.group(2) or ""

            # Kiểm tra từ đứng trước để quyết định viết hoa hay viết thường
            effective_trans = t
            prefix_text = text[:m.start()]
            m_prev_word = re.search(r'([a-zA-Zà-ỹÀ-Ỹ0-9]+)\s*$', prefix_text)
            if m_prev_word:
                prev_word = m_prev_word.group(1)
                if prev_word[0].isupper():
                    effective_trans = t.capitalize()
                elif prev_word.islower():
                    effective_trans = t.lower()
            elif pre:
                if pre.islower():
                    effective_trans = t.lower()
                elif pre.isupper():
                    effective_trans = t.capitalize()

            prefix_space = f"{pre} " if pre else ""
            suffix_space = f" {post}" if post else ""

            # Nếu vị trí thay thế nằm trên dòng tiêu đề chương (Chương X / Chapter X):
            # Chỉ thay thế bằng chữ thuần túy, tuyệt đối KHÔNG bọc thẻ span HTML làm hỏng tiêu đề
            line_start = text.rfind('\n', 0, m.start())
            line_start = 0 if line_start == -1 else line_start + 1
            line_end = text.find('\n', m.end())
            line_end = len(text) if line_end == -1 else line_end
            current_line = text[line_start:line_end]
            if re.match(r'^\s*(?:Quyển\s*\d+\s*)?(?:Chương|Chapter|Hồi|Tiết|Chap|Vol|Volume)\s*\d*', current_line, re.IGNORECASE):
                return f"{prefix_space}{effective_trans}{suffix_space}"

            ph_key = f"__SWEPT_SPAN_{len(replacement_placeholders)}__"
            replacement_placeholders[ph_key] = f'{prefix_space}<span style="text-decoration: underline; text-decoration-color: #0284c7;" class="swept-chinese" data-raw="{c}">{effective_trans}</span>{suffix_space}'
            return ph_key

        pattern = rf'({vn_char})?{escaped_chunk}(?:\s*[\(（][^()（）]{{1,50}}[\)）])?({vn_char})?'
        text = re.sub(pattern, _smart_replace, text)

    # Khôi phục các thẻ swept span vừa tạo
    for ph, span_html in replacement_placeholders.items():
        text = text.replace(ph, span_html)

    # Khôi phục các thẻ span ban đầu
    for ph, orig in span_placeholders.items():
        text = text.replace(ph, orig)

    return text

async def enforce_entity_names(text: str, novel_id: int) -> str:
    return text

def enforce_chapter_corrections(text: str, corrections: Dict[str, str]) -> str:
    return text


def make_chapter_begin_pattern(target_id: Union[str, int]) -> str:
    """Tạo regex bắt thẻ bắt đầu chương (hỗ trợ cả thẻ XML <chapter_X> siêu bền bỉ và thẻ văn bản)."""
    return (
        rf"(?:<\s*chapter_{target_id}\s*>|"
        rf"(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?|"
        rf"(?:===\s*(?:\[|\()?\s*|(?:\[|\()\s*)(?:CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?)"
    )

def make_chapter_end_pattern(target_id: Union[str, int]) -> str:
    """Tạo regex bắt thẻ kết thúc chương (hỗ trợ cả thẻ XML </chapter_X> siêu bền bỉ và thẻ văn bản)."""
    return (
        rf"(?:<\s*/\s*chapter_{target_id}\s*>|"
        rf"(?:===\s*)?(?:\[|\()?\s*(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+TH[ÚUƯ][CCh]\s+CHƯƠNG)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{target_id}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?)"
    )

def extract_chapter_text(full_text: str, cid: int, next_cid: int = None, chap_no: int = None, next_chap_no: int = None) -> Optional[str]:
    """
    Trích xuất nội dung chương cực kỳ bền bỉ (robust), chịu lỗi tốt.
    CHỈ dùng chapter_no (số chương) để tìm thẻ phân tách — KHÔNG dùng cid (DB ID).
    """
    if not full_text or not full_text.strip():
        return None

    ids_to_try = []
    if chap_no is not None:
        ids_to_try.extend([str(chap_no), f"{chap_no:02d}", f"{chap_no:03d}", f"{chap_no:04d}"])
    if not ids_to_try:
        ids_to_try.append(str(cid))

    def clean_extracted(t: str) -> str:
        if not t: return t
        raw_pattern = re.compile(r"(?:===\s*)?(?:\[|\()?RAW_CHAPTER", re.IGNORECASE)
        rmatch = raw_pattern.search(t)
        if rmatch:
            t = t[:rmatch.start()]
        t = re.sub(
            r"^\s*(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|KẾT\s+THÚC\s+CHƯƠNG)[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
            "", t, flags=re.IGNORECASE
        ).strip()
        t = re.sub(
            r"(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|KẾT\s+THÚC\s+CHƯƠNG)[^\n\]\)]*(?:\]|\))?(?:\s*===)?\s*$",
            "", t, flags=re.IGNORECASE
        ).strip()
        return t.strip()

    for target_id in ids_to_try:
        # 1. Matching BEGIN tag và END tag mềm dẻo
        pattern_pair = re.compile(
            rf"{make_chapter_begin_pattern(target_id)}(.*?){make_chapter_end_pattern(target_id)}",
            re.DOTALL | re.IGNORECASE
        )
        match = pattern_pair.search(full_text)
        if match and len(match.group(1).strip()) > 20:
            extracted_raw = match.group(1).strip()
            if not re.search(r"(?:<\s*chapter_\d+\s*>|BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\s*(?:ID|NO|NO\.)?[_\s:-]*\d+", extracted_raw, re.IGNORECASE):
                return clean_extracted(extracted_raw)

        # 2. Match từ BEGIN tag của target_id tới BEGIN tag của chương kế tiếp
        next_ids_to_try = []
        if next_chap_no is not None:
            next_ids_to_try.extend([str(next_chap_no), f"{next_chap_no:02d}", f"{next_chap_no:03d}"])

        begin_pattern = re.compile(make_chapter_begin_pattern(target_id), re.IGNORECASE)
        begin_match = begin_pattern.search(full_text)
        if begin_match:
            start_idx = begin_match.end()
            for nid in next_ids_to_try:
                next_pattern = re.compile(make_chapter_begin_pattern(nid), re.IGNORECASE)
                next_match = next_pattern.search(full_text, pos=start_idx)
                if next_match:
                    end_idx = next_match.start()
                    extracted = clean_extracted(full_text[start_idx:end_idx])
                    if len(extracted) > 20:
                        return extracted

            remaining = full_text[start_idx:]
            next_any_begin = re.search(r"(?:<\s*chapter_\d+\s*>|(?:===\s*\[?|\[)\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\b|\bBẮT\s+ĐẦU\s+CHƯƠNG\s*\d+\b|\bBEGIN_CHAPTER\s*\d+\b)", remaining, re.IGNORECASE)
            if next_any_begin:
                remaining = remaining[:next_any_begin.start()]
            end_tag_pattern = re.compile(
                rf"{make_chapter_end_pattern(target_id)}.*",
                re.IGNORECASE | re.DOTALL
            )
            remaining = end_tag_pattern.sub("", remaining)
            extracted = clean_extracted(remaining)
            if len(extracted) > 20:
                return extracted

        # 3. Match theo Header "Chương X: ..."
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
    version_type: str,
    enable_erotic: bool = False
):
    """
    Hậu xử lý thuần khiết:
    1. Unmask (Giải mã từ nhạy cảm)
    2. Split (Tách chương) theo thẻ phân tách
    3. Chuẩn hóa tiêu đề chương và dọn rác kỹ thuật
    4. Lưu vào 04_KetQua và DB.
    TUYỆT ĐỐI KHÔNG làm biến đổi nội dung, dấu câu, hay lời thoại của bản dịch LLM.
    """
    print(f"[POST-PROCESS] 🚀 Bắt đầu bóc tách & lưu kết quả cho lô gồm {len(chapter_map)} chương...")

    # 1. Unmask giải mã placeholder
    full_text = unmask_text_with_dictionary(translated_text_masked, mapping_table, enable_erotic=enable_erotic)

    # 2. Khử sạch tiền tố rác PREFIX_ và token nội bộ unblock nếu có (luôn chèn khoảng trắng để tránh dính chữ)
    full_text = re.sub(r'§?\s*PREFIX_([A-Za-z0-9_一-鿿\s]+?)§?', r' \1 ', full_text)
    full_text = re.sub(r'\bPREFIX_', ' ', full_text)
    full_text = full_text.replace('PREFIX_', ' ')
    full_text = re.sub(r'\?[\s_]*[ỗôo][\s_]*\?\.?', '?.', full_text)
    full_text = re.sub(r'§[A-Za-z0-9_]*§', ' ', full_text)
    full_text = re.sub(r'[^\S\r\n]{2,}', ' ', full_text)

    # Khởi tạo thư mục
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()

    base_dir = str(OUTPUT_DIR / "04_KetQua")
    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(base_dir, novel_folder, "chapters")
    os.makedirs(out_dir, exist_ok=True)

    # Lưu output LLM gốc ra file debug
    debug_dir = os.path.join(str(OUTPUT_DIR / "03_DichAI_LLM"), novel_folder)
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

            chap_nos_in_batch = [chapter_map[c] for c in cids]
            print(f"[POST-PROCESS] 📋 Bắt đầu tách {len(cids)} chương: {chap_nos_in_batch}")

            # Dọn dẹp thẻ BEGIN mồ côi xếp chồng ở đầu nếu có
            tag_p = r"(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG)\s*(?:ID|NO|NO\.)?[_\s:-]*\d+\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?"
            stacked_p = re.compile(rf"({tag_p})\s*({tag_p})", re.IGNORECASE)
            while True:
                m_st = stacked_p.search(full_text)
                if not m_st:
                    break
                full_text = full_text[:m_st.start()] + m_st.group(2) + full_text[m_st.end():]

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

            # Fallback nếu thiếu tag
            missing_cids = [cid for cid in cids if cid not in extracted_map]
            if missing_cids:
                if len(cids) == 1 and full_text and len(full_text.strip()) > 20:
                    cid = cids[0]
                    chap_no = chapter_map[cid]
                    clean_t = re.sub(r"^(?:===\s*)?(?:\[|\()?\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|KẾT\s+THÚC\s+CHƯƠNG)[^\n\]\)]*(?:\]|\))?(?:\s*===)?", "", full_text.strip(), flags=re.IGNORECASE).strip()
                    clean_t = re.sub(r"(?:===\s*)?(?:\[|\()?\s*(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|END_CHAPTER|END\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|KẾT\s+THÚC\s+CHƯƠNG)[^\n\]\)]*(?:\]|\))?(?:\s*===)?$", "", clean_t, flags=re.IGNORECASE).strip()
                    extracted_map[cid] = clean_t

            # Kiểm tra tính toàn vẹn
            valid_cids = []
            failed_cids = []
            for cid in cids:
                chap_no = chapter_map[cid]
                chap_text = extracted_map.get(cid)
                if not chap_text or len(chap_text.strip()) < 50:
                    failed_cids.append(cid)
                else:
                    valid_cids.append(cid)

            if failed_cids:
                async with AsyncSessionLocal() as fail_session:
                    for f_cid in failed_cids:
                        stmt_f = select(Chapter).where(Chapter.id == f_cid)
                        res_f = await fail_session.execute(stmt_f)
                        f_ch = res_f.scalar_one_or_none()
                        if f_ch and f_ch.status != "FINAL_DONE":
                            f_ch.status = "CRAWLED"
                    await fail_session.commit()

            for cid in valid_cids:
                chap_no = chapter_map[cid]
                print(f"[POST-PROCESS] Đang xử lý hoàn thiện chương {chap_no}...")
                chap_text = extracted_map.get(cid)
                if not chap_text:
                    continue

                # 1. Dọn rác thẻ phân chương kỹ thuật hoặc rác quảng cáo crawler
                chap_text = re.sub(r'(?i)</?chapter(?:_\d+)?\b[^>]*>', '', chap_text)
                chap_text = re.sub(r'(?i)\[/?chapter(?:_\d+)?\b[^\]]*\]', '', chap_text)
                chap_text = re.sub(r'(?im)^\s*===+\s*(?:BEGIN|END)\s+CHAPTER\s*\d*.*?===+\s*\n?', '', chap_text)
                chap_text = re.sub(r'(?im)^\s*===+\s*\[?(?:BẮT\s+ĐẦU|KẾT\s+THÚC)\s+CHƯƠNG\s*\d*.*?\]?\s*===+\s*\n?', '', chap_text)
                chap_text = re.sub(r'(?im)^\s*(?:cổng game|casino|nhà cái|nổ hũ|game slot|pagcor|baccarat|uy tín hơn\. Cụ thể).*\n?', '', chap_text)

                # 2. Chuẩn hóa khoảng trắng cơ bản, giữ nguyên 100% từ ngữ của AI
                chap_text = fix_broken_words(chap_text)
                # 3. Cứu Hán tự sót bằng Hán-Việt/HanLP hoặc Google Dịch (bọc thẻ xanh để Frontend và nút Sửa Đỏ bắt được)
                chap_text = await sweep_chinese_characters(chap_text)
                # 3b. Tự động nắn chuẩn tên nhân vật/thực thể cố định (Entity Consistency & Auto-Reanchoring)
                chap_text = await realign_entity_names(chap_text, novel_id, session=session)
                chap_text = chap_text.strip()

                # Lấy thông tin chapter từ DB để có fallback title nếu cần
                stmt_chap = select(Chapter).where(Chapter.id == cid)
                res_chap = await session.execute(stmt_chap)
                chap = res_chap.scalar_one_or_none()
                fb_title = (chap.title_rough or chap.title_raw) if chap else ""

                # 4. CHUẨN HÓA TIÊU ĐỀ CHƯƠNG ĐỘC LẬP & CÁCH DÒNG TRỐNG VỚI THÂN TRUYỆN:
                chap_text = normalize_chapter_title(chap_text, chap_no, fallback_title=fb_title)

                if chap:
                    first_l = chap_text.split('\n')[0].strip()
                    m_t = re.match(r'^(?:Chương|Chapter)\s*\d+[\s:.-]*(.*)$', first_l, re.IGNORECASE)
                    if m_t and m_t.group(1).strip():
                        extracted_t = m_t.group(1).strip()
                        extracted_t = re.sub(r'<[^>]+>', '', extracted_t).strip()
                        if not any('\u4e00' <= c <= '\u9fff' for c in extracted_t):
                            chap.title_rough = extracted_t
                    chap.status = "FINAL_DONE"
                
                # 5. Lưu file 04_KetQua
                file_name = f"{chap_no:06d}.txt"
                file_path = os.path.join(out_dir, file_name)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(chap_text)
                    
                saved_files.append(file_path)

                # 6. Cập nhật DB cho các phiên bản kết quả: FINAL, CONTEXTT, EDITED, LLM
                for v_type in ["FINAL", "CONTEXTT", "EDITED", "LLM"]:
                    stmt_ver = select(ChapterVersion).where(
                        ChapterVersion.chapter_id == cid, 
                        ChapterVersion.version_type == v_type
                    )
                    res_ver = await session.execute(stmt_ver)
                    ver = res_ver.scalar_one_or_none()
                    if ver:
                        ver.file_path = file_path
                        ver.content = chap_text
                    else:
                        session.add(ChapterVersion(
                            chapter_id=cid, 
                            version_type=v_type, 
                            file_path=file_path, 
                            content=chap_text
                        ))

                # Xóa cache tệp Audio cũ nếu có
                try:
                    mp3_cache_path = os.path.join(str(OUTPUT_DIR / "05_Audio_TTS"), novel_folder, "chapters", f"{chap_no:06d}.mp3")
                    if os.path.exists(mp3_cache_path):
                        os.remove(mp3_cache_path)
                except Exception:
                    pass

            await session.commit()
            logger.info(f"[POST-PROCESS] Hoan tat boc tach & luu ket qua {len(valid_cids)}/{len(cids)} chuong!")

    except Exception as e:
        logger.error(f"[POST-PROCESS] Loi nghiem trong khi boc tach lo: {e}", exc_info=True)

    return saved_files


async def export_full_novel_txt(novel_id: int, novel_title: Optional[str] = None, include_chapter_titles: bool = True) -> Dict[str, Any]:
    """
    Tổng hợp toàn bộ các chương đã hoàn thành (FINAL) của một bộ truyện thành 1 file .txt duy nhất.
    Ưu tiên đọc trực tiếp từ DB (ver.content) để truy xuất siêu tốc!
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt_nov = select(Novel).where(Novel.id == novel_id)
            res_nov = await session.execute(stmt_nov)
            novel = res_nov.scalar_one_or_none()
            if not novel:
                logger.warning(f"[POST-PROCESS] Khong tim thay novel_id={novel_id}")
                return {}

            effective_title = novel_title or novel.title_rough or novel.title_raw or f"Novel_{novel_id}"
            novel_folder = sanitize_filename(effective_title)
            base_dir = str(OUTPUT_DIR / "04_KetQua")
            out_dir = os.path.join(base_dir, novel_folder)
            os.makedirs(out_dir, exist_ok=True)

            full_file_path = os.path.join(out_dir, f"{novel_folder}_Full.txt")

            # Lấy tất cả các chương theo thứ tự
            stmt_chaps = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
            res_chaps = await session.execute(stmt_chaps)
            chapters = res_chaps.scalars().all()

            if not chapters:
                # Fallback: kiểm tra xem trên đĩa có file txt chương nào không
                chap_dir = os.path.join(out_dir, "chapters")
                if os.path.exists(chap_dir):
                    txt_files = sorted([f for f in os.listdir(chap_dir) if f.endswith(".txt") and not f.startswith("all_") and not f.endswith("_Full.txt")])
                    if txt_files:
                        with open(full_file_path, "w", encoding="utf-8") as outfile:
                            for fname in txt_files:
                                fpath = os.path.join(chap_dir, fname)
                                with open(fpath, "r", encoding="utf-8", errors="ignore") as infile:
                                    content = infile.read().strip()
                                    if content:
                                        outfile.write(content)
                                        outfile.write("\n\n" + "="*40 + "\n\n")
                        return {"file_path": full_file_path, "title": effective_title}
                return {"file_path": "", "title": effective_title}

            exported_count = 0
            with open(full_file_path, "w", encoding="utf-8") as out_f:
                out_f.write(f"=== {effective_title} ===\n")
                if novel.author:
                    out_f.write(f"Tác giả: {novel.author}\n\n\n")
                else:
                    out_f.write("\n\n")

                for chap in chapters:
                    stmt_ver = select(ChapterVersion).where(
                        ChapterVersion.chapter_id == chap.id,
                        ChapterVersion.version_type == "FINAL"
                    )
                    res_ver = await session.execute(stmt_ver)
                    ver = res_ver.scalar_one_or_none()

                    raw_text = ""
                    if ver:
                        raw_text = ver.content.strip() if ver.content else ""
                        if not raw_text and ver.file_path and os.path.exists(ver.file_path):
                            try:
                                with open(ver.file_path, "r", encoding="utf-8", errors="ignore") as in_f:
                                    raw_text = in_f.read().strip()
                            except Exception:
                                pass

                    # Nếu DB không có FINAL, fallback kiểm tra file trên đĩa
                    if not raw_text:
                        disk_chap_path = os.path.join(out_dir, "chapters", f"{chap.chapter_no:06d}.txt")
                        if os.path.exists(disk_chap_path):
                            try:
                                with open(disk_chap_path, "r", encoding="utf-8", errors="ignore") as in_f:
                                    raw_text = in_f.read().strip()
                            except Exception:
                                pass

                    if raw_text:
                        exported_count += 1
                        if not include_chapter_titles:
                            clean_body = strip_chapter_title(raw_text, chap_no=chap.chapter_no, fallback_title=chap.title_rough or chap.title_raw)
                            out_f.write(clean_body)
                            out_f.write("\n\n\n")
                        else:
                            out_f.write(f"\n--- CHƯƠNG {chap.chapter_no}: {chap.title_rough or chap.title_raw} ---\n\n")
                            out_f.write(raw_text)
                            out_f.write("\n\n")

            logger.info(f"[POST-PROCESS] Da xuat gop {exported_count}/{len(chapters)} chuong vao: {full_file_path}")
            return {
                "file_path": full_file_path,
                "title": effective_title
            }
    except Exception as e:
        logger.error(f"[POST-PROCESS] Loi khi xuat gop truyen novel_id={novel_id}: {e}", exc_info=True)
        return {"file_path": "", "title": ""}

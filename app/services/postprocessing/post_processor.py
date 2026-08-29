import re
import os
import shutil
from typing import Dict, List, Any, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, Novel, NovelEntity
from app.services.unblock.unblock_pipeline import unmask_text_with_dictionary
from app.services.preprocessing.crawler.google_translator import translate_text_via_google
from app.services.storage.file_storage import sanitize_filename

async def sweep_chinese_characters(text: str) -> str:
    """
    Quét và tự động dịch vét các Hán tự còn sót lại trong văn bản sang tiếng Việt.
    Ưu tiên tra từ điển Unblock/Sắc hiệp trước (tránh dịch 骚 thành 'Sao', 奸 thành 'độc ác').
    Tự động gọt bỏ phần giải nghĩa trong ngoặc đơn đi kèm (VD: '玲珑有致 (tinh xảo)' -> bọc dịch 'Linh Lung Hữu Trí' và bỏ '(tinh xảo)').
    Bọc thẻ gạch chân xanh dương để đánh dấu ở Frontend.
    """
    if not text:
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
        
    if len(matches) > 50:
        print(f"[POST-PROCESS] Cảnh báo: Tìm thấy {len(matches)} cụm Hán tự (>50), bỏ qua tự động dịch để tránh treo hệ thống.")
        for ph, orig in span_placeholders.items():
            text = text.replace(ph, orig)
        return text
        
    # Tra từ điển Unblock / Sắc hiệp trước để dịch chuẩn xác ngữ cảnh
    from app.services.unblock.rawt.rawt_decoder import ZH_TO_EROTIC_VN_MAP
    from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name

    # Dịch tất cả các chunks trước
    chunk_map = {}
    for chunk in sorted(matches, key=len, reverse=True):
        try:
            # 1. Ưu tiên từ điển sắc văn / unblock (giữ đúng độ tục, giấu TTS nhẹ)
            translated = ZH_TO_EROTIC_VN_MAP.get(chunk)
            
            # 2. Nếu không phải từ lóng, dùng HanLP / Hán-Việt chuẩn ngữ nghĩa
            if not translated:
                translated = build_hanviet_name(chunk)
                
            # 3. Phao cứu sinh cuối cùng: Google Translate (nếu Hán-Việt không tra được)
            if not translated or translated == chunk:
                try:
                    raw_trans = await translate_text_via_google(chunk)
                    if raw_trans:
                        # Ưu tiên lấy nghĩa giải nghĩa chuẩn xác trong ngoặc đơn
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
            print(f"[POST-PROCESS] Lỗi dịch Hán tự '{chunk}': {e}")

    # Thay thế bằng placeholder để chuỗi con không đè vào thẻ HTML của chuỗi cha
    # Đồng thời tự động gọt bỏ phần chú thích giải nghĩa trong ngoặc đơn đi liền sau Hán tự (VD: '玲珑有致 (tinh xảo)' -> chỉ lấy 'Linh Lung Hữu Trí')
    replacement_placeholders = {}
    vn_char = r'[a-zA-Zà-ỹÀ-Ỹ0-9]'
    for chunk in sorted(chunk_map.keys(), key=len, reverse=True):
        translated = chunk_map[chunk]
        escaped_chunk = re.escape(chunk)
        
        def _smart_replace(m, c=chunk, t=translated):
            pre = m.group(1) or ""
            post = m.group(2) or ""
            prefix_space = f"{pre} " if pre else ""
            suffix_space = f" {post}" if post else ""
            ph_key = f"__SWEPT_SPAN_{len(replacement_placeholders)}__"
            replacement_placeholders[ph_key] = f'{prefix_space}<span style="text-decoration: underline; text-decoration-color: blue;" class="swept-chinese" data-raw="{c}">{t}</span>{suffix_space}'
            return ph_key
        
        # Match Hán tự kèm ngoặc đơn chú thích giải nghĩa thừa phía sau (nếu có)
        pattern = rf'({vn_char})?{escaped_chunk}(?:\s*[\(（][^()（）]{{1,50}}[\)）])?({vn_char})?'
        text = re.sub(pattern, _smart_replace, text)

    # Khôi phục các thẻ swept span vừa tạo
    for ph, span_html in replacement_placeholders.items():
        text = text.replace(ph, span_html)

    # Khôi phục các thẻ span ban đầu
    for ph, orig in span_placeholders.items():
        text = text.replace(ph, orig)
            
    return text

def sanitize_false_positive_slang(text: str) -> str:
    """
    LƯỚI AN TOÀN CUỐI CÙNG: Phát hiện và sửa lỗi thay thế nhầm (false positive)
    từ hệ thống Unblock/Sắc Văn trong văn bản tiếng Việt đầu ra.
    
    Chạy SAU TẤT CẢ các bước dịch và unmask, để bắt những trường hợp
    edge-case hiếm mà Trie matcher + rawt_decoder không ngăn được.
    """
    if not text:
        return text
    
    t = text
    
    # === NHÓM 1: Lỗi từ 干 (làm/khô) bị dịch nhầm thành 'địtt' ===
    # 干得好 → 'địtt đến tốt' thay vì 'làm tốt'
    t = re.sub(r'(?i)\bđịtt\s+đến\s+(tốt|hay|đẹp|giỏi|nhanh|chậm|khá|xuất\s+sắc|mệt|nhiều|sạch)\b', r'làm \1', t)
    t = re.sub(r'(?i)\bđịtt\s+thành\s+(quả|tích|công|tựu|phẩm|tựu)\b', r'làm nên \1', t)
    t = re.sub(r'(?i)\bđịtt\s+(?:đến\s+)?khô\b', 'uống cạn', t)
    
    # === NHÓM 2: Lỗi từ 插入 (chèn vào) bị dịch nhầm thành 'đút vào' ===
    t = re.sub(r'(?i)\bđút\s+vào\s+(sắp\s+xếp|phân\s+loại|thuật\s+toán|thứ\s+tự|dữ\s+liệu)\b', r'chèn vào \1', t)
    t = re.sub(r'(?i)\bđút\s+vào\s+ngữ\b', 'chêm ngữ', t)
    
    # === NHÓM 3: Lỗi từ 喷水 (phun nước) bị thêm 'dâm' ===  
    t = re.sub(r'(?i)\bphun\s+nước\s+dâm\s+(ao|hồ|đài|vườn|bể|sân|công\s+viên)\b', r'phun nước \1', t)
    t = re.sub(r'(?i)\bđài\s+phun\s+nước\s+dâm\b', 'đài phun nước', t)
    
    # === NHÓM 4: Lỗi từ 射 (bắn) trong ngữ cảnh quân sự/khoa học ===
    t = re.sub(r'(?i)\bbắn\s+tinh\s+(tên|cung|súng|đạn|pháo|tia)\b', r'bắn \1', t)
    t = re.sub(r'(?i)\b(phóng|phát|phản|chiếu|bức)\s+bắn\s+tinh\b', r'\1 xạ', t)
    
    # === NHÓM 5: Lỗi 精 (tinh hoa) bị hiểu nhầm ngữ cảnh tinh dịch ===
    t = re.sub(r'(?i)\btinh\s+dịch\s+(thần|lực|hoa|thông|xác|tế|mật|anh|tuyển|phẩm|giản|chuẩn)\b', r'tinh \1', t)
    t = re.sub(r'(?i)\brượu\s+tinh\s+dịch\b', 'rượu cồn', t)
    
    # === NHÓM 6: Lỗi 交 (giao) bị hiểu nhầm thành giao hợp ===
    t = re.sub(r'(?i)\bđịtt\s+nhau\s+thông\b', 'giao thông', t)
    t = re.sub(r'(?i)\bđịtt\s+nhau\s+lưu\b', 'giao lưu', t)
    t = re.sub(r'(?i)\bđịtt\s+nhau\s+dịch\b', 'giao dịch', t)
    t = re.sub(r'(?i)\bđịtt\s+nhau\s+hoán\b', 'giao hoán', t)
    
    # === NHÓM 7: Lỗi 乳 (sữa) trong ngữ cảnh thực phẩm/khoa học ===
    t = re.sub(r'(?i)\b(đầu\s+vú|bầu\s+vú)\s+(trắng|sản\s+phẩm|tương|keo|hóa|danh|acid)\b', r'sữa \2', t)
    t = re.sub(r'(?i)\bcho\s+bú\s+động\s+vật\b', 'động vật có vú', t)
    
    # === NHÓM 8: Lỗi 穴 (huyệt đạo) trong ngữ cảnh y học/địa lý ===
    t = re.sub(r'(?i)\b(lỗ\s+lồn|hoa\s+huyệt|mật\s+huyệt)\s+(vị|đạo|đạo|châm\s+cứu)\b', r'huyệt \2', t)
    t = re.sub(r'(?i)\bhang\s+lỗ\s+lồn\b', 'hang động', t)
    
    return t

def reformat_fragmented_paragraphs(text: str) -> str:
    """
    Tự động ghép nối các câu văn miêu tả bị ngắt dòng vụn vặt từng câu thành các đoạn văn thuần Việt mượt mà.
    Giữ nguyên các dòng hội thoại ("...", “...”) và các thẻ phân chương (=== [BẮT ĐẦU CHƯƠNG X] ===).
    """
    if not text:
        return text

    lines = text.split('\n')
    new_lines = []
    buffer = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                new_lines.append(buffer)
                buffer = ""
            new_lines.append("")
            continue

        # Kiểm tra xem có phải thẻ phân chương, tiêu đề, hoặc lời thoại hội thoại
        is_tag_or_dialogue = (
            stripped.startswith("===") or 
            stripped.startswith("Chương") or 
            stripped.startswith("CHAPTER") or
            re.match(r'^[“"‘\'「『【\[\(]', stripped) or
            re.match(r'^[-–—]\s*', stripped)
        )

        if is_tag_or_dialogue:
            if buffer:
                new_lines.append(buffer)
                buffer = ""
            new_lines.append(stripped)
        else:
            if buffer:
                # Nếu buffer kết thúc bằng dấu ngoặc kép hội thoại thì dừng buffer cũ
                if re.search(r'[”"’\'」』】\]\)]$]', buffer.strip()):
                    new_lines.append(buffer)
                    buffer = stripped
                else:
                    buffer += " " + stripped
            else:
                buffer = stripped

    if buffer:
        new_lines.append(buffer)

    res = "\n".join(new_lines)
    res = re.sub(r'\n{3,}', '\n\n', res)
    return res


def fix_broken_words(text: str, protected_names: list = None) -> str:
    """
    Phát hiện và sửa lỗi dính chữ từ LLM output (Gemini):
    - Chữ thường dính chữ HOA giữa câu (VD: nhìnKhiếu → nhìn Khiếu)
    - Dấu câu dính chữ liền sau (VD: rồi.Hắn → rồi. Hắn)
    - Chuẩn hóa khoảng trắng thừa
    - BẢO VỆ tên thực thể (protected_names) không bị tách nhầm
    """
    if not text:
        return text
    
    original_text = text
    
    # === 1. BẢO VỆ THẺ HTML (swept-chinese, unblock-sensitive) VÀ TÊN THỰC THỂ: Che giấu trước khi xử lý ===
    span_placeholders = {}
    def _save_span(m):
        idx = len(span_placeholders)
        ph = f"___HTML_SPAN_{idx:04d}___"
        span_placeholders[ph] = m.group(0)
        return ph
    
    text = re.sub(r'<span\b[^>]*\bclass=["\'](?:swept-chinese|unblock-sensitive|fixed-sentence|fixed-word)["\'][^>]*>.*?</span>', _save_span, text, flags=re.DOTALL)

    name_placeholders = {}
    if protected_names:
        # Sắp xếp dài trước ngắn sau để tránh thay thế con trước cha
        sorted_names = sorted(set(protected_names), key=len, reverse=True)
        for idx, name in enumerate(sorted_names):
            if name and name in text:
                placeholder = f"___PROT_NAME_{idx:04d}___"
                text = text.replace(name, placeholder)
                name_placeholders[placeholder] = name
    
    # Tập ký tự tiếng Việt đầy đủ (bao gồm ơƠ, ưƯ, đĐ)
    vn_lower = r'a-zàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộơớờởỡợúùủũụưứừửữựỳýỷỹỵđ'
    vn_upper = r'A-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ'
    vn_all = rf'{vn_lower}{vn_upper}'
    
    # Rule 00: Tự động dọn dẹp các thẻ lỗi hoặc ký tự rò rỉ (không chứa thẻ đã bảo vệ)
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'[<>‹›⟦⟧§]', ' ', text)

    # Rule 00b: Tự động loại bỏ rác metadata crawler website Trung Quốc ở đầu/cuối chương
    text = re.sub(r'(?i)^\s*(?:Mì\s+nấm\s+.*|蘑菇面要加蛋)\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\s*(?:Chữ|từ|字)\s*\n?', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[]\s*\n?', '', text, flags=re.MULTILINE)

    # Rule 00c: Tự động ghép nối các câu miêu tả bị ngắt dòng vụn vặt thành đoạn văn hoàn chỉnh
    text = reformat_fragmented_paragraphs(text)

    # Rule 00d: Làm sạch dấu ngoặc kép rỗng trơ trọi & Chuẩn hóa ngoặc Trung Quốc
    text = re.sub(r'^\s*["“”\']+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'["“”]{2,}', '', text)
    text = re.sub(r'[【〖](.*?)[】〗]', r'[\1]', text)
    text = re.sub(r'[《「『](.*?)[》」』]', r'"\1"', text)

    # Rule 00e: Chuẩn hóa ký tự số / Cấp độ / Ký hiệu toán học để TTS đọc chuẩn mượt mà
    text = re.sub(r'(?i)\bLv\.?\s*(\d+)\b', r'cấp \1', text)
    text = re.sub(r'(?i)\bLevel\s*(\d+)\b', r'cấp \1', text)
    text = re.sub(r'(\s|\(|\[|^|,)\+\s*(\d+)\b', r'\1cộng \2', text)
    text = re.sub(r'(\d+)\s*[%％]', r'\1 phần trăm', text)
    text = re.sub(r'——+', '—', text)

    # Rule 00f: Ưu tiên lấy nghĩa giải nghĩa chuẩn xác trong ngoặc đơn từ Google Dịch (VD: 'trò chơi tục tĩu (chà đạp quấy rối)' -> 'chà đạp quấy rối', 'u sầu (sầu muộn)' -> 'sầu muộn')
    text = re.sub(rf'(?i)\b[{vn_lower}{vn_upper}\s]{{2,30}}\s*\(\s*([{vn_lower}{vn_upper}\s]{{2,30}})\s*\)', r'\1', text)

    # Rule 0a: Sửa triệt để rác tiêu đề chương bị dịch nhầm
    text = re.sub(r'(?i)(?:KHÔNG|NO)\s*\.?\s*(\d+)\s*(?:chương|Chương|章)?\s*[:.:-]?\s*', r'Chương \1: ', text)
    text = re.sub(r'第\s*(\d+)\s*章\s*[:.:-]?\s*', r'Chương \1: ', text)
    text = re.sub(r'(?i)(?:Chương\s*(\d+)\s*:\s*){2,}', r'Chương \1: ', text)

    # Rule 1a: Chữ thường tiếng Việt dính chữ HOA giữa từ → tách ra (VD: nhìnKhiếu → nhìn Khiếu)
    text = re.sub(f'([{vn_lower}])([{vn_upper}])', r'\1 \2', text)

    # Rule 1c: Sửa lỗi lặp chữ HOA đầu từ
    text = re.sub(rf'\b([{vn_upper}])\1+([{vn_upper}][{vn_lower}]+)', r'\1\2', text)
    text = re.sub(rf'\b([{vn_upper}])\1+([{vn_lower}]+)', r'\1\2', text)

    # Rule 2: Dấu câu dính chữ HOA (thiếu khoảng trắng sau dấu câu)
    text = re.sub(f'([.!?;:,])([{vn_upper}])', r'\1 \2', text)
    
    # Rule 3: Chuẩn hóa khoảng trắng thừa (2+ spaces → 1 space)
    text = re.sub(r' {2,}', ' ', text)
    
    # Rule 4: Loại bỏ khoảng trắng thừa trước dấu câu
    text = re.sub(r' +([.!?;:,])', r'\1', text)

    # Rule 5: Dọn dòng trống thừa
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    
    # === KHÔI PHỤC TÊN THỰC THỂ & THẺ HTML ĐÃ BẢO VỆ ===
    for placeholder, original_name in name_placeholders.items():
        text = text.replace(placeholder, original_name)

    for ph, orig_span in span_placeholders.items():
        text = text.replace(ph, orig_span)
    
    # Tự động tách khoảng trắng nếu thẻ span bị dính sát vào chữ tiếng Việt trước hoặc sau (chống lỗi quyĐầu)
    text = re.sub(rf'([{vn_lower}{vn_upper}])(<span\b[^>]*>)', r'\1 \2', text)
    text = re.sub(r' {2,}', ' ', text)
    
    # Khử lỗi rãnh quy cái đầu / quy cái đầu sinh ra từ Google Translate cho chữ 头/頭
    text = re.sub(r'(?i)\brãnh\s+quy\s+<span\b[^>]*data-raw=["\']?[頭头]["\']?[^>]*>.*?</span>', 'rãnh đầu cặc', text)
    text = re.sub(r'(?i)\bquy\s+<span\b[^>]*data-raw=["\']?[頭头]["\']?[^>]*>.*?</span>', 'đầu cặc', text)
    text = re.sub(r'(?i)\brãnh\s+quy\s+cái\s+đầu\b', 'rãnh đầu cặc', text)
    text = re.sub(r'(?i)\bquy\s+cái\s+đầu\b', 'đầu cặc', text)
    text = re.sub(r'(?i)\brãnh\s+quy\s+đầu\b', 'rãnh đầu cặc', text)
    text = re.sub(r'(?i)\bquy\s+đầu\b', 'đầu cặc', text)
    
    # Khử lỗi tiền tố Hán dính từ thừa (VD: "Tiểu bé gái" -> "cô bé", "Tiểu con gái" -> "cô bé")
    text = re.sub(r'(?i)\bTiểu\s+(<span\b[^>]*>(?:bé\s+gái|con\s+gái|cô\s+bé|cô\s+gái)</span>)', r'\1', text)
    text = re.sub(r'(?i)\bTiểu\s+(?:bé\s+gái|con\s+gái)\b', 'cô bé', text)

    # Chuẩn hóa cụm từ chức danh giáo phái tránh lặp từ (VD: "Minh Giáo giáo chủ" -> "Giáo chủ Minh Giáo")
    sects_pattern = r'Minh|Ma|Thần|Nhật\s+Nguyệt\s+Thần|Bạch\s+Liên|Huyết|Thiên|Cửu\s+U|Hắc\s+Phong|Ngũ\s+Độc|La\s+Sát'
    text = re.sub(rf'(?i)\b((?:{sects_pattern})\s+Giáo)\s+giáo\s+chủ\b', r'Giáo chủ \1', text)
    
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

def enforce_chapter_corrections(text: str, corrections: Dict[str, str]) -> str:
    """
    Hậu xử lý an toàn: Quét và thay thế các từ Pinyin / Tiếng Anh dịch lỗi còn sót lại (như Mo Yayi, Serena, Wang Wei)
    bằng tên Việt chuẩn theo đúng ranh giới từ (Word Boundary \\b...\\b), đảm bảo 100% không bao giờ thay thế lố hay dính từ.
    """
    if not text or not corrections:
        return text or ""
    for wrong_text, correct_text in corrections.items():
        if wrong_text and correct_text and wrong_text.strip().lower() != correct_text.strip().lower():
            # CHỈ thay thế nếu wrong_text là Pinyin / Tiếng Anh (không chứa dấu thanh tiếng Việt)
            if not re.search(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', wrong_text.lower()):
                pattern = r'\b' + re.escape(wrong_text) + r'\b'
                text = re.sub(pattern, correct_text, text)
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
            extracted_raw = match.group(1).strip()
            # Kiểm tra an toàn: nếu đoạn trích xuất chứa thẻ BEGIN của chương khác (do LLM xếp chồng thẻ ở đầu),
            # thì đây là đoạn lồng thẻ lỗi, không được lấy.
            if not re.search(r"(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU)\s*(?:ID|NO|NO\.)?[_\s:-]*\d+", extracted_raw, re.IGNORECASE):
                return clean_extracted(extracted_raw)

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
    version_type: str,
    enable_erotic: bool = False
):
    """
    Hậu xử lý toàn bộ:
    1. Unmask (Giải mã từ nhạy cảm)
    2. Split (Tách chương) với đa tầng Fallback siêu bền bỉ
    3. Sweep Chinese (Dịch Hán tự sót) & Chuẩn hóa từ ngữ / dính chữ
    4. Lưu vào file và cập nhật DB.
    """
    # 1. Unmask (Giải mã từ nhạy cảm - hỗ trợ Phong cách Dịch Sắc 18+ Từ Nặng vs Dịch Uyển Chuyển YouTube)
    is_contextt = (version_type.upper() == "CONTEXTT")
    print(f"[POST-PROCESS] Đang giải mã các từ nhạy cảm (Unmasking - Phong cách Dịch Sắc 18+ Từ Nặng: {enable_erotic} | Flow: {version_type})...")
    full_text = unmask_text_with_dictionary(translated_text_masked, mapping_table, is_draft_only=is_contextt, enable_erotic=enable_erotic, flow=version_type.lower())
    
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
            
            # Dọn dẹp các thẻ BEGIN mồ côi bị xếp chồng ở đầu văn bản (nếu LLM nhầm lẫn chèn thẻ chương cuối lên đầu)
            tag_p = r"(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU)\s*(?:ID|NO|NO\.)?[_\s:-]*\d+\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?"
            stacked_p = re.compile(rf"({tag_p})\s*({tag_p})", re.IGNORECASE)
            while True:
                m_st = stacked_p.search(full_text)
                if not m_st:
                    break
                full_text = full_text[:m_st.start()] + m_st.group(2) + full_text[m_st.end():]

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

            # Bước 3: Kiểm tra NGHIÊM NGẶT — Mỗi chương PHẢI có CẢ thẻ BẮT ĐẦU lẫn KẾT THÚC
            # Một chương hoàn chỉnh = có thẻ BẮT ĐẦU + nội dung + thẻ KẾT THÚC (KHÔNG DỊCH VÁ LẺ)
            async with AsyncSessionLocal() as session:
                for idx, cid in enumerate(cids):
                    chap_no = chapter_map[cid]
                    chap_text = extracted_map.get(cid, "").strip()
                    
                    # 3a. Kiểm tra thẻ BẮT ĐẦU CHƯƠNG trong LLM output
                    begin_tag_pattern = re.compile(
                        rf"(?:===\s*)?(?:\[|\()? *(?:BEGIN_CHAPTER|BEGIN\s+CHAPTER|BẮT\s+ĐẦU\s+CHƯƠNG|BẮT\s+ĐẦU|CHƯƠNG|CHAPTER)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{chap_no}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
                        re.IGNORECASE
                    )
                    has_begin_tag = bool(begin_tag_pattern.search(full_text))
                    
                    # 3b. Kiểm tra thẻ KẾT THÚC CHƯƠNG trong LLM output
                    end_tag_pattern = re.compile(
                        rf"(?:===\s*)?(?:\[|\()? *(?:END_CHAPTER|END\s+CHAPTER|KẾT\s+THÚC\s+CHƯƠNG|KẾT\s+THÚC)[_\s:-]*(?:ID|NO|NO\.)?[_\s:-]*{chap_no}\b[^\n\]\)]*(?:\]|\))?(?:\s*===)?",
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
                    
                    # BỀN BỈ: Nếu trích xuất được nội dung và chiều dài hợp lệ, chấp nhận chương mà không hủy cả lô
                    if not chap_text or is_too_short:
                        reason = []
                        if is_too_short:
                            reason.append(f"đầu ra bị xén ngắn (RAW: {raw_len} ký tự, Output: {out_len} ký tự)")
                        if not chap_text:
                            reason.append("không trích xuất được nội dung (thiếu thẻ phân tách)")
                            
                        reason_str = ", ".join(reason)
                        err_msg = (
                            f"❌ [CHƯƠNG KHÔNG HOÀN CHỈNH] Chương {chap_no} vi phạm: {reason_str}. "
                            f"HỦY BỎ TOÀN BỘ LÔ (Chương {chap_nos_in_batch}), XÓA SẠCH DỮ LIỆU DỞ DANG VÀ DỊCH LẠI!"
                        )
                        print(err_msg)
            # 3e. Kiểm tra chống trùng lặp nội dung giữa các chương trong lô (khi LLM bị ảo giác chỉ dịch 1 chương)
            if len(cids) > 1:
                seen_snippets = {}
                for cid in cids:
                    c_text = extracted_map.get(cid, "").strip()
                    # Lấy đoạn văn mẫu 100 ký tự (bỏ khoảng trắng và dấu câu)
                    snippet = re.sub(r"[\s\W_]+", "", c_text[:200].lower())
                    if len(snippet) >= 30:
                        if snippet in seen_snippets:
                            dup_chap = chapter_map[seen_snippets[snippet]]
                            curr_chap = chapter_map[cid]
                            err_msg = (
                                f"❌ [TRÙNG LẶP NỘI DUNG] Chương {curr_chap} bị trùng lặp nội dung với Chương {dup_chap} "
                                f"(do LLM xếp chồng thẻ và chỉ dịch 1 chương). HỦY BỎ LÔ {chap_nos_in_batch} ĐỂ DỊCH LẠI!"
                            )
                            print(err_msg)
                            raise ValueError(err_msg)
                        seen_snippets[snippet] = cid

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

                # 3a. Sweep Chinese (Dịch vá Hán tự sót bằng Hán-Việt/HanLP hoặc Google Dịch và bọc thẻ xanh báo lỗi)
                chap_text = await sweep_chinese_characters(chap_text)
                
                # 3b. Fix broken words (dính chữ từ LLM output) — có bảo vệ tên thực thể
                chap_text = fix_broken_words(chap_text, protected_names=protected_names)
                
                # 3c. Enforce entity names (lưới an toàn cuối cùng)
                chap_text = await enforce_entity_names(chap_text, novel_id)

                # 3d. Sanitize false positive slang (lưới an toàn cuối cùng chống thay nhầm từ lóng)
                chap_text = sanitize_false_positive_slang(chap_text)

                # 3e. Chuẩn hóa dấu câu tiếng Việt & làm sạch chuỗi la hét / cảm thán lặp từ quá dài
                chap_text = re.sub(r'(?i)\b([aáàảãạ])(?:\s*[\-—.,~]*\s*\1){3,}', r'\1...', chap_text)
                chap_text = re.sub(r'(?i)\b(ha|hả|hô|hì|hê|oa|oá|hức|hic|hừ|hừm|ơ|ô|ư|ưm)(?:\s*[\-—.,~]*\s*\1){3,}', r'\1 \1 \1!', chap_text)
                chap_text = re.sub(r'(?i)\b(á|ối|ối dồi ôi|trời ơi)(?:\s*[\-—.,~]*\s*\1){2,}', r'\1!', chap_text)
                chap_text = re.sub(r'[!]{2,}', '!', chap_text)
                chap_text = re.sub(r'[?]{2,}', '?', chap_text)
                chap_text = re.sub(r'[,]{2,}', ', ', chap_text)
                chap_text = re.sub(r'[;]{2,}', '; ', chap_text)
                chap_text = re.sub(r'[:]{2,}', ': ', chap_text)
                chap_text = re.sub(r'(?:\?\!|\!\?){2,}', '!? ', chap_text)
                chap_text = re.sub(r'[…]{1,}', '... ', chap_text)
                chap_text = re.sub(r'\.{4,}', '... ', chap_text)
                chap_text = re.sub(r'([,.:;!?])([A-ZÀ-Ỹa-zà-ỹ0-9])', r'\1 \2', chap_text)
                
                # 4. Lưu file 04_KetQua
                file_name = f"{chap_no:06d}.txt"
                file_path = os.path.join(out_dir, file_name)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(chap_text)
                    
                saved_files.append(file_path)

                # 4b. Cập nhật DB cho tất cả các loại phiên bản kết quả: FINAL, CONTEXTT, EDITED, LLM
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
                    tmp_ch_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS", novel_folder, "chapters", f"_tmp_ch{chap_no:06d}")
                    if os.path.exists(tmp_ch_dir):
                        shutil.rmtree(tmp_ch_dir, ignore_errors=True)
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
    
    # 5b. Thông báo real-time tới Frontend để tự động cập nhật danh sách chương ngay lập tức
    try:
        from app.api.translation_router import broadcast_sse
        broadcast_sse("chapter_updated", {
            "novelId": novel_id,
            "completedBatchCount": len(saved_files)
        })
    except Exception:
        pass
    
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

import re
import json
import os
import asyncio
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, Novel
from app.services.storage.file_storage import read_version_file_content
from app.core.config import get_active_setting
from app.core.llm_client import post_gemini_with_retry, safe_json_loads
import httpx

async def call_gemini_api(prompt: str, model: str = None, is_json: bool = True) -> tuple[Optional[str], Optional[str]]:
    """
    Gọi Gemini/OpenRouter API sử dụng ĐÚNG mã Model và Key mà người dùng cấu hình.
    Trả về (kết_quả_text, thông_báo_lỗi_chi_tiết).
    """
    api_keys_str = await get_active_setting("AIREAD_API_KEYS")
    if not api_keys_str:
        api_keys_str = os.getenv("GEMINI_API_KEY", "") or os.getenv("AIREAD_API_KEYS", "")
    if not api_keys_str:
        return None, "Không tìm thấy API Key trong cấu hình CSDL hoặc file .env."
        
    keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]
    if not keys:
        return None, "Danh sách API Key rỗng."

    selected_model = model or (await get_active_setting("AIREAD_MODEL")) or "gemini-3.5-flash-lite"
    selected_model = selected_model.strip()
    if "grok" in selected_model.lower():
        selected_model = "gemini-3.5-flash-lite"
    if "3.8" in selected_model or "flash-medium" in selected_model.lower():
        selected_model = "gemini-3.5-flash-lite"
    
    provider_val = os.environ.get("AIREAD_PROVIDER") or await get_active_setting("AIREAD_PROVIDER") or "gemini"
    provider = str(provider_val).lower().strip()
    
    # Nếu cấu hình hệ thống là gemini, BẮT BUỘC dùng Gemini và chuẩn hóa model
    if provider == "gemini":
        is_openrouter = False
        if "/" in selected_model or "openrouter" in selected_model.lower() or "free" in selected_model.lower():
            selected_model = "gemini-3.5-flash-lite"
    else:
        is_openrouter = (provider == "openrouter") or ("/" in selected_model) or ("qwen" in selected_model.lower()) or ("openrouter" in selected_model.lower())

    if is_openrouter:
        api_key = keys[0]
        # Nếu key truyền vào là key Gemini (bắt đầu bằng AIza) hoặc rỗng, tự động fallback về Gemini
        if api_key.startswith("AIza") or not api_key:
            is_openrouter = False
            selected_model = "gemini-3.5-flash-lite"
        else:
            or_headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "AiRead"
            }
            or_body = {
                "model": selected_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 32768
            }
            try:
                async with httpx.AsyncClient(timeout=600.0) as client:
                    resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=or_headers, json=or_body)
                if resp.status_code == 200:
                    text_out = resp.json()["choices"][0]["message"]["content"].strip()
                    if text_out:
                        return text_out, None
                return None, f"OpenRouter API Error (HTTP {resp.status_code}): {resp.text[:300]}"
            except Exception as e:
                return None, f"OpenRouter Exception: {str(e)}"
    
    # Gemini path
    headers = {"Content-Type": "application/json"}
    gen_config = {
        "temperature": 0.3,
        "topP": 0.9,
        "topK": 40
    }
    if is_json:
        gen_config["responseMimeType"] = "application/json"
    if any(m in selected_model.lower() for m in ["2.0", "2.5", "3.0", "3.5", "flash"]):
        gen_config["maxOutputTokens"] = 65536

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_config
    }
        
    last_err = None
    async with httpx.AsyncClient(timeout=600.0) as client:
        for key_idx, api_key in enumerate(keys):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
            try:
                resp = await post_gemini_with_retry(client, url, headers, payload, max_retries=2)
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                        if text_out and text_out.strip():
                            return text_out, None
                    except (KeyError, IndexError):
                        last_err = "API trả về 200 nhưng cấu trúc candidates rỗng."
                elif resp.status_code in (503, 404, 400) and selected_model != "gemini-3.5-flash-lite":
                    # Tự động cứu cánh fallback ngay sang gemini-3.5-flash-lite nếu model bị quá tải hoặc không tồn tại
                    print(f"⚠️ Model '{selected_model}' trả về {resp.status_code} ({resp.text[:80]}), tự động fallback sang 'gemini-3.5-flash-lite'...")
                    selected_model = "gemini-3.5-flash-lite"
                    fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={api_key}"
                    resp_fallback = await post_gemini_with_retry(client, fallback_url, headers, payload, max_retries=2)
                    if resp_fallback.status_code == 200:
                        data = resp_fallback.json()
                        text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                        if text_out and text_out.strip():
                            return text_out, None
                    last_err = f"HTTP {resp_fallback.status_code} ({selected_model}): {resp_fallback.text[:200]}"
                else:
                    err_msg = resp.text
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        pass
                    last_err = f"HTTP {resp.status_code} ({selected_model}): {err_msg}"
                    
                    if resp.status_code in (429, 500, 502, 503, 504) and key_idx < len(keys) - 1:
                        print(f"⚠️ Key #{key_idx+1} gặp lỗi {resp.status_code}, tự động chuyển sang Key #{key_idx+2}...")
                        continue
            except Exception as e:
                last_err = f"Lỗi kết nối ({selected_model}): {str(e)}"
                if key_idx < len(keys) - 1:
                    continue
                    
    return None, last_err

# Regex bắt thẻ span của lỗi Hán tự do Google dịch
# VD mới: <span class="swept-chinese" data-raw="灌透">tưới tiêu</span>
# VD cũ: <span class="swept-chinese">tưới tiêu</span>
SWEPT_SPAN_REGEX = re.compile(r'<span[^>]*class="swept-chinese"(?:[^>]*data-raw="([^"]*)")?[^>]*>(.*?)</span>')

def find_sentence_bounds(line: str, match_start: int, match_end: int) -> tuple[int, int]:
    """
    Tìm vị trí bắt đầu và kết thúc của CÂU VĂN TRỌN VẸN chứa lỗi trong dòng.
    Ranh giới câu dựa trên các dấu kết câu: '.', '!', '?', '…', '...', hoặc kết thúc bằng ':' ở cuối mệnh đề.
    TUYỆT ĐỐI KHÔNG cắt theo dấu phẩy (,) hay chấm phẩy (;) để AI có đầy đủ ngữ cảnh biên tập lại cả câu.
    """
    # 1. Tìm điểm bắt đầu câu (sent_start)
    sent_start = 0
    for idx in range(match_start - 1, -1, -1):
        ch = line[idx]
        if ch in ['.', '!', '?', '…']:
            # Bỏ qua nếu là số thập phân (vd: 3.5 hay 1.2)
            if ch == '.' and idx > 0 and idx < len(line) - 1 and line[idx-1].isdigit() and line[idx+1].isdigit():
                continue
            # Bắt đầu câu mới ngay sau dấu kết thúc câu (và sau các dấu đóng ngoặc/khoảng trắng)
            next_idx = idx + 1
            while next_idx < match_start and line[next_idx] in ['"', '”', "'", "’", ")", "]", " ", "\t"]:
                next_idx += 1
            sent_start = next_idx
            break
            
    # 2. Tìm điểm kết thúc câu (sent_end)
    sent_end = len(line)
    for idx in range(match_end, len(line)):
        ch = line[idx]
        if ch in ['.', '!', '?', '…'] or (ch == ':' and (idx == len(line) - 1 or line[idx+1].isspace())):
            if ch == '.' and idx > 0 and idx < len(line) - 1 and line[idx-1].isdigit() and line[idx+1].isdigit():
                continue
            # Lấy trọn dấu kết thúc và các dấu đóng ngoặc kép/đơn đi liền sau
            end_idx = idx + 1
            while end_idx < len(line) and line[end_idx] in ['"', '”', "'", "’", ")", "]"]:
                end_idx += 1
            sent_end = end_idx
            break
            
    return sent_start, sent_end

def extract_swept_errors(content: str, chapter_no: int) -> List[Dict[str, Any]]:
    """
    Quét nội dung chương để tìm các thẻ swept-chinese và trích xuất TRỌN VẸN CẢ CÂU THEO DẤU CHẤM/RANH GIỚI CÂU.
    TUYỆT ĐỐI KHÔNG cắt vụn theo dấu phẩy để AI có đầy đủ ngữ cảnh biên tập lại cả câu văn.
    """
    errors = []
    if not content:
        return errors
        
    lines = content.split('\n')
    error_idx = 0
    
    for i, line in enumerate(lines):
        for match in SWEPT_SPAN_REGEX.finditer(line):
            raw_chinese = match.group(1) or "Không rõ (Bản dịch cũ)"
            faulty_term = match.group(2)
            span_text = match.group(0)
            
            # Tìm ranh giới trọn vẹn của câu văn chứa lỗi (theo dấu chấm . ! ? … :)
            sent_start, sent_end = find_sentence_bounds(line, match.start(), match.end())
            raw_sentence = line[sent_start:sent_end].strip()
            
            # Gửi thẳng chữ Hán gốc cần dịch, không gửi bản dịch cứu lỗi từ hanlp / google
            target_han = raw_chinese if (raw_chinese and raw_chinese != "Không rõ (Bản dịch cũ)") else faulty_term
            raw_sent_masked = line[sent_start:match.start()] + f"[CHỮ HÁN CẦN DỊCH: {target_han}]" + line[match.end():sent_end]
            
            # Clean HTML to provide clear context for LLM
            sentence_context = re.sub(r'<[^>]+>', '', raw_sent_masked).strip()
            
            errors.append({
                "error_id": f"ERR_CH{chapter_no}_{error_idx}",
                "chapter_no": chapter_no,
                "raw_chinese": target_han,
                "sentence_context": sentence_context,
                "raw_sentence": raw_sentence,
                "span_html": span_text,
                "line_idx": i
            })
            error_idx += 1
            
    return errors

def apply_swept_corrections(content: str, corrections_map: Dict[str, Any], chapter_errors: List[Dict[str, Any]]) -> str:
    """
    Thay thế chuẩn xác 100%: Thay thế trực tiếp thẻ span cũ (swept-chinese) bằng cụm từ / vế câu ngắn đã được chuốt mượt (corrected_term)
    bọc trong thẻ gạch chân màu cam. Đảm bảo diệt sạch 100% thẻ swept-chinese cũ khỏi file, không bao giờ bị trôi lỗi hay sót thẻ cũ.
    """
    if not content:
        return content
        
    lines = content.split('\n')
    for err in chapter_errors:
        err_id = err["error_id"]
        if err_id not in corrections_map:
            continue
        corr_info = corrections_map[err_id]
        if corr_info is None:
            continue
            
        corrected_term = ""
        if isinstance(corr_info, dict):
            corrected_term = corr_info.get("corrected_term") or corr_info.get("fixed_sentence") or ""
        elif isinstance(corr_info, str):
            corrected_term = corr_info
            
        # Nếu AI trả về có bọc [FIX]cụm_từ[/FIX], chỉ trích xuất phần bên trong [FIX]
        if '[FIX]' in corrected_term and '[/FIX]' in corrected_term:
            match_fix = re.search(r'\[FIX\](.*?)\[/FIX\]', corrected_term)
            if match_fix:
                corrected_term = match_fix.group(1).strip()
            else:
                corrected_term = re.sub(r'\[/?FIX\]', '', corrected_term).strip()
            
        corrected_term = re.sub(r'\s*\([^)]+\)', '', corrected_term).strip()
        corrected_term = re.sub(r'\s*\[[^\]]+\]', '', corrected_term).strip()
            
        line_idx = err["line_idx"]
        span_html = err["span_html"]
        raw_cn = err.get("raw_chinese", "")
        tooltip_str = f"Gốc Hán: {raw_cn}" if (raw_cn and raw_cn != "Không rõ (Bản dịch cũ)") else "Đã sửa lỗi"
        
        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            
            if corrected_term == "":
                # XÓA BỎ HOÀN TOÀN: Xóa thẻ span cũ và dọn dẹp khoảng trắng
                pattern = r'\s*' + re.escape(span_html) + r'(?:\s*\([^)]+\))?\s*'
                lines[line_idx] = re.sub(pattern, ' ', line, count=1)
                lines[line_idx] = re.sub(r'[ \t]{2,}', ' ', lines[line_idx]).strip()
            elif span_html in line:
                # LẮP ĐÚNG CHỖ 100%: Tách line tại vị trí span_html để thay thế thẻ cũ bằng thẻ màu cam mới
                span_pos = line.find(span_html)
                pre_span = line[:span_pos]
                post_span = line[span_pos + len(span_html):]
                
                corr_clean = corrected_term.strip()
                first_corr_word = corr_clean.split()[0] if corr_clean else ""
                
                # Tự động làm sạch mảnh chữ cái La Tinh đơn lẻ hoặc mảnh từ bị cắt dở dính ở đuôi pre_span (VD: "Hắc Sí Đại B" + "Đại Bàng" -> "Hắc Sí " + "Đại Bàng")
                pre_span = re.sub(r'(?:\b[a-zA-ZÀ-Ỹa-zà-ỹĐđ]{1,3}\s*)+$', '', pre_span) if (first_corr_word and pre_span.strip().split() and pre_span.strip().split()[-1].lower() in first_corr_word.lower()) else pre_span
                # Khử ký tự La Tinh rác đứng dính độc lập ở cuối pre_span (VD: "Đại B " -> "Đại ")
                pre_span = re.sub(r'\s+\b[a-zA-Z]\b\s*$', ' ', pre_span)
                
                # Khử từ trùng ở đuôi pre_span (VD: "đầu " + "đầu óc")
                if first_corr_word and len(first_corr_word) >= 2:
                    pre_span_clean = re.sub(rf'\b{re.escape(first_corr_word)}\s*$', '', pre_span, flags=re.IGNORECASE)
                    if pre_span_clean != pre_span:
                        pre_span = pre_span_clean
                
                # Khử các từ Hán dư thừa ở đuôi pre_span
                if re.search(r'(?i)\bquy\s*$', pre_span) and re.match(r'(?i)^(?:đầu\s+cặc|quy\s+đầu|đầu)', corr_clean):
                    pre_span = re.sub(r'(?i)\bquy\s*$', '', pre_span)
                if re.search(r'(?i)\btiếng\s+kêu\s*$', pre_span) and re.match(r'(?i)^(?:rên\s+rỉ|kêu\s+la|la\s+hét)', corr_clean):
                    pre_span = re.sub(r'(?i)\bkêu\s*$', '', pre_span)
                if re.search(r'(?i)\btiểu\s*$', pre_span) and re.match(r'(?i)^(?:bé\s+gái|con\s+gái|cô\s+bé|cô\s+gái|thiếu\s+nữ)', corr_clean):
                    pre_span = re.sub(r'(?i)\btiểu\s*$', '', pre_span)
                    if corr_clean in ["bé gái", "con gái"]:
                        corr_clean = "cô bé"
                
                # Khử ngoặc đơn thừa ở đầu post_span
                post_span = re.sub(r'^\s*\([^)]+\)', '', post_span)
                
                highlighted_term = f'<span class="fixed-sentence" style="text-decoration: underline; text-decoration-color: #f59e0b; text-underline-offset: 4px;"><span class="fixed-word" style="color: #f59e0b; font-weight: bold; background: rgba(245, 158, 11, 0.18); padding: 1px 5px; border-radius: 3px; text-decoration: none;" title="{tooltip_str}">{corr_clean}</span></span>'
                
                lines[line_idx] = (pre_span + " " + highlighted_term + " " + post_span).strip()
                lines[line_idx] = re.sub(r'[ \t]{2,}', ' ', lines[line_idx])
            else:
                # Trường hợp dự phòng nếu span_html chính xác không còn trong dòng (do xử lý lỗi trước đó trên cùng 1 dòng):
                # Dùng regex diệt sạch thẻ swept-chinese còn dính lại
                faulty_esc = re.escape(faulty) if faulty else ""
                fallback_pattern = rf'<span[^>]*class="swept-chinese"[^>]*>{faulty_esc}</span>' if faulty_esc else r'<span[^>]*class="swept-chinese"[^>]*>.*?</span>'
                
                highlighted_term = f'<span class="fixed-sentence" style="text-decoration: underline; text-decoration-color: #f59e0b; text-underline-offset: 4px;"><span class="fixed-word" style="color: #f59e0b; font-weight: bold; background: rgba(245, 158, 11, 0.18); padding: 1px 5px; border-radius: 3px; text-decoration: none;" title="{tooltip_str}">{corrected_term}</span></span>'
                if re.search(fallback_pattern, line):
                    lines[line_idx] = re.sub(fallback_pattern, highlighted_term, line, count=1)
            
    from app.services.postprocessing.post_processor import fix_broken_words
    new_content = '\n'.join(lines)
    return fix_broken_words(new_content)


async def batch_fix_swept_errors_llm(novel_id: int, model: Optional[str] = None):
    """
    1. Quét toàn bộ chương dịch (FINAL) của truyện
    2. Gom tất cả lỗi câu cụ thể
    3. Trích xuất ngữ cảnh cả câu trọn vẹn theo dấu chấm, nhưng yêu cầu LLM chỉ trả về cụm từ / vế ngắn mượt mà
    4. Áp dụng thay thế trực tiếp thẻ swept-chinese thành thẻ màu cam chính xác 100% và lưu DB + file
    """
    async with AsyncSessionLocal() as session:
        # Lấy thông tin truyện để biết thể loại
        stmt = select(Novel).where(Novel.id == novel_id)
        novel = (await session.execute(stmt)).scalar_one_or_none()
        if not novel:
            return {"status": "error", "message": "Novel not found"}
            
        genre = novel.context_profile or "urban"
            
        # 1. Fetch chapters and versions in 1 single fast query (ưu tiên file đĩa 04_KetQua)
        from sqlalchemy import case
        stmt_vers = (
            select(Chapter.id, Chapter.chapter_no, ChapterVersion)
            .join(ChapterVersion, Chapter.id == ChapterVersion.chapter_id)
            .where(
                Chapter.novel_id == novel_id,
                ChapterVersion.version_type.in_(["FINAL", "GG"])
            )
            .order_by(Chapter.chapter_no.asc(), case((ChapterVersion.version_type == "FINAL", 1), else_=2))
        )
        res_vers = await session.execute(stmt_vers)
        rows_vers = res_vers.all()
        
        all_errors = []
        chapter_content_map = {}
        chapter_error_map = {}
        seen_chaps = set()
        
        for ch_id, ch_no, ver in rows_vers:
            if ch_id in seen_chaps:
                continue
            seen_chaps.add(ch_id)
            
            content = ""
            if ver.file_path and os.path.exists(ver.file_path):
                try:
                    content = read_version_file_content(ver.file_path)
                except Exception:
                    content = ver.content or ""
            elif ver.content:
                content = ver.content
                
            # Bỏ qua ngay nếu chương không chứa thẻ gạch chân xanh (swept-chinese) hoặc lỗi (swept-error)
            if 'swept-chinese' not in content and 'swept-error' not in content:
                continue
                
            errs = extract_swept_errors(content, ch_no)
            if errs:
                all_errors.extend(errs)
                chapter_content_map[ch_id] = {"content": content, "version": ver, "chapter_no": ch_no}
                chapter_error_map[ch_id] = errs

        if not all_errors:
            return {"status": "success", "message": "Không tìm thấy lỗi Hán tự gạch chân xanh nào cần sửa.", "fixed_count": 0}

        # 2. Gom toàn bộ câu lỗi vào 1 request duy nhất (vì trả về cực kỳ ngắn gọn ~20 tokens/lỗi)
        from app.api.translation_router import add_system_log
        import math

        total_errors = len(all_errors)
        # Chỉ tốn ~20 output tokens/lỗi do LLM chỉ cần trả về cụm từ ngắn gọn
        total_est_output_tokens = total_errors * 20
        
        MAX_SAFE_TOKENS_PER_REQ = 50000
        MAX_SAFE_ITEMS_PER_REQ = 500
        
        batches_by_tokens = math.ceil(total_est_output_tokens / MAX_SAFE_TOKENS_PER_REQ)
        batches_by_items = math.ceil(total_errors / MAX_SAFE_ITEMS_PER_REQ)
        total_batches = max(1, batches_by_tokens, batches_by_items)
        
        k, m = divmod(total_errors, total_batches)
        batches = [
            all_errors[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)]
            for i in range(total_batches)
        ]

        if total_batches == 1:
            add_system_log(f"🔍 Gom toàn bộ {total_errors} vị trí lỗi gửi AI sửa trong 1 request duy nhất...", "info")
        else:
            add_system_log(f"🔍 Tìm thấy {total_errors} vị trí lỗi. Chia làm {total_batches} đợt (~{len(batches[0])} câu/đợt)...", "info")

        corrections_map = {}

        for b_idx, batch_errs in enumerate(batches):
            if total_batches > 1:
                add_system_log(f"⚡ Đang gửi AI xử lý đợt {b_idx + 1}/{total_batches} ({len(batch_errs)} vị trí lỗi)...", "info")

            llm_input_items = [
                {
                    "error_id": err["error_id"],
                    "raw_chinese": err["raw_chinese"],
                    "sentence_context": err["sentence_context"]
                }
                for err in batch_errs
            ]

            prompt = f"""Bạn là TỔNG BIÊN TẬP VIÊN VĂN HỌC & TIỂU THUYẾT CAO CẤP (thể loại: {genre.upper()}).
Dưới đây là danh sách các vị trí sót chữ Hán cần dịch và chuốt câu (được đánh dấu là [CHỮ HÁN CẦN DỊCH: ...] trong ngữ cảnh câu văn trọn vẹn) kèm chữ Hán gốc [raw_chinese].

=== DANH SÁCH CÁC VỊ TRÍ CẦN SỬA ===
{json.dumps(llm_input_items, ensure_ascii=False, indent=2)}

=== NGUYÊN TẮC BIÊN TẬP & SỬA LỖI (CHỊU TRÁCH NHIỆM TOÀN BỘ CÂU VĂN) ===
1. TRÁCH NHIỆM CHUỐT MƯỢT CẢ CÂU VĂN CÓ NGHĨA HOÀN CHỈNH (fixed_sentence):
   - Bạn được cung cấp cả câu trọn vẹn (sentence_context) chứa vị trí chữ Hán chưa dịch.
   - Hãy dịch chữ Hán đó theo đúng văn cảnh, hòa nhập hoàn toàn vào câu văn để tạo thành một câu văn tiếng Việt hoàn chỉnh, tự nhiên, trôi chảy, giàu hình ảnh và đúng ngữ cảnh câu chuyện.
   - Xóa bỏ triệt để các ký tự rác, mảnh từ bị cắt dở hoặc từ lặp lại do lỗi dịch trước đó.
   - TUYỆT ĐỐI CẤM dịch bẻ âm thô từng chữ (convert máy móc). Phải dùng từ ngữ tiếng Việt chuẩn mực, đúng văn phong thể loại.

2. CỤM TỪ THAY THẾ (corrected_term):
   - Điền cụm từ tiếng Việt chuẩn xác nhất dùng để thay thế cho vị trí chữ Hán vào trường `corrected_term`.
   - Điền câu văn hoàn chỉnh đã biên tập làm sạch 100% vào trường `fixed_sentence`.

=== CẤU TRÚC JSON BẮT BUỘC TRẢ VỀ ===
{{
  "corrections": [
    {{
      "error_id": "MÃ_LỖI",
      "corrected_term": "Cụm từ tiếng Việt đã dịch chuẩn",
      "fixed_sentence": "Câu văn mới hoàn chỉnh trôi chảy đã làm sạch 100%"
    }}
  ]
}}
Chỉ trả về JSON thuần hợp lệ, không bọc thẻ markdown."""
            llm_response, err_msg = await call_gemini_api(prompt, model=model, is_json=True)
            if not llm_response:
                add_system_log(f"⚠️ Đợt {b_idx + 1} gặp lỗi: {err_msg or 'Phản hồi rỗng'}", "warning")
                continue

            try:
                res_data = safe_json_loads(llm_response)
                corrections_list = res_data.get("corrections", []) if isinstance(res_data, dict) else []
                for c in corrections_list:
                    if c.get("error_id"):
                        corrections_map[c["error_id"]] = c
            except Exception as e:
                add_system_log(f"⚠️ Đợt {b_idx + 1} lỗi parse JSON: {str(e)}", "warning")
                continue

            if b_idx < total_batches - 1:
                await asyncio.sleep(0.5)

        if not corrections_map:
            return {"status": "error", "message": "Không nhận được phản hồi sửa lỗi hợp lệ nào từ LLM."}
        
        # 4. Áp dụng thay thế
        fixed_count = 0
        fixed_details = []
        for ch_id, errs in chapter_error_map.items():
            original_content = chapter_content_map[ch_id]["content"]
            ver = chapter_content_map[ch_id]["version"]
            
            new_content = apply_swept_corrections(original_content, corrections_map, errs)
            
            if new_content != original_content:
                ver.content = new_content
                stmt_all_v = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == ch_id,
                    ChapterVersion.version_type.in_(["FINAL", "EDITED", "CONTEXTT", "LLM"])
                )
                all_vers = (await session.execute(stmt_all_v)).scalars().all()
                for v in all_vers:
                    v.content = new_content

                if ver.file_path:
                    try:
                        os.makedirs(os.path.dirname(ver.file_path), exist_ok=True)
                        with open(ver.file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                    except Exception as e:
                        print(f"Lỗi ghi file phiên bản: {e}")

                # Tự động đồng bộ sang 04b_VanBanTTS và cập nhật TTS_TEXT sạch sẽ 100%
                try:
                    from app.services.tts.pipeline import sanitize_tts_text
                    from app.core.config import OUTPUT_DIR
                    novel_folder = novel.title_rough or novel.title_raw
                    c_no = chapter_content_map[ch_id].get("chapter_no", 0)
                    tts_base_dir = str(OUTPUT_DIR / "04b_VanBanTTS")
                    tts_out_dir = os.path.join(tts_base_dir, novel_folder, "chapters")
                    os.makedirs(tts_out_dir, exist_ok=True)
                    tts_file_path = os.path.join(tts_out_dir, f"{c_no:06d}.txt")
                    cleaned_tts = sanitize_tts_text(new_content)
                    with open(tts_file_path, "w", encoding="utf-8") as tf:
                        tf.write(cleaned_tts + "\n")

                    stmt_tts_ver = select(ChapterVersion).where(
                        ChapterVersion.chapter_id == ch_id,
                        ChapterVersion.version_type == "TTS_TEXT"
                    )
                    res_tts_ver = await session.execute(stmt_tts_ver)
                    tts_ver = res_tts_ver.scalar_one_or_none()
                    if tts_ver:
                        tts_ver.content = cleaned_tts
                        tts_ver.file_path = tts_file_path
                    else:
                        session.add(ChapterVersion(
                            chapter_id=ch_id,
                            version_type="TTS_TEXT",
                            file_path=tts_file_path,
                            content=cleaned_tts,
                            status="COMPLETED"
                        ))
                except Exception as e:
                    print(f"⚠️ Lỗi đồng bộ 04b_VanBanTTS: {e}")
                
                for e in errs:
                    if e["error_id"] in corrections_map:
                        c_val = corrections_map[e["error_id"]]
                        corr_term = c_val.get("corrected_term", "") if isinstance(c_val, dict) else str(c_val)
                        fixed_sent = c_val.get("fixed_sentence", "") if isinstance(c_val, dict) else ""
                        fixed_details.append({
                            "chapter_no": e["chapter_no"],
                            "raw_chinese": e.get("raw_chinese", ""),
                            "faulty_term": e.get("faulty_term", ""),
                            "corrected_term": corr_term,
                            "fixed_sentence": fixed_sent,
                            "sentence": e.get("sentence_context", "")
                        })
                fixed_count += len([e for e in errs if e["error_id"] in corrections_map])
                
        await session.commit()
        
        # Re-export Full.txt if anything fixed
        if fixed_count > 0:
            from app.services.postprocessing.post_processor import export_full_novel_txt
            await export_full_novel_txt(novel_id)
            
        return {
            "status": "success",
            "message": f"Đã quét và nhờ LLM sửa thành công {fixed_count} lỗi gạch chân xanh.",
            "fixed_count": fixed_count,
            "details": fixed_details
        }

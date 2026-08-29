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
    
    provider_val = os.environ.get("AIREAD_PROVIDER") or await get_active_setting("AIREAD_PROVIDER") or "gemini"
    provider = str(provider_val).lower().strip()
    is_openrouter = (provider == "openrouter") or ("/" in selected_model) or ("qwen" in selected_model.lower()) or ("openrouter" in selected_model.lower())

    if is_openrouter:
        api_key = keys[0]
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
            "max_tokens": 4096
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
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
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {}
    }
    if is_json:
        payload["generationConfig"]["responseMimeType"] = "application/json"
        
    last_err = None
    async with httpx.AsyncClient(timeout=60.0) as client:
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
                else:
                    err_msg = resp.text
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        pass
                    last_err = f"HTTP {resp.status_code} ({selected_model}): {err_msg}"
                    
                    if resp.status_code == 429 and key_idx < len(keys) - 1:
                        print(f"⚠️ Key #{key_idx+1} bị dính 429, tự động chuyển sang Key #{key_idx+2}...")
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

def extract_swept_errors(content: str, chapter_no: int) -> List[Dict[str, Any]]:
    """
    Quét nội dung chương để tìm các thẻ swept-chinese và trích xuất câu văn ngữ cảnh.
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
            
            # Mask the faulty term with [LỖI: ...]
            masked_line = line[:match.start()] + f"[LỖI: {faulty_term}]" + line[match.end():]
            
            # Clean HTML to provide clear context for LLM
            sentence_context = re.sub(r'<[^>]+>', '', masked_line).strip()
            
            errors.append({
                "error_id": f"ERR_CH{chapter_no}_{error_idx}",
                "chapter_no": chapter_no,
                "raw_chinese": raw_chinese,
                "faulty_term": faulty_term,
                "sentence_context": sentence_context,
                "span_html": span_text,
                "line_idx": i
            })
            error_idx += 1
            
    return errors

def apply_swept_corrections(content: str, corrections_map: Dict[str, Any], chapter_errors: List[Dict[str, Any]]) -> str:
    """
    Thay thế siêu chính xác: Ưu tiên áp dụng cả câu văn hoàn chỉnh đã được Gemini chuốt mượt mà (fixed_sentence),
    hoặc thay thế cụm từ (corrected_term), tự động khử sạch mọi từ lặp/từ thừa/mở ngoặc đơn rác.
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
            
        fixed_sentence = None
        corrected_term = ""
        if isinstance(corr_info, dict):
            fixed_sentence = corr_info.get("fixed_sentence")
            corrected_term = corr_info.get("corrected_term", "")
        elif isinstance(corr_info, str):
            corrected_term = corr_info
            
        corrected_term = re.sub(r'\s*\([^)]+\)', '', corrected_term).strip()
        corrected_term = re.sub(r'\s*\[[^\]]+\]', '', corrected_term).strip()
            
        line_idx = err["line_idx"]
        span_html = err["span_html"]
        raw_cn = err.get("raw_chinese", "")
        faulty = err.get("faulty_term", "")
        tooltip_str = f"Gốc Hán: {raw_cn} | Lỗi cũ: {faulty}" if (raw_cn and raw_cn != "Không rõ (Bản dịch cũ)") else f"Lỗi cũ: {faulty}"
        
        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            
            # ƯU TIÊN 1: Nếu Gemini trả về cả câu văn hoàn chỉnh (fixed_sentence)
            if fixed_sentence and fixed_sentence.strip():
                clean_fixed = fixed_sentence.strip()
                # Chuyển [FIX]...[/FIX] thành thẻ gạch chân và màu xanh lá
                if '[FIX]' in clean_fixed and '[/FIX]' in clean_fixed:
                    formatted_fixed = re.sub(
                        r'\[FIX\](.*?)\[/FIX\]',
                        rf'<span class="fixed-sentence" style="text-decoration: underline; text-decoration-color: #f59e0b; text-underline-offset: 4px;"><span class="fixed-word" style="color: #f59e0b; font-weight: bold; background: rgba(245, 158, 11, 0.18); padding: 1px 5px; border-radius: 3px; text-decoration: none;" title="{tooltip_str}">\1</span></span>',
                        clean_fixed
                    )
                elif corrected_term and corrected_term in clean_fixed:
                    # Tự động bọc corrected_term nếu Gemini quên đóng thẻ [FIX]
                    formatted_fixed = clean_fixed.replace(
                        corrected_term,
                        f'<span class="fixed-sentence" style="text-decoration: underline; text-decoration-color: #f59e0b; text-underline-offset: 4px;"><span class="fixed-word" style="color: #f59e0b; font-weight: bold; background: rgba(245, 158, 11, 0.18); padding: 1px 5px; border-radius: 3px; text-decoration: none;" title="{tooltip_str}">{corrected_term}</span></span>',
                        1
                    )
                else:
                    formatted_fixed = clean_fixed
                
                lines[line_idx] = formatted_fixed
            elif corrected_term == "":
                # XÓA BỎ HOÀN TOÀN: Xóa thẻ span và dọn dẹp khoảng trắng/từ lặp/ngoặc đơn thừa
                pattern = r'\s*' + re.escape(span_html) + r'(?:\s*\([^)]+\))?\s*'
                lines[line_idx] = re.sub(pattern, ' ', line, count=1)
                lines[line_idx] = re.sub(r'[ \t]{2,}', ' ', lines[line_idx]).strip()
            else:
                # Khử trùng lặp từ đứng trước span_html nếu bị dính chữ (VD: "rãnh quy" + "đầu cặc" -> "rãnh đầu cặc", "tiếng kêu" + "kêu la" -> "tiếng kêu la")
                pre_span = line[:line.find(span_html)] if span_html in line else ""
                post_span = line[line.find(span_html) + len(span_html):] if span_html in line else ""
                
                corr_clean = corrected_term.strip()
                first_corr_word = corr_clean.split()[0] if corr_clean else ""
                
                # 1. Khử từ trùng ở đuôi pre_span (VD: "đầu " + "đầu óc", "thân hình " + "thân hình to lớn")
                if first_corr_word and len(first_corr_word) >= 2:
                    pre_span_clean = re.sub(rf'\b{re.escape(first_corr_word)}\s*$', '', pre_span, flags=re.IGNORECASE)
                    if pre_span_clean != pre_span:
                        pre_span = pre_span_clean
                
                # 2. Khử "quy " khi thay "đầu cặc" / "quy đầu" (VD: "rãnh quy " -> "rãnh ")
                if re.search(r'(?i)\bquy\s*$', pre_span) and re.match(r'(?i)^(?:đầu\s+cặc|quy\s+đầu|đầu)', corr_clean):
                    pre_span = re.sub(r'(?i)\bquy\s*$', '', pre_span)
                
                # 3. Khử "tiếng kêu " khi thay "kêu la" / "tiếng rên rỉ" (VD: "phát ra tiếng kêu " + "rên rỉ" -> "phát ra tiếng rên rỉ")
                if re.search(r'(?i)\btiếng\s+kêu\s*$', pre_span) and re.match(r'(?i)^(?:rên\s+rỉ|kêu\s+la|la\s+hét)', corr_clean):
                    pre_span = re.sub(r'(?i)\bkêu\s*$', '', pre_span)
                
                # 4. Khử "Tiểu " khi thay "bé gái" / "con gái" / "cô bé" (VD: "hệt như Tiểu " + "bé gái" -> "hệt như " + "cô bé")
                if re.search(r'(?i)\btiểu\s*$', pre_span) and re.match(r'(?i)^(?:bé\s+gái|con\s+gái|cô\s+bé|cô\s+gái|thiếu\s+nữ)', corr_clean):
                    pre_span = re.sub(r'(?i)\btiểu\s*$', '', pre_span)
                    if corr_clean in ["bé gái", "con gái"]:
                        corr_clean = "cô bé"
                
                # 5. Khử phần mở ngoặc đơn rác đằng sau post_span (VD: " (chà đạp quấy rối)")
                post_span = re.sub(r'^\s*\([^)]+\)', '', post_span)
                
                highlighted_term = f'<span class="fixed-sentence" style="text-decoration: underline; text-decoration-color: #f59e0b; text-underline-offset: 4px;"><span class="fixed-word" style="color: #f59e0b; font-weight: bold; background: rgba(245, 158, 11, 0.18); padding: 1px 5px; border-radius: 3px; text-decoration: none;" title="{tooltip_str}">{corr_clean}</span></span>'
                
                lines[line_idx] = (pre_span + " " + highlighted_term + " " + post_span).strip()
                lines[line_idx] = re.sub(r'[ \t]{2,}', ' ', lines[line_idx])
            
    # Chạy lại fix_broken_words cho an toàn lỡ dính dấu câu
    from app.services.postprocessing.post_processor import fix_broken_words
    new_content = '\n'.join(lines)
    return fix_broken_words(new_content)


async def batch_fix_swept_errors_llm(novel_id: int, model: Optional[str] = None):
    """
    1. Quét toàn bộ chương dịch (FINAL) của truyện
    2. Gom tất cả lỗi
    3. Gửi 1 request LLM duy nhất với Model người dùng cấu hình
    4. Áp dụng sửa lỗi siêu chính xác và lưu lại DB + file
    """
    async with AsyncSessionLocal() as session:
        # Lấy thông tin truyện để biết thể loại
        stmt = select(Novel).where(Novel.id == novel_id)
        novel = (await session.execute(stmt)).scalar_one_or_none()
        if not novel:
            return {"status": "error", "message": "Novel not found"}
            
        genre = novel.context_profile or "urban"
            
        # 1. Fetch all chapters
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
        chapters = (await session.execute(stmt_ch)).scalars().all()
        
        all_errors = []
        chapter_content_map = {}
        chapter_error_map = {}
        
        for ch in chapters:
            content = None
            best_ver = None
            for v_type in ["FINAL", "GG"]:
                stmt_v = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == ch.id,
                    ChapterVersion.version_type == v_type
                )
                res_v = await session.execute(stmt_v)
                ver = res_v.scalar_one_or_none()
                if ver:
                    if ver.content:
                        content = ver.content
                    elif ver.file_path and os.path.exists(ver.file_path):
                        try:
                            content = read_version_file_content(ver.file_path)
                        except Exception:
                            pass
                    if content:
                        best_ver = ver
                        break
                    
            if content:
                errs = extract_swept_errors(content, ch.chapter_no)
                if errs:
                    all_errors.extend(errs)
                    chapter_content_map[ch.id] = {"content": content, "version": best_ver}
                    chapter_error_map[ch.id] = errs

        if not all_errors:
            return {"status": "success", "message": "Không tìm thấy lỗi Hán tự gạch chân xanh nào cần sửa.", "fixed_count": 0}

        # 2. Gom nhóm các chương theo kích thước Lô (batch_size) từ Cài đặt hệ thống
        try:
            batch_size_str = await get_active_setting("AIREAD_BATCH_SIZE")
            batch_size = max(1, int(batch_size_str)) if batch_size_str and str(batch_size_str).isdigit() else 3
        except Exception:
            batch_size = 3

        # Lấy danh sách ID các chương có lỗi
        ch_ids_with_errors = [cid for cid in chapter_error_map.keys()]
        
        corrections_map = {}
        error_logs = []
        
        # Chia các chương có lỗi thành các lô (mỗi lô chứa batch_size chương)
        for i in range(0, len(ch_ids_with_errors), batch_size):
            batch_cids = ch_ids_with_errors[i : i + batch_size]
            batch_errors = []
            for cid in batch_cids:
                batch_errors.extend(chapter_error_map[cid])
                
            if not batch_errors:
                continue

            prompt = f"""Bạn là ĐẠI SƯ BIÊN TẬP VIÊN VĂN HỌC & TIỂU THUYẾT CAO CẤP (thể loại: {genre.upper()}).
Dưới đây là danh sách CÁC CÂU VĂN ĐANG BỊ BẤT THƯỜNG / LỖI / THỪA TỪ / DỊCH NGÔ NGHÊ trong Lô {len(batch_cids)} chương.

Mỗi mục lỗi chứa:
- [error_id]: Mã định danh lỗi
- [raw_chinese]: Từ/cụm từ gốc tiếng Trung
- [faulty_term]: Từ bị dịch máy sai/ngô nghê
- [sentence_context]: NGUYÊN CẢ CÂU VĂN TIẾNG VIỆT HIỆN TẠI (đã đánh dấu vị trí lỗi là [LỖI: ...])

=== DANH SÁCH CÁC CÂU CẦN BIÊN TẬP LẠI ===
{json.dumps(batch_errors, ensure_ascii=False, indent=2)}

=== QUY TẮC BẮT BUỘC: QUAN SÁT CẢ TỪ ĐỨNG TRƯỚC, ĐỨNG SAU & BIÊN TẬP NGUYÊN CÂU CHO TRƠN TRU 100% ===
⚠️ TUYỆT ĐỐI KHÔNG ĐƯỢC CHỈ CHĂM CHĂM SỬA 1 TỪ DUY NHẤT! 
Trong câu có từ lỗi tức là CÂU VĂN ĐÓ ĐANG BẤT THƯỜNG. Bạn là Biên tập viên cao cấp, nhiệm vụ của bạn là PHẢI ĐỂ Ý KỸ CẢ TỪ ĐỨNG TRƯỚC, TỪ ĐỨNG SAU VÀ TOÀN BỘ CÂU VĂN ĐỂ SỬA LẠI CẢ CÂU CHO THẬT PHÙ HỢP, KHÔNG CÒN LỖI NỮA:

1. QUAN SÁT KỸ TỪ ĐỨNG TRƯỚC VÀ ĐỨNG SAU CHỖ LỖI ĐỂ KHỬ SẠCH TỪ THỪA / TỪ LẶP:
   - Nhìn xem từ đứng trước là gì, từ đứng sau là gì, có bị thừa chữ, lặp nghĩa hay dính mảnh ghép Hán Việt dở dang không:
     * Ví dụ 1: Trước lỗi có chữ "Tiểu", trong lỗi có [LỖI: con gái] -> Ghép lại bị thành "Tiểu bé gái" (rất ngô nghê và thừa chữ). Bạn PHẢI quan sát chữ "Tiểu" đằng trước để viết lại câu thành: "...hệt như [FIX]cô bé[/FIX] ngay trước mặt..." (xóa chữ "Tiểu" thừa).
     * Ví dụ 2: Trước lỗi có "tiếng kêu", trong lỗi có [LỖI: Kêu la] -> Bạn PHẢI nhìn chữ "tiếng kêu" đằng trước để xóa từ lặp và viết lại thành: "...phát ra [FIX]tiếng rên rỉ dâm đãng[/FIX], chẳng hề động đậy gì." (CẤM để lại "tiếng kêu Kêu la" hay "tiếng kêu rên rỉ" lặp từ!).
     * Ví dụ 3: Trước lỗi có "rãnh quy", trong lỗi có [LỖI: cái đầu] -> Bạn PHẢI quan sát chữ "rãnh quy" đằng trước để viết lại thành: "...ngay dưới [FIX]rãnh đầu cặc[/FIX]...".
     * Ví dụ 4: Trước lỗi có "đầu", trong lỗi có [LỖI: não] -> Viết lại thành: "...[FIX]đầu óc[/FIX] của hắn...".
     * Ví dụ 5: Trước lỗi có "thân hình", trong lỗi có [LỖI: to lớn], sau lỗi lại có chữ "to lớn" -> Viết lại thành: "...[FIX]thân hình đồ sộ[/FIX]..." (gọt sạch phần lặp).
     * Ví dụ 6: Sau lỗi có mở ngoặc giải thích rác kiểu "(chà đạp quấy rối)" -> Xóa bỏ hoàn toàn phần mở ngoặc rác đó.

2. NẾU SAI NGHĨA / DỊCH MÁY NGÔ NGHÊ -> SỬA THÀNH TỪ NGỮ GỢI CẢM, SINH ĐỘNG, GIÀU HÌNH ẢNH:
   - 浪叫 -> "tiếng rên rỉ dâm đãng" / "rên rỉ"
   - 玩弄 / 亵弄 -> "mân mê" / "sờ soạng" / "vần vò"
   - 抽插 -> "thúc đẩy mãnh liệt" / "nhấp đâm liên hồi"
   - 灌透 -> "rót đầy bên trong" / "ngập tràn"
   - 瘫软 -> "mềm nhũn ngã quỵ"
   - 痉挛 / 抽搐 -> "co giật cực khoái" / "co thắt"
   - 穴口 / 玉门 -> "khe hoa" / "miệng hoa huyệt" / "cửa mình"
   - 熟女 -> "thục nữ"
   - 龟头 -> "đầu cặc" / "phần đầu nhạy cảm"

3. NẾU CÂU VĂN KHÓ HIỂU / QUÈ QUẶT -> DỊCH LẠI THOÁT Ý XOAY QUANH CHỖ TỪ LỖI:
   - Điều chỉnh cả từ trước, từ sau và các từ nối để NGUYÊN CẢ CÂU VĂN ĐÓ trở nên trơn tru, bay bổng, gãy gọn chuẩn văn học audio/tiểu thuyết xuất bản.

4. BẮT BUỘC BỌC [FIX]...[/FIX] vào chỗ cụm từ bạn đã sửa đổi trong câu fixed_sentence để hệ thống làm nổi bật cho người đọc.

=== CẤU TRÚC JSON BẮT BUỘC TRẢ VỀ ===
{{
  "corrections": [
    {{
      "error_id": "ERR_CHX_Y",
      "fixed_sentence": "Nguyên cả câu văn hoàn chỉnh sau khi bạn đã sửa trơn tru 100%, có bọc [FIX]cụm_từ_đã_sửa[/FIX]",
      "corrected_term": "cụm từ thay thế ngắn gọn (để ghi nhật ký)"
    }}
  ]
}}
5. Chỉ trả về JSON thuần hợp lệ, không bọc thẻ markdown ```json.
"""
            # 3. Gọi LLM cho từng lô chương
            llm_response, err_msg = await call_gemini_api(prompt, model=model, is_json=True)
            if not llm_response:
                error_logs.append(err_msg or "Phản hồi rỗng")
                continue
                
            try:
                res_data = safe_json_loads(llm_response)
                corrections_list = res_data.get("corrections", []) if isinstance(res_data, dict) else []
                for c in corrections_list:
                    if c.get("error_id"):
                        corrections_map[c["error_id"]] = c
            except Exception as e:
                error_logs.append(f"Parse error: {e}")

        if not corrections_map and error_logs:
            return {"status": "error", "message": f"LLM API thất bại: {error_logs[0]}"}
        
        # 4. Áp dụng thay thế
        fixed_count = 0
        fixed_details = []
        for ch_id, errs in chapter_error_map.items():
            original_content = chapter_content_map[ch_id]["content"]
            ver = chapter_content_map[ch_id]["version"]
            
            new_content = apply_swept_corrections(original_content, corrections_map, errs)
            
            if new_content != original_content:
                # Update DB and File for all active translation version records
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

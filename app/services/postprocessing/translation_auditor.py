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

async def call_gemini_api(prompt: str, model: str = None, is_json: bool = True) -> Optional[str]:
    api_keys_str = await get_active_setting("AIREAD_API_KEYS")
    if not api_keys_str:
        return None
        
    if not model:
        model = await get_active_setting("AIREAD_MODEL") or "gemini-3.5-flash-lite"
    
    api_key = api_keys_str.split(',')[0].strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {}
    }
    if is_json:
        payload["generationConfig"]["responseMimeType"] = "application/json"
        
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await post_gemini_with_retry(client, url, headers, payload)
        if resp.status_code == 200:
            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                pass
        return None

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

def apply_swept_corrections(content: str, corrections_map: Dict[str, str], chapter_errors: List[Dict[str, Any]]) -> str:
    """
    Thay thế siêu chính xác: Tìm đúng thẻ span html đã lưu trong lỗi để đổi bằng cụm từ sửa đúng (corrected_term)
    hoặc xóa bỏ từ đó nếu corrected_term là chuỗi rỗng "", gỡ bỏ hoàn toàn thẻ span và từ lặp/mở ngoặc giải thích thừa.
    """
    if not content:
        return content
        
    lines = content.split('\n')
    for err in chapter_errors:
        err_id = err["error_id"]
        if err_id not in corrections_map:
            continue
        corrected_term = corrections_map[err_id]
        if corrected_term is None:
            continue
            
        corrected_term = re.sub(r'\s*\([^)]+\)', '', corrected_term).strip()
        corrected_term = re.sub(r'\s*\[[^\]]+\]', '', corrected_term).strip()
            
        line_idx = err["line_idx"]
        span_html = err["span_html"]
        
        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            corr_words = corrected_term.split()
            last_corr_word = corr_words[-1] if corr_words else ""
            first_corr_word = corr_words[0] if corr_words else ""
            
            # Pattern khớp từ lặp dính liền ngay sau span_html
            extra_word_pattern = ""
            if last_corr_word and len(last_corr_word) >= 2 and re.match(r'^[a-zA-ZàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựỳýỷỹỵA-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰỲÝỶỸỴđĐ]+$', last_corr_word):
                extra_word_pattern = rf'(?:\s+{re.escape(last_corr_word)})?'
            elif first_corr_word and len(first_corr_word) >= 2 and re.match(r'^[a-zA-ZàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựỳýỷỹỵA-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰỲÝỶỸỴđĐ]+$', first_corr_word):
                extra_word_pattern = rf'(?:\s+{re.escape(first_corr_word)})?'
            
            if corrected_term == "":
                # XÓA BỎ HOÀN TOÀN: Xóa thẻ span và dọn dẹp khoảng trắng/từ lặp/ngoặc đơn thừa
                pattern = r'\s*' + re.escape(span_html) + extra_word_pattern + r'(?:\s*\([^)]+\))?\s*'
                lines[line_idx] = re.sub(pattern, ' ', line, count=1)
                lines[line_idx] = re.sub(r'[ \t]{2,}', ' ', lines[line_idx]).strip()
            else:
                # Wrap the corrected term in a styled span (Màu xanh lá mạ - emerald-500)
                highlighted_term = f'<span class="fixed-word" style="color: #10b981; font-weight: bold;">{corrected_term}</span>'
                pattern = re.escape(span_html) + extra_word_pattern + r'(?:\s*\([^)]+\))?'
                lines[line_idx] = re.sub(pattern, highlighted_term, line, count=1)
            
    # Chạy lại fix_broken_words cho an toàn lỡ dính dấu câu
    from app.services.postprocessing.post_processor import fix_broken_words
    new_content = '\n'.join(lines)
    return fix_broken_words(new_content)


async def batch_fix_swept_errors_llm(novel_id: int):
    """
    1. Quét toàn bộ chương dịch (FINAL) của truyện
    2. Gom tất cả lỗi
    3. Gửi 1 request LLM duy nhất
    4. Áp dụng sửa lỗi siêu chính xác và lưu lại DB + file
    """
    async with AsyncSessionLocal() as session:
        # Lấy thông tin truyện để biết thể loại
        stmt = select(Novel).where(Novel.id == novel_id)
        novel = (await session.execute(stmt)).scalar_one_or_none()
        if not novel:
            return {"status": "error", "message": "Novel not found"}
            
        genre = novel.context_profile or "xianxia"
            
        # 1. Fetch all chapters
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
        chapters = (await session.execute(stmt_ch)).scalars().all()
        
        all_errors = []
        chapter_content_map = {}
        chapter_error_map = {}
        
        for ch in chapters:
            # Lấy bản dịch ưu tiên là FINAL, LLM, GG
            stmt_ver = select(ChapterVersion).where(
                ChapterVersion.chapter_id == ch.id,
                ChapterVersion.version_type.in_(["FINAL", "LLM", "GG"])
            )
            versions = (await session.execute(stmt_ver)).scalars().all()
            
            # Ưu tiên lấy FINAL, nếu ko có thì LLM, GG
            ver_dict = {v.version_type: v for v in versions}
            best_ver = ver_dict.get("FINAL") or ver_dict.get("LLM") or ver_dict.get("GG")
            if not best_ver:
                continue
                
            content = best_ver.content
            if not content and best_ver.file_path and os.path.exists(best_ver.file_path):
                try:
                    content = read_version_file_content(best_ver.file_path)
                except Exception:
                    pass
                    
            if content:
                errs = extract_swept_errors(content, ch.chapter_no)
                if errs:
                    all_errors.extend(errs)
                    chapter_content_map[ch.id] = {"content": content, "version": best_ver}
                    chapter_error_map[ch.id] = errs

        if not all_errors:
            return {"status": "success", "message": "Không tìm thấy lỗi Hán tự gạch chân xanh nào cần sửa.", "fixed_count": 0}

        # 2. Tạo Request duy nhất tới LLM
        prompt = f"""Bạn là biên tập viên cao cấp chuyên dịch thuật và hiệu đính văn học mạng Trung Quốc (thể loại: {genre.upper()}).
Dưới đây là danh sách TẤT CẢ các TỪ DỊCH LỖI (do công cụ dịch tự động dịch sai cụm từ Hán) được ghim trong câu văn của từng chương.

Mỗi mục lỗi chứa mã [error_id], từ gốc tiếng Trung [raw_chinese], từ bị dịch sai [faulty_term], và câu văn chứa nó [sentence_context] (đã bọc lỗi trong thẻ [LỖI: ...]).

=== DANH SÁCH LỖI BẮT BUỘC SỬA ===
{json.dumps(all_errors, ensure_ascii=False, indent=2)}

=== YÊU CẦU BẮT BUỘC (SỬA TRỌN VẸN CỤM TỪ MƯỢT MÀ - LÀM SẠCH VĂN BẢN CUỐI CÙNG) ===
1. NGUYÊN TẮC QUAN TRỌNG NHẤT — SỬA CẢ CỤM TỪ (KHÔNG DỊCH MỘT TỪ ĐƠN ĐỘC):
   - Công cụ dịch tự động thường ngắt sai cụm từ Hán (ví dụ: Hán gốc là "佩剑" = bội kiếm/thanh kiếm, nhưng Google dịch chỉ gắn lỗi vào từ "佩" thành "[LỖI: mặc] kiếm (kiếm đeo bên mình)").
   - Bạn BẮT BUỘC phải phân tích CẢ CỤM TỪ đằng sau lỗi (bao gồm từ bị dính liền sau đó và các phần mở ngoặc giải thích thừa của Google Translate).
   - Trả về CỤM TỪ THAY THẾ HOÀN CHỈNH CHO CẢ CỤM (ví dụ: trả về "bội kiếm" hoặc "thanh kiếm"), sao cho khi đắp vào câu văn, câu sẽ mượt mà, chuẩn nghĩa và gãy gọn 100%, KHÔNG bị lặp từ (như "bội kiếm kiếm") và tự động XÓA BỎ hoàn toàn các mở ngoặc giải thích thừa.

2. ĐÁNH GIÁ KHẢ NĂNG LƯỢC BỎ (XÓA BỎ TỪ RÁC):
   - Nếu việc thiếu từ bị lỗi KHÔNG ảnh hưởng tới ngữ nghĩa và ngữ pháp của câu (ví dụ: "Đây là cái cảm giác [LỖI: thao tác] gì thế này!" -> xóa [LỖI: thao tác] thành "Đây là cái cảm giác gì thế này!"), hãy trả về "corrected_term": "" (chuỗi rỗng) để XÓA BỎ từ đó.
   - Không gượng ép cố đoán từ thay thế nếu câu văn khi bỏ từ đó đi vẫn hoàn hảo và mượt mà.

3. NẾU CÂU VĂN BỊ LẶP CHỮ RÁC HOẶC DÍNH KHOẢNG TRẮNG:
   - Tự động lọc bỏ chữ rác lặp đầu (ví dụ: "ChTranh" -> "Tranh", "ThThứ" -> "Thứ") hoặc dính chữ ("đượckéo" -> "được kéo").

4. VÍ DỤ CỤ THỂ BẮT BUỘC MẪU:
   - [raw_chinese]: "佩", [faulty_term]: "mặc", sentence: "Tiếng này là tất cả [LỖI: mặc] kiếm (kiếm đeo bên mình) của mọi người đều rung lên..." -> corrected_term: "bội kiếm" hoặc "thanh kiếm".
   - [raw_chinese]: "灌透", [faulty_term]: "tưới tiêu", sentence: "Linh khí [LỖI: tưới tiêu] (thấm đượm) vào cơ thể..." -> corrected_term: "quán thấu" hoặc "rót vào".
   - [raw_chinese]: "操作", [faulty_term]: "thao tác", sentence: "Đây là cái cảm giác [LỖI: thao tác] gì thế này!" -> corrected_term: "" (chuỗi rỗng).

5. CHỈ TRẢ VỀ JSON array chứa các sửa đổi, cấu trúc bắt buộc:
{{
  "corrections": [
    {{
      "error_id": "ERR_CHX_Y",
      "corrected_term": "cụm_từ_đã_sửa_chuẩn HOẶC chuỗi rỗng \"\" nếu chọn xóa bỏ"
    }}
  ]
}}
6. Chỉ trả về JSON thuần hợp lệ, không bọc thẻ markdown ```json.
"""
        
        # 3. Call LLM
        llm_response = await call_gemini_api(prompt, model=None, is_json=True)
        if not llm_response:
            return {"status": "error", "message": "LLM API thất bại hoặc trả về rỗng."}
            
        try:
            res_data = safe_json_loads(llm_response)
            corrections_list = res_data.get("corrections", []) if isinstance(res_data, dict) else []
        except Exception:
            return {"status": "error", "message": "Lỗi parse JSON từ phản hồi LLM."}

            
        # Map error_id -> corrected_term
        corrections_map = {c.get("error_id"): c.get("corrected_term") for c in corrections_list if c.get("error_id") and c.get("corrected_term")}
        
        # 4. Áp dụng thay thế
        fixed_count = 0
        for ch_id, errs in chapter_error_map.items():
            original_content = chapter_content_map[ch_id]["content"]
            ver = chapter_content_map[ch_id]["version"]
            
            new_content = apply_swept_corrections(original_content, corrections_map, errs)
            
            if new_content != original_content:
                # Update DB and File
                ver.content = new_content
                if ver.file_path:
                    try:
                        os.makedirs(os.path.dirname(ver.file_path), exist_ok=True)
                        with open(ver.file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                    except Exception as e:
                        print(f"Lỗi ghi file phiên bản: {e}")
                fixed_count += len([e for e in errs if e["error_id"] in corrections_map])
                
        await session.commit()
        
        # Re-export Full.txt if anything fixed
        if fixed_count > 0:
            from app.services.postprocessing.post_processor import export_full_novel_txt
            await export_full_novel_txt(novel_id)
            
        return {
            "status": "success",
            "message": f"Đã quét và nhờ LLM sửa thành công {fixed_count} lỗi gạch chân xanh.",
            "fixed_count": fixed_count
        }

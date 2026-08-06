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
    Thay thế siêu chính xác: Tìm đúng thẻ span html đã lưu trong lỗi để đổi bằng từ sửa đúng (corrected_term)
    và gỡ bỏ hoàn toàn thẻ span đó ra khỏi đoạn text.
    """
    if not content:
        return content
        
    lines = content.split('\n')
    for err in chapter_errors:
        err_id = err["error_id"]
        corrected_term = corrections_map.get(err_id)
        if not corrected_term:
            continue
            
        # Strip bất kỳ giải thích trong ngoặc nào do LLM tự sinh (ví dụ: "chữ chuẩn (nghĩa 1/nghĩa 2)")
        corrected_term = re.sub(r'\s*\([^)]+\)', '', corrected_term).strip()
        corrected_term = re.sub(r'\s*\[[^\]]+\]', '', corrected_term).strip()
            
        line_idx = err["line_idx"]
        span_html = err["span_html"]
        
        # Thay thế span_html và tuỳ chọn CẢ CÁC NGOẶC ĐƠN theo sau nó (ví dụ: <span...>mở rộng</span> (kéo dài/mở rộng))
        if 0 <= line_idx < len(lines):
            # Wrap the corrected term in a styled span (Màu xanh lá mạ - emerald-500)
            highlighted_term = f'<span class="fixed-word" style="color: #10b981; font-weight: bold;">{corrected_term}</span>'
            # Pattern bao gồm span gốc và tuỳ chọn ngoặc đơn giải thích theo sau
            pattern = r'([a-zA-ZàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựỳýỷỹỵA-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰỲÝỶỸỴ]?)' + re.escape(span_html) + r'(?:\s*\([^)]+\))?([a-zA-ZàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựỳýỷỹỵA-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰỲÝỶỸỴ]?)'
            
            def _replace_with_space(match):
                before = match.group(1) or ""
                after = match.group(2) or ""
                res = highlighted_term
                if before:
                    res = before + " " + res
                if after:
                    res = res + " " + after
                return res

            lines[line_idx] = re.sub(pattern, _replace_with_space, lines[line_idx], count=1)
            
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

=== YÊU CẦU BẮT BUỘC (LÀM SẠCH VĂN BẢN CUỐI CÙNG) ===
1. Hãy phân tích ngữ cảnh câu văn và thể loại truyện để đưa ra TỪ THAY THẾ CHUẨN XÁC NGHĨA VÀ MƯỢT MÀ NHẤT cho từ bị lỗi đó.
2. NẾU CÂU VĂN BỊ LẶP CHỮ RÁC (ví dụ: "ChTranh" -> "Tranh", "SựCCác" -> "Sự Các", "ThThứ" -> "Thứ"), hãy tự động lọc bỏ chữ rác lặp đầu và trả về từ đã sửa sạch sẽ.
3. NẾU CÂU VĂN BỊ DÍNH CHỮ THIẾU KHOẢNG TRẮNG (ví dụ: "đượckéo" -> "được kéo"), hãy tự động sửa từ thay thế để khi đắp vào câu văn sẽ cách chữ rõ ràng, chuẩn xác.
4. Ví dụ: Nếu [raw_chinese] là "灌透" hoặc "灌注", công cụ dịch là "tưới tiêu", bạn BẮT BUỘC phải sửa thành "quán thấu" hoặc "rót vào". Không được dùng "tưới tiêu" trong truyện tiên hiệp!
5. CHỈ TRẢ VỀ JSON array chứa các sửa đổi, cấu trúc bắt buộc:
{{
  "corrections": [
    {{
      "error_id": "ERR_CHX_Y",
      "corrected_term": "từ_đã_sửa_chuẩn"
    }}
  ]
}}
4. Chỉ trả về JSON thuần hợp lệ, không bọc thẻ markdown ```json.
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

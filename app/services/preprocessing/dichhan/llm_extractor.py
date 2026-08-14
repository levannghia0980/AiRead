import json
import os
import httpx
import re
from typing import List, Dict, Any
from app.core.config import get_active_setting
from app.core.llm_client import post_gemini_with_retry, post_openrouter_with_retry, safe_json_loads


async def _get_llm_config():
    """Đọc cấu hình LLM provider/model/api_key và xác định là Gemini hay OpenRouter."""
    provider_val = os.environ.get("AIREAD_PROVIDER") or await get_active_setting("AIREAD_PROVIDER") or "gemini"
    provider = str(provider_val).lower().strip()
    model = (os.environ.get("AIREAD_MODEL") or await get_active_setting("AIREAD_MODEL") or "gemini-3.5-flash-lite").strip()
    raw_api_key = os.environ.get("AIREAD_API_KEYS") or await get_active_setting("AIREAD_API_KEYS") or ""
    api_key = raw_api_key.split(',')[0].strip() if raw_api_key else ""
    is_openrouter = (provider == "openrouter") or ("/" in model) or ("qwen" in model.lower()) or ("openrouter" in model.lower())
    return model, api_key, is_openrouter


async def _remove_sensitive_words_for_extraction(text: str) -> str:

    """
    Xóa bỏ các từ nhạy cảm 18+ trước khi gửi cho LLM xử lý NER/Entity extraction.
    Mục đích: Tránh Gemini/LLM bị chặn do vi phạm SafetyPolicy khi phân tích văn bản có nội dung nhạy cảm.
    """
    try:
        from app.services.preprocessing.crawler.pronoun_protector import EROTIC_SENSITIVE_ZH
        for word in EROTIC_SENSITIVE_ZH:
            text = text.replace(word, "")
    except Exception:
        pass
    return text


async def extract_entities_via_llm(raw_text: str) -> List[Dict[str, Any]]:
    """
    Sử dụng Gemini/OpenRouter LLM để bóc tách thực thể (tên nhân vật, địa danh, chiêu thức, môn phái)
    từ bản gốc tiếng Trung và trả về cấu trúc JSON mẫu.
    """
    model, api_key, is_openrouter = await _get_llm_config()

    if not api_key:
        raise Exception("Không tìm thấy API Key. Vui lòng thiết lập cấu hình trong Settings.")

    clean_text = await _remove_sensitive_words_for_extraction(raw_text)

    prompt = f"""
Nhiệm vụ: Trích xuất danh sách các danh từ riêng (tên nhân vật, địa danh, môn phái, võ công/chiêu thức) từ đoạn văn bản tiểu thuyết tiếng Trung sau.

Văn bản tiếng Trung:
\"\"\"
{clean_text[:3000]}
\"\"\"

Quy tắc phân loại (entity_type):
- 'PERSON': Tên nhân vật (ví dụ: "莫雅依", "叶凡").
- 'LOCATION': Địa danh, sông, núi, thành trì (ví dụ: "青云宗" nếu là địa điểm, "天玄山").
- 'SECT_SKILL': Tông môn, bang phái, pháp bảo, tên võ công chiêu thức (ví dụ: "青云宗" nếu là môn phái, "天玄剑诀").
- 'OTHER': Các thuật ngữ danh từ riêng đặc thù khác.

Hãy dịch thô nghĩa Hán-Việt chuẩn cho từng từ này vào cột 'rough_translation' (Ví dụ: "莫雅依" -> "Mạc Nhã Y").

Yêu cầu trả về kết quả định dạng JSON Array chứa các object có cấu trúc như ví dụ sau:
[
  {{"chinese_name": "莫雅依", "rough_translation": "Mạc Nhã Y", "entity_type": "PERSON"}},
  {{"chinese_name": "青云宗", "rough_translation": "Thanh Vân Tông", "entity_type": "SECT_SKILL"}}
]
CHỈ trả về JSON Array, không kèm giải thích.
"""

    if is_openrouter:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AiRead"
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await post_openrouter_with_retry(client, url, headers, body)
        if resp.status_code != 200:
            raise Exception(f"OpenRouter API Error (HTTP {resp.status_code}): {resp.text}")
        res_json = resp.json()
        text_response = res_json["choices"][0]["message"]["content"].strip()
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await post_gemini_with_retry(client, url, headers, body)
            if resp.status_code != 200:
                raise Exception(f"Lỗi gọi Gemini API (HTTP {resp.status_code}): {resp.text}")
        res_json = resp.json()
        text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()

    try:
        entities = safe_json_loads(text_response)
        if isinstance(entities, list):
            return entities
        elif isinstance(entities, dict) and "entities" in entities:
            return entities["entities"]
        return []
    except Exception as e:
        raise Exception(f"Thất bại khi phân tích JSON trả về từ LLM: {str(e)}. Response: {text_response[:500]}")


async def process_2branch_evidence_via_llm(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gửi gói bằng chứng 2 Nhánh hợp nhất (NER + Làm sạch GG) lên LLM.
    Luôn tự động chạy mã hóa chặn từ nhạy cảm 100% để LLM KHÔNG BAO GIỜ bị dính vi phạm Policy.
    """
    model, api_key, is_openrouter = await _get_llm_config()

    if not api_key:
        raise Exception("Không tìm thấy API Key. Vui lòng thiết lập cấu hình trong Settings.")

    instruction = evidence_data.get("system_prompt_instruction", "")
    existing_entities = evidence_data.get("existing_db_entities", {})
    ner_candidates = evidence_data.get("branch_1_ner_candidates", [])
    gg_errors = evidence_data.get("branch_2_gg_errors_to_clean", [])

    # Luôn BẬT CHẶN NHẠY CẢM 100% cho bóc tách thực thể bằng từ điển Unblock Pipeline
    from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, unmask_text_with_dictionary

    cleaned_ner = []
    mapping_table = {}
    for item in ner_candidates:
        c_item = dict(item)
        if "context" in c_item and c_item["context"]:
            ctx = await _remove_sensitive_words_for_extraction(c_item["context"])
            m_ctx, m_map, _ = await mask_text_with_dictionary(ctx, aggressive=True)
            mapping_table.update(m_map)
            c_item["context"] = m_ctx
        cleaned_ner.append(c_item)

    cleaned_gg = []
    for item in gg_errors:
        c_item = dict(item)
        if "chinese_context" in c_item and c_item["chinese_context"]:
            ctx = await _remove_sensitive_words_for_extraction(c_item["chinese_context"])
            m_ctx, m_map, _ = await mask_text_with_dictionary(ctx, aggressive=True)
            mapping_table.update(m_map)
            c_item["chinese_context"] = m_ctx
        if "vietnamese_context" in c_item and c_item["vietnamese_context"]:
            m_ctx, m_map, _ = await mask_text_with_dictionary(c_item["vietnamese_context"], aggressive=True)
            mapping_table.update(m_map)
            c_item["vietnamese_context"] = m_ctx
        cleaned_gg.append(c_item)

    prompt = f"""
Bạn là chuyên gia dịch thuật và chuẩn hóa tên nhân vật, chiêu thức, tên kiếm, bảo vật, địa danh trong tiểu thuyết Trung - Việt.

{instruction}

=== TỪ ĐIỂN THỰC THỂ ĐÃ TỒN TẠI TỪ CÁC CHƯƠNG TRƯỚC ===
Giữ nguyên bản dịch vietnamese_name và entity_type nếu từ Hán đã có trong từ điển:
{json.dumps(existing_entities, ensure_ascii=False, indent=2)}

=== DỮ LIỆU BẰNG CHỨNG NHÁNH 1 (NER - Nghi vấn từ bản gốc) ===
{json.dumps(cleaned_ner, ensure_ascii=False, indent=2)}

=== DỮ LIỆU BẰNG CHỨNG NHÁNH 2 (Lỗi Google Translate cần sửa) ===
{json.dumps(cleaned_gg, ensure_ascii=False, indent=2)}

Yêu cầu trả về kết quả dưới dạng JSON object chứa 2 danh sách 'entities' và 'corrections':
{{
  "entities": [
    {{"chinese_name": "莫雅仪", "vietnamese_name": "Mạc Nhã Nghi", "entity_type": "NAME", "gender": "female", "role": "Mẹ của Nam chính"}}
  ],
  "corrections": [
    {{"gg_error": "Mo Yayi", "correct_vietnamese": "Mạc Nhã Nghi"}}
  ]
}}
CHỈ trả về JSON, không kèm giải thích.
"""

    if is_openrouter:
        url = "https://openrouter.ai/api/v1/chat/completions"
        or_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AiRead"
        }
        or_body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await post_openrouter_with_retry(client, url, or_headers, or_body)
        if resp.status_code != 200:
            raise Exception(f"OpenRouter API Error (HTTP {resp.status_code}): {resp.text}")
        res_json = resp.json()
        text_response = res_json["choices"][0]["message"]["content"].strip()
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await post_gemini_with_retry(client, url, headers, body)
            if resp.status_code != 200:
                raise Exception(f"Lỗi gọi Gemini API (HTTP {resp.status_code}): {resp.text}")
        res_json = resp.json()
        text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()

    try:
        parsed = safe_json_loads(text_response)
        entities = parsed.get("entities", []) if isinstance(parsed, dict) else []
        corrections = parsed.get("corrections", []) if isinstance(parsed, dict) else []
        
        if mapping_table:
            for e in entities:
                if "vietnamese_name" in e and e["vietnamese_name"]:
                    e["vietnamese_name"] = unmask_text_with_dictionary(e["vietnamese_name"], mapping_table)
            for c in corrections:
                if "correct_vietnamese" in c and c["correct_vietnamese"]:
                    c["correct_vietnamese"] = unmask_text_with_dictionary(c["correct_vietnamese"], mapping_table)

        # Lọc corrections: Chỉ giữ những từ sửa đổi thành tên nhân vật/thực thể chuẩn (không sửa pronoun bừa bãi)
        from app.services.preprocessing.dichhan.candidate_mining import is_likely_foreign_or_pinyin
        from app.services.preprocessing.dichhan.common_lists import VIETNAMESE_STOPWORDS
        
        valid_correct_names = set()
        for e in entities:
            if isinstance(e, dict) and e.get("vietnamese_name"):
                valid_correct_names.add(e["vietnamese_name"].strip())
        for name, info in existing_entities.items():
            if isinstance(info, dict) and info.get("vietnamese_name"):
                valid_correct_names.add(info["vietnamese_name"].strip())
            elif isinstance(info, str):
                valid_correct_names.add(info.strip())

        filtered_corrections = []
        for c in corrections:
            if not isinstance(c, dict):
                continue
            corr_vi = c.get("correct_vietnamese", "").strip()
            gg_err = c.get("gg_error", "").strip()
            if not corr_vi or not gg_err:
                continue
            if corr_vi not in valid_correct_names:
                continue
            
            # Không chấp nhận sửa các từ tiếng Việt thông thường một từ (như 'mang', 'bao', 'che', 'lai', 'run', 'dai'...)
            # Phải là Pinyin/tên tiếng Anh ngoại lai HOẶC tên viết hoa/khớp alias
            err_lower = gg_err.lower()
            if err_lower in VIETNAMESE_STOPWORDS or len(gg_err) <= 2:
                continue
            if not (is_likely_foreign_or_pinyin(gg_err) or gg_err[0].isupper() or len(gg_err.split()) >= 2):
                continue
                
            filtered_corrections.append(c)

        return {"entities": entities, "corrections": filtered_corrections}
    except Exception as e:
        print(f"⚠️ [PREPROCESS LLM] Thất bại khi phân tích JSON trả về từ LLM: {e}")

    return {"entities": [], "corrections": []}

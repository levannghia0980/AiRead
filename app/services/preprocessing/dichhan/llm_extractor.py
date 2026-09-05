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
Nhiệm vụ: Trích xuất danh sách các danh từ riêng (tên nhân vật, địa danh, môn phái, võ công/chiêu thức, pháp bảo) từ đoạn văn bản tiểu thuyết tiếng Trung sau.

Văn bản tiếng Trung:
\"\"\"
{clean_text[:3000]}
\"\"\"

Quy tắc phân loại (entity_type):
- 'PERSON': Tên nhân vật (ví dụ: "莫雅依", "周佐", "苏浅浅", "刘震", "萧七修").
- 'LOCATION': Địa danh, sông, núi, thành trì (ví dụ: "青云宗" nếu là địa điểm, "天玄山", "灵法阁").
- 'SECT_SKILL': Tông môn, bang phái, võ công, chiêu thức, bí tịch, kiếm pháp, chưởng pháp, quyền pháp, trận pháp, pháp bảo (ví dụ: "金刚伏魔圈", "降龙十八掌", "太极拳", "独孤九剑", "天玄剑诀", "紫光雷翼").
- 'OTHER': Các thuật ngữ danh từ riêng đặc thù khác.

QUY TẮC ĐỐI CHIẾU ÂM HÁN-VIỆT CHUẨN XÁC TỪNG CHỮ (BẮT BUỘC):
- Dịch chuẩn âm Hán-Việt từng chữ vào cột 'rough_translation'.
- Phân biệt chính xác: 佐 = 'Tá' (Chu Tá), 修 = 'Tu' (Thất Tu), 事 = 'Sự' (Linh Sự Các), 浅 = 'Thiển' (Tô Thiển Thiển), 阁 = 'Các' (Linh Pháp Các), 震 = 'Chấn' (Lưu Chấn).
- Võ công & Trận pháp: 圈/阵 = 'Trận/Quyển' (金刚伏魔圈 = 'Kim Cương Phục Ma Trận / Kim Cương Phục Ma Quyển', CẤM: 'Khuyên'), 拳 = 'Quyền' (CẤM: 'đấm'), 掌 = 'Chưởng', 指 = 'Chỉ', 爪 = 'Trảo', 腿 = 'Cước'.
- TUYỆT ĐỐI NGHIÊM CẤM trả về tên dính chữ Hán lai tạp (CẤM 'Tô T浅浅', CẤM 'Linh Pháp C阁', CẤM 'L岚'). Cột rough_translation phải là 100% chữ tiếng Việt có dấu.

Yêu cầu trả về kết quả định dạng JSON Array chứa các object có cấu trúc như ví dụ sau:
[
  {{"chinese_name": "莫雅依", "rough_translation": "Mạc Nhã Y", "entity_type": "PERSON"}},
  {{"chinese_name": "周佐", "rough_translation": "Chu Tá", "entity_type": "PERSON"}},
  {{"chinese_name": "金刚伏魔圈", "rough_translation": "Kim Cương Phục Ma Trận", "entity_type": "SECT_SKILL"}},
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
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
            ]
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await post_gemini_with_retry(client, url, headers, body)
            if resp.status_code != 200:
                raise Exception(f"Lỗi gọi Gemini API (HTTP {resp.status_code}): {resp.text}")
        res_json = resp.json()
        text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()

    try:
        from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese
        entities = safe_json_loads(text_response)
        raw_list = []
        if isinstance(entities, list):
            raw_list = entities
        elif isinstance(entities, dict) and "entities" in entities:
            raw_list = entities["entities"]

        cleaned_result = []
        for item in raw_list:
            if isinstance(item, dict) and "chinese_name" in item:
                ch_n = item.get("chinese_name", "").strip()
                r_tr = item.get("rough_translation", "").strip()
                item["rough_translation"] = sanitize_entity_vietnamese(r_tr, ch_n)
                cleaned_result.append(item)
        return cleaned_result
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

⚠️ NGUYÊN TẮC HÀNG ĐẦU KHI XỬ LÝ DỮ LIỆU GỢI Ý:
- Tuyệt đối KHÔNG cố dựa vào các ví dụ nhỏ bên cạnh của Hán/Google Dịch nếu thấy ngô nghê/tối nghĩa.
- BẮT BUỘC dịch thật hay, đặt tên bóng bẩy, chuẩn phong vị tiên hiệp/kiếm hiệp cho chiêu thức võ công, pháp bảo, dược liệu hoặc dịch thuần Việt dễ hiểu.

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

        # === KHỬ SẠCH 100% HÁN TỰ SÓT VÀ KÝ TỰ RÁC TRONG TÊN THỰC THỂ (VD: 'Phương Hân L岚' -> 'Phương Hân Lam') ===
        from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese
        for e in entities:
            if not isinstance(e, dict):
                continue
            vn_name = e.get("vietnamese_name", "").strip()
            ch_name = e.get("chinese_name", "").strip()
            cleaned_vn = sanitize_entity_vietnamese(vn_name, ch_name)
            if cleaned_vn != vn_name:
                print(f"[PREPROCESS LLM] ✅ Đã chuẩn hóa tên thực thể '{vn_name}' -> '{cleaned_vn}' cho '{ch_name}'")
            e["vietnamese_name"] = cleaned_vn

        for c in corrections:
            if not isinstance(c, dict):
                continue
            corr_vi = c.get("correct_vietnamese", "").strip()
            if corr_vi:
                c["correct_vietnamese"] = sanitize_entity_vietnamese(corr_vi)

        return {"entities": entities, "corrections": []}
    except Exception as e:
        print(f"⚠️ [PREPROCESS LLM] Thất bại khi phân tích JSON trả về từ LLM: {e}")

    return {"entities": [], "corrections": []}

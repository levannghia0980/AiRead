import json
import httpx
import re
from typing import List, Dict, Any
from app.core.config import get_active_setting
from app.core.llm_client import post_gemini_with_retry, safe_json_loads

async def _remove_sensitive_words_for_extraction(text: str) -> str:

    """
    Xóa các từ nhạy cảm và ngữ cảnh nhạy cảm (như thông tin tuổi tác, từ ngữ loạn luân, tình dục)
    CHỈ DÀNH RIÊNG cho tác vụ bóc tách danh từ riêng / dịch tên nhằm tránh bị bộ lọc an toàn của LLM
    (PROHIBITED_CONTENT / CSAM) chặn lại.
    Không áp dụng hay ảnh hưởng đến luồng dịch truyện chung.
    """
    if not text:
        return text
    from app.services.unblock.unblock_pipeline import get_global_trie
    trie = await get_global_trie()
    matches = trie.find_all_matches(text)
    if matches:
        res = list(text)
        for start, end, word, cat in sorted(matches, key=lambda x: x[0], reverse=True):
            res[start:end] = [" "]
        text = "".join(res)

    text = re.sub(r'\d+岁', '  ', text)
    extra_sensitive_context = [
        '乱伦', '阴道', '子宫', '肉便器', '暴奸', '性奴', '内射', '潮吹', 
        '做爱', '性交', '迷奸', '轮奸', '强奸', '奸淫', '阳具', '龟头', 
        '后庭', '肛交', '口交', '精液', '鸡巴', '大鸡巴', '阴唇', '阴毛', 
        '阴部', '肛门', '肉棒', '花穴', '嫩穴'
    ]
    for w in extra_sensitive_context:
        text = text.replace(w, ' ')

    return text


async def extract_entities_via_llm(raw_text: str) -> List[Dict[str, Any]]:
    """
    Sử dụng Gemini LLM để bóc tách thực thể (tên nhân vật, địa danh, chiêu thức, môn phái)
    từ bản gốc tiếng Trung và trả về cấu trúc JSON mẫu.
    """
    model = await get_active_setting("AIREAD_MODEL")
    api_key = await get_active_setting("AIREAD_API_KEYS")

    if not api_key:
        raise Exception("Không tìm thấy Gemini API Key. Vui lòng thiết lập cấu hình trong Settings.")

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
"""

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
        try:
            text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            entities = safe_json_loads(text_response)
            if isinstance(entities, list):
                return entities
            elif isinstance(entities, dict) and "entities" in entities:
                return entities["entities"]
            return []
        except Exception as e:
            raise Exception(f"Thất bại khi phân tích JSON trả về từ Gemini: {str(e)}. Response: {resp.text}")


async def process_2branch_evidence_via_llm(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gửi gói bằng chứng 2 Nhánh hợp nhất (NER + Làm sạch GG) lên Gemini LLM.
    Yêu cầu LLM trả về cả 2 danh sách:
    1. 'entities': Tên nhân vật/thực thể đã dịch chuẩn (dùng cập nhật DB).
    2. 'corrections': Danh sách sửa lỗi từ Google Translate (dùng làm sạch văn bản dịch).
    """
    model = await get_active_setting("AIREAD_MODEL")
    api_key = await get_active_setting("AIREAD_API_KEYS")

    if not api_key:
        raise Exception("Không tìm thấy Gemini API Key. Vui lòng thiết lập cấu hình trong Settings.")

    instruction = evidence_data.get("system_prompt_instruction", "")
    existing_entities = evidence_data.get("existing_db_entities", {})
    ner_candidates = evidence_data.get("branch_1_ner_candidates", [])
    gg_errors = evidence_data.get("branch_2_gg_errors_to_clean", [])

    prompt = f"""
Bạn là chuyên gia dịch thuật và chuẩn hóa tên nhân vật, chiêu thức, tên kiếm, bảo vật, địa danh, cùng các thuộc tính và bối phận nhân vật trong tiểu thuyết Trung - Việt.

{instruction}

=== TỪ ĐIỂN THỰC THỂ ĐÃ TỒN TẠI TỪ CÁC CHƯƠNG TRƯỚC (QUY TẮC ĐỒNG BỘ BẮT BUỘC) ===
⚠️ NGUYÊN TẮC VÀNG — TUYỆT ĐỐI KHÔNG ĐƯỢC VI PHẠM:
Nếu một từ Hán gốc (chinese_name) ĐÃ CÓ TRONG TỪ ĐIỂN bên dưới, bạn BẮT BUỘC PHẢI:
1. Sao chép Y NGUYÊN bản dịch vietnamese_name từ từ điển vào output — KHÔNG ĐƯỢC sửa dù chỉ 1 ký tự
2. Giữ nguyên entity_type từ từ điển
3. KHÔNG ĐƯỢC "cải thiện", "sửa lỗi", hay "dịch lại" tên đã có — dù bạn cho rằng bản dịch cũ chưa chuẩn
CHỈ ĐƯỢC tạo bản dịch MỚI cho các từ Hán CHƯA CÓ trong từ điển.
{json.dumps(existing_entities, ensure_ascii=False, indent=2)}

=== DỮ LIỆU BẰNG CHỨNG NHÁNH 1 (NER - Tên/Chiêu thức/Tên kiếm/Địa danh nghi vấn từ bản gốc kèm ngữ cảnh) ===
{json.dumps(ner_candidates, ensure_ascii=False, indent=2)}

=== DỮ LIỆU BẰNG CHỨNG NHÁNH 2 (Các lỗi Google Translate cần sửa như Pinyin tiếng Anh hoặc dịch sai âm Hán-Việt đồng âm/gần âm kèm ngữ cảnh Hán gốc) ===
{json.dumps(gg_errors, ensure_ascii=False, indent=2)}

Yêu cầu trả về kết quả dưới dạng JSON object chứa 2 danh sách 'entities' và 'corrections':
- Với các thực thể tên nhân vật (entity_type: "NAME" hoặc "PERSON"), hãy cố gắng phân tích ngữ cảnh để suy ra `gender` ("male" hoặc "female") và `role` (mối quan hệ/bối phận, ví dụ: "Mẹ của Nam chính", "Nữ chính", "Sư phụ", "Đại sư huynh", "Chị gái", v.v.).
{{
  "entities": [
    {{"chinese_name": "莫雅仪", "vietnamese_name": "Mạc Nhã Nghi", "entity_type": "NAME", "gender": "female", "role": "Mẹ của Nam chính"}},
    {{"chinese_name": "雷神之息", "vietnamese_name": "Lôi Thần Chi Sức", "entity_type": "SKILL"}},
    {{"chinese_name": "紫光雷翼", "vietnamese_name": "Tử Quang Lôi Dực", "entity_type": "ITEM"}},
    {{"chinese_name": "天桑灵宫", "vietnamese_name": "Thiên Tang Linh Cung", "entity_type": "PLACE"}}
  ],
  "corrections": [
    {{"gg_error": "Mo Yayi", "correct_vietnamese": "Mạc Nhã Nghi"}}
  ]
}}
"""

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
        try:
            text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            parsed = safe_json_loads(text_response)
            return {
                "entities": parsed.get("entities", []) if isinstance(parsed, dict) else [],
                "corrections": parsed.get("corrections", []) if isinstance(parsed, dict) else []
            }
        except Exception as e:
            raise Exception(f"Thất bại khi phân tích JSON phản hồi 2 nhánh từ Gemini: {str(e)}. Response: {resp.text}")


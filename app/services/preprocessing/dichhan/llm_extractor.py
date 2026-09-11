import json
import os
import httpx
import re
from typing import List, Dict, Any
from app.core.config import get_active_setting
from app.core.llm_client import post_gemini_with_retry, post_openrouter_with_retry, safe_json_loads


async def _get_llm_config():
    """Đọc cấu hình LLM provider/model/api_key và xác định là Gemini, OpenRouter hay Grok."""
    provider_val = os.environ.get("AIREAD_PROVIDER") or await get_active_setting("AIREAD_PROVIDER") or "gemini"
    provider = str(provider_val).lower().strip()
    model = (os.environ.get("AIREAD_MODEL") or await get_active_setting("AIREAD_MODEL") or "gemini-3.5-flash-lite").strip()
    raw_api_key = os.environ.get("AIREAD_API_KEYS") or await get_active_setting("AIREAD_API_KEYS") or ""
    api_key = raw_api_key.split(',')[0].strip() if raw_api_key else ""

    is_grok_local = (provider in ["grok_local", "grok", "grok_web"]) or ("grok" in model.lower())
    is_openrouter = not is_grok_local and ((provider == "openrouter") or ("/" in model) or ("qwen" in model.lower()) or ("openrouter" in model.lower()))

    # Nếu đang chọn Grok và có API key (Gemini):
    # Dùng gemini-3.5-flash-lite cho khâu bóc tách thực thể để trả về JSON siêu tốc 1-2s, tránh lỗi 404
    if is_grok_local:
        if api_key:
            model = "gemini-3.5-flash-lite"
            is_grok_local = False
        else:
            # Nếu không có key, model giữ nguyên nhưng cờ is_grok_local=True để gọi Grok Server
            pass

    return model, api_key, is_openrouter, is_grok_local



async def _remove_sensitive_words_for_extraction(text: str) -> str:

    """
    Xóa bỏ các từ nhạy cảm 18+ trước khi gửi cho LLM xử lý NER/Entity extraction.
    Mục đích: Tránh Gemini/LLM bị chặn do vi phạm SafetyPolicy khi phân tích văn bản có nội dung nhạy cảm.
    """
    try:
        from app.services.unblock.common.dictionary_loader import load_zh_erotic_map
        zh_map = load_zh_erotic_map()
        for word in zh_map:
            if word in text:
                text = text.replace(word, "")
    except Exception:
        pass
    return text


async def extract_entities_via_llm(raw_text: str) -> List[Dict[str, Any]]:
    """
    Sử dụng Gemini/OpenRouter/Grok LLM để bóc tách thực thể (tên nhân vật, địa danh, chiêu thức, môn phái)
    từ bản gốc tiếng Trung và trả về cấu trúc JSON mẫu.
    """
    model, api_key, is_openrouter, is_grok_local = await _get_llm_config()

    if not api_key and not is_grok_local:
        raise Exception("Không tìm thấy API Key hoặc Grok Server. Vui lòng thiết lập cấu hình trong Settings.")

    clean_text = await _remove_sensitive_words_for_extraction(raw_text)

    prompt = f"""
Nhiệm vụ: Trích xuất danh sách các danh từ riêng và từ vựng mang bản sắc thể loại (tên nhân vật, địa danh, môn phái, võ công/chiêu thức, pháp bảo, thuật ngữ nghề nghiệp / thế giới quan) từ toàn bộ văn bản tiểu thuyết tiếng Trung sau (quét đầy đủ 100% không bỏ sót).

Văn bản tiếng Trung:
\"\"\"
{clean_text}
\"\"\"

CÁC NHÓM THỰC THỂ CẦN BÓC TÁCH:
- 'PERSON': Tên nhân vật, bao gồm cả tên thân mật, nhũ danh trẻ con. TUYỆT ĐỐI KHÔNG bóc tách phó từ, liên từ, từ ngữ sinh hoạt thông thường thành tên người!
- 'LOCATION': Địa danh, sông, núi, thành trì.
- 'SECT_SKILL': Tông môn, bang phái, võ công, chiêu thức, bí tịch, kiếm pháp, chưởng pháp, quyền pháp, trận pháp, pháp bảo.
- 'LORE_TERM': Thuật ngữ thế giới quan, biệt ngữ nghề nghiệp, cảnh giới tu luyện, các thời kỳ / phân kỳ tu luyện & trạng thái (sơ kỳ, trung kỳ, hậu kỳ, đỉnh phong, viên mãn, bình cảnh, bán bộ, hóa hình kỳ...), các thời kỳ lịch sử thế giới quan (thượng cổ, viễn cổ, mạt pháp...), từ vựng mang bản sắc đặc thù theo thể loại tác phẩm.
- 'OTHER': Các thuật ngữ danh từ riêng đặc thù khác.

TRƯỜNG 'evaluation' (ĐÁNH GIÁ CÁCH DÙNG BẮT BUỘC):
Đánh giá cụ thể giá trị từ vựng để điều hướng mô hình dịch thuật:
- "TÊN CỐ ĐỊNH": Dành cho tên nhân vật, địa danh, môn phái (khóa 1-1, không đổi tên giữa các chương).
- "NÊN DÙNG BẢN SẮC": Dành cho thuật ngữ thế giới quan, biệt ngữ nghề nghiệp mang phong vị tác phẩm (đây là từ đắt giá, NÊN DÙNG trong bản dịch, cấm thuần Việt hóa làm mất chất truyện).
- "NÊN DỊCH THUẦN VIỆT": Dành cho các từ ngữ nên linh hoạt diễn đạt thuần Việt tự nhiên, dễ hiểu theo ngữ cảnh.

TRƯỜNG 'role' (VAI TRÒ / NGỮ CẢNH):
- Ghi chú ngắn gọn vai trò hoặc ngữ cảnh sử dụng.

QUY TẮC ĐỐI CHIẾU ÂM HÁN-VIỆT CHUẨN XÁC TỪNG CHỮ (BẮT BUỘC):
- Dịch chuẩn âm Hán-Việt hoặc từ dịch nghĩa văn học đắt giá vào cột 'rough_translation'.
- Võ công & Trận pháp: 圈/阵 = 'Trận/Quyển' (CẤM: 'Khuyên'), 拳 = 'Quyền' (CẤM: 'đấm'), 掌 = 'Chưởng', 指 = 'Chỉ', 爪 = 'Trảo', 腿 = 'Cước'.
- TUYỆT ĐỐI NGHIÊM CẤM trả về tên dính chữ Hán lai tạp. Cột rough_translation phải là 100% chữ tiếng Việt có dấu.

🔴 MỆNH LỆNH TỐI CAO ĐỐI VỚI ĐIỂN CỐ, VÕ HỌC, NGOẠI HIỆU & DANH XƯNG KINH ĐIỂN:
- CÁC GỢI Ý CỦA TỪ ĐIỂN MÁY / HanLP / DỊCH THÔ CHỈ LÀ PHIÊN ÂM MẶT CHỮ CƠ HỌC (~3000 TỪ), THƯỜNG RẤT NGU VÀ BẺ NGHĨA ĐEN (ví dụ: bẻ '摸着天' thành 'Mô Trước Thiên', '八百里' thành 'Bát Bách Lịch', '好汉' thành 'người tốt').
- BẠN LÀ MÔ HÌNH NGÔN NGỮ ĐÃ CÓ TOÀN BỘ KHO TRI THỨC VĂN HỌC DỊCH THUẬT TRUNG - VIỆT ĐỒ SỘ:
  * Khi gặp các nhân vật, ngoại hiệu giang hồ, tước xưng, bang phái, chiêu thức võ học, thần thông, pháp bảo, địa danh, điển tích kinh điển (trong toàn bộ kho tàng Thủy Hử, Tam Quốc Diễn Nghĩa, Tây Du Ký, Phong Thần Diễn Nghĩa, Kim Dung, Cổ Long, Ôn Thụy An, Huỳnh Dị, Tiên hiệp đại chúng...):
  * BẮT BUỘC tự động truy xuất và sử dụng ĐÚNG 100% tên dịch thuật văn học đã đi vào đại chúng Việt Nam, TUYỆT ĐỐI CẤM bẻ chữ cơ học mặt chữ!
  * VÍ DỤ MINH HỌA (YÊU CẦU + LỖI CẤM TRÁNH BẺ CHỮ):
    + Ngoại hiệu / Nhân vật: 摸着天 (Đỗ Thiên) -> BẮT BUỘC: 'Mạc Già Thiên' (CẤM bẻ thô: 'Mô Trước Thiên', 'Mốt Trưởng Thiên').
    + Địa danh / Điển cố: 八百里水泊梁山 -> BẮT BUỘC: 'Bát Bách Lý / Tám trăm dặm Thủy Bạc Lương Sơn' (CẤM: 'Bát Bách Lịch').
    + Thần thoại / Thực thể: 巨灵神 -> BẮT BUỘC: 'Cự Linh Thần' (CẤM gõ sai: 'Cựu Linh Thần').
    + Võ học / Chiêu thức: 降龙十八掌 -> 'Hàng Long Thập Bát Chưởng', 乾坤大挪移 -> 'Càn Khôn Đại Na Di' (CẤM bẻ nghĩa đen cơ học).

Yêu cầu trả về kết quả định dạng JSON Array chứa các object có cấu trúc như ví dụ sau:
[
  {{"chinese_name": "莫雅依", "rough_translation": "Mạc Nhã Y", "entity_type": "PERSON", "evaluation": "TÊN CỐ ĐỊNH", "role": "Nhân vật nữ"}},
  {{"chinese_name": "青云宗", "rough_translation": "Thanh Vân Tông", "entity_type": "SECT_SKILL", "evaluation": "TÊN CỐ ĐỊNH", "role": "Môn phái"}},
  {{"chinese_name": "金刚伏魔圈", "rough_translation": "Kim Cương Phục Ma Trận", "entity_type": "SECT_SKILL", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "Võ kỹ / Trận pháp đặc thù"}},
  {{"chinese_name": "...", "rough_translation": "...", "entity_type": "LORE_TERM", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "Biệt ngữ mang phong vị tác phẩm"}},
  {{"chinese_name": "...", "rough_translation": "...", "entity_type": "LORE_TERM", "evaluation": "NÊN DỊCH THUẦN VIỆT", "role": "Linh hoạt diễn đạt thuần Việt"}}
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
    elif is_grok_local:
        grok_url = os.environ.get("AIREAD_GROK_URL") or "http://127.0.0.1:8020/translate-text"
        from app.core.llm_client import post_grok_local_with_retry
        async with httpx.AsyncClient(timeout=180.0) as client:
            res_data = await post_grok_local_with_retry(client, grok_url, {"text": prompt, "timeout": 120.0})
            text_response = res_data.get("translated_text", "").strip()
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
    Gửi danh sách ứng viên thực thể lên LLM để trích xuất, chuẩn hóa tên và phân loại thực thể chi tiết.
    Luôn tự động chạy mã hóa chặn từ nhạy cảm 100% để LLM KHÔNG BAO GIỜ bị dính vi phạm Policy.
    """
    model, api_key, is_openrouter, is_grok_local = await _get_llm_config()

    if not api_key and not is_grok_local:
        raise Exception("Không tìm thấy API Key hoặc Grok Server. Vui lòng thiết lập cấu hình trong Settings.")

    instruction = evidence_data.get("system_prompt_instruction", "")
    existing_entities = evidence_data.get("existing_db_entities", {})
    ner_candidates = evidence_data.get("branch_1_ner_candidates", [])

    # Luôn BẬT CHẶN NHẠY CẢM 100% cho bóc tách thực thể bằng từ điển Unblock Pipeline
    from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, unmask_text_with_dictionary

    cleaned_ner = []
    mapping_table = {}
    for item in ner_candidates:
        c_item = dict(item)
        if "context_han" in c_item and c_item["context_han"]:
            ctx = await _remove_sensitive_words_for_extraction(c_item["context_han"])
            m_ctx, m_map, _ = await mask_text_with_dictionary(ctx, aggressive=True)
            mapping_table.update(m_map)
            c_item["context_han"] = m_ctx
        cleaned_ner.append(c_item)

    prompt = f"""
Bạn là chuyên gia dịch thuật và chuẩn hóa tên nhân vật, chiêu thức, bảo vật, địa danh trong tiểu thuyết Trung - Việt.

{instruction}

⚠️ NGUYÊN TẮC HÀNG ĐẦU KHI XỬ LÝ DỮ LIỆU GỢI Ý:
- Dữ liệu gửi lên là danh sách ứng viên nghi vấn thô: BẮT BUỘC phân tích vi ngữ cảnh 【...】 để chọn lọc thông minh.
- BẮT BUỘC phân loại rõ ràng thực thể vào 2 trường 'entity_type' và 'evaluation':
  * 'entity_type': 'NAME' (nhân vật, ngoại hiệu), 'PLACE' (địa danh, căn cứ), 'SECT' (tông môn, bang hội), 'SKILL' (chiêu thức, võ công), 'ITEM' (bảo vật, binh khí), 'LORE_TERM' (thuật ngữ thế giới quan, cảnh giới), 'OTHER'.
  * 'evaluation': 'TÊN CỐ ĐỊNH' (khóa 1-1 cho NAME, PLACE, SECT), 'NÊN DÙNG BẢN SẮC' (ưu tiên dùng trong bản dịch cho SKILL, ITEM, LORE_TERM), 'NÊN DỊCH THUẦN VIỆT' (diễn đạt thuần Việt linh hoạt).
- Loại bỏ triệt để các phó từ, liên từ, hư từ ngữ pháp vô nghĩa (như '倒是', '一下子', '大不了', '好日子', '大家', '按人头', '大声', '出乱子', '租子', '媳妇', '围裙', '勺子', '大包', '死尸').
- Tuyệt đối KHÔNG cố dựa vào các ví dụ gợi ý bên cạnh nếu thấy ngô nghê/tối nghĩa hoặc bẻ từ cơ học (kho HanLP máy cục bộ chỉ có ~3000 từ thô).
- 🔴 MỆNH LỆNH TỐI CAO ĐỐI VỚI ĐIỂN CỐ, VÕ HỌC, NGOẠI HIỆU & DANH XƯNG KINH ĐIỂN:
  * Khi gặp nhân vật, ngoại hiệu, bang phái, võ công, chiêu thức, pháp bảo, địa danh kinh điển (trong Thủy Hử, Tam Quốc, Tây Du, Phong Thần, Kim Dung, Cổ Long, Ôn Thụy An, Tiên hiệp đại chúng...):
  * BẮT BUỘC tự động truy xuất và sử dụng ĐÚNG 100% tên dịch thuật văn học đã đi vào đại chúng Việt Nam, TUYỆT ĐỐI CẤM bẻ chữ cơ học mặt chữ!
  * Ví dụ: 摸着天 -> 'Mạc Già Thiên' (CẤM bẻ thô 'Mô Trước Thiên'), 白衣秀士 -> 'Bạch Y Tú Sĩ', 云里金刚 -> 'Vân Lý Kim Cương', 八百里水泊梁山 -> 'Bát Bách Lý Thủy Bạc Lương Sơn' (CẤM 'Bát Bách Lịch').
- 🔴 BẢO TOÀN TRỌN VẸN CẢ CỤM TỪ — TUYỆT ĐỐI CẤM CẮT CỤT NGOẠI HIỆU / TÊN RIÊNG:
  * Khi nhận diện ngoại hiệu giang hồ, danh hiệu, tên riêng: BẮT BUỘC giữ nguyên vẹn cả cụm danh xưng hoàn chỉnh.
  * TUYỆT ĐỐI CẤM cắt cụt đầu đuôi làm rụng từ (như cắt thành '里金刚', '衣秀士', '州小旋风', '飞将')!
  * TUYỆT ĐỐI CẤM dính từ nối/giới từ vào tên (như '和短命二郎', '江鸿飞将').
  * CẤM băm nhỏ một tên riêng/ngoại hiệu thành nhiều thực thể con!
- 🔴 NGUYÊN TẮC PHÂN TÍCH MỞ RỘNG VÙNG NEO NGỮ CẢNH 【...】:
  * Ký hiệu 【...】 trong 'context_han' chỉ là mốc neo đánh dấu vùng nghi vấn giúp bạn định vị trọng tâm trong câu văn.
  * TUYỆT ĐỐI KHÔNG BỊ TRÓI BUỘC CỨNG NHẮC CHỈ TRÍCH XUẤT MỖI CHỮ TRONG 【...】!
  * Hãy nhìn rộng ra toàn bộ câu văn ngữ cảnh xung quanh để:
    1. Xác định ĐẦY ĐỦ CẢ CỤM TỰ NHIÊN: Nếu vùng neo đi liền với số lượng từ / địa danh / ngoại hiệu / danh xưng (ví dụ: thấy '八百里【水泊梁山】' -> bóc tách trọn vẹn cả cụm là '八百里水泊梁山' -> 'Bát Bách Lý Thủy Bạc Lương Sơn' hoặc 'Tám trăm dặm Thủy Bạc Lương Sơn', TUYỆT ĐỐI CẤM làm rơi rụng chữ 'Lý'; thấy '喜欢火拼的【晁盖】' -> nhận diện rõ nhân vật là '晁盖' -> 'Triều Cái').
    2. Hiểu đúng chức vụ, bối phận, tính cách nhân vật trong câu để chọn cách dịch chuẩn xác nhất, tránh dịch ngáo, rơi chữ, cụt từ (không biến '晁盖' thành 'Tiêu Cung chủ', không biến '八百里水泊梁山' thành 'Bát Bách Thủy Bạc').

=== TỪ ĐIỂN THỰC THỂ ĐÃ TỒN TẠI TỪ CÁC CHƯƠNG TRƯỚC ===
Giữ nguyên bản dịch vietnamese_name và entity_type nếu từ Hán đã có trong từ điển:
{json.dumps(existing_entities, ensure_ascii=False, indent=2)}

=== DANH SÁCH ỨNG VIÊN THỰC THỂ NGHI VẤN KÈM NGỮ CẢNH ===
{json.dumps(cleaned_ner, ensure_ascii=False, indent=2)}

Yêu cầu trả về kết quả dưới dạng JSON object chứa danh sách 'entities':
{{
  "entities": [
    {{"chinese_name": "王威", "vietnamese_name": "Vương Uy", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "nhân vật chính"}},
    {{"chinese_name": "白衣秀士", "vietnamese_name": "Bạch Y Tú Sĩ", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "ngoại hiệu Vương Luân"}},
    {{"chinese_name": "水泊梁山", "vietnamese_name": "Thủy Bạc Lương Sơn", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "căn cứ Lương Sơn"}},
    {{"chinese_name": "夺命十三枪", "vietnamese_name": "Đoạt Mệnh Thập Tam Thương", "entity_type": "SKILL", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "thương pháp võ học"}},
    {{"chinese_name": "妖姬", "vietnamese_name": "Yêu Cơ", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "thần binh bảo thương"}}
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
    elif is_grok_local:
        grok_url = os.environ.get("AIREAD_GROK_URL") or "http://127.0.0.1:8020/translate-text"
        from app.core.llm_client import post_grok_local_with_retry
        async with httpx.AsyncClient(timeout=180.0) as client:
            res_data = await post_grok_local_with_retry(client, grok_url, {"text": prompt, "timeout": 120.0})
            text_response = res_data.get("translated_text", "").strip()
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
        
        if mapping_table:
            for e in entities:
                if "vietnamese_name" in e and e["vietnamese_name"]:
                    e["vietnamese_name"] = unmask_text_with_dictionary(e["vietnamese_name"], mapping_table)

        # === KHỬ SẠCH 100% HÁN TỰ SÓT VÀ KÝ TỰ RÁC TRONG TÊN THỰC THỂ ===
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

        return {"entities": entities}
    except Exception as e:
        print(f"⚠️ [PREPROCESS LLM] Thất bại khi phân tích JSON trả về từ LLM: {e}")

    return {"entities": []}

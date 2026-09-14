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


async def extract_batch_entities_direct_llm(
    combined_raw_text: str,
    existing_entities: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Bóc tách thực thể trực tiếp từ toàn văn RAW của lô chương bằng LLM Reasoning (Zero Code Heuristics).
    - Quét trực tiếp toàn bộ các chương trong lô.
    - Nhận diện đầy đủ 5 phân loại phổ biến + OTHER (tên riêng của mọi thực thể, tên cúng cơm, tên thú cưng nông thôn,
      ngoại hiệu võ học, điển cố, pháp bảo, hệ thống...).
    - Tiếp nhận danh sách thực thể đã có từ trước để khóa cứng bản dịch, chống biến đổi tên sau hàng trăm chương.
    - Trả về toàn bộ thực thể trong lô (cả cũ lẫn mới).
    """
    if not combined_raw_text or not combined_raw_text.strip():
        return []

    model, api_key, is_openrouter, is_grok_local = await _get_llm_config()
    if not api_key and not is_grok_local:
        raise Exception("Không tìm thấy API Key hoặc Grok Server.")

    from app.services.unblock.unblock_pipeline import mask_text_with_dictionary, unmask_text_with_dictionary
    clean_text = await _remove_sensitive_words_for_extraction(combined_raw_text)
    masked_text, mapping_table, _ = await mask_text_with_dictionary(clean_text, aggressive=True)

    existing_ref = ""
    if existing_entities:
        ref_lines = []
        for cn, info in existing_entities.items():
            vn = info.get("vietnamese_name", "")
            etype = info.get("entity_type", "NAME")
            role = info.get("role", "")
            ref_lines.append(f"  • {cn} ➔ {vn} [{etype}] (Vai trò: {role})")

        existing_ref = f"""
🔴 CÁC THỰC THỂ ĐÃ XUẤT HIỆN Ở CÁC CHƯƠNG TRƯỚC VÀ ĐÃ CÓ BẢN DỊCH CHUẨN:
Hệ thống đã tự động rà soát CSDL và phát hiện các thực thể sau ĐÃ TỒN TẠI từ trước và ĐANG XUẤT HIỆN LẠI trong lô chương này:
{chr(10).join(ref_lines)}

⚠️ MỆNH LỆNH BẮT BUỘC ĐỐI VỚI CÁC THỰC THỂ ĐÃ CÓ NÀY:
1. KHÔNG BIẾN ĐỔI LINH TINH: Dùng đúng 100% bản dịch 'vietnamese_name' đã cho ở trên, TUYỆT ĐỐI CẤM tự ý dịch khác hay sửa đổi tên!
2. VẪN BẮT BUỘC TRẢ VỀ: Nếu các thực thể trên xuất hiện trong lô này, BẮT BUỘC vẫn đưa chúng vào mảng JSON "entities" trả về cùng với các thực thể mới (giữ nguyên 'vietnamese_name' chuẩn).
3. TẬP TRUNG TÌM MỚI: Đồng thời quét kỹ toàn bộ văn bản để bóc tách thêm tất cả các thực thể MỚI chưa có trong danh sách trên!
"""

    prompt = f"""Bạn là chuyên gia ngôn ngữ học và dịch thuật tiểu thuyết cao cấp, sở hữu vốn từ vựng Hán - Việt bác học và khả năng phân tích bối cảnh, ngữ pháp sâu sắc.

🔴 ĐỊNH NGHĨA & MỤC TIÊU TỐI CAO:
BÓC TÁCH TẤT CẢ TÊN RIÊNG CỦA MỌI THỰC THỂ HOẶC TÊN CHUNG CỦA CÁC THỰC THỂ MANG BẢN SẮC TRONG TOÀN BỘ LÔ CHƯƠNG.
🎯 TIÊU CHUẨN VÀNG: Bất kỳ danh từ riêng, tên gọi nào mà khi dịch sang tiếng Việt BẮT BUỘC PHẢI VIẾT HOA (tên người, tên con vật, tên đồ vật, địa danh, võ học kỹ năng, hệ thống, tổ chức) thì ĐỀU LÀ THỰC THỂ CẦN BÓC TÁCH!

🎯 HỆ THỐNG PHÂN LOẠI THỰC THỂ (5 LOẠI PHỔ BIẾN + LOẠI ĐẶC BIỆT KHÁC):
1. 'NAME': Tên người, nhân vật:
   - Họ tên đầy đủ, tên chữ, tên gọi thân mật, đạo hiệu, danh xưng, tước hiệu, tôn xưng.
   - Ngoại hiệu giang hồ / hảo hán / danh hiệu võ lâm (ví dụ: Bạch Y Tú Sĩ, Thác Tháp Thiên Vương, Mạc Trước Thiên, Báo Tử Đầu...).
   - Tên cúng cơm, tên dân dã nông thôn của nhân vật (ví dụ: Nhị Cẩu, Đại Tráng, Mộc Đầu, Thiết Đản...).
   - Lưu ý họ '杨' trong tên người luôn luôn dịch là 'Dương' (Dương Đại Bưu, Dương Tiễn, Dương Quá...).

2. 'CREATURE': Tên con vật, linh thú, yêu thú:
   - Tên riêng của thú cưng, con vật nuôi, linh sủng được đặt tên (kể cả tên bình dân nông thôn như: Hắc Cẩu, Bạch Miêu, Than Cục / Môi Cầu, Bánh Bao, Đại Hắc, Tiểu Hoàng...).
   - Tên chung của các chủng loài yêu thú, thần thú, dị thú mang bản sắc (ví dụ: Kim Sí Đại Bàng, Cửu Vĩ Thiên Hồ, Hắc Sí Ma Viên, Thôn Thiên Mãng...).

3. 'PLACE': Địa danh, không gian:
   - Núi non, sông biển, hồ đầm, thôn xóm, trấn, quận huyện, thành trì, quốc gia, bí cảnh, động phủ, giới diện, cấm địa.

4. 'SECT': Thế lực, tổ chức:
   - Tông môn, môn phái, thế gia gia tộc, bang hội, triều đình, hoàng triều, cơ quan, quân đoàn, phủ nha.

5. 'ITEM': Vật phẩm, trang bị, bảo vật:
   - Pháp bảo, thần binh, vũ khí, đan dược, linh thảo, linh dược, điển tịch, tác phẩm văn học, điển cố nghệ thuật.

6. 'SKILL': Võ học, công pháp:
   - Tuyệt kỹ võ công, tâm pháp tu luyện, thần thông, chiêu thức, trận pháp, bí thuật, cấm thuật.

7. 'OTHER': Mọi thực thể đặc biệt khác:
   - Hệ thống (System), bảng trạng thái, cảnh giới tu vi đặc biệt, thần vị, danh xưng quy ước thế giới quan riêng biệt.

🎯 NGUYÊN TẮC DỊCH TÊN:
- Dịch thật chuẩn, thật hay, đúng âm Hán-Việt văn học bác học chuẩn 100% tiếng Việt có dấu.
- Với tên riêng dân dã/nông thôn (của người hoặc con vật như Hắc Cẩu, Bạch Miêu, Nhị Cẩu...): giữ đúng tính chất tên riêng được gọi.
- Tách sạch động từ/tiền tố ngữ pháp đứng liền trước (như 给, 杀, 救, 看, 当, 见...) và trạng từ/hành động đứng liền sau (như 神色, 冷笑, 说道, 喝道...).
- Đánh giá 'evaluation':
  * "TÊN CỐ ĐỊNH": Cho 'NAME', 'PLACE', 'SECT', 'ITEM' (tên riêng cố định 1-1).
  * "NÊN DÙNG BẢN SẮC": Cho 'SKILL', 'CREATURE', 'OTHER'.
{existing_ref}
=== VĂN BẢN TOÀN BỘ LÔ CHƯƠNG (RAW TEXT) ===
{masked_text}

Yêu cầu trả về DUY NHẤT một JSON object theo đúng định dạng sau, không kèm bất kỳ lời dẫn nào:
{{
  "entities": [
    {{"chinese_name": "林冲", "vietnamese_name": "Lâm Xung", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "nhân vật"}},
    {{"chinese_name": "豹子头", "vietnamese_name": "Báo Tử Đầu", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "ngoại hiệu của Lâm Xung"}},
    {{"chinese_name": "二狗", "vietnamese_name": "Nhị Cẩu", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "tên cúng cơm nông thôn"}},
    {{"chinese_name": "黑狗", "vietnamese_name": "Hắc Cẩu", "entity_type": "CREATURE", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "tên riêng con chó nuôi"}},
    {{"chinese_name": "金翅大鹏", "vietnamese_name": "Kim Sí Đại Bàng", "entity_type": "CREATURE", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "chủng loài thần thú"}},
    {{"chinese_name": "青云宗", "vietnamese_name": "Thanh Vân Tông", "entity_type": "SECT", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "tông môn"}},
    {{"chinese_name": "落霞峰", "vietnamese_name": "Lạc Hà Phong", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "địa danh núi"}},
    {{"chinese_name": "青龙偃月刀", "vietnamese_name": "Thanh Long Yển Nguyệt Đao", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "thần binh binh khí"}},
    {{"chinese_name": "太极拳", "vietnamese_name": "Thái Cực Quyền", "entity_type": "SKILL", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "công pháp võ học"}},
    {{"chinese_name": "大反派系统", "vietnamese_name": "Đại Phản Phái Hệ Thống", "entity_type": "OTHER", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "hệ thống hỗ trợ"}}
  ]
}}
"""

    text_response = ""
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
            }
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await post_gemini_with_retry(client, url, headers, body)
            if resp.status_code != 200:
                raise Exception(f"Lỗi gọi Gemini API (HTTP {resp.status_code}): {resp.text}")
        res_json = resp.json()
        text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()

    parsed = safe_json_loads(text_response)
    raw_entities = parsed.get("entities", []) if isinstance(parsed, dict) else []

    if mapping_table:
        for e in raw_entities:
            if "vietnamese_name" in e and e["vietnamese_name"]:
                e["vietnamese_name"] = unmask_text_with_dictionary(e["vietnamese_name"], mapping_table)

    from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese

    final_entities = []
    seen = set()
    for e in raw_entities:
        if not isinstance(e, dict):
            continue
        ch_name = e.get("chinese_name", "").strip()
        vn_name = e.get("vietnamese_name", "").strip()
        if not ch_name or not vn_name or len(ch_name) < 2 or ch_name in seen:
            continue

        e["chinese_name"] = ch_name
        # Khóa cứng 100% bản dịch cũ nếu đã có trong CSDL các chương trước
        if existing_entities and ch_name in existing_entities:
            e["vietnamese_name"] = existing_entities[ch_name].get("vietnamese_name", vn_name)
        else:
            e["vietnamese_name"] = sanitize_entity_vietnamese(vn_name, ch_name)

        seen.add(ch_name)
        final_entities.append(e)

    return final_entities


async def extract_entities_via_llm(raw_text: str) -> List[Dict[str, Any]]:
    """Hàm tương thích ngược: Bóc tách thực thể cho đoạn văn bản đơn lẻ."""
    return await extract_batch_entities_direct_llm(raw_text)


async def process_2branch_evidence_via_llm(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """Hàm tương thích ngược: chuyển hướng sang bóc tách trực tiếp."""
    candidates = evidence_data.get("branch_1_ner_candidates", [])
    raw_texts = [c.get("context_han", "") for c in candidates if c.get("context_han")]
    combined = "\n".join(raw_texts)
    existing = evidence_data.get("existing_db_entities", {})
    ents = await extract_batch_entities_direct_llm(combined, existing)
    return {"entities": ents}

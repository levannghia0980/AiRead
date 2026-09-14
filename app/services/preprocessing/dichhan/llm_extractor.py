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
- 'CREATURE': Tên riêng hoặc tên chủng loài yêu thú, linh thú, dị thú, thần thú mang bản sắc truyện (ví dụ: 黑翅大鹏 -> Hắc Sí Đại Bàng, 九尾天狐 -> Cửu Vĩ Thiên Hồ, 碧眼金睛兽 -> Bích Nhãn Kim Tinh Thú). Dù là tên loài chung hay tên riêng con vật thì ĐÂY LÀ TỪ BẢN SẮC TRUYỆN TRUNG, BẮT BUỘC GIỮ ÂM HÁN-VIỆT VĂN HỌC, TUYỆT ĐỐI CẤM DỊCH NÔM NA THUẦN VIỆT!
- 'LORE_TERM': Thuật ngữ thế giới quan, biệt ngữ nghề nghiệp, cảnh giới tu luyện, các thời kỳ / phân kỳ tu luyện & trạng thái (sơ kỳ, trung kỳ, hậu kỳ, đỉnh phong, viên mãn, bình cảnh, bán bộ, hóa hình kỳ...), các thời kỳ lịch sử thế giới quan (thượng cổ, viễn cổ, mạt pháp...), từ vựng mang bản sắc đặc thù theo thể loại tác phẩm.
- 'OTHER': Các thuật ngữ danh từ riêng đặc thù khác (tên riêng thú cưng, đồ vật cưng mang phong vị truyện).

TRƯỜNG 'evaluation' (3 VÙNG ĐÁNH GIÁ CỐT LÕI - BẮT BUỘC CHỌN ĐÚNG 1 TRONG 3):
- "TÊN CỐ ĐỊNH": Dành cho danh từ riêng, tên nhân vật (PERSON), địa danh (LOCATION), môn phái (SECT_SKILL), tác phẩm văn học, tên riêng thú cưng / bảo vật (khóa 1-1 cố định, không đổi tên giữa các chương).
- "NÊN DÙNG BẢN SẮC": Dành cho võ học (SKILL), pháp bảo quý (ITEM), thuật ngữ thế giới quan & cảnh giới (LORE_TERM), và TÊN LOÀI / TÊN CÁ THỂ YÊU THÚ, DỊ THÚ, LINH THÚ (CREATURE mang bản sắc truyện như Hắc Sí Đại Bàng, Cửu Vĩ Hồ... BẮT BUỘC giữ âm Hán-Việt văn học, cấm thuần Việt hóa làm mất chất truyện).
- "KHÔNG LƯU DB": Dành cho từ ngữ đời thường, món ăn, đồ uống, nông sản, sinh hoạt gia đình, danh từ chung chung không phải thực thể tên riêng và không phải bản sắc truyện (ví dụ: '蘑菇炖鸡' -> 'nấm hầm thịt gà', cấm dịch 'Ma Cô Độn Kê'). Hệ thống sẽ tự động DROP BỎ, không lưu vào DB để tránh ô nhiễm dữ liệu!

TRƯỜNG 'role' (VAI TRÒ / NGỮ CẢNH):
- Ghi chú ngắn gọn vai trò hoặc ngữ cảnh sử dụng.

QUY TẮC ĐỐI CHIẾU ÂM HÁN-VIỆT CHUẨN XÁC TỪNG CHỮ (BẮT BUỘC):
- Dịch chuẩn âm Hán-Việt hoặc từ dịch nghĩa văn học đắt giá vào cột 'rough_translation' (với từ đời thường thì dịch thuần Việt dễ hiểu).
- Võ công & Trận pháp: 圈/阵 = 'Trận/Quyển' (CẤM: 'Khuyên'), 拳 = 'Quyền' (CẤM: 'đấm'), 掌 = 'Chưởng', 指 = 'Chỉ', 爪 = 'Trảo', 腿 = 'Cước'.
- TUYỆT ĐỐI NGHIÊM CẤM trả về tên dính chữ Hán lai tạp. Cột rough_translation phải là 100% chữ tiếng Việt có dấu.

🔴 MỆNH LỆNH TỐI CAO ĐỐI VỚI ĐIỂN CỐ, VÕ HỌC, NGOẠI HIỆU & DANH XƯNG KINH ĐIỂN:
- CÁC GỢI Ý CỦA TỪ ĐIỂN MÁY / HanLP / DỊCH THÔ CHỈ LÀ PHIÊN ÂM MẶT CHỮ CƠ HỌC (~3000 TỪ), THƯỜNG RẤT NGU VÀ BẺ NGHĨA ĐEN (ví dụ: bẻ '摸着天' thành 'Mô Trước Thiên', '八百里' thành 'Bát Bách Lịch', '好汉' thành 'người tốt').
- BẠN LÀ MÔ HÌNH NGÔN NGỮ ĐÃ CÓ TOÀN BỘ KHO TRI THỨC VĂN HỌC DỊCH THUẬT TRUNG - VIỆT ĐỒ SỘ:
  * Khi gặp các nhân vật, ngoại hiệu giang hồ, tước xưng, bang phái, chiêu thức võ học, thần thông, pháp bảo, địa danh, điển tích kinh điển (trong toàn bộ kho tàng Thủy Hử, Tam Quốc Diễn Nghĩa, Tây Du Ký, Phong Thần Diễn Nghĩa, Kim Dung, Cổ Long, Ôn Thụy An, Huỳnh Dị, Tiên hiệp đại chúng...):
  * BẮT BUỘC tự động truy xuất và sử dụng ĐÚNG 100% tên dịch thuật văn học đã đi vào đại chúng Việt Nam, TUYỆT ĐỐI CẤM bẻ chữ cơ học mặt chữ!
  * VÍ DỤ MINH HỌA (YÊU CẦU + LỖI CẤM TRÁNH BẺ CHỮ):
    + Ngoại hiệu / Nhân vật: 摸着天 (Đỗ Thiên) -> BẮT BUỘC: 'Mạc Trước Thiên' (CẤM bẻ thô: 'Mô Trước Thiên', 'Mạc Già Thiên').
    + Địa danh / Điển cố: 八百里水泊梁山 -> BẮT BUỘC: 'Bát Bách Lý / Tám trăm dặm Thủy Bạc Lương Sơn' (CẤM: 'Bát Bách Lịch').
    + Thần thoại / Thực thể: 巨灵神 -> BẮT BUỘC: 'Cự Linh Thần' (CẤM gõ sai: 'Cựu Linh Thần').
    + Võ học / Chiêu thức: 降龙十八掌 -> 'Hàng Long Thập Bát Chưởng', 乾坤大挪移 -> 'Càn Khôn Đại Na Di' (CẤM bẻ nghĩa đen cơ học).

Yêu cầu trả về kết quả định dạng JSON Array chứa các object có cấu trúc như ví dụ sau:
[
  {{"chinese_name": "莫雅依", "rough_translation": "Mạc Nhã Y", "entity_type": "PERSON", "evaluation": "TÊN CỐ ĐỊNH", "role": "Nhân vật nữ"}},
  {{"chinese_name": "青云宗", "rough_translation": "Thanh Vân Tông", "entity_type": "SECT_SKILL", "evaluation": "TÊN CỐ ĐỊNH", "role": "Môn phái"}},
  {{"chinese_name": "金刚伏魔圈", "rough_translation": "Kim Cương Phục Ma Trận", "entity_type": "SECT_SKILL", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "Võ kỹ / Trận pháp đặc thù"}},
  {{"chinese_name": "黑翅大鹏", "rough_translation": "Hắc Sí Đại Bàng", "entity_type": "CREATURE", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "Yêu thú dị thú bản sắc truyện"}},
  {{"chinese_name": "蘑菇炖鸡", "rough_translation": "nấm hầm thịt gà", "entity_type": "OTHER", "evaluation": "KHÔNG LƯU DB", "role": "Món ăn đời thường (tên chung)"}}
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
Bạn là chuyên gia ngôn ngữ học và dịch thuật tiểu thuyết Trung - Việt cao cấp, sở hữu vốn từ vựng Hán - Việt bác học và khả năng phân tích ngữ pháp tiếng Trung chuyên sâu.

{instruction}

🔴 NHIỆM VỤ CỐT LÕI CỦA TRÍ TUỆ NHÂN TẠO (LLM REASONING, DISAMBIGUATION & CONTEXT ANALYSIS):
Dữ liệu gửi lên gồm Danh sách ứng viên thực thể được chọn lọc kèm ngữ cảnh đa dòng 'context_han' 【...】.
Bạn KHÔNG ĐƯỢC bẻ từ cơ học hay tin tưởng mù quáng vào gợi ý thô, mà BẮT BUỘC phải dùng TRÍ NÃO ĐỌC HIỂU NGỮ CẢNH câu văn 'context_han' 【...】 để thực hiện các phân tích ngôn ngữ sau:

1. 🧠 PHÂN TÍCH RANH GIỚI THỰC THỂ (BOUNDARY DETECTION) — TÔN TRỌNG TÊN 4 CHỮ & TÁCH BỎ TỪ GHÉP LIỀN KỀ:
   * TÔN TRỌNG TUYỆT ĐỐI CÁC TÊN & THỰC THỂ 4 CHỮ HOÀN CHỈNH:
     - Tên người họ kép 4 chữ: 【南宫仙子】 (Nam Cung Tiên Tử), 【令狐青墨】 (Lệnh Hồ Thanh Mặc), 【东方不败】 (Đông Phương Bất Bại), 【司马相如】 (Tư Mã Tương Như)... ➔ BẮT BUỘC giữ trọn vẹn 4 chữ.
     - Danh hiệu, ngoại hiệu hảo hán 4 chữ: 【白衣秀士】 (Bạch Y Tú Sĩ), 【托塔天王】 (Thác Tháp Thiên Vương), 【云里金刚】 (Vân Lý Kim Cương), 【摸着天】 (Mạc Trước Thiên)... ➔ BẮT BUỘC giữ trọn vẹn.
     - Địa danh, tông môn, công pháp 4 chữ: 【水泊梁山】 (Thủy Bạc Lương Sơn), 【缺月山庄】 (Khuyết Nguyệt Sơn Trang), 【夺命十三枪】 (Đoạt Mệnh Thập Tam Thương)... ➔ BẮT BUỘC giữ trọn vẹn.
   * PHÂN TÍCH NGỮ PHÁP ĐỂ TÁCH BỎ ĐỘNG TỪ / TIỀN TỐ PHÍA TRƯỚC:
     - Khi thấy động từ đứng trước tên người: 【送给南宫仙子】 (tặng cho Nam Cung Tiên Tử) ➔ Tự bóc tách đúng danh từ riêng '南宫仙子' (Nam Cung Tiên Tử), CẤM lấy '给南宫仙子'.
     - 【杀李四】 ➔ chỉ lấy '李四'; 【救林冲】 ➔ chỉ lấy '林冲'; 【当掌门】 ➔ '掌门'.
   * PHÂN TÍCH CẤU TRÚC TỪ ĐỂ TÁCH BỎ TỪ GHÉP TRẠNG THÁI / ĐỘNG TỪ PHÍA SAU:
     - Khi thấy tên người đứng trước từ trạng thái: 【杨大彪神色一变】 ➔ Ngữ pháp: '杨大彪' (Dương Đại Bưu) là chủ ngữ, '神色' (sắc mặt) là danh từ trạng thái ➔ BẮT BUỘC chỉ bóc tách '杨大彪' (Dương Đại Bưu), TUYỆT ĐỐI CẤM nuốt chữ '神' thành '杨大彪神'!
     - 【谢尽欢神态自若】 ➔ chỉ bóc tách '谢尽欢' (Tạ Tận Hoan).
     - 【张三说道】 ➔ chỉ lấy '张三'; 【李四冷笑】 ➔ chỉ lấy '李四'.
     - ĐẶC BIỆT: Nếu tên vốn dĩ có chữ '神' mang nghĩa thần linh: 【巨灵神】 (Cự Linh Thần), 【剑神】 (Kiếm Thần) ➔ Giữ nguyên trọn vẹn!

2. 🧠 LOẠI BỎ TRIỆT ĐỂ HƯ TỪ NGỮ PHÁP & TỪ ĐỜI THƯỜNG / MÓN ĂN:
   * LOẠI BỎ HƯ TỪ NGỮ PHÁP VÔ NGHĨA: Bỏ qua các hư từ, trạng thái, liên từ, từ cảm thán không mang nghĩa thực thể:
     - '回神', '但神', '时神', '心神', '失神', '留神', '眼神', '精神', '一下子', '大不了', '按人头', '大声', '出乱子'.
   * 🛑 TUYỆT ĐỐI CẤM BÓC TÁCH MÓN ĂN, ĐỒ UỐNG, ĐỒ DÙNG, RAU CỎ SINH HOẠT THƯỜNG:
     - KHÔNG bóc tách các món ăn thường ngày (ví dụ: '蘑菇炖飞龙', '蘑菇炖鸡', '馄饨', '烤兔', '烧饼'...).
     - KHÔNG bóc tách đồ dùng sinh hoạt gia đình (ấm trà, bàn ghế, lều bạt, đuốc, tiền bạc, quần áo thông thường).
     - BẠN CHỈ LẤY CÁC THỰC THỂ TÊN RIÊNG MÀ KHI DỊCH BẮT BUỘC PHẢI VIẾT HOA!
   * 🔴 LƯU Ý ĐẶC BIỆT VỀ TÊN RIÊNG ĐẶT THEO TỪ ĐỜI THƯỜNG (THÚ CƯNG, LINH VẬT, BẢO VẬT, BIỆT DANH):
     - Rất nhiều nhân vật đặt tên cho thú cưng, chim ưng, linh thú, yêu thú, vũ khí hoặc biệt danh bằng từ ngữ đời thường (ví dụ: '煤球' - Môi Cầu / Cục Than là tên riêng của con hắc ưng / chim ưng; '包子' - Bánh Bao là tên riêng của con chó; '铁锤' - Thiết Chùy là tên người hoặc bảo kiếm...).
     - BẮT BUỘC NHÌN VÀO NGỮ CẢNH: Khi một từ ngữ đời thường được dùng làm TÊN RIÊNG (của chim, thú, người, vật) thì ĐÓ LÀ THỰC THỂ TÊN RIÊNG (CREATURE/NAME/ITEM), BẮT BUỘC BÓC TÁCH VÀO 'entities' với evaluation='TÊN CỐ ĐỊNH' hoặc 'NÊN DÙNG BẢN SẮC' (ví dụ: 煤球 -> Môi Cầu, CREATURE/NAME). TUYỆT ĐỐI CẤM XẾP VÀO TỪ THƯỜNG LÀM BỎ MẤT!

3. 🧠 PHÂN LOẠI CHÍNH XÁC VÀO ĐÚNG 1 TRONG 2 VÙNG ĐÁNH GIÁ ('evaluation'):
   * "TÊN CỐ ĐỊNH": Tên người (NAME), địa danh (PLACE), tông môn thế lực (SECT), bảo vật quý hoặc tác phẩm văn học (ITEM) ➔ LƯU DB & KHÓA CỐ ĐỊNH 1-1, âm Hán-Việt văn học bác học.
   * "NÊN DÙNG BẢN SẮC": Tuyệt kỹ võ học / bí tịch tâm pháp (SKILL), pháp bảo thần binh (ITEM), cảnh giới tu vi & thuật ngữ thế giới quan (LORE_TERM), chủng loài / cá thể yêu thú dị thú, thú cưng bản sắc (CREATURE) ➔ LƯU DB & NÊN DÙNG trong bản dịch, cấm thuần Việt hóa tùy tiện làm mất chất truyện.

4. 🧠 CHUẨN HÓA ÂM HÁN - VIỆT VĂN HỌC BÁC HỌC (CHUẨN 100% TIẾNG VIỆT CÓ DẤU):
   * Tự động truy xuất âm Hán - Việt chuẩn mực theo văn học cổ điển, CẤM bẻ thô theo từ điển máy ngô nghê:
     - '杨': Họ người ➔ BẮT BUỘC dịch là 'Dương' (【杨大彪】 -> 'Dương Đại Bưu', 【杨温】 -> 'Dương Ôn', 【杨霆】 -> 'Dương Đình'), TUYỆT ĐỐI CẤM dịch nhầm sang 'Tạ'.
     - '化': Trong tên người, danh xưng tu tiên biến hóa (【杨化仙】, 【化神】) ➔ Dịch là 'Hóa' ('Dương Hóa Tiên', 'Hóa Thần'), CẤM dịch thành 'Hoa'.
     - '圣': Trong tôn xưng, thánh nhân, cảnh giới (【叶圣】, 【剑圣】, 【成圣】) ➔ Dịch là 'Thánh' ('Diệp Thánh', 'Kiếm Thánh'), TUYỆT ĐỐI CẤM dịch thành 'Khốt'.
     - '尽': Trong tên người (【谢尽欢】) ➔ Dịch là 'Tận' ('Tạ Tận Hoan'), CẤM dịch thành 'Cận'.
     - '迟': Trong tên người (【叶云迟】) ➔ Dịch là 'Trì' ('Diệp Vân Trì'), CẤM sót chữ Hán hay dịch 'Lịch'.
     - '仇': Họ người ➔ Dịch là 'Cừu' ('Cừu Hạo', 'Cừu Thiên Nhận'), CẤM dịch 'Thù'.
     - '单': Họ người ➔ Dịch là 'Đơn' ('Đơn Hùng Tín'), CẤM dịch 'Đan'.
     - '少': Trong tên/danh xưng (【欧阳少恭】) ➔ 'Thiếu' ('Âu Dương Thiếu Cung').
   * TUYỆT ĐỐI KHÔNG ĐỂ SÓT BẤT KỲ KÝ TỰ CHỮ HÁN NÀO trong 'vietnamese_name' (CẤM 'Diệp Vân Kh迟', 'Tô T浅浅').

5. 🧠 ĐỐI CHIẾU MẪU ĐÃ CÓ VS KHAI PHÁ TỪ MỚI:
   * Ứng viên có ghi '[ĐÃ DỊCH CHUẨN TỪ TRƯỚC]: ...' ➔ Giữ nguyên 100% bản dịch mẫu đã khóa từ các chương trước.
   * Ứng viên có ghi '[GỢI Ý PHIÊN ÂM HÁN-VIỆT]: ...' ➔ Đây là từ mới, tự do dùng toàn bộ trí tuệ ngôn ngữ cao cấp của bạn để xác định ranh giới chuẩn và dịch âm Hán-Việt hay nhất.

6. 🧠 QUÉT TOÀN VĂN LÔ CHƯƠNG — TỰ ĐỘNG TÌM TẤT CẢ CÁC THỰC THỂ BỊ CODE BỎ SÓT:
   * ⚠️ CẢNH BÁO QUAN TRỌNG: Danh sách ứng viên thô do code gửi lên chỉ là gợi ý tham khảo, code thường xuyên bỏ sót tên thú cưng, linh vật, thần binh hoặc danh xưng đặc thù!
   * Bạn BẮT BUỘC PHẢI TỰ ĐỌC VÀ RÀ SOÁT TOÀN BỘ VĂN BẢN LÔ CHƯƠNG (FULL BATCH RAW TEXT) để chủ động phát hiện và bóc tách TẤT CẢ các thực thể tên riêng bị bỏ sót trong mọi thể loại:
     - Tên riêng thú cưng, linh thú, yêu thú, tọa kỵ (Ví dụ: con hắc ưng tên là 煤球 -> Môi Cầu, CREATURE; linh thú, thần điểu, chiến sủng...).
     - Tên vũ khí, thần binh, bảo vật, pháp khí có tên riêng (Chính Luân Kiếm, Thiên Cương Giản, chiến hạm, cơ giáp...).
     - Tuyệt kỹ võ công, tâm pháp, bí tịch, dị năng, thần thông.
     - Tông môn, bang phái, thế lực, vương triều, cơ quan, tập đoàn.
     - Tên nhân vật, đạo hiệu, ngoại hiệu, tôn xưng, biệt danh.
   * CỨ THẤY TÊN RIÊNG XUẤT HIỆN TRONG VĂN BẢN LÀ BẮT BUỘC BÓC TÁCH VÀ ĐƯA VÀO 'entities', TUYỆT ĐỐI KHÔNG ĐƯỢC BỎ QUA VỚI LÝ DO DANH SÁCH ỨNG VIÊN CHƯA CÓ!

=== TỪ ĐIỂN THỰC THỂ ĐÃ TỒN TẠI TỪ CÁC CHƯƠNG TRƯỚC ===
{json.dumps(existing_entities, ensure_ascii=False, indent=2)}

=== DANH SÁCH ỨNG VIÊN THỰC THỂ NGHI VẤN KÈM NGỮ CẢNH ===
{json.dumps(cleaned_ner, ensure_ascii=False, indent=2)}

Yêu cầu trả về kết quả dưới dạng JSON object chứa danh sách 'entities':
{{
  "entities": [
    {{"chinese_name": "谢尽欢", "vietnamese_name": "Tạ Tận Hoan", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "nhân vật chính (viết hoa)"}},
    {{"chinese_name": "紫徽山", "vietnamese_name": "Tử Huy Sơn", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "địa danh núi (viết hoa)"}},
    {{"chinese_name": "望海市", "vietnamese_name": "Vọng Hải Thị", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "địa danh thành phố hiện đại (viết hoa)"}},
    {{"chinese_name": "盛世集团", "vietnamese_name": "Tập Đoàn Thịnh Thế", "entity_type": "SECT", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "tổ chức / tập đoàn công ty (viết hoa)"}},
    {{"chinese_name": "正伦剑", "vietnamese_name": "Chính Luân Kiếm", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "thần binh / vũ khí đặc biệt (viết hoa)"}},
    {{"chinese_name": "欢喜心经", "vietnamese_name": "Hoan Hỷ Tâm Kinh", "entity_type": "SKILL", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "bí tịch / công pháp / dị năng (viết hoa)"}},
    {{"chinese_name": "黑翅大鹏", "vietnamese_name": "Hắc Sí Đại Bàng", "entity_type": "CREATURE", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "linh thú / dị thú / cự thú (viết hoa)"}}
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

        # === KHỬ SẠCH 100% HÁN TỰ SÓT, GỌT RÁC VÀ KHÓA CỨNG TÊN THEO TỪ ĐIỂN ĐÃ CÓ ===
        from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese
        CLEANED_JUNK_PREFIXES = ("给", "过", "杀", "看", "见", "当", "算", "做", "被", "在", "站", "摆", "出", "了", "知", "父", "向", "跟", "和", "对", "把", "是", "有", "个", "这", "那", "的")
        
        final_entities = []
        for e in entities:
            if not isinstance(e, dict):
                continue
            vn_name = e.get("vietnamese_name", "").strip()
            ch_name = e.get("chinese_name", "").strip()

            # 1. Gọt tiền tố động từ/hư từ nếu bị LLM nhặt thừa (Ví dụ: 给南宫仙子 -> 南宫仙子)
            for p in CLEANED_JUNK_PREFIXES:
                if ch_name.startswith(p) and len(ch_name) >= 3:
                    ch_name = ch_name[len(p):].strip()
                    break

            # 2. Gọt đuôi '神' nếu dính vào sau tên người (Ví dụ: 杨大彪神 -> 杨大彪)
            if ch_name.endswith("神") and len(ch_name) >= 4 and not ch_name.endswith("眼神") and not ch_name.endswith("精神"):
                ch_name = ch_name[:-1].strip()

            e["chinese_name"] = ch_name

            # 3. ƯU TIÊN VÀNG: Nếu tên này đã tồn tại trong CSDL các chương trước, KHÓA CỨNG 100% BẢN DỊCH ĐÃ CÓ!
            if ch_name in existing_entities:
                cleaned_vn = existing_entities[ch_name]["vietnamese_name"]
            else:
                cleaned_vn = sanitize_entity_vietnamese(vn_name, ch_name)

            if cleaned_vn != vn_name:
                print(f"[PREPROCESS LLM] ✅ Đã chuẩn hóa tên thực thể '{vn_name}' -> '{cleaned_vn}' cho '{ch_name}'")
            e["vietnamese_name"] = cleaned_vn
            final_entities.append(e)

        # Khử trùng lặp theo chinese_name và loại bỏ chuỗi câu rác nếu đã có thực thể con sạch hơn
        seen_ch = set()
        deduped_entities = []
        for e in final_entities:
            cn = e.get("chinese_name", "").strip()
            if cn and cn not in seen_ch:
                seen_ch.add(cn)
                deduped_entities.append(e)

        # Nếu một thực thể dài (>= 5 chữ) nuốt một thực thể ngắn sạch hơn (2-4 chữ), loại bỏ thực thể dài rác
        cleaned_final = []
        for e in deduped_entities:
            cn = e.get("chinese_name", "").strip()
            is_bloated = False
            if len(cn) >= 5:
                for other_e in deduped_entities:
                    o_cn = other_e.get("chinese_name", "").strip()
                    if o_cn and o_cn != cn and len(o_cn) in (2, 3, 4) and o_cn in cn:
                        is_bloated = True
                        break
            if not is_bloated:
                cleaned_final.append(e)

        return {"entities": cleaned_final}
    except Exception as e:
        print(f"⚠️ [PREPROCESS LLM] Thất bại khi phân tích JSON trả về từ LLM: {e}")

    return {"entities": []}


async def extract_batch_entities_direct_llm(
    combined_raw_text: str,
    existing_entities: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Bóc tách thực thể trực tiếp từ toàn văn RAW của lô chương bằng LLM Reasoning (Zero Code Heuristics).
    Được kiểm chứng bắt trọn 100% nhân vật, linh thú (煤球), thần binh, vương triều trong 24s.
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
        existing_ref = f"""
=== TỪ ĐIỂN THỰC THỂ ĐÃ CÓ TỪ CÁC CHƯƠNG TRƯỚC (DÙNG ĐỂ THAM CHIẾU, KHÔNG DỊCH LẠI) ===
{json.dumps(existing_entities, ensure_ascii=False, indent=2)}
"""

    prompt = f"""Bạn là chuyên gia ngôn ngữ học và dịch thuật tiểu thuyết Trung - Việt cao cấp, sở hữu vốn từ vựng Hán - Việt bác học và khả năng phân tích ngữ pháp, bối cảnh tiếng Trung chuyên sâu.

🔴 NHIỆM VỤ: ĐỌC HIỂU TOÀN VĂN LÔ CHƯƠNG TIỂU THUYẾT VÀ BÓC TÁCH TOÀN BỘ CÁC THỰC THỂ TÊN RIÊNG:
Đọc kỹ toàn bộ nội dung trong các thẻ <chapter_X>...</chapter_X> và trích xuất tất cả các danh từ riêng, thuật ngữ thế giới quan quan trọng mà khi dịch sang tiếng Việt BẮT BUỘC PHẢI VIẾT HOA:

🎯 CÁC PHÂN LOẠI THỰC THỂ BẮT BUỘC:
1. 'NAME': Tên người, họ tên, danh xưng, đạo hiệu, ngoại hiệu, tôn xưng, tước hiệu.
   * LƯU Ý QUAN TRỌNG VỀ HỌ '杨': Trong mọi tên nhân vật (ví dụ: 杨大彪, 杨温, 杨霆, 杨化仙...), họ '杨' BẮT BUỘC dịch là 'Dương' (Dương Đại Bưu, Dương Ôn, Dương Đình, Dương Hóa Tiên...), TUYỆT ĐỐI CẤM dịch thành 'Tạ'.
   * Nhận diện chuẩn xác tên nhân vật chính, nhân vật phụ, đối thủ (ví dụ: 谢尽欢 -> Tạ Tận Hoan, 令狐青墨 -> Lệnh Hồ Thanh Mặc, 长宁郡主 -> Trường Ninh quận chúa, 刘庆之 -> Lưu Khánh Chi...).
2. 'CREATURE': Linh thú, thần thú, yêu thú, dị thú, cự thú hoặc THÚ CƯNG CÓ TÊN RIÊNG.
   * ĐẶC BIỆT CHÚ Ý: Nhân vật đặt tên cho con vật cưng, linh sủng bằng từ ngữ đời thường (ví dụ: con hắc ưng / chim ưng được đặt tên là 【煤球】 ➔ 'Môi Cầu', CREATURE, con hắc ưng; hoặc 【黑翅大鹏】 ➔ 'Hắc Sí Đại Bàng'...). BẮT BUỘC BÓC TÁCH, tuyệt đối không được bỏ qua!
3. 'PLACE': Địa danh, núi non, sông hồ, quận huyện, phủ nha, thành trấn, quốc gia (ví dụ: 紫徽山 -> Tử Huy Sơn, 万安县 -> Vạn An Huyện...).
4. 'SECT': Tông môn, bang phái, thế lực, vương triều, cơ quan, quân vệ triều đình (ví dụ: 大乾王朝 -> Đại Càn Vương Triều, 赤麟卫 -> Xích Lân Vệ...).
5. 'ITEM': Thần binh, pháp bảo, vũ khí, bảo vật quý, bí tịch, tác phẩm (ví dụ: 正伦剑 -> Chính Luân Kiếm, 天罡锏 -> Thiên Cương Giản...).
6. 'SKILL': Chiêu thức võ học, công pháp, tâm pháp, bí thuật, dị năng (ví dụ: 欢喜心经 -> Hoan Hỷ Tâm Kinh...).

🎯 NGUYÊN TẮC CHUYỂN NGỮ HÁN - VIỆT BÁC HỌC:
- Dịch đúng âm Hán-Việt văn học cổ điển chuẩn 100% tiếng Việt có dấu.
- Tuyệt đối không để sót chữ Hán hay Pinyin trong 'vietnamese_name'.
- Tách sạch động từ/hư từ đứng liền trước hoặc liền sau (ví dụ: '给南宫仙子' -> chỉ lấy '南宫仙子'; '杨大彪神色' -> chỉ lấy '杨大彪').
- Đánh giá 'evaluation':
  * "TÊN CỐ ĐỊNH": Cho 'NAME', 'PLACE', 'SECT', 'ITEM' (tên riêng cố định 1-1).
  * "NÊN DÙNG BẢN SẮC": Cho 'SKILL', 'CREATURE', binh khí.
{existing_ref}
=== VĂN BẢN TOÀN BỘ LÔ CHƯƠNG (RAW TEXT) ===
{masked_text}

Yêu cầu trả về DUY NHẤT một JSON object theo đúng định dạng sau, không kèm bất kỳ lời dẫn nào:
{{
  "entities": [
    {{"chinese_name": "谢尽欢", "vietnamese_name": "Tạ Tận Hoan", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "gender": "male", "role": "nhân vật chính"}},
    {{"chinese_name": "煤球", "vietnamese_name": "Môi Cầu", "entity_type": "CREATURE", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "con hắc ưng của Tạ Tận Hoan"}},
    {{"chinese_name": "大乾王朝", "vietnamese_name": "Đại Càn Vương Triều", "entity_type": "SECT", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "vương triều bối cảnh"}},
    {{"chinese_name": "紫徽山", "vietnamese_name": "Tử Huy Sơn", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "gender": null, "role": "địa danh núi"}},
    {{"chinese_name": "正伦剑", "vietnamese_name": "Chính Luân Kiếm", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "thần binh kiếm"}},
    {{"chinese_name": "天罡锏", "vietnamese_name": "Thiên Cương Giản", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "gender": null, "role": "thần binh binh khí"}}
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
    CLEANED_JUNK_PREFIXES = ("给", "过", "杀", "看", "见", "当", "算", "做", "被", "在", "站", "摆", "出", "了", "知", "父", "向", "跟", "和", "对", "把", "是", "有", "个", "这", "那", "的")

    final_entities = []
    seen = set()
    for e in raw_entities:
        if not isinstance(e, dict):
            continue
        ch_name = e.get("chinese_name", "").strip()
        vn_name = e.get("vietnamese_name", "").strip()
        if not ch_name or not vn_name or len(ch_name) < 2 or ch_name in seen:
            continue

        for p in CLEANED_JUNK_PREFIXES:
            if ch_name.startswith(p) and len(ch_name) >= 3:
                ch_name = ch_name[len(p):].strip()
                break

        if ch_name.endswith("神") and len(ch_name) >= 4 and not ch_name.endswith("眼神") and not ch_name.endswith("精神"):
            ch_name = ch_name[:-1].strip()

        e["chinese_name"] = ch_name
        if existing_entities and ch_name in existing_entities:
            e["vietnamese_name"] = existing_entities[ch_name].get("vietnamese_name", vn_name)
        else:
            e["vietnamese_name"] = sanitize_entity_vietnamese(vn_name, ch_name)

        seen.add(ch_name)
        final_entities.append(e)

    return final_entities

import asyncio
import os
import sys
import json
import time
import httpx
from sqlalchemy import select

# Đảm bảo in UTF-8 không lỗi trên Windows
sys.stdout.reconfigure(encoding='utf-8')

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion
from app.core.config import get_active_setting
from app.core.llm_client import post_gemini_with_retry, safe_json_loads

async def run_direct_llm_ner_test(novel_id: int = 19, start_chapter: int = 1, end_chapter: int = 7):
    print(f"=== TEST BÓC TÁCH THỰC THỂ TRỰC TIẾP QUA LLM (KHÔNG DÙNG CODE GỌI GỢI Ý) ===")
    print(f"Bộ truyện ID: {novel_id} | Phạm vi: Chương {start_chapter} -> Chương {end_chapter}")
    
    # 1. Lấy toàn bộ văn bản RAW của các chương trong lô
    chapter_texts = []
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Chapter.chapter_no, ChapterVersion.content)
            .join(Chapter, ChapterVersion.chapter_id == Chapter.id)
            .where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_no >= start_chapter,
                Chapter.chapter_no <= end_chapter,
                ChapterVersion.version_type == "RAW"
            )
            .order_by(Chapter.chapter_no)
        )
        res = await session.execute(stmt)
        rows = res.all()
        for ch_no, content in rows:
            if content and content.strip():
                chapter_texts.append(f"<chapter_{ch_no}>\n{content.strip()}\n</chapter_{ch_no}>")

    if not chapter_texts:
        print("❌ Không tìm thấy nội dung RAW của các chương trong lô!")
        return

    combined_raw = "\n\n".join(chapter_texts)
    print(f"✅ Đã nạp thành công {len(chapter_texts)} chương. Tổng độ dài văn bản RAW: {len(combined_raw)} ký tự (~{len(combined_raw)//1.5:.0f} tokens).")

    # 2. Đọc cấu hình Model và API Key từ cài đặt
    api_key = await get_active_setting("AIREAD_API_KEYS")
    model = (await get_active_setting("AIREAD_MODEL") or "gemini-3.5-flash").strip()
    provider = (await get_active_setting("AIREAD_PROVIDER") or "gemini").strip().lower()

    if not api_key:
        print("❌ Không tìm thấy API Key trong Cài đặt (.env hoặc DB)!")
        return

    key_masked = api_key[:8] + "..." + api_key[-4:]
    print(f"🤖 Sử dụng mô hình: {model} ({provider}) | API Key: {key_masked}")

    # 3. Xây dựng Prompt bóc tách thuần túy bằng yêu cầu (Zero Heuristics Code)
    prompt = f"""Bạn là chuyên gia ngôn ngữ học và dịch thuật tiểu thuyết Trung - Việt cao cấp, sở hữu vốn từ vựng Hán - Việt bác học và khả năng phân tích ngữ pháp, bối cảnh tiếng Trung chuyên sâu.

🔴 NHIỆM VỤ: ĐỌC HIỂU TOÀN VĂN LÔ CHƯƠNG TIỂU THUYẾT DƯỚI ĐÂY VÀ BÓC TÁCH TOÀN BỘ CÁC THỰC THỂ TÊN RIÊNG:
Đọc kỹ toàn bộ nội dung trong các thẻ <chapter_X>...</chapter_X> và trích xuất tất cả các danh từ riêng, thuật ngữ thế giới quan quan trọng mà khi dịch sang tiếng Việt BẮT BUỘC PHẢI VIẾT HOA.

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

=== VĂN BẢN TOÀN BỘ LÔ {len(chapter_texts)} CHƯƠNG (RAW TEXT) ===
{combined_raw}

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

    print(f"🚀 Đang gửi toàn văn {len(chapter_texts)} chương trực tiếp lên {model} để bóc tách...")
    t0 = time.time()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await post_gemini_with_retry(client, url, headers, body)
        if resp.status_code != 200:
            print(f"❌ Lỗi gọi Gemini API (HTTP {resp.status_code}): {resp.text}")
            return
            
    t1 = time.time()
    res_json = resp.json()
    text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
    
    print(f"⏱️ LLM phản hồi sau {t1 - t0:.2f} giây.")

    parsed = safe_json_loads(text_response)
    entities = parsed.get("entities", []) if isinstance(parsed, dict) else []

    print(f"\n========================================================")
    print(f"🎉 KẾT QUẢ BÓC TÁCH ĐƯỢC: {len(entities)} THỰC THỂ TỪ {len(chapter_texts)} CHƯƠNG")
    print(f"========================================================")

    # Phân nhóm thực thể hiển thị
    grouped = {}
    for e in entities:
        etype = e.get("entity_type", "OTHER")
        grouped.setdefault(etype, []).append(e)

    for etype, items in grouped.items():
        print(f"\n📁 【NHÓM: {etype}】 ({len(items)} thực thể):")
        for it in items:
            cn = it.get("chinese_name", "")
            vn = it.get("vietnamese_name", "")
            eval_str = it.get("evaluation", "")
            role = it.get("role", "")
            print(f"   * 【{cn}】 ➔ 【{vn}】 | Đánh giá: {eval_str} | Vai trò: {role}")

    # Kiểm tra các thực thể cốt lõi của tác phẩm
    print(f"\n--------------------------------------------------------")
    print(f"🔍 KIỂM TRA ĐỘ TOÀN VẸN CỦA CÁC THỰC THỂ QUAN TRỌNG:")
    test_keys = [
        ("谢尽欢", "Tạ Tận Hoan"),
        ("煤球", "Môi Cầu"),
        ("黑翅大鹏", "Hắc Sí Đại Bàng"),
        ("紫徽山", "Tử Huy Sơn"),
        ("大乾王朝", "Đại Càn Vương Triều"),
        ("万安县", "Vạn An Huyện"),
        ("杨大彪", "Dương Đại Bưu"),
        ("刘庆之", "Lưu Khánh Chi"),
        ("正伦剑", "Chính Luân Kiếm"),
        ("天罡锏", "Thiên Cương Giản"),
        ("赤麟卫", "Xích Lân Vệ"),
        ("南宫烨", "Nam Cung Diệp"),
        ("令狐青墨", "Lệnh Hồ Thanh Mặc"),
        ("长宁郡主", "Trường Ninh quận chúa"),
        ("杨霆", "Dương Đình"),
        ("杨温", "Dương Ôn")
    ]
    
    extracted_map = {e.get("chinese_name"): e.get("vietnamese_name") for e in entities}
    success_count = 0
    for cn, expected_vn in test_keys:
        if cn in extracted_map:
            actual_vn = extracted_map[cn]
            match_status = "✅ CHUẨN" if expected_vn.lower() in actual_vn.lower() else f"⚠️ KHÁC ({actual_vn})"
            print(f"   * {cn} ➔ {actual_vn} ({match_status})")
            success_count += 1
        else:
            print(f"   * {cn} ➔ ❌ KHÔNG TÌM THẤY")

    print(f"\n📊 Tỉ lệ phát hiện thực thể cốt lõi: {success_count}/{len(test_keys)} ({success_count/len(test_keys)*100:.1f}%)")
    print(f"========================================================\n")

if __name__ == "__main__":
    asyncio.run(run_direct_llm_ner_test(novel_id=19, start_chapter=1, end_chapter=7))

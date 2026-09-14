import os
import json
from typing import Dict, Any, List
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, NovelEntity
from app.services.preprocessing.dichhan.entity_extractor import extract_ner_branch
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

SYSTEM_PROMPT_INSTRUCTION = (
    "Nhiệm vụ của bạn là nhận diện, bóc tách và chuẩn hóa TẤT CẢ CÁC THỰC THỂ TÊN RIÊNG (bắt buộc phải VIẾT HOA CHỮ CÁI ĐẦU khi dịch sang tiếng Việt) từ văn bản tiểu thuyết tiếng Trung, ÁP DỤNG ĐA DẠNG CHO MỌI THỂ LOẠI (Tiên hiệp, Kiếm hiệp, Đô thị hiện đại, Khoa huyễn / Tinh tế không gian, Mạt thế viễn tưởng, Huyền huyễn phương Tây, Lịch sử quân sự).\n\n"
    "🎯 NGUYÊN TẮC VÀNG TỐI CAO: CHỈ LẤY DANH TỪ RIÊNG CẦN VIẾT HOA\n"
    "- Bạn CHỈ tìm và trả về những thực thể mà trong văn bản dịch tiếng Việt BẮT BUỘC PHẢI ĐƯỢC VIẾT HOA (Proper Nouns).\n"
    "- TUYỆT ĐỐI CẤM lấy danh từ chung đời thường, món ăn, thức uống, rau củ thịt cá, đồ dùng sinh hoạt gia đình, trạng thái, động từ thông thường viết thường.\n\n"
    "CÁC NHÓM THỰC THỂ CẦN BÓC TÁCH (ÁP DỤNG MỌI THỂ LOẠI):\n"
    "- 'NAME': Tên nhân vật, danh xưng, họ tên, biệt danh, ngoại hiệu, tước hiệu, chức danh đi liền tên (Ví dụ: Tiên hiệp/Cổ trang: 谢尽欢 -> Tạ Tận Hoan, 白衣秀士 -> Bạch Y Tú Sĩ, 长宁郡主 -> Trường Ninh quận chúa; Đô thị: 陆沉 -> Lục Trầm, 楚总 -> Sở Tổng; Khoa huyễn/Tây phương: 亚瑟 -> Arthur / A Sơ, 凯撒 -> Caesar).\n"
    "- 'PLACE': Địa danh, sông núi, biển hồ, thành thị, quận huyện, quốc gia, tinh cầu, căn cứ, trạm không gian, địa điểm đặc thù (Ví dụ: 紫徽山 -> Tử Huy Sơn, 丹州 -> Đan Châu, 万安县 -> Vạn An Huyện; Đô thị: 望海市 -> Vọng Hải Thị; Khoa huyễn/Mạt thế: 泰拉星 -> Thái Lạp Tinh / Tinh cầu Terra, 0号避难所 -> Căn cứ Tị Nạn số 0).\n"
    "- 'SECT': Tổ chức, tông môn, bang phái, công ty tập đoàn, cơ quan chính phủ, chiến đội, liên minh thế lực (Ví dụ: 青云宗 -> Thanh Vân Tông, 巡抚衙门 -> Tuần Phủ Nha Môn, 大乾王朝 -> Đại Càn Vương Triều; Đô thị: 盛世集团 -> Tập đoàn Thịnh Thế; Khoa huyễn/Vũ trụ: 银河联邦 -> Liên Bang Ngân Hà, 黎明战队 -> Chiến Đội Lê Minh).\n"
    "- 'SKILL': Chiêu thức, bí tịch võ công, tâm pháp, công pháp, phép thuật, dị năng, hệ thống kỹ năng đặc dị (Ví dụ: 欢喜心经 -> Hoan Hỷ Tâm Kinh, 降龙十八掌 -> Hàng Long Thập Bát Chưởng, 空间撕裂 -> Không Gian Tê Liệt, 绝对零度 -> Tuyệt Đối Linh Độ).\n"
    "- 'ITEM': Tên riêng vũ khí, thần binh, pháp bảo, cơ giáp, tàu chiến không gian, tác phẩm kinh điển, bí tịch (Ví dụ: 正伦剑 -> Chính Luân Kiếm, 天罡锏 -> Thiên Cương Giản, 暴风赤红 -> Bạo Phong Xích Hồng / Crimson Typhoon, 金瓶梅 -> Kim Bình Mai).\n"
    "- 'CREATURE': Tên chủng tộc đặc thù, dị thú, linh thú, yêu thú, sinh vật ngoài hành tinh, tang thi dị biến mang tên riêng (Ví dụ: 黑翅大鹏 -> Hắc Sí Đại Bàng, 九尾天狐 -> Cửu Vĩ Thiên Hồ, 泰坦巨兽 -> Cự Thú Titan, 嗜血暴君 -> Thị Huyết Bạo Quân).\n\n"
    "2 VÙNG ĐÁNH GIÁ (evaluation):\n"
    "- 'TÊN CỐ ĐỊNH': Tên người (NAME), địa danh (PLACE), tổ chức / môn phái (SECT), tác phẩm kinh điển (ITEM) ➔ Khóa cứng 1-1 cố định, không đổi tên giữa các chương.\n"
    "- 'NÊN DÙNG BẢN SẮC': Binh khí, võ công, dị năng (SKILL/ITEM), chủng tộc dị thú (CREATURE) ➔ Giữ chuẩn danh xưng văn học/thể loại, cấm thuần Việt hóa tùy tiện.\n\n"
    "Yêu cầu trả về kết quả dưới dạng JSON:\n"
    "{\n"
    '  "entities": [\n'
    '    {"chinese_name": "谢尽欢", "vietnamese_name": "Tạ Tận Hoan", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "role": "nhân vật chính", "gender": "male"},\n'
    '    {"chinese_name": "紫徽山", "vietnamese_name": "Tử Huy Sơn", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "role": "địa danh núi", "gender": null},\n'
    '    {"chinese_name": "正伦剑", "vietnamese_name": "Chính Luân Kiếm", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "thần binh bảo kiếm", "gender": null},\n'
    '    {"chinese_name": "盛世集团", "vietnamese_name": "Tập Đoàn Thịnh Thế", "entity_type": "SECT", "evaluation": "TÊN CỐ ĐỊNH", "role": "tổ chức / tập đoàn", "gender": null},\n'
    '    {"chinese_name": "黑翅大鹏", "vietnamese_name": "Hắc Sí Đại Bàng", "entity_type": "CREATURE", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "dị thú linh cầm", "gender": null}\n'
    "  ]\n"
    "}"
)

async def collect_chapter_entities(chapter_id: int) -> Dict[str, Any]:
    """
    Thu thập dữ liệu thực thể từ bản gốc RAW phục vụ bóc tách NER và phân loại thực thể qua LLM.
    Bóc tách từ Hán nghi vấn + ngữ cảnh vi mô (`context_han`) + gợi ý đối chiếu (`suggested_hanviet_example`).
    """
    async with AsyncSessionLocal() as session:
        stmt_ch = select(Chapter).where(Chapter.id == chapter_id)
        res_ch = await session.execute(stmt_ch)
        chapter = res_ch.scalar_one_or_none()
        
        if not chapter:
            raise Exception(f"Không tìm thấy Chapter ID {chapter_id} trong cơ sở dữ liệu.")
            
        novel_id = chapter.novel_id
        
        stmt_ver = select(ChapterVersion).where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.version_type == "RAW"
        )
        res_ver = await session.execute(stmt_ver)
        raw_version = res_ver.scalar_one_or_none()

    raw_path = raw_version.file_path if raw_version else None

    raw_text = ""
    if raw_path and os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
        raw_text = sanitize_chinese_raw_text(raw_text)

    # 1. Thu thập ứng viên NER từ bản gốc
    ner_raw = await extract_ner_branch(novel_id, raw_text) if raw_text else []

    # 2. Gói dữ liệu gửi LLM (Kèm cặp song song: Chữ Hán gốc & Bản dịch mẫu đã có kèm cả cụm ngữ cảnh xung quanh)
    from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name
    ner_candidates = []
    for item in ner_raw:
        if item.get("db_example"):
            sugg = f"[ĐÃ DỊCH CHUẨN TỪ TRƯỚC]: {item['db_example']}"
        else:
            sugg = f"[GỢI Ý PHIÊN ÂM HÁN-VIỆT]: {build_hanviet_name(item['han'])}"
        ner_candidates.append({
            "original_han": item["han"],
            "suggested_hanviet_example": sugg,
            "context_han": item.get("context_han", item["han"]),
            "entity_type": item.get("entity_type", "OTHER"),
            "positions_in_raw": item.get("positions_in_raw", [])
        })

    existing_db_dict = {}
    async with AsyncSessionLocal() as session:
        stmt_ent = select(NovelEntity).where(
            NovelEntity.novel_id == novel_id,
            NovelEntity.entity_type != "CORRECTION"
        ).order_by(NovelEntity.frequency_count.desc()).limit(200)
        res_ent = await session.execute(stmt_ent)
        for e in res_ent.scalars():
            if e.chinese_name and e.rough_translation:
                existing_db_dict[e.chinese_name.strip()] = {
                    "vietnamese_name": e.rough_translation.strip(),
                    "entity_type": e.entity_type or "NAME",
                    "role": e.role or ""
                }

    return {
        "chapter_id": chapter_id,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "existing_db_entities": existing_db_dict,
        "branch_1_ner_candidates": ner_candidates,
        "_internal_ner_details": ner_raw
    }

async def collect_batch_entities(chapter_ids: List[int]) -> Dict[str, Any]:
    """
    Gom ứng viên thực thể của nhiều chương thành 1 payload duy nhất gửi LLM.
    Lọc bỏ trùng lặp, xếp hạng theo độ ưu tiên ngữ cảnh để giữ prompt gọn gàng (< 4,000 tokens),
    không làm bùng nổ token chạm trần giới hạn 250k TPM của Google Gemini.
    """
    from app.services.preprocessing.dichhan.entity_extractor import DEFINING_KEYWORDS
    STOP_INTERNAL = frozenset(['了', '的', '着', '在', '从', '把', '也', '如', '同', '没', '并', '又', '便', '就', '与', '给', '被', '到', '去', '来', '说', '道', '想', '看', '听', '问', '得', '过', '是'])

    combined_candidates = []
    internal_details = {}
    novel_id = None
    
    for cid in chapter_ids:
        try:
            res = await collect_chapter_entities(cid)
            if novel_id is None:
                novel_id = res["novel_id"]
            
            combined_candidates.extend(res["branch_1_ner_candidates"])
            internal_details[cid] = {
                "ner": res["_internal_ner_details"]
            }
        except Exception as e:
            print(f"Error collecting evidence for chapter {cid}: {e}")
            
    # Xoá trùng lặp & Chấm điểm xếp hạng ứng viên (Scoring & Ranking)
    b1_seen = set()
    scored_candidates = []
    
    for item in combined_candidates:
        k = item.get("original_han") or item.get("han")
        if not k or k in b1_seen:
            continue
        b1_seen.add(k)

        # Loại bỏ các cụm quá dài (> 5 ký tự) hoặc chứa hư từ/động từ ngắt câu bên trong
        if len(k) < 2 or len(k) > 5:
            continue
        if any(sc in k for sc in STOP_INTERNAL):
            continue

        et = item.get("entity_type", "OTHER")
        ctx = item.get("context_han", "")
        has_kw = any(kw in ctx for kw in DEFINING_KEYWORDS)

        # Bỏ qua từ loại OTHER có 2 chữ nếu không có từ khóa định danh
        if et == "OTHER" and not has_kw and len(k) == 2:
            continue

        # Tính điểm ưu tiên cho ứng viên thực thể thực sự
        score = 0
        if any(kw in ctx for kw in ("名为", "名叫", "黑鹰", "灵兽", "神兽", "佩剑", "贴身奴婢")):
            score += 100
        elif has_kw:
            score += 50

        if et in ("CREATURE", "ITEM", "SKILL", "SECT", "PLACE"):
            score += 50
        elif et == "NAME":
            score += 35

        if len(k) in (3, 4):
            score += 20
        if len(item.get("positions_in_raw", [])) >= 2:
            score += 15

        # Đưa vào danh sách có chấm điểm (chỉ gửi các trường cần thiết cho LLM)
        clean_item = {
            "original_han": item["original_han"],
            "suggested_hanviet_example": item["suggested_hanviet_example"],
            "context_han": item["context_han"]
        }
        scored_candidates.append((score, clean_item))

    # Sắp xếp theo thứ tự ưu tiên cao nhất
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    # Giới hạn tối đa 150 ứng viên tinh hoa nhất của lô để payload luôn nhẹ nhàng (~3,000 tokens), an toàn tuyệt đối
    b1_final = [c for s, c in scored_candidates[:150]]

    existing_db_dict = {}
    if novel_id:
        async with AsyncSessionLocal() as session:
            stmt_ent = select(NovelEntity).where(
                NovelEntity.novel_id == novel_id,
                NovelEntity.entity_type != "CORRECTION"
            ).order_by(NovelEntity.frequency_count.desc()).limit(200)
            res_ent = await session.execute(stmt_ent)
            for e in res_ent.scalars():
                if e.chinese_name and e.rough_translation:
                    existing_db_dict[e.chinese_name.strip()] = {
                        "vietnamese_name": e.rough_translation.strip(),
                        "entity_type": e.entity_type or "NAME",
                        "role": e.role or ""
                    }

    return {
        "chapter_ids": chapter_ids,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "existing_db_entities": existing_db_dict,
        "branch_1_ner_candidates": b1_final,
        "_internal_batch_details": internal_details
    }

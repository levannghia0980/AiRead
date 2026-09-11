import os
import json
from typing import Dict, Any, List
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, ChapterVersion, NovelEntity
from app.services.preprocessing.dichhan.entity_extractor import extract_ner_branch
from app.services.preprocessing.dichhan.raw_text_cleaner import sanitize_chinese_raw_text

SYSTEM_PROMPT_INSTRUCTION = (
    "Nhiệm vụ của bạn là nhận diện, bóc tách và phân loại chuẩn xác các danh từ riêng, thuật ngữ thế giới quan, võ học, bảo vật, địa danh từ văn bản tiếng Trung để phục vụ mô hình dịch thuật.\n\n"
    "CÁC QUY TẮC PHÂN LOẠI THỰC THỂ (entity_type) - BẮT BUỘC CHỌN 1 TRONG CÁC LOẠI SAU:\n"
    "- 'NAME': Tên nhân vật, biệt danh thân mật, ngoại hiệu giang hồ, nhân vật thần thoại / lịch sử, danh xưng xưng hô (ví dụ: 晁盖 -> Triều Cái, 巨灵神 -> Cự Linh Thần, 摸着天 -> Mạc Già Thiên, 白衣秀士 -> Bạch Y Tú Sĩ, 杜迁 -> Đỗ Thiên, 宋万 -> Tống Vạn, 潘金莲 -> Phan Kim Liên, 小金莲 -> Tiểu Kim Liên, 王威 -> Vương Uy, 莫雅仪 -> Mạc Nhã Nghi).\n"
    "- 'PLACE': Địa danh, căn cứ, linh cung, thành phố, sông núi, hồ đầm, điện thờ (ví dụ: 水泊梁山 -> Thủy Bạc Lương Sơn, 蓼儿洼 -> Liêu Nhi Oa, 金沙滩 -> Kim Sa Than, 宛子城 -> Uyển Tử Thành, 聚义厅 -> Tụ Nghĩa Sảnh, 天桑灵宫 -> Thiên Tang Linh Cung, 望海市 -> Vọng Hải thị, 少林寺 -> Thiếu Lâm Tự, 武当山 -> Võ Đang sơn, 华山 -> Hoa Sơn).\n"
    "- 'SECT': Tông môn, bang phái, thế lực, ma giáo, bang hội, tổ chức. DANH TỪ RIÊNG VIẾT HOA (ví dụ: 丐帮 -> Cái Bang, 明教 -> Minh Giáo, 天地会 -> Thiên Địa Hội, 日月神教 -> Nhật Nguyệt Thần Giáo, 全真教 -> Toàn Chân Giáo, 武当派 -> Võ Đang phái, 少林派 -> Thiếu Lâm phái, 星辰宗 -> Tinh Thần Tông).\n"
    "- 'SKILL': Tuyệt kỹ võ công, chiêu thức, công pháp, thân pháp, kỹ năng hệ thống, thần thông (ví dụ: 夺命十三枪 -> Đoạt Mệnh Thập Tam Thương, 法天象地 -> Pháp Thiên Tượng Địa, 灵眼 -> Linh Nhãn, 降龙十八掌 -> Hàng Long Thập Bát Chưởng, 凌波微步 -> Lăng Ba Vi Bộ, 雷神之息 -> Lôi Thần Chi Tức, 太极拳 -> Thái Cực Quyền). TUYỆT ĐỐI CẤM dịch nôm na theo nghĩa đen thành ngữ dân gian hoặc từ ngữ giao tiếp đời thường ngô nghê.\n"
    "- 'ITEM': Kiếm, binh khí, bảo vật, pháp bảo, thần khí, trang bị, đan dược, HOẶC TÁC PHẨM VĂN HỌC, ĐIỂN TÍCH, SÁCH KINH ĐIỂN (ví dụ: 金瓶梅 -> Kim Bình Mai, 水浒传 -> Thủy Hử Truyện, 西游记 -> Tây Du Ký, 道德经 -> Đạo Đức Kinh, 妖姬 -> Yêu Cơ, 藏剑 -> Tàng Kiếm). Với sách/tác phẩm, BẮT BUỘC giữ lại 100% với evaluation 'TÊN CỐ ĐỊNH', TUYỆT ĐỐI CẤM BỎ QUA!\n"
    "- 'LORE_TERM': Thuật ngữ thế giới quan, biệt ngữ nghề nghiệp, cảnh giới tu luyện (Luyện Khí, Trúc Cơ, Kim Đan...), các thời kỳ / phân kỳ tu luyện & trạng thái (sơ kỳ, trung kỳ, hậu kỳ, đỉnh phong, viên mãn, bình cảnh, bán bộ, hóa hình kỳ...), các thời kỳ lịch sử thế giới quan (thượng cổ, thái cổ, viễn cổ, hồng hoang, mạt pháp...), phẩm giai (Hoàng phẩm, Huyền phẩm...), từ vựng mang bản sắc đặc thù thể loại.\n"
    "- 'OTHER': Danh từ riêng hoặc thuật ngữ đặc thù khác.\n\n"
    "QUY TẮC ĐÁNH GIÁ CÁCH DÙNG (evaluation) - ĐIỀU HƯỚNG MÔ HÌNH DỊCH:\n"
    "- 'TÊN CỐ ĐỊNH': BẮT BUỘC dành cho 'NAME', 'PLACE', 'SECT'. Khóa 1-1, bắt buộc dùng thống nhất xuyên suốt mọi chương, cấm đổi tên.\n"
    "- 'NÊN DÙNG BẢN SẮC': Dành cho 'SKILL', 'ITEM', 'LORE_TERM'. Đây là từ vựng đắt giá mang phong vị tác phẩm, NÊN DÙNG trong bản dịch, cấm thuần Việt hóa tùy tiện làm mất chất truyện.\n"
    "- 'NÊN DỊCH THUẦN VIỆT': Dành cho các từ ngữ nên diễn đạt thuần Việt tự nhiên, linh hoạt theo ngữ cảnh.\n\n"
    "HƯỚNG DẪN DỊCH VÀ SÀNG LỌC BẰNG CHỨNG:\n"
    "1. SÀNG LỌC THÔNG MINH, KHÔNG TRẢ VỀ TỪ RÁC:\n"
    "   - Trường gợi ý 'suggested_hanviet_example' và 'db_example' CHỈ LÀ THAM KHẢO THÔ BẬC THẤP.\n"
    "   - BẮT BUỘC phân tích vi ngữ cảnh 【...】 để chọn lọc: CHỈ giữ lại danh từ riêng, thực thể đích thực.\n"
    "   - TUYỆT ĐỐI KHÔNG bóc tách các phó từ, liên từ, từ cảm thán, số lượng từ, từ ngữ đời thường (như '倒是', '一下子', '大不了', '好日子', '大家', '按人头', '大声', '出乱子', '租子', '媳妇', '围裙', '勺子', '大包', '死尸') thành thực thể!\n"
    "2. ĐỒNG BỘ VỚI TỪ ĐIỂN ĐÃ LƯU: Nếu từ Hán gốc ĐÃ CÓ trong danh sách từ điển các chương trước ('existing_db_entities'), hãy ưu tiên giữ sự nhất quán xuyên suốt bộ truyện.\n"
    "3. BỐI PHẬN / VAI TRÒ VÀ GIỚI TÍNH: Phân tích ngữ cảnh đoạn văn để xác định đúng vai trò ('role') và giới tính ('gender': 'male', 'female', hoặc null).\n"
    "4. DỊCH CHUẨN HÁN-VIỆT / VĂN HỌC ĐẮT GIÁ:\n"
    "   - Đối chiếu từng chữ Hán gốc để dịch theo âm Hán-Việt chuẩn xác, đúng âm và thanh điệu.\n"
    "   - TUYỆT ĐỐI NGHIÊM CẤM TÊN DÍNH CHỮ HÁN LAI TẠP: vietnamese_name BẮT BUỘC là 100% tiếng Việt có dấu thanh.\n"
    "   - Với nhân vật, ngoại hiệu giang hồ, thần thoại, điển tích, tác phẩm văn học (Thủy Hử, Kim Bình Mai, Tam Quốc, Tây Du, Kim Dung...): BẮT BUỘC dùng đúng tên dịch thuật văn học đại chúng (ví dụ: 金瓶梅 -> 'Kim Bình Mai', 晁盖 -> 'Triều Cái', 巨灵神 -> 'Cự Linh Thần', 摸着天 -> 'Mạc Già Thiên', 白衣秀士 -> 'Bạch Y Tú Sĩ', 云里金刚 -> 'Vân Lý Kim Cương', 沧州小旋风 -> 'Thương Châu Tiểu Toàn Phong'). CẤM bẻ nghĩa đen cơ học!\n"
    "5. 🔴 BẢO TOÀN TRỌN VẸN CẢ CỤM DANH TỪ — TUYỆT ĐỐI CẤM CẮT CỤT NGOẠI HIỆU / TÊN RIÊNG:\n"
    "   - Khi nhận diện ngoại hiệu, tên riêng, danh hiệu, võ học: BẮT BUỘC giữ trọn vẹn cả cụm danh xưng hoàn chỉnh.\n"
    "   - TUYỆT ĐỐI CẤM cắt cụt đầu đuôi làm rụng từ thành các mảnh vụn vô nghĩa (như cắt thành '里金刚', '衣秀士', '州小旋风', '飞将').\n"
    "   - TUYỆT ĐỐI CẤM dính từ nối, giới từ phía trước vào tên (như '和短命二郎', '江鸿飞将').\n"
    "   - TUYỆT ĐỐI CẤM băm nhỏ một tên riêng/ngoại hiệu thành nhiều thực thể con!\n"
    "6. CHUẨN XÁC TÊN GỐC (chinese_name) & TRÁNH GỘP TỪ RÁC:\n"
    "   - 'chinese_name' BẮT BUỘC là danh từ riêng / thực thể cốt lõi chuẩn xác (thường 2 - 4 chữ Hán, tối đa 5-6 chữ với chiêu thức/tác phẩm).\n"
    "   - Tuyệt đối KHÔNG gộp các động từ, tính từ miêu tả, phó từ hay từ cảm thán xung quanh vào chinese_name (ví dụ: '晁盖', cấm gộp thành '喜欢火拼的晁盖'; '水泊梁山', cấm gộp thừa động từ phía trước).\n"
    "   - Ký hiệu 【...】 giúp bạn định vị trọng tâm thực thể; hãy bóc tách đúng cụm danh từ thực thể cốt lõi, không kéo theo các từ ngữ không liên quan bên ngoài.\n\n"
    "Yêu cầu trả về kết quả dưới dạng JSON:\n"
    "{\n"
    '  "entities": [\n'
    '    {"chinese_name": "王威", "vietnamese_name": "Vương Uy", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "role": "nhân vật chính", "gender": "male"},\n'
    '    {"chinese_name": "白衣秀士", "vietnamese_name": "Bạch Y Tú Sĩ", "entity_type": "NAME", "evaluation": "TÊN CỐ ĐỊNH", "role": "ngoại hiệu Vương Luân", "gender": "male"},\n'
    '    {"chinese_name": "丐帮", "vietnamese_name": "Cái Bang", "entity_type": "SECT", "evaluation": "TÊN CỐ ĐỊNH", "role": "bang phái giang hồ", "gender": null},\n'
    '    {"chinese_name": "水泊梁山", "vietnamese_name": "Thủy Bạc Lương Sơn", "entity_type": "PLACE", "evaluation": "TÊN CỐ ĐỊNH", "role": "căn cứ địa danh", "gender": null},\n'
    '    {"chinese_name": "夺命十三枪", "vietnamese_name": "Đoạt Mệnh Thập Tam Thương", "entity_type": "SKILL", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "thương pháp võ học", "gender": null},\n'
    '    {"chinese_name": "妖姬", "vietnamese_name": "Yêu Cơ", "entity_type": "ITEM", "evaluation": "NÊN DÙNG BẢN SẮC", "role": "thần binh bảo thương", "gender": null}\n'
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

    # 2. Gói dữ liệu gửi LLM (Kèm cặp song song: Chữ Hán gốc & Bản dịch gợi ý tra cứu)
    from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name
    ner_candidates = [
        {
            "original_han": item["han"],
            "suggested_hanviet_example": item.get("db_example") or build_hanviet_name(item["han"]),
            "context_han": item.get("context_han", item["han"])
        }
        for item in ner_raw
    ]

    return {
        "chapter_id": chapter_id,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "existing_db_entities": {},
        "branch_1_ner_candidates": ner_candidates,
        "_internal_ner_details": ner_raw
    }

async def collect_batch_entities(chapter_ids: List[int]) -> Dict[str, Any]:
    """
    Gom ứng viên thực thể của nhiều chương thành 1 payload duy nhất gửi LLM.
    Lọc bỏ trùng lặp và loại bỏ các từ con bị nuốt trong từ mẹ dài hơn (Sub-string suppression).
    """
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
            
    # Xoá trùng lặp (Deduplicate)
    b1_seen = set()
    b1_unique = []
    for item in combined_candidates:
        k = item.get("original_han") or item.get("han")
        if k and k not in b1_seen:
            b1_seen.add(k)
            b1_unique.append(item)

    existing_db_dict = {}
    if novel_id and chapter_ids:
        async with AsyncSessionLocal() as session:
            from app.models.schema import ChapterEntityLink
            stmt_ent = select(NovelEntity).join(ChapterEntityLink).where(
                ChapterEntityLink.chapter_id.in_(chapter_ids),
                NovelEntity.entity_type != "CORRECTION"
            )
            res_ent = await session.execute(stmt_ent)
            for e in res_ent.scalars():
                if e.chinese_name and e.rough_translation:
                    existing_db_dict[e.chinese_name] = {
                        "vietnamese_name": e.rough_translation,
                        "entity_type": e.entity_type or "NAME",
                        "role": e.role or ""
                    }

    # Sub-string suppression an toàn: Loại bỏ chuỗi rác dính liên từ phía trước hoặc mẩu rác cắt xén
    from app.services.preprocessing.dichhan.common_lists import CHINESE_SURNAMES, EPITHET_SUFFIXES, LEADING_STRIP_PARTICLES
    from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP
    b1_sorted = sorted(b1_unique, key=lambda x: len((x.get("original_han") or x.get("han") or "").strip()), reverse=True)
    b1_final = []
    suppressed_cands = set()
    for i, item_long in enumerate(b1_sorted):
        k_long = (item_long.get("original_han") or item_long.get("han") or "").strip()
        if k_long in suppressed_cands:
            continue
        for item_short in b1_sorted[i + 1:]:
            k_short = (item_short.get("original_han") or item_short.get("han") or "").strip()
            if k_short in suppressed_cands:
                continue
            if k_short and k_long and (k_short in k_long) and len(k_short) < len(k_long):
                # Nếu k_long chỉ là k_short bị dính giới từ / liên từ phía trước (như 和摸着天, 但晁盖):
                # Thì loại bỏ k_long rác, TUYỆT ĐỐI KHÔNG được loại bỏ k_short!
                if any(k_long.startswith(p) for p in LEADING_STRIP_PARTICLES) or any(k_long.startswith(p) for p in ["可是", "但是", "如果", "让", "但", "便", "就"]):
                    suppressed_cands.add(k_long)
                    continue
                
                # Không triệt tiêu k_short nếu k_short là thực thể hoàn chỉnh độc lập
                is_standalone_entity = (
                    k_short in SPECIAL_ENTITIES_MAP or
                    any(k_short.startswith(s) for s in CHINESE_SURNAMES) or
                    any(k_short.endswith(ep) for ep in EPITHET_SUFFIXES) or
                    k_short in existing_db_dict
                )
                if not is_standalone_entity:
                    suppressed_cands.add(k_short)
        if k_long not in suppressed_cands:
            b1_final.append(item_long)
    b1_unique = b1_final

    return {
        "chapter_ids": chapter_ids,
        "novel_id": novel_id,
        "system_prompt_instruction": SYSTEM_PROMPT_INSTRUCTION,
        "existing_db_entities": existing_db_dict,
        "branch_1_ner_candidates": b1_unique,
        "_internal_batch_details": internal_details
    }

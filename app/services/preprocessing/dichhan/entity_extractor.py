import re
from typing import Dict, List, Set, Tuple, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import NamesDictionary, NovelEntity
from app.services.preprocessing.dichhan.common_lists import CHINESE_SURNAMES, TITLE_SUFFIXES, TITLE_PREFIXES, ENTITY_COMPOUND_SUFFIXES
from app.services.unblock.unblock_pipeline import is_exact_sensitive_word

# Các ký tự tiếng Trung thông dụng không dùng làm tên riêng
CHINESE_STOP_CHARS = set([
    "的", "了", "是", "在", "有", "个", "和", "你", "很", "不", "只", "被", "看", "一", "可", 
    "用", "甚", "虽", "还", "怎", "欲", "也", "着", "立", "怒", "该", "感", "终", "马", "放", 
    "第", "知", "抽", "干", "吟", "激", "气", "隔", "爱", "转", "失", "淫", "扭", "顶", "度", "差",
    "开", "举", "嘴", "强", "轻", "羞", "耻", "勉", "撞", "动", "地", "得", "成", "作", "变", "高"
])

PREFIX_NON_SURNAME = set(["紧", "慌", "夸", "身", "高"]) # Chặn 紧张, 慌张, 夸张, 身高

def is_valid_chinese_term(term: str) -> bool:
    """Kiểm tra xem chuỗi có phải là thực thể chữ Hán chuẩn hay không (độ dài >= 2 và chỉ chứa chữ Hán)"""
    if not term or len(term) < 2:
        return False
    clean_term = term.replace('\x00', '').strip()
    return bool(re.match(r'^[\u4e00-\u9fff]+$', clean_term))

def get_context_han(raw_lines: List[str], line_idx: int, char_start: int, char_end: int) -> str:
    """Lấy từ Hán nghi vấn kèm 1 ký tự ngữ cảnh trước và sau trong bản gốc RAW"""
    if line_idx < 0 or line_idx >= len(raw_lines):
        return ""
    line = raw_lines[line_idx]
    start = max(0, char_start - 1)
    end = min(len(line), char_end + 1)
    return line[start:end]

async def extract_ner_branch(novel_id: int, raw_text: str) -> List[dict]:
    """
    NHÁNH 1: NER & Tìm Tên Thực Thể trong bản RAW (Tiếng Trung gốc)
    - Quét tên chuẩn từ DB.
    - Quét tên mới theo Họ, loại bỏ triệt để các cụm từ thông dụng (há miệng, giơ cao, căng thẳng...).
    - Lọc từ nhạy cảm qua Unblock API.
    - Trích xuất 1 ký tự ngữ cảnh xung quanh (`context_han`).
    """
    if not raw_text:
        return []

    db_examples_map: Dict[str, Tuple[str, str]] = {}
    async with AsyncSessionLocal() as session:
        stmt = select(NovelEntity).where(NovelEntity.novel_id == novel_id)
        res = await session.execute(stmt)
        for row in res.scalars():
            ch_name = row.chinese_name.replace('\x00', '').strip() if row.chinese_name else ""
            vi_trans = row.rough_translation.replace('\x00', '').strip() if row.rough_translation else ""
            if is_valid_chinese_term(ch_name) and vi_trans:
                db_examples_map[ch_name] = (vi_trans, row.entity_type)

        stmt_dict = select(NamesDictionary.chinese_name, NamesDictionary.vietnamese_name)
        res_dict = await session.execute(stmt_dict)
        for row in res_dict:
            ch_name = row[0].replace('\x00', '').strip() if row[0] else ""
            vi_trans = row[1].replace('\x00', '').strip() if row[1] else ""
            if is_valid_chinese_term(ch_name) and vi_trans and (ch_name not in db_examples_map):
                db_examples_map[ch_name] = (vi_trans, "PERSON")

    found_terms: Dict[str, List[dict]] = {}
    raw_lines = raw_text.split('\n')

    for line_idx, line in enumerate(raw_lines):
        if not line.strip():
            continue

        # a. Quét từ DB
        for ch_name in db_examples_map.keys():
            if ch_name in line:
                for match in re.finditer(re.escape(ch_name), line):
                    if ch_name not in found_terms:
                        found_terms[ch_name] = []
                    found_terms[ch_name].append({
                        "line_index": line_idx,
                        "char_start": match.start(),
                        "char_end": match.end()
                    })

        # b. Quét Heuristics theo Họ (Chỉ lấy khi không thuộc DB và là tên thực sự)
        for surname in CHINESE_SURNAMES:
            for match in re.finditer(rf"{surname}[\u4e00-\u9fff]{{1,3}}", line):
                m = match.group()
                idx_start = match.start()
                
                # Bỏ qua nếu ký tự ngay trước đó làm nên từ thông dụng (Ví dụ: 紧张, 慌张, 夸张, 身高)
                if idx_start > 0 and line[idx_start - 1] in PREFIX_NON_SURNAME:
                    continue

                if is_valid_chinese_term(m):
                    # Kiểm tra ký tự bất kỳ trong m thuộc danh sách stop chars
                    if any(c in CHINESE_STOP_CHARS for c in m[1:]):
                        continue

                    prefix_2 = m[:2]
                    if len(m) > 2 and (prefix_2 in db_examples_map or prefix_2 in found_terms):
                        continue

                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append({
                        "line_index": line_idx,
                        "char_start": match.start(),
                        "char_end": match.end()
                    })

        # c. Quét Heuristics theo Tiền tố thân mật / biệt danh (小, 老, 阿, 大)
        for prefix in TITLE_PREFIXES:
            for match in re.finditer(rf"{prefix}[\u4e00-\u9fff]{{1,3}}", line):
                m = match.group()
                if is_valid_chinese_term(m) and not any(c in CHINESE_STOP_CHARS for c in m[1:]):
                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append({
                        "line_index": line_idx,
                        "char_start": match.start(),
                        "char_end": match.end()
                    })

        # d. Quét Heuristics theo Hậu tố chức danh / gia đình / biệt danh (哥, 姐, 弟, 妹, 叔, 伯, 姨, 嫂, 师兄...)
        for suffix in TITLE_SUFFIXES:
            for match in re.finditer(rf"[\u4e00-\u9fff]{{1,3}}{re.escape(suffix)}", line):
                m = match.group()
                if is_valid_chinese_term(m):
                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append({
                        "line_index": line_idx,
                        "char_start": match.start(),
                        "char_end": match.end()
                    })

        # e. Quét Compound Entities (Địa danh, Tông môn, Vật phẩm, Chiêu thức)
        for etype_compound, suffixes_compound in ENTITY_COMPOUND_SUFFIXES.items():
            for suffix_c in suffixes_compound:
                for match in re.finditer(rf"[\u4e00-\u9fff]{{2,5}}{re.escape(suffix_c)}", line):
                    m = match.group()
                    if is_valid_chinese_term(m) and m not in found_terms and m not in db_examples_map:
                        if not any(c in CHINESE_STOP_CHARS for c in m[:2]):
                            found_terms[m] = []
                            found_terms[m].append({
                                "line_index": line_idx,
                                "char_start": match.start(),
                                "char_end": match.end()
                            })

    ner_results = []
    for term, positions in found_terms.items():
        if await is_exact_sensitive_word(term):
            continue

        db_info = db_examples_map.get(term)
        db_example = db_info[0] if db_info else None
        
        raw_type = db_info[1] if db_info else "NAME"
        
        # Chuyển đổi mã cũ -> mã mới
        type_mapping = {
            "PERSON": "NAME",
            "LOCATION": "PLACE",
            "SECT_SKILL": "SECT",
            "ORGANIZATION": "SECT"
        }
        ent_type = type_mapping.get(raw_type, raw_type)
        
        if not db_info:
            if any(s in term for s in TITLE_SUFFIXES) or any(s in term for s in ["哥", "姐", "弟", "妹", "伯", "叔", "爷", "奶"]):
                ent_type = "NAME"
            elif any(s in term for s in ["集团", "公司", "宗", "门", "派", "帮", "教", "盟", "会", "庄", "院"]):
                ent_type = "SECT"
            elif any(s in term for s in ["市", "城", "山", "谷", "峰", "海", "域", "界", "洲", "省", "县", "关", "岛", "村", "河", "江", "潭", "原"]):
                ent_type = "PLACE"
            elif any(s in term for s in ["制药", "重工", "电子", "剑", "珠", "镜", "丹", "符", "鼎", "瓶", "铠", "轮", "刀", "枪", "戟", "弓", "扇", "琴", "甲", "宝", "石", "令", "图"]):
                ent_type = "ITEM"
            elif any(s in term for s in ["掌", "拳", "指", "剑法", "功", "诀", "经", "术", "阵", "法", "印", "吟", "步", "体", "腿", "爪", "身法", "斩"]):
                ent_type = "SKILL"
            else:
                ent_type = "OTHER"

        unique_positions = []
        seen = set()
        for p in positions:
            key = (p["line_index"], p["char_start"], p["char_end"])
            if key not in seen:
                seen.add(key)
                unique_positions.append(p)

        first_p = unique_positions[0]
        context_han = get_context_han(raw_lines, first_p["line_index"], first_p["char_start"], first_p["char_end"])

        ner_results.append({
            "han": term,
            "context_han": context_han,
            "entity_type": ent_type,
            "positions_in_raw": unique_positions,
            "db_example": db_example
        })

    return ner_results


async def extract_entities_from_text(novel_id: int, text: str) -> Tuple[List[dict], List[dict]]:
    """Hàm tương thích backward: Gọi extract_ner_branch"""
    ner_list = await extract_ner_branch(novel_id, text)
    confirmed = [item for item in ner_list if item.get("db_example")]
    new_items = [item for item in ner_list if not item.get("db_example")]
    return confirmed, new_items

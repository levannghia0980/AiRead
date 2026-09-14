import re
from typing import Dict, List, Set, Tuple, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import NamesDictionary, NovelEntity
from app.services.preprocessing.dichhan.common_lists import (
    CHINESE_SURNAMES, TITLE_SUFFIXES, TITLE_PREFIXES, ENTITY_COMPOUND_SUFFIXES, CONTEXT_PLACE_PREFIXES,
    FOLK_NAME_SUFFIXES, FOLK_OCCUPATION_ENTITIES, VERB_TRAILING_CHARS, EPITHET_SUFFIXES
)
from app.services.preprocessing.dichhan.realm_detector import detect_realms
from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP
from app.services.unblock.unblock_pipeline import is_exact_sensitive_word

# Các ký tự tiếng Trung thông dụng không dùng làm tên riêng
CHINESE_STOP_CHARS = set([
    "的", "了", "是", "在", "有", "个", "和", "你", "很", "不", "只", "被", "看", "一", "可", 
    "用", "甚", "虽", "还", "怎", "欲", "也", "立", "怒", "该", "感", "终", "马", "放", 
    "第", "知", "抽", "干", "吟", "激", "气", "隔", "爱", "转", "失", "淫", "扭", "顶", "度", "差",
    "开", "举", "嘴", "强", "轻", "羞", "耻", "勉", "撞", "动", "地", "得", "成", "作", "变", "高"
])

PREFIX_NON_SURNAME = set(["紧", "慌", "夸", "身", "高"]) # Chặn 紧张, 慌张, 夸张, 身高
LEADING_STRIP_PARTICLES = frozenset(["和", "与", "跟", "同", "及", "的", "在", "是", "那", "这", "有", "个", "被", "对", "从", "由", "见", "了", "向", "正", "将"])

# Pre-compiled Regex cho toàn bộ họ để quét siêu tốc O(1)
_SURNAME_PATTERN = "|".join(re.escape(s) for s in sorted(CHINESE_SURNAMES, key=len, reverse=True))
_SURNAME_REGEX = re.compile(rf"({_SURNAME_PATTERN})([\u4e00-\u9fff]{{1,3}})")

def is_valid_chinese_term(term: str) -> bool:
    """Kiểm tra xem chuỗi có phải là thực thể chữ Hán chuẩn hay không (độ dài >= 2 và chỉ chứa chữ Hán)"""
    if not term or len(term) < 2:
        return False
    clean_term = term.replace('\x00', '').strip()
    return bool(re.match(r'^[\u4e00-\u9fff]+$', clean_term))

DEFINING_KEYWORDS = [
    "名为", "名叫", "号为", "人称", "唤作", "唤做", "自称", "乃是", "是一只", "是一头", "是一柄", "是一条", "是一座",
    "黑鹰", "神兽", "灵兽", "妖兽", "异兽", "灵禽", "神鸟", "坐骑", "贴身奴婢", "妖魔", "大鹏", "巨蟒",
    "佩剑", "长剑", "宝刀", "铁锏", "功法", "心法", "宗门", "帮派", "山庄", "道人", "真人", "郡主", "仙子"
]

def get_context_han(raw_lines: List[str], line_idx: int, char_start: int, char_end: int) -> str:
    """
    Lấy từ Hán nghi vấn kèm ngữ cảnh rộng đa dòng có đánh dấu mốc neo 【term】
    Nếu dòng quá ngắn (< 70 ký tự), tự động lấy thêm dòng trước và dòng sau có nội dung để LLM thấy trọn vẹn mạch câu.
    """
    if line_idx < 0 or line_idx >= len(raw_lines):
        return ""
    line = raw_lines[line_idx]
    start = max(0, char_start - 60)
    end = min(len(line), char_end + 60)
    prefix = line[start:char_start]
    target = line[char_start:char_end]
    suffix = line[char_end:end]
    current_span = f"{prefix}【{target}】{suffix}"

    pre_text = ""
    post_text = ""
    if len(line) < 80:
        for p_i in range(line_idx - 1, max(-1, line_idx - 4), -1):
            if raw_lines[p_i].strip():
                pre_text = raw_lines[p_i].strip() + " "
                break
        for s_i in range(line_idx + 1, min(len(raw_lines), line_idx + 4)):
            if raw_lines[s_i].strip():
                post_text = " " + raw_lines[s_i].strip()
                break

    full_context = f"{pre_text}{current_span}{post_text}".strip()
    return full_context

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
        # Chỉ nạp các thực thể tên riêng / bản sắc, loại bỏ từ thường và từ sửa lỗi
        stmt = select(NovelEntity).where(
            NovelEntity.novel_id == novel_id,
            NovelEntity.entity_type.in_(["NAME", "PLACE", "SECT", "SKILL", "ITEM", "CREATURE", "PERSON"])
        )
        res = await session.execute(stmt)
        for row in res.scalars():
            role_str = (row.role or "").upper()
            if "TỪ THƯỜNG" in role_str or "TU THUONG" in role_str or "THAM KHẢO" in role_str or "THAM KHAO" in role_str:
                continue
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

        from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP
        for sp_term, sp_trans in SPECIAL_ENTITIES_MAP.items():
            if sp_term.endswith("期") or sp_term.endswith("时期") or sp_term in ["行者", "装逼", "抱大腿", "火并", "武力值", "战斗力", "大冤种"]:
                continue
            db_examples_map[sp_term] = (sp_trans, "ITEM" if sp_term in ["金瓶梅", "水浒传", "西游记", "红楼梦", "三国演义", "道德经"] else "PERSON")

    # 🚀 TỐI ƯU HÓA: Phân nhóm từ điển theo ký tự đầu tiên (Bucket Indexing / Inverted Index)
    # Sắp xếp mỗi bucket theo độ dài giảm dần (Longest Match First)
    prefix_bucket: Dict[str, List[str]] = {}
    for ch_name in db_examples_map.keys():
        first_char = ch_name[0]
        prefix_bucket.setdefault(first_char, []).append(ch_name)
    for first_char in prefix_bucket:
        prefix_bucket[first_char].sort(key=len, reverse=True)

    found_terms: Dict[str, List[dict]] = {}
    raw_lines = raw_text.split('\n')

    for line_idx, line in enumerate(raw_lines):
        if not line.strip():
            continue

        # Danh sách các khoảng tọa độ ký tự đã được xác thực bởi tên trong DB (Occupied Spans)
        line_occupied_spans: List[Tuple[int, int]] = []

        # a. Quét siêu tốc theo Bucket Indexing O(N) thay vì O(NxM):
        # Duyệt từng vị trí ký tự trong dòng, nếu ký tự đó có trong prefix_bucket thì mới khớp các từ thuộc bucket đó
        line_len = len(line)
        c_idx = 0
        while c_idx < line_len:
            char = line[c_idx]
            cand_list = prefix_bucket.get(char)
            if not cand_list:
                c_idx += 1
                continue

            matched_term = None
            for ch_name in cand_list:
                term_len = len(ch_name)
                if c_idx + term_len <= line_len and line[c_idx:c_idx + term_len] == ch_name:
                    m_start, m_end = c_idx, c_idx + term_len
                    # Tránh chồng chéo
                    if any(not (m_end <= occ_s or m_start >= occ_e) for occ_s, occ_e in line_occupied_spans):
                        continue
                    line_occupied_spans.append((m_start, m_end))
                    if ch_name not in found_terms:
                        found_terms[ch_name] = []
                    found_terms[ch_name].append({
                        "line_index": line_idx,
                        "char_start": m_start,
                        "char_end": m_end
                    })
                    matched_term = ch_name
                    c_idx += term_len  # Nhảy cóc qua độ dài từ vừa khớp
                    break

            if not matched_term:
                c_idx += 1

        def is_overlapping_with_db(cand_start: int, cand_end: int) -> bool:
            """Kiểm tra xem ứng viên heuristic mới có bị chồng lấn vào tên đã có trong DB hay không."""
            return any(not (cand_end <= occ_s or cand_start >= occ_e) for occ_s, occ_e in line_occupied_spans)

        # b. Quét Heuristics theo Họ (Sử dụng _SURNAME_REGEX compiled O(1) siêu tốc)
        for match in _SURNAME_REGEX.finditer(line):
            idx_start = match.start()
            idx_end = match.end()

            # Nếu vùng này đã có tên chuẩn trong DB -> TUYỆT ĐỐI KHÔNG nuốt thêm chữ (Bỏ qua ngay)
            if is_overlapping_with_db(idx_start, idx_end):
                continue

            m = match.group()
            
            # Bỏ qua nếu ký tự ngay trước đó làm nên từ thông dụng (Ví dụ: 紧张, 慌张, 夸张, 身高)
            if idx_start > 0 and line[idx_start - 1] in PREFIX_NON_SURNAME:
                continue

            if is_valid_chinese_term(m):
                # Tự động cắt bỏ các từ nối / động từ ở đuôi (Ví dụ: '王伦和' -> '王伦', '宋万说' -> '宋万')
                clean_m = m
                while len(clean_m) >= 2 and (clean_m[-1] in CHINESE_STOP_CHARS or clean_m[-1] in VERB_TRAILING_CHARS):
                    clean_m = clean_m[:-1]

                # Chỉ cắt bỏ nếu chữ cuối thuộc về từ ghép biểu cảm / ngữ cảnh liền sau (Ví dụ: 杨大彪神色一变 -> '神色', Trương Tam thần thức -> '神识'):
                if len(clean_m) >= 4 and clean_m[-1] in ("神", "仙", "圣", "鬼", "魔", "道", "佛"):
                    idx_m_end = match.start() + len(clean_m)
                    if idx_m_end < len(line) and line[idx_m_end] in ("色", "情", "态", "通", "秘", "识", "魂", "威", "力", "念", "光", "器", "明", "火", "像", "兵", "皇"):
                        clean_m = clean_m[:-1]

                if is_valid_chinese_term(clean_m):
                    candidates = [clean_m]
                    if len(clean_m) == 3 and not any(c in CHINESE_STOP_CHARS for c in clean_m[:2]):
                        candidates.append(clean_m[:2])

                    for cand in candidates:
                        if any(c in CHINESE_STOP_CHARS for c in cand[1:]):
                            continue
                        cand_s = match.start()
                        cand_e = cand_s + len(cand)
                        if is_overlapping_with_db(cand_s, cand_e):
                            continue
                        if cand not in found_terms:
                            found_terms[cand] = []
                        found_terms[cand].append({
                            "line_index": line_idx,
                            "char_start": cand_s,
                            "char_end": cand_e
                        })

                        # Quét ngược O(1) tìm Ngoại hiệu đứng liền trước tên (Ví dụ: 白衣秀士王伦, 摸着天杜迁, 小旋风柴进)
                        prefix_window = line[max(0, idx_start - 5):idx_start]
                        pref_m = re.search(r"[\u4e00-\u9fff]{2,4}$", prefix_window)
                        if pref_m:
                            raw_pref = pref_m.group()
                            clean_pref = raw_pref
                            while clean_pref and clean_pref[0] in LEADING_STRIP_PARTICLES:
                                clean_pref = clean_pref[1:]
                            if len(clean_pref) >= 2 and is_valid_chinese_term(clean_pref):
                                pref_s = idx_start - len(clean_pref)
                                pref_e = idx_start
                                if not is_overlapping_with_db(pref_s, pref_e):
                                    if clean_pref not in found_terms and clean_pref not in db_examples_map:
                                        found_terms[clean_pref] = [{
                                            "line_index": line_idx,
                                            "char_start": pref_s,
                                            "char_end": pref_e
                                        }]
                                clean_pref = clean_pref.strip()

        # c. Quét Heuristics theo Tiền tố thân mật / biệt danh (小, 老, 阿, 大)
        for prefix in TITLE_PREFIXES:
            for match in re.finditer(rf"{prefix}[\u4e00-\u9fff]{{1,3}}", line):
                m = match.group()
                if is_valid_chinese_term(m) and not any(c in CHINESE_STOP_CHARS for c in m[1:]):
                    candidates = [m]
                    if len(m) >= 3 and m[-1] in VERB_TRAILING_CHARS:
                        sub_cand = m[:-1]
                        if is_valid_chinese_term(sub_cand) and not any(c in CHINESE_STOP_CHARS for c in sub_cand[1:]):
                            candidates.append(sub_cand)

                    for cand in candidates:
                        if cand not in found_terms:
                            found_terms[cand] = []
                        found_terms[cand].append({
                            "line_index": line_idx,
                            "char_start": match.start(),
                            "char_end": match.start() + len(cand)
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

        # d2. Quét tên dân dã, nhũ danh, biệt danh thôn quê theo hậu tố (石头, 虎子, 铁柱, 水猴儿, 二蛋, 狗剩...)
        for f_suffix in FOLK_NAME_SUFFIXES:
            for match in re.finditer(rf"[\u4e00-\u9fff]{{1,2}}{re.escape(f_suffix)}", line):
                m = match.group()
                if is_valid_chinese_term(m) and not any(c in CHINESE_STOP_CHARS for c in m):
                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append({
                        "line_index": line_idx,
                        "char_start": match.start(),
                        "char_end": match.end()
                    })

        # d3. Quét Thực thể dân gian, nghề nghiệp cổ truyền, ma mị, tâm linh (捞尸人, 扎纸人, 水猴子, 黄大仙, 出马仙...)
        for folk_ent in FOLK_OCCUPATION_ENTITIES:
            if folk_ent in line:
                for match in re.finditer(re.escape(folk_ent), line):
                    if folk_ent not in found_terms:
                        found_terms[folk_ent] = []
                    found_terms[folk_ent].append({
                        "line_index": line_idx,
                        "char_start": match.start(),
                        "char_end": match.end()
                    })

        # d4. Quét Ngoại hiệu giang hồ, Đạo hiệu, Hảo hán (摸着天, 白衣秀士, 云里金刚, 托塔天王, 豹子头...)
        STRIP_PREFIX_PATTERNS = (
            "一身", "一个", "这位", "那位", "这个", "那个", "作为", "自号", "诨名", "外号", "人称", 
            "正是", "便是", "号", "要", "叫", "看", "见", "听", "打", "拉", "提", "背", "跟", "和", "与", "同", "及",
            "可是", "但是", "如果", "让", "但", "便", "就", "又", "也", "且", "而", "在",
            "给", "过", "杀", "当", "算", "做", "被", "站", "摆", "出", "了", "知", "父", "向", "对", "把", "是", "有", "个", "这", "那", "的"
        )
        for ep_suffix in EPITHET_SUFFIXES:
            for match in re.finditer(rf"[\u4e00-\u9fff]{{2,4}}{re.escape(ep_suffix)}", line):
                m = match.group()
                clean_ep = m

                # Nếu bị dính liên từ / từ nối ở giữa cụm (ví dụ: '伦和摸着天', 'A与B', 'A跟B')
                # Ngoại hiệu chuẩn không bao giờ chứa liên từ ngữ pháp ở giữa, tách lấy phần sau liên từ
                for conj in ("和", "与", "跟", "同", "及", "或", "但", "便", "就", "在", "从", "把", "让", "又", "也", "且", "而"):
                    if conj in clean_ep:
                        clean_ep = clean_ep.split(conj)[-1]

                changed = True
                while changed and clean_ep:
                    changed = False
                    while clean_ep and clean_ep[0] in LEADING_STRIP_PARTICLES:
                        clean_ep = clean_ep[1:]
                        changed = True
                    for bad_p in STRIP_PREFIX_PATTERNS:
                        if clean_ep.startswith(bad_p):
                            clean_ep = clean_ep[len(bad_p):]
                            changed = True

                # Nếu cụm bị dính 1-2 chữ động từ/hư từ đứng trước Họ (ví dụ: '给南宫仙子' -> '南宫仙子', '救林冲' -> '林冲', '见柴进' -> '柴进')
                for sname in sorted(CHINESE_SURNAMES, key=len, reverse=True):
                    if clean_ep.startswith(sname):
                        break
                    s_idx = clean_ep.find(sname)
                    if s_idx in (1, 2) and (len(clean_ep) - s_idx) >= 2:
                        prefix_junk = clean_ep[:s_idx]
                        if any(pj in STRIP_PREFIX_PATTERNS or pj in LEADING_STRIP_PARTICLES for pj in prefix_junk) or len(prefix_junk) == 1:
                            clean_ep = clean_ep[s_idx:]
                            break

                # Nếu bị dính 1 ký tự đuôi của tên người phía trước (ví dụ: '王伦' -> '伦摸着天' -> '摸着天')
                for existing_name in list(found_terms.keys()) + list(db_examples_map.keys()):
                    if len(existing_name) >= 2 and clean_ep.startswith(existing_name[-1]) and len(clean_ep) > len(ep_suffix) + 1:
                        clean_ep = clean_ep[1:]

                if len(clean_ep) in [3, 4, 5] and is_valid_chinese_term(clean_ep) and clean_ep not in db_examples_map:
                    cand_ep_s = match.start() + (len(m) - len(clean_ep))
                    cand_ep_e = match.end()
                    if is_overlapping_with_db(cand_ep_s, cand_ep_e):
                        continue

                    # Bỏ qua nếu là chuỗi con bị cắt xén của một thực thể dài hơn đã có trong DB hoặc found_terms
                    if any(clean_ep in ft for ft in found_terms if len(ft) > len(clean_ep)):
                        continue
                    if any(clean_ep in db_e for db_e in db_examples_map if len(db_e) > len(clean_ep)):
                        continue

                    # TUYỆT ĐỐI KHÔNG xóa các thực thể chuẩn trong SPECIAL_ENTITIES_MAP hoặc đã có trong DB
                    shorter_keys = [ft for ft in found_terms if ft in clean_ep and len(ft) < len(clean_ep) and ft not in SPECIAL_ENTITIES_MAP and ft not in db_examples_map]
                    for sk in shorter_keys:
                        del found_terms[sk]
                    found_terms[clean_ep] = [{
                        "line_index": line_idx,
                        "char_start": cand_ep_s,
                        "char_end": cand_ep_e
                    }]

        # e. Quét thực thể trong dấu ngoặc kép / sách / bảo vật / bí tịch / chiêu thức (《...》, 「...」, 『...』, 【...】, ‘...’, “...”)
        for quote_match in re.finditer(r"[《「『【〖‘“]([\u4e00-\u9fff]{2,10})[》」』】〗’”]", line):
            m = quote_match.group(1).strip()
            if is_valid_chinese_term(m) and m not in found_terms:
                found_terms[m] = [{
                    "line_index": line_idx,
                    "char_start": quote_match.start(1),
                    "char_end": quote_match.end(1)
                }]

        # f. Quét Compound Entities (Địa danh, Tông môn, Vật phẩm, Võ công, Chiêu thức)
        for etype_compound, suffixes_compound in ENTITY_COMPOUND_SUFFIXES.items():
            for suffix_c in suffixes_compound:
                for match in re.finditer(rf"[\u4e00-\u9fff]{{2,7}}{re.escape(suffix_c)}", line):
                    m = match.group()
                    if is_valid_chinese_term(m) and m not in found_terms and m not in db_examples_map:
                        if not any(c in CHINESE_STOP_CHARS for c in m[:2]):
                            found_terms[m] = [{
                                "line_index": line_idx,
                                "char_start": match.start(),
                                "char_end": match.end()
                            }]

        # f2. Quét Địa danh / Thế giới theo tiền tố ngữ cảnh (Ví dụ: 这里是泰拉, 来到泰拉, 身在...)
        for p_pref in CONTEXT_PLACE_PREFIXES:
            for match in re.finditer(rf"{re.escape(p_pref)}([\u4e00-\u9fff]{{2,5}})", line):
                m = match.group(1).strip()
                if is_valid_chinese_term(m) and m not in found_terms and m not in db_examples_map:
                    if not any(c in CHINESE_STOP_CHARS for c in m):
                        found_terms[m] = [{
                            "line_index": line_idx,
                            "char_start": match.start(1),
                            "char_end": match.end(1)
                        }]

        # f3. Quét Tác phẩm / Kinh thư / Điển tịch / Tên định danh (名为, 名叫, 唤作, 出自...)
        BOOK_VERB_PREFIXES = ("读", "念", "翻开", "阅", "著", "写", "名为", "名叫", "号为", "人称", "唤作", "唤做", "自称", "出自", "书名")
        for b_pref in BOOK_VERB_PREFIXES:
            for match in re.finditer(rf"{re.escape(b_pref)}([\u4e00-\u9fff]{{2,6}})", line):
                m = match.group(1).strip()
                if is_valid_chinese_term(m) and m not in db_examples_map:
                    if not any(c in CHINESE_STOP_CHARS for c in m):
                        pos_dict = {
                            "line_index": line_idx,
                            "char_start": match.start(1),
                            "char_end": match.end(1)
                        }
                        if m not in found_terms:
                            found_terms[m] = []
                        found_terms[m].append(pos_dict)

        # f4. Quét Tên Thú Cưng / Linh Vật / Dị Thú đi kèm tên riêng (Ví dụ: 黑鹰名为煤球, 灵兽煤球, 贴身奴婢煤球)
        PET_NAMING_REGEX = re.compile(r"(?:黑鹰|灵兽|神兽|妖兽|异兽|灵禽|神鸟|大鹏|巨蟒|白蛇|灵狐|坐骑|贴身奴婢)(?:名为|名叫|叫|为)?([\u4e00-\u9fff]{2,4})")
        for match in PET_NAMING_REGEX.finditer(line):
            m = match.group(1).strip()
            if is_valid_chinese_term(m) and m not in db_examples_map:
                if not any(c in CHINESE_STOP_CHARS for c in m):
                    pos_dict = {
                        "line_index": line_idx,
                        "char_start": match.start(1),
                        "char_end": match.end(1)
                    }
                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append(pos_dict)

        # f5. Quét Lời gọi tên riêng / danh xưng trong ngoặc thoại (Ví dụ: “煤球？”, “大彪！”)
        CALL_NAME_REGEX = re.compile(r"[“‘]([\u4e00-\u9fff]{2,4})[？?！!~]*[”’]")
        for match in CALL_NAME_REGEX.finditer(line):
            m = match.group(1).strip()
            if is_valid_chinese_term(m) and m not in db_examples_map:
                if not any(c in CHINESE_STOP_CHARS for c in m):
                    pos_dict = {
                        "line_index": line_idx,
                        "char_start": match.start(1),
                        "char_end": match.end(1)
                    }
                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append(pos_dict)

        # f6. Quét Sinh vật lạ / Quái thú / Dị thể theo Lượng từ tiếng Trung (Phổ quát 7 thể loại)
        #     Ví dụ: 一只水猴子, 一头黑煞, 一条巨蟒, 那具僵尸
        CREATURE_QUANTIFIER_PREFIXES = ("一只", "两只", "数只", "一头", "两头", "数头", "一条", "两条", "一具", "那具", "头顶的", "水底的")
        for c_pref in CREATURE_QUANTIFIER_PREFIXES:
            for match in re.finditer(rf"{re.escape(c_pref)}([\u4e00-\u9fff]{{2,5}})", line):
                m = match.group(1).strip()
                if is_valid_chinese_term(m) and m not in db_examples_map:
                    if not any(c in CHINESE_STOP_CHARS for c in m):
                        pos_dict = {
                            "line_index": line_idx,
                            "char_start": match.start(1),
                            "char_end": match.end(1)
                        }
                        if m not in found_terms:
                            found_terms[m] = []
                        found_terms[m].append(pos_dict)

        # f7. Quét Vật phẩm / Pháp bảo / Binh khí / Dược liệu quý theo Lượng từ tiếng Trung
        #     Ví dụ: 一柄飞剑, 一枚筑基丹, 一株赤血参, 一口宝钟, 一面宝镜
        ITEM_QUANTIFIER_REGEX = re.compile(r"(?:[一二三四五六七八九十百数几])?[柄枚株件根副顶架面张尊口]([\u4e00-\u9fff]{2,5})")
        for match in ITEM_QUANTIFIER_REGEX.finditer(line):
            m = match.group(1).strip()
            if is_valid_chinese_term(m) and m not in db_examples_map:
                if not any(c in CHINESE_STOP_CHARS for c in m):
                    pos_dict = {
                        "line_index": line_idx,
                        "char_start": match.start(1),
                        "char_end": match.end(1)
                    }
                    if m not in found_terms:
                        found_terms[m] = []
                    found_terms[m].append(pos_dict)

        # g. Quét cảnh giới tu luyện (Cultivation Realm Detection)
        #    Phát hiện các cụm cảnh giới (炼灵三境, 筑基后期, 炼气九重...) và dịch Hán-Việt tự động
        realm_results = detect_realms(line)
        for realm in realm_results:
            realm_han = realm["han"]
            if realm_han not in found_terms and realm_han not in db_examples_map:
                # Tìm vị trí trong line
                for rm in re.finditer(re.escape(realm_han), line):
                    if realm_han not in found_terms:
                        found_terms[realm_han] = []
                    found_terms[realm_han].append({
                        "line_index": line_idx,
                        "char_start": rm.start(),
                        "char_end": rm.end()
                    })
                # Lưu bản dịch Hán-Việt vào db_examples_map để tự động có db_example
                db_examples_map[realm_han] = (realm["viet"], "REALM")

    # h. Quét mở rộng tên 2 chữ không họ (Given Names) & Tên thân mật từ các tên nhân vật đã tìm thấy
    #    Ví dụ: từ 李追远 -> tự động quét tìm tiếp 追远, 小远, 远子 trong toàn văn bản
    from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name
    potential_given_names: Dict[str, Tuple[str, str]] = {}
    for t in list(found_terms.keys()) + list(db_examples_map.keys()):
        for s in CHINESE_SURNAMES:
            if t.startswith(s) and len(t) - len(s) >= 2:
                given = t[len(s):]
                if is_valid_chinese_term(given) and not any(c in CHINESE_STOP_CHARS for c in given):
                    # Tính bản dịch Hán-Việt tương ứng nếu có
                    t_trans = db_examples_map.get(t, (None, None))[0]
                    if t_trans and len(t_trans.split()) >= 3:
                        given_trans = " ".join(t_trans.split()[1:])
                    else:
                        given_trans = build_hanviet_name(given)
                    potential_given_names[given] = (given_trans, "NAME")
                    
                    last_c = given[-1]
                    last_v = given_trans.split()[-1] if given_trans else build_hanviet_name(last_c)
                    potential_given_names[f"小{last_c}"] = (f"Tiểu {last_v}", "NAME")
                    potential_given_names[f"{last_c}子"] = (f"{last_v} Tử", "NAME")
                break

    for g_name, (g_trans, g_type) in potential_given_names.items():
        for l_idx, l_text in enumerate(raw_lines):
            if g_name in l_text:
                for m_g in re.finditer(re.escape(g_name), l_text):
                    if g_name not in found_terms:
                        found_terms[g_name] = []
                    found_terms[g_name].append({
                        "line_index": l_idx,
                        "char_start": m_g.start(),
                        "char_end": m_g.end()
                    })
        if g_name in found_terms and g_name not in db_examples_map:
            db_examples_map[g_name] = (g_trans, g_type)

    ner_results = []
    for term, positions in found_terms.items():
        # Không chặn nhạy cảm nếu từ này là thực thể tâm linh dân gian hoặc đã có trong DB
        if term not in FOLK_OCCUPATION_ENTITIES and term not in db_examples_map:
            if await is_exact_sensitive_word(term):
                continue


        db_info = db_examples_map.get(term)
        db_example = db_info[0] if db_info else None
        
        raw_type = db_info[1] if db_info else "NAME"
        
        # Chuyển đổi mã cũ -> mã mới
        type_mapping = {
            "PERSON": "NAME",
            "LOCATION": "PLACE",
            "SECT_SKILL": "SKILL",
            "ORGANIZATION": "SECT",
            "REALM": "REALM"
        }
        ent_type = type_mapping.get(raw_type, raw_type)
        
        from app.services.preprocessing.dichhan.hanviet_data import SPECIAL_ENTITIES_MAP
        if not db_info:
            if term in SPECIAL_ENTITIES_MAP:
                db_example = SPECIAL_ENTITIES_MAP[term]
                if term in ["金瓶梅", "水浒传", "西游记", "红楼梦", "三国演义", "道德经"]:
                    ent_type = "ITEM"
                else:
                    ent_type = "NAME"
            elif term in FOLK_OCCUPATION_ENTITIES:
                ent_type = "NAME"
            elif any(term.endswith(s) for s in FOLK_NAME_SUFFIXES) or any(s in term for s in TITLE_SUFFIXES) or any(s in term for s in ["哥", "姐", "弟", "妹", "伯", "叔", "爷", "奶"]):
                ent_type = "NAME"
            elif any(term.startswith(p) for p in TITLE_PREFIXES) and len(term) in [2, 3]:
                ent_type = "NAME"
            elif any(term.startswith(s) for s in CHINESE_SURNAMES) and len(term) in [2, 3] and not any(term.endswith(pl) for pl in ["市", "省", "县", "村", "镇", "山", "关", "岛"]):
                ent_type = "NAME"
            elif any(s in term for s in ["掌", "拳", "指", "功", "诀", "经", "术", "阵", "圈", "法", "印", "吟", "步", "体", "腿", "爪", "斩", "剑法", "刀法", "指法", "枪法", "棍法", "身法", "心法", "神功", "大法", "真经", "宝典", "秘籍", "图录", "剑谱", "绝技", "神通", "剑气", "剑意"]):
                ent_type = "SKILL"
            elif any(s in term for s in ["集团", "公司", "宗", "门", "派", "帮", "教", "盟", "会", "庄", "院", "世家", "镖局", "神教"]):
                ent_type = "SECT"
            elif any(s in term for s in ["市", "城", "山", "谷", "峰", "海", "域", "界", "洲", "省", "县", "关", "岛", "村", "河", "江", "潭", "原", "窟", "寨", "堡", "山庄", "崖", "坡", "冈", "洼", "泊", "大厦", "广场", "公园", "小区", "大桥", "路", "街"]):
                ent_type = "PLACE"
            elif any(s in term for s in ["猴", "猿", "蟒", "蛇", "狼", "虎", "豹", "熊", "雕", "鹰", "鸟", "龙", "凤", "麟", "龟", "尸", "鬼", "兽", "妖", "怪", "魔", "丧尸"]):
                ent_type = "CREATURE"
            elif any(s in term for s in ["书", "传", "录", "志", "谱", "篇", "卷", "赋", "集"]):
                ent_type = "ITEM"
            elif any(s in term for s in ["制药", "重工", "电子", "剑", "珠", "镜", "丹", "符", "鼎", "瓶", "铠", "轮", "刀", "枪", "戟", "弓", "扇", "琴", "甲", "宝", "令", "图", "环", "膏", "丸", "散", "棒", "杖", "鞭", "索", "尺", "幡", "佩", "玉", "机甲"]):
                ent_type = "ITEM"
            else:
                ent_type = "OTHER"

        unique_positions = []
        seen = set()
        for p in positions:
            key = (p["line_index"], p["char_start"], p["char_end"])
            if key not in seen:
                seen.add(key)
                unique_positions.append(p)

        # Thuật toán chọn vị trí có ngữ cảnh định danh tốt nhất (Best Context Selection)
        best_p = unique_positions[0]
        best_score = -1.0
        for p in unique_positions:
            l_idx = p["line_index"]
            c_line = raw_lines[l_idx] if 0 <= l_idx < len(raw_lines) else ""
            score = 0.0
            for kw in DEFINING_KEYWORDS:
                if kw in c_line:
                    score += 15.0
            if any(p_k in c_line for p_k in ("名为", "名叫", "号为", "唤作", "黑鹰", "灵兽", "神兽", "妖兽", "异兽", "神鸟", "坐骑", "贴身奴婢", "宝剑", "佩剑", "铁锏")):
                score += 25.0
            score += min(len(c_line), 80) / 10.0
            if score > best_score:
                best_score = score
                best_p = p

        context_han = get_context_han(raw_lines, best_p["line_index"], best_p["char_start"], best_p["char_end"])

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

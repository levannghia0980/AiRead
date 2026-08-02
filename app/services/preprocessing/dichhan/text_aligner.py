import os
import re
from typing import Optional, List, Tuple, Union
from app.services.preprocessing.dichhan.hanviet_data import HanVietContext

def remove_diacritics(s: str) -> str:
    """Loại bỏ dấu tiếng Việt để so khớp tương đồng Latin/Pinyin chuẩn xác hơn."""
    s = s.lower()
    replacements = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        'đ': 'd'
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s

def token_similarity(s1: str, s2: str) -> float:
    """Tính độ tương đồng ký tự Jaccard giữa hai chuỗi đã bỏ dấu."""
    s1_clean = remove_diacritics(s1)
    s2_clean = remove_diacritics(s2)
    set1, set2 = set(s1_clean), set(s2_clean)
    if not set1 or not set2:
        return 0.0
    return len(set1.intersection(set2)) / len(set1.union(set2))

async def align_candidate_to_chinese(
    candidate_text: str,
    gg_line_text: str,
    raw_line_text: str,
    gg_char_start: int,
    gg_char_end: int,
    db_entities: list = None,
    context: Optional[HanVietContext] = None
) -> Tuple[Optional[str], float]:
    """
    Tìm cụm chữ Hán phù hợp nhất trong dòng RAW tương ứng với candidate trong dòng GG.
    Sử dụng so khớp dựa trên thực thể DB truyện (NER) và vị trí tương đối, không gọi get_hanviet.
    """
    if not raw_line_text or not candidate_text:
        return None, -999.0

    # 1. Tìm các ứng viên chữ Hán trong dòng RAW
    chinese_blocks = re.findall(r'[\u4e00-\u9fff]+', raw_line_text)
    if not chinese_blocks:
        return None, -999.0

    # Sinh tất cả n-gram chữ Hán độ dài 1-4
    candidates_chinese = []
    for block in chinese_blocks:
        n = len(block)
        for length in range(1, min(5, n + 1)):
            for i in range(n - length + 1):
                candidates_chinese.append(block[i:i+length])

    if not candidates_chinese:
        return None, -999.0

    # Tính vị trí tương đối của candidate trong dòng GG
    gg_len = len(gg_line_text)
    gg_rel_pos = 0.5
    if gg_len > 0:
        gg_rel_pos = (gg_char_start + gg_char_end) / 2.0 / gg_len

    best_chinese = None
    best_score = -999.0

    for ch_sub in set(candidates_chinese):
        # 1. So khớp Proper Noun (Tên riêng) sử dụng thông tin dịch có sẵn của NER nhánh trước để lấy name_sim
        is_name = False
        is_exact_name = False
        matched_ent_len = 0
        name_sim = 0.0
        
        if db_entities:
            for ent in db_entities:
                ent_ch = getattr(ent, "chinese_name", ent.get("chinese_name") if isinstance(ent, dict) else "")
                ent_vi = getattr(ent, "rough_translation", ent.get("rough_translation") if isinstance(ent, dict) else "")
                if ent_ch and ent_vi:
                    if ch_sub == ent_ch:
                        is_exact_name = True
                        is_name = True
                        matched_ent_len = len(ent_ch)
                        name_sim = max(name_sim, token_similarity(candidate_text, ent_vi))
                        break
                    elif len(ent_ch) >= 2 and ent_ch in ch_sub:
                        is_name = True
                        matched_ent_len = max(matched_ent_len, len(ent_ch))
                        name_sim = max(name_sim, token_similarity(candidate_text, ent_vi))
        
        # Nếu chưa khớp thực thể DB, kiểm tra trong names_dictionary
        if not is_name:
            conn = context.get_conn() if context else None
            local_conn = None
            if not conn:
                import sqlite3
                if os.path.exists("database.db"):
                    local_conn = sqlite3.connect("database.db")
                    conn = local_conn
            try:
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM names_dictionary WHERE chinese_name = ? LIMIT 1", (ch_sub,))
                    if cursor.fetchone():
                        is_exact_name = True
                        is_name = True
                        matched_ent_len = len(ch_sub)
                        name_sim = 0.1  # Giá trị tương đồng mặc định nhỏ cho từ điển chung
            except Exception:
                pass
            finally:
                if local_conn:
                    local_conn.close()

        # 2. Tính khoảng cách vị trí tương đối và hình phạt
        raw_len = len(raw_line_text)
        first_index = raw_line_text.find(ch_sub)
        raw_rel_pos = 0.5
        if raw_len > 0 and first_index != -1:
            raw_rel_pos = (first_index + len(ch_sub) / 2.0) / raw_len

        pos_diff = abs(gg_rel_pos - raw_rel_pos)
        
        # Nếu độ tương đồng tên riêng tốt (Latin trùng lặp nhiều), giảm thiểu hình phạt vị trí
        # để chống lỗi đảo lộn trật tự từ do cấu trúc ngữ pháp dịch thuật
        if name_sim >= 0.18:
            pos_penalty = pos_diff * 5.0
        else:
            pos_penalty = pos_diff * 40.0
        
        # Điểm cơ bản dựa trên độ dài của cụm từ và hình phạt vị trí
        score = len(ch_sub) * 5.0 - pos_penalty

        # Cộng điểm ưu tiên rất lớn nếu khớp tên riêng (Proper Noun) và candidate bắt đầu bằng chữ hoa
        if is_name:
            if candidate_text and candidate_text[0].isupper():
                if is_exact_name:
                    # Ưu tiên cao nhất cho khớp chính xác tên riêng và nhân với độ tương đồng của tên
                    score += 150.0 * (1.0 + name_sim)
                else:
                    # Phạt các cụm chứa tên riêng nhưng bị dư ký tự rác xung quanh
                    extra_chars = len(ch_sub) - matched_ent_len
                    score += (120.0 * (1.0 + name_sim) - extra_chars * 15.0)
            else:
                score += 50.0

        if score > best_score:
            best_score = score
            best_chinese = ch_sub

    if best_score < 0.0:
        return None, -999.0

    return best_chinese, best_score

async def align_gg_to_raw(
    raw_input: Union[str, List[str]],
    gg_input: Union[str, List[str]],
    candidate_text: str,
    target_gg_line_idx: int,
    char_start_in_line: int,
    db_entities: list = None,
    context: Optional[HanVietContext] = None
) -> Optional[str]:
    """
    Nhận diện dòng chứa candidate trong gg_text, map sang dòng trong raw_text
    và tìm cụm chữ Hán tương ứng sử dụng hệ thống tính điểm tối ưu.
    """
    if not raw_input or not gg_input or not candidate_text:
        return None

    raw_lines = raw_input if isinstance(raw_input, list) else raw_input.split('\n')
    gg_lines = gg_input if isinstance(gg_input, list) else gg_input.split('\n')

    if target_gg_line_idx == -1 or target_gg_line_idx >= len(gg_lines):
        return None

    gg_line_text = gg_lines[target_gg_line_idx]
    char_end_in_line = char_start_in_line + len(candidate_text)

    raw_total = len(raw_lines)
    gg_total = len(gg_lines)
    if gg_total == 0 or raw_total == 0:
        return None

    target_raw_line_idx = int(target_gg_line_idx * raw_total / gg_total)
    target_raw_line_idx = max(0, min(target_raw_line_idx, raw_total - 1))

    best_align = None
    best_score = -999.0
    
    start_search = max(0, target_raw_line_idx - 2)
    end_search = min(raw_total, target_raw_line_idx + 3)

    for r_idx in range(start_search, end_search):
        raw_line_text = raw_lines[r_idx]
        aligned, score = await align_candidate_to_chinese(
            candidate_text,
            gg_line_text,
            raw_line_text,
            char_start_in_line,
            char_end_in_line,
            db_entities,
            context
        )
        if aligned and score > best_score:
            best_score = score
            best_align = aligned

    return best_align

import re
from typing import List, Set, Dict, Any, Optional
from app.services.preprocessing.dichhan.common_lists import (
    PINYIN_SYLLABLES,
    HONORIFICS,
    VIETNAMESE_STOPWORDS
)

def can_split_pinyin(s: str) -> bool:
    """Kiểm tra xem chuỗi có thể tách hoàn toàn thành các âm tiết pinyin hợp lệ hay không (DP)"""
    s = s.lower().replace("'", "").replace("-", "")
    n = len(s)
    if n == 0:
        return False
    dp = [False] * (n + 1)
    dp[0] = True
    for i in range(1, n + 1):
        for j in range(i):
            if dp[j] and s[j:i] in PINYIN_SYLLABLES:
                dp[i] = True
                break
    return dp[n]

def edit_distance(s1: str, s2: str) -> int:
    """Tính khoảng cách Levenshtein giữa hai chuỗi"""
    if len(s1) < len(s2):
        return edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def token_similarity(s1: str, s2: str) -> float:
    """Tính độ tương đồng tập ký tự giữa hai chuỗi (Jaccard)"""
    set1, set2 = set(s1.lower()), set(s2.lower())
    if not set1 or not set2:
        return 0.0
    return len(set1.intersection(set2)) / len(set1.union(set2))

async def extract_gg_clean_branch(
    raw_text: str,
    gg_text: str,
    db_entities: List[Any]
) -> List[Dict[str, Any]]:
    """
    NHÁNH 2: Bộ lọc làm sạch lỗi Google Translate (GG Error Mining Branch)
    - Dùng các bộ lọc tìm từ nghi vấn/lỗi dịch trong Google Translate text.
    - Lưu địa chỉ vị trí xuất hiện trong GG text.
    - Truy vấn (align) ngược về từ Hán gốc trong bản RAW và đính kèm 1 ký tự ngữ cảnh (context_han).
    - Tiền xử lý gom nhóm các từ lỗi trùng lặp để giảm thiểu Token.
    """
    if not gg_text or not raw_text:
        return []

    from app.services.preprocessing.dichhan.candidate_mining import mine_candidates

    mined_candidates = await mine_candidates(raw_text, gg_text, db_entities)

    grouped_errors: Dict[str, Dict[str, Any]] = {}

    for cand in mined_candidates:
        orig_han = cand.get("aligned_chinese")
        gg_err = cand.get("text")
        context_han = cand.get("context_han", orig_han)
        context_gg = cand.get("context_gg", "")
        occurrences = cand.get("occurrences", [])

        if not orig_han or not gg_err:
            continue

        group_key = (orig_han, gg_err.lower())
        if group_key not in grouped_errors:
            grouped_errors[group_key] = {
                "original_han": orig_han,
                "context_han": context_han,
                "context_gg": context_gg,
                "gg_error": gg_err,
                "positions_in_gg": []
            }

        existing_pos = grouped_errors[group_key]["positions_in_gg"]
        for occ in occurrences:
            pos_dict = {
                "line_index": occ.get("gg_line_index"),
                "char_start": occ.get("gg_char_start"),
                "char_end": occ.get("gg_char_end")
            }
            if pos_dict not in existing_pos:
                existing_pos.append(pos_dict)

    return list(grouped_errors.values())

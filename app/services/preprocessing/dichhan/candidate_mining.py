import re
import gc
from typing import List, Dict, Set, Any, Optional, Tuple
from app.services.preprocessing.dichhan.hanviet_data import HanVietContext
from app.services.preprocessing.dichhan.text_aligner import align_gg_to_raw, token_similarity
from app.services.preprocessing.dichhan.common_lists import (
    PINYIN_SYLLABLES,
    HONORIFICS,
    VIETNAMESE_STOPWORDS
)
from app.services.unblock.unblock_pipeline import is_exact_sensitive_word

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

def is_likely_foreign_or_pinyin(s: str) -> bool:
    """
    Kiểm tra xem chuỗi có phải là Pinyin, tên tiếng Anh (VD: Serena, David, Peter, Mo Yayi, Wang Wei), 
    hoặc từ phiên âm ngoại lai của Google Translate hay không.
    """
    s_clean = s.lower().replace("'", "").replace("-", "").strip()
    if not s_clean or len(s_clean) <= 1:
        return False
    # Nếu chứa dấu thanh / ký tự đặc thù Tiếng Việt -> 100% KHÔNG phải Pinyin hay Tên Tiếng Anh ngoại lai
    if re.search(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', s_clean):
        return False
    # Các ký tự tiếng Anh/Pinyin đặc trưng không có trong bảng chữ cái tiếng Việt cơ bản
    if any(char in s_clean for char in ['w', 'j', 'z', 'f']):
        return True
    # Các đuôi phụ âm không bao giờ kết thúc từ đơn tiếng Việt (tiếng Việt chỉ kết thúc bằng c, ch, m, n, ng, nh, p, t hoặc nguyên âm)
    if re.search(r'[bdgklrsvxzfjw]$', s_clean):
        return True
    # Các cụm phụ âm / nguyên âm đặc trưng của tiếng Anh và ngoại ngữ
    if re.search(r'(sh|wh|ck|gh|st|nd|ld|rd|mp|nt|lt|rt|ct|ft|pt|xt|oo|ee|ea|ou|cl|cr|fl|fr|gl|gr|pl|pr|sl|sm|sn|sp|sq|str|sw|tw)', s_clean):
        return True
    # Từ ghép nhiều từ không dấu thanh (VD: "Mo Yayi", "Wang Wei", "Xiao Fan")
    words = s.split()
    if len(words) >= 2:
        return True
    # Đối với từ đơn: Phải từ 4 ký tự trở lên và tách được thành nhiều âm tiết pinyin (VD: 'yayi', 'xiaowei')
    if len(s_clean) >= 4 and can_split_pinyin(s_clean):
        return True
    return False

def clean_candidate_text(text: str) -> str:
    """
    Loại bỏ các từ nối / từ dừng tiếng Việt đứng đầu cụm từ viết hoa (VD: 'Nhưng Mo Yayi' -> 'Mo Yayi').
    """
    words = text.split()
    while len(words) > 1 and words[0].lower() in VIETNAMESE_STOPWORDS:
        words.pop(0)
    return " ".join(words).strip()

def get_context_han_for_aligned(raw_lines: List[str], aligned_chinese: str) -> str:
    """Tìm 1 ký tự ngữ cảnh xung quanh từ Hán trong bản gốc RAW"""
    if not aligned_chinese or not raw_lines:
        return aligned_chinese
    for line in raw_lines:
        if aligned_chinese in line:
            idx = line.find(aligned_chinese)
            start = max(0, idx - 1)
            end = min(len(line), idx + len(aligned_chinese) + 1)
            return line[start:end]
    return aligned_chinese

async def mine_candidates(
    raw_text: str,
    gg_text: str,
    db_entities: List[Any],
    context: Optional[HanVietContext] = None
) -> List[Dict[str, Any]]:
    """
    Entity Candidate Mining Engine (Khai phá Thực thể Nghi vấn):
    Chạy các bộ dò song song trên bản dịch Google để thu thập các từ nghi vấn danh từ riêng / pinyin.
    Loại bỏ các từ tiếng Việt thông thường ở đầu câu, lọc từ nhạy cảm qua Unblock API.
    """
    if not gg_text or not raw_text:
        return []

    raw_lines = raw_text.split('\n')

    db_translations = []
    db_chinese = set()
    db_aliases = set()

    for ent in db_entities:
        ch_name = getattr(ent, "chinese_name", ent.get("chinese_name") if isinstance(ent, dict) else None)
        vi_name = getattr(ent, "rough_translation", ent.get("rough_translation") if isinstance(ent, dict) else None)
        if ch_name:
            db_chinese.add(ch_name)
        if vi_name:
            db_translations.append(vi_name)
            tokens = vi_name.split()
            if len(tokens) >= 2:
                db_aliases.add(" ".join(tokens[1:]))
                db_aliases.add(tokens[-1])

    cap_pattern = re.compile(r"\b[A-ZÀ-Ỹ][a-zà-ỹ\-\x27]*(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ\-\x27]*){0,3}\b")
    honorifics_esc = "|".join(re.escape(h) for h in HONORIFICS)
    hon_pattern_prefix = re.compile(rf"\b(?:{honorifics_esc})\s+[A-ZÀ-Ỹ][a-zà-ỹ\-\x27]*\b", re.IGNORECASE)
    hon_pattern_suffix = re.compile(rf"\b[A-ZÀ-Ỹ][a-zà-ỹ\-\x27]*\s+(?:{honorifics_esc})\b", re.IGNORECASE)
    spec_pattern = re.compile(r"\b[a-zA-Z]+(?:[-'][a-zA-Z]+)+\b")
    pinyin_cand_pattern = re.compile(r"\b[a-zA-Z]{3,15}\b")

    word_freq: Dict[str, int] = {}
    for match in re.finditer(r"\b[a-zA-ZÀ-ỹ\-\x27]+\b", gg_text):
        w_lower = match.group().lower()
        word_freq[w_lower] = word_freq.get(w_lower, 0) + 1

    gg_lines = gg_text.split('\n')
    raw_candidates: Dict[str, List[Tuple[int, int, int]]] = {}

    for line_idx, line in enumerate(gg_lines):
        found_matches = []
        for pat in [cap_pattern, hon_pattern_prefix, hon_pattern_suffix, spec_pattern]:
            for match in pat.finditer(line):
                found_matches.append((match.group().strip(), match.start(), match.end()))
        
        for match in pinyin_cand_pattern.finditer(line):
            w = match.group().strip()
            if is_likely_foreign_or_pinyin(w):
                found_matches.append((w, match.start(), match.end()))

        for text, start, end in found_matches:
            if len(text) <= 1:
                continue
            
            cleaned_text = clean_candidate_text(text)
            cleaned_lower = cleaned_text.lower()

            if not cleaned_text or cleaned_lower in VIETNAMESE_STOPWORDS or len(cleaned_text) <= 1:
                continue

            # Giữ lại các candidate nghi vấn: Pinyin, tên tiếng Anh/ngoại lai, danh hiệu, hoặc khớp DB
            is_foreign_pinyin = is_likely_foreign_or_pinyin(cleaned_lower)
            is_honorific = any(h in cleaned_lower for h in HONORIFICS)
            in_db = cleaned_text in db_translations or cleaned_text in db_aliases

            # Bỏ qua các từ tiếng Việt thông dụng viết hoa đầu câu (VD: "Đồng ý", "Ngươi định", "Hiện", "Chào"...)
            if not (is_foreign_pinyin or is_honorific or in_db):
                continue

            if await is_exact_sensitive_word(cleaned_text):
                continue
                
            if cleaned_text not in raw_candidates:
                raw_candidates[cleaned_text] = []
            raw_candidates[cleaned_text].append((line_idx, start, end))

    scored_candidates = []

    for cand_text, occurrences in raw_candidates.items():
        cand_lower = cand_text.lower()
        score = 0
        signals = {}

        if re.match(r'^[A-ZÀ-Ỹ]', cand_text):
            score += 40
            signals["capital_pattern"] = 40

        if is_likely_foreign_or_pinyin(cand_lower):
            score += 70
            signals["foreign_or_pinyin"] = 70

        if any(h in cand_lower for h in HONORIFICS):
            score += 50
            signals["honorific"] = 50

        if cand_text in db_aliases:
            score += 60
            signals["alias_db"] = 60

        freq = word_freq.get(cand_lower, 0)
        if freq > 3:
            score += 20
            signals["frequency"] = 20

        if cand_text in db_translations:
            score += 80
            signals["exact_db"] = 80

        best_sim = 0.0
        for db_t in db_translations:
            sim = token_similarity(cand_text, db_t)
            if sim > best_sim:
                best_sim = sim
        if best_sim > 0.5:
            score += 40
            signals["similarity"] = 40

        if "-" in cand_text or "'" in cand_text:
            score += 10
            signals["special_char"] = 10

        if score >= 30:
            first_occ = occurrences[0]
            aligned_chinese = await align_gg_to_raw(
                raw_lines, gg_lines, cand_text, first_occ[0], first_occ[1], db_entities, context
            )
            
            if aligned_chinese:
                if await is_exact_sensitive_word(aligned_chinese):
                    continue

                score += 100
                signals["aligned_chinese"] = 100
                if aligned_chinese in db_chinese:
                    score += 30
                    signals["context_db_entity"] = 30
            else:
                aligned_chinese = None

            if aligned_chinese:
                context_han = get_context_han_for_aligned(raw_lines, aligned_chinese)
                occ_list = [{"gg_line_index": o[0], "gg_char_start": o[1], "gg_char_end": o[2]} for o in occurrences]
                
                # Trích xuất ngữ cảnh GG (câu trước/sau hoặc câu hiện tại)
                gg_contexts = []
                for o in occ_list[:3]:
                    idx = o["gg_line_index"]
                    if 0 <= idx < len(gg_lines):
                        gg_contexts.append(gg_lines[idx])
                context_gg = " | ".join(gg_contexts)
                
                scored_candidates.append({
                    "text": cand_text,
                    "aligned_chinese": aligned_chinese,
                    "context_han": context_han,
                    "context_gg": context_gg,
                    "score": score,
                    "occurrences": occ_list,
                    "signals": signals
                })

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    final_candidates = []
    seen_pair: Set[Tuple[str, str]] = set()

    for cand in scored_candidates:
        orig_ch = cand["aligned_chinese"]
        err_text = cand["text"].lower()
        pair_key = (orig_ch, err_text)
        if pair_key not in seen_pair:
            seen_pair.add(pair_key)
            final_candidates.append(cand)

    del raw_candidates
    gc.collect()

    return final_candidates

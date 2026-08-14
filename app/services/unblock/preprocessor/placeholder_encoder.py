import re
import secrets
import logging
from typing import Dict, List, Tuple
from app.services.unblock.preprocessor.trie_matcher import LongestMatchTrie

logger = logging.getLogger(__name__)

class PlaceholderEncoder:
    def __init__(self, trie: LongestMatchTrie):
        self.trie = trie

    def generate_token(self, type_hint: str = "") -> str:
        """
        Sinh token ngẫu nhiên có chứa tiền tố gợi ý loại từ (Type Prefix) cho LLM:
        - BDY_xxxx: Bộ phận cơ thể
        - ACT_xxxx: Động từ / Hành vi
        - ST_xxxx: Trạng thái / Tính chất
        - SCN_xxxx: Cảnh / Đoạn nhạy cảm
        - PF_xxxx: Chửi bới / Bạo lực
        - STRICT_xxxx: Từ ngữ bị cấm nghiêm ngặt
        - ZH_xxxx: Thuật ngữ Hán tự nhạy cảm
        """
        prefix = "OBF"
        if type_hint:
            th_lower = type_hint.lower()
            if "strict" in th_lower:
                prefix = "STRICT"
            elif "body" in th_lower:
                prefix = "BDY"
            elif "action" in th_lower:
                prefix = "ACT"
            elif "state" in th_lower:
                prefix = "ST"
            elif "scene" in th_lower:
                prefix = "SCN"
            elif "profanity" in th_lower:
                prefix = "PF"
            elif "zh" in th_lower:
                prefix = "ZH"
        
        import string
        rand_suffix = secrets.choice(string.ascii_uppercase) + secrets.token_hex(2).upper()[:3]
        return f"§{prefix}_{rand_suffix}§"

    def _merge_overlapping_matches(self, text: str, matches: List[Tuple[int, int, str, str]]) -> List[Tuple[int, int, str, str]]:
        """
        Xử lý chồng chéo vị trí giữa các từ nhạy cảm trong CSDL (Tuyệt đối KHÔNG gộp các từ ngoài từ điển ở giữa).
        """
        if not matches:
            return []

        merged = []
        curr_start, curr_end, curr_word, curr_type = matches[0]

        for next_start, next_end, next_word, next_type in matches[1:]:
            if next_start < curr_end:
                # Đã trùng lặp hoặc chồng chéo vị trí -> lấy phạm vi bao phủ dài nhất
                curr_end = max(curr_end, next_end)
                curr_word = text[curr_start:curr_end].lower()
                continue

            merged.append((curr_start, curr_end, curr_word, curr_type))
            curr_start, curr_end, curr_word, curr_type = next_start, next_end, next_word, next_type

        merged.append((curr_start, curr_end, curr_word, curr_type))
        return merged

    def encode(self, text: str, mask_level: str = "word") -> Tuple[str, Dict[str, Dict[str, str]]]:
        """
        Rà soát và giấu triệt để các từ/cụm từ khớp từ điển nhạy cảm.
        Tự động gộp các từ đứng cạnh nhau thành 1 cụm nhạy cảm duy nhất.
        Giữ nguyên 100% cấu trúc câu từ, chủ ngữ, vị ngữ, đại từ sở hữu xung quanh.
        """
        if not text:
            return "", {}

        raw_matches = self.trie.find_all_matches(text)
        if not raw_matches:
            return text, {}

        # Xử lý chồng chéo vị trí nếu có
        matches = self._merge_overlapping_matches(text, raw_matches)

        # 1. Phân loại các match: Vùng trong thẻ neo gợi ý VS Vùng văn bản chính
        # - Vùng văn bản chính: Gán mã §PREFIX_XXXX§ thật, đưa vào mapping_table để theo dõi tỷ lệ bảo vệ (80%) và giải mã sau khi dịch.
        # - Vùng trong thẻ neo gợi ý: Gán mã tự do giả lập (DUMMY MASK) như ⟪TAG_MASK_xxxx⟫ để Gemini KHÔNG BỊ CHẶN (Safety Pass),
        #   nhưng TUYỆT ĐỐI KHÔNG đưa vào mapping_table (không tính vào tổng số lượng thẻ, không cần giải mã vì thẻ neo sẽ bị xóa).
        protected_tag_spans = []
        for tag_match in re.finditer(r'‹[^›\n]+›|⟦[^⟧\n]+⟧|<([A-Za-z0-9_]+)>.*?</\1>', text, re.DOTALL):
            protected_tag_spans.append((tag_match.start(), tag_match.end()))

        main_matches = []
        inside_matches = []
        for m in matches:
            m_start, m_end = m[0], m[1]
            inside_tag = False
            for p_start, p_end in protected_tag_spans:
                if p_start <= m_start and m_end <= p_end:
                    inside_tag = True
                    break
            if inside_tag:
                inside_matches.append(m)
            else:
                main_matches.append(m)

        # 2. Xử lý mã hóa DUMMY cho các từ nhạy cảm nằm trong ruột thẻ neo (KHÔNG TÍNH VÀO MAPPING_TABLE)
        text_with_dummy = text
        if inside_matches:
            # Sắp xếp ngược từ cuối lên đầu để không làm lệch index
            for start, end, matched_term_lower, word_type in sorted(inside_matches, key=lambda x: x[0], reverse=True):
                dummy_token = f"⟪TAG_MASK_{secrets.token_hex(2).upper()}⟫"
                text_with_dummy = text_with_dummy[:start] + dummy_token + text_with_dummy[end:]

            # Cập nhật lại danh sách span của thẻ neo sau khi đã chèn dummy
            new_protected_tag_spans = []
            for tag_match in re.finditer(r'‹[^›\n]+›|⟦[^⟧\n]+⟧|<([A-Za-z0-9_]+)>.*?</\1>', text_with_dummy, re.DOTALL):
                new_protected_tag_spans.append((tag_match.start(), tag_match.end()))

            # Tìm lại matches và LOẠI BỎ TRIỆT ĐỂ mọi match nằm trong ruột thẻ neo
            raw_matches = self.trie.find_all_matches(text_with_dummy)
            merged = self._merge_overlapping_matches(text_with_dummy, raw_matches)
            
            final_matches = []
            for m in merged:
                m_start, m_end = m[0], m[1]
                inside = False
                for p_start, p_end in new_protected_tag_spans:
                    if p_start <= m_start and m_end <= p_end:
                        inside = True
                        break
                if not inside:
                    final_matches.append(m)
            matches = final_matches
        else:
            matches = main_matches

        mapping_table: Dict[str, Dict[str, str]] = {}
        reverse_term_token_map: Dict[str, str] = {}
        encoded_chunks = []
        last_idx = 0

        for start, end, matched_term_lower, word_type in matches:
            encoded_chunks.append(text_with_dummy[last_idx:start])
            actual_original_text = text_with_dummy[start:end]

            if matched_term_lower in reverse_term_token_map:
                token = reverse_term_token_map[matched_term_lower]
            else:
                token = self.generate_token(word_type)
                while token in mapping_table:
                    token = self.generate_token(word_type)
                reverse_term_token_map[matched_term_lower] = token

            mapping_table[token] = {
                "text": actual_original_text,
                "type": word_type
            }
            encoded_chunks.append(f" {token} ")
            last_idx = end

        encoded_chunks.append(text_with_dummy[last_idx:])
        encoded_text = "".join(encoded_chunks)
        logger.info(f"🛡️ [Encoder] Đã giấu {len(matches)} cụm từ nhạy cảm chính thành {len(mapping_table)} token (Bỏ qua {len(inside_matches)} từ trong thẻ neo).")
        return encoded_text, mapping_table


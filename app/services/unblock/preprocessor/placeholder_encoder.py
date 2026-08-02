import re
import secrets
import logging
from typing import Dict, List, Tuple
from app.services.unblock.preprocessor.trie_matcher import LongestMatchTrie

logger = logging.getLogger(__name__)

CONNECTORS = {
    "vào", "ra", "lên", "xuống", "của", "trong", "trên", "dưới", "ở", "từ",
    "với", "cho", "đã", "đang", "sắp", "lại", "chỗ", "vùng", "vị trí", "mặt",
    "khe", "cặp", "đôi", "chiếc", "cái", "bộ", "nắn", "mó", "mút", "bóp",
    "vuốt", "bằng", "qua", "sang", "tới", "lấy", "về", "bề", "lọt", "đoạn", "bớt",
    "sẵn", "lòng", "trở", "thành", "một", "mình", "có", "thích", "không", "sau",
    "khi", "đứa", "bé", "bụng", "nên", "gọi", "con", "là", "anh", "hay", "bố",
    "mẹ", "cha", "bạn", "khiến", "người", "bị", "được", "làm", "thể", "nằm",
    "ôm", "áp", "sát", "đè", "tựa", "kéo", "đẩy", "rút", "nhét", "kẹp", "vòng",
    "quấn", "toàn", "thân", "thể", "da", "thịt", "môi", "lưỡi", "hơi", "thở",
    "nóng", "bừng", "ấm", "áp", "sâu", "nhẹ", "khẽ", "mạnh", "chậm", "nhanh",
    "liên", "tục", "nơi", "cả", "cùng", "rất", "như", "đều", "đáng", "yêu",
    "xinh", "đẹp", "trắng", "nõn", "mềm", "mại", "nâng", "hạ", "run", "rẩy"
}

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
        
        return f"§{prefix}_{secrets.token_hex(2).upper()}§"

    def _merge_proximity_matches(self, text: str, matches: List[Tuple[int, int, str, str]], aggressive: bool = True) -> List[Tuple[int, int, str, str]]:
        """
        Gộp các từ nhẹ hoặc từ nhạy cảm đứng gần nhau thành 1 cụm token duy nhất.
        - Khi aggressive=True (Dịch thô): nới rộng phạm vi gộp (gap <= 90 chars) và gộp toàn bộ vế câu nhạy cảm
          chứa từ 2 từ nhạy cảm / gợi cảm trở lên, đảm bảo 100% không để lộ câu văn gợi dục lên LLM.
        """
        if not matches:
            return []

        merged = []
        curr_start, curr_end, curr_word, curr_type = matches[0]
        max_allowed_gap = 90 if aggressive else 35

        for next_start, next_end, next_word, next_type in matches[1:]:
            if next_start < curr_end:
                # Đã trùng lặp hoặc chồng chéo
                curr_end = max(curr_end, next_end)
                curr_word = text[curr_start:curr_end].lower()
                continue

            gap_text = text[curr_end:next_start]
            gap_clean = gap_text.strip().lower()
            gap_words = set(re.findall(r"[A-Za-zÀ-ỹ]+", gap_clean))

            # Điều kiện gộp mạnh tay:
            # 1. Khoảng cách ngắn (gap <= max_allowed_gap)
            # 2. Hoặc không chứa dấu ngắt câu nghiêm ngặt (., !, ?, \n) trong luồng aggressive
            should_merge = False
            if len(gap_clean) <= max_allowed_gap:
                if not gap_words or gap_words.issubset(CONNECTORS):
                    should_merge = True
                elif aggressive and not any(p in gap_text for p in [".", "!", "?", "\n"]):
                    # Trong luồng dịch thô, nếu cùng nằm trong 1 vế câu thoại/lời dẫn, gộp nguyên vế câu
                    should_merge = True

            if should_merge:
                curr_end = next_end
                curr_word = text[curr_start:curr_end].lower()
                curr_type = "scene"  # Gộp thành loại scene (SCN) đại diện cho cảnh nhạy cảm
            else:
                merged.append((curr_start, curr_end, curr_word, curr_type))
                curr_start, curr_end, curr_word, curr_type = next_start, next_end, next_word, next_type

        merged.append((curr_start, curr_end, curr_word, curr_type))
        return merged

    def encode(self, text: str, mask_level: str = "word", aggressive: bool = True) -> Tuple[str, Dict[str, Dict[str, str]]]:
        """
        Rà soát và giấu triệt để các từ/cụm từ khớp từ điển nhạy cảm.
        Tự động gộp các từ nhẹ đứng cạnh nhau thành 1 cụm nhạy cảm duy nhất (chế độ aggressive=True mạnh tay hơn cho dịch thô).
        Giữ nguyên 100% cấu trúc câu từ, chủ ngữ, vị ngữ, đại từ sở hữu xung quanh.
        """
        if not text:
            return "", {}

        raw_matches = self.trie.find_all_matches(text)
        if not raw_matches:
            return text, {}

        # Gộp các từ nhạy cảm gần nhau thành cụm ngữ cảnh nhạy cảm thống nhất
        matches = self._merge_proximity_matches(text, raw_matches, aggressive=aggressive)

        mapping_table: Dict[str, Dict[str, str]] = {}
        reverse_term_token_map: Dict[str, str] = {}
        encoded_chunks = []
        last_idx = 0

        for start, end, matched_term_lower, word_type in matches:
            encoded_chunks.append(text[last_idx:start])
            actual_original_text = text[start:end]

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

        encoded_chunks.append(text[last_idx:])
        encoded_text = "".join(encoded_chunks)
        logger.info(f"🛡️ [Encoder - Aggressive={aggressive}] Đã giấu {len(matches)} cụm từ nhạy cảm ngữ cảnh thành {len(mapping_table)} token.")
        return encoded_text, mapping_table


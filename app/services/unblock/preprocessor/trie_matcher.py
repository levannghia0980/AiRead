"""
Longest-Match Trie Matcher (Aho-Corasick / Longest Match Algorithm)
Cải tiến để nạp nhiều từ điển và trả về type (loại từ điển) để mapping chuẩn xác.
"""
from typing import List, Tuple, Dict, Any

import re

WORD_CHAR_RE = re.compile(r"[a-zà-ỹá-ỵă-ặâ-ậê-ệô-ộơ-ợư-ựA-ZÁ-Ỵ0-9_]")

def is_valid_word_boundary(text: str, start: int, end: int) -> bool:
    """
    Kiểm tra ranh giới từ (Word Boundary): Chỉ chấp nhận match nếu start và end đứng ở ranh giới từ,
    tránh việc match 1 từ ngắn ở giữa một từ ghép Tiếng Việt (VD: match 'ấn' trong 'phấn' hay 'vẫn').
    """
    if start > 0 and WORD_CHAR_RE.match(text[start - 1]):
        return False
    if end < len(text) and WORD_CHAR_RE.match(text[end]):
        return False
    return True


class TrieNode:
    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end: bool = False
        self.word: str = ""
        self.type: str = ""

class LongestMatchTrie:
    def __init__(self):
        self.root = TrieNode()
        self.words = []

    def insert(self, word: str, word_type: str = "phrase"):
        """Chèn từ vào Trie với loại cụ thể (scene, body, action...)"""
        if not word:
            return
        # Luôn đưa về lowercase để match không phân biệt hoa thường
        word_lower = word.lower()
        node = self.root
        for char in word_lower:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True
        node.word = word_lower
        node.type = word_type
        if word_lower not in self.words:
            self.words.append(word_lower)

    def load_dictionary(self, words: List[str], word_type: str = "phrase"):
        # Sắp xếp từ theo độ dài giảm dần (mặc dù Trie tự xử lý longest match, 
        # nhưng việc load có logic giúp quản lý tốt hơn).
        sorted_words = sorted(set(words), key=len, reverse=True)
        for word in sorted_words:
            self.insert(word, word_type)

    def find_all_matches(self, text: str) -> List[Tuple[int, int, str, str]]:
        """
        Tìm tất cả các match trong text theo thuật toán Longest Match (không chồng chéo).
        Trả về danh sách tuple: (start_index, end_index, matched_word, word_type)
        Lưu ý: Chỉ chấp nhận match nếu thỏa mãn ranh giới từ chuẩn (Word Boundary).
        """
        if not text:
            return []

        text_lower = text.lower()
        matches = []
        i = 0
        n = len(text_lower)

        while i < n:
            node = self.root
            longest_match = None
            longest_type = None
            longest_end = i

            j = i
            while j < n and text_lower[j] in node.children:
                node = node.children[text_lower[j]]
                j += 1
                if node.is_end:
                    # Kiểm tra xem match này có phải là chữ Hán hay Tiếng Việt hợp lệ ranh giới từ
                    is_chinese = bool(re.search(r"[\u4e00-\u9fff]", node.word))
                    if is_chinese or is_valid_word_boundary(text, i, j):
                        longest_match = node.word
                        longest_type = node.type
                        longest_end = j

            if longest_match:
                matches.append((i, longest_end, longest_match, longest_type))
                i = longest_end  # Nhảy qua span đã match để không bị chồng chéo
            else:
                i += 1

        return matches

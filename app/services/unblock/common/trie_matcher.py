import re
from typing import List, Dict, Tuple, Set

# Danh sách từ ghép tiếng Hán an toàn (Safe Compounds / Whitelist)
# Tuyệt đối KHÔNG ĐƯỢC bóc tách hoặc mask bất kỳ chuỗi con nào thuộc các từ này!
SAFE_COMPOUNDS: Set[str] = {
    # Nhóm 操
    "贞操", "操心", "操劳", "操办", "操纵", "操持", "体操", "早操", "晚操", "操场", "操练", "操刀", "节操", "操作", "风操",
    # Nhóm 逼
    "逼近", "逼迫", "紧逼", "逼人", "威逼", "逼退", "逼真", "逼降", "逼问", "倒逼", "逼出", "逼得", "逼走", "逼供",
    # Nhóm 龟
    "乌龟", "金龟", "海龟", "神龟", "龟缩", "龟壳", "龟速",
    # Nhóm 奸
    "奸细", "奸商", "奸雄", "奸诈", "奸贼", "汉奸", "奸佞", "抓奸", "捉奸",
    # Nhóm 骚
    "骚动", "骚乱", "骚扰", "风骚", "离骚", "骚客",
    # Nhóm 骨
    "骨髓", "深入骨髓", "透骨", "脱胎换骨", "骨肉", "骨气", "骨头", "白骨", "露骨", "刻骨铭心",
    # Nhóm 瘫
    "瘫痪", "瘫坐", "瘫倒", "瘫软"
}

class TrieNode:
    def __init__(self):
        self.children: Dict[str, TrieNode] = {}
        self.is_end_of_word: bool = False
        self.categories: Set[str] = set()

class LongestMatchTrie:
    def __init__(self):
        self.root = TrieNode()
        self.words: Set[str] = set()

    def insert(self, word: str, category: str = "default"):
        if not word or not word.strip():
            return
        clean_word = word.strip().lower()
        
        # BẢO VỆ CHỮ HÁN: Từ tiếng Trung bắt buộc phải từ 2 ký tự trở lên
        # Tuyệt đối cấm từ 1 ký tự đơn lẻ để tránh phá hỏng từ ghép thông thường
        if len(clean_word) < 2 and any('\u4e00' <= c <= '\u9fff' for c in clean_word):
            return
            
        self.words.add(clean_word)
        node = self.root
        for char in clean_word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        node.categories.add(category)

    def load_dictionary(self, words: List[str], category: str = "default"):
        for w in words:
            self.insert(w, category)

    def find_all_matches(self, text: str) -> List[Tuple[int, int, str, Set[str]]]:
        if not text:
            return []
        
        matches = []
        text_lower = text.lower()
        n = len(text)
        i = 0
        
        while i < n:
            node = self.root
            longest_match_len = 0
            longest_categories = set()
            j = i
            
            while j < n and text_lower[j] in node.children:
                node = node.children[text_lower[j]]
                j += 1
                if node.is_end_of_word:
                    is_valid_end = True
                    if j < n:
                        prev_char = text_lower[j-1]
                        next_char = text_lower[j]
                        if re.match(r'[a-zA-Z0-9]', prev_char) and re.match(r'[a-zA-Z0-9]', next_char):
                            is_valid_end = False
                            
                    if is_valid_end:
                        longest_match_len = j - i
                        longest_categories = set(node.categories)
            
            if longest_match_len > 0:
                matched_str = text[i:i + longest_match_len]
                
                # KIỂM TRA BẢO VỆ TỪ AN TOÀN (SAFE COMPOUNDS)
                # Nếu từ khớp nằm trong một từ ghép an toàn (ví dụ: '操' nằm trong '贞操' hay '骨' nằm trong '骨髓') -> BỎ QUA
                is_safe_compound = False
                check_window = text[max(0, i-6):min(n, i + longest_match_len + 6)]
                for safe_word in SAFE_COMPOUNDS:
                    if safe_word in check_window:
                        safe_idx = check_window.find(safe_word)
                        safe_start = max(0, i-6) + safe_idx
                        safe_end = safe_start + len(safe_word)
                        if not (i + longest_match_len <= safe_start or i >= safe_end):
                            is_safe_compound = True
                            break
                            
                if not is_safe_compound:
                    matches.append((i, i + longest_match_len, matched_str, longest_categories))
                    i += longest_match_len
                else:
                    i += 1
            else:
                i += 1
                
        return matches

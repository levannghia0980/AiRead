import re
from typing import List, Dict, Tuple, Set

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
                matches.append((i, i + longest_match_len, matched_str, longest_categories))
                i += longest_match_len
            else:
                i += 1
                
        return matches

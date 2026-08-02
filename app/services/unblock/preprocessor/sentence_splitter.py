import re
from typing import List

def split_sentences(text: str) -> List[str]:
    """
    Tách văn bản thành các câu riêng biệt dựa trên dấu câu (., ?, !)
    nhưng vẫn giữ nguyên cấu trúc xuống dòng và đoạn văn.
    
    Phương pháp: Tìm các dấu câu kết thúc câu, theo sau là khoảng trắng hoặc newline.
    """
    if not text:
        return []
        
    # Pattern giải thích:
    # (?<=...) là lookbehind: phía trước phải là dấu ., !, ? (có thể có ngoặc kép đóng)
    # (?=\s|[A-ZÀ-Ỹ]) là lookahead: phía sau là khoảng trắng hoặc chữ hoa bắt đầu câu mới
    # Tuy nhiên Regex chuẩn tách câu tiếng Việt khá phức tạp.
    # Một cách đơn giản hơn là dùng re.split và bắt lại các dấu câu.
    
    # Chia theo dấu chấm, chấm hỏi, chấm than, hoặc xuống dòng kép.
    # Pattern tách nhưng giữ lại dấu câu: 
    # ([.!?]+(?:\s+|$)) -> Nhóm dấu câu và khoảng trắng sau nó.
    
    parts = re.split(r'([.!?]+(?:\s+|$))', text)
    
    sentences = []
    current_sentence = ""
    
    for part in parts:
        current_sentence += part
        # Nếu part chứa dấu kết thúc câu và khoảng trắng, ta gom lại thành 1 câu
        if re.match(r'^[.!?]+(?:\s+|$)', part):
            sentences.append(current_sentence)
            current_sentence = ""
            
    if current_sentence.strip():
        sentences.append(current_sentence)
        
    # Xử lý trường hợp không có dấu câu nào nhưng có xuống dòng
    final_sentences = []
    for s in sentences:
        if '\n' in s:
            lines = [line + '\n' for line in s.split('\n')]
            # Loại bỏ \n dư ở phần tử cuối nếu text gốc không kết thúc bằng \n
            if lines and lines[-1] == '\n' and not s.endswith('\n'):
                 lines.pop()
            else:
                 if lines and not s.endswith('\n'):
                     lines[-1] = lines[-1][:-1]
            final_sentences.extend([l for l in lines if l])
        else:
            final_sentences.append(s)

    return [s for s in final_sentences if s]

def join_sentences(sentences: List[str]) -> str:
    """Ghép các câu lại thành văn bản."""
    return "".join(sentences)

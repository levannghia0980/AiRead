import re

def clean_duplicate_slang_words(text: str) -> str:
    """
    Khử trùng lặp từ lóng, sửa các lỗi ghép từ nhân bản (ví dụ: 'đầu khấc cặc cặc', 'cổ cổ tử cung', 'địtt tác', 'dâm đãng dâm đãng'...)
    Đảm bảo văn bản sắc văn tự nhiên, mượt mà và không bị lặp từ thô cứng.
    """
    if not text:
        return ""
    
    t = text

    # 1. Sửa từ sai ngữ nghĩa do bị thay thế nhầm 'thao' -> 'địtt'
    t = re.sub(r'(?i)\bđịtt\s+tác\b', 'thao tác', t)
    t = re.sub(r'(?i)\bđịtt\s+túng\b', 'thao túng', t)
    t = re.sub(r'(?i)\bđịtt\s+lộng\b', 'thao lộng', t)
    t = re.sub(r'(?i)\bđịtt\s+tâm\b', 'thao tâm', t)
    t = re.sub(r'(?i)\bđịtt\s+diễn\b', 'thao diễn', t)
    t = re.sub(r'(?i)\bđịtt\s+trì\b', 'thao trì', t)
    t = re.sub(r'(?i)\bthể\s+địtt\b', 'thể thao', t)
    
    # 1b. Sửa từ sai ngữ nghĩa do 干 (làm/khô) bị dịch nhầm thành 'địtt'
    t = re.sub(r'(?i)\bđịtt\s+đến\s+(tốt|hay|đẹp|giỏi|nhanh|chậm|khá|sạch)\b', r'làm \1', t)
    t = re.sub(r'(?i)\bđịtt\s+thành\s+(quả|tích|công|tựu|phẩm)\b', r'làm nên \1', t)
    t = re.sub(r'(?i)\bđịtt\s+(?:đến\s+)?khô\b', 'uống cạn', t)
    t = re.sub(r'(?i)\bđịtt\s+(?:đến\s+)?sạch\b', 'dọn sạch', t)
    t = re.sub(r'(?i)\bđịtt\s+(?:đến\s+)?gọn\b', 'thu gọn', t)

    # 2. Chuẩn hóa 'đầu cặc' & Sửa lặp 'đầu cặc cặc' / 'đầu khấc cặc cặc' / 'đầu khấc' / 'đầu cặc con cặc'
    t = re.sub(r'(?i)\bđầu\s+(?:khấc|cặc)(?:\s+(?:con\s+)?cặc)+\b', 'đầu cặc', t)
    t = re.sub(r'(?i)\b(?:đầu\s+(?:khấc|cặc)\s+)+đầu\s+(?:khấc|cặc)\b', 'đầu cặc', t)
    t = re.sub(r'(?i)\bđầu\s+khấc\b', 'đầu cặc', t)
    t = re.sub(r'(?i)\b(?:quy\s+đầu\s+)+quy\s+đầu\b', 'quy đầu', t)

    # 3. Sửa lặp 'cổ cổ tử cung' / 'cổ cổ' / 'tử tử cung' / 'cổ tử cung tử cung'
    t = re.sub(r'(?i)\b(?:cổ\s+){2,}tử\s+cung\b', 'cổ tử cung', t)
    t = re.sub(r'(?i)\bcổ\s+(?:cổ\s+tử\s+cung|tử\s+cung)\b', 'cổ tử cung', t)
    t = re.sub(r'(?i)\b(?:tử\s+cung\s+)+tử\s+cung\b', 'tử cung', t)
    t = re.sub(r'(?i)\bcổ\s+tử\s+cung(?:\s+tử\s+cung)+\b', 'cổ tử cung', t)

    # 4. Sửa các cụm từ lóng ghép đôi bị nhân bản (Multi-word duplicate compounds)
    compound_dedups = [
        (r'(?i)\b(chó\s+cái)(?:\s+dâm\s+đãng)+\b', 'chó cái dâm đãng'),
        (r'(?i)\b(chó\s+cái\s+dâm\s+đãng)(?:\s+dâm\s+đãng|\s+chó\s+cái)+\b', r'\1'),
        (r'(?i)\b(con\s+đĩ)(?:\s+dâm\s+đãng)+\b', 'con đĩ dâm đãng'),
        (r'(?i)\b(dâm\s+phụ)(?:\s+lẳng\s+lơ|\s+dâm\s+đãng)+\b', r'\1 lẳng lơ'),
        (r'(?i)\b(gợi\s+tình)(?:\s+dâm\s+dục|\s+gợi\s+tình)+\b', 'gợi tình'),
        (r'(?i)\b(khoái\s+cảm)(?:\s+dâm\s+dục)+\b', 'khoái cảm'),
        (r'(?i)\b(tiếng\s+rên)(?:\s+dâm\s+mị)+\b', 'tiếng rên dâm mị'),
        (r'(?i)\b(tiếng\s+rên\s+dâm\s+mị)(?:\s+dâm\s+mị|\s+tiếng\s+rên)+\b', r'\1'),
        (r'(?i)\b(thở\s+dốc)(?:\s+dâm\s+dục)+\b', 'thở dốc'),
        (r'(?i)\b(rên\s+la)(?:\s+dâm\s+đãng)+\b', 'rên la dâm đãng'),
        (r'(?i)\b(rên\s+la\s+dâm\s+đãng)(?:\s+dâm\s+đãng)+\b', r'\1'),
        (r'(?i)\b(phát\s+tình)(?:\s+dâm\s+dục)+\b', 'phát tình'),
        (r'(?i)\b(động\s+tình)(?:\s+dâm\s+dục)+\b', 'động tình'),
        (r'(?i)\b(búp\s+bê\s+tình\s+dục)(?:\s+tình\s+dục|\s+búp\s+bê)+\b', r'\1'),
        (r'(?i)\b(nước\s+lồn)(?:\s+dâm\s+đãng|\s+nước\s+lồn)+\b', 'nước lồn'),
        (r'(?i)\b(ướt\s+đẫm)(?:\s+nước\s+lồn)+\b', 'ướt đẫm nước lồn'),
        (r'(?i)\b(ẩm\s+ướt)(?:\s+nước\s+lồn)+\b', 'ẩm ướt'),
        (r'(?i)\b(trơn\s+tuột)(?:\s+nước\s+lồn)+\b', 'trơn tuột'),
        (r'(?i)\b(nhóp\s+nhép|nhớp\s+nháp)(?:\s+nước\s+lồn)+\b', r'\1'),
        (r'(?i)\b(con\s+cặc\s+bự)(?:\s+con\s+cặc|\s+cặc|\s+bự)+\b', r'\1'),
        (r'(?i)\b(con\s+cặc)(?:\s+con\s+cặc|\s+cặc)+\b', r'\1'),
        (r'(?i)\b(côn\s+thịt)(?:\s+côn\s+thịt|\s+con\s+cặc|\s+cặc)+\b', r'\1'),
        (r'(?i)\b(lỗ\s+lồn)(?:\s+lỗ\s+lồn|\s+lồn)+\b', r'\1'),
        (r'(?i)\b(khe\s+lồn)(?:\s+khe\s+lồn|\s+lồn)+\b', r'\1'),
        (r'(?i)\b(mép\s+lồn)(?:\s+mép\s+lồn|\s+lồn)+\b', r'\1'),
        (r'(?i)\b(hoa\s+huyệt)(?:\s+hoa\s+huyệt|\s+lỗ\s+lồn)+\b', r'\1'),
        (r'(?i)\b(mật\s+huyệt)(?:\s+mật\s+huyệt|\s+lỗ\s+lồn)+\b', r'\1'),
        (r'(?i)\b(bầu\s+vú)(?:\s+bầu\s+vú|\s+vú|\s+ngực)+\b', r'\1'),
        (r'(?i)\b(cặp\s+vú)(?:\s+cặp\s+vú|\s+vú|\s+ngực)+\b', r'\1'),
        (r'(?i)\b(đầu\s+vú)(?:\s+đầu\s+vú|\s+núm\s+vú|\s+vú)+\b', r'\1'),
        (r'(?i)\bđại\s+(?:nhục|nhũ)\s+bầu\s+vú\b', 'bầu vú bự'),
        (r'(?i)\bđại\s+nhục\b', 'khối thịt bự'),
        (r'(?i)\brãnh\s+quy\s+(?:<[^>]+>\s*)?cái\s+đầu(?:\s*</[^>]+>)?\b', 'rãnh đầu cặc'),
        (r'(?i)\bquy\s+(?:<[^>]+>\s*)?cái\s+đầu(?:\s*</[^>]+>)?\b', 'đầu cặc'),
        (r'(?i)\brãnh\s+quy\s+đầu(?:\s+cái\s+đầu|\s+đầu)+\b', 'rãnh đầu cặc'),
        (r'(?i)\brãnh\s+quy\s+đầu\b', 'rãnh đầu cặc'),
        (r'(?i)\bquy\s+đầu\b', 'đầu cặc'),
        (r'(?i)\b(đầu\s+cặc)(?:\s+đầu\s+cặc|\s+cái\s+đầu|\s+đầu)+\b', r'\1'),
        (r'(?i)\b(núm\s+vú)(?:\s+núm\s+vú|\s+đầu\s+vú)+\b', r'\1'),
        (r'(?i)\b(bờ\s+mông)(?:\s+bờ\s+mông|\s+mông)+\b', r'\1'),
        (r'(?i)\b(cặp\s+mông)(?:\s+cặp\s+mông|\s+mông)+\b', r'\1'),
        (r'(?i)\b(cặp\s+đùi)(?:\s+cặp\s+đùi|\s+đùi)+\b', r'\1'),
        (r'(?i)\b(lỗ\s+đít)(?:\s+lỗ\s+đít|\s+đít)+\b', r'\1'),
        (r'(?i)\b(hòn\s+dái)(?:\s+hòn\s+dái|\s+dái)+\b', r'\1'),
        (r'(?i)\b(đút|cắm|đâm)\s+cặc(?:\s+vào\s+lồn|\s+vào)?\s+(lỗ\s+lồn|hoa\s+huyệt|khe\s+lồn)\b', r'\1 cặc vào \2'),
        (r'(?i)\b(đút\s+cặc\s+vào)(?:\s+lồn|\s+cặc)+\b', 'đút cặc vào'),
        (r'(?i)\b(cắm\s+cặc\s+vào)(?:\s+lồn|\s+cặc)+\b', 'cắm cặc vào'),
        (r'(?i)\b(đâm\s+cặc\s+vào)(?:\s+lồn|\s+cặc)+\b', 'đâm cặc vào'),
        (r'(?i)\b(địtt\s+nhau)(?:\s+địtt\s+nhau|\s+làm\s+tình)+\b', r'\1'),
        (r'(?i)\b(hoan\s+ái)(?:\s+hoan\s+ái|\s+địtt\s+nhau)+\b', r'\1'),
        (r'(?i)\b(mây\s+mưa)(?:\s+mây\s+mưa|\s+địtt\s+nhau)+\b', r'\1'),
        (r'(?i)\b(luân\s+phiên\s+cưỡng\s+hiếp\s+tập\s+thể)(?:\s+tập\s+thể)+\b', r'\1'),
        (r'(?i)\b(cưỡng\s+hiếp\s+cuồng\s+bạo)(?:\s+cuồng\s+bạo)+\b', r'\1'),
        (r'(?i)\b(cưỡng\s+hiếp\s+thô\s+bạo)(?:\s+thô\s+bạo)+\b', r'\1'),
        (r'(?i)\b(quần\s+tất)(?:\s+quần\s+tất|\s+tất)+\b', r'\1'),
        (r'(?i)\b(lớp|đôi|chiếc)\s+quần\s+tất(?:\s+(?:lớp|đôi|chiếc)?\s*quần\s+tất|\s+tất)+\b', r'\1 quần tất'),
        (r'(?i)\b(quần\s+tất\s+đen)(?:\s+quần\s+tất|\s+tất\s+đen|\s+tất)+\b', r'\1'),
        (r'(?i)\b(tất\s+đen)(?:\s+quần\s+tất|\s+tất\s+đen|\s+tất)+\b', r'\1'),
        (r'(?i)\b(tất\s+lưới)(?:\s+quần\s+tất|\s+tất\s+lưới|\s+tất)+\b', r'\1'),
        (r'(?i)\b(tất\s+chân)(?:\s+tất\s+chân|\s+tất)+\b', r'\1'),
        (r'(?i)\b(quần\s+tất)\s+tất\s+đen\b', 'quần tất đen'),
        (r'(?i)\b(tất\s+đen)\s+quần\s+tất\b', 'quần tất đen'),
        (r'(?i)\b(quần\s+lót)(?:\s+quần\s+lót|\s+quần\s+trong)+\b', r'\1'),
        (r'(?i)\b(quần\s+lọt\s+khe)(?:\s+quần\s+lọt\s+khe|\s+lọt\s+khe)+\b', r'\1'),
        (r'(?i)\b(áo\s+ngực)(?:\s+áo\s+ngực|\s+áo\s+lót)+\b', r'\1'),
        (r'(?i)\b(đồ\s+lót)(?:\s+đồ\s+lót)+\b', r'\1'),
        (r'(?i)\bcu\s+cuối\s+cùng\b', 'cuối cùng'),
        (r'(?i)\blồn\s+tử\s+cung\b', 'sâu trong tử cung'),
        (r'(?i)\bcon\s+gà\s+trống(?:\s+của\s+hắn|\s+của\s+anh|\s+to\s+lớn|\s+di\s+chuyển|\s+cứng\s+ngắc)?\b', 'côn thịt'),
    ]

    for p, repl in compound_dedups:
        t = re.sub(p, repl, t)

    # 5. Khử trùng lặp tổng quát cho từng từ/cụm từ đơn lẻ lặp liên tiếp 2 lần trở lên
    single_slangs = [
        r'quần\s+tất', r'quần\s+tất\s+đen', r'tất\s+đen', r'tất\s+lưới', r'tất\s+chân',
        r'quần\s+lót', r'quần\s+lọt\s+khe', r'áo\s+ngực', r'đồ\s+lót',
        r'dâm\s+đãng', r'dâm\s+dục', r'dâm\s+mị', r'dâm\s+loạn', r'dâm\s+mỹ', r'dâm\s+tình',
        r'gợi\s+tình', r'khiêu\s+dâm', r'khoái\s+cảm', r'thở\s+dốc', r'rên\s+rỉ',
        r'tiếng\s+rên', r'chó\s+cái', r'nô\s+lệ', r'búp\s+bê\s+tình\s+dục',
        r'nước\s+lồn', r'dâm\s+dịch', r'tinh\s+dịch', r'tinh\s+trùng', r'lỗ\s+lồn', r'khe\s+lồn',
        r'mép\s+lồn', r'hoa\s+huyệt', r'mật\s+huyệt', r'con\s+cặc', r'con\s+cặc\s+bự',
        r'côn\s+thịt', r'bầu\s+vú', r'cặp\s+vú', r'đầu\s+vú', r'núm\s+vú',
        r'bờ\s+mông', r'cặp\s+mông', r'cặp\s+đùi', r'lỗ\s+đít', r'hòn\s+dái',
        r'bắn\s+tinh', r'phun\s+tinh', r'đút\s+cặc', r'rút\s+cặc', r'địtt\s+nhau',
        r'làm\s+tình', r'hoan\s+ái', r'mây\s+mưa', r'cưỡng\s+hiếp', r'thôi\s+miên',
        r'đầu\s+cặc', r'đầu\s+khấc', r'quy\s+đầu', r'cổ\s+tử\s+cung', r'tử\s+cung', r'cặc', r'lồn', r'địtt', r'địt'
    ]

    for s in single_slangs:
        t = re.sub(rf'(?i)\b({s})(?:\s+(?:\1))+\b', r'\1', t)
    # 6. Tự động tách khoảng trắng cho từ lóng / bộ phận cơ thể bị dính với từ tiếng Việt đứng trước / sau
    # (VD: cảlỗ lồn -> cả lỗ lồn, vàtử cung -> và tử cung, câycon cặc -> con cặc, lầntinh dịch -> lần tinh dịch, tứcđồi trụy -> tức đồi trụy)
    stuck_slang_words = [
        "lỗ lồn", "tử cung", "cổ tử cung", "con cặc", "con cặc bự", "côn thịt", "cự vật",
        "tinh dịch", "đồi trụy", "dâm đãng", "dâm dục", "dâm loạn", "đầu cặc", "búp bê tình dục",
        "nhục bổng", "âm đạo", "hoa huyệt", "mật huyệt", "tiểu huyệt", "cưỡng hiếp", "hãm hiếp",
        "địtt", "đụ", "chịch", "xoạc", "hòn dái", "lông lồn", "khe lồn", "mép lồn", "lỗ đít"
    ]
    vn_lower = r'a-zàáảãạâấầẩẫậăắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộơớờởỡợúùủũụưứừửữựỳýỷỹỵđ'
    vn_upper = r'A-ZÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ'
    vn_char = rf'[{vn_lower}{vn_upper}]'

    # Sắp xếp từ dài trước ngắn sau để không bao giờ cắt nhầm đuôi từ
    sorted_stuck_slangs = sorted(set(stuck_slang_words), key=len, reverse=True)

    for sw in sorted_stuck_slangs:
        t = re.sub(rf'({vn_char})({re.escape(sw)})\b', r'\1 \2', t, flags=re.IGNORECASE)
        t = re.sub(rf'\b({re.escape(sw)})({vn_char})', r'\1 \2', t, flags=re.IGNORECASE)

    # 7. KHÔI PHỤC BẢO VỆ TỪ LÓNG TTS: Khôi phục 'địtt' nếu lỡ bị tách thành 'địt t'
    t = re.sub(r'(?i)\bđịt\s+t\b', 'địtt', t)
    t = re.sub(r'(?i)\bđịtt\s+t\b', 'địtt', t)

    t = re.sub(rf'({vn_char})(độc ác|gian lận|triền miên|xung kích|trò chơi)', r'\1 \2', t, flags=re.IGNORECASE)
    t = re.sub(r'(?i)\bcây\s*con\s+cặc\b', 'con cặc', t)
    t = re.sub(r'(?i)\bquy\s*đầu\b', 'quy đầu', t)
    
    # Dọn khoảng trắng thừa
    t = re.sub(r' {2,}', ' ', t)
    return t

import re
from typing import List

# Các mẫu rác quảng cáo TOÀN DÒNG (chỉ xóa khi cả dòng là quảng cáo, không xóa giữa câu)
FULL_LINE_AD_PATTERNS = [
    re.compile(r'^\s*https?://\S+\s*$'),
    re.compile(r'^\s*www\.\S+\s*$'),
    re.compile(r'^\s*m\.[a-zA-Z0-9.-]+\.[a-zA-Z]+\s*$'),
    re.compile(r'^\s*请记住本书首发域名：.*$'),
    re.compile(r'^\s*最新章节txt下载：.*$'),
    re.compile(r'^\s*本书域名：.*$'),
    re.compile(r'^\s*手机用户请浏览.*阅读.*$'),
    re.compile(r'^\s*一秒记住【.*】.*$'),
    re.compile(r'^\s*百度搜索【.*】.*$'),
    re.compile(r'^\s*【\s*推荐下.*换源.*】\s*$'),
    re.compile(r'^\s*p\s*s\s*[：:].*求.*$', re.IGNORECASE),
    re.compile(r'^\s*\(?笔趣阁\)?\s*$'),
    re.compile(r'^\s*\(?UU看书\)?\s*$'),
    re.compile(r'^\s*\(?全本小说网\)?\s*$'),
    re.compile(r'^\s*\(?起点中文网\)?\s*$'),
    re.compile(r'^\s*\(?看书神站\)?\s*$'),
    re.compile(r'^\s*\(?飞卢小说网\)?\s*$'),
]


def sanitize_chinese_raw_text(text: str) -> str:
    """
    Chuẩn hóa văn bản gốc tiếng Trung (RAW) trước khi gửi LLM.
    Lọc bỏ rác crawler metadata (icon web, số từ, thời gian cào web, tên tác giả crawler rác) để AI không dịch nhầm vào truyện.
    """
    if not text:
        return text

    t = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Loại bỏ các dòng rác crawler website Trung Quốc
    t = re.sub(r'(?m)^\s*[]\s*\n?', '', t)
    t = re.sub(r'(?m)^\s*(?:蘑菇面要加蛋|Mì\s+nấm\s+.*)\s*\n?', '', t)
    t = re.sub(r'(?m)^\s*\d+\s*(?:字|Chữ|từ)\s*\n?', '', t)
    t = re.sub(r'(?m)^\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s*\n?', '', t)
    
    return t


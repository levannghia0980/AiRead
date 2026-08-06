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
    Giữ 100% VĂN BẢN GỐC tiếng Trung (RAW) trước khi gửi LLM.
    Đảm bảo tuyệt đối không xóa bớt dòng, không lọc chữ/quảng cáo/PS gây mất đoạn.
    Chỉ chuẩn hóa kiểu xuống dòng giữa Windows và Linux/Mac.
    """
    if not text:
        return text

    # Chỉ chuẩn hóa xuống dòng để đảm bảo tương thích hệ thống
    return text.replace('\r\n', '\n').replace('\r', '\n')


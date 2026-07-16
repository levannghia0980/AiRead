import re
from typing import List

# Regular expressions for common Chinese novel website ads, watermarks, and prompts
CLEAN_PATTERNS = [
    # Website urls and references
    r"https?://[a-zA-Z0-9\.\/\-_]+",
    r"www\.[a-zA-Z0-9\.\/\-_]+",
    r"[a-zA-Z0-9\-]+\.(cx|pro|me|com|net|org|xyz|site|club|vip|info)",
    
    # Common 69shuba / twkan watermarks & ad lines
    r"最新网址：.*",
    r"请收藏.*",
    r"手机阅读.*",
    r"本站.*",
    r"无广告.*",
    r"更新最快.*",
    r"订阅.*",
    r"点击下载.*",
    r"TXT下载.*",
    r"&nbsp;",
    r"记住网址.*",
    r"\\t",
    
    # Brackets containing ads
    r"【.*?(github|discord|telegram|app|web|tải|truyện|dịch).*?】",
    r"（.*?广告.*?）",
    r"\(.*?广告.*?\)",
    r"\[.*?广告.*?\]",
]

# Compiled patterns for efficiency
COMPILED_CLEAN_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in CLEAN_PATTERNS]

def clean_raw_chinese_text(text: str) -> str:
    """
    Cleans raw Chinese text by removing watermarks, ads, HTML remains,
    and normalizes line breaks and whitespace.
    """
    if not text:
        return ""
    
    # Split text into lines to process each line individually
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
            
        # Apply ad removal patterns
        for pattern in COMPILED_CLEAN_PATTERNS:
            cleaned_line = pattern.sub("", cleaned_line)
            
        cleaned_line = cleaned_line.strip()
        
        # Skip if the entire line has been wiped out or is too short and looks like leftover ads
        if not cleaned_line:
            continue
            
        # Filter lines that only contain words like "69shuba" or domain names
        line_lower = cleaned_line.lower()
        if any(term in line_lower for term in ["69shuba", "69shu", "69shu.pro", "69shu.cx", "69shu.me", "twkan", "twkan.com", "twkan.co", "shuba"]):
            continue
            
        # Skip consecutive duplicate lines
        if cleaned_lines and cleaned_line == cleaned_lines[-1]:
            continue
            
        cleaned_lines.append(cleaned_line)
    
    # Strip non-consecutive watermarks: detect paragraphs that appear 2+ times
    # across the entire chapter (anti-scraping watermarks inserted at random positions)
    if len(cleaned_lines) >= 5:
        line_counts = {}
        for cl in cleaned_lines:
            if len(cl) >= 10:
                line_counts[cl] = line_counts.get(cl, 0) + 1
        watermark_set = {l for l, c in line_counts.items() if c >= 2}
        if watermark_set:
            cleaned_lines = [cl for cl in cleaned_lines if cl not in watermark_set]
        
    # Reassemble and normalize spacing
    # Ensure paragraphs are separated by exactly one blank line
    cleaned_text = "\n\n".join(cleaned_lines)
    
    # Replace 3 or more newlines with double newlines
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    
    return cleaned_text.strip()

def clean_translated_vietnamese_text(text: str) -> str:
    """
    Cleans and standardizes the translated Vietnamese text.
    Corrects common quotation marks and spacing anomalies.
    """
    if not text:
        return ""
        
    # Standardize quotation marks
    text = text.replace("「", "\"").replace("」", "\"")
    text = text.replace("『", "'").replace("』", "'")
    text = text.replace("“", "\"").replace("”", "\"")
    text = text.replace("‘", "'").replace("’", "'")
    
    # Fix spacing issues before/after punctuation
    text = re.sub(r"\s+([,\.\?\!;\:])", r"\1", text)  # remove spaces before punctuation
    
    # Reduce consecutive newlines to maximum of two
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove leading/trailing spaces for each line
    lines = [line.strip() for line in text.split("\n")]
    
    # Filter empty lines at start/end
    return "\n\n".join([l for l in lines if l]).strip()

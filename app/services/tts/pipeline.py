import os
import re
import time
import shutil
import asyncio
import random
import subprocess
import psutil
import edge_tts
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion, TTSChunk
from app.services.storage.file_storage import sanitize_filename, save_tts_text_file
from app.core.config import get_active_setting
from app.services.tts.offline_piper import synthesize_text_piper_async, is_piper_available

# Bản đồ ánh xạ cấu hình giọng đọc của Edge-TTS sang tên giọng nói thực tế
VOICE_MAP = {
    "default": "vi-VN-HoaiMyNeural",
    "female": "vi-VN-HoaiMyNeural",
    "nu": "vi-VN-HoaiMyNeural",
    "male": "vi-VN-NamMinhNeural",
    "nam": "vi-VN-NamMinhNeural"
}

# Theo dõi các tác vụ TTS đang chạy trực tiếp trên bộ nhớ để thăm dò trạng thái
ACTIVE_TTS_JOBS: Dict[str, Dict[str, Any]] = {}

# Semaphore toàn cục giới hạn số kết nối TTS đồng thời thực sự tới Microsoft (ngưỡng an toàn 4 luồng/IP tránh ConnectionReset)
TTS_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(4)
_CONSECUTIVE_FAILURES = {"count": 0}

def get_ffmpeg_cmd() -> str:
    """Trả về đường dẫn tới ffmpeg executable (dùng imageio_ffmpeg hoặc hệ thống)"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def get_voice_name(profile_name: str) -> str:
    p = profile_name.lower().strip()
    return VOICE_MAP.get(p, p)

def get_audio_duration_ffmpeg(file_path: str) -> str:
    """Sử dụng FFmpeg -i để trích xuất độ dài (duration) của file âm thanh"""
    if not os.path.exists(file_path):
        return "00:00:00"
    try:
        cmd = [get_ffmpeg_cmd(), "-i", file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        output = result.stderr
        match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2})", output)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[TTS-MERGER] Lỗi đọc duration tệp {file_path}: {e}")
    return "00:00:00"

def generate_silence_file(duration_sec: float = 0.25, sample_rate: int = 44100) -> Optional[str]:
    """Tạo tệp MP3 chứa khoảng lặng (silence) với độ dài tùy chọn theo chuẩn 44.1kHz Stereo"""
    import tempfile
    silence_path = os.path.join(tempfile.gettempdir(), f"silence_{int(duration_sec*1000)}ms_44k.mp3")
    if os.path.exists(silence_path) and os.path.getsize(silence_path) > 0:
        return silence_path
    try:
        cmd = [
            get_ffmpeg_cmd(), "-y", "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=stereo",
            "-t", str(duration_sec),
            "-ar", "44100", "-ac", "2",
            "-b:a", "192k", silence_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        if result.returncode == 0 and os.path.exists(silence_path):
            return silence_path
    except Exception as e:
        print(f"[TTS-SILENCE] Lỗi tạo file silence: {e}")
    return None

def merge_audio_files(file_paths: List[str], output_path: str, add_silence_sec: float = 0.25) -> bool:
    """Ghép nối danh sách các tệp mp3 bằng FFmpeg Concat Demuxer (-c copy) kèm khoảng nghỉ silence tùy chọn"""
    if not file_paths:
        return False
    
    silence_path = generate_silence_file(add_silence_sec, sample_rate=44100) if (add_silence_sec > 0 and len(file_paths) > 1) else None
    
    list_file_path = output_path + ".txt"
    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for idx, fp in enumerate(file_paths):
                # Chuẩn hóa đường dẫn chứa dấu gạch chéo xuôi cho FFmpeg tương thích Windows
                normalized_path = fp.replace("\\", "/")
                f.write(f"file '{normalized_path}'\n")
                if silence_path and idx < len(file_paths) - 1:
                    norm_silence = silence_path.replace("\\", "/")
                    f.write(f"file '{norm_silence}'\n")
        
        cmd = [get_ffmpeg_cmd(), "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        return result.returncode == 0
    except Exception as e:
        print(f"[TTS-MERGER] Lỗi khi chạy lệnh ghép nối FFmpeg: {e}")
        return False
    finally:
        if os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
            except Exception:
                pass

def _convert_roman_numerals(text: str) -> str:
    """Chuyển đổi số La Mã trong ngữ cảnh tiếng Việt (Tập I -> Tập 1, Chương IV -> Chương 4, thế kỷ XXI -> thế kỷ 21)"""
    roman_map = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
        'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
        'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20,
        'XXI': 21, 'XXII': 22, 'XXIII': 23, 'XXIV': 24, 'XXV': 25,
        'XXX': 30, 'XL': 40, 'L': 50, 'LX': 60, 'LXX': 70, 'LXXX': 80, 'XC': 90, 'C': 100
    }
    sorted_romans = sorted(roman_map.keys(), key=len, reverse=True)
    roman_pattern = '|'.join(sorted_romans)
    
    prefix_keywords = r'(?:Tập|Chương|Quyển|Phần|Hồi|Cấp|Bậc|Tầng|Thế\s+kỷ|thế\s+kỷ|Khóa|Hàng|Đợt|Giai\s+đoạn|Vòng)'
    def replace_prefix(m):
        kw = m.group(1)
        r = m.group(2).upper()
        return f"{kw} {roman_map.get(r, r)}"
    
    text = re.sub(rf'\b({prefix_keywords})\s+({roman_pattern})\b', replace_prefix, text, flags=re.IGNORECASE)
    
    def replace_heading(m):
        r = m.group(1).upper()
        punct = m.group(2)
        return f"{roman_map.get(r, r)}{punct} "
    
    text = re.sub(rf'^\s*({roman_pattern})([.:\-])\s+', replace_heading, text, flags=re.MULTILINE)
    return text

def sanitize_tts_text(text: str) -> str:
    """
    Tiền xử lý văn bản toàn diện chuẩn mực trước khi gửi vào Edge-TTS:
    - Loại bỏ HTML, Markdown, rác quảng cáo, emoji, ký tự điều khiển/zero-width
    - Chuẩn hóa số La Mã, từ viết tắt game/truyện hệ thống (EXP, HP, MP, Lv, NPC, VIP)
    - Xử lý hoàn hảo các ký hiệu toán học, dấu âm (+100, -50 HP, 5+3=8, 10-3, 5*3, 10/2, 50%, $100, 5000₫, °C, >, <, >=, <=, !=, ~)
    - Xử lý dấu ngoặc mượt mà, bảo toàn dấu ba chấm (...) tạo nhịp ngắt cảm xúc
    - Loại bỏ ngắt nhịp vô lý giúp audiobook truyền cảm, tự nhiên, đọc xuyên suốt.
    """
    if not text:
        return text

    # 0. Loại bỏ ký tự rỗng/vô hình zero-width, byte order mark và control characters
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0]', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # 1. Unescape HTML entities trước khi xử lý
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")

    # 2. Loại bỏ HTML tags thực sự (tránh xóa nhầm biểu thức so sánh toán học như < 5 hay <= 10)
    text = re.sub(r'</?[a-zA-Z][a-zA-Z0-9]*[^>]*>', ' ', text)
    text = re.sub(r'\[/?[a-zA-Z0-9=\-]+\]', '', text)

    # 3. Chuyển đổi phép nhân và số thẻ '#' TRƯỚC khi xóa Markdown
    text = re.sub(r'(\d+)\s*[*×xX]\s*(\d+)', r'\1 nhân \2', text)
    text = re.sub(r'(^|\s)#(\d+)', r'\1số \2', text)

    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'_{1,3}', '', text)
    text = re.sub(r'^[=\-*~+_#]{3,}.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[-–—]{3,}', ' — ', text)
    text = re.sub(r'~{2,}', '', text)

    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001f900-\U0001f9ff\U00002600-\U000026FF]', '', text)
    text = re.sub(r'[★☆◆◇■□▲△▼▽●○♥♠♣♦♂♀⟪⟫▸▹►▻◄◄§†‡✓✕✗¶™®©♪♫✿❀❁☸⚡⚙⚔🛡🗡👑✦✧✨✴❇❄🔴🔵🟡🟢🟣⭐🌟🔥💥💢]', '', text)

    unit_words_pattern = r'^(?:năm|tháng|ngày|giờ|phút|giây|lần|tuổi|người|cái|bước|món|trận|hiệp|vòng|tầng|cấp|thế\s+kỷ)$'
    def _clean_chapter_header(m):
        line = m.group(0).strip()
        if not line:
            return ""
        if re.search(r'[,;!?]$', line):
            return line 
        if re.match(r'^(?:Quyển\s+\d+\s*[-–—:]?\s*)?Chương\s+\d+$', line, re.IGNORECASE):
            return "" 
        if re.match(r'^(?:Quyển\s+\d+\s*[-–—:]?\s*)?Chương\s+\d+\s*[:.:\-–—]', line, re.IGNORECASE):
            return "" 
        m_word = re.match(r'^(?:Quyển\s+\d+\s*[-–—:]?\s*)?Chương\s+\d+\s+([^\s]+)', line, re.IGNORECASE)
        if m_word:
            first_w = m_word.group(1).lower()
            if re.match(unit_words_pattern, first_w):
                return line 
            if not re.search(r'\.$', line):
                return "" 
        return line

    text = re.sub(r'^\s*(?:Quyển\s+\d+\s*[-–—:]?\s*)?Chương\s+\d+.*$', _clean_chapter_header, text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'[\(\[\{]\s*(?:Hết\s+Chương(?:\s+\d+)?|\bHết\b|Chương\s+kết\ thúc|Tác\ giả\ có\ lời\ muốn\ nói)[^\)\}\]\n]*[\)\]\}]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*[\(\[\{]?\s*(?:Hết\s+Chương(?:\s+\d+)?|\bHết\b)\s*[\)\]\}]?\.?\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*[-–—]*\s*Hết\s*[-–—]*\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)

    text = re.sub(r'\s*(?:→|⇒|-->|->)\s*', ' chuyển thành ', text)
    text = re.sub(r'\s*(?:←|⇐|<--|<-)\s*', ' từ ', text)
    text = re.sub(r'↑\s*(\d+)', r' tăng \1 ', text)
    text = re.sub(r'↓\s*(\d+)', r' giảm \1 ', text)
    text = text.replace('↑', ' tăng ').replace('↓', ' giảm ')

    text = re.sub(r'(?<!cộng trừ)\s*±\s*', ' cộng trừ ', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<!vô cực)\s*∞\s*', ' vô cực ', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<!xấp xỉ)\s*≈\s*', ' xấp xỉ ', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<!khác)\s*≠\s*', ' khác ', text, flags=re.IGNORECASE)
    text = text.replace('≥', ' lớn hơn hoặc bằng ').replace('≤', ' nhỏ hơn hoặc bằng ')

    text = text.replace('「', '"').replace('」', '"').replace('『', '"').replace('』', '"')
    text = text.replace('《', '"').replace('》', '"').replace('【', '"').replace('】', '"')
    text = text.replace('。', '.').replace('，', ',').replace('！？', '?').replace('？！', '?').replace('……', '...')

    text = re.sub(r'[\(\[\{]\s*', ' ', text)
    text = re.sub(r'\s*[\)\]\}]', ' ', text)

    text = _convert_roman_numerals(text)

    text = re.sub(r'\bEXP\b|\bExp\b', 'điểm kinh nghiệm', text)
    text = re.sub(r'\bHP\b|\bHp\b', 'máu', text)
    text = re.sub(r'\bMP\b|\bMp\b', 'năng lượng', text)
    text = re.sub(r'\b(?:Lv|LV|Level)\.?\s*(\d+)\b', r'Cấp \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bNPC\b', 'N P C', text)
    text = re.sub(r'\bVIP\b', 'V I P', text)
    text = re.sub(r'\bBOSS\b|\bBoss\b', 'Trùm', text)
    text = re.sub(r'\bBUG\b|\bBug\b', 'lỗi', text)
    text = re.sub(r'\bPK\b', 'P K', text)
    text = re.sub(r'\bKO\b|\bK\.O\b', 'K O', text)
    text = re.sub(r'\bAI\b', 'A I', text)

    text = re.sub(r'(^|[^\w\d\s]|\s)\+(\d+)', r'\1cộng \2', text)
    text = re.sub(r'(^|[^\w\d\s]|\s)-(\d+)(?=\s*(?:máu|năng lượng|điểm|exp|%|$|\b|\)))', r'\1trừ \2', text)

    text = re.sub(r'\$\s*(\d+(?:[.,]\d+)?)', r'\1 đô la', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*\$', r'\1 đô la', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*(?:USD|usd)\b', r'\1 đô la', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*€', r'\1 ơ-rô', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*(?:EUR|eur)\b', r'\1 ơ-rô', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*[¥￥]', r'\1 yên', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*(?:JPY|jpy)\b', r'\1 yên', text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*(?:₫|VNĐ|vnd|VND)(?!\w)', r'\1 đồng', text)

    text = re.sub(r'-\s*(\d+)\s*°?\s*C\b', r'âm \1 độ C', text)
    text = re.sub(r'-\s*(\d+)\s*độ\b', r'âm \1 độ', text)
    text = re.sub(r'(\d+)\s*°\s*C\b', r'\1 độ C', text)
    text = re.sub(r'(\d+)\s*°\s*F\b', r'\1 độ F', text)
    text = re.sub(r'(\d+)\s*°(?!\w)', r'\1 độ', text)

    text = re.sub(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', lambda m: f"ngày {int(m.group(1))} tháng {int(m.group(2))} năm {m.group(3)}", text)

    text = re.sub(r'\b1/2\b', 'một phần hai', text)
    text = re.sub(r'\b1/3\b', 'một phần ba', text)
    text = re.sub(r'\b1/4\b', 'một phần tư', text)
    text = re.sub(r'\b3/4\b', 'ba phần tư', text)

    text = re.sub(r'(\d+)\s*\+\s*(\d+)', r'\1 cộng \2', text)
    text = re.sub(r'(?<=\s)\+(?=\s)', 'cộng', text)
    text = re.sub(r'(\d+)\s*[-–]\s*(\d+)', r'\1 trừ \2', text)
    text = re.sub(r'(\d+)\s*[xX*×]\s*(\d+)', r'\1 nhân \2', text)
    text = re.sub(r'(?<=\s)[*×](?=\s)', 'nhân', text)
    text = re.sub(r'(\d+)\s*[:/÷]\s*(\d+)', r'\1 chia \2', text)
    text = re.sub(r'(?<=\s)[:÷](?=\s)', 'chia', text)
    text = re.sub(r'(\d+)\s*=\s*(\d+)', r'\1 bằng \2', text)
    text = re.sub(r'(?<=\s)=(?=\s)', 'bằng', text)

    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 phần trăm', text)
    text = re.sub(r'(?<=\s)%([,\s.!?]|$)', r' phần trăm\1', text)

    text = re.sub(r'(^|\s)>=\s*', r'\1lớn hơn hoặc bằng ', text)
    text = re.sub(r'(^|\s)<=\s*', r'\1nhỏ hơn hoặc bằng ', text)
    text = re.sub(r'(^|\s)!=\s*', r'\1khác ', text)
    text = re.sub(r'(^|\s)>\s*', r'\1lớn hơn ', text)
    text = re.sub(r'(^|\s)<\s*', r'\1nhỏ hơn ', text)
    text = re.sub(r'(^|\s)~\s*(\d+)', r'\1khoảng \2', text)
    text = re.sub(r'(^|\s)~\s*', r'\1khoảng ', text)
    text = re.sub(r'(?<=\s)&(?=\s)', 'và', text)
    text = re.sub(r'(^|\s)@([A-Za-z0-9_]+|\s)', r'\1a còng \2', text)
    text = re.sub(r'(\d+)\s*\^\s*(\d+)', r'\1 mũ \2', text)

    text = re.sub(r'(\d+)\s*(km/h|km/g|m/s)\b', r'\1 km trên giờ', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*(km|cm|mm|kg|mg|ml|m|g|tháng|năm|phút|giây|h|tr|tỷ|V|Hz|W|kW|GB|MB|TB)\b', r'\1 \2', text, flags=re.IGNORECASE)

    text = re.sub(r'\bTP\.?\s*HCM\b', 'Thành phố Hồ Chí Minh', text, flags=re.IGNORECASE)
    text = re.sub(r'\bTP\.\s*', 'Thành phố ', text)
    text = re.sub(r'\bPGS\.\s*', 'Phó Giáo sư ', text)
    text = re.sub(r'\bGS\.\s*', 'Giáo sư ', text)
    text = re.sub(r'\bTS\.\s*', 'Tiến sĩ ', text)
    text = re.sub(r'\bThS\.\s*', 'Thạc sĩ ', text)

    text = re.sub(r'["“”]{2,}', '"', text)
    text = re.sub(r"['’]{2,}", "'", text)
    text = re.sub(r'[:：]\s*[-–—]?\s*["“”\'’]{1,2}', r': "', text)
    text = re.sub(r'^\s*[-–—]\s*(?=["“])', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-–—]\s+(?=[A-ZÀ-Ỹa-zà-ỹ])', '"', text, flags=re.MULTILINE)

    text = re.sub(r'([aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵAEIOUYÀÁẢÃẠ])\1{2,}', r'\1\1', text, flags=re.IGNORECASE)
    text = re.sub(r'([bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ])\1{2,}', r'\1', text)

    text = re.sub(r'\b((?:ha|hà|hả|hạ|he|hê|hề|hi|hì|hí|ho|hò|hó|hu|hù|hú|hư|hừ|kha|khà)\s*){4,}', 
                  lambda m: ' '.join(m.group(0).split()[:3]) + '.', text, flags=re.IGNORECASE)

    text = text.strip()
    return text


def split_text_into_chunks(text: str, max_chars: int = 2200) -> List[str]:
    """
    Phân tách văn bản thành các chunk kích thước tối ưu (mặc định 2200 ký tự) để Edge-TTS đọc mượt mà,
    xuyên suốt, tự nhiên, tải song song siêu nhanh gấp 15-20 lần và không bị ngắt ngập vô lý.
    """
    if not text or not text.strip():
        return []
    
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    
    # 1. Tách theo đoạn văn trước
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    chunks = []
    current_chunk = []
    current_len = 0
    
    for para in paragraphs:
        para_len = len(para)
        
        # Nếu đoạn văn quá dài vượt max_chars, chia theo câu (.!?)
        if para_len > max_chars:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_len = 0
            
            # Tách đoạn dài thành các câu (giữ kèm dấu ngoặc kép / ngoặc ôm phía sau)
            sentences = re.split(r'(?<=[.!?]["”’\)\}\]])\s+|\n+|(?<=[.!?])\s+', para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                sent_len = len(sent)
                
                if sent_len > max_chars:
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = []
                        current_len = 0
                    
                    start = 0
                    while start < len(sent):
                        end = min(start + max_chars, len(sent))
                        if end < len(sent):
                            last_space = sent.rfind(' ', start, end)
                            if last_space > start:
                                end = last_space
                        chunks.append(sent[start:end].strip())
                        start = end
                    continue
                
                if current_len + sent_len + 1 > max_chars:
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                    current_chunk = [sent]
                    current_len = sent_len
                else:
                    current_chunk.append(sent)
                    current_len += sent_len + 1
            continue
        
        # Đoạn văn vừa vặn: gộp vào chunk hiện tại
        if current_len + para_len + 2 > max_chars:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk = [para]
            current_len = para_len
        else:
            current_chunk.append(para)
            current_len += para_len + 2
            
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
        
    return [c.strip() for c in chunks if c and c.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# PER-CHAPTER AUDIO CACHE ARCHITECTURE
# Mỗi chương = 1 file mp3 vĩnh viễn tại chapters/XXXXXX.mp3
# Range audio = FFmpeg concat tức thì, không cần TTS lại
# ─────────────────────────────────────────────────────────────────────────────

BASE_AUDIO_DIR = r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS"
BASE_TRANSLATED_DIR = r"D:\NENGHIA0980\AIREAD\Output"


def _get_chapter_cache_path(chapters_cache_dir: str, chapter_no: int) -> str:
    """Trả về đường dẫn cache mp3 của 1 chương cụ thể"""
    return os.path.join(chapters_cache_dir, f"{chapter_no:06d}.mp3")


def _is_chapter_cached(chapters_cache_dir: str, chapter_no: int, novel_folder: str = "") -> bool:
    """Kiểm tra cache mp3 của chương có tồn tại và còn mới hơn tệp văn bản dịch không"""
    p = _get_chapter_cache_path(chapters_cache_dir, chapter_no)
    if not (os.path.exists(p) and os.path.getsize(p) > 0):
        return False
    if novel_folder:
        for subf in ["04_KetQua", "04b_VanBanTTS"]:
            txt_path = os.path.join(BASE_TRANSLATED_DIR, subf, novel_folder, "chapters", f"{chapter_no:06d}.txt")
            if os.path.exists(txt_path) and os.path.getsize(txt_path) > 0:
                try:
                    # Nếu tệp văn bản mới hơn tệp mp3 cache -> cache đã cũ, cần làm lại
                    if os.path.getmtime(txt_path) > os.path.getmtime(p):
                        return False
                except Exception:
                    pass
    return True


def _read_chapter_text(novel_folder: str, chapter_no: int) -> Optional[str]:
    """Chỉ đọc bản dịch chuẩn đã hoàn thành Hậu Xử Lý tại 04_KetQua (TUYỆT ĐỐI KHÔNG đọc 03_DichAI_LLM, GG hay RAW)"""
    path = os.path.join(
        BASE_TRANSLATED_DIR, "04_KetQua", novel_folder,
        "chapters", f"{chapter_no:06d}.txt"
    )
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return None


async def _read_chapter_text_from_db_or_disk(session, novel_id: int, novel_folder: str, chapter: Chapter) -> Optional[str]:
    """Đọc nội dung văn bản của chương từ DB hoặc đĩa"""
    from app.services.storage.file_storage import read_version_file_content
    stmt_ver = select(ChapterVersion).where(
        ChapterVersion.chapter_id == chapter.id,
        ChapterVersion.version_type == "FINAL"
    )
    res_ver = await session.execute(stmt_ver)
    ver_final = res_ver.scalar_one_or_none()

    if ver_final:
        if ver_final.file_path and os.path.exists(ver_final.file_path) and os.path.getsize(ver_final.file_path) > 0:
            try:
                txt = read_version_file_content(ver_final.file_path)
                if txt and txt.strip():
                    return txt
            except Exception:
                pass
        if ver_final.content and ver_final.content.strip():
            return ver_final.content

    return None


async def tts_chapter_worker(
    queue: asyncio.Queue,
    voice: str,
    novel_folder: str,
    chapters_cache_dir: str,
    job_info: Dict[str, Any],
    session_factory,
    tts_rate: str = "-4%",
    tts_pitch: str = "+0Hz",
    proxy_list: Optional[List[str]] = None,
    silence_sec: float = 0.25
):
    """
    Worker xử lý TTS từng CHƯƠNG với tốc độ siêu nhanh (song song nhiều sub-chunks).
    """
    import tempfile, shutil

    while True:
        try:
            item = await queue.get()
        except asyncio.CancelledError:
            break

        if item is None:
            queue.task_done()
            break

        chapter_no, text = item
        success = False
        chapter_mp3 = _get_chapter_cache_path(chapters_cache_dir, chapter_no)

        # Làm sạch HTML/thẻ tag và chuẩn hóa văn bản trước khi đưa vào Edge-TTS
        clean_text = sanitize_tts_text(text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # Chia text thành sub-chunks 2000 ký tự từ văn bản đã được làm sạch
        sub_chunks = split_text_into_chunks(clean_text, max_chars=2000)
        if not sub_chunks:
            queue.task_done()
            continue

        # Tạo thư mục temp riêng cho chương này
        tmp_dir = os.path.join(chapters_cache_dir, f"_tmp_ch{chapter_no:06d}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        async def _download_subchunk(sub_idx: int, chunk_text: str) -> Optional[str]:
            sub_path = os.path.join(tmp_dir, f"sub_{sub_idx:04d}.mp3")
            sub_wav_path = os.path.join(tmp_dir, f"sub_{sub_idx:04d}.wav")
            
            # 1. Ưu tiên sử dụng Giọng đọc Hoài My (Edge-TTS) chuẩn Studio cao cấp
            for attempt in range(2):
                async with TTS_CONCURRENCY_SEMAPHORE:
                    try:
                        await asyncio.sleep(random.uniform(0.0, 0.05))
                        proxy_url = random.choice(proxy_list) if (proxy_list and len(proxy_list) > 0) else None
                        
                        communicate_kwargs = {
                            "text": chunk_text,
                            "voice": voice,
                            "rate": tts_rate,
                            "pitch": tts_pitch
                        }
                        if proxy_url:
                            communicate_kwargs["proxy"] = proxy_url

                        communicate = edge_tts.Communicate(**communicate_kwargs)
                        await asyncio.wait_for(communicate.save(sub_path), timeout=15.0)
                        if os.path.exists(sub_path) and os.path.getsize(sub_path) > 0:
                            _CONSECUTIVE_FAILURES["count"] = 0
                            return sub_path
                        if os.path.exists(sub_path) and os.path.getsize(sub_path) == 0:
                            try: os.remove(sub_path)
                            except Exception: pass
                    except Exception:
                        if os.path.exists(sub_path) and os.path.getsize(sub_path) == 0:
                            try: os.remove(sub_path)
                            except Exception: pass
                        # Áp dụng ngắt âm nhẹ để Hoài My đọc chuẩn 100% từ ngữ 18+ mà Microsoft không chặn
                        try:
                            camou_text = re.sub(r'(?i)\blồn\b', 'l-ồn', chunk_text)
                            camou_text = re.sub(r'(?i)\bcặc\b', 'c-ặc', camou_text)
                            camou_text = re.sub(r'(?i)\bbuồi\b', 'b-uồi', camou_text)
                            camou_text = re.sub(r'(?i)\bđịt\b', 'đ-ịt', camou_text)
                            camou_text = re.sub(r'(?i)\bchịch\b', 'ch-ịch', camou_text)
                            com_camou = edge_tts.Communicate(camou_text, voice, rate=tts_rate, pitch=tts_pitch)
                            await asyncio.wait_for(com_camou.save(sub_path), timeout=15.0)
                            if os.path.exists(sub_path) and os.path.getsize(sub_path) > 0:
                                _CONSECUTIVE_FAILURES["count"] = 0
                                return sub_path
                            if os.path.exists(sub_path) and os.path.getsize(sub_path) == 0:
                                try: os.remove(sub_path)
                                except Exception: pass
                        except Exception:
                            if os.path.exists(sub_path) and os.path.getsize(sub_path) == 0:
                                try: os.remove(sub_path)
                                except Exception: pass
                        _CONSECUTIVE_FAILURES["count"] += 1
                        await asyncio.sleep(0.05)

            # 2. Fallback sang Động cơ Offline Piper nếu mạng bị ngắt
            if is_piper_available():
                try:
                    piper_ok = await synthesize_text_piper_async(chunk_text, sub_wav_path)
                    if piper_ok and os.path.exists(sub_wav_path) and os.path.getsize(sub_wav_path) > 0:
                        cmd_ffmpeg = [get_ffmpeg_cmd(), "-y", "-i", sub_wav_path, "-ar", "44100", "-ac", "2", "-b:a", "192k", sub_path]
                        proc_conv = subprocess.run(cmd_ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if proc_conv.returncode == 0 and os.path.exists(sub_path) and os.path.getsize(sub_path) > 0:
                            try: os.remove(sub_wav_path)
                            except Exception: pass
                            _CONSECUTIVE_FAILURES["count"] = 0
                            return sub_path
                except Exception as ex_piper:
                    print(f"[PIPER-FALLBACK] Lỗi Piper: {ex_piper}")

            return None

        # Tải tất cả sub-chunk của chương song song (tuân thủ Concurrency Semaphore)
        valid_chunks = [
            (idx, c.strip()) for idx, c in enumerate(sub_chunks)
            if c and c.strip() and re.search(r'\w', c)
        ]
        
        if valid_chunks:
            download_tasks = [_download_subchunk(idx, ctext) for idx, ctext in valid_chunks]
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            
            sub_mp3s = []
            for r in results:
                if isinstance(r, str) and r and os.path.exists(r) and os.path.getsize(r) > 0:
                    sub_mp3s.append(r)
            
            # Chỉ cần có các phần sub_mp3s hợp lệ là tiến hành ghép nối chương ngay
            if sub_mp3s:
                if len(sub_mp3s) == 1:
                    try:
                        if os.path.exists(chapter_mp3):
                            os.remove(chapter_mp3)
                        shutil.copyfile(sub_mp3s[0], chapter_mp3)
                        success = os.path.exists(chapter_mp3) and os.path.getsize(chapter_mp3) > 0
                    except Exception as e:
                        success = merge_audio_files(sub_mp3s, chapter_mp3, add_silence_sec=0.0)
                else:
                    success = merge_audio_files(sub_mp3s, chapter_mp3, add_silence_sec=0.0)

        # Dọn dẹp temp
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        if success:
            job_info["done_chapters"] += 1
            job_info["recent_successes"] += 1
            print(f"✅ [TTS-CH] Chương {chapter_no} → {os.path.basename(chapter_mp3)}", flush=True)
        else:
            job_info["failed_chapters"] += 1
            job_info["recent_failures"] += 1
            print(f"❌ [TTS-CH] Chương {chapter_no} thất bại sau 5 lần thử.", flush=True)

        queue.task_done()


def generate_range_mp3(
    chapters_cache_dir: str,
    chapter_nos: List[int],
    output_path: str,
    silence_sec: float = 0.25
) -> bool:
    """
    Tạo file mp3 khoảng (Range) bằng FFmpeg concat từ các chapter-cache mp3.
    Trả về True nếu thành công.
    """
    files = [_get_chapter_cache_path(chapters_cache_dir, c) for c in chapter_nos]
    # Lọc bỏ file không tồn tại hoặc rỗng
    files = [f for f in files if os.path.exists(f) and os.path.getsize(f) > 0]
    if not files:
        return False
    return merge_audio_files(files, output_path, add_silence_sec=silence_sec)


def normalize_final_audio(input_path: str, output_path: str) -> bool:
    """
    Bảo toàn 100% độ thoáng và chi tiết tự nhiên nguyên bản của giọng đọc Neural.
    Loại bỏ bộ lọc acompressor/loudnorm nén đè gây méo tiếng/ồm giọng/chói tai.
    """
    try:
        if os.path.abspath(input_path) == os.path.abspath(output_path):
            return os.path.exists(input_path) and os.path.getsize(input_path) > 0
        import shutil
        shutil.copyfile(input_path, output_path)
        return True
    except Exception as e:
        print(f"[TTS-NORMALIZE] Lỗi xử lý tệp âm thanh: {e}")
        return False


async def run_tts_volume_pipeline(
    novel_id: int,
    volume_no: int,
    chapters_per_volume: int,
    voice_profile: str = "default"
):
    """
    Pipeline TTS per-chapter cache hoàn chỉnh:
    1. Xác định danh sách chương cần xử lý
    2. Quét chapter-cache mp3 → chỉ TTS chương chưa có
    3. Worker pool TTS song song
    4. FFmpeg concat tất cả chapter mp3 → file output cuối
    """
    from sqlalchemy import delete

    job_key = f"{novel_id}_{volume_no}"
    job_info = ACTIVE_TTS_JOBS[job_key]

    # ── 1. Lấy thông tin truyện & chương ──────────────────────────────────────
    async with AsyncSessionLocal() as session:
        novel = (await session.execute(select(Novel).where(Novel.id == novel_id))).scalar_one_or_none()

    if not novel:
        job_info["status"] = "failed"
        job_info["status_msg"] = "❌ Không tìm thấy truyện trong CSDL."
        job_info["is_running"] = False
        return

    novel_folder = sanitize_filename(novel.title_rough if novel.title_rough else novel.title_raw)
    out_dir = os.path.join(BASE_AUDIO_DIR, novel_folder)
    chapters_cache_dir = os.path.join(out_dir, "chapters")
    os.makedirs(chapters_cache_dir, exist_ok=True)

    # Tự động quét và dọn sạch các thư mục tạm _tmp_ch* còn sót lại từ các lần chạy trước bị hủy/ngắt
    if os.path.exists(chapters_cache_dir):
        for f in os.listdir(chapters_cache_dir):
            if f.startswith("_tmp_ch"):
                shutil.rmtree(os.path.join(chapters_cache_dir, f), ignore_errors=True)

    # ── 2. Xác định khoảng chương ────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        all_chapters = (await session.execute(
            select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no)
        )).scalars().all()

    if volume_no >= 1000000:
        rem = volume_no - 1000000
        start_ch = rem // 10000
        end_ch = rem % 10000
        volume_chapters = [ch for ch in all_chapters if start_ch <= ch.chapter_no <= end_ch]
        final_name = f"{novel_folder}_Ch{start_ch}_to_Ch{end_ch}.mp3"
    else:
        start_idx = (volume_no - 1) * chapters_per_volume
        end_idx = min(start_idx + chapters_per_volume, len(all_chapters))
        volume_chapters = all_chapters[start_idx:end_idx]
        final_name = f"{novel_folder}_Vol{volume_no:03d}.mp3"

    if not volume_chapters:
        err = "⚠️ Không tìm thấy chương nào hợp lệ trong khoảng đã chọn."
        print(f"[TTS-ERROR] {err}")
        job_info["status"] = "failed"
        job_info["status_msg"] = err
        job_info["is_running"] = False
        return

    chapter_nos = [ch.chapter_no for ch in volume_chapters]
    total_chapters = len(chapter_nos)
    job_info["total_chapters"] = total_chapters
    job_info["total_chunks"] = total_chapters  # backward-compat cho UI

    # ── 3. Quét chapter-cache: tìm chương nào chưa có mp3 ────────────────────
    need_tts = []
    need_text = {}  # chapter_no → text

    async with AsyncSessionLocal() as session:
        for ch in volume_chapters:
            if _is_chapter_cached(chapters_cache_dir, ch.chapter_no, novel_folder=novel_folder):
                continue  # Đã có cache và mới hơn văn bản dịch → bỏ qua
            # Đọc text ngay để tránh mở nhiều DB session sau
            txt = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, ch)
            if txt:
                clean = sanitize_tts_text(txt)
                if clean and clean.strip():
                    # Lưu văn bản đã qua tiền xử lý chuẩn vào 04b_VanBanTTS
                    try:
                        save_tts_text_file(novel_folder, ch.chapter_no, clean)
                    except Exception as e_save:
                        print(f"⚠️ Không thể lưu tệp 04b_VanBanTTS ch{ch.chapter_no}: {e_save}")
                    need_tts.append(ch.chapter_no)
                    need_text[ch.chapter_no] = clean

    cached_count = total_chapters - len(need_tts)
    print(
        f"🔊 [TTS-START] Truyện '{novel_folder}' | Tập {volume_no} | "
        f"{total_chapters} chương | Đã cache: {cached_count} | Cần TTS: {len(need_tts)}",
        flush=True
    )

    job_info["done_chapters"] = cached_count
    job_info["done_chunks"] = cached_count  # backward-compat
    job_info["failed_chapters"] = 0
    job_info["failed_chunks"] = 0
    job_info["recent_successes"] = 0
    job_info["recent_failures"] = 0

    # ── 4. Nếu tất cả đã cache → skip TTS, chỉ FFmpeg ───────────────────────
    voice = get_voice_name(voice_profile)
    workers = []
    start_time = time.time()

    if need_tts:
        # Nạp các cấu hình TTS động từ DB / .env
        tts_workers_str = await get_active_setting("TTS_MAX_WORKERS")
        tts_rate = await get_active_setting("TTS_RATE") or "-4%"
        tts_pitch = await get_active_setting("TTS_PITCH") or "+0Hz"
        silence_ms_str = await get_active_setting("TTS_SILENCE_MS")
        proxy_list_str = await get_active_setting("TTS_PROXY_LIST")
        
        try:
            num_workers = min(int(tts_workers_str), 6) if (tts_workers_str and tts_workers_str.strip()) else 6
            if num_workers < 1:
                num_workers = 6
        except Exception:
            num_workers = 6

        try:
            silence_sec = max(0.0, float(silence_ms_str) / 1000.0) if silence_ms_str else 0.25
        except Exception:
            silence_sec = 0.25

        proxy_list = [p.strip() for p in proxy_list_str.split(",") if p.strip()] if proxy_list_str else None

        job_info["worker_count"] = num_workers

        queue = asyncio.Queue()
        for ch_no in need_tts:
            await queue.put((ch_no, need_text[ch_no]))

        try:
            for _ in range(num_workers):
                t = asyncio.create_task(
                    tts_chapter_worker(
                        queue, voice, novel_folder, chapters_cache_dir, job_info, AsyncSessionLocal,
                        tts_rate=tts_rate, tts_pitch=tts_pitch, proxy_list=proxy_list, silence_sec=silence_sec
                    )
                )
                workers.append(t)
                await asyncio.sleep(0.2)

            # Vòng giám sát tiến độ
            while True:
                await asyncio.sleep(2)
                job_info["ram_usage_percent"] = psutil.virtual_memory().percent
                elapsed = time.time() - start_time
                done = job_info["done_chapters"]
                failed = job_info.get("failed_chapters", 0)

                if done > cached_count and elapsed > 0:
                    speed = ((done - cached_count) / elapsed) * 60
                    job_info["speed_chunks_per_min"] = round(speed, 2)
                    job_info["eta_seconds"] = int((total_chapters - done) / (speed / 60)) if speed > 0 else 0
                    job_info["percent"] = round((done / total_chapters) * 100, 1)
                    job_info["done_chunks"] = done  # backward-compat

                if (done + failed) >= total_chapters or (queue.empty() and done >= cached_count + len(need_tts) - failed):
                    print(f"🎉 [TTS-MONITOR] Đã hoàn thành {done}/{total_chapters} chương.", flush=True)
                    break

            # Dừng tất cả worker
            for _ in range(num_workers):
                await queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)

        except asyncio.CancelledError:
            print(f"[TTS-PIPELINE] Job {job_key} bị hủy bởi người dùng.")
            for w in workers:
                if not w.done():
                    w.cancel()
            
            # Gộp ngay tất cả các chương đã làm xong cache cho tới thời điểm ngắt
            try:
                cached_files = [c for c in chapter_nos if _is_chapter_cached(chapters_cache_dir, c, novel_folder=novel_folder)]
                if cached_files:
                    partial_final_name = f"{novel_folder}_Ch{cached_files[0]}_to_Ch{cached_files[-1]}.mp3"
                    partial_final_path = os.path.join(out_dir, partial_final_name)
                    generate_range_mp3(chapters_cache_dir, cached_files, partial_final_path)
                    print(f"🎬 [TTS-CANCEL-MERGE] Đã tự động gộp {len(cached_files)} chương đã tạo thành {partial_final_name}", flush=True)
            except Exception as ex_merge:
                print(f"[TTS-CANCEL-MERGE-ERROR] {ex_merge}")

            job_info["status"] = "cancelled"
            job_info["is_running"] = False
            return

        except Exception as e:
            print(f"[TTS-PIPELINE ERROR] {e}")
            for w in workers:
                if not w.done():
                    w.cancel()
            job_info["status"] = "failed"
            job_info["is_running"] = False
            raise e
    else:
        job_info["worker_count"] = 0
        job_info["percent"] = 100.0
        print(f"⚡ [TTS-FAST] Tất cả {total_chapters} chương đã có cache. Chuyển thẳng FFmpeg...", flush=True)

    # ── 5. FFmpeg concat tất cả chapter mp3 → output cuối ────────────────────
    final_path = os.path.join(out_dir, final_name)
    job_info["status_msg"] = f"🎬 Đang ghép nối {total_chapters} chương → FFmpeg..."
    print(f"[TTS-MERGE] Bắt đầu FFmpeg concat {total_chapters} chapter mp3...", flush=True)

    success_merge = generate_range_mp3(chapters_cache_dir, chapter_nos, final_path)

    if success_merge:
        # Chuẩn hóa âm lượng + giảm chói/vỡ tiếng trên file cuối
        normalized_path = final_path.replace(".mp3", "_norm.mp3")
        if normalize_final_audio(final_path, normalized_path):
            try:
                os.replace(normalized_path, final_path)
            except Exception:
                pass
        job_info["status"] = "completed"
        job_info["percent"] = 100.0
        job_info["done_chunks"] = total_chapters
        job_info["status_msg"] = f"✅ Hoàn tất! Đã lưu tại {final_name}"
        print(f"🎉 [TTS-DONE] Audiobook lưu tại: {final_path}", flush=True)
    else:
        job_info["status"] = "failed"
        job_info["status_msg"] = "❌ FFmpeg ghép nối thất bại."
        print(f"❌ [TTS-MERGE-FAIL] Không thể ghép nối file cuối.", flush=True)

    job_info["is_running"] = False


async def cleanup_tts_volume(novel_id: int, volume_no: int, temp_dir: str = ""):
    """Dọn dẹp DB khi cần reset (legacy compat - chapter cache không có temp dir)"""
    from sqlalchemy import delete
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                delete(TTSChunk).where(TTSChunk.novel_id == novel_id, TTSChunk.volume_no == volume_no)
            )
            await session.commit()
        except Exception as e:
            print(f"[TTS-CLEANUP] Loi: {e}")


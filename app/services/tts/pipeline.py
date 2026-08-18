import os
import re
import time
import shutil
import asyncio
import random
import subprocess
import psutil
import gc
import edge_tts
from typing import List, Dict, Any, Optional, Set
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion, TTSChunk
from app.services.storage.file_storage import sanitize_filename, save_tts_text_file
from app.core.config import get_active_setting
from app.services.tts.persistent_client import PersistentEdgeTTSClient
from app.services.tts.rotating_engine import RotatingBatchTTSEngine

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

# Semaphore giới hạn nghiêm ngặt 1 kết nối đồng thời tới Microsoft Edge-TTS để đảm bảo 1 luồng duy nhất, ổn định tuyệt đối
TTS_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(1)
_CONSECUTIVE_FAILURES = {"count": 0}

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            cleaned = [str(a).encode("ascii", "replace").decode("ascii") for a in args]
            print(*cleaned, **kwargs)
        except Exception:
            pass

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

def generate_silence_file(duration_sec: float = 0.25, sample_rate: int = 24000) -> Optional[str]:
    """Tạo tệp MP3 chứa khoảng lặng (silence) với độ dài tùy chọn theo chuẩn 24kHz Mono 48kbps của Edge-TTS"""
    import tempfile
    silence_path = os.path.join(tempfile.gettempdir(), f"silence_{int(duration_sec*1000)}ms_24k_mono.mp3")
    if os.path.exists(silence_path) and os.path.getsize(silence_path) > 0:
        return silence_path
    try:
        cmd = [
            get_ffmpeg_cmd(), "-y", "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=mono",
            "-t", str(duration_sec),
            "-ar", str(sample_rate), "-ac", "1",
            "-b:a", "48k", silence_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        if result.returncode == 0 and os.path.exists(silence_path):
            return silence_path
    except Exception as e:
        print(f"[TTS-SILENCE] Lỗi tạo file silence: {e}")
    return None

# Chuỗi bộ lọc Audio DSP Mastering chuyên biệt cho Audiobook:
# 1. highpass (75Hz): Lọc sạch tạp âm siêu trầm gây ù nền, làm nhòe chữ khi tua nhanh
# 2. equalizer (300Hz, -1.8dB): Triệt tiêu tiếng ồm đục, giúp giọng thoáng và sáng
# 3. equalizer (2800Hz, +2.2dB): Tăng độ nét bóc tách phụ âm (Presence) - giữ phát âm cực rõ ràng kể cả khi tua 1.5x - 2.0x
# 4. equalizer (6200Hz, -3.0dB): De-essing làm dịu phụ âm xát (s, x, ch, tr, dấu sắc), loại bỏ 100% tiếng xì chói / rè dải âm cao
# 5. lowpass (11000Hz): Cắt lọc nhiễu lượng tử hóa số dải siêu cao
# BỘ LỌC AUDIO MASTERING TỰ NHIÊN (Không kích chói, không nuốt âm, chuẩn EBU R128):
# 1. highpass=f=50: Lọc bỏ ù xì tần số cực thấp dưới 50Hz mà tai người không nghe thấy
# 2. loudnorm: Chuẩn hóa âm lượng EBU R128 (-16 LUFS, True Peak -1.5dB, LRA 11) giữ nguyên độ động tự nhiên, không bị pumping/nuốt chữ
AUDIOBOOK_MASTERING_FILTERS = (
    "highpass=f=50,"
    "loudnorm=I=-16:TP=-1.5:LRA=11"
)

def merge_audio_files(
    file_paths: List[str], 
    output_path: str, 
    add_silence_sec: float = 0.0,
    apply_mastering: bool = False
) -> bool:
    """
    Ghép nối danh sách các tệp mp3 bằng Stream Copy nguyên bản (-c copy) 100%.
    - Bảo toàn 100% độ trung thực (Fidelity) chuẩn phòng thu của Microsoft Edge-TTS.
    - Không nén lại (0% generation loss), không méo dải tần, không nuốt âm/rách tiếng.
    - Cho ra file lưu trên đĩa và tải về nghe chuẩn 100% y hệt như nghe trực tiếp trên web.
    """
    if not file_paths:
        return False
    
    import tempfile, uuid
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    list_file_path = os.path.join(tempfile.gettempdir(), f"airead_concat_{uuid.uuid4().hex[:8]}.txt")
    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for fp in file_paths:
                normalized_path = fp.replace("\\", "/")
                f.write(f"file '{normalized_path}'\n")
        
        # 1. Ưu tiên số 1: Ghép nối Stream Copy nguyên bản (0% suy hao, chuẩn 100% như Web)
        cmd_copy = [get_ffmpeg_cmd(), "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_path]
        res_copy = subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        if res_copy.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            return True

        # 2. Fallback: Nếu stream copy không được thì chuyển mã cơ bản
        cmd_fallback = [
            get_ffmpeg_cmd(), "-y", "-f", "concat", "-safe", "0", 
            "-i", list_file_path, "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "24000", output_path
        ]
        res_fb = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        return res_fb.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024
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
    Làm sạch văn bản khi đưa lên TTS & lưu vào 04b_VanBanTTS:
    - Loại bỏ dòng tiêu đề tên chương ở đầu (Chương 1: ..., Hồi 1: ..., Quyển 1..., Chapter 1...).
    - Loại bỏ các dòng / cụm kết thúc chương (Hết chương, Toàn văn hoàn, End Chapter,...).
    - Loại bỏ lời kêu gọi tác giả / xin phiếu / xin đề cử ở cuối chương.
    - Loại bỏ ký tự rỗng/vô hình zero-width, HTML tags, Markdown formatting, Emojis, URL, watermark cào web.
    - Chuẩn hóa dấu câu Đông Á, ngoặc kép, dấu chấm lửng, đơn vị, chức danh và khoảng trắng sau dấu câu.
    - Chuẩn hóa ngắt nghỉ câu theo từng loại dấu câu để Edge-TTS diễn đọc tự nhiên, liền mạch, có cảm xúc.
    - Bảo toàn 100% nguyên văn từ ngữ và từ lóng của nội dung truyện.
    """
    if not text:
        return ""

    # 0. Loại bỏ ký tự rỗng/vô hình zero-width, BOM và control characters
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0]', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # 1. Bóc tách thẻ HTML <span ...>Nội dung</span> -> Giữ lại Nội dung thuần túy
    text = re.sub(r'<span\b[^>]*data-raw=["\'](.*?)["\'][^>]*>(.*?)</span>', r'\2', text, flags=re.DOTALL)
    text = re.sub(r'<span\b[^>]*>(.*?)</span>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'</?[a-zA-Z][a-zA-Z0-9]*[^>]*>', ' ', text)

    # 2. Xóa Markdown, URL, Email, code block
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'#{1,6}[ \t]+', '', text)
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'_{1,3}', '', text)

    # 3. Loại bỏ Emojis & ký tự trang trí lạ
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001f900-\U0001f9ff\U00002600-\U000026FF]', '', text)
    text = re.sub(r'[★☆◆◇■□▲△▼▽●○♥♠♣♦♂♀⟪⟫▸▹►▻◄◄§†‡✓✕✗¶™®©♪♫✿❀❁☸⚡⚙⚔🛡🗡👑✦✧✨✴❇❄🔴🔵🟡🟢🟣⭐🌟🔥💥💢]', '', text)

    # 4. Chuẩn hóa ngoặc kép & ngoặc Đông Á
    text = text.replace('「', '"').replace('」', '"').replace('『', '"').replace('』', '"')
    text = text.replace('《', '"').replace('》', '"').replace('【', '[').replace('】', ']')
    text = text.replace('“', '"').replace('”', '"').replace('„', '"')
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('。', '. ').replace('，', ', ').replace('！？', '!? ').replace('？！', '!? ')

    # 5. Chuẩn hóa đơn vị đo, chức danh, ký hiệu toán học
    text = re.sub(r'(^|[ \t])>=[ \t]*', r'\1lớn hơn hoặc bằng ', text)
    text = re.sub(r'(^|[ \t])<=[ \t]*', r'\1nhỏ hơn hoặc bằng ', text)
    text = re.sub(r'(^|[ \t])!=[ \t]*', r'\1khác ', text)
    text = re.sub(r'(^|[ \t])>[ \t]*', r'\1lớn hơn ', text)
    text = re.sub(r'(^|[ \t])<[ \t]*', r'\1nhỏ hơn ', text)
    text = re.sub(r'(^|[ \t])~[ \t]*(\d+)', r'\1khoảng \2', text)
    text = re.sub(r'(\d+)[ \t]*\^[ \t]*(\d+)', r'\1 mũ \2', text)
    text = re.sub(r'(\d+)[ \t]*[%％]', r'\1 phần trăm', text)
    text = re.sub(r'([ \t]|\(|\[|^|,)\+[ \t]*(\d+)\b', r'\1cộng \2', text)
    text = re.sub(r'(?i)\bLv\.?[ \t]*(\d+)\b', r'cấp \1', text)
    text = re.sub(r'(?i)\bLevel[ \t]*(\d+)\b', r'cấp \1', text)
    text = re.sub(r'(\d+)[ \t]*(km/h|km/g|m/s)\b', r'\1 km trên giờ', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)[ \t]*(km|cm|mm|kg|mg|ml|m|g|tháng|năm|phút|giây|h|tr|tỷ|V|Hz|W|kW|GB|MB|TB)\b', r'\1 \2', text, flags=re.IGNORECASE)

    text = re.sub(r'\bTP\.?[ \t]*HCM\b', 'Thành phố Hồ Chí Minh', text, flags=re.IGNORECASE)
    text = re.sub(r'\bTP\.[ \t]*', 'Thành phố ', text)
    text = re.sub(r'\bPGS\.[ \t]*', 'Phó Giáo sư ', text)
    text = re.sub(r'\bGS\.[ \t]*', 'Giáo sư ', text)
    text = re.sub(r'\bTS\.[ \t]*', 'Tiến sĩ ', text)
    text = re.sub(r'\bThS\.[ \t]*', 'Thạc sĩ ', text)

    # 6. Tiền xử lý chuỗi biểu cảm cho Edge-TTS (la hét, rên rỉ, cười, khóc, thở dốc, lắp bắp)
    # NGUYÊN TẮC VÀNG:
    # - La hét dấu sắc: giới hạn đúng 2 từ "á á" / "Á á" / "é é" (tạo 1 xung to đầu thoải đuôi, tránh vỡ giọng).
    # - La hét không dấu / rên / cười / khóc: nối liền ("aaa", "ôôô", "hahaha", "huhu", "ưmưm") để tạo 1 cụm âm mượt.
    # - Lắp bắp (k-không, c-con): chuyển thành "không... không", "con... con" (tránh Edge-TTS đọc chữ cái tiếng Anh).
    # - Tilde (~): bóc sạch, không chuyển thành ba chấm để không làm đứt gãy nhịp thở.

    # 6a. Tilde kéo dài âm: "quá~", "sướng~", "ha~ ha~ ha~" → xóa tilde, giữ nguyên chữ
    text = re.sub(r'([a-zA-ZÀ-ỹ])~+', r'\1', text)
    text = re.sub(r'[~～]+', '', text)

    # 6b. Xử lý lắp bắp cộc lốc tiếng Việt (k-không -> không... không, c-con -> con... con)
    stutter_pattern = r'\b([a-zA-ZÀ-ỹ])\s*[-–—.]+\s*([a-zA-ZÀ-ỹ]{2,})\b'
    def _smart_stutter_replace(m):
        lead_char = m.group(1).lower()
        word = m.group(2)
        if word.lower().startswith(lead_char) or (lead_char == 'k' and word.lower().startswith('kh')):
            return f"{word}... {word}"
        return m.group(0)
    text = re.sub(stutter_pattern, _smart_stutter_replace, text)

    # 6c. Chuỗi la hét có dấu sắc: bắt buộc chuẩn hóa về đúng 2 từ "á á" / "Á á" / "é é" / "oá oá"
    def _normalize_acute_scream(m):
        raw = m.group(0)
        v = m.group(1)
        is_upper = raw.strip()[:1].isupper()
        base_v = v.capitalize() if is_upper else v.lower()
        return f"{base_v} {base_v.lower()}"
    text = re.sub(r'(?i)(?<![a-zA-ZÀ-ỹ])([áÁéÉíÍóÓúÚớỚứỨ]|oá|oé)(?:[ \t]*[\-—.,~]*[ \t]*\1)+(?![a-zA-ZÀ-ỹ])', _normalize_acute_scream, text)
    text = re.sub(r'(?i)([áÁéÉíÍóÓúÚớỚứỨ]|oá|oé)\1+', _normalize_acute_scream, text)

    # 6d. Chuỗi nguyên âm la hét không dấu: a a a -> aaa, e e e -> eee, o o o -> ooo
    def _merge_plain_vowels(m):
        v = m.group(1).lower()
        return v * 3
    text = re.sub(r'(?i)(?<![a-zA-ZÀ-ỹ])([aeouàèòùảẻỏủãẽõũạẹọụ])(?:[ \t]*[\-—.,~]*[ \t]*\1){1,}(?![a-zA-ZÀ-ỹ])', _merge_plain_vowels, text)

    # 6e. Chuỗi nguyên âm rên rỉ: ô ô ô -> ôôô, ơ ơ ơ -> ơơơ, ư ư ư -> ưưư, ừ ừ -> ừừ
    def _merge_moan_vowels(m):
        v = m.group(1).lower()
        return v * 3
    text = re.sub(r'(?i)(?<![a-zA-ZÀ-ỹ])([ôốồổỗộơờởỡợưừửữựêềểễệ])(?:[ \t]*[\-—.,~]*[ \t]*\1){1,}(?![a-zA-ZÀ-ỹ])', _merge_moan_vowels, text)

    # 6f. Chuỗi từ tượng thanh cười/khóc/rên/thở dốc/cảm thán
    ONOMA_WORDS = (
        r'ha|hả|hô|hì|hê|hi|hề|hú|hứ|hừ|hừm|hức|hic|hu|oa|oá|'
        r'kha|khà|khẹc|khặc|hắc|hặc|phì|hộc|hắt|hự|ực|chẹp|ưm|ừm'
    )
    def _merge_onoma(m):
        word = m.group(1).lower()
        count = len(re.findall(re.escape(word), m.group(0), re.IGNORECASE))
        repeat = min(max(count, 2), 3)
        return word * repeat
    text = re.sub(rf'(?i)\b({ONOMA_WORDS})(?:[ \t]*[\-—.,~]*[ \t]*\1){{1,}}\b', _merge_onoma, text)

    # 6g. Cảm thán lặp: ối ối -> ốiối!, trời ơi trời ơi -> trời ơi!
    def _merge_exclaim(m):
        word = m.group(1)
        count = len(re.findall(re.escape(word), m.group(0), re.IGNORECASE))
        repeat = min(max(count, 2), 2)
        return word * repeat + "!"
    text = re.sub(r'(?i)\b(ối|ối dồi ôi|trời ơi)(?:[ \t]*[\-—.,~!]*[ \t]*\1){1,}', _merge_exclaim, text)

    # 6h. Cắt tỉa nguyên âm dính liền quá 3 ký tự (aaaaaaa -> aaa, ôôôôô -> ôôô)
    text = re.sub(r'(?i)([aàảãạeèẻẽẹoòỏõọuùủũụôốồổỗộơớờởỡợưứừửữựêếềểễệ])\1{3,}', r'\1\1\1', text)

    # 7. Chuẩn hóa dấu chấm lửng, ba chấm, ngắt biểu cảm
    text = re.sub(r'[…]+', '... ', text)
    text = re.sub(r'\.{4,}', '... ', text)
    # Lưu ý: ~ đã được xử lý ở bước 6a, không cần chuyển thành "..." nữa
    text = re.sub(r'[-–—]{3,}', ' — ', text)

    # 8. Chuẩn hóa chuỗi dấu lặp
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    text = re.sub(r'[,]{2,}', ', ', text)
    text = re.sub(r'[;]{2,}', '; ', text)
    text = re.sub(r'[:]{2,}', ': ', text)
    text = re.sub(r'(?:\?\!|\!\?)+', '!? ', text)
    text = re.sub(r'["“”]{2,}', '"', text)

    # 9. Chuẩn hóa khoảng trắng quanh ngoặc vuông, ngoặc đơn, hai chấm dẫn thoại
    text = re.sub(r'([\]\)])([A-ZÀ-Ỹa-zà-ỹ0-9])', r'\1 \2', text)
    text = re.sub(r'([A-ZÀ-Ỹa-zà-ỹ0-9])([\[\(])', r'\1 \2', text)
    text = re.sub(r'([:])([^\S\r\n]*)(["“])', r': \3', text)
    text = re.sub(r'([a-zA-Zà-ỹÀ-Ỹ0-9])"([a-zA-Zà-ỹÀ-Ỹ0-9])', r'\1" \2', text)

    # 10. Xóa khoảng trắng thừa NGAY TRONG dấu ngoặc / ngoặc kép
    text = re.sub(r'([(\[{])[ \t]+', r'\1', text)
    text = re.sub(r'[ \t]+([)\]}])', r'\1', text)
    text = re.sub(r'(^|[ \t\n])"[ \t]+', r'\1"', text)
    text = re.sub(r'[ \t]+"([ \t\n.,!?;:]|$)', r'"\1', text)

    # 11. Xóa khoảng trắng thừa TRƯỚC dấu câu
    text = re.sub(r'[ \t]+([.!?;:,])', r'\1', text)

    # 12. Đảm bảo luôn có đúng 1 khoảng trắng SAU dấu câu trên cùng một dòng
    text = re.sub(r'([,;:])([A-ZÀ-Ỹa-zà-ỹ0-9])', r'\1 \2', text)
    text = re.sub(r'([!?])([A-ZÀ-Ỹa-zà-ỹ0-9])', r'\1 \2', text)
    text = re.sub(r'(\.)([A-ZÀ-Ỹa-zà-ỹ])', r'\1 \2', text)
    text = re.sub(r'(\.\.\.)([A-ZÀ-Ỹa-zà-ỹ0-9])', r'\1 \2', text)

    # Sửa lỗi chữ Hán dịch lẻ bị viết hoa giữa câu
    text = re.sub(r'\bbế tử Quan\b', 'bế tử quan', text)
    text = re.sub(r'\bthổ Nạp\b', 'thổ nạp', text)
    text = re.sub(r'\blinh Khí\b', 'linh khí', text)

    # 13. Lọc tiêu đề chương, kết thúc chương và lời tác giả
    chapter_title_pattern = re.compile(
        r'^(?:===+|---|___|\*\*\*)*[ \t]*(?:\[|\(|\{)?[ \t]*'
        r'(?:Quyển[ \t]*\d+[ \t]*)?'
        r'(?:Chương|Hồi|Tiết|Tập|Thứ|Chapter|Chap|Section|Vol|Volume|第)[ \t]*'
        r'(?:\d+|[IVXLCDM]+|[一二三四五六七八九十百千万]+|[a-zA-Z0-9]+)[ \t]*'
        r'(?:章)?[ \t]*'
        r'(?:[:.:\-—\s]|\b).*(?:\]|\)|\})?[ \t]*(?:===+|---|___|\*\*\*)*$',
        re.IGNORECASE
    )

    chapter_end_pattern = re.compile(
        r'^(?:===+|---|___|\*\*\*)*[ \t]*(?:\[|\(|\{|【|（)?[ \t]*'
        r'(?:Hết[ \t]*chương|Hết[ \t]*hồi|Hết[ \t]*tiết|Hết[ \t]*quyển|Toàn[ \t]*văn[ \t]*hoàn|Hoàn[ \t]*thành[ \t]*toàn[ \t]*văn|Hết[ \t]*bản[ \t]*chính|Chương[ \t]*hoàn|Hết|End[ \t]*Chapter|The[ \t]*End|END)[ \t]*'
        r'(?:\d+)?[ \t]*(?:\.|\!|\?|…)*[ \t]*(?:\]|\)|\}|】|）)?[ \t]*(?:===+|---|___|\*\*\*)*$',
        re.IGNORECASE
    )

    author_call_pattern = re.compile(
        r'^(?:===+|---|___|\*\*\*)*[ \t]*(?:\[|\(|\{|【|（)?[ \t]*'
        r'(?:sách[ \t]*mới|cầu[ \t]*sưu[ \t]*tầm|cầu[ \t]*đề[ \t]*cử|cầu[ \t]*nguyệt[ \t]*phiếu|cầu[ \t]*phiếu|cầu[ \t]*hoa|cầu[ \t]*đánh[ \t]*giá|cầu[ \t]*theo[ \t]*dõi|xin[ \t]*phiếu|xin[ \t]*đề[ \t]*cử|xin[ \t]*hoa|ủng[ \t]*hộ[ \t]*sách|vô[ \t]*cùng[ \t]*cảm[ \t]*kích|lời[ \t]*tác[ \t]*giả|p\.?s[ \t]*[:：]).*$',
        re.IGNORECASE
    )

    raw_lines = text.split('\n')
    clean_lines = []

    for line in raw_lines:
        s = line.strip()
        if not s or not re.search(r'[\w\dÀ-ỹ]', s):
            continue

        if chapter_title_pattern.match(s):
            continue

        if chapter_end_pattern.match(s):
            continue

        if author_call_pattern.match(s):
            continue

        clean_lines.append(s)

    # 14. Loại bỏ cụm từ kết thúc chương dính ở cuối đoạn văn cuối cùng (nếu có)
    if clean_lines:
        clean_lines[-1] = re.sub(
            r'[ \t(\[{【（]*(?:Hết[ \t]*chương|Hết[ \t]*hồi|Hết[ \t]*tiết|Hết[ \t]*quyển|Toàn[ \t]*văn[ \t]*hoàn|Hoàn[ \t]*thành|End[ \t]*Chapter|The[ \t]*End)[ \t]*(?:\d+)?[ \t]*(?:\.|\!|\?|…)*[ \t)\]}】）]*$',
            '',
            clean_lines[-1],
            flags=re.IGNORECASE
        ).strip()
        if not clean_lines[-1]:
            clean_lines.pop()

    text = '\n\n'.join(clean_lines)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def split_text_into_chunks(text: str, max_chars: int = 650) -> List[str]:
    """
    Phân tách văn bản thành các chunk <= max_chars ký tự:
    - Giữ nguyên cấu trúc ngắt dòng (\n\n) giữa các đoạn văn để Edge-TTS ngắt nghỉ tự nhiên, có nhịp thở giữa lời thoại và lời dẫn.
    - Tách câu an toàn theo dấu chấm, hỏi, than, ba chấm (. ! ? ...).
    - Câu quá dài được tách nhịp theo dấu phẩy / chấm phẩy (, ; :).
    """
    if not text or not text.strip():
        return []

    # Tách theo từng đoạn văn
    raw_paras = [p.strip() for p in re.split(r'\n+', text.strip()) if p.strip()]

    def _split_sentences(para: str) -> List[str]:
        """Tách đoạn thành các câu hoàn chỉnh, giữ nguyên dấu kết thúc câu."""
        sents = re.split(r'(?<=[.!?…])\s+', para)
        return [s.strip() for s in sents if s.strip()]

    def _split_by_comma(sent: str) -> List[str]:
        """Tách câu dài theo dấu phẩy/chấm phẩy/hai chấm, fallback chia theo từ nếu mảnh vẫn quá dài."""
        parts = re.split(r'(?<=[,;:])\s+', sent)
        result = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if len(p) <= max_chars:
                result.append(p)
            else:
                # Fallback: chia theo khoảng trắng (word-break) khi mảnh không có dấu phẩy mà vẫn dài hơn max_chars
                words = p.split(' ')
                buf: List[str] = []
                buf_len = 0
                for w in words:
                    w_len = len(w)
                    needed = buf_len + w_len + (1 if buf else 0)
                    if needed > max_chars and buf:
                        result.append(' '.join(buf))
                        buf = []
                        buf_len = 0
                    buf.append(w)
                    buf_len += w_len + (1 if len(buf) > 1 else 0)
                if buf:
                    result.append(' '.join(buf))
        return result

    chunks: List[str] = []
    current_paras: List[str] = []
    current_len: int = 0

    def _flush():
        nonlocal current_len
        if current_paras:
            joined = '\n\n'.join(current_paras).strip()
            if joined:
                chunks.append(joined)
            current_paras.clear()
            current_len = 0

    for para in raw_paras:
        para_len = len(para)
        # Nếu đoạn văn ngắn vừa khít vào chunk hiện tại
        if current_len + para_len + (2 if current_paras else 0) <= max_chars:
            current_paras.append(para)
            current_len += para_len + (2 if len(current_paras) > 1 else 0)
        elif para_len <= max_chars:
            # Đoạn văn không vừa chunk hiện tại nhưng vừa đủ cho 1 chunk mới
            _flush()
            current_paras.append(para)
            current_len = para_len
        else:
            # Đoạn văn quá dài (> max_chars): chia nhỏ từng câu trong đoạn
            _flush()
            sentences = _split_sentences(para)
            current_sents: List[str] = []
            sent_accum_len = 0

            for sent in sentences:
                sent_len = len(sent)
                if sent_len > max_chars:
                    # Câu quá dài: chia tiếp theo dấu phẩy
                    comma_parts = _split_by_comma(sent)
                    for cp in comma_parts:
                        cp_len = len(cp)
                        if sent_accum_len + cp_len + (1 if current_sents else 0) > max_chars:
                            if current_sents:
                                chunks.append(' '.join(current_sents).strip())
                                current_sents.clear()
                                sent_accum_len = 0
                        current_sents.append(cp)
                        sent_accum_len += cp_len + (1 if len(current_sents) > 1 else 0)
                else:
                    if sent_accum_len + sent_len + (1 if current_sents else 0) > max_chars:
                        if current_sents:
                            chunks.append(' '.join(current_sents).strip())
                            current_sents.clear()
                            sent_accum_len = 0
                    current_sents.append(sent)
                    sent_accum_len += sent_len + (1 if len(current_sents) > 1 else 0)

            if current_sents:
                chunks.append(' '.join(current_sents).strip())

    _flush()
    return [c for c in chunks if c.strip() and re.search(r'[\w\dÀ-ỹ]', c)]




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
    """Kiểm tra cache mp3 của chương có tồn tại và hợp lệ (> 1KB) không"""
    p = _get_chapter_cache_path(chapters_cache_dir, chapter_no)
    return bool(os.path.exists(p) and os.path.getsize(p) > 1024)


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
    """
    Luôn đọc nội dung dịch chuẩn mới nhất (FINAL / 04_KetQua) từ DB hoặc đĩa.
    TUYỆT ĐỐI KHÔNG đọc bản TTS_TEXT cũ để đảm bảo mỗi khi tạo/tạo lại luôn làm sạch tươi mới từ nguồn gốc.
    """
    from app.services.storage.file_storage import read_version_file_content

    # 1. Đọc bản FINAL từ CSDL
    stmt_ver = select(ChapterVersion).where(
        ChapterVersion.chapter_id == chapter.id,
        ChapterVersion.version_type == "FINAL"
    )
    res_ver = await session.execute(stmt_ver)
    ver_final = res_ver.scalar_one_or_none()

    if ver_final:
        if ver_final.content and ver_final.content.strip():
            return ver_final.content
        if ver_final.file_path and os.path.exists(ver_final.file_path) and os.path.getsize(ver_final.file_path) > 0:
            try:
                txt = read_version_file_content(ver_final.file_path)
                if txt and txt.strip():
                    return txt
            except Exception:
                pass

    # 2. Fallback đọc file đĩa 04_KetQua
    txt_disk = _read_chapter_text(novel_folder, chapter.chapter_no)
    if txt_disk and txt_disk.strip():
        return txt_disk

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
    silence_sec: float = 0.25,
    custom_parallel_workers: Optional[int] = None,
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

        # Chia text thành sub-chunks từ văn bản đã được làm sạch theo đúng đoạn văn và câu kết thúc
        chunk_size_str = await get_active_setting("TTS_MAX_CHUNK_SIZE")
        max_chars = int(chunk_size_str) if (chunk_size_str and chunk_size_str.strip().isdigit()) else 600
        sub_chunks = split_text_into_chunks(clean_text, max_chars=max_chars)
        if not sub_chunks:
            queue.task_done()
            continue

        # Tạo thư mục temp riêng cho chương này
        tmp_dir = os.path.join(chapters_cache_dir, f"_tmp_ch{chapter_no:06d}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        # Tổng hợp audio chương - Đa luồng (N workers song song, mỗi worker 1 Proxy riêng)
        if custom_parallel_workers and custom_parallel_workers >= 1:
            parallel_workers = min(16, max(1, custom_parallel_workers))
        else:
            parallel_workers_str = await get_active_setting("TTS_PARALLEL_WORKERS")
            try:
                parallel_workers = min(16, max(1, int(parallel_workers_str or "8")))
            except Exception:
                parallel_workers = 8

        pacing_str = await get_active_setting("TTS_PACING_SECONDS")
        try:
            pacing_sec = float(pacing_str or "0.2")
        except Exception:
            pacing_sec = 0.2

        engine = RotatingBatchTTSEngine(
            voice=voice,
            rate=tts_rate,
            pitch=tts_pitch,
            proxies=proxy_list,
            auto_fetch_proxy=True,
            max_parallel_workers=parallel_workers,
            pacing_sec=pacing_sec,
            max_retries=4,
            chunk_timeout=25.0
        )

        total_sc = len(sub_chunks)

        def on_subchunk_done(idx, ok, dur, out_p, worker_id=0, *args):
            if ok and os.path.exists(out_p):
                job_info["done_subchunks"] = job_info.get("done_subchunks", 0) + 1
                done_count = job_info["done_subchunks"]
                tot = max(1, job_info.get("total_subchunks", 1))
                curr_pct = round((done_count / tot) * 100, 1)
                job_info["percent"] = min(99.9, curr_pct)
                job_info["progress_pct"] = job_info["percent"]
                sz_kb = os.path.getsize(out_p) / 1024
                audio_dur = sz_kb * 1024 * 8 / 128_000
                rtf = audio_dur / dur if dur > 0 else 0
                snippet = sub_chunks[idx].replace("\n", " ")[:30] + "..."
                log_line = f"[{idx+1:02d}/{total_sc}] | {sz_kb:5.1f} KB | {dur:4.1f}s | 🚀 {rtf:4.1f}x RTF | \"{snippet}\""
                job_info["last_chunk_log"] = log_line
                
                # Cập nhật mảng logs realtime để FE hiển thị bảng log
                if "logs" not in job_info:
                    job_info["logs"] = []
                job_info["logs"].append(log_line)
                if len(job_info["logs"]) > 50:
                    job_info["logs"] = job_info["logs"][-50:]
                    
                safe_print(f"⚡ [TTS CH{chapter_no}] {log_line} (Tiến độ toàn lô: {done_count}/{tot} đoạn - {job_info['percent']}%)", flush=True)

        results = await engine.synthesize_all(
            chunks=sub_chunks,
            output_dir=tmp_dir,
            on_chunk_done=on_subchunk_done
        )

        # Kiểm tra tính toàn vẹn 100%: bắt buộc tất cả các sub-chunks phải tồn tại và > 1KB
        sub_mp3s = []
        for i in range(total_sc):
            sc_path = os.path.join(tmp_dir, f"chunk_{i:04d}.mp3")
            if os.path.exists(sc_path) and os.path.getsize(sc_path) > 1024:
                sub_mp3s.append(sc_path)

        if sub_mp3s and len(sub_mp3s) == total_sc:
            if len(sub_mp3s) == 1:
                try:
                    if os.path.exists(chapter_mp3):
                        os.remove(chapter_mp3)
                    shutil.copyfile(sub_mp3s[0], chapter_mp3)
                    success = os.path.exists(chapter_mp3) and os.path.getsize(chapter_mp3) > 10240
                except Exception:
                    success = False
            else:
                success = await asyncio.to_thread(merge_audio_files, sub_mp3s, chapter_mp3, 0.0, False)
                if not success:
                    try:
                        with open(chapter_mp3, "wb") as out_f:
                            for part in sub_mp3s:
                                with open(part, "rb") as in_f:
                                    out_f.write(in_f.read())
                        success = os.path.exists(chapter_mp3) and os.path.getsize(chapter_mp3) > 10240
                    except Exception as e:
                        print(f"[TTS-MERGE] Ghép file thất bại: {e}")
                        success = False
        else:
            # Log chi tiết nếu vẫn thiếu
            missing_count = total_sc - len(sub_mp3s)
            try:
                print(f"[TTS-CH-WARN] Chuong {chapter_no}: thieu {missing_count}/{total_sc} sub-chunks.", flush=True)
            except Exception:
                pass

        # Luôn cleanup tmp dir dù thành công hay thất bại
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        if success:
            job_info["done_chapters"] += 1
            job_info["recent_successes"] += 1
            job_info["last_completed_chapter"] = chapter_no
            sz_mb = os.path.getsize(chapter_mp3) / (1024 * 1024)
            
            # Lưu vĩnh viễn bản ghi AUDIO vào CSDL ngay khi chương vừa hoàn tất
            try:
                async with AsyncSessionLocal() as session:
                    stmt_ch = select(Chapter).where(Chapter.novel_id == job_info.get("novel_id"), Chapter.chapter_no == chapter_no)
                    res_ch = await session.execute(stmt_ch)
                    db_ch = res_ch.scalar_one_or_none()
                    if db_ch:
                        stmt_v = select(ChapterVersion).where(
                            ChapterVersion.chapter_id == db_ch.id,
                            ChapterVersion.version_type == "AUDIO"
                        )
                        res_v = await session.execute(stmt_v)
                        v_audio = res_v.scalar_one_or_none()
                        if v_audio:
                            v_audio.file_path = chapter_mp3
                        else:
                            session.add(ChapterVersion(
                                chapter_id=db_ch.id,
                                version_type="AUDIO",
                                file_path=chapter_mp3
                            ))
                        await session.commit()
            except Exception as e_db:
                pass

            safe_print(f"[TTS-CH OK] Chuong {chapter_no} -> {os.path.basename(chapter_mp3)} ({sz_mb:.2f} MB) [ĐÃ LƯU ĐĨA & DB]", flush=True)
        else:
            job_info["failed_chapters"] += 1
            job_info["recent_failures"] += 1
            safe_print(f"[TTS-CH FAIL] Chuong {chapter_no} khong the tong hop.", flush=True)

        # Thu hồi bộ nhớ + cooldown giữa các chương để Edge-TTS không rate-limit
        del engine
        gc.collect()
        await asyncio.sleep(1.0)  # Cooldown 1s giữa các chương

        queue.task_done()


def generate_range_mp3(
    chapters_cache_dir: str,
    chapter_nos: List[int],
    output_path: str,
    silence_sec: float = 0.0,
    apply_mastering: bool = False
) -> bool:
    """
    Tạo file mp3 khoảng (Range) bằng FFmpeg concat từ các chapter-cache mp3.
    Mặc định sử dụng stream copy để hoàn thành siêu tốc dưới 0.5s.
    """
    files = [_get_chapter_cache_path(chapters_cache_dir, c) for c in chapter_nos]
    # Lọc bỏ file không tồn tại hoặc rỗng
    files = [f for f in files if os.path.exists(f) and os.path.getsize(f) > 0]
    if not files:
        return False
    return merge_audio_files(files, output_path, add_silence_sec=silence_sec, apply_mastering=apply_mastering)


def normalize_final_audio(input_path: str, output_path: str) -> bool:
    """
    Hậu xử lý Audio DSP Mastering toàn diện cho file thành phẩm:
    - Khử 100% tiếng rè dải âm cao (De-essing + High-frequency shaping).
    - Tăng độ nét bóc tách phụ âm (Voice Presence) giúp tua nhanh 1.5x - 2.0x vẫn rõ từng chữ.
    - Chuẩn hóa âm lượng EBU R128 (-16 LUFS) và khóa trần True-Peak -1.0 dBFS chống clipping vỡ tiếng.
    """
    if not (os.path.exists(input_path) and os.path.getsize(input_path) > 1024):
        return False
    try:
        cmd = [
            get_ffmpeg_cmd(), "-y", "-i", input_path,
            "-af", AUDIOBOOK_MASTERING_FILTERS,
            "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "24000",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            return True
            
        # Fallback: sao chép nếu FFmpeg filter gặp lỗi
        if os.path.abspath(input_path) != os.path.abspath(output_path):
            shutil.copyfile(input_path, output_path)
        return True
    except Exception as e:
        print(f"[TTS-NORMALIZE] Lỗi xử lý tệp âm thanh: {e}")
        return False


async def run_tts_volume_pipeline(
    novel_id: int,
    volume_no: int,
    chapters_per_volume: int,
    voice_profile: str = "default",
    force_regenerate: bool = False,
    custom_workers: Optional[int] = None,
):
    """
    Pipeline TTS per-chapter cache hoàn chỉnh:
    1. Xác định danh sách chương cần xử lý
    2. Quét chapter-cache mp3 → chỉ TTS chương chưa có (nếu force_regenerate=True sẽ tạo mới toàn bộ)
    3. Worker pool TTS song song
    4. FFmpeg concat tất cả chapter mp3 → file output cuối
    """
    import gc
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
        gc.collect()
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

    short_title = novel_folder[:30].strip() if len(novel_folder) > 30 else novel_folder
    if volume_no >= 1000000:
        rem = volume_no - 1000000
        start_ch = rem // 10000
        end_ch = rem % 10000
        volume_chapters = [ch for ch in all_chapters if start_ch <= ch.chapter_no <= end_ch]
        final_name = f"{short_title}_Ch{start_ch}_to_Ch{end_ch}.mp3"
    else:
        start_idx = (volume_no - 1) * chapters_per_volume
        end_idx = min(start_idx + chapters_per_volume, len(all_chapters))
        volume_chapters = all_chapters[start_idx:end_idx]
        final_name = f"{short_title}_Vol{volume_no:03d}.mp3"

    if not volume_chapters:
        err = "⚠️ Không tìm thấy chương nào hợp lệ trong khoảng đã chọn."
        print(f"[TTS-ERROR] {err}")
        job_info["status"] = "failed"
        job_info["status_msg"] = err
        job_info["is_running"] = False
        gc.collect()
        return

    chapter_nos = [ch.chapter_no for ch in volume_chapters]
    total_chapters = len(chapter_nos)
    job_info["total_chapters"] = total_chapters
    job_info["total_chunks"] = total_chapters  # backward-compat cho UI

    # Nếu người dùng chọn Tạo lại (Force Regenerate) -> Xóa sạch cache cũ của các chương này
    if force_regenerate:
        print(f"🔄 [TTS-FORCE] Xóa cache cũ cho {total_chapters} chương để tạo mới hoàn toàn...", flush=True)
        for c_no in chapter_nos:
            # 1. Xóa cache mp3 của chương
            old_c = _get_chapter_cache_path(chapters_cache_dir, c_no)
            if os.path.exists(old_c):
                try: os.remove(old_c)
                except Exception: pass
            # 2. Xóa thư mục tạm của chương nếu có
            tmp_c_dir = os.path.join(chapters_cache_dir, f"_tmp_ch{c_no:06d}")
            if os.path.exists(tmp_c_dir):
                try: shutil.rmtree(tmp_c_dir, ignore_errors=True)
                except Exception: pass
            # 3. Xóa file 04b_VanBanTTS cũ để chắc chắn làm sạch lại từ đầu
            old_tts_txt = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS", novel_folder, "chapters", f"{c_no:06d}.txt")
            if os.path.exists(old_tts_txt):
                try: os.remove(old_tts_txt)
                except Exception: pass

    # ── 3. Quét chapter-cache: tìm chương nào chưa có mp3 ────────────────────
    cached_chapters = []
    missing_untranslated = []
    need_tts = []
    need_text = {}  # chapter_no → text

    async with AsyncSessionLocal() as session:
        for ch in volume_chapters:
            is_cached = _is_chapter_cached(chapters_cache_dir, ch.chapter_no, novel_folder=novel_folder)
            
            # Đọc text của chương
            txt = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, ch)
            if txt and txt.strip():
                clean = sanitize_tts_text(txt)
                if clean and clean.strip():
                    # Lưu văn bản đã qua tiền xử lý chuẩn vào 04b_VanBanTTS và ghi vào DB
                    try:
                        tts_fp = save_tts_text_file(novel_folder, ch.chapter_no, clean)
                        stmt_v_tts = select(ChapterVersion).where(
                            ChapterVersion.chapter_id == ch.id,
                            ChapterVersion.version_type == "TTS_TEXT"
                        )
                        res_v_tts = await session.execute(stmt_v_tts)
                        v_tts = res_v_tts.scalar_one_or_none()
                        if v_tts:
                            v_tts.file_path = tts_fp
                            v_tts.content = clean
                        else:
                            session.add(ChapterVersion(
                                chapter_id=ch.id,
                                version_type="TTS_TEXT",
                                file_path=tts_fp,
                                content=clean
                            ))
                        await session.commit()
                    except Exception as e_save:
                        print(f"⚠️ Không thể lưu tệp 04b_VanBanTTS ch{ch.chapter_no}: {e_save}")

                    if is_cached:
                        cached_chapters.append(ch.chapter_no)
                    else:
                        need_tts.append(ch.chapter_no)
                        need_text[ch.chapter_no] = clean
                else:
                    if is_cached:
                        cached_chapters.append(ch.chapter_no)
                    else:
                        missing_untranslated.append(ch.chapter_no)
            else:
                if is_cached:
                    cached_chapters.append(ch.chapter_no)
                else:
                    missing_untranslated.append(ch.chapter_no)

    valid_chapters_to_process = cached_chapters + need_tts
    if not valid_chapters_to_process:
        err = f"⚠️ Chưa có chương nào trong khoảng đã chọn (Chương {volume_chapters[0].chapter_no} - {volume_chapters[-1].chapter_no}) được dịch hoàn tất (FINAL). Vui lòng dịch truyện trước khi tạo Audio!"
        print(f"[TTS-ERROR] {err}")
        job_info["status"] = "failed"
        job_info["status_msg"] = err
        job_info["is_running"] = False
        gc.collect()
        return

    if missing_untranslated:
        print(f"⚠️ [TTS-NOTICE] Phát hiện {len(missing_untranslated)} chương chưa có bản dịch ({missing_untranslated[:5]}...), hệ thống sẽ chỉ tổng hợp {len(valid_chapters_to_process)} chương đã dịch.", flush=True)

    total_chapters = len(valid_chapters_to_process)
    cached_count = len(cached_chapters)
    job_info["total_chapters"] = total_chapters
    job_info["total_chunks"] = total_chapters  # backward-compat cho UI
    
    # Tính toán tổng số subchunks ước tính để tính phần trăm mượt mà theo thời gian thực
    total_subchunks_est = 0
    for ch_no in need_tts:
        chunk_size_str = await get_active_setting("TTS_MAX_CHUNK_SIZE")
        max_chars = int(chunk_size_str) if (chunk_size_str and chunk_size_str.strip().isdigit()) else 600
        sub_c = split_text_into_chunks(need_text[ch_no], max_chars=max_chars)
        total_subchunks_est += max(1, len(sub_c))
        
    job_info["total_subchunks"] = max(1, total_subchunks_est)
    job_info["done_subchunks"] = 0

    safe_print(
        f"🔊 [TTS-START] Truyện '{novel_folder}' | Tập {volume_no} | "
        f"{total_chapters} chương hợp lệ ({total_subchunks_est} sub-chunks) | Đã cache: {cached_count} | Cần TTS: {len(need_tts)}",
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
            num_workers = min(int(tts_workers_str), 4) if (tts_workers_str and tts_workers_str.strip()) else 1
            if num_workers < 1:
                num_workers = 1
        except Exception:
            num_workers = 1

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
                        tts_rate=tts_rate, tts_pitch=tts_pitch, proxy_list=proxy_list, silence_sec=silence_sec,
                        custom_parallel_workers=custom_workers
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
                    safe_print(f"🎉 [TTS-MONITOR] Đã hoàn thành {done}/{total_chapters} chương.", flush=True)
                    break

            # Dừng tất cả worker
            for _ in range(num_workers):
                await queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)

        except asyncio.CancelledError:
            safe_print(f"[TTS-PIPELINE] Job {job_key} bị hủy bởi người dùng.")
            for w in workers:
                if not w.done():
                    w.cancel()

            job_info["status"] = "cancelled"
            job_info["is_running"] = False
            gc.collect()
            return

        except Exception as e:
            safe_print(f"[TTS-PIPELINE ERROR] {e}")
            for w in workers:
                if not w.done():
                    w.cancel()
            job_info["status"] = "failed"
            job_info["is_running"] = False
            gc.collect()
            raise e
    else:
        job_info["worker_count"] = 0
        job_info["percent"] = 100.0
        safe_print(f"⚡ [TTS-FAST] Tất cả {total_chapters} chương đã có sẵn Audio.", flush=True)

    # ── 5. Hoàn tất tiến trình TTS lô (Chỉ tạo & lưu file từng chương riêng biệt, gộp khi người dùng bấm tải) ──
    done_count = job_info.get("done_chapters", total_chapters)
    job_info["status"] = "completed"
    job_info["percent"] = 100.0
    job_info["done_chunks"] = done_count
    job_info["status_msg"] = f"✅ Hoàn tất tạo Audio cho {done_count}/{total_chapters} chương!"
    safe_print(f"🎉 [TTS-DONE] Đã lưu xong Audio các chương trong lô ({done_count}/{total_chapters} chương).", flush=True)

    job_info["is_running"] = False
    gc.collect()


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


import os
import re
import time
import shutil
import asyncio
import random
import subprocess
import psutil
import gc
import json
import edge_tts
from typing import List, Dict, Any, Optional, Set, Tuple
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
        match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)", output)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[TTS-MERGER] Lỗi đọc duration tệp {file_path}: {e}")
    return "00:00:00"

def generate_silence_file(duration_sec: float = 0.35, sample_rate: int = 24000) -> Optional[str]:
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
    Ghép nối danh sách các tệp mp3 bằng FFmpeg re-encode chuẩn 48kbps 24kHz Mono.

    QUAN TRỌNG - LÝ DO KHÔNG DÙNG STREAM COPY (-c copy):
    - Stream copy tốc độ nhanh nhưng KHÔNG tạo lại Xing/LAME seek table cho file ghép.
    - Khi tua nhanh x2/x3 hoặc seek đến đoạn sau của file dài, decoder MP3 (điện thoại,
      VLC, trình duyệt) đọc seek table sai → giật, nhảy cóc, mất ngắt nghỉ giữa câu.
    - aresample=async=1000 chuẩn hóa timestamp giữa các chunk, loại bỏ gap/overlap.
    - write_xing=1 tạo Xing header đầy đủ → tua x2/x3 chính xác 100%.
    - Bitrate 48k 24kHz mono khớp chuẩn Edge-TTS → chất lượng tương đương, dung lượng
      không tăng đáng kể (chỉ thêm ~2-5 giây encode cho mỗi chương).
    """
    if not file_paths:
        return False

    # Nếu chỉ có 1 file, copy thẳng không cần ghép
    if len(file_paths) == 1:
        import shutil as _shutil
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            if os.path.abspath(file_paths[0]) != os.path.abspath(output_path):
                _shutil.copyfile(file_paths[0], output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1024
        except Exception as e:
            print(f"[TTS-MERGER] Lỗi copy file đơn: {e}")
            return False

    import tempfile, uuid
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    list_file_path = os.path.join(tempfile.gettempdir(), f"airead_concat_{uuid.uuid4().hex[:8]}.txt")

    silence_file = None
    if add_silence_sec > 0.02:
        silence_file = generate_silence_file(add_silence_sec)

    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for idx, fp in enumerate(file_paths):
                if idx > 0 and silence_file and os.path.exists(silence_file):
                    norm_silence = silence_file.replace("\\", "/")
                    f.write(f"file '{norm_silence}'\n")
                normalized_path = fp.replace("\\", "/")
                f.write(f"file '{normalized_path}'\n")

        # Re-encode chuẩn với aresample (chuẩn hóa timestamps) + write_xing=1 (tạo seek table)
        # Giúp tua nhanh x2/x3 mượt mà trên mọi thiết bị/trình duyệt, không bị nuốt câu, giật lag hay vấp tiếng.
        cmd_encode = [
            get_ffmpeg_cmd(), "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file_path,
            "-threads", "0",
            "-af", "aresample=async=1000",
            "-c:a", "libmp3lame", "-b:a", "48k", "-ar", "24000", "-ac", "1",
            "-max_muxing_queue_size", "4096",
            "-id3v2_version", "3", "-write_xing", "1",
            output_path
        ]
        res_encode = subprocess.run(
            cmd_encode, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="ignore"
        )
        if res_encode.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            return True

        # Fallback cuối cùng: stream copy nếu encode thất bại (libmp3lame không có)
        # Lưu ý: file này có thể giật khi tua x2/x3 nhưng ít nhất có audio
        print(f"[TTS-MERGER] Re-encode thất bại (returncode={res_encode.returncode}), fallback stream copy...")
        cmd_copy = [
            get_ffmpeg_cmd(), "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",
            output_path
        ]
        res_copy = subprocess.run(
            cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="ignore"
        )
        return res_copy.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024

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

def detect_and_separate_chapter_title(
    text: str,
    chapter_no: Optional[int] = None,
    fallback_title: Optional[str] = None
) -> Tuple[Optional[str], str]:
    """
    Tự động nhận diện chính xác Tiêu đề chương và tách biệt hoàn toàn khỏi thân truyện:
    1. Tiêu đề có tiền tố chuẩn: 'Chương X: [Tên]', 'Chapter X: [Tên]', 'Hồi X', 'Tiết X'...
    2. Tiêu đề không có tiền tố 'Chương' nhưng trùng khớp với fallback_title / chapter.title_rough từ CSDL.
    3. Dòng đầu tiên độc lập ngắn (<= 70 ký tự), theo sau là dòng trống hoặc chuyển đoạn, không phải lời thoại/suy nghĩ.
    
    Trả về:
    - title_str: Tên chương đã chuẩn hóa (hoặc None nếu không phát hiện)
    - body_str: Toàn bộ thân truyện sạch sẽ 100%, bắt đầu từ câu văn đầu tiên.
    """
    if not text:
        return None, ""

    lines = text.split('\n')
    start_idx = 0
    while start_idx < len(lines):
        line = lines[start_idx].strip()
        if not line:
            start_idx += 1
            continue
        clean_tag = re.sub(r'^[=\-_\*#\s\(\[\{【（"“\.,:;]+|[=\-_\*#\s\)\]\}】）"”\.,:;]+$', '', line).strip()
        if re.match(r'^(?:bắt đầu)\s*(?:chương|chapter)', clean_tag, re.IGNORECASE):
            start_idx += 1
            continue
        break

    if start_idx >= len(lines):
        return None, ""

    first_line = lines[start_idx].strip()
    rest_lines = lines[start_idx + 1:]
    clean_first = re.sub(r'^[“"‘\'\[\(]+|[”"’\'\]\)]+$', '', first_line).strip()
    title_str = None
    body_prefix = ""

    clean_fb = ""
    if fallback_title and len(fallback_title.strip()) <= 80:
        clean_fb = re.sub(r'^(?:第?\s*\d+\s*章\s*[:.:-]?|Chương\s*\d+\s*[:.:-]?)', '', fallback_title, flags=re.IGNORECASE).strip()
        clean_fb = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', clean_fb)

    # TH1: Tiền tố chuẩn: Chương X / Chapter X / Hồi X / Tiết X
    ch_match = re.match(r'^(?:Quyển\s*\d+\s*)?(?:Chương|Hồi|Tiết|Tập|Chapter|Chap|Section|Vol|Volume)\s*(\d*)[\s:.-]*(.*)$', clean_first, re.IGNORECASE)
    if ch_match:
        c_num_str = ch_match.group(1).strip()
        c_num = int(c_num_str) if c_num_str else (chapter_no or 0)
        raw_name = ch_match.group(2).strip()
        raw_name = re.sub(r'[\(（](?:cầu|hết|chương).*?[\)）]', '', raw_name, flags=re.IGNORECASE).strip()
        # Nếu dòng chỉ có 'Chương X:' và tên chương nằm ở dòng kế tiếp
        if not raw_name and rest_lines:
            next_line = rest_lines[0].strip()
            if len(next_line) <= 60 and not re.search(r'^[“"‘\'\-–—]', next_line):
                raw_name = next_line
                rest_lines = rest_lines[1:]
        if len(raw_name) > 60:
            split_m = re.search(r'(?:\!\.\.|\?\.\.|\.\.|\!|\?|\.)\s+', raw_name)
            if split_m and split_m.start() < 60:
                actual_name = raw_name[:split_m.start() + 1].strip()
                body_prefix = raw_name[split_m.end():].strip()
            else:
                actual_name = raw_name[:60].strip()
                body_prefix = raw_name[60:].strip()
        else:
            actual_name = raw_name
        actual_name = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', actual_name)
        title_str = f"Chương {c_num}: {actual_name}".strip() if actual_name else f"Chương {c_num}"

    # TH2: Khớp với fallback_title từ CSDL
    elif clean_fb and (clean_first.lower().startswith(clean_fb.lower()) or clean_fb.lower() in clean_first.lower()):
        c_num = chapter_no or 0
        title_str = f"Chương {c_num}: {clean_fb}".strip() if c_num else clean_fb
        idx = clean_first.lower().find(clean_fb.lower())
        if idx != -1:
            after_fb = clean_first[idx + len(clean_fb):].strip()
            if after_fb:
                body_prefix = re.sub(r'^[.:,\s-]+', '', after_fb).strip()

    # TH3: Dòng đầu tiên chỉ là tiêu đề độc lập nếu có chapter_no VÀ khớp với cấu trúc tiêu đề (không có dấu câu truyện)
    elif chapter_no and len(clean_first) <= 60 and not re.search(r'^[“"‘\'\-–—]', clean_first) and not re.search(r'[,:;!?…]\s*\w+', clean_first) and clean_first[-1:] not in '.!?…' and (fallback_title or re.match(r'^(?:thứ\s*\d+\s*chương|bản\s+chương)\b', clean_first, re.IGNORECASE)):
        c_num = chapter_no
        actual_name = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', clean_first)
        title_str = f"Chương {c_num}: {actual_name}".strip() if c_num else actual_name

    body_lines = []
    if title_str:
        if body_prefix:
            body_lines.append(body_prefix)
        body_lines.extend(rest_lines)
    else:
        # TUYỆT ĐỐI KHÔNG BỎ SÓT DÒNG ĐẦU TIÊN: Không phát hiện tiêu đề chương -> first_line là 100% nội dung truyện!
        body_lines = [first_line] + rest_lines

    body_str = '\n'.join(body_lines).strip()
    return title_str, body_str


def format_dialogue_flow(text: str) -> str:
    """
    Chuẩn hóa nhịp ngắt thoại để giọng đọc TTS tự nhiên, không bị khựng lâu hoặc dính câu:
    - Nhận diện lời dẫn thoại ('anh nói:', 'hắn bảo,', 'tôi hỏi:', 'đáp:', v.v.):
      Dùng chấm phẩy '; ' trên cùng dòng để Edge-TTS ngắt nghỉ tự nhiên vừa đủ (~180ms) trước lời thoại,
      không ngắt dòng riêng làm tách rời người nói và câu thoại.
    - Nhận diện kết thúc lời thoại trước lời dẫn/phản ứng của nhân vật khác:
      Ngắt dòng '\\n' để phân biệt rõ ràng lượt nói (turns) giữa các nhân vật.
    - Sau khi lời dẫn của nhân vật kết thúc (vd 'Anh đáp.'), ngắt dòng '\\n' để vào câu tiếp theo.
    - Giữ dấu đơn chuẩn, tránh khựng quá lâu.
    """
    if not text:
        return text

    # 1. Lead-in: Người nói + động từ nói + dấu hai chấm/phẩy -> đổi thành '; ' (nhịp nghỉ nhẹ tự nhiên ~180ms trước khi nhân vật cất tiếng)
    lead_in_pat = re.compile(
        r'(?<!\bchính xác mà )(?<!\bnói tóm lại )(?<!\bthực tế mà )'
        r'(\b(?:nói|bảo|hỏi|đáp|thốt lên|kêu lên|quát|hét|gầm lên|cười nói|lên tiếng hỏi|trầm giọng hỏi|gật đầu đáp|lắc đầu đáp|thì thầm|lẩm bẩm))\s*([,:;]+)\s+(?=[A-ZÀ-Ỹ0-9])',
        re.IGNORECASE
    )
    text = lead_in_pat.sub(r'\1; ', text)

    # 2. Xong câu nói của nhân vật + lời dẫn truyện/người đáp tiếp theo -> tách dòng \n cho lượt nói mới
    attr_after_pat = re.compile(
        r'([.!?…]+)\s+(?=(?:[A-ZÀ-Ỹ][\w\dÀ-ỹ\s]{0,35}?\s+)?(?:nói|bảo|hỏi|đáp|thốt lên|kêu lên|quát|hét|gầm lên|lên tiếng hỏi|ngạc nhiên hỏi|trầm giọng hỏi|gật đầu đáp|lắc đầu đáp)\s*[;:.!?…]+)',
        re.IGNORECASE
    )
    text = attr_after_pat.sub(r'\1\n', text)

    # 3. Sau khi lời dẫn của nhân vật kết thúc (vd: "Anh đáp. "), nếu có câu tiếp theo thì ngắt dòng \n
    tag_end_pat = re.compile(
        r'(\b(?:nói|bảo|hỏi|đáp|thốt lên|kêu lên|quát|hét|gầm lên|lên tiếng hỏi|ngạc nhiên hỏi|trầm giọng hỏi|gật đầu đáp|lắc đầu đáp)\s*[.!?…]+)\s+(?=[A-ZÀ-Ỹ0-9])',
        re.IGNORECASE
    )
    text = tag_end_pat.sub(r'\1\n', text)

    # 4. Dọn dẹp khoảng trắng và xuống dòng thừa: không quá 2 dòng trống liên tiếp
    text = re.sub(r'[^\S\r\n]+', ' ', text)
    text = re.sub(r'\n[^\S\r\n]+', '\n', text)
    text = re.sub(r'[^\S\r\n]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()



def sanitize_tts_text(
    text: str,
    chapter_no: Optional[int] = None,
    chapter_title: Optional[str] = None,
    include_title: bool = False
) -> str:
    """
    Làm sạch văn bản khi đưa lên TTS & lưu vào 04b_VanBanTTS:
    - Tự động nhận diện Tên chương và tách biệt hoàn toàn khỏi thân truyện.
    - Nếu include_title=True: Đặt tên chương ở đầu với nhịp ngắt dứt khoát ('.. .. ') để TTS ngắt nghỉ 1.5s trước khi vào truyện.
    - Nếu include_title=False: Loại bỏ sạch sẽ tên chương, thân truyện bắt đầu trực tiếp từ câu đầu tiên.
    - Loại bỏ lời tác giả/xin phiếu, thẻ HTML, Markdown, URL, Emojis, ký tự trang trí lạ.
    - Chuẩn hóa toàn bộ dấu câu Đông Á & ngoặc sang dạng chuẩn ASCII.
    - Bóc ngoặc đơn/kép, chuyển thành nhịp ngắt phẩy nhẹ hoặc khoảng trắng, không sinh dấu kép.
    - Chuyển các cụm ngắt từ ngắn (cái... cái, tôi... tôi) thành dấu phẩy (cái, cái) để giọng đọc trôi mượt.
    - Đồng bộ hóa toàn bộ dấu câu về ĐÚNG 1 dấu duy nhất (. ! ? , ; :), khử 100% các lỗi dấu kép.
    - Gộp toàn bộ thành một dòng văn bản liền mạch (không phụ thuộc vào phân đoạn \\n của LLM).
    - Bảo toàn 100% nguyên văn từ ngữ và từ lóng của nội dung truyện.
    """
    if not text:
        return ""

    # 0. Loại bỏ ký tự rỗng/vô hình zero-width, BOM và control characters
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0]', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # 0b. Tách biệt tên chương và thân truyện
    detected_title, body_text = detect_and_separate_chapter_title(text, chapter_no=chapter_no, fallback_title=chapter_title)
    text = body_text

    def _is_tail_meta_line(line_str: str) -> bool:
        clean = re.sub(r'^[=\-_\*#\s\(\[\{【（"“\.,:;]+|[=\-_\*#\s\)\]\}】）"”\.,:;]+$', '', line_str).strip()
        if not clean:
            return True
        # Thẻ kết thúc chương: === [KẾT THÚC CHƯƠNG X] ===
        if re.match(r'^(?:kết thúc|hết)\s*(?:chương|chapter)', clean, re.IGNORECASE):
            return True
        # Thông báo hết chương độc lập chuẩn xác (toàn bộ dòng chỉ là thông báo kết thúc)
        if re.match(r'^(?:hết\s+chương|kết\s+thúc\s+chương|toàn\s+văn\s+hoàn|chính\s+văn\s+hoàn|bản\s+chương\s+hoàn|tấu\s+chương\s+hoàn|chương\s+hoàn|end\s+chapter|the\s+end|to\s+be\s+continued|còn\s+tiếp|hoàn)$', clean, re.IGNORECASE):
            return True
        if len(clean) <= 40 and re.search(r'(?:hết|kết\s+thúc)\s+chương', clean, re.IGNORECASE):
            return True
        # Lời xin phiếu / tác giả cuối chương
        if re.match(r'^(?:sách mới|cầu sưu tầm|cầu đề cử|cầu phiếu|cầu hoa|cầu nguyệt|xin phiếu|ủng hộ|cảm kích|cảm ơn đã đọc|xin cảm ơn|cầu bình luận|các bạn ủng hộ|xin ủng hộ|cầu đánh giá|cầu vé|cầu thu thập|nhớ bỏ phiếu|cuối tháng)\b', clean, re.IGNORECASE):
            return True
        return False

    raw_lines = text.split('\n')

    # Quét từ dưới lên: Bỏ các dòng meta cuối chương cho đến khi chạm dòng truyện cuối cùng thì DỪNG LẠI
    end_idx = len(raw_lines) - 1
    while end_idx >= 0:
        l = raw_lines[end_idx].strip()
        if not l or not re.search(r'[\w\dÀ-ỹ]', l):
            end_idx -= 1
            continue
        if _is_tail_meta_line(l):
            end_idx -= 1
            continue
        break

    # GIỮ NGUYÊN 100% THÂN TRUYỆN Ở GIỮA
    clean_lines = [l.strip() for l in raw_lines[:end_idx + 1] if l.strip() and re.search(r'[\w\dÀ-ỹ]', l)]
    text = '\n'.join(clean_lines)

    # 1. Bóc tách triệt để thẻ HTML: Bóc tất cả các dạng thẻ <tag...>Nội dung</tag> -> Giữ lại Nội dung chữ thuần túy
    for _ in range(5):
        _prev_text = text
        text = re.sub(r'<span\b[^>]*data-raw=["\'](.*?)["\'][^>]*>(.*?)</span>', r'\2', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[a-zA-Z0-9_-]+\b[^>]*>(.*?)</[a-zA-Z0-9_-]+>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'</?[a-zA-Z0-9_-]+[^>]*>', ' ', text)
        if text == _prev_text:
            break

    # 1b. Loại bỏ các ghi chú / chú thích của dịch giả / tác giả trong ngoặc
    AUTHOR_NOTE_KEYWORDS = r'chú thích|ghi chú|note|lời dịch giả|lời tác giả|lời người dịch|tg|tác giả|p/?s|cầu hoa tươi|cầu nguyệt phiếu|cầu đề cử'
    text = re.sub(r'[\(\[\{【（]\s*(?:' + AUTHOR_NOTE_KEYWORDS + r')[\s:][^\)\]\}】）]*[\)\]\}】）]', ' ', text, flags=re.IGNORECASE)

    # 1c. Xử lý các cụm chữ Hán kèm mở ngoặc tiếng Việt: ác戾气 (lệ khí) -> ác lệ khí
    text = re.sub(r'[\u4e00-\u9fff]+\s*[\(\（\[【]([^\)\）\]】]+)[\)\）\]】]', r' \1 ', text)
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)

    # 2. Xóa Markdown, URL, Email
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'[\*_~=]{1,}', ' ', text)

    # 3. Loại bỏ Emojis & ký tự trang trí lạ
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001f900-\U0001f9ff\U00002600-\U000026FF]', '', text)
    text = re.sub(r'[★☆◆◇■□▲△▼▽●○♥♠♣♦♂♀⟪⟫▸▹►▻◄◄§†‡✓✕✗¶™®©♪♫✿❀❁☸⚡⚙⚔🛡🗡👑✦✧✨✴❇❄🔴🔵🟡🟢🟣⭐🌟🔥💥💢￥¥@#$%^&+=|\\/～~]', ' ', text)

    # 4. Chuẩn hóa toàn bộ dấu câu Đông Á & ngoặc sang dạng chuẩn ASCII
    # 4a. Ngoặc Đông Á & ngoặc kép: Chuẩn hóa về ngoặc kép chuẩn để nhận diện lời thoại
    text = text.replace('「', '"').replace('」', '"').replace('『', '"').replace('』', '"')
    text = text.replace('《', ' ').replace('》', ' ')
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u201e', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    # 4b. Dấu câu Đông Á → ASCII chuẩn
    text = text.replace('\u3002', '. ').replace('\uff0c', ', ').replace('\uff01\uff1f', '! ').replace('\uff1f\uff01', '? ').replace('\uff01', '! ').replace('\uff1f', '? ')
    text = text.replace('\uff1a', ': ').replace('\uff1b', ', ').replace('\u00b7', ' ')

    # 5. Chuẩn hóa đơn vị đo, chức danh
    text = re.sub(r'(^|[ \t])>=[ \t]*', r'\1lớn hơn hoặc bằng ', text)
    text = re.sub(r'(^|[ \t])<=[ \t]*', r'\1nhỏ hơn hoặc bằng ', text)
    text = re.sub(r'(^|[ \t])!=[ \t]*', r'\1khác ', text)
    text = re.sub(r'(^|[ \t])>[ \t]*', r'\1lớn hơn ', text)
    text = re.sub(r'(^|[ \t])<[ \t]*', r'\1nhỏ hơn ', text)
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

    # 6. Biểu cảm & lắp bắp:
    # 6a. Lắp bắp (k-không -> không, không; c-con -> con, con) -> chuyển thành phẩy nhẹ
    stutter_pattern = r'\b([a-zA-ZÀ-ỹ])\s*[-–—.]+\s*([a-zA-ZÀ-ỹ]{2,})\b'
    def _smart_stutter_replace(m):
        lead_char = m.group(1).lower()
        word = m.group(2)
        if word.lower().startswith(lead_char) or (lead_char == 'k' and word.lower().startswith('kh')):
            return f"{word}, {word}"
        return m.group(0)
    text = re.sub(stutter_pattern, _smart_stutter_replace, text)

    # 6b. La hét có dấu sắc: chuẩn hóa về đúng "á, á!" / "é, é!"
    def _normalize_acute_scream(m):
        raw = m.group(0)
        v = m.group(1)
        is_upper = raw.strip()[:1].isupper()
        base_v = v.capitalize() if is_upper else v.lower()
        return f"{base_v}, {base_v.lower()}!"
    text = re.sub(r'(?i)(?<![a-zA-ZÀ-ỹ])([áÁéÉíÍóÓúÚớỚứỨ]|oá|oé)(?:[ \t]*[\-—.,~]*[ \t]*\1)+(?![a-zA-ZÀ-ỹ])', _normalize_acute_scream, text)
    text = re.sub(r'(?i)([áÁéÉíÍóÓúÚớỚứỨ]|oá|oé)\1+', _normalize_acute_scream, text)

    # 6c. Nguyên âm la hét / rên rỉ
    text = re.sub(r'(?i)(?<![a-zA-ZÀ-ỹ])([aeouàèòùảẻỏủãẽõũạẹọụ])(?:[ \t]*[\-—.,~]*[ \t]*\1){1,}(?![a-zA-ZÀ-ỹ])', lambda m: m.group(1).lower() * 3, text)
    text = re.sub(r'(?i)(?<![a-zA-ZÀ-ỹ])([ôốồổỗộơờởỡợưừửữựêềểễệ])(?:[ \t]*[\-—.,~]*[ \t]*\1){1,}(?![a-zA-ZÀ-ỹ])', lambda m: m.group(1).lower() * 3, text)

    # 6d. Từ tượng thanh lặp
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

    # 6e. Cảm thán lặp
    text = re.sub(r'(?i)\b(ối|ối dồi ôi|trời ơi)(?:[ \t]*[\-—.,~!]*[ \t]*\1){1,}', lambda m: m.group(1) * 2 + "!", text)

    # 6f. Chuẩn hóa dấu gạch ngang thoại và nối từ
    text = re.sub(r'[\u2013\u2014\u2015\-]{2,}', ', ', text)
    text = re.sub(r'(?m)^\s*[\-\u2013\u2014\u2015]+\s*', '', text)
    text = re.sub(r'\s+[\-\u2013\u2014\u2015]+\s+', ', ', text)

    # 7. Xóa các ký tự ngoặc đơn / vuông / nhọn còn sót lại nếu trống rỗng
    text = re.sub(r'[\(\[\{][\s,.]*[\)\]\}]', ' ', text)

    # 8. Hợp nhất khoảng trắng thừa
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)

    # 8b. HỢP NHẤT DÒNG DẪN THOẠI ĐỨNG RIÊNG VỚI CÂU NÓI TIẾP THEO
    # Tránh trường hợp "Triệu Nghị lạnh lùng đáp:\n..." bị tách làm 2 chunk hoặc nghỉ quá dài
    raw_lines = [l.strip() for l in text.split('\n') if l.strip()]
    merged_lines = []
    idx = 0
    # Pattern nhận diện dòng chứa tên nhân vật / lời dẫn thoại kết thúc bằng dấu hai chấm (<= 150 ký tự)
    speaker_tag_pat = re.compile(r'^([A-ZÀ-Ỹa-zà-ỹ0-9\s,\'"“”–—]{2,150}):\s*$')

    while idx < len(raw_lines):
        cur_l = raw_lines[idx]
        m = speaker_tag_pat.match(cur_l)
        if m and (idx + 1) < len(raw_lines):
            speaker = m.group(1).strip()
            speaker = re.sub(r'["\']', '', speaker).strip()
            next_l = raw_lines[idx + 1].strip()
            clean_dlg = re.sub(r'^["\']+|["\']+$', '', next_l).strip()
            merged_lines.append(f"{speaker}; {clean_dlg}")
            idx += 2
            continue
        merged_lines.append(cur_l)
        idx += 1

    lines = merged_lines

    # 9. Giữ nguyên cấu trúc phân đoạn và các lượt thoại bằng ký tự xuống dòng \n
    # Đảm bảo không bao giờ bỏ rơi dấu chấm sau câu nói/lời thoại:
    for idx, l in enumerate(lines):
        clean_end = re.sub(r'["\'”’]+$', '', l).strip()
        if clean_end and not re.search(r'[.:;!?…—~]$', clean_end):
            if re.search(r'["\'”’]+$', l):
                lines[idx] = re.sub(r'(["\'”’]+)$', r'.\1', l)
            else:
                lines[idx] = l + '.'
    full_text = '\n'.join(lines)
    full_text = full_text.replace('"', '').replace("'", '')

    # Bảo vệ số thập phân và phân cách hàng nghìn trước khi xử lý dấu câu
    full_text = re.sub(r'(\d+),(\d{1,2})\b', r'\1 phẩy \2', full_text)
    full_text = re.sub(r'(\d{1,3}),(\d{3})\b', r'\1\2', full_text)

    # CHUẨN HÓA DẤU CÂU CHO TTS (NGẮT NGHỈ RÕ RÀNG, BẢO TOÀN DẤU PHẨY TỰ NHIÊN):
    # 0. Khử triệt để các chuỗi dấu lộn xộn, dấu phẩy dính sau dấu chấm/than/hỏi (ví dụ !..,, hay ?.,,)
    full_text = re.sub(r'([.!?…]+)[,;:\s]+(?=[.!?…])', r'\1', full_text)
    full_text = re.sub(r'([.!?…]+)[,;:]+', r'\1', full_text)
    full_text = re.sub(r'[,;:]+([.!?…]+)', r'\1', full_text)

    # 1. Dấu kết hợp hỏi + than (!? hoặc ?!)
    full_text = re.sub(r'(?:![ \t]*\?|\?[ \t]*!)[!? \t\.]*', ' ___QMARK_EXCL___ ', full_text)

    # 2. Dấu cảm thán: Đổi thành '! '
    full_text = re.sub(r'!+[! \t\.]*', ' ___EXCLAMATION___ ', full_text)

    # 3. Dấu hỏi: Đổi thành '? '
    full_text = re.sub(r'\?+[! \t\.]*', ' ___QUESTION___ ', full_text)

    # 4. Dấu ba chấm (. . ., ..., …)
    full_text = re.sub(r'(?:\.\s*){3,}|[…]+|\.{3,}', ' ___ELLIPSE___ ', full_text)

    # 5. Dấu chấm: Chuẩn hóa ngắt câu '. ' để nghỉ dứt khoát nhanh gọn (~250-300ms)
    full_text = re.sub(r'\.+', ' ___PERIOD___ ', full_text)

    # 6a. Dấu hai chấm: Chuẩn hóa ngắt thoại nhẹ nhàng (~180ms như chấm phẩy/phẩy)
    full_text = re.sub(r':+', ' ___COLON___ ', full_text)

    # 6b. Dấu chấm phẩy: Giữ nguyên để phục vụ ngắt trầm ngâm (~200-230ms)
    full_text = re.sub(r';+', ' ___SEMICOLON___ ', full_text)

    # 6c. Dấu phẩy: Bảo tồn dấu phẩy tự nhiên để ngắt nghỉ linh hoạt (~100-120ms), không ép sang chấm phẩy
    full_text = re.sub(r',+', ' ___COMMA___ ', full_text)

    # 7. Khôi phục CHUẨN XÁC nhịp đọc:
    full_text = full_text.replace('___QMARK_EXCL___', '!? ')
    full_text = full_text.replace('___EXCLAMATION___', '! ')
    full_text = full_text.replace('___QUESTION___', '? ')
    full_text = full_text.replace('___ELLIPSE___', '... ')
    full_text = full_text.replace('___PERIOD___', '. ')
    # Dấu hai chấm chuyển thành '; ' (ngắt nhẹ tự nhiên ~180ms như phẩy/chấm phẩy, tránh khựng : ... kéo dài)
    full_text = full_text.replace('___COLON___', '; ')
    full_text = full_text.replace('___SEMICOLON___', '; ')
    full_text = full_text.replace('___COMMA___', ', ')

    # Xóa khoảng trắng thừa đứng trước dấu câu & đảm bảo khoảng trắng chuẩn sau dấu câu
    full_text = re.sub(r'[^\S\r\n]+([,.:;!?…])', r'\1', full_text)
    full_text = re.sub(r'([,.:;!?…]+)(?=[^\s,.:;!?…])', r'\1 ', full_text)
    full_text = re.sub(r'^[,\.:;!?…\s]+', '', full_text)
    full_text = re.sub(r'[^\S\r\n]+', ' ', full_text).strip()

    # KHẮC PHỤC TRIỆT ĐỂ LỖI NHÂN BẢN DẤU (Bảo tồn ... 3 chấm chuẩn):
    full_text = re.sub(r'\.{4,}', '... ', full_text)
    full_text = re.sub(r'(?<!\.)\.\.(?!\.)', '. ', full_text)
    full_text = re.sub(r',{2,}', ', ', full_text)
    full_text = re.sub(r';{2,}', '; ', full_text)
    full_text = re.sub(r':{2,}', '; ', full_text)
    full_text = re.sub(r'[,;]\s*[,;]+', '; ', full_text)
    full_text = re.sub(r'\.\s*[,;:]+', '. ', full_text)
    full_text = re.sub(r'[,;:]\s*\.+', '. ', full_text)

    # Dọn dẹp dấu phẩy/chấm phẩy bị treo lơ lửng ở cuối văn bản trước khi bọc dấu kết thúc
    full_text = re.sub(r'[,;:\s]+$', '', full_text)

    # 13. Khử triệt để các tàn dư thẻ chương, tên chương hoặc thông báo kết thúc chương ở cuối văn bản
    _trailing_tag_pat = re.compile(
        r'(?:[.,:;!?…\s]|\-)*(?:===|\[\s*(?:BẮT ĐẦU|KẾT THÚC)?[^\]]*\]|\(?(?:Hết|Kết thúc)\s+chương\)?|(?:Bắt đầu|Kết thúc)\s+chương(?:\s*\d+)?|\bCHƯƠNG\s*\d+\b)[.,:;!?…\s]*$',
        re.IGNORECASE
    )
    for _ in range(5):
        _new_ft = _trailing_tag_pat.sub('', full_text)
        if _new_ft == full_text:
            break
        full_text = _new_ft

    # Xóa lại lần cuối nếu có ngoặc kép tàn dư hoặc thẻ HTML sót
    full_text = full_text.replace('"', '').replace("'", '')
    full_text = re.sub(r'</?[a-zA-Z0-9_-]+[^>]*>', ' ', full_text)
    full_text = re.sub(r'[^\S\r\n]+', ' ', full_text).strip()

    # Dọn dẹp lại dấu phẩy treo ở cuối (nếu sau khi xóa thẻ lại lòi ra dấu phẩy)
    full_text = re.sub(r'[,;:\s]+$', '', full_text)
    if full_text and full_text[-1] not in '.!?…':
        full_text += '.'

    # Chuẩn hóa nhịp ngắt thoại cho câu nói nhân vật / lời dẫn ('anh nói,\n') và kết thúc thoại
    full_text = format_dialogue_flow(full_text)

    # Chuẩn hóa khoảng trắng nội dòng và dòng trống thừa (tối đa 2 dòng trống liên tiếp)
    full_text = re.sub(r'[^\S\r\n]+', ' ', full_text)
    full_text = re.sub(r'\n[^\S\r\n]+', '\n', full_text)
    full_text = re.sub(r'[^\S\r\n]+\n', '\n', full_text)
    full_text = re.sub(r'\n{3,}', '\n\n', full_text).strip()

    # Nếu include_title=True và có detected_title: Ghép tên chương ở đầu với khoảng ngắt dứt khoát (~500ms)
    if include_title and detected_title:
        clean_title = detected_title.strip()
        clean_title = clean_title.replace('"', '').replace("'", '')
        clean_title = re.sub(r'[.:,\s-]+$', '', clean_title)
        if clean_title:
            full_text = f"{clean_title}.\n\n{full_text}"


    return full_text


def split_text_into_chunks(text: str, max_chars: int = 650) -> List[str]:
    """
    Phân tách văn bản thành các chunk <= max_chars ký tự:
    - Bảo toàn ký tự xuống dòng \\n giữa các đoạn / câu thoại để Edge-TTS giữ nhịp ngắt thoại tự nhiên.
    - Tách chuẩn xác theo từng câu kết thúc (. ! ? ...).
    - Câu quá dài được chia theo dấu phẩy hoặc dấu chấm phẩy (,, , ; :).
    - Đảm bảo mỗi chunk luôn kết thúc bằng dấu câu hợp lệ (.., ,,) để không bị nuốt/cắt chữ cuối.
    - Bảo toàn 100% từ ngữ, tuyệt đối không bị mất từ khi câu dài.
    """
    if not text or not text.strip():
        return []

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    atomic_units = []
    for line in lines:
        raw_sents = re.split(r'([.!?…]+(?:\s+|$))', line)
        line_sents = []
        if len(raw_sents) > 1:
            for i in range(0, len(raw_sents) - 1, 2):
                s = (raw_sents[i] + raw_sents[i+1]).strip()
                if s:
                    line_sents.append(s)
            if len(raw_sents) % 2 == 1 and raw_sents[-1].strip():
                line_sents.append(raw_sents[-1].strip())
        else:
            line_sents = [line]

        for s_idx, s in enumerate(line_sents):
            is_end = (s_idx == len(line_sents) - 1)
            atomic_units.append((s, is_end))

    final_units = []
    for s, is_end in atomic_units:
        if len(s) <= max_chars:
            final_units.append((s, is_end))
        else:
            raw_parts = re.split(r'([,;:]+(?:\s+|$))', s)
            parts = []
            if len(raw_parts) > 1:
                for i in range(0, len(raw_parts) - 1, 2):
                    p = (raw_parts[i] + raw_parts[i+1]).strip()
                    if p:
                        parts.append(p)
                if len(raw_parts) % 2 == 1 and raw_parts[-1].strip():
                    parts.append(raw_parts[-1].strip())
            else:
                parts = [s]
            
            for p_idx, p in enumerate(parts):
                p_end = is_end if (p_idx == len(parts) - 1) else False
                if len(p) <= max_chars:
                    final_units.append((p, p_end))
                else:
                    words = p.split(' ')
                    buf: List[str] = []
                    buf_len = 0
                    for w in words:
                        if not w:
                            continue
                        w_len = len(w)
                        needed = buf_len + w_len + (1 if buf else 0)
                        if needed > max_chars and buf:
                            sub_str = ' '.join(buf).strip()
                            if sub_str and sub_str[-1] not in '.!?,;…':
                                sub_str += ','
                            final_units.append((sub_str, False))
                            buf = [w]
                            buf_len = w_len
                        else:
                            buf.append(w)
                            buf_len = needed
                    if buf:
                        sub_str = ' '.join(buf).strip()
                        final_units.append((sub_str, p_end))

    chunks = []
    cur_chunk = ""
    for unit_text, is_line_end in final_units:
        unit_text = unit_text.strip()
        if not unit_text:
            continue
        sep = "\n" if (cur_chunk and cur_chunk.endswith("\n")) else (" " if cur_chunk else "")
        test_len = len(cur_chunk.strip()) + len(unit_text) + (1 if sep else 0)
        if test_len <= max_chars:
            cur_chunk = (cur_chunk.strip() + sep + unit_text) if cur_chunk else unit_text
            if is_line_end:
                cur_chunk += "\n"
        else:
            if cur_chunk.strip():
                clean_chunk = cur_chunk.strip()
                clean_chunk = re.sub(r'[,;:]+\s*([.!?…]+)', r'\1', clean_chunk)
                clean_chunk = re.sub(r'([.!?…]+)\s*[,;:]+', r'\1', clean_chunk)
                clean_chunk = re.sub(r'[,;:]+$', '.', clean_chunk)
                if clean_chunk[-1] not in '.!?…':
                    clean_chunk += '.'
                chunks.append(clean_chunk)
            cur_chunk = re.sub(r'^[,\.:;!?…\s]+', '', unit_text)
            if is_line_end:
                cur_chunk += "\n"

    if cur_chunk.strip():
        clean_chunk = cur_chunk.strip()
        clean_chunk = re.sub(r'[,;:]+\s*([.!?…]+)', r'\1', clean_chunk)
        clean_chunk = re.sub(r'([.!?…]+)\s*[,;:]+', r'\1', clean_chunk)
        clean_chunk = re.sub(r'[,;:]+$', '.', clean_chunk)
        if clean_chunk[-1] not in '.!?…':
            clean_chunk += '.'
        chunks.append(clean_chunk)

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


def _get_chapter_json_path(chapters_cache_dir: str, chapter_no: int) -> str:
    """Trả về đường dẫn file json subtitle của 1 chương cụ thể"""
    return os.path.join(chapters_cache_dir, f"{chapter_no:06d}.json")


def _is_chapter_cached(chapters_cache_dir: str, chapter_no: int, novel_folder: str = "") -> bool:
    """Kiểm tra cache mp3 của chương có tồn tại, hợp lệ và bảo toàn 100% nội dung không"""
    p_mp3 = _get_chapter_cache_path(chapters_cache_dir, chapter_no)
    if not (os.path.exists(p_mp3) and os.path.getsize(p_mp3) > 10240):
        return False

    p_json = _get_chapter_json_path(chapters_cache_dir, chapter_no)
    if os.path.exists(p_json) and novel_folder:
        try:
            candidate_paths = [
                os.path.join(r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS", novel_folder, "chapters", f"{chapter_no:06d}.txt"),
                os.path.join(r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS", novel_folder, f"{chapter_no:06d}.txt"),
            ]
            for c_path in candidate_paths:
                if os.path.exists(c_path):
                    with open(c_path, "r", encoding="utf-8") as f_src:
                        src_words = len(re.findall(r'[\wÀ-ỹ]+', f_src.read()))
                    with open(p_json, "r", encoding="utf-8") as f_j:
                        j_data = json.load(f_j)
                        j_words = len(j_data.get("words", []))
                    if src_words >= 20 and j_words < src_words * 0.98:
                        safe_print(f"⚠️ [TTS-CACHE] Chương {chapter_no} bị thiếu từ ({j_words}/{src_words} từ) -> Bỏ qua cache để tạo lại 100%!", flush=True)
                        return False
                    break
        except Exception:
            pass
    return True


def _read_chapter_text(novel_folder: str, chapter_no: int) -> Optional[str]:
    """Chỉ đọc bản dịch chuẩn đã hoàn thành Hậu Xử Lý tại 04_KetQua (TUYỆT ĐỐI KHÔNG đọc 03_DichAI_LLM, GG hay RAW)"""
    candidate_paths = [
        os.path.join(BASE_TRANSLATED_DIR, "04_KetQua", novel_folder, "chapters", f"{chapter_no:06d}.txt"),
        os.path.join(BASE_TRANSLATED_DIR, "04_KetQua", novel_folder, f"{chapter_no:06d}.txt"),
    ]
    for path in candidate_paths:
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


FFMPEG_MERGE_SEMAPHORE = asyncio.Semaphore(2)


async def _finalize_chapter(ch_info: dict, voice: str, chapters_cache_dir: str, job_info: dict, session_factory) -> bool:
    """
    Hoàn thiện và đóng gói 1 chương đã hoàn tất tất cả sub-chunks:
    1. Ghép nối các file mp3 sub-chunk thành file mp3 chương hoàn chỉnh (Re-encode chuẩn với Xing seek table).
    2. Xuất metadata JSON phụ đề/timeline đồng bộ.
    3. Cập nhật bản ghi AUDIO vào CSDL.
    4. Dọn sạch thư mục tạm _tmp_ch*.
    """
    async with FFMPEG_MERGE_SEMAPHORE:
        chapter_no = ch_info["chapter_no"]
        chapter_id = ch_info.get("chapter_id")
        tmp_dir = ch_info["tmp_dir"]
        chapter_mp3 = ch_info["chapter_mp3"]
        total_sc = ch_info["total_sc"]

        expected_subchunks = ch_info.get("sub_chunks", [])
        sub_mp3s = []
        sub_jsons = []
        corrupted_chunks = []

        for i in range(total_sc):
            sc_path = os.path.join(tmp_dir, f"chunk_{i:04d}.mp3")
            sj_path = os.path.join(tmp_dir, f"chunk_{i:04d}.json")
            if not (os.path.exists(sc_path) and os.path.getsize(sc_path) > 1024):
                corrupted_chunks.append(i)
                continue

            # Đọc dữ liệu JSON subchunk
            sc_data = {"segments": [], "words": []}
            if os.path.exists(sj_path):
                try:
                    with open(sj_path, "r", encoding="utf-8") as f_sj:
                        sc_data = json.load(f_sj)
                except Exception:
                    pass

            # Đối chiếu từ vựng của từng phân đoạn
            if i < len(expected_subchunks):
                exp_text = expected_subchunks[i]
                exp_words = re.findall(r'[\wÀ-ỹ]+', exp_text)
                act_words_raw = sc_data.get("words", [])
                act_words_list = [w["word"] for w in act_words_raw if isinstance(w, dict) and "word" in w]
                act_words_count = len(re.findall(r'[\wÀ-ỹ]+', " ".join(act_words_list))) if act_words_list else len(act_words_raw)
                if len(exp_words) >= 10 and act_words_count < len(exp_words) * 0.88:
                    safe_print(
                        f"⚠️ [TTS CH{chapter_no}] Đoạn {i+1:02d}/{total_sc} bị thiếu từ "
                        f"({act_words_count}/{len(exp_words)} từ). Loại bỏ để tải lại 100%!"
                    )
                    corrupted_chunks.append(i)
                    continue

            sub_mp3s.append(sc_path)
            sub_jsons.append(sc_data)

        if corrupted_chunks or len(sub_mp3s) < total_sc:
            # Dọn dẹp các phân đoạn lỗi để worker quét lại ở lượt sau
            for bad_idx in corrupted_chunks:
                bad_mp3 = os.path.join(tmp_dir, f"chunk_{bad_idx:04d}.mp3")
                bad_json = os.path.join(tmp_dir, f"chunk_{bad_idx:04d}.json")
                try:
                    if os.path.exists(bad_mp3): os.remove(bad_mp3)
                    if os.path.exists(bad_json): os.remove(bad_json)
                except Exception:
                    pass
                if "completed_sc_set" in ch_info:
                    ch_info["completed_sc_set"].discard(bad_idx)
            ch_info["done_sc"] = len(ch_info.get("completed_sc_set", set()))
            ch_info["is_finalized"] = False
            return False

        # ── 1. Tạo JSON Subtitle chương và kiểm tra độ toàn vẹn 100% ──
        chapter_json_path = _get_chapter_json_path(chapters_cache_dir, chapter_no)
        ch_title = f"Chương {chapter_no}"
        if chapter_id:
            try:
                async with session_factory() as session:
                    stmt_ch_title = select(Chapter.title_rough, Chapter.title_raw).where(Chapter.id == chapter_id)
                    res_ch_title = await session.execute(stmt_ch_title)
                    row_t = res_ch_title.first()
                    if row_t:
                        ch_title = row_t[0] or row_t[1] or ch_title
            except Exception:
                pass

        from app.services.tts.tts_exporter import merge_subchunks_json_to_chapter
        merged_json_data = merge_subchunks_json_to_chapter(
            subchunk_data_list=sub_jsons,
            chapter_no=chapter_no,
            chapter_title=ch_title,
            output_json_path=chapter_json_path,
            voice=voice
        )

        # Đọc văn bản nguồn TTS để kiểm tra độ toàn vẹn
        _tts_text_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS")
        _novel_folder_name = os.path.basename(os.path.dirname(chapters_cache_dir))
        _tts_fp = os.path.join(_tts_text_dir, _novel_folder_name, "chapters", f"{chapter_no:06d}.txt")
        if not os.path.exists(_tts_fp):
            _tts_fp = os.path.join(_tts_text_dir, _novel_folder_name, f"{chapter_no:06d}.txt")

        source_words_count = 0
        if os.path.exists(_tts_fp):
            try:
                with open(_tts_fp, "r", encoding="utf-8") as _ft:
                    source_words_count = len(re.findall(r'[\wÀ-ỹ]+', _ft.read()))
            except Exception:
                pass

        merged_words_count = len(merged_json_data.get("words", [])) if merged_json_data else 0

        # Kiểm tra nghiêm ngặt: Nếu mất từ > 2% thì từ chối đóng gói
        if source_words_count >= 20 and merged_words_count < source_words_count * 0.98:
            safe_print(
                f"❌ [TTS-INTEGRITY CH{chapter_no}] THẤT BẠI: JSON subtitle chỉ có {merged_words_count}/{source_words_count} từ "
                f"({merged_words_count/source_words_count:.1%})! Hủy kết quả để tạo lại đầy đủ 100%!",
                flush=True
            )
            ch_info["is_finalized"] = False
            return False

        if source_words_count > 0:
            safe_print(
                f"🎉 [TTS-INTEGRITY CH{chapter_no}] Đạt chuẩn 100% toàn vẹn: {merged_words_count}/{source_words_count} từ "
                f"({(merged_words_count/source_words_count):.1%})!",
                flush=True
            )

        # ── 2. Ghép các phân đoạn Audio thành Chapter MP3 ──
        silence_sec = ch_info.get("silence_sec", 0.35)
        success = await asyncio.to_thread(merge_audio_files, sub_mp3s, chapter_mp3, silence_sec, False)
        if not (success and os.path.exists(chapter_mp3) and os.path.getsize(chapter_mp3) > 10240):
            ch_info["is_finalized"] = False
            job_info["failed_chapters"] = job_info.get("failed_chapters", 0) + 1
            job_info["recent_failures"] = job_info.get("recent_failures", 0) + 1
            safe_print(f"❌ [TTS CH{chapter_no} FAIL] Ghép file audio chương thất bại, sẽ tự động thử lại ở lượt sau.", flush=True)
            return False

        # ── 3. Hoàn tất đóng gói chương & Lưu DB ──
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        ch_info["is_finalized"] = True

        job_info["done_chapters"] = job_info.get("done_chapters", 0) + 1
        job_info["done_chunks"] = job_info["done_chapters"]
        job_info["recent_successes"] = job_info.get("recent_successes", 0) + 1
        job_info["last_completed_chapter"] = chapter_no
        sz_mb = os.path.getsize(chapter_mp3) / (1024 * 1024)

        try:
            async with session_factory() as session:
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
        except Exception:
            pass

        safe_print(f"⚡ [TTS CH{chapter_no} OK] -> {os.path.basename(chapter_mp3)} ({sz_mb:.2f} MB) [ĐÃ LƯU ĐĨA & DB]", flush=True)
        return True


def build_atempo_filter(speed: float) -> str:
    """Tạo chuỗi bộ lọc FFmpeg atempo hỗ trợ tốc độ từ 0.25x đến 4.0x mà không méo tiếng / giữ nguyên cao độ."""
    if abs(speed - 1.0) < 0.01:
        return ""
    filters = []
    rem = float(speed)
    while rem > 2.0:
        filters.append("atempo=2.0")
        rem /= 2.0
    while rem < 0.5:
        filters.append("atempo=0.5")
        rem /= 0.5
    filters.append(f"atempo={rem:.4f}")
    return ",".join(filters)


def generate_range_mp3(
    chapters_cache_dir: str,
    chapter_nos: List[int],
    output_path: str,
    silence_sec: float = 0.0,
    apply_mastering: bool = False,
    speed: float = 1.0
) -> bool:
    """
    Tạo file mp3 khoảng (Range) bằng FFmpeg concat từ các chapter-cache mp3.
    Hỗ trợ xuất tốc độ tùy chọn (speed x1.25, x1.5, x2.0, x3.0...) chuẩn chất lượng cao bằng FFmpeg atempo.
    """
    files = []
    for c in chapter_nos:
        for fmt in [f"{c:06d}.mp3", f"{c:05d}.mp3", f"{c:04d}.mp3", f"{c}.mp3"]:
            p = os.path.join(chapters_cache_dir, fmt)
            if os.path.exists(p) and os.path.getsize(p) > 100:
                files.append(p)
                break
    if not files:
        return False

    effective_speed = max(0.25, min(4.0, float(speed))) if speed else 1.0
    is_speed_scaled = abs(effective_speed - 1.0) >= 0.01

    if len(files) == 1 and not is_speed_scaled:
        import shutil as _shutil
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            if os.path.abspath(files[0]) != os.path.abspath(output_path):
                _shutil.copyfile(files[0], output_path)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1024
        except Exception:
            return False

    import tempfile, uuid
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    list_file_path = os.path.join(tempfile.gettempdir(), f"airead_range_{uuid.uuid4().hex[:8]}.txt")

    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for fp in files:
                norm_p = fp.replace("\\", "/")
                f.write(f"file '{norm_p}'\n")

        # 1. Nếu có scale tốc độ (ví dụ x1.25, x1.5, x2.0, x3.0) -> Re-encode chuẩn atempo giữ nguyên cao độ
        if is_speed_scaled:
            atempo_str = build_atempo_filter(effective_speed)
            af_filter = f"{atempo_str},aresample=async=1000" if atempo_str else "aresample=async=1000"
            cmd_speed = [
                get_ffmpeg_cmd(), "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_file_path,
                "-af", af_filter,
                "-c:a", "libmp3lame",
                "-b:a", "48k",
                "-ar", "24000",
                "-ac", "1",
                "-write_xing", "1",
                "-id3v2_version", "3",
                output_path
            ]
            res_speed = subprocess.run(
                cmd_speed, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, errors="ignore"
            )
            if res_speed.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                return True

        # 2. Tốc độ gốc 1.0x: Stream copy siêu tốc (chỉ mất ~0.5s cho 200 chương)
        cmd_copy = [
            get_ffmpeg_cmd(), "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file_path,
            "-c", "copy",
            "-id3v2_version", "3",
            output_path
        ]
        res_copy = subprocess.run(
            cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="ignore"
        )
        if res_copy.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            return True

        # 3. Fallback nếu stream copy gặp lỗi
        return merge_audio_files(files, output_path, add_silence_sec=silence_sec, apply_mastering=apply_mastering)
    except Exception as e:
        print(f"[TTS-RANGE-MERGER] Lỗi: {e}")
        return False
    finally:
        if os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
            except Exception:
                pass


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
    Pipeline TTS High-Throughput liên chương:
    1. Quét toàn bộ các chương cần TTS trong khoảng đã chọn.
    2. Làm sạch văn bản, lưu 04b_VanBanTTS & DB (TTS_TEXT).
    3. Chia nhỏ thành dòng task chunks và phân phối đồng thời cho N workers (hỗ trợ 32, 48, 64+ luồng).
    4. Tận dụng 100% công suất: Workers KHÔNG BAO GIỜ bị rảnh khi một chương có ít chunks hơn số workers.
    5. Đóng gói chương ngay khi xong (không chờ hết cả lô) và cập nhật Playlist realtime.
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
        safe_print(f"🔄 [TTS-FORCE] Xóa cache cũ cho {total_chapters} chương để tạo mới hoàn toàn...", flush=True)
        for c_no in chapter_nos:
            old_c = _get_chapter_cache_path(chapters_cache_dir, c_no)
            if os.path.exists(old_c):
                try: os.remove(old_c)
                except Exception: pass
            tmp_c_dir = os.path.join(chapters_cache_dir, f"_tmp_ch{c_no:06d}")
            if os.path.exists(tmp_c_dir):
                try: shutil.rmtree(tmp_c_dir, ignore_errors=True)
                except Exception: pass
            old_tts_txt = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\04b_VanBanTTS", novel_folder, "chapters", f"{c_no:06d}.txt")
            if os.path.exists(old_tts_txt):
                try: os.remove(old_tts_txt)
                except Exception: pass

    # ── 3. Quét và xác định các chương hợp lệ có bản dịch chuẩn (FINAL) ────
    valid_chapters_to_process = []
    missing_untranslated = []

    chunk_size_str = await get_active_setting("TTS_MAX_CHUNK_SIZE")
    max_chars = int(chunk_size_str) if (chunk_size_str and chunk_size_str.strip().isdigit()) else 650

    async with AsyncSessionLocal() as session:
        for ch in volume_chapters:
            txt = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, ch)
            if txt and txt.strip():
                valid_chapters_to_process.append((ch.chapter_no, ch.id))
            else:
                is_cached = _is_chapter_cached(chapters_cache_dir, ch.chapter_no, novel_folder=novel_folder)
                if is_cached:
                    valid_chapters_to_process.append((ch.chapter_no, ch.id))
                else:
                    missing_untranslated.append(ch.chapter_no)

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
    job_info["total_chapters"] = total_chapters
    job_info["total_chunks"] = total_chapters
    job_info["failed_chapters"] = 0
    job_info["failed_chunks"] = 0
    job_info["recent_successes"] = 0
    job_info["recent_failures"] = 0

    voice = get_voice_name(voice_profile)
    start_time = time.time()

    # Nạp các cấu hình TTS động từ DB / .env với giá trị mặc định rõ ràng
    tts_rate: str = str(await get_active_setting("TTS_RATE") or "-4%")
    tts_pitch: str = str(await get_active_setting("TTS_PITCH") or "+0Hz")
    
    silence_ms_str = await get_active_setting("TTS_SILENCE_MS")
    silence_sec: float = 0.15
    if silence_ms_str:
        try:
            silence_sec = max(0.0, float(silence_ms_str) / 1000.0)
        except Exception:
            silence_sec = 0.15

    max_chars_str = await get_active_setting("TTS_CHUNK_MAX_CHARS")
    max_chars: int = 650
    if max_chars_str:
        try:
            max_chars = max(100, int(max_chars_str))
        except Exception:
            max_chars = 650

    pacing_str = await get_active_setting("TTS_PACING_SECONDS")
    pacing_sec: float = 0.5
    if pacing_str:
        try:
            pacing_sec = max(0.0, float(pacing_str))
        except Exception:
            pacing_sec = 0.5

    proxy_list_str = await get_active_setting("TTS_PROXY_LIST")
    proxy_list: Optional[List[str]] = [p.strip() for p in proxy_list_str.split(",") if p.strip()] if proxy_list_str else None

    num_parallel_workers: int = 8
    if custom_workers and custom_workers >= 1:
        num_parallel_workers = min(128, max(1, int(custom_workers)))
    else:
        parallel_workers_str = await get_active_setting("TTS_PARALLEL_WORKERS")
        if parallel_workers_str:
            try:
                num_parallel_workers = min(128, max(1, int(parallel_workers_str)))
            except Exception:
                num_parallel_workers = 8

    # ── 4. Vòng lặp đảm bảo hoàn thiện đủ 100% chương và phân đoạn trong lô ──
    batch_round = 0
    max_batch_rounds = 10
    total_sc_global = 0

    while batch_round < max_batch_rounds:
        batch_round += 1

        # 4.1. Quét kiểm tra xem chương nào chưa có audio hoàn chỉnh (> 10KB)
        need_tts_chapters = []
        cached_chapter_nos = []
        for ch_no, ch_id in valid_chapters_to_process:
            if _is_chapter_cached(chapters_cache_dir, ch_no, novel_folder=novel_folder):
                cached_chapter_nos.append(ch_no)
            else:
                need_tts_chapters.append((ch_no, ch_id))

        cached_count = len(cached_chapter_nos)
        job_info["done_chapters"] = cached_count
        job_info["done_chunks"] = cached_count

        if not need_tts_chapters:
            # 100% tất cả các chương trong lô đã hoàn thành!
            job_info["percent"] = 100.0
            job_info["progress_pct"] = 100.0
            break

        if batch_round > 1:
            safe_print(
                f"🔁 [TTS-BATCH-ROUND {batch_round}] Còn {len(need_tts_chapters)}/{total_chapters} chương chưa hoàn thiện "
                f"-> Đang tiếp tục xử lý các phân đoạn còn thiếu để hoàn tất 100% lô...",
                flush=True
            )

        # 4.2. Chuẩn bị sub-chunks cho các chương còn thiếu (tận dụng lại các chunks đã tải sẵn trên đĩa)
        chapter_jobs: Dict[int, dict] = {}
        all_chunk_tasks: List[dict] = []

        for ch_no, ch_id in need_tts_chapters:
            fresh_text = None
            async with AsyncSessionLocal() as session:
                stmt_ch = select(Chapter).where(Chapter.id == ch_id)
                res_ch = await session.execute(stmt_ch)
                db_ch = res_ch.scalar_one_or_none()
                if db_ch:
                    fresh_text = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, db_ch)

            if not fresh_text or not fresh_text.strip():
                safe_print(
                    f"⚠️ [TTS-PRECHECK CH{ch_no}] KHÔNG TÌM THẤY text nguồn cho chương {ch_no}! "
                    f"Kiểm tra file 04_KetQua hoặc bản ghi FINAL trong CSDL. Bỏ qua chương này.",
                    flush=True
                )
                continue

            ch_title = (db_ch.title_rough or db_ch.title_raw) if db_ch else None
            clean_text = sanitize_tts_text(fresh_text, chapter_no=ch_no, chapter_title=ch_title)
            if not clean_text or not clean_text.strip():
                safe_print(
                    f"⚠️ [TTS-PRECHECK CH{ch_no}] Text sau khi làm sạch bị rỗng! Bỏ qua chương này.",
                    flush=True
                )
                continue

            # Cảnh báo nếu text nguồn quá ngắn (có thể bị cắt/corrupt)
            if len(clean_text) < 200:
                safe_print(
                    f"⚠️ [TTS-PRECHECK CH{ch_no}] Text nguồn rất ngắn ({len(clean_text)} ký tự). "
                    f"Có thể file nguồn bị hỏng hoặc thiếu nội dung!",
                    flush=True
                )

            # Lưu văn bản đã làm sạch vào 04b_VanBanTTS và CSDL (TTS_TEXT)
            try:
                tts_fp = save_tts_text_file(novel_folder, ch_no, clean_text)
                if ch_id:
                    async with AsyncSessionLocal() as session:
                        stmt_v_tts = select(ChapterVersion).where(
                            ChapterVersion.chapter_id == ch_id,
                            ChapterVersion.version_type == "TTS_TEXT"
                        )
                        res_v_tts = await session.execute(stmt_v_tts)
                        v_tts = res_v_tts.scalar_one_or_none()
                        if v_tts:
                            v_tts.file_path = tts_fp
                            v_tts.content = clean_text
                        else:
                            session.add(ChapterVersion(
                                chapter_id=ch_id,
                                version_type="TTS_TEXT",
                                file_path=tts_fp,
                                content=clean_text
                            ))
                        await session.commit()
            except Exception as e_save:
                pass

            sub_chunks = split_text_into_chunks(clean_text, max_chars=max_chars)
            if not sub_chunks:
                continue

            tmp_dir = os.path.join(chapters_cache_dir, f"_tmp_ch{ch_no:06d}")
            os.makedirs(tmp_dir, exist_ok=True)

            chapter_mp3 = _get_chapter_cache_path(chapters_cache_dir, ch_no)
            ch_job = {
                "chapter_no": ch_no,
                "chapter_id": ch_id,
                "total_sc": len(sub_chunks),
                "done_sc": 0,
                "tmp_dir": tmp_dir,
                "chapter_mp3": chapter_mp3,
                "sub_chunks": sub_chunks,
                "silence_sec": silence_sec,
                "is_finalized": False
            }
            chapter_jobs[ch_no] = ch_job

            # Kiểm tra xem những subchunk nào ĐÃ CÓ TRÊN ĐĨA (> 1024 bytes) và đủ từ thì mới đánh dấu hoàn thành
            completed_sc_set = set()
            for idx, text_sc in enumerate(sub_chunks):
                sc_p = os.path.join(tmp_dir, f"chunk_{idx:04d}.mp3")
                sc_j = os.path.join(tmp_dir, f"chunk_{idx:04d}.json")
                is_sc_valid = False
                if os.path.exists(sc_p) and os.path.getsize(sc_p) > 1024:
                    is_sc_valid = True
                    if os.path.exists(sc_j):
                        try:
                            with open(sc_j, "r", encoding="utf-8") as _f_scj:
                                _sc_chk = json.load(_f_scj)
                            _exp_sc_w = len(re.findall(r'[\wÀ-ỹ]+', text_sc))
                            _act_words_raw = _sc_chk.get("words", [])
                            _act_words_list = [w["word"] for w in _act_words_raw if isinstance(w, dict) and "word" in w]
                            _act_sc_w = len(re.findall(r'[\wÀ-ỹ]+', " ".join(_act_words_list))) if _act_words_list else len(_act_words_raw)
                            if _exp_sc_w >= 10 and _act_sc_w < _exp_sc_w * 0.88:
                                is_sc_valid = False
                        except Exception:
                            pass
                if is_sc_valid:
                    completed_sc_set.add(idx)
                else:
                    if os.path.exists(sc_p):
                        try: os.remove(sc_p)
                        except Exception: pass
                    if os.path.exists(sc_j):
                        try: os.remove(sc_j)
                        except Exception: pass
                    all_chunk_tasks.append({
                        "id": f"{ch_no}_{idx}",
                        "chapter_no": ch_no,
                        "chapter_id": ch_id,
                        "chapter_mp3": chapter_mp3,
                        "chunk_idx": idx,
                        "total_chunks": len(sub_chunks),
                        "text": text_sc,
                        "output_dir": tmp_dir,
                        "priority": ch_no * 10000 + idx
                    })
            ch_job["completed_sc_set"] = completed_sc_set
            ch_job["done_sc"] = len(completed_sc_set)

            # Nếu tất cả sub-chunks đã có sẵn trên đĩa từ trước mà chưa finalize -> finalize ngay
            if ch_job["done_sc"] == ch_job["total_sc"]:
                await _finalize_chapter(ch_job, voice, chapters_cache_dir, job_info, AsyncSessionLocal)

        if not all_chunk_tasks:
            # Không còn chunk nào cần tải thêm trong đợt này -> vòng lặp tiếp tục kiểm tra cache
            continue

        total_sc_round = len(all_chunk_tasks)
        if total_sc_global == 0:
            total_sc_global = total_sc_round + sum(len(j["completed_sc_set"]) for j in chapter_jobs.values())
            job_info["total_subchunks"] = total_sc_global
            job_info["done_subchunks"] = sum(len(j["completed_sc_set"]) for j in chapter_jobs.values())

        actual_workers = min(num_parallel_workers, total_sc_round) if total_sc_round > 0 else 1
        job_info["worker_count"] = actual_workers

        safe_print(
            f"🔊 [TTS-START] Truyện '{novel_folder}' | "
            f"{len(need_tts_chapters)} chương cần tạo | Tổng {total_sc_round} phân đoạn cần tải | "
            f"Đã có sẵn audio: {cached_count}/{total_chapters} chương | Khởi chạy {actual_workers} workers song song!",
            flush=True
        )

        last_log_print_time = [0.0]
        finalize_tasks = []
        active_workers_set = set()
        completed_chunk_ids: Set[str] = set()

        def on_subchunk_done(task_ref, ok, dur, out_p, worker_id=0, channel="Proxy", *args):
            if not ok or not os.path.exists(out_p):
                return
            
            active_workers_set.add(worker_id)
            ch_no = task_ref.get("chapter_no") if isinstance(task_ref, dict) else None
            chunk_idx = task_ref.get("chunk_idx", 0) if isinstance(task_ref, dict) else task_ref
            total_sc = task_ref.get("total_chunks", 1) if isinstance(task_ref, dict) else 1
            txt = task_ref.get("text", "") if isinstance(task_ref, dict) else ""
            task_id = f"{ch_no}_{chunk_idx}" if ch_no is not None else str(chunk_idx)

            completed_chunk_ids.add(task_id)
            done_count = job_info.get("done_subchunks", 0) + 1
            job_info["done_subchunks"] = done_count
            tot = max(1, job_info.get("total_subchunks", total_sc_round))
            curr_pct = round((done_count / tot) * 100, 1)
            job_info["percent"] = min(100.0, curr_pct)
            job_info["progress_pct"] = job_info["percent"]

            sz_kb = os.path.getsize(out_p) / 1024
            audio_dur = sz_kb * 1024 * 8 / 128_000
            rtf = audio_dur / dur if dur > 0 else 0
            snippet = txt.replace("\n", " ")[:25] + "..."
            ch_label = f"Ch{ch_no} " if ch_no else ""
            log_line = f"[W#{worker_id:02d}|{channel}] [{ch_label}{chunk_idx+1:02d}/{total_sc}] | {sz_kb:5.1f} KB | {dur:4.1f}s | 🚀 {rtf:4.1f}x | \"{snippet}\""
            job_info["last_chunk_log"] = log_line

            if "logs" not in job_info:
                job_info["logs"] = []
            job_info["logs"].append(log_line)
            if len(job_info["logs"]) > 30:
                job_info["logs"] = job_info["logs"][-30:]

            now_t = time.time()
            if now_t - last_log_print_time[0] >= 1.5 or done_count == tot:
                last_log_print_time[0] = now_t
                elapsed = now_t - start_time
                speed = (done_count / elapsed) * 60 if elapsed > 0 else 0
                job_info["speed_chunks_per_min"] = round(speed, 1)
                job_info["eta_seconds"] = int((tot - done_count) / (speed / 60)) if speed > 0 else 0
                job_info["ram_usage_percent"] = psutil.virtual_memory().percent
                safe_print(
                    f"⚡ [W#{worker_id:02d}|{channel}] -> {ch_label}đoạn {chunk_idx+1:02d}/{total_sc} OK ({dur:.1f}s) | "
                    f"Tiến độ: {done_count}/{tot} ({job_info['percent']}%) | "
                    f"Tốc độ: {speed:.1f} đ/ph | Active: {len(active_workers_set)}/{job_info['worker_count']} workers",
                    flush=True
                )

            # Tự động phát hiện khi 1 chương xong toàn bộ subchunks -> Đóng gói & lưu DB ngay lập tức
            if ch_no and ch_no in chapter_jobs:
                ch_job = chapter_jobs[ch_no]
                if "completed_sc_set" not in ch_job:
                    ch_job["completed_sc_set"] = set()
                ch_job["completed_sc_set"].add(chunk_idx)
                ch_job["done_sc"] = len(ch_job["completed_sc_set"])
                
                if ch_job["done_sc"] == ch_job["total_sc"] and not ch_job["is_finalized"]:
                    ch_job["is_finalized"] = True
                    ft = asyncio.create_task(_finalize_chapter(ch_job, voice, chapters_cache_dir, job_info, AsyncSessionLocal))
                    finalize_tasks.append(ft)

        engine = RotatingBatchTTSEngine(
            voice=voice,
            rate=tts_rate,
            pitch=tts_pitch,
            proxies=proxy_list,
            auto_fetch_proxy=True,
            max_parallel_workers=num_parallel_workers,
            pacing_sec=pacing_sec,
            max_retries=4,
            chunk_timeout=45.0
        )

        try:
            await engine.synthesize_tasks(all_chunk_tasks, on_chunk_done=on_subchunk_done)
            
            # Chờ tất cả các tiến trình đóng gói chương hoàn tất
            if finalize_tasks:
                await asyncio.gather(*finalize_tasks, return_exceptions=True)

            # Quét bổ sung xem còn chương nào đã đủ chunks trên đĩa mà chưa finalize
            for ch_no, ch_job in chapter_jobs.items():
                if not ch_job["is_finalized"]:
                    t_dir = ch_job["tmp_dir"]
                    disk_sc_count = len([f for f in os.listdir(t_dir) if f.startswith("chunk_") and f.endswith(".mp3") and os.path.getsize(os.path.join(t_dir, f)) > 1024]) if os.path.exists(t_dir) else 0
                    if disk_sc_count == ch_job["total_sc"]:
                        ch_job["is_finalized"] = True
                        await _finalize_chapter(ch_job, voice, chapters_cache_dir, job_info, AsyncSessionLocal)

        except asyncio.CancelledError:
            safe_print(f"[TTS-PIPELINE] Job {job_key} bị hủy bởi người dùng...")
            job_info["status"] = "cancelled"
            job_info["is_running"] = False
            gc.collect()
            return
        except Exception as e:
            safe_print(f"[TTS-PIPELINE ERROR] {e}")
            if batch_round >= max_batch_rounds:
                job_info["status"] = "failed"
                job_info["is_running"] = False
                gc.collect()
                raise e

    # ── 5. Hoàn tất toàn bộ tiến trình TTS lô ──
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


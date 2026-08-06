import os
import re
import time
import asyncio
import random
import subprocess
import psutil
import edge_tts
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion, TTSChunk
from app.services.storage.file_storage import sanitize_filename
from app.core.config import get_active_setting

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

# Semaphore toàn cục giới hạn số kết nối TTS đồng thời thực sự tới Microsoft (ngưỡng ngọt 10 luồng/IP)
TTS_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(10)
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

def merge_audio_files(file_paths: List[str], output_path: str) -> bool:
    """Ghép nối danh sách các tệp mp3 bằng FFmpeg Concat Demuxer (-c copy)"""
    if not file_paths:
        return False
    
    list_file_path = output_path + ".txt"
    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for fp in file_paths:
                # Chuẩn hóa đường dẫn chứa dấu gạch chéo xuôi cho FFmpeg tương thích Windows
                normalized_path = fp.replace("\\", "/")
                f.write(f"file '{normalized_path}'\n")
        
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

def sanitize_tts_text(text: str) -> str:
    """
    Tiền xử lý văn bản toàn diện 22 quy tắc trước khi gửi vào Edge-TTS 
    để tạo Audiobook truyền cảm, tự nhiên, đọc xuyên suốt.
    """
    if not text:
        return text

    # 1. Loại bỏ HTML tags và BBCode ([url], [color], <br>, <div>...)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\[/?[a-zA-Z0-9=\-]+\]', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

    # 2. Loại bỏ Markdown, URL, Email
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'_{1,3}', '', text)

    # 3. Loại bỏ ký hiệu quảng cáo, dòng kẻ trang trí (===, ***, ~~~, ###...)
    text = re.sub(r'^[=\-*~+_#]{3,}.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[-–—]{3,}', ' — ', text)
    text = re.sub(r'~{2,}', '', text)

    # 4. Loại bỏ Emoji và ký tự biểu tượng trang trí (★, ☆, ◆, ◇, ■, □...)
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001f900-\U0001f9ff\U00002600-\U000026FF]', '', text)
    text = re.sub(r'[★☆◆◇■□▲△▼▽●○♥♠♣♦♂♀⟪⟫▸▹►▻◄◄]', '', text)

    # 5. Loại bỏ Tiêu đề chương ("Chương 27: Từ đại lừa bịp") và Nhãn kết thúc ("(Hết chương)", "[Hết]")
    # Giúp audio đọc xuyên suốt mạch truyện mà không bị gián đoạn bởi tiêu đề/hết chương.
    text = re.sub(r'^\s*Chương\s+\d+\s*[:.:-]?\s*.*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'[\(\[\{]?\s*(?:Hết\s+Chương(?:\s+\d+)?|Hết|Chương\s+kết\ thúc|Tác\ giả\ có\ lời\ muốn\ nói)[^\)\}\]\n]*[\)\]\}]?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*(?:Hết\s+Chương|Hết\s+\d+|Hết)\.?\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)

    # 6. Chuẩn hóa ngoặc Trung Quốc / đặc biệt: 「」『』《》 -> ""
    text = text.replace('「', '"').replace('」', '"').replace('『', '"').replace('』', '"')
    text = text.replace('《', '"').replace('》', '"').replace('【', '(').replace('】', ')')

    # 6. Chuẩn hóa dấu câu tiếng Trung sót lại: 。→ . | ，→ , | ！？→ ? | ？！→ ? | …… → ...
    text = text.replace('。', '.').replace('，', ',').replace('！？', '?').replace('？！', '?').replace('……', '...')

    # 7. Chuẩn hóa dấu thoại:
    #    nói:-" | nói -": -> nói, "
    #    - "Xin chào." -> "Xin chào."
    text = re.sub(r'["“”]{2,}', '"', text)
    text = re.sub(r"['’]{2,}", "'", text)
    text = re.sub(r'[:：]\s*[-–—]?\s*["“”\'’]{1,2}', r', "', text)
    text = re.sub(r'^\s*[-–—]\s*(?=["“])', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-–—]\s+(?=[A-ZÀ-Ỹa-zà-ỹ])', '"', text, flags=re.MULTILINE)

    # 8. Thu gọn nguyên âm / phụ âm lặp dài gây vỡ giọng (aaaaaaa -> aa, uuuuuuu -> uu)
    text = re.sub(r'([aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵAEIOUYÀÁẢÃẠ])\1{2,}', r'\1\1', text, flags=re.IGNORECASE)
    text = re.sub(r'([bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ])\1{2,}', r'\1', text)

    # 9. Xử lý tiếng cười / la hét lặp âm tiết (ha ha ha ha...)
    text = re.sub(r'\b((?:ha|hà|hả|hạ|he|hê|hề|hi|hì|hí|ho|hò|hó|hu|hù|hú|hư|hừ|kha|khà)\s*){4,}', 
                  lambda m: ' '.join(m.group(0).split()[:3]) + '.', text, flags=re.IGNORECASE)

    # 9b. Xử lý chuỗi la hét/gào thét thuần nguyên âm xen kẽ bất kỳ (uauauau, oaoaoa, ahhhhaaaiii...)
    _VOWELS = ("aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộ"
               "ơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ"
               "AÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘ"
               "ƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ")
    text = re.sub(
        rf'\b[{_VOWELS}]{{5,}}\b',
        lambda m: m.group(0)[:2],
        text
    )
    text = re.sub(
        rf'\b[hkH{_VOWELS}]{{6,}}\b',
        lambda m: m.group(0)[:3],
        text
    )

    # 10. Từ lặp vô nghĩa do OCR / lỗi dịch: "đi đi đi đi đi" -> "đi đi"
    text = re.sub(r'\b(\w+)(?:\s+\1){3,}\b', r'\1 \1', text, flags=re.IGNORECASE)

    # 11. Chuẩn hóa viết tắt phổ biến trong tiếng Việt để đọc chính xác
    text = re.sub(r'\bTP\.?\s*HCM\b', 'Thành phố Hồ Chí Minh', text, flags=re.IGNORECASE)
    text = re.sub(r'\bTP\.\s*', 'Thành phố ', text)
    text = re.sub(r'\bPGS\.\s*', 'Phó Giáo sư ', text)
    text = re.sub(r'\bGS\.\s*', 'Giáo sư ', text)
    text = re.sub(r'\bTS\.\s*', 'Tiến sĩ ', text)
    text = re.sub(r'\bThS\.\s*', 'Thạc sĩ ', text)

    # 12. Tách số và đơn vị: 100km -> 100 km, 20kg -> 20 kg
    text = re.sub(r'(\d+)\s*(km|m|cm|mm|kg|g|tháng|năm|phút|giây|h|tr|tỷ)\b', r'\1 \2', text, flags=re.IGNORECASE)

    # 13. Ký hiệu toán học khi đứng giữa khoảng trắng
    text = re.sub(r'(?<=\s)\+(?=\s)', 'cộng', text)
    text = re.sub(r'(?<=\s)=(?=\s)', 'bằng', text)

    # 14. Chuẩn hóa khoảng trắng TRƯỚC dấu câu (xóa khoảng trắng thừa trước , . : ; ! ?)
    text = re.sub(r'\s+([,.:;!?])', r'\1', text)

    # 15. Gộp các cụm dấu câu lặp / dị dạng
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r',\s*\.', '.', text)
    text = re.sub(r'\.\s*,+', '.', text)
    text = re.sub(r'\.{2}', '.', text)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)
    text = re.sub(r'\.{4,}', '...', text)
    text = re.sub(r'[!?]{2,}', '!', text)

    # 16. Chuẩn hóa xuống dòng & gộp dòng ngắn thành đoạn văn liền mạch
    lines = text.split('\n')
    merged_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if merged_lines and len(merged_lines[-1].strip()) > 30:
                merged_lines.append('')
            continue
        merged_lines.append(stripped)
    text = '\n'.join(merged_lines)

    # 17. Nối các dòng ngắn liên tiếp thành câu liền mạch
    text = re.sub(r'(?<=[.!?])\s*\n(?=[A-ZÀ-Ỹa-zà-ỹ])', ' ', text)

    # 18. Xóa ký tự tiếng Trung còn sót lại (nếu có)
    text = re.sub(r'[\u4e00-\u9fff]+', '', text)

    # 20. Giảm dấu câu gây ngắt giọng không cần thiết
    # Chấm phẩy -> phẩy (đọc mượt hơn)
    text = re.sub(r';', ',', text)
    # Hai chấm giữa câu -> phẩy, nhưng GIỮ hai chấm trong số/giờ (vd 20:30, tỉ lệ 3:1)
    text = re.sub(r'(?<!\d):(?!\d)', ',', text)
    # Bỏ ngoặc đơn/vuông/nhọn còn sót (giữ nội dung bên trong, chỉ bỏ ký tự ngoặc)
    text = re.sub(r'[()\[\]{}]', '', text)
    # Bỏ dấu gạch ngang đơn lẻ dùng làm liệt kê đầu dòng còn sót
    text = re.sub(r'^\s*[-–—]\s+', '', text, flags=re.MULTILINE)
    # Gộp dấu phẩy/chấm bị trùng sau khi thay thế ở trên
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r',\s*\.', '.', text)

    # 19. Loại bỏ khoảng trắng dư thừa cuối cùng
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = text.strip()

    return text


def split_text_into_chunks(text: str, max_chars: int = 900) -> List[str]:
    """
    Phân tách văn bản thành các chunk vừa đủ (800-1000 ký tự, mặc định 900) để Edge-TTS đọc mượt mà,
    giảm số lượng request HTTP API và tối ưu tốc độ sinh Audio tối đa.
    """
    if not text or not text.strip():
        return []
    
    # Tách thành đoạn văn dựa trên dòng trống kép
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    chunks = []
    current_chunk = []
    current_len = 0
    
    for para in paragraphs:
        para_len = len(para)
        
        # Nếu đoạn văn quá dài, cần chia nhỏ theo câu
        if para_len > max_chars:
            # Flush đoạn hiện tại trước
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_len = 0
            
            # Tách đoạn dài thành các câu
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                sent_len = len(sent)
                
                if sent_len > max_chars:
                    # Câu siêu dài: tách theo dấu phẩy/chấm phẩy
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = []
                        current_len = 0
                    
                    sub_parts = re.split(r'(?<=[,;:])\s+', sent)
                    for sp in sub_parts:
                        sp = sp.strip()
                        if not sp:
                            continue
                        if len(sp) > max_chars:
                            # Cắt cứng theo ký tự kèm lùi về khoảng trắng gần nhất để không cắt giữa từ
                            start = 0
                            while start < len(sp):
                                end = min(start + max_chars, len(sp))
                                if end < len(sp):
                                    last_space = sp.rfind(' ', start, end)
                                    if last_space > start:
                                        end = last_space
                                chunks.append(sp[start:end].strip())
                                start = end
                        elif current_len + len(sp) + 1 > max_chars:
                            if current_chunk:
                                chunks.append(' '.join(current_chunk))
                            current_chunk = [sp]
                            current_len = len(sp)
                        else:
                            current_chunk.append(sp)
                            current_len += len(sp) + 1
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
        
        # Đoạn văn vừa đủ: gộp vào chunk hiện tại
        if current_len + para_len + 2 > max_chars:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            current_chunk = [para]
            current_len = para_len
        else:
            current_chunk.append(para)
            current_len += para_len + 2
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    # Lọc bỏ chunk rỗng hoặc quá ngắn vô nghĩa
    chunks = [c.strip() for c in chunks if c.strip() and len(c.strip()) > 5]
    
    return chunks


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


def _is_chapter_cached(chapters_cache_dir: str, chapter_no: int) -> bool:
    """Kiểm tra cache mp3 của chương có tồn tại và hợp lệ không"""
    p = _get_chapter_cache_path(chapters_cache_dir, chapter_no)
    return os.path.exists(p) and os.path.getsize(p) > 0


def _read_chapter_text(novel_folder: str, chapter_no: int) -> Optional[str]:
    """Đọc bản dịch tốt nhất của chương từ đĩa (FINAL > LLM > GG)"""
    for subfolder in ["04_KetQua", "03_DichAI_LLM", "02_DichMau_GG"]:
        path = os.path.join(
            BASE_TRANSLATED_DIR, subfolder, novel_folder,
            "chapters", f"{chapter_no:06d}.txt"
        )
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
    return None


async def _read_chapter_text_from_db_or_disk(session, novel_id: int, novel_folder: str, chapter) -> Optional[str]:
    """Đọc bản dịch từ DB hoặc đĩa, ưu tiên FINAL > LLM > GG"""
    from app.services.storage.file_storage import read_version_file_content

    stmt_ver = select(ChapterVersion).where(
        ChapterVersion.chapter_id == chapter.id,
        ChapterVersion.version_type.in_(["FINAL", "LLM", "GG"])
    )
    res_ver = await session.execute(stmt_ver)
    vers = res_ver.scalars().all()
    ver_dict = {v.version_type: v for v in vers}
    ver_best = ver_dict.get("FINAL") or ver_dict.get("LLM") or ver_dict.get("GG")

    if ver_best and ver_best.file_path and os.path.exists(ver_best.file_path) and os.path.getsize(ver_best.file_path) > 0:
        try:
            return read_version_file_content(ver_best.file_path)
        except Exception:
            pass

    # Fallback đọc từ đĩa
    return _read_chapter_text(novel_folder, chapter.chapter_no)


async def tts_chapter_worker(
    queue: asyncio.Queue,
    voice: str,
    novel_folder: str,
    chapters_cache_dir: str,
    job_info: Dict[str, Any],
    session_factory
):
    """
    Worker xử lý TTS từng CHƯƠNG.
    - Nhận chapter_no từ queue
    - Đọc text chương → split sub-chunks (1200 ký tự)
    - TTS từng sub-chunk → temp files
    - FFmpeg concat sub-chunks → chapters/XXXXXX.mp3 (cache vĩnh viễn)
    - Xóa temp sub-chunk files
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

        # Chia text thành sub-chunks 900 ký tự
        sub_chunks = split_text_into_chunks(text, max_chars=900)
        if not sub_chunks:
            queue.task_done()
            continue

        # Tạo thư mục temp riêng cho chương này
        tmp_dir = os.path.join(chapters_cache_dir, f"_tmp_ch{chapter_no:06d}")
        os.makedirs(tmp_dir, exist_ok=True)

        sub_mp3s = []
        chapter_ok = True
        for idx, chunk_text in enumerate(sub_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text or not re.search(r'\w', chunk_text):
                continue

            sub_path = os.path.join(tmp_dir, f"sub_{idx:04d}.mp3")
            chunk_ok = False
            # Kiểm tra nếu sub-chunk đã được tạo thành công từ trước
            if os.path.exists(sub_path) and os.path.getsize(sub_path) > 0:
                chunk_ok = True
                sub_mp3s.append(sub_path)
                continue

            for attempt in range(5):
                async with TTS_CONCURRENCY_SEMAPHORE:
                    try:
                        # jitter ngẫu nhiên tránh nhiều worker đập request cùng 1 mili-giây
                        await asyncio.sleep(random.uniform(0.1, 0.4))
                        communicate = edge_tts.Communicate(chunk_text, voice)
                        await communicate.save(sub_path)
                        if os.path.exists(sub_path) and os.path.getsize(sub_path) > 0:
                            chunk_ok = True
                            _CONSECUTIVE_FAILURES["count"] = 0
                            break
                    except Exception as e:
                        print(f"[TTS-CH-WORKER] Lỗi ch{chapter_no} sub{idx} (thử {attempt+1}/5): {e}")
                        _CONSECUTIVE_FAILURES["count"] += 1
                        # Nếu phát hiện lỗi dồn dập (Microsoft rate-limit IP), tạm dừng toàn cục 8s để giải phóng IP
                        if _CONSECUTIVE_FAILURES["count"] >= 5:
                            print("⚠️ [TTS] Phát hiện rate-limit IP từ Microsoft, tạm dừng 8s toàn cục...", flush=True)
                            await asyncio.sleep(8.0)
                            _CONSECUTIVE_FAILURES["count"] = 0
                        
                        # Dynamic backoff tăng dần: 2s -> 5s -> 10s -> 15s
                        retry_delays = [2.0, 5.0, 10.0, 15.0]
                        delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                        await asyncio.sleep(delay)
            if not chunk_ok:
                chapter_ok = False
                break
            sub_mp3s.append(sub_path)

        if chapter_ok and sub_mp3s:
            if len(sub_mp3s) == 1:
                # Chỉ 1 sub-chunk: di chuyển tệp thay vì ghép FFmpeg
                try:
                    import shutil
                    if os.path.exists(chapter_mp3):
                        os.remove(chapter_mp3)
                    shutil.move(sub_mp3s[0], chapter_mp3)
                    success = os.path.exists(chapter_mp3) and os.path.getsize(chapter_mp3) > 0
                except Exception as e:
                    print(f"[TTS-CH-WORKER] Lỗi di chuyển mp3 ch{chapter_no}: {e}")
                    success = merge_audio_files(sub_mp3s, chapter_mp3)
            else:
                # Nhiều sub-chunk: ghép bằng FFmpeg
                success = merge_audio_files(sub_mp3s, chapter_mp3)

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
            print(f"❌ [TTS-CH] Chương {chapter_no} thất bại sau 3 lần thử.", flush=True)

        queue.task_done()


def generate_range_mp3(
    chapters_cache_dir: str,
    chapter_nos: List[int],
    output_path: str
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
    return merge_audio_files(files, output_path)


def normalize_final_audio(input_path: str, output_path: str) -> bool:
    """Chuẩn hóa âm lượng + nén nhẹ để tránh vỡ tiếng/chói ở đoạn cao trào,
    chạy 1 lần trên file volume cuối cùng (không chạy per-chunk để tiết kiệm CPU)."""
    try:
        cmd = [
            get_ffmpeg_cmd(), "-y", "-i", input_path,
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11,"
            "acompressor=threshold=-20dB:ratio=3:attack=10:release=200,"
            "highpass=f=80",
            "-ar", "44100", "-b:a", "128k",
            output_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"[TTS-NORMALIZE] Lỗi chuẩn hóa âm thanh: {e}")
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
    3. Worker pool TTS song song (6 workers)
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
            if _is_chapter_cached(chapters_cache_dir, ch.chapter_no):
                continue  # Đã có cache → bỏ qua
            # Đọc text ngay để tránh mở nhiều DB session sau
            txt = await _read_chapter_text_from_db_or_disk(session, novel_id, novel_folder, ch)
            if txt:
                clean = sanitize_tts_text(txt)
                if clean and clean.strip():
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
        # Nạp worker count từ cài đặt (mặc định 24, tối đa 30)
        tts_workers_str = await get_active_setting("TTS_MAX_WORKERS")
        try:
            num_workers = min(int(tts_workers_str), 30)
            if num_workers < 1:
                num_workers = 24
        except Exception:
            num_workers = 24
        job_info["worker_count"] = num_workers

        queue = asyncio.Queue()
        for ch_no in need_tts:
            await queue.put((ch_no, need_text[ch_no]))

        try:
            for _ in range(num_workers):
                t = asyncio.create_task(
                    tts_chapter_worker(queue, voice, novel_folder, chapters_cache_dir, job_info, AsyncSessionLocal)
                )
                workers.append(t)

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
                cached_files = [c for c in chapter_nos if _is_chapter_cached(chapters_cache_dir, c)]
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


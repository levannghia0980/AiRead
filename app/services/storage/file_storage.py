import os
import re
import gc
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

# Root Output Directory: d:\NENGHIA0980\AIREAD\Output
OUTPUT_ROOT = Path("d:/NENGHIA0980/AIREAD/Output")

# Các thư mục chuẩn lưu trữ dữ liệu Output
VERSION_FOLDER_MAP: Dict[str, str] = {
    "RAW": "01_BanGoc",
    "LLM": "03_DichAI_LLM",
    "FINAL": "04_KetQua",
    "TTS_TEXT": "04b_VanBanTTS",
    "AUDIO": "05_Audio_TTS",
    "METADATA": "06_Metadata"
}

def sanitize_filename(name: str) -> str:
    """Loại bỏ các ký tự cấm trong tên file/thư mục hệ thống Windows"""
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def init_output_directories():
    """Tạo đúng các thư mục chuẩn trong Output"""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Xóa các thư mục dư thừa cũ nếu có
    for item in OUTPUT_ROOT.iterdir():
        if item.is_dir() and item.name not in VERSION_FOLDER_MAP.values():
            shutil.rmtree(item, ignore_errors=True)
            
    for folder_name in VERSION_FOLDER_MAP.values():
        (OUTPUT_ROOT / folder_name).mkdir(parents=True, exist_ok=True)

def get_version_dir(version_type: str, novel_title_rough: str) -> Path:
    """Lấy đường dẫn thư mục lưu trữ phân loại cho các phiên bản"""
    v_type = version_type.upper()
    folder_type = VERSION_FOLDER_MAP.get(v_type, "03_DichAI_LLM")
    folder_novel = sanitize_filename(novel_title_rough or "Unknown_Novel")
    target_dir = OUTPUT_ROOT / folder_type / folder_novel
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir

def save_chapter_version_file(
    version_type: str,
    novel_title_raw: str,
    novel_title_rough: str,
    chapter_no: int,
    chapter_title_raw: str,
    chapter_title_rough: str,
    content_text: str
) -> str:
    """
    Ghi 1 chương phiên bản ra đĩa TXT theo đúng thư mục chuẩn
    """
    version_dir = get_version_dir(version_type, novel_title_rough or novel_title_raw)
    filename = f"{chapter_no:06d}.txt"
    file_path = version_dir / filename

    # Làm sạch nội dung dịch thô khỏi tiền tố dịch lỗi "KHÔNG.Xchương", "NO.Xchương", "第X章"
    cleaned_content = content_text or ""
    cleaned_content = re.sub(r'(?i)(?:KHÔNG|NO)\s*\.?\s*(\d+)\s*(?:chương|Chương|章)?\s*[:.:-]?\s*', r'Chương \1: ', cleaned_content)
    cleaned_content = re.sub(r'第\s*(\d+)\s*章\s*[:.:-]?\s*', r'Chương \1: ', cleaned_content)
    cleaned_content = re.sub(r'(?i)(?:Chương\s*(\d+)\s*:\s*){2,}', r'Chương \1: ', cleaned_content)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(cleaned_content)

    gc.collect()

    return str(file_path.resolve())

def save_tts_text_file(
    novel_title_rough: str,
    chapter_no: int,
    content_text: str
) -> str:
    """
    Ghi văn bản chương đã qua xử lý chuẩn cho TTS vào thư mục Output/04b_VanBanTTS/<Tên_Truyện>/chapters/000001.txt
    """
    folder_novel = sanitize_filename(novel_title_rough or "Unknown_Novel")
    target_dir = OUTPUT_ROOT / "04b_VanBanTTS" / folder_novel / "chapters"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{chapter_no:06d}.txt"
    file_path = target_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content_text or "")
    return str(file_path.resolve())

def save_audio_chapter_file(
    novel_title_rough: str,
    chapter_no: int,
    audio_bytes: bytes,
    extension: str = "mp3"
) -> str:
    """Ghi file Audio TTS (.mp3 / .wav) vào thư mục 05_Audio_TTS"""
    version_dir = get_version_dir("AUDIO", novel_title_rough)
    filename = f"{chapter_no:06d}.{extension}"
    file_path = version_dir / filename

    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    return str(file_path.resolve())

def read_version_file_content(file_path_str: str) -> str:
    """Đọc nhanh nội dung file phiên bản từ đường dẫn lưu trữ"""
    path = Path(file_path_str)
    if not path.exists():
        raise FileNotFoundError(f"File không tồn tại tại đường dẫn: {file_path_str}")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def delete_novel_disk_files(novel_title_rough: str, preserve_raw: bool = False):
    """Xóa sạch dữ liệu đĩa của truyện ở các thư mục trong Output (giữ 01_BanGoc nếu preserve_raw=True)"""
    folder_novel = sanitize_filename(novel_title_rough)
    for folder_type in VERSION_FOLDER_MAP.values():
        if preserve_raw and folder_type == "01_BanGoc":
            continue
        target_dir = OUTPUT_ROOT / folder_type / folder_novel
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

def delete_version_disk_files(version_type: str, novel_title_rough: str):
    """Xóa sạch file đĩa của 1 phiên bản cụ thể"""
    v_type = version_type.upper()
    folder_type = VERSION_FOLDER_MAP.get(v_type, "03_DichAI_LLM")
    folder_novel = sanitize_filename(novel_title_rough)
    target_dir = OUTPUT_ROOT / folder_type / folder_novel
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

# Tự động đồng bộ và tạo các thư mục chuẩn khi import
init_output_directories()

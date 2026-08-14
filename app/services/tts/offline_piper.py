import os
import sys
import time
import asyncio
import subprocess
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Đường dẫn mặc định tới binary Piper và mô hình
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_piper_executable() -> Optional[str]:
    """Tìm đường dẫn tệp thực thi piper.exe"""
    possible_paths = [
        os.path.join(BASE_DIR, "app", "bin", "piper", "piper", "piper.exe"),
        os.path.join(BASE_DIR, "app", "bin", "piper", "piper.exe"),
        os.path.join(BASE_DIR, "bin", "piper", "piper.exe"),
        "piper.exe",
        "piper"
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            return os.path.abspath(path)
    return None

def get_piper_model_paths() -> tuple[Optional[str], Optional[str]]:
    """Tìm đường dẫn model onnx và config json tiếng Việt"""
    models_dir = os.path.join(BASE_DIR, "app", "models", "piper_voices")
    
    onnx_candidates = [
        os.path.join(models_dir, "vi_VN-vais1000-medium.onnx"),
        os.path.join(models_dir, "vi_VN-vivos-x_low.onnx"),
        os.path.join(models_dir, "vi_VN-25hours_single-low.onnx"),
    ]
    
    for onnx_path in onnx_candidates:
        json_path = onnx_path + ".json"
        if os.path.exists(onnx_path) and os.path.exists(json_path):
            return os.path.abspath(onnx_path), os.path.abspath(json_path)
            
    return None, None

def is_piper_available() -> bool:
    """Kiểm tra xem hệ thống đã có sẵn Piper binary và model tiếng Việt chưa"""
    exe = get_piper_executable()
    onnx_path, json_path = get_piper_model_paths()
    return bool(exe and onnx_path and json_path)

def synthesize_text_piper_sync(
    text: str,
    output_wav_path: str,
    speaker_id: Optional[int] = None
) -> bool:
    """
    Tổng hợp âm thanh tiếng Việt Offline đồng bộ với subprocess trực tiếp.
    Cực kỳ ổn định trên Windows, tránh lỗi đóng pipe của asyncio.
    """
    exe = get_piper_executable()
    onnx_path, json_path = get_piper_model_paths()
    
    if not exe or not onnx_path or not json_path:
        logger.error("[PIPER] Không tìm thấy Piper executable hoặc model voice.")
        return False

    import uuid
    import shutil
    import tempfile

    output_wav_path = os.path.abspath(output_wav_path)
    os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
    
    # Tạo đường dẫn tạm thuần ASCII để tương thích 100% với C++ piper.exe trên Windows
    temp_dir = os.path.join(tempfile.gettempdir(), "airead_piper_tmp")
    os.makedirs(temp_dir, exist_ok=True)
    safe_temp_wav = os.path.join(temp_dir, f"chunk_{uuid.uuid4().hex[:12]}.wav")
        
    cmd = [
        exe,
        "--model", onnx_path,
        "--config", json_path,
        "--output_file", safe_temp_wav
    ]
    if speaker_id is not None:
        cmd.extend(["--speaker", str(speaker_id)])

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate(input=text.encode("utf-8"), timeout=120.0)
        
        # Kiểm tra và chuyển tệp an toàn về đích
        for _ in range(20):
            if os.path.exists(safe_temp_wav) and os.path.getsize(safe_temp_wav) > 0:
                shutil.move(safe_temp_wav, output_wav_path)
                return True
            time.sleep(0.05)
            
        if proc.returncode == 0 and os.path.exists(safe_temp_wav) and os.path.getsize(safe_temp_wav) > 0:
            shutil.move(safe_temp_wav, output_wav_path)
            return True
        else:
            if os.path.exists(safe_temp_wav):
                try: os.remove(safe_temp_wav)
                except Exception: pass
            err_msg = stderr.decode("utf-8", errors="ignore")
            logger.warning(f"[PIPER] Lỗi render (code {proc.returncode}): {err_msg}")
            return False
    except Exception as e:
        if os.path.exists(safe_temp_wav):
            try: os.remove(safe_temp_wav)
            except Exception: pass
        logger.error(f"[PIPER] Ngoại lệ khi chạy Piper: {e}")
        return False

async def synthesize_text_piper_async(
    text: str,
    output_wav_path: str,
    speaker_id: Optional[int] = None
) -> bool:
    """
    Tổng hợp âm thanh tiếng Việt Offline 100% bằng Piper Neural TTS qua ThreadPool.
    Tốc độ siêu nhanh, 0% kiểm duyệt từ ngữ.
    """
    return await asyncio.to_thread(synthesize_text_piper_sync, text, output_wav_path, speaker_id)

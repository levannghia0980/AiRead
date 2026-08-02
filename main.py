import os
import sys
import subprocess

# 1. Đảm bảo thư mục gốc dự án nằm trong sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def ensure_virtualenv():
    """Tự động phát hiện và chuyển hướng chạy script bằng môi trường ảo (venv) nếu chưa kích hoạt."""
    # Kiểm tra xem có đang chạy trong venv hay không
    in_venv = (sys.prefix != sys.base_prefix) or hasattr(sys, 'real_prefix')
    if in_venv:
        return

    # Tìm file thực thi python trong venv của dự án
    windows_venv_py = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    unix_venv_py = os.path.join(PROJECT_ROOT, "venv", "bin", "python")

    venv_py = None
    if os.path.exists(windows_venv_py):
        venv_py = windows_venv_py
    elif os.path.exists(unix_venv_py):
        venv_py = unix_venv_py

    if venv_py:
        print(f"[AIREAD] Phát hiện môi trường ảo tại '{venv_py}'. Đang tự động kích hoạt venv...")
        # Gọi lại chính main.py sử dụng Python trong venv
        cmd = [venv_py] + sys.argv
        sys.exit(subprocess.call(cmd))
    else:
        print("[AIREAD] Cảnh báo: Không tìm thấy thư mục 'venv'. Chạy trên Python hệ thống...")

if __name__ == "__main__":
    ensure_virtualenv()

    import uvicorn
    print("[AIREAD] Đang khởi động AIREAD FastAPI Backend Server...")
    print("[AIREAD] Swagger Docs available at: http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

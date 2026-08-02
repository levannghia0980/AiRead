import os
import sys
import time
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# Đỉnh nghĩa đường dẫn Python môi trường ảo (venv)
VENV_PYTHON_WIN = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
VENV_PYTHON_POSIX = os.path.join(PROJECT_ROOT, "venv", "bin", "python")

def get_venv_python():
    """Lấy đường dẫn trình thông dịch Python trong môi trường ảo venv."""
    if os.name == "nt" and os.path.exists(VENV_PYTHON_WIN):
        return VENV_PYTHON_WIN
    elif os.path.exists(VENV_PYTHON_POSIX):
        return VENV_PYTHON_POSIX
    return sys.executable

def ensure_venv_execution():
    """
    Tự động kiểm tra và chuyển sang chạy bằng Python của môi trường ảo (venv).
    Người dùng chỉ cần gõ `py run.py` hoặc `python run.py` từ bất kỳ terminal nào.
    """
    venv_py = get_venv_python()
    current_py = os.path.abspath(sys.executable).lower()
    target_py = os.path.abspath(venv_py).lower()

    if os.path.exists(venv_py) and current_py != target_py:
        print("=" * 60)
        print(f"🔄 Phát hiện Môi Trường Ảo (Virtual Environment): {venv_py}")
        print("🔄 Đang tự động chuyển sang sử dụng Python venv...")
        print("=" * 60 + "\n")
        
        # Chạy lại script này bằng Python trong venv và dừng tiến trình bên ngoài
        try:
            res = subprocess.run([venv_py] + sys.argv, cwd=PROJECT_ROOT)
            sys.exit(res.returncode)
        except Exception as e:
            print(f"⚠️ Không thể chuyển tự động sang venv: {e}")

import socket

def get_local_ip():
    """Lấy địa chỉ IP mạng nội bộ (LAN IP) của máy tính."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_services():
    venv_py = get_venv_python()
    local_ip = get_local_ip()
    
    print("=" * 65)
    print("🚀 AIREAD - HỆ THỐNG DỊCH TRUYỆN AI & ĐỌC TRUYỆN SEPIA")
    print("=" * 65)
    print(f"📌 Môi trường Python   : {venv_py}")
    print(f"🎨 Giao diện chính (Local) : http://localhost:8000")
    print(f"📱 Giao diện trên Điện thoại: http://{local_ip}:8000")
    print(f"🌐 Link Tên Miền Tùy Chỉnh : http://nghianeaudio0980.net:8000")
    print(f"🔹 Backend API (Internal)  : http://localhost:8001")
    print("=" * 65)
    print("Đang khởi chạy dịch vụ trên CỔNG 8000...\n")

    # Command khởi chạy Backend FastAPI trên cổng 8001 (Nội bộ / Proxied)
    be_cmd = [venv_py, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
    
    # Command khởi chạy Frontend Vite trên CỔNG 8000 (Cống cho phép điện thoại vào trực tiếp)
    fe_cmd = ["npx.cmd", "vite", "--host", "0.0.0.0", "--port", "8000"] if os.name == "nt" else ["npx", "vite", "--host", "0.0.0.0", "--port", "8000"]

    be_process = None
    fe_process = None

    try:
        # 1. Khởi chạy Backend
        print("[1/2] 🐍 Đang khởi chạy Backend FastAPI (Uvicorn 0.0.0.0:8001)...")
        be_process = subprocess.Popen(be_cmd, cwd=PROJECT_ROOT)

        time.sleep(1.5)

        # 2. Khởi chạy Frontend
        print("[2/2] ⚛️ Đang khởi chạy Frontend React (Vite 0.0.0.0:8000)...")
        fe_process = subprocess.Popen(fe_cmd, cwd=FRONTEND_DIR)

        print("\n✅ Cả Backend và Frontend đã sẵn sàng!")
        print(f"💡 Mở trên máy tính  : http://localhost:8000  hoặc  http://nghianeaudio0980.net:8000")
        print(f"📱 Mở trên Điện thoại: http://{local_ip}:8000")
        print("Nhấn Ctrl+C để dừng tất cả dịch vụ.\n")

        # Giữ tiến trình và chờ tín hiệu tắt
        while True:
            time.sleep(1)
            if be_process.poll() is not None:
                print("⚠️ Backend đã dừng.")
                break
            if fe_process.poll() is not None:
                print("⚠️ Frontend đã dừng.")
                break

    except KeyboardInterrupt:
        print("\n🛑 Nhận tín hiệu dừng từ người dùng (Ctrl+C)...")
    finally:
        print("🧹 Đang dọn dẹp và tắt toàn bộ tiến trình...")
        if fe_process and fe_process.poll() is None:
            fe_process.terminate()
            try:
                fe_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                fe_process.kill()
            print("✓ Đã tắt Frontend.")

        if be_process and be_process.poll() is None:
            be_process.terminate()
            try:
                be_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                be_process.kill()
            print("✓ Đã tắt Backend.")

        print("✨ Hoàn tất tắt ứng dụng AIREAD.")

if __name__ == "__main__":
    ensure_venv_execution()
    run_services()


import os
import sys
import time
import subprocess
import webbrowser

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
import re

def get_real_lan_ip():
    """Lấy địa chỉ IP mạng nội bộ thực tế của máy tính (loại bỏ Cloudflare WARP/VPN/WSL/Virtual adapters)."""
    # 1. Socket route (nhanh và chính xác nhất theo card mạng đang kết nối Internet/LAN)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        s_ip = s.getsockname()[0]
        s.close()
        if not s_ip.startswith("127.") and not s_ip.startswith("172.16."):
            return s_ip
    except Exception:
        pass

    # 2. Thử lấy qua ipconfig (tìm adapter có Default Gateway)
    try:
        res = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=2)
        lines = res.stdout.splitlines()
        current_adapter = ""
        adapter_ips = {}
        for line in lines:
            if "adapter" in line.lower() and ":" in line:
                current_adapter = line.strip().rstrip(":")
            m_ip = re.search(r"IPv4 Address[.\s]+:\s*([\d.]+)", line)
            if m_ip and current_adapter:
                adapter_ips[current_adapter] = m_ip.group(1)
            if "Default Gateway" in line and current_adapter in adapter_ips:
                gw = line.split(":")[-1].strip()
                if gw and not gw.startswith("0.0.0.0"):
                    cand_ip = adapter_ips[current_adapter]
                    if not cand_ip.startswith("172.16.") and not cand_ip.startswith("127."):
                        return cand_ip
    except Exception:
        pass

    # 3. Hostname resolution
    try:
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip and not host_ip.startswith("127.") and not host_ip.startswith("172.16."):
            return host_ip
    except Exception:
        pass

    return "127.0.0.1"

def print_qr_code(url: str):
    """In mã QR Code ASCII ra terminal để quét bằng camera điện thoại mở web ngay lập tức."""
    try:
        import qrcode
        import io
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        f = io.StringIO()
        qr.print_ascii(out=f, invert=True)
        print("📱 QUÉT MÃ QR DƯỚI ĐÂY BẰNG CAMERA ĐIỆN THOẠI ĐỂ TRUY CẬP NGAY:")
        print(f.getvalue())
    except Exception:
        pass

def run_services():
    venv_py = get_venv_python()
    local_ip = get_real_lan_ip()
    hostname = socket.gethostname().lower()
    
    phone_ip_url = f"http://{local_ip}:8000"
    phone_fixed_url = f"http://{hostname}.local:8000"
    
    print("=" * 68)
    print("🚀 AIREAD - HỆ THỐNG DỊCH TRUYỆN AI & ĐỌC TRUYỆN SEPIA")
    print("=" * 68)
    print(f"📌 Môi trường Python   : {venv_py}")
    print(f"🎨 Mở trên Máy Tính    : http://localhost:8000")
    print(f"📱 Mở trên Điện Thoại  : {phone_ip_url}")
    print(f"🔗 Link Cố Định (mDNS) : {phone_fixed_url}  (Không đổi khi IP đổi)")
    print(f"🌐 Link Tên Miền       : http://nghianeaudio0980.net:8000")
    print(f"🔹 Backend API         : http://localhost:8001")
    print("=" * 68)
    print("Đang khởi chạy dịch vụ trên CỔNG 8000...\n")

    # Command khởi chạy Backend FastAPI trên cổng 8001 (Nội bộ / Proxied)
    # --reload-dir app: Chỉ theo dõi mã nguồn trong thư mục app/, hoàn toàn bỏ qua Output/ và audio files
    be_cmd = [venv_py, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--reload-dir", "app"]
    
    # Command khởi chạy Frontend Vite trên CỔNG 8000
    import shutil
    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx") or r"C:\Users\ADMIN\AppData\Local\Programs\nodejs\npx.cmd"
    fe_cmd = [npx_cmd, "vite", "--host", "0.0.0.0", "--port", "8000"]

    be_process = None
    fe_process = None

    be_env = os.environ.copy()
    be_env["PYTHONUNBUFFERED"] = "1"
    node_dir = r"C:\Users\ADMIN\AppData\Local\Programs\nodejs"
    py_dir = r"C:\Users\ADMIN\AppData\Local\Programs\Python\Python311"
    if node_dir not in be_env.get("PATH", ""):
        be_env["PATH"] = f"{node_dir};{py_dir};{be_env.get('PATH', '')}"

    try:
        # 1. Khởi chạy Backend
        print("[1/2] 🐍 Đang khởi chạy Backend FastAPI (Uvicorn 0.0.0.0:8001)...")
        be_process = subprocess.Popen(be_cmd, cwd=PROJECT_ROOT, env=be_env)

        time.sleep(1.5)

        # 2. Khởi chạy Frontend
        print("[2/2] ⚛️ Đang khởi chạy Frontend React (Vite 0.0.0.0:8000)...")
        fe_process = subprocess.Popen(fe_cmd, cwd=FRONTEND_DIR, env=be_env)

        print("\n✅ Cả Backend và Frontend đã sẵn sàng!")
        print(f"💡 Mở trên máy tính  : http://localhost:8000")
        print(f"📱 Mở trên Điện thoại: {phone_ip_url}  hoặc  {phone_fixed_url}")
        print_qr_code(phone_ip_url)
        print("Nhấn Ctrl+C hoặc đóng cửa sổ terminal để dừng tất cả dịch vụ.\n")

        # Tự động mở trình duyệt web
        try:
            webbrowser.open("http://localhost:8000")
        except Exception:
            pass

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

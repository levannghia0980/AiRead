import os
import sys
import subprocess
import time
import signal

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def print_banner(text):
    print("=" * 60)
    print(f" {text}")
    print("=" * 60)

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")

    # Tự động phát hiện và chuyển sang chạy bằng môi trường ảo (venv) nếu chạy bằng Python hệ thống
    venv_python = os.path.join(root_dir, "venv", "Scripts", "python.exe")
    if sys.prefix == sys.base_prefix and os.path.exists(venv_python):
        print("🔄 Phát hiện chạy ngoài môi trường ảo. Tự động chuyển hướng sang venv...")
        try:
            sys.exit(subprocess.call([venv_python] + sys.argv))
        except Exception as e:
            print(f"❌ Lỗi khi tự động chuyển hướng sang venv: {e}")
            sys.exit(1)

    print_banner("AiRead v2 Rebuild: Khởi chạy Hệ thống")

    # Launch Backend and Frontend in Parallel
    print("🚀 Đang khởi chạy Backend và Frontend...")
    
    # Backend command
    backend_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"]
    # Frontend command
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]

    processes = []
    try:
        # Start backend (outputs to terminal directly)
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=backend_dir
        )
        processes.append(backend_proc)
        print("🔥 Backend FastAPI đã chạy tại: http://127.0.0.1:8000")

        # Start frontend (outputs to terminal directly)
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir
        )
        processes.append(frontend_proc)
        print("🔥 Frontend Vite đã chạy tại: http://localhost:5173")

        print("\n🎉 Khởi chạy hoàn tất! Trình duyệt sẽ tự động tải giao diện.")
        print("Bấm Ctrl + C để dừng cả hai máy chủ.\n")

        # Wait for processes
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"\n❌ Một tiến trình đã dừng đột ngột (Mã thoát: {p.returncode})")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Đang tắt các máy chủ hoạt động...")
        for p in processes:
            try:
                if os.name == 'nt':
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except Exception:
                p.terminate()
        print("👋 Đã tắt toàn bộ dịch vụ. Hẹn gặp lại bạn!")

if __name__ == "__main__":
    main()

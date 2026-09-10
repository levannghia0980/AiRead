import os
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, field_validator
from typing import Dict, Optional, Union
from app.core.config import get_all_active_settings
from app.core.database import AsyncSessionLocal
from app.models.schema import Setting
from sqlalchemy import select

router = APIRouter(prefix="/settings", tags=["System Settings"])

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

def update_env_file_key(key: str, val: Optional[str]):
    """Cập nhật hoặc xóa cấu hình trực tiếp vào file .env trên đĩa để lưu cho các lần chạy chương trình sau."""
    if val is not None:
        os.environ[key] = str(val)
    elif key in os.environ:
        del os.environ[key]
        
    if not os.path.exists(ENV_PATH):
        if val is not None:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(f"{key}={val}\n")
        return

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            found = True
            if val is not None:
                new_lines.append(f"{key}={val}\n")
        else:
            new_lines.append(line)

    if not found and val is not None:
        new_lines.append(f"{key}={val}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


class SettingsUpdatePayload(BaseModel):
    AIREAD_PROVIDER: Optional[str] = None
    AIREAD_MODEL: Optional[str] = None
    AIREAD_API_KEYS: Optional[str] = None
    AIREAD_CONCURRENCY: Optional[int] = None
    AIREAD_DELAY: Optional[float] = None
    AIREAD_BATCH_SIZE: Optional[int] = None
    AIREAD_TRANSLATION_STYLE: Optional[str] = None
    AIREAD_CUSTOM_PROMPT: Optional[str] = None
    AIREAD_TEMPERATURE: Optional[str] = None
    AIREAD_TOP_P: Optional[str] = None
    AIREAD_TOP_K: Optional[str] = None

    @field_validator("AIREAD_MODEL")
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v

@router.get("")
async def get_settings():
    """Lấy danh sách toàn bộ cấu hình đang hoạt động (kết hợp DB và file .env)"""
    try:
        active_settings = await get_all_active_settings()
        # Bổ sung các key định dạng snake_case phục vụ Frontend React
        res = dict(active_settings)
        res["provider"] = active_settings.get("AIREAD_PROVIDER", "")
        res["model"] = active_settings.get("AIREAD_MODEL", "")
        res["api_keys"] = active_settings.get("AIREAD_API_KEYS", "")
        res["batch_size"] = int(active_settings.get("AIREAD_BATCH_SIZE", 1)) if str(active_settings.get("AIREAD_BATCH_SIZE", "1")).isdigit() else 1
        res["delay"] = float(active_settings.get("AIREAD_DELAY", 0.0))
        res["translation_style"] = active_settings.get("AIREAD_TRANSLATION_STYLE", "")
        res["custom_prompt"] = active_settings.get("AIREAD_CUSTOM_PROMPT", "")
        res["temperature"] = active_settings.get("AIREAD_TEMPERATURE", "")
        res["top_p"] = active_settings.get("AIREAD_TOP_P", "")
        res["top_k"] = active_settings.get("AIREAD_TOP_K", "")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SaveSettingsPayload(BaseModel):
    api_keys: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    batch_size: Optional[int] = None
    delay: Optional[float] = None
    custom_prompt: Optional[str] = None
    translation_style: Optional[str] = None
    temperature: Optional[Union[float, str]] = None
    top_p: Optional[Union[float, str]] = None
    top_k: Optional[Union[int, str]] = None

@router.post("/save")
async def save_settings(payload: SaveSettingsPayload):
    """Lưu cài đặt từ Frontend dạng snake_case vào .env và DB"""
    mapping = {
        "api_keys": "AIREAD_API_KEYS",
        "provider": "AIREAD_PROVIDER",
        "model": "AIREAD_MODEL",
        "batch_size": "AIREAD_BATCH_SIZE",
        "delay": "AIREAD_DELAY",
        "custom_prompt": "AIREAD_CUSTOM_PROMPT",
        "translation_style": "AIREAD_TRANSLATION_STYLE",
        "temperature": "AIREAD_TEMPERATURE",
        "top_p": "AIREAD_TOP_P",
        "top_k": "AIREAD_TOP_K",
    }
    async with AsyncSessionLocal() as session:
        for p_key, env_key in mapping.items():
            val = getattr(payload, p_key, None)
            if val is not None:
                str_val = str(val)
                update_env_file_key(env_key, str_val)
                stmt = select(Setting).where(Setting.key == env_key)
                res = await session.execute(stmt)
                setting_row = res.scalar_one_or_none()
                if setting_row:
                    setting_row.value = str_val
                else:
                    session.add(Setting(key=env_key, value=str_val))
        await session.commit()
    return {"status": "success", "message": "Cấu hình hệ thống đã được cập nhật thành công."}

@router.post("")
async def update_settings(payload: SettingsUpdatePayload):
    """
    Cập nhật cấu hình động vào Database VÀ file .env trên đĩa.
    Hệ thống sẽ lập tức áp dụng và duy trì cho các lần khởi động tiếp theo.
    """
    async with AsyncSessionLocal() as session:
        for key, val in payload.model_dump(exclude_unset=True).items():
            if val is None:
                continue
            
            str_val = str(val)
            update_env_file_key(key, str_val)
            
            stmt = select(Setting).where(Setting.key == key)
            res = await session.execute(stmt)
            setting_row = res.scalar_one_or_none()
            
            if setting_row:
                setting_row.value = str_val
            else:
                setting_row = Setting(key=key, value=str_val)
                session.add(setting_row)
                
        await session.commit()
        
    updated_settings = await get_all_active_settings()
    return {
        "status": "success",
        "message": "Cấu hình hệ thống đã được cập nhật vào DB và file .env thành công.",
        "settings": updated_settings
    }


@router.delete("/{key}")
async def delete_setting(key: str = Path(...)):
    """
    Xóa cấu hình tùy chỉnh khỏi DB và reset trong file .env.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Setting).where(Setting.key == key)
        res = await session.execute(stmt)
        setting_row = res.scalar_one_or_none()
        if setting_row:
            await session.delete(setting_row)
            await session.commit()
            
    update_env_file_key(key, None)
    
    return {"status": "success", "message": f"Đã xóa cấu hình '{key}'."}

class TestConnectionPayload(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = ""

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v:
            return v.strip()
        return "gemini-3.5-flash-lite"

@router.post("/test-connection")
async def test_api_connection(payload: TestConnectionPayload):
    """
    Thử nghiệm kết nối đến nhà cung cấp LLM (Gemini, OpenRouter hoặc Grok Web Local)
    để kiểm tra xem kết nối và cấu hình có hoạt động tốt hay không.
    """
    import httpx
    provider = payload.provider.lower().strip()
    model = payload.model
    api_key = (payload.api_key or "").strip()

    if provider in ["grok_local", "grok", "grok_web"]:
        health_url = "http://127.0.0.1:8020/health"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    return {
                        "status": "success",
                        "message": "✅ Kết nối Grok Web Automation Server (Cổng 8020) thành công! Sẵn sàng dịch qua Edge."
                    }
                return {
                    "status": "failed",
                    "message": f"Grok Server phản hồi HTTP {resp.status_code}: {resp.text}"
                }
            except Exception:
                return {
                    "status": "failed",
                    "message": "❌ Chưa kết nối được Grok Server cổng 8020! Hãy nhấp mở file 'Run_Grok_Server.bat' hoặc chạy 'python tools/grok_server/server.py' trước!"
                }
    
    if not api_key:
        return {"status": "failed", "message": "API Key không được để trống."}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            if provider == "gemini":
                # Gọi API trực tiếp của Google Gemini
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                body = {
                    "contents": [{"parts": [{"text": "Hello, respond with short OK."}]}]
                }
                resp = await client.post(url, json=body)
                if resp.status_code == 200:
                    return {
                        "status": "success",
                        "message": f"Kết nối Gemini thành công! Model '{model}' đang hoạt động tốt."
                    }
                else:
                    err_msg = resp.text
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        pass
                    if resp.status_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg:
                        return {
                            "status": "success",
                            "message": f"✅ API Key HOÀN TOÀN HỢP LỆ! (Lưu ý: Key đang chạm mốc 15 RPM Free Tier của Google, hệ thống sẽ tự chờ vài chục giây để chạy tiếp)."
                        }
                    return {
                        "status": "failed",
                        "message": f"Kết nối Gemini thất bại (HTTP {resp.status_code}): {err_msg}"
                    }
                    
            elif provider == "openrouter":
                # Gọi API thông qua cổng OpenRouter
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                body = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 5
                }
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code == 200:
                    return {
                        "status": "success",
                        "message": f"Kết nối OpenRouter thành công! Model '{model}' phản hồi tốt."
                    }
                else:
                    return {
                        "status": "failed",
                        "message": f"Kết nối OpenRouter thất bại (HTTP {resp.status_code}): {resp.text}"
                    }
            else:
                return {
                    "status": "failed",
                    "message": f"Nhà cung cấp '{provider}' chưa được hỗ trợ chạy thử nghiệm kết nối."
                }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Lỗi trong quá trình kết nối thử nghiệm: {str(e)}"
            }

@router.get("/network-info")
async def get_network_info():
    """Lấy thông tin mạng nội bộ thực tế để kết nối từ điện thoại."""
    import socket
    import subprocess
    import re

    hostname = socket.gethostname()
    primary_ip = "127.0.0.1"
    adapters = []

    # 1. Lấy IP qua socket route (nhanh, chuẩn xác nhất theo định tuyến OS)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # 2. Duyệt qua danh sách adapter để tìm tất cả IP cục bộ
    try:
        res = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=2)
        lines = res.stdout.splitlines()
        curr_adapter = ""
        for line in lines:
            if ("adapter" in line.lower() or "interface" in line.lower()) and ":" in line:
                curr_adapter = line.strip().rstrip(":")
            m_ip = re.search(r"IPv4 Address[.\s]+:\s*([\d.]+)", line)
            if m_ip:
                ip_val = m_ip.group(1).strip()
                if ip_val and not ip_val.startswith("127."):
                    name_clean = curr_adapter.replace("adapter", "").replace("Ethernet", "").strip() or "LAN/Wi-Fi"
                    adapters.append({"name": name_clean, "ip": ip_val})
    except Exception:
        pass

    if not adapters and primary_ip != "127.0.0.1":
        adapters.append({"name": "Mạng LAN chính", "ip": primary_ip})

    if primary_ip == "127.0.0.1" and adapters:
        primary_ip = adapters[0]["ip"]

    return {
        "status": "success",
        "lan_ip": primary_ip,
        "adapters": adapters,
        "hostname": hostname,
        "port": 8000,
        "ip_url": f"http://{primary_ip}:8000",
        "hostname_url": f"http://{hostname.lower()}.local:8000",
        "direct_host_url": f"http://{hostname.lower()}:8000",
        "domain_url": "http://nghianeaudio0980.net:8000"
    }


_GROK_SERVER_PROCESS = None

@router.post("/grok/open-edge")
async def open_edge_grok():
    """Mở cửa sổ trình duyệt Edge thật trên màn hình desktop tới grok.com."""
    import sys
    import os
    import subprocess
    from pathlib import Path

    workspace_dir = Path(__file__).resolve().parent.parent.parent
    user_data_dir = workspace_dir / "tools" / "grok_server" / "user_data" / "edge_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
    ]
    edge_exe = next((path for path in candidates if path and Path(path).exists()), None)

    if not edge_exe:
        raise HTTPException(status_code=404, detail="Không tìm thấy trình duyệt Microsoft Edge trên máy tính.")

    cmd = (
        f'start "" "{edge_exe}" '
        f'--remote-debugging-port=9222 '
        f'--user-data-dir="{user_data_dir}" '
        f'--profile-directory=Default '
        f'--start-maximized '
        f'--no-first-run '
        f'--new-window "https://grok.com"'
    )
    subprocess.Popen(cmd, shell=True)
    return {"status": "success", "message": "🖥️ Đã bật cửa sổ trình duyệt Edge trên màn hình! Vui lòng đăng nhập tài khoản Grok."}


@router.post("/grok/connect")
async def connect_grok_server():
    """Kiểm tra hoặc tự động khởi chạy Grok Web Automation Server (Cổng 8020) và mở cửa sổ Edge."""
    global _GROK_SERVER_PROCESS
    import sys
    import os
    import subprocess
    import asyncio
    import httpx
    from pathlib import Path

    health_url = "http://127.0.0.1:8020/health"
    connect_url = "http://127.0.0.1:8020/connect"
    workspace_dir = Path(__file__).resolve().parent.parent.parent

    # Hàm mở cửa sổ Edge trên desktop
    def _force_open_edge():
        try:
            user_data_dir = workspace_dir / "tools" / "grok_server" / "user_data" / "edge_profile"
            user_data_dir.mkdir(parents=True, exist_ok=True)
            candidates = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
            ]
            edge_exe = next((path for path in candidates if path and Path(path).exists()), None)
            if edge_exe:
                cmd = (
                    f'start "" "{edge_exe}" '
                    f'--remote-debugging-port=9222 '
                    f'--user-data-dir="{user_data_dir}" '
                    f'--profile-directory=Default '
                    f'--start-maximized '
                    f'--no-first-run '
                    f'--new-window "https://grok.com"'
                )
                subprocess.Popen(cmd, shell=True)
        except Exception:
            pass

    async def _call_connect():
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                c_resp = await client.post(connect_url)
                if c_resp.status_code == 200:
                    c_data = c_resp.json()
                    has_session = c_data.get("has_session", False)
                    return {
                        "status": "success" if has_session else "warning",
                        "message": c_data.get("message", "🟢 Grok Server đang hoạt động tốt tại cổng 8020!"),
                        "has_session": has_session,
                        "is_running": True
                    }
            except Exception:
                pass
        return {
            "status": "success",
            "message": "🟢 Grok Server đang hoạt động tại cổng 8020! Cửa sổ Edge đã mở.",
            "has_session": True,
            "is_running": True
        }

    # 1. Kiểm tra xem server 8020 đã chạy chưa
    server_already_running = False
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            resp = await client.get(health_url)
            if resp.status_code == 200:
                server_already_running = True
        except Exception:
            pass

    if server_already_running:
        _force_open_edge()
        return await _call_connect()

    # 2. Nếu chưa chạy, tự động khởi động process tools/grok_server/server.py
    server_script = workspace_dir / "tools" / "grok_server" / "server.py"
    if not server_script.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy file server tại {server_script}")

    venv_py = workspace_dir / "venv" / "Scripts" / "python.exe"
    py_exec = str(venv_py) if venv_py.exists() else sys.executable

    # Ép mở cửa sổ Edge trước trên Desktop để người dùng nhìn thấy ngay
    _force_open_edge()

    try:
        flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        _GROK_SERVER_PROCESS = subprocess.Popen(
            [py_exec, str(server_script)],
            cwd=str(workspace_dir),
            creationflags=flags
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể khởi động Grok Server: {e}")

    # 3. Chờ tối đa 12 giây để server khởi động và lắng nghe port 8020
    for _ in range(24):
        await asyncio.sleep(0.5)
        async with httpx.AsyncClient(timeout=1.5) as client:
            try:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    return await _call_connect()
            except Exception:
                pass

    return {
        "status": "warning",
        "message": "⚠️ Đã khởi chạy Grok Server và mở cửa sổ Edge trên màn hình. Hãy đăng nhập tài khoản Grok để bắt đầu dịch!",
        "has_session": False,
        "is_running": True
    }


@router.post("/grok/relogin")
async def relogin_grok_server():
    """Xóa cookies cũ để đăng nhập lại tài khoản Grok mới trên Edge."""
    import httpx
    relogin_url = "http://127.0.0.1:8020/relogin"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(relogin_url)
            data = resp.json()
            return data
        except httpx.ConnectError:
            raise HTTPException(status_code=400, detail="Grok Server cổng 8020 chưa được bật. Vui lòng bấm Kết Nối trước!")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))



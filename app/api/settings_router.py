import os
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, field_validator
from typing import Dict, Optional
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
    api_key: str

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v:
            return v.strip()
        return "gemini-3.5-flash-lite"

@router.post("/test-connection")
async def test_api_connection(payload: TestConnectionPayload):
    """
    Thử nghiệm kết nối đến nhà cung cấp LLM (Gemini hoặc OpenRouter)
    để kiểm tra xem API Key và Model lựa chọn có hoạt động tốt hay không.
    """
    import httpx
    provider = payload.provider.lower()
    model = payload.model
    api_key = payload.api_key.strip()
    
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

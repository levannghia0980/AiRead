import asyncio
import json
import re
import time
import httpx
from typing import Dict, Any, Optional

DEFAULT_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
]

_LAST_GEMINI_REQUEST_TIME = 0.0
_GEMINI_REQUEST_LOCK = asyncio.Lock()

async def post_gemini_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 6
) -> httpx.Response:
    """
    Tự động gửi request đến Gemini API và xử lý thông minh:
    - Chủ động giãn cách tối thiểu 4.1s giữa các request (Adaptive Pacing) để 100% không chạm mốc 15 RPM.
    - Bắt và thử lại tự động các lỗi mạng/ngắt kết nối.
    - Xử lý thông minh lỗi HTTP 429 (Rate Limit / Quota Exceeded) với delay từ API.
    - Tự động gắn bộ lọc safetySettings=BLOCK_NONE để loại bỏ hoàn toàn vi phạm chặn văn bản.
    """
    global _LAST_GEMINI_REQUEST_TIME

    if payload is not None and "safetySettings" not in payload:
        payload["safetySettings"] = DEFAULT_SAFETY_SETTINGS

    def _safe_add_log(msg: str, level: str = "info"):
        try:
            from app.api.translation_router import add_system_log
            add_system_log(msg, level)
        except Exception:
            pass

    last_exception = None
    for attempt in range(1, max_retries + 1):
        # Tự động điều tiết tần suất request (Pacing): Giãn cách tối thiểu 4.1s giữa các request
        # để đảm bảo 100% không vượt quá ngưỡng 15 RPM của Gemini Free Tier, tránh tối đa việc bị ngắt 60s.
        async with _GEMINI_REQUEST_LOCK:
            now = time.time()
            elapsed = now - _LAST_GEMINI_REQUEST_TIME
            min_interval = 4.1  # 60s / 15 RPM = 4.0s -> 4.1s safe margin
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            _LAST_GEMINI_REQUEST_TIME = time.time()

        try:
            resp = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            last_exception = e
            wait_seconds = min(3.0 * attempt, 15.0)
            err_name = type(e).__name__
            err_msg = str(e) or err_name
            log_net = f"⚠️ [LLM MẠNG/DISCONNECT] Gặp lỗi kết nối ({err_name}: {err_msg}). Đang chờ {wait_seconds:.1f}s để thử lại (Lần {attempt}/{max_retries})..."
            print(log_net)
            _safe_add_log(log_net, "warning")

            if attempt < max_retries:
                await asyncio.sleep(wait_seconds)
                continue
            else:
                raise Exception(f"Lỗi kết nối Gemini API sau {max_retries} lần thử: {err_msg}") from e

        if resp.status_code == 200:
            return resp
            
        # Kiểm tra nếu dính lỗi 429 Quota Exceeded / Rate Limit
        if resp.status_code == 429 or "RESOURCE_EXHAUSTED" in resp.text or "Quota exceeded" in resp.text:
            wait_seconds = 8.0  # Chờ ngắn hơn để nhanh thử lại hoặc xoay key
            
            try:
                err_data = resp.json()
                details = err_data.get("error", {}).get("details", [])
                for d in details:
                    if "retryDelay" in d:
                        delay_str = d["retryDelay"]
                        num = float(re.sub(r"[^\d.]", "", delay_str))
                        if num > 0:
                            wait_seconds = min(num + 1.0, 15.0)  # Cắt tối đa 15s chờ
                            break
            except Exception:
                pass
                
            log_429 = f"⚠️ [LLM 429 Rate Limit] Chạm giới hạn 15 RPM Gemini Free Tier. Đang thử lại (Lần {attempt}/{max_retries})..."
            print(log_429)
            _safe_add_log(log_429, "warning")
            if attempt < max_retries:
                await asyncio.sleep(wait_seconds)
            else:
                return resp
        else:
            # Lỗi khác (400, 500...), thử lại với exponential backoff ngắn
            log_err = f"⚠️ [LLM HTTP {resp.status_code}] Gặp lỗi API: {resp.text[:150]}... Đang chờ 5s để thử lại ({attempt}/{max_retries})."
            print(log_err)
            _safe_add_log(log_err, "warning")
            await asyncio.sleep(5.0)
            
    return resp


async def post_openrouter_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 6
) -> httpx.Response:
    """
    Gửi request đến OpenRouter API với auto-retry thông minh:
    - Tự đọc retry_after_seconds từ response 429 và chờ đúng thời gian yêu cầu.
    - Retry tối đa max_retries lần cho các lỗi mạng và 429.
    """
    def _safe_add_log(msg: str, level: str = "info"):
        try:
            from app.api.translation_router import add_system_log
            add_system_log(msg, level)
        except Exception:
            pass

    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            wait_s = min(5.0 * attempt, 30.0)
            log_net = f"⚠️ [OpenRouter MẠNG] Lỗi kết nối: {e}. Chờ {wait_s:.0f}s thử lại ({attempt}/{max_retries})..."
            print(log_net)
            _safe_add_log(log_net, "warning")
            if attempt < max_retries:
                await asyncio.sleep(wait_s)
                continue
            raise

        if resp.status_code == 200:
            return resp

        if resp.status_code == 429:
            # Đọc retry_after_seconds từ response OpenRouter
            wait_s = 10.0
            try:
                err_data = resp.json()
                retry_s = err_data.get("error", {}).get("metadata", {}).get("retry_after_seconds")
                if retry_s and float(retry_s) > 0:
                    wait_s = float(retry_s) + 2.0  # Thêm 2s buffer
            except Exception:
                pass
            wait_s = min(wait_s, 60.0)
            log_429 = f"⚠️ [OpenRouter 429] Rate Limit Free Tier. Chờ {wait_s:.0f}s thử lại ({attempt}/{max_retries})..."
            print(log_429)
            _safe_add_log(log_429, "warning")
            if attempt < max_retries:
                await asyncio.sleep(wait_s)
                continue
            return resp
        else:
            # Lỗi khác
            log_err = f"⚠️ [OpenRouter HTTP {resp.status_code}] {resp.text[:200]}... ({attempt}/{max_retries})"
            print(log_err)
            _safe_add_log(log_err, "warning")
            if attempt < max_retries:
                await asyncio.sleep(5.0)
                continue
            return resp

    return resp


def safe_json_loads(text: str) -> Any:
    """
    Phân tích JSON an toàn và thông minh từ phản hồi của LLM (Gemini, ChatGPT...):
    - Tự động bóc tách markdown codeblock (```json ... ```)
    - Tự động cắt bỏ text thừa / rác ở đầu và đuôi
    - Khôi phục từ lỗi 'Extra data' do LLM lặp ngoặc đóng (vd: }\\n})
    - Tự động sửa lỗi ngoặc thừa hoặc phẩy thừa (trailing comma)
    """
    if not text:
        raise ValueError("Văn bản phản hồi từ LLM rỗng.")

    cleaned = text.strip()

    # 1. Bóc tách markdown backticks
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # 2. Tìm vị trí dấu ngoặc mở đầu tiên ({ hoặc [) và dấu ngoặc đóng tương ứng cuối cùng (} hoặc ])
    first_brace = min([i for i in [cleaned.find('{'), cleaned.find('[')] if i != -1], default=-1)
    last_brace = max([cleaned.rfind('}'), cleaned.rfind(']')], default=-1)

    if first_brace != -1 and last_brace != -1 and last_brace >= first_brace:
        candidate = cleaned[first_brace:last_brace + 1]
    else:
        candidate = cleaned

    # Lần 1: Thử parse trực tiếp candidate
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # Lần 2: Xử lý lỗi Extra data (LLM in thêm ngoặc } hoặc text sau object JSON hoàn chỉnh)
        if "Extra data" in str(e) and e.pos > 0:
            try:
                return json.loads(candidate[:e.pos].strip())
            except Exception:
                pass

        # Lần 3: Loại bỏ lặp ngoặc đóng ở đuôi
        fixed = re.sub(r'\}\s*\}$', '}', candidate.strip())
        fixed = re.sub(r'\]\s*\]$', ']', fixed)
        try:
            return json.loads(fixed)
        except Exception:
            pass

        # Lần 4: Loại bỏ dấu phẩy thừa trước ngoặc đóng (vd: {"a": 1,})
        fixed_comma = re.sub(r',\s*([\}\]])', r'\1', candidate)
        try:
            return json.loads(fixed_comma)
        except Exception:
            pass

        # Nâng cao: Thử parse toàn bộ cleaned text nếu candidate cắt bị thiếu
        if candidate != cleaned:
            try:
                return json.loads(cleaned)
            except Exception:
                pass

        raise e


import asyncio
import json
import re
import httpx
from typing import Dict, Any, Optional

DEFAULT_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
]

async def post_gemini_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 6
) -> httpx.Response:
    """
    Tự động gửi request đến Gemini API và xử lý thông minh:
    - Bắt và thử lại tự động các lỗi mạng/ngắt kết nối (Server disconnected without sending a response, Timeout, Connection reset).
    - Xử lý thông minh lỗi HTTP 429 (Rate Limit / Quota Exceeded) với delay khuyến nghị từ API.
    - Tự động gắn bộ lọc safetySettings=BLOCK_NONE để loại bỏ hoàn toàn vi phạm chặn văn bản (PROHIBITED_CONTENT).
    """
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
            wait_seconds = 18.0 # Giá trị chờ mặc định an toàn cho Gemini Free Tier (15 RPM)
            
            try:
                err_data = resp.json()
                # Tìm retryDelay trong details của Gemini response
                details = err_data.get("error", {}).get("details", [])
                for d in details:
                    if "retryDelay" in d:
                        delay_str = d["retryDelay"] # Dạng "18s" hoặc "21s"
                        num = float(re.sub(r"[^\d.]", "", delay_str))
                        if num > 0:
                            wait_seconds = num + 1.5 # Thêm 1.5s buffer an toàn
                            break
            except Exception:
                pass
                
            log_429 = f"⚠️ [LLM 429 Rate Limit] Chạm giới hạn 15 RPM Gemini Free Tier. Đang tự động nghỉ {wait_seconds:.1f}s trước khi thử lại (Lần {attempt}/{max_retries})..."
            print(log_429)
            _safe_add_log(log_429, "warning")
            await asyncio.sleep(wait_seconds)
        else:
            # Lỗi khác (400, 500...), thử lại với exponential backoff ngắn
            log_err = f"⚠️ [LLM HTTP {resp.status_code}] Gặp lỗi API: {resp.text[:150]}... Đang chờ 5s để thử lại ({attempt}/{max_retries})."
            print(log_err)
            _safe_add_log(log_err, "warning")
            await asyncio.sleep(5.0)
            
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


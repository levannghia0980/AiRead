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
    Tự động gửi request đến Gemini API và xử lý thông minh lỗi HTTP 429.
    Tự động gắn bộ lọc safetySettings=BLOCK_NONE để loại bỏ hoàn toàn vi phạm chặn văn bản (PROHIBITED_CONTENT).
    """
    if payload is not None and "safetySettings" not in payload:
        payload["safetySettings"] = DEFAULT_SAFETY_SETTINGS

    for attempt in range(1, max_retries + 1):
        resp = await client.post(url, headers=headers, json=payload)
        
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
                
            print(f"⚠️ [LLM 429 Rate Limit] Chạm giới hạn 15 RPM Gemini Free Tier. Đang tự động nghỉ {wait_seconds:.1f}s trước khi thử lại (Lần {attempt}/{max_retries})...")
            await asyncio.sleep(wait_seconds)
        else:
            # Lỗi khác (400, 500...), thử lại với exponential backoff ngắn
            print(f"⚠️ [LLM HTTP {resp.status_code}] Gặp lỗi API: {resp.text[:150]}... Đang chờ 5s để thử lại ({attempt}/{max_retries}).")
            await asyncio.sleep(5.0)
            
    return resp

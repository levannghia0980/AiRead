import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

class DummyAsyncContext:
    def __init__(self, client):
        self.client = client
    async def __aenter__(self):
        return self.client
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class AdaptiveLimiter:
    """
    Adaptive concurrency limiter — tự động tăng/giảm số request song song
    dựa trên kết quả thực tế (thành công → tăng, rate limit → giảm).
    
    Tối ưu cho OpenRouter: khởi đầu cao (8), tối đa 30 concurrent requests.
    """
    def __init__(self, start=8, max_limit=30):
        self.limit = start
        self.max_limit = max_limit
        self._active_requests = 0
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(lock=self._lock)

    async def adjust_for_provider(self, provider: str, model: str, num_keys: int, user_concurrency: int = 15):
        """Tự động điều chỉnh giới hạn song song phù hợp với nhà cung cấp."""
        provider = provider.lower()
        model = model.lower()
        
        async with self._lock:
            # Tôn trọng cấu hình luồng song song do người dùng chọn trên UI
            self.max_limit = max(user_concurrency, 1)
            self.limit = self.max_limit
            logger.info(f"⚙️ Adaptive Limiter: Đặt giới hạn song song theo UI -> {self.limit}")
            self._cond.notify_all()

    async def acquire(self):
        async with self._cond:
            while self._active_requests >= self.limit:
                await self._cond.wait()
            self._active_requests += 1
            logger.debug(f"🔑 Limiter acquired. Active: {self._active_requests}/{self.limit}")

    async def release(self):
        async with self._cond:
            self._active_requests = max(0, self._active_requests - 1)
            self._cond.notify_all()
            logger.debug(f"🔓 Limiter released. Active: {self._active_requests}/{self.limit}")

    async def on_success(self):
        """Tăng 2 sau mỗi thành công — leo thang nhanh hơn khi ổn định."""
        async with self._cond:
            if self.limit < self.max_limit:
                self.limit = min(self.max_limit, self.limit + 2)
                logger.info(f"⚡ Adaptive Limiter: Concurrency → {self.limit}")
                self._cond.notify_all()

    async def on_rate_limit(self):
        """Giảm limit khi bị rate limit — an toàn để bảo toàn key."""
        async with self._cond:
            self.limit = max(1, self.limit - 3)
            logger.warning(f"⏳ Adaptive Limiter: Rate limit hit → Concurrency → {self.limit}")
            self._cond.notify_all()


global_limiter = AdaptiveLimiter(start=15, max_limit=30)


class TranslatorClient:
    """
    Client for interacting with LLM APIs (Gemini, OpenAI, Claude, OpenRouter).
    
    Tối ưu hóa:
    - Key Rotation thông minh: xoay key ngay khi gặp rate limit
    - Exponential Backoff với jitter để tránh thundering herd
    - Per-key cooldown tracking: tránh spam key đang bị cooldown
    - Tối đa số chương/key bằng cách phân phối request đều giữa các key
    """
    
    def __init__(self, provider: str, model: str, api_keys_str: str, concurrency: int = 15, http_client: Optional[httpx.AsyncClient] = None):
        self.provider = provider.lower()
        self.model = model
        # Split API keys by semicolon and strip whitespace
        self.api_keys = [k.strip() for k in api_keys_str.split(";") if k.strip()]
        self.current_key_idx = 0
        self.http_client = http_client
        
        # Per-key cooldown: key_idx -> (cooldown_until timestamp, consecutive_rate_limits)
        self._key_cooldowns: Dict[int, float] = {}
        self._key_rate_limit_count: Dict[int, int] = {}
        self._key_lock = asyncio.Lock()
        
        if not self.api_keys:
            raise ValueError("No valid API keys provided.")
            
        # Tự động điều chỉnh giới hạn song song dựa trên config UI
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(global_limiter.adjust_for_provider(self.provider, self.model, len(self.api_keys), concurrency))
        except Exception:
            pass

    def get_current_key(self) -> str:
        """Returns the currently active API key."""
        if not self.api_keys:
            return ""
        return self.api_keys[self.current_key_idx]

    def rotate_key(self):
        """Rotates to the next available API key, skipping keys in cooldown."""
        if len(self.api_keys) <= 1:
            return
        
        now = time.monotonic()
        # Try to find next key not in cooldown
        for _ in range(len(self.api_keys)):
            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            cooldown_until = self._key_cooldowns.get(self.current_key_idx, 0)
            if now >= cooldown_until:
                logger.info(f"🔄 Rotated to API Key index {self.current_key_idx}")
                return
        
        # All keys in cooldown — pick the one with shortest remaining cooldown
        best_idx = min(
            range(len(self.api_keys)),
            key=lambda i: self._key_cooldowns.get(i, 0)
        )
        self.current_key_idx = best_idx
        logger.warning(f"⚠️ All keys in cooldown. Using key #{best_idx} (shortest cooldown).")

    def _set_key_cooldown(self, key_idx: int, seconds: float):
        """Đặt cooldown cho key cụ thể."""
        self._key_cooldowns[key_idx] = time.monotonic() + seconds
        count = self._key_rate_limit_count.get(key_idx, 0) + 1
        self._key_rate_limit_count[key_idx] = count
        logger.warning(f"⏱️ Key #{key_idx} cooldown {seconds:.1f}s (hit {count}x total)")

    @staticmethod
    def _parse_retry_delay(response_text: str) -> float:
        """Extracts the recommended retry delay from API error response."""
        try:
            error_data = json.loads(response_text)
            details = error_data.get("error", {}).get("details", [])
            for detail in details:
                if detail.get("@type", "").endswith("RetryInfo"):
                    delay_str = detail.get("retryDelay", "")
                    if delay_str.endswith("s"):
                        return float(delay_str[:-1])
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _is_quota_zero(response_text: str) -> bool:
        """Checks if the quota limit is 0 (free tier completely exhausted for the day)."""
        try:
            return "limit: 0" in response_text
        except Exception:
            return False

    async def translate(self, prompt: str, system_instruction: str = "") -> Dict[str, Any]:
        """
        Sends the translation request to the selected AI provider.
        
        Tối ưu hóa:
        - Xoay key ngay khi rate limit (không chờ)
        - Parse retryDelay từ API response
        - Cooldown tracking per key
        - Tối đa 10 lần thử (tăng từ 6→10)
        
        Returns:
            Dict containing:
                - text (str): Translated text
                - input_tokens (int): Tokens used in request
                - output_tokens (int): Tokens used in response
        """
        max_attempts = 10
        base_delay = 1.5
        consecutive_rate_limits = 0
        tried_keys = set()
        
        for attempt in range(max_attempts):
            current_idx = self.current_key_idx
            api_key = self.get_current_key()
            
            try:
                result = await self._call_api(prompt, system_instruction, api_key)
                # Reset rate limit count on success
                self._key_rate_limit_count[current_idx] = 0
                return result
                
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                response_text = e.response.text
                
                # Check for permanent credential errors
                response_lower = response_text.lower()
                is_invalid_key = (
                    "api_key_invalid" in response_lower or
                    ("api key" in response_lower and "not valid" in response_lower) or
                    "unauthenticated" in response_lower or
                    "invalid key" in response_lower or
                    "key is invalid" in response_lower or
                    "invalid_api_key" in response_lower or
                    "no auth" in response_lower
                )
                if is_invalid_key or status_code == 401:
                    raise ValueError(f"API Key không hợp lệ: {response_text[:200]}")
                
                # Check for rate limit or quota exceeded
                is_rate_limit = (
                    status_code == 429 or
                    status_code == 403 or
                    "quota" in response_text.lower() or
                    "rate limit" in response_text.lower() or
                    "too many requests" in response_text.lower()
                )
                
                if is_rate_limit:
                    await global_limiter.on_rate_limit()
                    consecutive_rate_limits += 1
                    tried_keys.add(current_idx)
                    
                    # Check if free tier is completely exhausted
                    if self._is_quota_zero(response_text):
                        logger.warning(f"⚠️ Quota free tier hết hoàn toàn cho key #{current_idx}")
                        self._set_key_cooldown(current_idx, 3600.0)  # 1 hour cooldown
                        self.rotate_key()
                        
                        if consecutive_rate_limits >= len(self.api_keys):
                            raise ValueError(
                                f"🚫 Tất cả API key đều đã hết quota. "
                                f"Hãy nâng cấp lên gói trả phí hoặc đợi reset quota."
                            )
                        await asyncio.sleep(0.5)
                        continue
                    
                    # Parse retry delay from API response
                    suggested_delay = self._parse_retry_delay(response_text)
                    
                    # OpenRouter: thêm jitter để tránh thundering herd
                    import random
                    jitter = random.uniform(0.5, 1.5)
                    
                    if len(self.api_keys) > 1 and len(tried_keys) < len(self.api_keys):
                        # Còn key chưa thử → xoay ngay, delay ngắn
                        cooldown = max(suggested_delay * 0.5, 1.0) * jitter
                        self._set_key_cooldown(current_idx, max(suggested_delay, 30.0))
                        logger.warning(
                            f"⏳ Key #{current_idx} rate limited (HTTP {status_code}). "
                            f"Xoay sang key khác sau {cooldown:.1f}s..."
                        )
                        self.rotate_key()
                        await asyncio.sleep(cooldown)
                    else:
                        # Đã thử hết tất cả keys → chờ đầy đủ
                        min_wait = 30.0 if self.provider == "gemini" else base_delay
                        wait_time = max(suggested_delay, min_wait * (1.5 ** min(attempt, 5)))
                        wait_time = min(wait_time, 90.0) * jitter
                        logger.warning(
                            f"⏳ Tất cả key đều bận (HTTP {status_code}). "
                            f"Chờ {wait_time:.1f}s rồi thử lại (attempt {attempt+1}/{max_attempts})..."
                        )
                        tried_keys.clear()  # Reset để thử lại vòng mới
                        consecutive_rate_limits = 0
                        self.rotate_key()
                        await asyncio.sleep(wait_time)
                    continue
                    
                else:
                    # Other HTTP errors (4xx, 5xx)
                    logger.warning(f"HTTP Error {status_code} lần {attempt+1}: {response_text[:200]}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(base_delay * (2 ** min(attempt, 3)))
                    
            except ValueError as val_err:
                logger.error(f"Value error: {val_err}. Aborting retries.")
                raise val_err
            except httpx.TimeoutException as timeout_err:
                logger.warning(f"Timeout lần {attempt+1}: {str(timeout_err)}")
                self.rotate_key()
                if attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay)
            except Exception as e:
                logger.warning(f"Connection error lần {attempt+1}: {str(e)}")
                self.rotate_key()
                if attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay * (2 ** min(attempt, 3)))
                
        # Final attempt
        api_key = self.get_current_key()
        try:
            return await self._call_api(prompt, system_instruction, api_key)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            response_text = e.response.text
            if status_code in [400, 401, 403, 429] or "quota" in response_text.lower() or "limit" in response_text.lower():
                raise ValueError(f"Client error '{status_code}': {response_text[:200]}")
            raise e

    async def _call_api(self, prompt: str, system_instruction: str, api_key: str) -> Dict[str, Any]:
        """Performs raw HTTP request with adaptive concurrency limiting."""
        await global_limiter.acquire()
        try:
            result = await self._call_api_internal(prompt, system_instruction, api_key)
            await global_limiter.on_success()
            return result
        finally:
            await global_limiter.release()

    async def _call_api_internal(self, prompt: str, system_instruction: str, api_key: str) -> Dict[str, Any]:
        """Performs raw HTTP request to the selected API."""
        # Timeout 55s (giảm từ 90s) để tránh block lâu; OpenRouter thường trả lời nhanh
        client_context = DummyAsyncContext(self.http_client) if self.http_client is not None else httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=55.0, write=15.0, pool=5.0)
        )
        async with client_context as client:
            if self.provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.25,
                        "maxOutputTokens": 65536
                    },
                    "safetySettings": [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                    ]
                }
                if system_instruction:
                    payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
                
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                
                if "promptFeedback" in res_data and "blockReason" in res_data["promptFeedback"]:
                    block_reason = res_data["promptFeedback"]["blockReason"]
                    raise ValueError(f"Gemini blocked content: {block_reason}")
                
                try:
                    translated_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    usage = res_data.get("usageMetadata", {})
                    return {
                        "text": translated_text,
                        "input_tokens": usage.get("promptTokenCount", len(prompt) // 2),
                        "output_tokens": usage.get("candidatesTokenCount", len(translated_text) // 2)
                    }
                except (KeyError, IndexError) as e:
                    raise Exception(f"Failed to parse Gemini response: {e}. Raw: {json.dumps(res_data)}")
                    
            elif self.provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                payload = {"model": self.model, "messages": messages, "temperature": 0.25}
                
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                
                try:
                    translated_text = res_data["choices"][0]["message"]["content"].strip()
                    usage = res_data.get("usage", {})
                    return {
                        "text": translated_text,
                        "input_tokens": usage.get("prompt_tokens", len(prompt) // 3),
                        "output_tokens": usage.get("completion_tokens", len(translated_text) // 3)
                    }
                except (KeyError, IndexError) as e:
                    raise Exception(f"Failed to parse OpenAI response: {e}. Raw: {json.dumps(res_data)}")
                    
            elif self.provider == "openrouter":
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/airead/airead2",
                    "X-Title": "AiRead v2"
                }
                
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                model_name = self.model if self.model else "deepseek/deepseek-chat"
                
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.25,
                    # OpenRouter: tắt streaming để giảm overhead, nhận full response ngay
                    "stream": False
                }
                
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                
                # Kiểm tra lỗi OpenRouter dạng {"error": {...}}
                if "error" in res_data and not res_data.get("choices"):
                    err = res_data["error"]
                    err_msg = err.get("message", str(err))
                    err_code = err.get("code", 0)
                    if err_code in [429, 402] or "rate" in err_msg.lower() or "quota" in err_msg.lower():
                        # Simulate HTTP 429 để retry logic xử lý
                        raise httpx.HTTPStatusError(
                            message=f"OpenRouter error: {err_msg}",
                            request=response.request,
                            response=httpx.Response(429, content=json.dumps(res_data).encode())
                        )
                    raise ValueError(f"OpenRouter API error: {err_msg}")
                
                try:
                    translated_text = res_data["choices"][0]["message"]["content"].strip()
                    usage = res_data.get("usage", {})
                    return {
                        "text": translated_text,
                        "input_tokens": usage.get("prompt_tokens", len(prompt) // 3),
                        "output_tokens": usage.get("completion_tokens", len(translated_text) // 3)
                    }
                except (KeyError, IndexError) as e:
                    raise Exception(f"Failed to parse OpenRouter response: {e}. Raw: {json.dumps(res_data)}")

            elif self.provider == "claude":
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "prompt-caching-2024-07-31"
                }
                
                payload = {
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.25
                }
                if system_instruction:
                    payload["system"] = [
                        {
                            "type": "text",
                            "text": system_instruction,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                    
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                
                try:
                    translated_text = res_data["content"][0]["text"].strip()
                    usage = res_data.get("usage", {})
                    return {
                        "text": translated_text,
                        "input_tokens": usage.get("input_tokens", len(prompt) // 3),
                        "output_tokens": usage.get("output_tokens", len(translated_text) // 3)
                    }
                except (KeyError, IndexError) as e:
                    raise Exception(f"Failed to parse Claude response: {e}. Raw: {json.dumps(res_data)}")
            else:
                raise ValueError(f"Unsupported AI provider: {self.provider}")

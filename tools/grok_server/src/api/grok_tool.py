import asyncio
import json
import time
from pathlib import Path
from typing import Optional
from loguru import logger
from src.browser.browser_manager import BrowserManager
from src.browser.page_controller import PageController
from src.adapters.grok_adapter import GrokAdapter
from src.pipelines.response_pipeline import ResponsePipeline
from src.core.config import ConfigManager

DEFAULT_PROMPT_PREFIX = "Dịch văn bản sau sang tiếng Việt chuẩn, mượt mà, văn phong truyện đọc:"
VALID_COOKIE_DOMAINS = [".grok.com", "grok.com"]
INVALID_COOKIE_NAMES = {"cf_clearance", "cf_chl_rc_ni", "__cf_bm"}
AUTH_COOKIE_KEYWORDS = ["session", "auth", "token", "jwt", "grok", "sid", "user", "xauth", "login"]

PROMPT_SELECTORS = [
    "textarea[placeholder*='What do you want to know']",
    "textarea[placeholder*='Ask']",
    "textarea[placeholder*='Message']",
    "textarea[placeholder*='Grok']",
    "textarea[aria-label*='Ask']",
    "textarea[aria-label*='Grok']",
    "div[contenteditable='true']",
    "[role='textbox']",
    "textarea"
]

LOGIN_CHECK_SELECTORS = [
    "a[href*='login']",
    "button:has-text('Log in')",
    "button:has-text('Sign in')"
]


class GrokTool:
    def __init__(self, config_path: str = "config/config.yaml", selectors_path: str = "config/selectors.yaml"):
        TOOL_ROOT = Path(__file__).resolve().parent.parent.parent
        if not os.path.isabs(config_path):
            config_path = str(TOOL_ROOT / config_path)
        if not os.path.isabs(selectors_path):
            selectors_path = str(TOOL_ROOT / selectors_path)

        self.config = ConfigManager(config_path=config_path, selectors_path=selectors_path)
        browser_config = self.config.get("browser", {})

        raw_user_data_dir = browser_config.get("user_data_dir", "user_data/edge_profile")
        if not os.path.isabs(raw_user_data_dir):
            user_data_dir = str(TOOL_ROOT / raw_user_data_dir)
        else:
            user_data_dir = raw_user_data_dir

        self.browser_manager = BrowserManager(
            user_data_dir=user_data_dir,
            headless=browser_config.get("headless", False),
            viewport=browser_config.get("viewport", {"width": 1280, "height": 900}),
            slow_mo=browser_config.get("slow_mo", 50),
            remote_debug_port=browser_config.get("remote_debug_port", 9222)
        )

        self.response_pipeline = ResponsePipeline()
        self.page_controller: Optional[PageController] = None
        self.adapter: Optional[GrokAdapter] = None
        
        self.cookie_file = Path(user_data_dir) / "cookies.json"
        if not self.cookie_file.exists() and (TOOL_ROOT / "cookies.json").exists():
            self.cookie_file = TOOL_ROOT / "cookies.json"

    async def start(self) -> None:
        page = await self.browser_manager.start()
        self.page_controller = PageController(page=page, config_manager=self.config, provider="grok")
        self.adapter = GrokAdapter(page_controller=self.page_controller, response_pipeline=self.response_pipeline)

    async def close(self) -> None:
        await self.browser_manager.stop()

    def _is_auth_cookie(self, cookie: dict) -> bool:
        name = cookie.get("name", "").lower()
        if name in INVALID_COOKIE_NAMES:
            return False
        return any(keyword in name for keyword in AUTH_COOKIE_KEYWORDS)

    def _cookies_file_valid(self) -> bool:
        if not self.cookie_file.exists():
            return False

        try:
            with self.cookie_file.open("r", encoding="utf-8") as f:
                cookies = json.load(f)
            now = time.time()
            has_auth = False
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                domain = cookie.get("domain", "")
                if not any(domain.endswith(valid) for valid in VALID_COOKIE_DOMAINS):
                    continue
                expires = cookie.get("expires")
                if expires is not None and expires != 0 and expires <= now:
                    continue
                if self._is_auth_cookie(cookie):
                    has_auth = True
                    break
            return has_auth
        except Exception as e:
            logger.warning(f"[GrokTool] Lỗi kiểm tra file cookie: {e}")
        return False

    async def _load_cookies(self) -> bool:
        if not self.page_controller or not self.page_controller.page or self.page_controller.page.is_closed():
            return False
        if not self.cookie_file.exists():
            return False

        try:
            with self.cookie_file.open("r", encoding="utf-8") as f:
                cookies = json.load(f)
            if not isinstance(cookies, list) or not cookies:
                return False

            context = self.page_controller.page.context
            if context is None:
                return False

            sanitized_cookies = []
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                sanitized = {
                    key: cookie[key]
                    for key in [
                        "name",
                        "value",
                        "domain",
                        "path",
                        "expires",
                        "httpOnly",
                        "secure",
                        "sameSite",
                        "url"
                    ]
                    if key in cookie
                }
                if not sanitized.get("domain") and sanitized.get("url"):
                    continue
                if sanitized:
                    sanitized_cookies.append(sanitized)

            if not sanitized_cookies:
                return False

            await context.add_cookies(sanitized_cookies)
            logger.info(f"[GrokTool] Đã tải {len(sanitized_cookies)} cookie từ '{self.cookie_file}'.")
            return True
        except Exception as e:
            logger.warning(f"[GrokTool] Không thể tải cookie: {e}")
            return False

    async def _save_cookies(self, context) -> None:
        try:
            cookies = await context.cookies()
            self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
            with self.cookie_file.open("w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"[GrokTool] Lưu thành công {len(cookies)} cookie vào '{self.cookie_file}'.")
        except Exception as e:
            logger.warning(f"[GrokTool] Không thể lưu cookie: {e}")

    async def _has_valid_session(self) -> bool:
        if not self.page_controller or not self.page_controller.page or self.page_controller.page.is_closed():
            return False

        page = self.page_controller.page
        url = page.url.lower() if page.url else ""
        if any(item in url for item in ["/login", "/signin", "auth.x.com"]):
            logger.warning("[GrokTool] URL chứa biểu tượng login, session chưa hợp lệ.")
            return False

        # Use configured selectors when available
        login_selectors = self.page_controller.selectors.get("login_indicator", LOGIN_CHECK_SELECTORS)
        prompt_selectors = self.page_controller.selectors.get("textbox", PROMPT_SELECTORS)

        await asyncio.sleep(1)

        for selector in login_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    logger.warning(f"[GrokTool] Phát hiện login indicator '{selector}'. Session chưa hợp lệ.")
                    return False
            except Exception:
                pass

        for selector in prompt_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    logger.info(f"[GrokTool] Phát hiện prompt selector hợp lệ: '{selector}'. Session có thể dùng được.")
                    return True
            except Exception:
                pass

        logger.warning("[GrokTool] Không tìm thấy input prompt hợp lệ. Session có thể không dùng được.")
        return False

    async def _login_flow(self) -> bool:
        if self.page_controller is None or self.adapter is None:
            await self.start()

        if not await self.adapter.connect():
            logger.warning("[GrokTool] Không thể mở trang Grok để đăng nhập.")
            return False

        print("\n⚠️ Phiên Grok chưa đăng nhập hoặc cookie đã hết hạn.")
        print("👉 Vui lòng đăng nhập Grok trong trình duyệt Edge đang mở.")
        print("👉 Sau khi đăng nhập xong, quay lại terminal và nhấn ENTER.")
        input("Nhấn ENTER để tiếp tục: ")

        await self.page_controller.open_chat()
        valid = await self._has_valid_session()
        if valid and self.page_controller:
            await self._save_cookies(self.page_controller.page.context)
        return valid

    async def _ensure_authenticated(self) -> bool:
        if self.page_controller is None or self.adapter is None:
            await self.start()

        if self._cookies_file_valid():
            await self._load_cookies()

        if not await self.adapter.connect():
            logger.warning("[GrokTool] Không thể mở Grok.")
            return False

        if await self._has_valid_session():
            return True

        if self._cookies_file_valid():
            logger.info("[GrokTool] Cookie đã được nạp, thử kiểm tra lại phiên Grok...")
            await self.page_controller.open_chat()
            if await self._has_valid_session():
                return True

        return await self._login_flow()

    async def request(self, text: str, prompt_prefix: Optional[str] = None, timeout: float = 120.0) -> Optional[str]:
        if not text or not text.strip():
            logger.error("[GrokTool] Yêu cầu không được để trống.")
            return None

        if self.page_controller is None or self.adapter is None:
            await self.start()

        if not await self._ensure_authenticated():
            logger.error("[GrokTool] Phiên Grok không hợp lệ sau khi kiểm tra.")
            return None

        prompt = f"{prompt_prefix or DEFAULT_PROMPT_PREFIX}\n\n{text.strip()}"
        logger.info("[GrokTool] Gửi yêu cầu tới Grok...")
        success = await self.adapter.send_prompt(prompt)
        if not success:
            logger.error("[GrokTool] Gửi prompt thất bại.")
            return None

        response = await self.adapter.wait_response(
            timeout=timeout,
            stability_wait=self.config.get("engine.stability_wait_seconds", 3.0)
        )
        if response:
            logger.info("[GrokTool] Đã nhận phản hồi từ Grok.")
            return response

        logger.error("[GrokTool] Không nhận được phản hồi từ Grok.")
        return None

    async def async_run(self, text: str, prompt_prefix: Optional[str] = None, timeout: float = 120.0) -> Optional[str]:
        try:
            return await self.request(text, prompt_prefix=prompt_prefix, timeout=timeout)
        finally:
            await self.close()

    def run(self, text: str, prompt_prefix: Optional[str] = None, timeout: float = 120.0) -> Optional[str]:
        return asyncio.run(self.async_run(text, prompt_prefix=prompt_prefix, timeout=timeout))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Grok Tool: Gửi yêu cầu đến Grok qua trình duyệt Edge thật.")
    parser.add_argument("text", nargs="+", help="Văn bản yêu cầu gửi đến Grok")
    parser.add_argument("--prefix", help="Tiền tố prompt", default=DEFAULT_PROMPT_PREFIX)
    parser.add_argument("--timeout", type=float, default=120.0, help="Thời gian chờ phản hồi (giây)")
    args = parser.parse_args()

    request_text = " ".join(args.text)
    tool = GrokTool()
    result = tool.run(request_text, prompt_prefix=args.prefix, timeout=args.timeout)
    if result is not None:
        print("\n=== KẾT QUẢ GROK ===")
        print(result)
        print("====================")

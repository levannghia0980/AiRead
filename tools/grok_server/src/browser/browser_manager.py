import asyncio
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page
from loguru import logger

class BrowserManager:
    """
    Layer 1: Browser Automation Manager.
    Attaches to a real Microsoft Edge instance using CDP, avoiding artificial automation profiles.
    """
    def __init__(self, user_data_dir: Optional[str] = None, headless: bool = False, viewport: Optional[dict] = None, slow_mo: int = 50, remote_debug_port: int = 9222):
        if user_data_dir:
            self.user_data_dir = Path(user_data_dir)
        else:
            local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            self.user_data_dir = local_appdata / "EdgeGrok" / "User Data"

        if not self.user_data_dir.is_absolute():
            self.user_data_dir = Path.cwd() / self.user_data_dir

        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 900}
        self.slow_mo = slow_mo
        self.remote_debug_port = remote_debug_port

        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._edge_process: Optional[subprocess.Popen] = None
        self._lock = asyncio.Lock()

    @property
    def page(self) -> Optional[Page]:
        return self._page

    @property
    def context(self) -> Optional[BrowserContext]:
        return self._context

    def is_alive(self) -> bool:
        return self._context is not None and self._page is not None and not self._page.is_closed()

    def _find_edge_executable(self) -> Optional[str]:
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
        ]
        return next((path for path in candidates if path and Path(path).exists()), None)

    def _is_port_open(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    def _wait_for_port(self, timeout: int = 20) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self._is_port_open(self.remote_debug_port):
                return True
            time.sleep(0.5)
        return False

    def _launch_edge_with_cdp(self) -> subprocess.Popen:
        edge_exe = self._find_edge_executable()
        if edge_exe is None:
            raise RuntimeError("Không tìm thấy Microsoft Edge trên máy. Vui lòng cài đặt hoặc kiểm tra đường dẫn.")

        args = [
            edge_exe,
            f"--remote-debugging-port={self.remote_debug_port}",
            f"--user-data-dir={str(self.user_data_dir)}",
            "--profile-directory=Default",
            "--start-maximized",
            "--no-first-run",
            "--disable-features=AutomationControlled",
        ]

        logger.info(f"[BrowserManager] Khởi động Edge thật với remote debugging port={self.remote_debug_port}...")
        return subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)

    async def start(self) -> Page:
        async with self._lock:
            if self.is_alive():
                return self._page

            if not self._is_port_open(self.remote_debug_port):
                self._edge_process = self._launch_edge_with_cdp()
                if not self._wait_for_port():
                    raise RuntimeError("Không thể kết nối đến Edge qua cổng remote debugging.")
            else:
                logger.info(f"[BrowserManager] Đã tìm thấy Edge đang chạy trên cổng {self.remote_debug_port}.")

            self._playwright = await async_playwright().start()
            browser = await self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.remote_debug_port}")
            contexts = browser.contexts
            self._context = contexts[0] if contexts else await browser.new_context()
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

            logger.info("[BrowserManager] Kết nối đến Edge thật thành công.")
            return self._page

    async def stop(self):
        async with self._lock:
            logger.info("[BrowserManager] Stopping browser...")
            if self._page and not self._page.is_closed():
                try:
                    await self._page.close()
                except Exception as e:
                    logger.warning(f"[BrowserManager] Error closing page: {e}")

            if self._context:
                try:
                    await self._context.close()
                except Exception as e:
                    logger.warning(f"[BrowserManager] Error closing context: {e}")

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning(f"[BrowserManager] Error stopping playwright: {e}")

            if self._edge_process is not None:
                try:
                    self._edge_process.terminate()
                    self._edge_process.wait(timeout=5)
                except Exception as e:
                    logger.warning(f"[BrowserManager] Error stopping Edge process: {e}")
                finally:
                    self._edge_process = None

            self._page = None
            self._context = None
            self._playwright = None
            logger.info("[BrowserManager] Browser stopped.")

    async def restart(self) -> Page:
        logger.warning("[BrowserManager] Restarting browser engine...")
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    async def new_tab(self) -> Page:
        if not self._context:
            await self.start()
        self._page = await self._context.new_page()
        return self._page

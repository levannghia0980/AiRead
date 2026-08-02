import sys
import asyncio
import logging

logger = logging.getLogger(__name__)

class PlaywrightManager:
    """
    Singleton manager to maintain a single Chromium browser instance.
    This saves CPU/memory and avoids 2-3 seconds startup cost per chapter scrape.
    """
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def get_browser(self):
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception as e:
                logger.warning(f"Could not set WindowsProactorEventLoopPolicy: {e}")

        async with self._lock:
            if not self._playwright:
                from playwright.async_api import async_playwright
                logger.info("Initializing Playwright...")
                try:
                    self._playwright = await async_playwright().start()
                except NotImplementedError as e:
                    logger.error(f"Playwright start failed due to Windows Event Loop policy: {e}")
                    raise Exception("Playwright không tương thích với EventLoop hiện tại.")
            if not self._browser:
                logger.info("Launching shared Chromium browser instance...")
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu",
                    ]
                )
            return self._browser

    async def close(self):
        async with self._lock:
            if self._browser:
                logger.info("Closing shared Playwright browser...")
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.warning(f"Error closing Playwright browser: {e}")
                self._browser = None
            if self._playwright:
                logger.info("Stopping Playwright context...")
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping Playwright: {e}")
                self._playwright = None

# Global shared instance
playwright_manager = PlaywrightManager()

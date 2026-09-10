import asyncio
import time
from typing import Optional, List, Dict, Any
from playwright.async_api import Page, BrowserContext
from loguru import logger
from src.core.state_machine import ConnectionStateMachine, ConnectionState
from src.core.event_bus import EventBus
from src.core.database import DatabaseManager

class SessionManager:
    """
    Layer 2: Session Manager.
    Monitors cookies, tokens, and authentication status without interacting with DOM elements.
    """
    def __init__(
        self,
        state_machine: ConnectionStateMachine,
        event_bus: EventBus,
        db_manager: DatabaseManager,
        provider: str = "grok",
        check_interval: int = 30
    ):
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.db = db_manager
        self.provider = provider
        self.check_interval = check_interval
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def check_login_status(self, page: Page, login_indicators: Optional[List[str]] = None) -> bool:
        """
        Check if session is usable. If input box is available (guest or logged-in), returns True.
        """
        if not page or page.is_closed():
            return False

        try:
            url = page.url.lower()
            # If explicitly redirected to signin/login page
            if "/login" in url or "/signin" in url or "auth.x.com" in url:
                logger.warning(f"[SessionManager] URL explicitly on login page: {url}")
                return False

            # Check if prompt textbox is accessible on DOM
            textbox_selectors = [
                "textarea[placeholder*='Ask']",
                "textarea[placeholder*='Grok']",
                "textarea[aria-label*='Ask']",
                "textarea",
                "div[contenteditable='true']",
                "[role='textbox']"
            ]
            for sel in textbox_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        logger.info(f"[SessionManager] Promp input box is accessible ('{sel}'). Session is READY.")
                        cookies = await page.context.cookies()
                        await self.db.update_session_state(self.provider, "LOGGED_IN", cookies=cookies)
                        return True
                except Exception:
                    pass

            # If no input box is found and login indicator is visible
            if login_indicators:
                for selector in login_indicators:
                    try:
                        element = await page.query_selector(selector)
                        if element and await element.is_visible():
                            logger.warning(f"[SessionManager] Login required button visible ({selector}) -> Logged out!")
                            return False
                    except Exception:
                        pass

            return True

        except Exception as e:
            logger.error(f"[SessionManager] Error checking login status: {e}")
            return False

    async def monitor_loop(self, page_getter):
        """Continuous coroutine checking login state every check_interval seconds."""
        self._is_running = True
        logger.info(f"[SessionManager] Starting session monitor loop ({self.check_interval}s interval)...")
        while self._is_running:
            try:
                page = page_getter()
                if page and not page.is_closed() and self.state_machine.state not in (ConnectionState.BUSY, ConnectionState.WAITING_RESPONSE, ConnectionState.RECOVERING):
                    is_ready = await self.check_login_status(page)
                    if not is_ready and self.state_machine.state != ConnectionState.PAUSED:
                        logger.warning("[SessionManager] Input/Login lost! Pausing connection engine...")
                        await self.event_bus.publish("LoginRequired", provider=self.provider)
                        if self.state_machine.state in (ConnectionState.READY, ConnectionState.LOGIN_CHECK):
                            await self.state_machine.transition_to(ConnectionState.PAUSED, reason="Authentication Required")
                    elif is_ready and self.state_machine.state == ConnectionState.PAUSED:
                        logger.info("[SessionManager] Input/Login restored! Resuming connection engine...")
                        await self.state_machine.transition_to(ConnectionState.READY, reason="Session restored")
            except Exception as e:
                logger.error(f"[SessionManager] Exception in monitor loop: {e}")

            await asyncio.sleep(self.check_interval)

    def start_monitoring(self, page_getter):
        if not self._monitoring_task or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self.monitor_loop(page_getter))

    def stop_monitoring(self):
        self._is_running = False
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()

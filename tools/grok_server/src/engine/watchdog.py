import asyncio
import time
from typing import Optional
from loguru import logger
from src.core.state_machine import ConnectionStateMachine, ConnectionState
from src.core.event_bus import EventBus
from src.engine.recovery import RecoveryEngine

class SystemWatchdog:
    """
    Background Watchdog and Heartbeat monitor coroutines.
    Heartbeat (30s): Quick process/page ping.
    Watchdog (5s): Deep state and operational health check.
    """
    def __init__(
        self,
        state_machine: ConnectionStateMachine,
        event_bus: EventBus,
        recovery_engine: RecoveryEngine,
        heartbeat_interval: int = 30,
        watchdog_interval: int = 5
    ):
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.recovery = recovery_engine
        self.heartbeat_interval = heartbeat_interval
        self.watchdog_interval = watchdog_interval

        self._heartbeat_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_heartbeat_pass = time.time()
        self._last_busy_time = time.time()

    async def heartbeat_loop(self, browser_manager, adapter):
        """Heartbeat check every 30 seconds to confirm browser connectivity."""
        logger.info(f"[Watchdog] Heartbeat loop started ({self.heartbeat_interval}s interval)...")
        while self._is_running:
            try:
                if browser_manager.is_alive():
                    # Quick ping
                    page = browser_manager.page
                    if page and not page.is_closed():
                        title = await asyncio.wait_for(page.title(), timeout=10.0)
                        self._last_heartbeat_pass = time.time()
                        logger.debug(f"[Watchdog] Heartbeat PASS (Title: {title[:30]})")
                        await self.event_bus.publish("HeartbeatPassed")
                    else:
                        raise Exception("Page closed or missing")
                else:
                    raise Exception("Browser context dead")
            except Exception as e:
                logger.warning(f"[Watchdog] Heartbeat FAIL: {e}")
                await self.event_bus.publish("HeartbeatFailed", error=str(e))
                if self.state_machine.state in (ConnectionState.READY, ConnectionState.ERROR):
                    await self.recovery.execute_recovery(level=4, browser_manager=browser_manager, adapter=adapter, reason=f"Heartbeat failure: {e}")

            await asyncio.sleep(self.heartbeat_interval)

    async def watchdog_loop(self, browser_manager, adapter):
        """Watchdog check every 5 seconds for deep health inspection."""
        logger.info(f"[Watchdog] Watchdog loop started ({self.watchdog_interval}s interval)...")
        while self._is_running:
            try:
                current_state = self.state_machine.state

                # Check stuck WAITING_RESPONSE (> 150s)
                if current_state in (ConnectionState.BUSY, ConnectionState.WAITING_RESPONSE):
                    if time.time() - self._last_busy_time > 150:
                        logger.error("[Watchdog] Engine stuck in BUSY/WAITING_RESPONSE for > 150s! Triggering recovery.")
                        self._last_busy_time = time.time()
                        await self.recovery.execute_recovery(level=3, browser_manager=browser_manager, adapter=adapter, reason="Response stuck timeout")
                else:
                    self._last_busy_time = time.time()

                # Check if browser died while state claims READY
                if current_state == ConnectionState.READY and not browser_manager.is_alive():
                    logger.error("[Watchdog] State is READY but browser is dead! Triggering recovery.")
                    await self.recovery.execute_recovery(level=5, browser_manager=browser_manager, adapter=adapter, reason="Browser unexpected termination")

            except Exception as e:
                logger.error(f"[Watchdog] Error in watchdog loop: {e}")

            await asyncio.sleep(self.watchdog_interval)

    def start(self, browser_manager, adapter):
        """Launch background coroutines."""
        self._is_running = True
        self._heartbeat_task = asyncio.create_task(self.heartbeat_loop(browser_manager, adapter))
        self._watchdog_task = asyncio.create_task(self.watchdog_loop(browser_manager, adapter))

    def stop(self):
        """Cancel background tasks."""
        self._is_running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        logger.info("[Watchdog] Watchdog and Heartbeat stopped.")

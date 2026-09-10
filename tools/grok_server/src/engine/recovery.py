import asyncio
from typing import Callable, Optional
from loguru import logger
from src.core.state_machine import ConnectionStateMachine, ConnectionState
from src.core.event_bus import EventBus

class RecoveryEngine:
    """
    Multi-Level Cascading Recovery Engine.
    Executes staged escalation recovery without tearing down the entire system unnecessarily.
    Level 1: Selector / DOM Retry
    Level 2: Reload Page
    Level 3: Open New Chat
    Level 4: Create New Tab / Context Reconnect
    Level 5: Restart Browser Process
    Level 6: Full Engine Re-initialization
    """
    def __init__(self, state_machine: ConnectionStateMachine, event_bus: EventBus):
        self.state_machine = state_machine
        self.event_bus = event_bus

    async def execute_recovery(
        self,
        level: int,
        browser_manager,
        adapter,
        reason: str = "Unknown"
    ) -> bool:
        """
        Executes a specific level of recovery.
        """
        logger.warning(f"[RecoveryEngine] TRIGGERED Level {level} Recovery! Reason: {reason}")
        await self.event_bus.publish("RecoveryTriggered", level=level, reason=reason)
        
        # Transition state machine to RECOVERING
        try:
            await self.state_machine.transition_to(ConnectionState.RECOVERING, reason=f"Level {level} Recovery: {reason}")
        except Exception:
            pass

        success = False
        try:
            if level == 1:
                # Level 1: Quick retry / wait
                logger.info("[RecoveryEngine] Level 1: DOM Retry / Waiting 2 seconds...")
                await asyncio.sleep(2)
                success = adapter.controller.page is not None and not adapter.controller.page.is_closed()

            elif level == 2:
                # Level 2: Page reload
                logger.info("[RecoveryEngine] Level 2: Reloading current page...")
                page = adapter.controller.page
                if page and not page.is_closed():
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    success = True

            elif level == 3:
                # Level 3: Open new chat
                logger.info("[RecoveryEngine] Level 3: Opening new chat session...")
                success = await adapter.new_chat()

            elif level == 4:
                # Level 4: Reconnect context / new tab
                logger.info("[RecoveryEngine] Level 4: Opening new browser tab...")
                page = await browser_manager.new_tab()
                adapter.controller.set_page(page)
                success = await adapter.connect()

            elif level == 5:
                # Level 5: Restart browser
                logger.info("[RecoveryEngine] Level 5: Restarting browser process...")
                page = await browser_manager.restart()
                adapter.controller.set_page(page)
                success = await adapter.connect()

            elif level >= 6:
                # Level 6: Complete reset
                logger.info("[RecoveryEngine] Level 6: Performing full engine reset...")
                await browser_manager.stop()
                await asyncio.sleep(2)
                page = await browser_manager.start()
                adapter.controller.set_page(page)
                success = await adapter.connect()

        except Exception as e:
            logger.error(f"[RecoveryEngine] Level {level} recovery failed with error: {e}")
            success = False

        if success:
            logger.info(f"[RecoveryEngine] Level {level} Recovery SUCCESSFUL.")
            await self.event_bus.publish("RecoveryCompleted", level=level, success=True)
            await self.state_machine.transition_to(ConnectionState.READY, reason="Recovery Success")
            return True
        else:
            logger.error(f"[RecoveryEngine] Level {level} Recovery FAILED.")
            await self.event_bus.publish("RecoveryCompleted", level=level, success=False)
            if level < 6:
                # Escalate to next level
                return await self.execute_recovery(level + 1, browser_manager, adapter, reason=f"Escalated from L{level} failure")
            else:
                await self.state_machine.transition_to(ConnectionState.ERROR, reason="Max recovery level failed")
                return False

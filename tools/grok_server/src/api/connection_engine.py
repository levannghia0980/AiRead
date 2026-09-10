import asyncio
from typing import Dict, Any, Optional
from loguru import logger

from src.core.config import ConfigManager
from src.core.logger import setup_logger
from src.core.state_machine import ConnectionStateMachine, ConnectionState
from src.core.event_bus import EventBus
from src.core.database import DatabaseManager

from src.browser.browser_manager import BrowserManager
from src.browser.session_manager import SessionManager
from src.browser.page_controller import PageController

from src.adapters.grok_adapter import GrokAdapter
from src.adapters.chatgpt_adapter import ChatGPTAdapter

from src.pipelines.prompt_pipeline import PromptPipeline
from src.pipelines.response_pipeline import ResponsePipeline

from src.engine.recovery import RecoveryEngine
from src.engine.watchdog import SystemWatchdog
from src.engine.queue_worker import QueueWorker

class ConnectionEngine:
    """
    Public Facade API for the Grok Web Connection Middleware.
    Applications ONLY interact with this class. No raw Playwright code is exposed.
    """
    def __init__(self, config_path: str = "config/config.yaml", selectors_path: str = "config/selectors.yaml"):
        # 1. Load Configurations & Setup Logger
        self.config = ConfigManager(config_path=config_path, selectors_path=selectors_path)
        setup_logger(
            log_dir=self.config.get("logging.log_dir", "logs"),
            log_level=self.config.get("logging.level", "INFO"),
            rotation=self.config.get("logging.rotation", "10 MB"),
            retention=self.config.get("logging.retention", "30 days")
        )

        # 2. Core Infrastructure
        self.state_machine = ConnectionStateMachine()
        self.event_bus = EventBus()
        self.db = DatabaseManager(db_path=self.config.get("database.path", "data/grok_engine.db"))

        # 3. Layer 1 Browser Manager
        self.browser_manager = BrowserManager(
            user_data_dir=self.config.get("browser.user_data_dir", "user_data/edge_profile"),
            headless=self.config.get("browser.headless", False),
            viewport=self.config.get("browser.viewport", {"width": 1280, "height": 900}),
            slow_mo=self.config.get("browser.slow_mo", 50),
            remote_debug_port=self.config.get("browser.remote_debug_port", 9222)
        )

        # 4. Pipelines
        self.prompt_pipeline = PromptPipeline()
        self.response_pipeline = ResponsePipeline()

        # 5. Layer 2 Session Manager
        self.session_manager = SessionManager(
            state_machine=self.state_machine,
            event_bus=self.event_bus,
            db_manager=self.db,
            check_interval=self.config.get("engine.session_check_interval", 30)
        )

        # 6. Recovery & Watchdogs & Queue
        self.recovery_engine = RecoveryEngine(state_machine=self.state_machine, event_bus=self.event_bus)
        self.watchdog = SystemWatchdog(
            state_machine=self.state_machine,
            event_bus=self.event_bus,
            recovery_engine=self.recovery_engine,
            heartbeat_interval=self.config.get("engine.heartbeat_interval", 30),
            watchdog_interval=self.config.get("engine.watchdog_interval", 5)
        )
        self.queue_worker = QueueWorker(
            state_machine=self.state_machine,
            event_bus=self.event_bus,
            db_manager=self.db,
            prompt_pipeline=self.prompt_pipeline,
            max_retries=self.config.get("engine.max_retries", 4)
        )

        self.adapter: Optional[Any] = None
        self.controller: Optional[PageController] = None

    async def connect(self, provider: str = "grok") -> bool:
        """
        Initializes database, launches browser persistent context, checks auth, and sets state to READY.
        """
        logger.info(f"[ConnectionEngine] Starting engine connection for provider: {provider}")
        await self.state_machine.transition_to(ConnectionState.STARTING, reason="Connection Engine Start")
        await self.db.initialize()

        # Launch Browser (Layer 1)
        page = await self.browser_manager.start()

        # Layer 3 Page Controller
        self.controller = PageController(page=page, config_manager=self.config, provider=provider)

        # Protocol Adapter (Grok / ChatGPT)
        if provider == "chatgpt":
            self.adapter = ChatGPTAdapter(page_controller=self.controller, response_pipeline=self.response_pipeline)
        else:
            self.adapter = GrokAdapter(page_controller=self.controller, response_pipeline=self.response_pipeline)

        # Connect adapter to target URL
        connected = await self.adapter.connect()
        if not connected:
            logger.error(f"[ConnectionEngine] Adapter failed to connect to {provider} web interface.")
            await self.state_machine.transition_to(ConnectionState.ERROR, reason="Adapter Connect Failed")
            return False

        # Session Auth Check (Layer 2)
        await self.state_machine.transition_to(ConnectionState.LOGIN_CHECK, reason="Authenticating session")
        is_logged_in = await self.session_manager.check_login_status(
            page,
            login_indicators=self.config.get_selectors(provider).get("login_indicator")
        )

        if not is_logged_in:
            logger.warning("[ConnectionEngine] User is not logged in. Connection engine PAUSED for authentication.")
            await self.state_machine.transition_to(ConnectionState.PAUSED, reason="Waiting for user login in browser")
        else:
            await self.state_machine.transition_to(ConnectionState.READY, reason="Engine Connected and Authenticated")

        # Start Background Watchdog, Session Monitor & Queue Worker
        self.session_manager.start_monitoring(lambda: self.browser_manager.page)
        self.watchdog.start(self.browser_manager, self.adapter)
        self.queue_worker.start(self.adapter, self.recovery_engine, self.browser_manager)

        logger.info(f"[ConnectionEngine] Connection Engine initialized! State: {self.state_machine.state.name}")
        return True

    async def translate(self, text: str, provider: str = "grok", prompt_prefix: Optional[str] = None) -> str:
        """
        High-level translation / text processing method.
        Queues task, preprocesses text, submits to browser engine, and returns response string.
        """
        prefix = prompt_prefix or "Dịch văn bản sau sang tiếng Việt chuẩn, mượt mà, văn phong truyện đọc:"
        full_prompt = f"{prefix}\n\n{text}"
        return await self.send_prompt(full_prompt, provider=provider)

    async def send_prompt(self, text: str, provider: str = "grok") -> str:
        """
        Submits prompt to engine queue and awaits result asynchronously.
        """
        return await self.queue_worker.submit_task(prompt=text, provider=provider)

    async def new_chat(self) -> bool:
        """Resets chat session in browser."""
        if self.adapter:
            return await self.adapter.new_chat()
        return False

    async def health(self) -> Dict[str, Any]:
        """Returns engine diagnostic health metrics."""
        is_alive = self.browser_manager.is_alive()
        adapter_ok = await self.adapter.health_check() if self.adapter else False
        return {
            "state": self.state_machine.state.name,
            "browser_alive": is_alive,
            "adapter_healthy": adapter_ok,
            "queue_size": self.queue_worker.queue.qsize(),
            "provider": self.adapter.provider_name if self.adapter else "None"
        }

    async def restart(self):
        """Restarts browser process and reconnects."""
        logger.warning("[ConnectionEngine] Engine restart requested.")
        await self.recovery_engine.execute_recovery(
            level=5,
            browser_manager=self.browser_manager,
            adapter=self.adapter,
            reason="Manual engine restart call"
        )

    async def shutdown(self):
        """Gracefully shuts down watchdogs, queue worker, database, and browser context."""
        logger.info("[ConnectionEngine] Shutting down Connection Engine...")
        self.watchdog.stop()
        self.session_manager.stop_monitoring()
        self.queue_worker.stop()
        await self.browser_manager.stop()
        await self.state_machine.transition_to(ConnectionState.INIT, reason="System Shutdown")
        logger.info("[ConnectionEngine] Shutdown complete.")

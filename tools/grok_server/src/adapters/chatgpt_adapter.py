from typing import Optional
from loguru import logger
from src.adapters.base_adapter import BaseAdapter
from src.browser.page_controller import PageController
from src.pipelines.response_pipeline import ResponsePipeline

class ChatGPTAdapter(BaseAdapter):
    """
    Adapter for ChatGPT Web interface (Demonstrating multi-provider extensibility).
    """
    def __init__(self, page_controller: PageController, response_pipeline: ResponsePipeline):
        self.controller = page_controller
        self.response_pipeline = response_pipeline

    @property
    def provider_name(self) -> str:
        return "chatgpt"

    async def connect(self) -> bool:
        logger.info("[ChatGPTAdapter] Connecting to ChatGPT Web...")
        return await self.controller.open_chat(url="https://chatgpt.com")

    async def send_prompt(self, text: str) -> bool:
        return await self.controller.send_prompt(text)

    async def wait_response(self, timeout: float = 120.0, stability_wait: float = 3.0) -> Optional[str]:
        return await self.response_pipeline.monitor_and_collect(
            controller=self.controller,
            timeout=timeout,
            stability_wait=stability_wait
        )

    async def copy_response(self) -> Optional[str]:
        return await self.controller.get_latest_response()

    async def new_chat(self) -> bool:
        return await self.controller.new_chat()

    async def health_check(self) -> bool:
        try:
            page = self.controller.page
            return page is not None and not page.is_closed()
        except Exception:
            return False

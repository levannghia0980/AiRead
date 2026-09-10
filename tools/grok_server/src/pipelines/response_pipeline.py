import asyncio
import time
from typing import Optional
from loguru import logger
from src.browser.page_controller import PageController

class ResponsePipeline:
    """
    Pipeline for detecting response streaming, completion, and text cleaning.
    Uses hybrid MutationObserver/polling with 3-second stability detection algorithm.
    """

    async def inject_mutation_observer(self, page):
        """Inject JS MutationObserver to track DOM modifications without high CPU polling."""
        js_code = """
        if (!window.__grok_observer_attached) {
            window.__grok_last_change = Date.now();
            const observer = new MutationObserver(() => {
                window.__grok_last_change = Date.now();
            });
            observer.observe(document.body, { childList: true, subtree: true, characterData: true });
            window.__grok_observer_attached = true;
        }
        """
        try:
            await page.evaluate(js_code)
        except Exception as e:
            logger.debug(f"[ResponsePipeline] Could not inject MutationObserver: {e}")

    async def monitor_and_collect(
        self,
        controller: PageController,
        timeout: float = 120.0,
        stability_wait: float = 3.0
    ) -> Optional[str]:
        """
        Monitors DOM response until completion is detected (Stop button gone + response unchanged for stability_wait seconds).
        """
        page = controller.page
        if not page or page.is_closed():
            logger.error("[ResponsePipeline] Invalid page instance.")
            return None

        await self.inject_mutation_observer(page)

        start_time = time.time()
        last_text: Optional[str] = None
        last_change_time = time.time()

        # Initial wait for generation to begin
        await asyncio.sleep(1.0)

        while (time.time() - start_time) < timeout:
            try:
                # 1. Check if generating via Stop button
                generating = await controller.is_generating()
                current_text = await controller.get_latest_response()

                if current_text:
                    if current_text != last_text:
                        last_text = current_text
                        last_change_time = time.time()
                        logger.info(f"[ResponsePipeline] Streaming response length: {len(current_text)} chars...")

                # 2. Check stability condition
                time_since_last_change = time.time() - last_change_time

                if not generating and current_text and time_since_last_change >= stability_wait:
                    logger.info(f"[ResponsePipeline] Response complete! (Stable for {time_since_last_change:.1f}s, length: {len(current_text)})")
                    return self.clean_response(current_text)

            except Exception as e:
                logger.warning(f"[ResponsePipeline] Warning during response collection loop: {e}")

            await asyncio.sleep(0.5)

        logger.error(f"[ResponsePipeline] Response collection timed out after {timeout} seconds.")
        if last_text:
            logger.warning("[ResponsePipeline] Returning partial response after timeout.")
            return self.clean_response(last_text)

        return None

    @staticmethod
    def clean_response(raw_text: str) -> str:
        """Sanitizes and cleans raw LLM response text."""
        cleaned = raw_text.strip()
        # Remove trailing artifact markers if present
        if cleaned.endswith("▋") or cleaned.endswith("■"):
            cleaned = cleaned[:-1].strip()
        return cleaned

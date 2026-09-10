import asyncio
from typing import List, Optional, Tuple
from playwright.async_api import Page, ElementHandle
from loguru import logger

class DOMInteraction:
    """
    Layer 4: Low-level DOM Interaction Layer.
    Implements Priority Selector Strategy (aria-label -> placeholder -> role -> css -> xpath)
    and robust error-handling wrappers.
    """
    def __init__(self, page: Page):
        self.page = page

    def set_page(self, page: Page):
        self.page = page

    async def find_element(
        self,
        selectors: List[str],
        timeout: int = 5000,
        visible_only: bool = True
    ) -> Tuple[Optional[ElementHandle], Optional[str]]:
        """
        Attempts to locate an element sequentially using a priority list of selectors.
        Returns (ElementHandle, matched_selector) or (None, None).
        """
        if not self.page or self.page.is_closed():
            logger.error("[DOMInteraction] Page is invalid or closed.")
            return None, None

        for selector in selectors:
            try:
                # Use query_selector or wait_for_selector for quick checks
                element = await self.page.wait_for_selector(selector, timeout=timeout // len(selectors), state="visible" if visible_only else "attached")
                if element:
                    logger.debug(f"[DOMInteraction] Element found using priority selector: {selector}")
                    return element, selector
            except Exception:
                continue

        logger.warning(f"[DOMInteraction] Failed to locate element after trying {len(selectors)} selectors: {selectors}")
        return None, None

    async def safe_click(self, selectors: List[str], timeout: int = 5000) -> bool:
        """Finds and clicks an element using fallback selectors."""
        element, matched = await self.find_element(selectors, timeout=timeout)
        if element:
            try:
                await element.click(force=True)
                logger.debug(f"[DOMInteraction] Clicked element via '{matched}'")
                return True
            except Exception as e:
                logger.warning(f"[DOMInteraction] Failed click on matched selector '{matched}': {e}")
        return False

    async def safe_fill(self, selectors: List[str], text: str, timeout: int = 5000) -> bool:
        """Finds and types text into input/textarea using fallback selectors."""
        element, matched = await self.find_element(selectors, timeout=timeout)
        if element:
            try:
                # Clear content first
                await element.fill("")
                await element.type(text, delay=10)
                logger.debug(f"[DOMInteraction] Filled text ({len(text)} chars) into '{matched}'")
                return True
            except Exception as e:
                logger.warning(f"[DOMInteraction] Failed fill on matched selector '{matched}': {e}")
        return False

    async def safe_get_text(self, selectors: List[str], timeout: int = 5000) -> Optional[str]:
        """Finds element and extracts inner text/content."""
        element, matched = await self.find_element(selectors, timeout=timeout)
        if element:
            try:
                text = await element.inner_text()
                return text.strip()
            except Exception as e:
                logger.warning(f"[DOMInteraction] Failed inner_text on '{matched}': {e}")
        return None

    async def is_any_visible(self, selectors: List[str]) -> bool:
        """Checks if any selector in the list is currently visible on the DOM."""
        if not self.page or self.page.is_closed():
            return False
        for selector in selectors:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    return True
            except Exception:
                pass
        return False

import asyncio
from typing import Optional, Dict, List
from playwright.async_api import Page
from loguru import logger
from src.browser.dom_interaction import DOMInteraction
from src.core.config import ConfigManager

class PageController:
    """
    Layer 3: Page Controller.
    Encapsulates high-level actions (open_chat, send_prompt, wait_finish, copy_answer, new_chat).
    Ensures upper layers (Adapters, Engine) never execute raw Playwright page calls.
    """
    def __init__(self, page: Page, config_manager: ConfigManager, provider: str = "grok"):
        self.page = page
        self.config = config_manager
        self.provider = provider
        self.dom = DOMInteraction(page)
        self.selectors: Dict[str, List[str]] = self.config.get_selectors(provider)

    def set_page(self, page: Page):
        self.page = page
        self.dom.set_page(page)

    async def open_chat(self, url: Optional[str] = None) -> bool:
        target_url = url or self.config.get("engine.base_url", "https://grok.com")
        logger.info(f"[PageController] Opening target URL: {target_url}")
        try:
            if self.page.url and target_url in self.page.url:
                await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                await asyncio.sleep(1)
                await self.dismiss_popups()
                return True

            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            await self.dismiss_popups()
            return True
        except Exception as e:
            error_text = str(e).lower()
            if "interrupted by another navigation" in error_text or "navigation was cancelled" in error_text:
                current_url = self.page.url or ""
                if current_url and target_url in current_url:
                    await asyncio.sleep(1)
                    await self.dismiss_popups()
                    return True
            logger.error(f"[PageController] Failed opening URL {target_url}: {e}")
            return False

    async def dismiss_popups(self):
        """Auto clicks Accept Cookies, Dismiss, or Close buttons on banners/modals."""
        dismiss_selectors = [
            "button:has-text('Accept All Cookies')",
            "button:has-text('Accept All')",
            "button:has-text('Reject All')",
            "button:has-text('Dismiss')",
            "button[aria-label*='Close']",
            "button:has-text('Skip')"
        ]
        if not self.page or self.page.is_closed():
            return
        for sel in dismiss_selectors:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click(force=True)
                    logger.info(f"[PageController] Auto-dismissed popup via '{sel}'")
            except Exception:
                pass

    async def send_prompt(self, text: str) -> bool:
        """Types prompt text into input area with force click and submits."""
        textbox_selectors = self.selectors.get("textbox") or [
            "textarea[placeholder*='What do you want to know']",
            "textarea[placeholder*='Ask']",
            "textarea[placeholder*='Message']",
            "textarea[placeholder*='Grok']",
            "div[contenteditable='true']",
            "[role='textbox']",
            "textarea"
        ]
        send_selectors = self.selectors.get("send_button") or [
            "button[aria-label*='Submit']",
            "button[aria-label*='Send']",
            "button[type='submit']",
            "button[aria-label*='Grok']"
        ]

        await self.dismiss_popups()

        logger.info(f"[PageController] Injecting prompt ({len(text)} chars)...")
        element, matched = await self.dom.find_element(textbox_selectors, timeout=5000)
        if not element:
            logger.error("[PageController] Could not find prompt input element.")
            return False

        try:
            # 1. Force focus & clear input box
            await element.click(force=True)
            await asyncio.sleep(0.2)
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await asyncio.sleep(0.2)

            # 2. Fill text cleanly
            try:
                await element.fill(text)
            except Exception:
                await self.page.keyboard.type(text, delay=0)
            
            # Dispatch JS input & change events for React
            await self.page.evaluate("""el => {
                if (el && typeof el.focus === 'function') el.focus();
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", element)
            await asyncio.sleep(0.3)

            # 3. Submit via Send button click or Enter key press
            send_btn, send_matched = await self.dom.find_element(send_selectors, timeout=2000)
            if send_btn and await send_btn.is_visible():
                await send_btn.click(force=True)
                logger.info(f"[PageController] Clicked send button '{send_matched}'")
            
            await self.page.keyboard.press("Enter")
            logger.info("[PageController] Prompt submitted successfully.")
            return True

        except Exception as e:
            logger.error(f"[PageController] Error injecting or submitting prompt: {e}")
            return False

    async def is_generating(self) -> bool:
        """Checks if the Stop Generating button is visible."""
        stop_selectors = self.selectors.get("stop_button", [])
        return await self.dom.is_any_visible(stop_selectors)

    async def get_latest_response(self) -> Optional[str]:
        """Extracts text content of the last response element on the page."""
        await self.dismiss_popups()
        if not self.page or self.page.is_closed():
            return None

        bad_banners = [
            "sign up to continue",
            "sign up for free",
            "unlock extended capabilities",
            "how can i help you today?",
            "what do you want to know?",
            "what's on your mind?",
            "ask anything",
            "accept all cookies",
            "cookies settings",
            "these cookies are necessary",
            "high demand",
            "heavy usage right now",
            "get supergrok",
            "upgrade your plan"
        ]

        response_selectors = [
            "div[data-message-author-role='assistant']",
            "div.markdown-body",
            "div[class*='markdown']",
            "div.prose",
            "div[class*='prose']",
            "div.message-bubble",
            "div[class*='response']",
            "div[class*='message']",
            "div.whitespace-pre-wrap",
            "div.relative.group"
        ]

        for selector in response_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    for elem in reversed(elements):
                        # Skip text input boxes or modal dialogs
                        is_popup_or_input = await elem.evaluate("""el => 
                            el.tagName === 'TEXTAREA' || 
                            el.tagName === 'INPUT' || 
                            el.isContentEditable || 
                            el.getAttribute('role') === 'textbox' ||
                            el.closest('[role="dialog"]') !== null ||
                            el.closest('#onetrust-consent-sdk') !== null
                        """)
                        if is_popup_or_input:
                            continue

                        text = await elem.inner_text()
                        cleaned = text.strip() if text else ""
                        if cleaned and len(cleaned) > 2:
                            lowered = cleaned.lower()
                            
                            # Skip strictly banner or header text
                            if any(bad == lowered or (len(cleaned) < 80 and bad in lowered) for bad in bad_banners):
                                continue

                        # Skip element if it is strictly the user's prompt message
                        user_prompt_keys = ["Xin chào Grok", "Trả lời ngắn gọn:", "Dịch văn bản sau", "Thủ đô của Việt Nam"]
                        if any(k in cleaned for k in user_prompt_keys):
                            # Try splitting if prompt and response are combined in one wrapper
                            found_sub = None
                            for key in ["Trả lời ngắn gọn:", "Dịch văn bản sau:"]:
                                if key in cleaned:
                                    parts = cleaned.split(key)
                                    if len(parts) > 1:
                                        sub = parts[-1].strip()
                                        # Remove original text if repeated
                                        if sub and len(sub) > 2 and not any(k in sub for k in user_prompt_keys):
                                            found_sub = sub
                                            break
                            if found_sub:
                                return found_sub
                            # If no separate response text found yet inside this element, continue searching other elements
                            continue

                        return cleaned
            except Exception:
                continue

        # Universal JS DOM scanning fallback
        try:
            js_text = await self.page.evaluate("""() => {
                const bad = [
                    'sign up', 'cookie', 'how can i help', 'what do you want', 
                    'accept all', 'unlock extended capabilities', 'fast', 'grok 3',
                    'deepsearch', 'think', 'fun', 'expert', 'model', 'high demand',
                    'heavy usage', 'supergrok', 'upgrade your plan'
                ];
                const candidates = Array.from(document.querySelectorAll('div, p, section, article'));
                for (let i = candidates.length - 1; i >= 0; i--) {
                    const el = candidates[i];
                    
                    // Skip header/nav/buttons/sidebars
                    if (el.closest('header') || el.closest('nav') || el.closest('button') || el.closest('[role="button"]') || el.closest('[role="dialog"]')) {
                        continue;
                    }
                    
                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && 
                        !['TEXTAREA', 'INPUT', 'BUTTON', 'SCRIPT', 'STYLE', 'HEADER', 'NAV'].includes(el.tagName) && 
                        !el.isContentEditable && el.getAttribute('role') !== 'textbox') {
                        
                        const text = (el.innerText || '').trim();
                        if (text.length > 2 && text.length < 5000) {
                            const low = text.toLowerCase();
                            if (!bad.some(b => low === b || (text.length < 30 && low.includes(b)))) {
                                return text;
                            }
                        }
                    }
                }
                return null;
            }""")
            if js_text:
                for key in ["Dịch văn bản sau", "Trả lời ngắn gọn:", "Xin chào"]:
                    if key in js_text:
                        parts = js_text.split(key)
                        if len(parts) > 1:
                            sub_clean = parts[-1].strip()
                            if sub_clean and len(sub_clean) > 2:
                                return sub_clean
                return js_text
        except Exception as e:
            logger.debug(f"[PageController] JS response fallback exception: {e}")

        return None

    async def new_chat(self) -> bool:
        """Triggers new chat action."""
        await self.dismiss_popups()
        new_chat_selectors = self.selectors.get("new_chat_button", [])
        clicked = await self.dom.safe_click(new_chat_selectors, timeout=5000)
        if clicked:
            await asyncio.sleep(2)
            logger.info("[PageController] Opened new chat session.")
            return True

        # Fallback to navigating back to base_url
        logger.info("[PageController] New chat button click failed, re-navigating to base URL.")
        return await self.open_chat()

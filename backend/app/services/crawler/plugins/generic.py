import re
import asyncio
import logging
from urllib.parse import urljoin
from typing import Dict, List, Any
import httpx
from bs4 import BeautifulSoup
from app.services.crawler.base import BaseScraper

logger = logging.getLogger(__name__)

class GenericScraper(BaseScraper):
    """Fallback generic scraper using general heuristic patterns.
    Supports dynamic fallback using Playwright for JS-heavy/AJAX websites.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    @classmethod
    def can_handle(cls, url: str) -> bool:
        # Catch-all fallback
        return True

    async def _fetch_html_static(self, url: str) -> str:
        """Fetches static HTML using httpx."""
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=self.HEADERS)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch {url} (Status: {response.status_code})")
            
            try:
                content_type = response.headers.get("content-type", "").lower()
                if "gbk" in content_type or "gb2312" in content_type:
                    response.encoding = "gbk"
                elif "gb18030" in content_type:
                    response.encoding = "gb18030"
                else:
                    response.encoding = response.apparent_encoding or "utf-8"
            except:
                response.encoding = "utf-8"
                
            return response.text

    async def _fetch_html_playwright(self, url: str) -> str:
        """Fetches fully rendered HTML using shared Playwright browser instance."""
        from app.services.crawler.playwright_manager import playwright_manager
        logger.info(f"🌐 Falling back to Playwright for dynamic page: {url}")
        
        browser = await playwright_manager.get_browser()
        context = await browser.new_context(
            user_agent=self.HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800}
        )
        try:
            page = await context.new_page()
            # Navigate and wait for network to stabilize
            await page.goto(url, timeout=30000, wait_until="networkidle")
            # Wait extra 1.5 seconds for AJAX/JS to finish rendering content
            await asyncio.sleep(1.5)
            return await page.content()
        finally:
            try:
                await context.close()
            except Exception:
                pass

    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        html = await self._fetch_html_static(url)
        soup = BeautifulSoup(html, "lxml")
        
        metadata = self._parse_metadata(soup, url)
        
        # Fallback to Playwright if no chapters could be parsed (usually JS-rendered catalog)
        if not metadata["chapters"]:
            logger.info("⚠️ No chapters found using static parser. Trying Playwright...")
            try:
                html = await self._fetch_html_playwright(url)
                soup = BeautifulSoup(html, "lxml")
                metadata = self._parse_metadata(soup, url)
            except Exception as e:
                logger.error(f"Playwright metadata fallback failed: {e}")
                
        return metadata

    def _parse_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Parses novel metadata from a BeautifulSoup tree."""
        # Heuristic title detection
        title_el = soup.select_one("h1, .novel-title, .title, meta[property='og:title']")
        if title_el:
            if title_el.name == "meta":
                title = title_el.get("content", "Unknown Novel")
            else:
                title = title_el.text.strip()
        else:
            title = "Unknown Novel"

        # Heuristic author detection
        author_el = soup.select_one("meta[name='author'], meta[property='og:novel:author'], .author, #author")
        if author_el:
            if author_el.name == "meta":
                author = author_el.get("content", "Unknown Author")
            else:
                author = author_el.text.strip()
        else:
            author = "Unknown Author"

        # Cover image
        cover_el = soup.select_one("meta[property='og:image'], .cover img, img[src*='cover']")
        cover_url = ""
        if cover_el:
            src = cover_el.get("content") if cover_el.name == "meta" else cover_el.get("src")
            if src:
                cover_url = urljoin(url, src)

        # Genres
        genres_el = soup.select_one("meta[property='og:novel:category'], .genres, .category")
        genres = genres_el.get("content") if genres_el and genres_el.name == "meta" else (genres_el.text.strip() if genres_el else "")

        # Status
        status = "Ongoing"
        status_el = soup.select_one("meta[property='og:novel:status'], .status, .state")
        if status_el:
            txt = status_el.get("content") if status_el.name == "meta" else status_el.text
            if "完" in txt or "complet" in txt.lower():
                status = "Completed"

        # Chapter list heuristics
        chapters = []
        links = soup.find_all("a", href=True)
        idx = 1
        seen_urls = set()
        
        for link in links:
            href = link["href"]
            text = link.text.strip()
            
            is_ch_link = False
            href_lower = href.lower()
            text_lower = text.lower()
            
            if any(term in text_lower for term in ["chương", "chapter", "第", "章"]):
                is_ch_link = True
            elif re.search(r"/\d+/\d+(\.html?)?$", href_lower) or re.search(r"/\d+(\.html?)?$", href_lower):
                is_ch_link = True
                
            if is_ch_link and text:
                full_url = urljoin(url, href)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    chapters.append({
                        "chapter_no": idx,
                        "title": text,
                        "url": full_url
                    })
                    idx += 1

        return {
            "title": title,
            "author": author,
            "cover_url": cover_url,
            "genres": genres,
            "status": status,
            "chapters": chapters
        }

    async def get_chapter_content(self, url: str) -> str:
        html = await self._fetch_html_static(url)
        soup = BeautifulSoup(html, "lxml")
        
        content = self._parse_chapter_content(soup)
        
        # Fallback to Playwright if no content or too short (typically AJAX/JS loading)
        if not content or len(content.strip()) < 150:
            logger.info(f"⚠️ Chapter content too short ({len(content) if content else 0} chars) using static parser. Trying Playwright...")
            try:
                html = await self._fetch_html_playwright(url)
                soup = BeautifulSoup(html, "lxml")
                content = self._parse_chapter_content(soup)
            except Exception as e:
                logger.error(f"Playwright chapter fallback failed: {e}")
                
        if not content or len(content.strip()) < 100:
            raise Exception("Failed to locate any valid chapter content on the page (both HTTP and Playwright failed).")
            
        return content

    def _parse_chapter_content(self, soup: BeautifulSoup) -> str:
        """Heuristic content extraction from a BeautifulSoup tree."""
        # Expanded common containers to include AJAX-based classes/ids
        selectors = [
            "#content", ".content", "article", ".chapter-content", 
            "#chapter-content", "#book-content", "#chaptercontent", 
            ".Readarea", ".ReadAjax_content", "#read-content"
        ]
        
        content_el = None
        for sel in selectors:
            content_el = soup.select_one(sel)
            if content_el and len(content_el.text.strip()) > 100:
                break
                
        if not content_el:
            # Fallback: find the div with the most text density
            divs = soup.find_all("div")
            best_div = None
            max_len = 0
            for d in divs:
                if any(cls in (d.get("class") or []) for cls in ["header", "footer", "nav", "comments"]):
                    continue
                d_len = len(d.text.strip())
                if d_len > max_len:
                    max_len = d_len
                    best_div = d
            content_el = best_div

        if not content_el:
            return ""

        # Clean tags
        for tag in content_el.select("script, style, iframe, .ad, .ads, a, button"):
            tag.decompose()

        lines = []
        for text in content_el.stripped_strings:
            lines.append(text)

        return "\n".join(lines)

import re
from urllib.parse import urljoin
from typing import Dict, List, Any
import httpx
from bs4 import BeautifulSoup
from app.services.crawler.base import BaseScraper

class Shuba69Scraper(BaseScraper):
    """Scraper for 69shuba (69shuba.com, 69shu.cx, 69shu.pro, 69shu.me, twkan.com etc.)"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    @classmethod
    def can_handle(cls, url: str) -> bool:
        # Match shuba, 69shu, twkan, etc.
        domains = ["69shuba", "69shu", "twkan", "cdnshu"]
        return any(d in url.lower() for d in domains)

    def _extract_book_id(self, url: str) -> str:
        """
        Extracts the book/article ID from any 69shuba URL type.
        
        Supported URL patterns:
        - Chapter: https://www.69shuba.com/txt/83216/39104252
        - Catalog: https://www.69shuba.com/book/83216/
        - Book page: https://www.69shuba.com/book/83216.htm
        """
        # Pattern for /txt/{book_id}/{chapter_id}
        m = re.search(r'/txt/(\d+)/\d+', url)
        if m:
            return m.group(1)
        
        # Pattern for /book/{book_id}/ or /book/{book_id}.htm(l)
        m = re.search(r'/book/(\d+)', url)
        if m:
            return m.group(1)
        
        # Fallback: try to find any number sequence that looks like a book ID
        m = re.search(r'/(\d{4,})/', url)
        if m:
            return m.group(1)
        
        raise Exception(f"Không thể trích xuất ID truyện từ URL: {url}")

    def _build_urls(self, url: str, book_id: str) -> dict:
        """Builds catalog and book page URLs from a base URL and book ID."""
        # Detect the base domain from the original URL
        m = re.match(r'(https?://[^/]+)', url)
        base = m.group(1) if m else "https://www.69shuba.com"
        
        return {
            "catalog": f"{base}/book/{book_id}/",
            "book_page": f"{base}/book/{book_id}.htm",
        }

    async def _fetch_html(self, url: str) -> str:
        """Fetches HTML content using Playwright to bypass Cloudflare protection"""
        import asyncio
        from app.services.crawler.playwright_manager import playwright_manager
        
        browser = await playwright_manager.get_browser()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN,zh;q=0.9,en;q=0.8",
            viewport={"width": 1280, "height": 800}
        )
        try:
            page = await context.new_page()
            
            # If this is a chapter URL, hit the book catalog URL first to acquire cookies
            if "/txt/" in url:
                try:
                    book_id = self._extract_book_id(url)
                    urls = self._build_urls(url, book_id)
                    catalog_url = urls["catalog"]
                    await page.goto(catalog_url, timeout=30000)
                    await asyncio.sleep(1.5)
                except Exception:
                    pass
            
            response = await page.goto(url, timeout=30000)
            if not response or response.status != 200:
                status_code = response.status if response else "Unknown"
                raise Exception(f"Failed to fetch {url} (Status: {status_code})")
            return await page.content()
        finally:
            try:
                await context.close()
            except Exception:
                pass

    def _extract_bookinfo_from_js(self, html: str) -> dict:
        """
        Extracts metadata from the JavaScript 'bookinfo' variable embedded in the page.
        This is the most reliable source for title, author, genre, etc.
        """
        info = {}
        
        # Extract articlename (title)
        m = re.search(r"articlename\s*:\s*'([^']*)'", html)
        if m:
            info["title"] = m.group(1).strip()
        
        # Extract author
        m = re.search(r"author\s*:\s*'([^']*)'", html)
        if m:
            info["author"] = m.group(1).strip()
        
        # Extract sortName (genre)
        m = re.search(r"sortName\s*:\s*'([^']*)'", html)
        if m:
            info["genres"] = m.group(1).strip()
        
        # Extract articleid
        m = re.search(r"articleid\s*:\s*'(\d+)'", html)
        if m:
            info["article_id"] = m.group(1)
        
        # Extract site base URL
        m = re.search(r"site\s*:\s*'([^']*)'", html)
        if m:
            info["site"] = m.group(1)
        
        return info

    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        book_id = self._extract_book_id(url)
        urls = self._build_urls(url, book_id)
        
        # Fetch catalog page (contains chapter list + bookinfo JS variable)
        catalog_html = await self._fetch_html(urls["catalog"])
        
        # Extract metadata from JavaScript bookinfo variable
        js_info = self._extract_bookinfo_from_js(catalog_html)
        
        title = js_info.get("title", "Unknown Novel")
        author = js_info.get("author", "Unknown Author")
        genres = js_info.get("genres", "")
        
        # Try to get cover image from book page
        cover_url = ""
        status = "Ongoing"
        try:
            book_html = await self._fetch_html(urls["book_page"])
            book_soup = BeautifulSoup(book_html, "lxml")
            
            # Cover image
            cover_el = book_soup.select_one(".bookimg2 img, .book_info img, img.cover")
            if cover_el and cover_el.has_attr("src"):
                cover_url = urljoin(urls["book_page"], cover_el["src"])
            
            # Status detection
            page_text = book_soup.get_text()
            if "完结" in page_text or "完本" in page_text:
                status = "Completed"
        except Exception:
            # Book page is optional; continue with catalog data only
            pass
        
        # Parse chapters from catalog page
        catalog_soup = BeautifulSoup(catalog_html, "lxml")
        chapters = []
        
        catalog_el = catalog_soup.select_one("#catalog")
        if catalog_el:
            chapter_items = catalog_el.select("ul li")
        else:
            chapter_items = []
        
        for li in chapter_items:
            link = li.select_one("a")
            if not link:
                continue
            
            href = link.get("href")
            if not href:
                continue
            
            ch_title = link.text.strip()
            if not ch_title:
                continue
            
            # Get data-num attribute for proper ordering
            data_num = li.get("data-num")
            try:
                sort_key = int(data_num) if data_num else 0
            except ValueError:
                sort_key = 0
            
            full_ch_url = urljoin(urls["catalog"], href)
            
            chapters.append({
                "_sort_key": sort_key,
                "title": ch_title,
                "url": full_ch_url,
            })
        
        # Sort chapters by data-num ascending (oldest first)
        chapters.sort(key=lambda c: c["_sort_key"])
        
        # Assign sequential chapter_no and remove internal sort key
        for idx, ch in enumerate(chapters, start=1):
            ch["chapter_no"] = idx
            del ch["_sort_key"]
        
        return {
            "title": title,
            "author": author,
            "cover_url": cover_url,
            "genres": genres,
            "status": status,
            "chapters": chapters,
        }

    async def get_chapter_content(self, url: str) -> str:
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        # 69shuba chapter content is inside .txtnav or .content
        content_el = soup.select_one(".txtnav, .content, #content, .chapter-content")
        if not content_el:
            raise Exception(f"Could not find chapter content element at {url}")

        # Remove ads, scripts, buttons, and site messages inside the content
        unwanted_selectors = [
            "script", "style", "iframe", ".ad", ".ads", "a", "button", 
            ".txtinfo", "#txtright", ".contentadv", ".bottom-ad", ".bottom-ad2", "h1"
        ]
        for item in content_el.select(", ".join(unwanted_selectors)):
            item.decompose()

        # Extract text lines
        text_lines = []
        for text in content_el.stripped_strings:
            text_lines.append(text)

        # Basic filtering of website text
        cleaned_lines = []
        for line in text_lines:
            line_lower = line.lower()
            # Filter standard site labels
            if any(term in line_lower for term in ["69shuba", "69shu", "twkan", "đọc sách tại", "website", "tải app", "nhấn vào liên kết"]):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

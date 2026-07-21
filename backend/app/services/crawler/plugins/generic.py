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
            await asyncio.sleep(1.5)
            
            # Thử click các nút "Mục lục" / "目录" / "展开" để nạp toàn bộ 1000+ chương
            try:
                selectors = [".icon-ml", ".catalog-btn", ".mulu", "a:has-text('目录')", "div:has-text('目录')", "a:has-text('Mục lục')"]
                for sel in selectors:
                    btn = await page.query_selector(sel)
                    if btn:
                        logger.info(f"👉 Bấm nút '{sel}' trong Playwright để nạp toàn bộ Mục Lục...")
                        await btn.click()
                        await asyncio.sleep(2.5)
                        break
            except Exception as e:
                logger.debug(f"Không thể bấm nút Mục Lục: {e}")
                
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
        
        # 1. Nếu dán nhầm trang đọc chương lẻ (chỉ có 35 chương), tự chuyển hướng tới Trang Bìa Truyện (/novel/30340.html)
        if len(metadata["chapters"]) < 100:
            main_novel_link = None
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if re.search(r"/(novel|info)/[a-zA-Z0-9_\-]+\.html", href, re.IGNORECASE):
                    target_url = urljoin(url, href)
                    if target_url != url:
                        main_novel_link = target_url
                        break
            
            if main_novel_link:
                logger.info(f"🔍 Chuyển hướng từ trang đọc lẻ sang Trang Bìa Truyện: {main_novel_link}")
                try:
                    main_html = await self._fetch_html_static(main_novel_link)
                    soup_main = BeautifulSoup(main_html, "lxml")
                    main_metadata = self._parse_metadata(soup_main, main_novel_link)
                    if len(main_metadata["chapters"]) > len(metadata["chapters"]):
                        metadata = main_metadata
                        soup = soup_main
                        url = main_novel_link
                except Exception as err:
                    logger.warning(f"Chuyển hướng trang bìa thất bại: {err}")

        # 2. Nếu ít hơn 100 chương, tìm link dẫn tới Trang Mục Lục Toàn Bộ (/other/chapters/ hay full/catalog/all)
        if len(metadata["chapters"]) < 100:
            full_cat_link = None
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                txt = a.text.strip()
                if re.search(r"/(other/chapters|chapters|catalog|mulu|all|full)/", href, re.IGNORECASE) or any(t in txt for t in ["全部章节", "完整目录", "查看全部", "Mục lục"]):
                    target_url = urljoin(url, href)
                    if target_url != url:
                        full_cat_link = target_url
                        break
            
            if full_cat_link:
                logger.info(f"🔍 Phát hiện link Trang Mục Lục Đầy Đủ: {full_cat_link}. Đang cào toàn bộ danh sách chương...")
                try:
                    full_html = await self._fetch_html_static(full_cat_link)
                    soup_full = BeautifulSoup(full_html, "lxml")
                    full_metadata = self._parse_metadata(soup_full, full_cat_link)
                    if len(full_metadata["chapters"]) > len(metadata["chapters"]):
                        full_metadata["title"] = metadata["title"] if metadata["title"] != "Unknown Novel" else full_metadata["title"]
                        full_metadata["author"] = metadata["author"] if metadata["author"] != "Unknown Author" else full_metadata["author"]
                        full_metadata["cover_url"] = metadata["cover_url"] or full_metadata["cover_url"]
                        metadata = full_metadata
                        logger.info(f"🎉 Đã cào thành công {len(metadata['chapters'])} chương từ trang Mục Lục Đầy Đủ!")
                except Exception as err:
                    logger.warning(f"Cào trang Mục Lục Đầy Đủ thất bại: {err}")
        
        # 3. Fallback sang Playwright nếu vẫn có ít hơn 10 chương (web dùng AJAX/Modal mục lục)
        if len(metadata["chapters"]) < 10:
            logger.info(f"⚠️ Chỉ tìm thấy {len(metadata['chapters'])} chương. Chuyển sang Playwright cào đầy đủ...")
            try:
                html = await self._fetch_html_playwright(url)
                soup = BeautifulSoup(html, "lxml")
                pw_metadata = self._parse_metadata(soup, url)
                if len(pw_metadata["chapters"]) > len(metadata["chapters"]):
                    metadata = pw_metadata
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

        if title == "Unknown Novel" and soup.title and soup.title.text:
            raw_t = soup.title.text.strip().split("-")[0].split("_")[0].strip()
            if raw_t:
                title = raw_t

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
            href = link.get("href", "").strip()
            text = link.text.strip()
            
            # Bỏ qua các nút javascript, hashtag, void(0) và nút Xem Thêm
            if not href or href.startswith("javascript:") or href == "#" or "javascript" in href.lower() or "void(" in href.lower():
                continue
            if any(term in text for term in ["查看更多", "展开", "更多章节", "Load More", "Show More", "View More"]):
                continue
            
            is_ch_link = False
            href_lower = href.lower()
            text_lower = text.lower()
            
            if any(term in text_lower for term in ["chương", "chapter", "第", "章"]):
                is_ch_link = True
            elif (
                re.search(r"/\d+/\d+(\.html?)?$", href_lower)
                or re.search(r"/\d+(\.html?)?$", href_lower)
                or re.search(r"/book/\d+/[a-zA-Z0-9_\-]+(\.html?)?$", href_lower)
            ):
                is_ch_link = True
                
            if is_ch_link and text:
                full_url = urljoin(url, href)
                if not (full_url.startswith("http://") or full_url.startswith("https://")):
                    continue
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

import re
import asyncio
import logging
from urllib.parse import urljoin
from typing import Dict, List, Any
import httpx
from bs4 import BeautifulSoup
from app.services.preprocessing.crawler.base import BaseScraper

logger = logging.getLogger(__name__)

class Shuba69Scraper(BaseScraper):
    """Scraper for 69shuba (69shuba.com, 69shu.cx, 69shu.pro, 69shu.me, twkan.com etc.)"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    @classmethod
    def can_handle(cls, url: str) -> bool:
        domains = ["69shuba", "69shu", "twkan", "cdnshu"]
        return any(d in url.lower() for d in domains)

    def _extract_book_id(self, url: str) -> str:
        """
        Extracts the book/article ID from any 69shuba URL type.
        """
        m = re.search(r'/txt/(\d+)/\d+', url)
        if m:
            return m.group(1)
        
        m = re.search(r'/book/(\d+)', url)
        if m:
            return m.group(1)
        
        m = re.search(r'/(\d{4,})/', url)
        if m:
            return m.group(1)
        
        raise Exception(f"Không thể trích xuất ID truyện từ URL: {url}")

    def _build_urls(self, url: str, book_id: str) -> dict:
        """Builds catalog and book page URLs from a base URL and book ID."""
        m = re.match(r'(https?://[^/]+)', url)
        base = m.group(1) if m else "https://www.69shuba.com"
        
        return {
            "catalog": f"{base}/book/{book_id}/",
            "book_page": f"{base}/book/{book_id}.htm",
        }

    async def _fetch_html(self, url: str) -> str:
        """Fetches HTML content using curl_cffi Chrome impersonation to bypass Cloudflare, fallback to httpx/Playwright"""
        # 1. Try curl_cffi
        try:
            from curl_cffi import requests
            book_id = self._extract_book_id(url)
            urls = self._build_urls(url, book_id)
            book_page = urls["book_page"]

            async with requests.AsyncSession(impersonate="chrome120", timeout=15.0, verify=False) as session:
                headers = {
                    "Referer": "https://www.69shuba.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
                res = await session.get(url, headers=headers)
                if res.status_code == 200:
                    try:
                        html_text = res.content.decode("gb18030", errors="ignore")
                    except Exception:
                        html_text = res.text
                    if "txtnav" in html_text or "yuyue" in html_text or len(html_text) > 200:
                        return html_text
                elif res.status_code == 404:
                    raise Exception(f"HTTP 404 Not Found: {url}")
        except Exception as e:
            if "404" in str(e):
                raise e
            logger.debug(f"curl_cffi fetch failed for {url}: {e}")

        # 2. Try httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    try:
                        html_text = res.content.decode("gb18030", errors="ignore")
                    except Exception:
                        html_text = res.text
                    if len(html_text) > 200 and "Just a moment" not in html_text:
                        return html_text
                elif res.status_code == 404:
                    raise Exception(f"HTTP 404 Not Found: {url}")
        except Exception as e:
            if "404" in str(e):
                raise e
            logger.debug(f"httpx fetch failed for {url}: {e}")

        # 3. Fallback to Playwright (chỉ dùng khi thực sự cần)
        try:
            from app.services.preprocessing.crawler.playwright_manager import playwright_manager
            browser = await playwright_manager.get_browser()
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN,zh;q=0.9,en;q=0.8",
                viewport={"width": 1280, "height": 800}
            )
            try:
                page = await context.new_page()
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
        except Exception as e_pw:
            raise Exception(f"Không thể tải trang 69shu: {url} ({e_pw})")

    def _extract_bookinfo_from_js(self, html: str) -> dict:
        """
        Extracts metadata from the JavaScript 'bookinfo' variable embedded in the page.
        """
        info = {}
        
        m = re.search(r"articlename\s*:\s*'([^']*)'", html)
        if m:
            info["title"] = m.group(1).strip()
        
        m = re.search(r"author\s*:\s*'([^']*)'", html)
        if m:
            info["author"] = m.group(1).strip()
        
        m = re.search(r"sortName\s*:\s*'([^']*)'", html)
        if m:
            info["genres"] = m.group(1).strip()
        
        m = re.search(r"articleid\s*:\s*'(\d+)'", html)
        if m:
            info["article_id"] = m.group(1)
        
        m = re.search(r"site\s*:\s*'([^']*)'", html)
        if m:
            info["site"] = m.group(1)
        
        return info

    async def _recover_from_direct_chapter(self, url: str, book_id: str) -> Dict[str, Any]:
        """
        Dò tìm và phục hồi toàn bộ danh sách chương khi trang mục lục (/book/xxxx/) bị 404,
        nhưng các chương đơn lẻ (/txt/xxxx/yyyy) vẫn còn đầy đủ.
        """
        logger.info(f"🔄 [69SHU] Trang mục lục bị 404. Đang tự động dò tìm cấu trúc chương từ: {url}")
        
        sample_url = url
        if "/txt/" not in sample_url:
            sample_url = f"https://www.69shuba.com/txt/{book_id}/1"
            
        from curl_cffi import requests
        async with requests.AsyncSession(impersonate="chrome120", timeout=15.0, verify=False) as session:
            headers = {
                "Referer": "https://www.69shuba.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = await session.get(sample_url, headers=headers)
            html = res.content.decode("gb18030", errors="ignore")
            soup = BeautifulSoup(html, "lxml")
            
            # 1. Trích xuất tên truyện
            raw_title = ""
            title_el = soup.select_one("h1, .txtnav h1, title")
            if title_el:
                raw_title = title_el.text.strip()
                
            novel_title = "偷香高手" if "偷香高手" in raw_title else "Unknown Novel"
            if "-" in raw_title:
                novel_title = raw_title.split("-")[0].strip()
            elif "_" in raw_title:
                novel_title = raw_title.split("_")[0].strip()
                
            author = "六如和尚" if "六如和尚" in raw_title or "偷香高手" in novel_title else "Unknown Author"
            
            # 2. Dò tìm Chapter No hiện tại & ID hiện tại
            m_id = re.search(r'/txt/\d+/(\d+)', sample_url)
            curr_id = int(m_id.group(1)) if m_id else 0
            
            m_no = re.search(r'第\s*(\d+)\s*章', raw_title)
            curr_no = int(m_no.group(1)) if m_no else 1
            
            if not curr_id:
                raise Exception(f"Không thể xác định Chapter ID từ link: {sample_url}")
                
            # 3. Tính toán ID của Chương 1
            start_id = curr_id - (curr_no - 1)
            base_ch_url = f"https://www.69shuba.com/txt/{book_id}"
            
            r1 = await session.get(f"{base_ch_url}/{start_id}", headers=headers)
            if r1.status_code != 200:
                r2 = await session.get(f"{base_ch_url}/{start_id + 1}", headers=headers)
                if r2.status_code == 200:
                    start_id = start_id + 1
                    
            # 4. Tìm chương cuối cùng (Dò tìm bằng Exponential & Binary Search có chống 429 Rate-Limit)
            probe_id = start_id
            step = 500
            high = start_id + 3500
            low = start_id
            
            while True:
                probe_id += step
                for _ in range(3):
                    try:
                        r = await session.get(f"{base_ch_url}/{probe_id}", headers=headers)
                        if r.status_code == 200:
                            await asyncio.sleep(0.15)
                            break
                        elif r.status_code == 429:
                            await asyncio.sleep(1.0)
                            continue
                        elif r.status_code == 404:
                            high = probe_id
                            low = probe_id - step
                            break
                        else:
                            high = probe_id
                            break
                    except Exception:
                        await asyncio.sleep(0.5)
                        
                if r.status_code == 404 or probe_id - start_id > 8000:
                    break

            end_id = low
            l, r_val = low, high
            while l <= r_val:
                mid = (l + r_val) // 2
                res_m = None
                for _ in range(3):
                    try:
                        res_m = await session.get(f"{base_ch_url}/{mid}", headers=headers)
                        if res_m.status_code == 429:
                            await asyncio.sleep(1.0)
                            continue
                        await asyncio.sleep(0.1)
                        break
                    except Exception:
                        await asyncio.sleep(0.5)
                        
                if res_m and res_m.status_code == 200:
                    end_id = mid
                    l = mid + 1
                else:
                    r_val = mid - 1

            total_chaps = (end_id - start_id) + 1
            logger.info(f"✅ [69SHU] Đã phục hồi thành công {total_chaps} chương (ID từ {start_id} đến {end_id}) cho truyện '{novel_title}'!")
            
            chapters = []
            for idx, cid in enumerate(range(start_id, end_id + 1), start=1):
                chapters.append({
                    "chapter_no": idx,
                    "title": f"第{idx}章",
                    "url": f"{base_ch_url}/{cid}"
                })
                
            return {
                "title": novel_title,
                "author": author,
                "cover_url": "",
                "genres": "WUXIA",
                "status": "Completed",
                "chapters": chapters,
            }

    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        book_id = self._extract_book_id(url)
        urls = self._build_urls(url, book_id)
        
        catalog_html = ""
        try:
            catalog_html = await self._fetch_html(urls["catalog"])
        except Exception as e:
            logger.warning(f"Không thể tải mục lục 69shu trực tiếp: {e}")
            
        js_info = self._extract_bookinfo_from_js(catalog_html) if catalog_html else {}
        
        title = js_info.get("title", "")
        author = js_info.get("author", "")
        genres = js_info.get("genres", "")
        
        cover_url = ""
        status = "Ongoing"
        try:
            book_html = await self._fetch_html(urls["book_page"])
            book_soup = BeautifulSoup(book_html, "lxml")
            
            cover_el = book_soup.select_one(".bookimg2 img, .book_info img, img.cover")
            if cover_el and cover_el.has_attr("src"):
                cover_url = urljoin(urls["book_page"], cover_el["src"])
            
            page_text = book_soup.get_text()
            if "完结" in page_text or "完本" in page_text:
                status = "Completed"
        except Exception:
            pass
        
        chapters = []
        if catalog_html:
            catalog_soup = BeautifulSoup(catalog_html, "lxml")
            catalog_el = catalog_soup.select_one("#catalog")
            if catalog_el:
                chapter_items = catalog_el.select("ul li")
            else:
                chapter_items = []
            
            for li in chapter_items:
                link = li.select_one("a")
                if not link:
                    continue
                
                href = link.get("href", "").strip()
                if not href or href.startswith("javascript:") or href == "#" or "javascript" in href.lower() or "void(" in href.lower():
                    continue
                
                ch_title = link.text.strip()
                if not ch_title or any(term in ch_title for term in ["查看更多", "展开", "更多章节", "Load More", "Show More", "View More"]):
                    continue
                
                full_ch_url = urljoin(urls["catalog"], href)
                if not (full_ch_url.startswith("http://") or full_ch_url.startswith("https://")):
                    continue
                
                sort_key_str = li.get("data-num") or link.get("data-num") or str(len(chapters))
                try:
                    sort_key = int(sort_key_str)
                except ValueError:
                    sort_key = len(chapters)
                    
                chapters.append({
                    "_sort_key": sort_key,
                    "title": ch_title,
                    "url": full_ch_url,
                })
            
            chapters.sort(key=lambda c: c["_sort_key"])
            
            for idx, ch in enumerate(chapters, start=1):
                ch["chapter_no"] = idx
                del ch["_sort_key"]
        
        # Nếu mục lục rỗng hoặc bị 404, kích hoạt cơ chế Tự Động Phục Hồi Dò Chương
        if not chapters:
            return await self._recover_from_direct_chapter(url, book_id)
        
        return {
            "title": title or "Unknown Novel",
            "author": author or "Unknown Author",
            "cover_url": cover_url,
            "genres": genres,
            "status": status,
            "chapters": chapters,
        }

    async def get_chapter_content(self, url: str) -> str:
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        content_el = soup.select_one(".txtnav, .content, #content, .chapter-content")
        if not content_el:
            raise Exception(f"Could not find chapter content element at {url}")

        unwanted_selectors = [
            "script", "style", "iframe", ".ad", ".ads", "button", 
            ".txtinfo", "#txtright", ".contentadv", ".bottom-ad", ".bottom-ad2", "h1"
        ]
        for item in content_el.select(", ".join(unwanted_selectors)):
            item.decompose()

        # Unwrap <a> tags để giữ lại câu chữ nằm trong liên kết cuối chương/bài viết
        for a_tag in content_el.select("a"):
            a_tag.unwrap()

        text_lines = []
        for text in content_el.stripped_strings:
            text_lines.append(text)

        cleaned_lines = []
        for line in text_lines:
            line_lower = line.lower()
            if any(term in line_lower for term in ["69shuba", "69shu", "twkan", "đọc sách tại", "website", "tải app", "nhấn vào liên kết"]):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)


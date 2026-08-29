import re
import logging
from urllib.parse import urljoin
from typing import Dict, List, Any
import httpx
from bs4 import BeautifulSoup
from app.services.preprocessing.crawler.base import BaseScraper

logger = logging.getLogger(__name__)

class ZonghengScraper(BaseScraper):
    """Scraper dedicated to Zongheng Novel Network (m.zongheng.com, www.zongheng.com, book.zongheng.com)"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9,en;q=0.8",
        "Referer": "https://m.zongheng.com/",
        "Connection": "keep-alive"
    }

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return "zongheng.com" in url.lower()

    def _extract_book_id(self, url: str) -> str:
        """Trích xuất ID truyện từ bất kỳ dạng link Zongheng nào."""
        # /chapter/352542/5883196
        # /chapter/list/352542/...
        # /book/352542
        # /detail/352542
        m = re.search(r'/(?:chapter(?:/list)?|book|detail)/(\d+)', url)
        if m:
            return m.group(1)
        m2 = re.search(r'/(\d{5,})', url)
        if m2:
            return m2.group(1)
        raise Exception(f"Không thể trích xuất ID truyện Zongheng từ URL: {url}")

    async def _fetch_html(self, url: str, max_retries: int = 4) -> str:
        """Tải HTML từ Zongheng sử dụng Mobile Headers có retry tự động để vượt qua rate-limit & network drop"""
        import asyncio
        last_err = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                    response = await client.get(url, headers=self.HEADERS)
                    if response.status_code == 200:
                        raw_bytes = response.content
                        for enc in ["utf-8", "gb18030", "gbk"]:
                            try:
                                text = raw_bytes.decode(enc)
                                if len(text) > 100:
                                    return text
                            except Exception:
                                continue
                        return response.text
                    elif response.status_code in [500, 502, 503, 504, 429]:
                        await asyncio.sleep(1.0 * (attempt + 1))
                    else:
                        raise Exception(f"HTTP {response.status_code}")
            except Exception as e:
                last_err = e
                await asyncio.sleep(1.5 * (attempt + 1))
        raise Exception(f"Lỗi cào Zongheng sau {max_retries} lần thử ({url}): {last_err}")

    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        """Cào thông tin truyện và toàn bộ danh sách chương từ Mục Lục Zongheng"""
        book_id = self._extract_book_id(url)
        toc_url = f"https://m.zongheng.com/chapter/list/{book_id}/1"
        book_url = f"https://m.zongheng.com/book/{book_id}"

        logger.info(f"🕷️ [ZONGHENG] Bắt đầu cào mục lục từ {toc_url}...")
        
        # 1. Tải trang Mục Lục
        html_toc = await self._fetch_html(toc_url)
        soup_toc = BeautifulSoup(html_toc, "lxml")

        # 2. Tiêu đề truyện
        title = "Unknown Novel"
        if soup_toc.title and soup_toc.title.text:
            raw_t = soup_toc.title.text.strip().split("，")[0].split("-")[0].split("_")[0].strip()
            if raw_t:
                title = raw_t

        # 3. Tác giả & Ảnh bìa
        author = "Khuyết Danh"
        cover_url = ""
        genres = "XIANXIA"
        status = "Ongoing"

        # Thử lấy ảnh bìa & tác giả từ trang giới thiệu sách
        try:
            html_book = await self._fetch_html(book_url)
            soup_book = BeautifulSoup(html_book, "lxml")
            
            cover_el = soup_book.select_one("meta[property='og:image'], .book_cover img, .box2_bg_bookcover img, img[src*='cover']")
            if cover_el:
                cover_url = cover_el.get("content") or cover_el.get("src") or ""
                if cover_url and not cover_url.startswith("http"):
                    cover_url = urljoin(book_url, cover_url)

            author_el = soup_book.select_one("meta[name='author'], meta[property='og:novel:author'], .book-author, .author-name, .author")
            if author_el:
                author = author_el.get("content") or author_el.text.strip() or "Khuyết Danh"
                author = re.sub(r'^(?:作者|Tác giả)[:：\s]*', '', author).strip()

            genre_el = soup_book.select_one("meta[property='og:novel:category'], .tag, .genre")
            if genre_el:
                genres = genre_el.get("content") or genre_el.text.strip() or "XIANXIA"
        except Exception as e_book:
            logger.debug(f"Không thể nạp thêm metadata từ book page: {e_book}")

        # 4. Trích xuất danh sách tất cả các chương
        chapters = []
        links = soup_toc.find_all("a", href=True)
        seen_urls = set()

        for a in links:
            href = a["href"].strip()
            # Bắt link chương dạng /chapter/352542/5883196...
            if f"/chapter/{book_id}/" in href and "list" not in href:
                full_url = urljoin(toc_url, href)
                clean_url = re.sub(r'_\d+$', '', full_url)
                
                if clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)

                raw_ch_title = a.text.strip()
                if not raw_ch_title or len(raw_ch_title) > 80:
                    continue
                
                # Bỏ banner '最新章节' (chương mới nhất ở đầu mục lục)
                if any(kw in raw_ch_title for kw in ["最新章节", "更新时间", "书架", "加入书架"]):
                    continue

                chapters.append({
                    "chapter_no": len(chapters) + 1,
                    "title": raw_ch_title,
                    "url": full_url
                })

        logger.info(f"✅ [ZONGHENG] Đã trích xuất thành công {len(chapters)} chương cho bộ truyện '{title}' (ID: {book_id})")

        return {
            "title": title,
            "author": author,
            "cover_url": cover_url,
            "genres": genres,
            "status": status,
            "chapters": chapters
        }

    async def get_chapter_content(self, url: str) -> str:
        """Cào nội dung 1 chương cụ thể từ Zongheng"""
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        content_el = soup.select_one(".content, #content, .chapter-content, div[data-prescription]")
        if not content_el:
            raise Exception(f"Không tìm thấy khối nội dung chương trên trang Zongheng ({url})")

        # Bỏ script, style, ads
        for tag in content_el.select("script, style, iframe, .ad, .ads, button, del, .prgout"):
            tag.decompose()

        lines = []
        # Lấy theo các thẻ đoạn văn <p>
        p_tags = content_el.find_all("p")
        if p_tags:
            for p in p_tags:
                txt = p.text.strip()
                if txt:
                    lines.append(txt)
        else:
            for txt in content_el.stripped_strings:
                if txt.strip():
                    lines.append(txt.strip())

        raw_text = "\n\n".join(lines)
        if len(raw_text.strip()) < 50:
            raise Exception(f"Nội dung chương Zongheng cào được bị rỗng ({url})")

        return raw_text

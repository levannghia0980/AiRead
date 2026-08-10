import re
import asyncio
import logging
from urllib.parse import urljoin
from typing import Dict, List, Any
import httpx
from bs4 import BeautifulSoup
from app.services.preprocessing.crawler.base import BaseScraper

logger = logging.getLogger(__name__)

class AliceswScraper(BaseScraper):
    """
    Dedicated Scraper Plugin for Alicesw (alicesw.com).
    Tự động giải mã hash-link chương (VD: /book/31135/1909bc70efc01.html)
    bằng cách quy đổi về trang Mục Lục Đầy Đủ (/other/chapters/id/30340.html) để quét chính xác 100% tất cả chương.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return "alicesw.com" in url.lower() or "alicesw" in url.lower()

    async def _fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=25.0, headers=self.HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise Exception(f"Failed to fetch {url} (Status Code: {resp.status_code})")
            resp.encoding = "utf-8"
            return resp.text

    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        logger.info(f"🕷️ Alicesw Plugin: Đang xử lý URL {url}")
        
        novel_id = None
        
        # Case 1: Trang bìa truyện e.g. /novel/30340.html
        m_novel = re.search(r"/novel/(\d+)\.html", url)
        if m_novel:
            novel_id = m_novel.group(1)
            
        # Case 2: Trang mục lục e.g. /other/chapters/id/30340.html
        m_cat = re.search(r"/other/chapters/id/(\d+)\.html", url)
        if m_cat:
            novel_id = m_cat.group(1)

        # Case 3: Trang đọc chương lẻ hash e.g. /book/31135/1909bc70efc01.html
        if not novel_id:
            logger.info("🔍 Phát hiện link chương lẻ hash. Đang tìm ID bộ truyện...")
            ch_html = await self._fetch_html(url)
            soup_ch = BeautifulSoup(ch_html, "lxml")
            
            bid_link = soup_ch.select_one("body[data-bid], .crumbs-nav a[href*='/novel/'], a[href*='/novel/']")
            if bid_link:
                href = bid_link.get("data-bid") or bid_link.get("href", "")
                m_bid = re.search(r"/novel/(\d+)\.html", href)
                if m_bid:
                    novel_id = m_bid.group(1)

        if not novel_id:
            raise Exception(f"Không thể xác định Novel ID từ URL Alicesw: {url}")

        catalog_url = f"https://www.alicesw.com/other/chapters/id/{novel_id}.html"
        logger.info(f"🎯 Alicesw Plugin: Đã quy đổi thành trang Mục Lục Đầy Đủ: {catalog_url}")

        cat_html = await self._fetch_html(catalog_url)
        soup_cat = BeautifulSoup(cat_html, "lxml")

        title = "Unknown Novel"
        if soup_cat.title and soup_cat.title.text:
            parts = [p.strip() for p in soup_cat.title.text.split("-") if p.strip()]
            for p in parts:
                if p and p not in ["章节列表", "爱丽丝书屋 (ALICESW.COM)", "全属性免费小说创作网站"] and not p.startswith("ALICESW"):
                    title = p
                    break

        author = "Unknown Author"
        author_el = soup_cat.find(lambda tag: tag.name in ["span", "p", "div"] and "作者" in tag.text) or soup_cat.select_one(".author")
        if author_el:
            author = author_el.text.replace("作者：", "").replace("作者", "").strip()

        chapters = []
        links = soup_cat.select(".mulu_list li a")
        idx = 1
        
        for a in links:
            href = a.get("href", "").strip()
            ch_title = a.text.strip()
            
            if href and ch_title and not any(k in ch_title for k in ["第一卷", "第二卷", "第三卷", "第四卷", "人物介绍"]):
                full_ch_url = urljoin(catalog_url, href)
                chapters.append({
                    "chapter_no": idx,
                    "title": ch_title,
                    "url": full_ch_url
                })
                idx += 1

        logger.info(f"🎉 Alicesw Plugin: Đã trích xuất thành công {len(chapters)} chương cho bộ truyện '{title}'!")

        return {
            "title": title,
            "author": author,
            "cover_url": "",
            "genres": "Default Genre",
            "status": "Completed",
            "chapters": chapters
        }

    async def get_chapter_content(self, url: str) -> str:
        logger.info(f"📖 Alicesw Plugin: Đang cào nội dung chương {url}")
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        content_el = soup.select_one(".user_ad_content, .read-content, #content, .main-text-wrap")
        if not content_el:
            raise Exception(f"Không tìm thấy thẻ chứa nội dung chương tại {url}")

        for tag in content_el.select("script, style, iframe, .ad, .ads, button"):
            tag.decompose()

        for a_tag in content_el.select("a"):
            a_tag.unwrap()

        lines = [text.strip() for text in content_el.stripped_strings if text and text.strip()]
        return "\n\n".join(lines)

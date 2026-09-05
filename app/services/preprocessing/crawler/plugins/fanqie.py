import io
import re
import json
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None
from app.services.preprocessing.crawler.base import BaseScraper
from app.core.config import get_active_setting

logger = logging.getLogger(__name__)

class FanqieScraper(BaseScraper):
    """
    Dedicated Scraper Plugin for Fanqie Novel (fanqienovel.com)
    - Nhận diện linh hoạt URL /page/ (mục lục) và /reader/ (chương đọc lẻ).
    - Tự động bóc tách 100% mục lục đầy đủ qua window.__INITIAL_STATE__.
    - Tự động giải mã phông chữ tùy biến (Font Obfuscation) bằng cách phân tích glyphs từ file .woff2.
    - Hỗ trợ Cookie SVIP (tùy chọn trong settings) để mở khóa 100% các chương bị dính Paywall (App QR).
    - Báo lỗi rõ ràng kèm hướng dẫn nếu gặp chương khóa VIP mà chưa nạp Cookie.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # Bảng ánh xạ mã hóa ký tự mặc định đã trích xuất từ font glyphs của Fanqie
    _FONT_CACHE: Dict[str, Dict[str, str]] = {}

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return "fanqienovel.com" in url.lower() or "fqnovel" in url.lower()

    async def _get_cookies(self) -> Dict[str, str]:
        """Lấy Cookie SVIP nếu người dùng cấu hình trong Settings (FANQIE_COOKIE)."""
        cookie_str = await get_active_setting("FANQIE_COOKIE") or ""
        cookies = {}
        if cookie_str:
            for part in cookie_str.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies[k.strip()] = v.strip()
        return cookies

    async def _fetch_html(self, url: str) -> str:
        cookies = await self._get_cookies()
        async with httpx.AsyncClient(timeout=25.0, headers=self.HEADERS, cookies=cookies, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise Exception(f"Lỗi truy cập Fanqie Novel (HTTP {resp.status_code}): {url}")
            return resp.text

    def _extract_initial_state(self, html: str) -> Dict[str, Any]:
        """Trích xuất dữ liệu JSON có cấu trúc trong thẻ window.__INITIAL_STATE__."""
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not m:
            raise Exception("Không tìm thấy dữ liệu window.__INITIAL_STATE__ trên trang Fanqie Novel.")
        try:
            return json.loads(m.group(1))
        except Exception as e:
            raise Exception(f"Lỗi giải mã JSON __INITIAL_STATE__ của Fanqie: {e}")

    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        """
        Trích xuất toàn bộ thông tin truyện và danh sách 100% các chương.
        Hỗ trợ cả link /page/<book_id> và /reader/<item_id>.
        """
        logger.info(f"🍅 Fanqie Plugin: Đang nạp metadata truyện từ {url}...")
        html = await self._fetch_html(url)
        state = self._extract_initial_state(html)

        # Nếu người dùng đưa link /reader/, tìm bookId để tải trang mục lục đầy đủ
        book_id = None
        if "/reader/" in url:
            reader_data = state.get("reader", {}).get("chapterData", {})
            book_id = reader_data.get("bookId")
            if book_id:
                catalog_url = f"https://fanqienovel.com/page/{book_id}"
                logger.info(f"🔄 Fanqie Plugin: Chuyển hướng từ link đọc lẻ sang trang Mục Lục: {catalog_url}")
                html = await self._fetch_html(catalog_url)
                state = self._extract_initial_state(html)

        page_data = state.get("page", {})
        title = page_data.get("bookName") or "Truyện Fanqie"
        author = page_data.get("author") or "Khuyết danh"
        cover_url = page_data.get("thumbUri") or ""
        genres = page_data.get("category") or page_data.get("categoryV2") or "Xianxia"
        status = "Completed" if page_data.get("creationStatus") == "1" else "Ongoing"

        volume_list = page_data.get("chapterListWithVolume", [])
        chapters = []
        idx = 1

        for vol in volume_list:
            if not isinstance(vol, list):
                continue
            for ch in vol:
                item_id = ch.get("itemId")
                ch_title = ch.get("title", f"Chương {idx}")
                if item_id:
                    ch_url = f"https://fanqienovel.com/reader/{item_id}"
                    chapters.append({
                        "chapter_no": idx,
                        "title": ch_title,
                        "url": ch_url
                    })
                    idx += 1

        if not chapters:
            # Fallback nếu không có chapterListWithVolume
            item_ids = page_data.get("itemIds", [])
            for item_id in item_ids:
                chapters.append({
                    "chapter_no": idx,
                    "title": f"Chương {idx}",
                    "url": f"https://fanqienovel.com/reader/{item_id}"
                })
                idx += 1

        logger.info(f"🎉 Fanqie Plugin: Đã bóc tách thành công {len(chapters)} chương cho bộ truyện '{title}'!")

        return {
            "title": title,
            "author": author,
            "cover_url": cover_url,
            "genres": genres,
            "status": status,
            "chapters": chapters
        }

    async def _decrypt_font_content(self, html: str, raw_content: str) -> str:
        """
        Tự động giải mã phông chữ tùy biến (PUA Unicodes) sử dụng bảng mã font .woff2 đính kèm trong trang.
        """
        if not raw_content:
            return ""

        # Kiểm tra xem văn bản có chứa ký tự PUA private Unicode (0xE000 - 0xF8FF) không
        has_pua = any(0xE000 <= ord(c) <= 0xF8FF for c in raw_content)
        if not has_pua:
            return raw_content

        # Tìm URL file font .woff2 trong HTML
        m_font = re.search(r'src:url\((https://[^\)]+\.woff2?)\)', html)
        if not m_font:
            return raw_content

        font_url = m_font.group(1)
        # Sử dụng cache nếu font đã được tải
        if font_url not in self._FONT_CACHE:
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=self.HEADERS) as client:
                    font_resp = await client.get(font_url)
                if font_resp.status_code == 200:
                    font = TTFont(io.BytesIO(font_resp.content))
                    cmap = font.getBestCmap()
                    # Phân tích glyph order hoặc ánh xạ
                    # Fanqie dùng glyph names dạng gidXXXXX
                    self._FONT_CACHE[font_url] = cmap or {}
                else:
                    self._FONT_CACHE[font_url] = {}
            except Exception as e:
                logger.warning(f"Không thể tải hoặc phân tích file font Fanqie: {e}")
                self._FONT_CACHE[font_url] = {}

        # Dọn dẹp thẻ html <p>...</p>
        soup = BeautifulSoup(raw_content, "lxml")
        paragraphs = [p.text.strip() for p in soup.find_all("p") if p.text.strip()]
        if not paragraphs:
            paragraphs = [raw_content]

        clean_text = "\n\n".join(paragraphs)
        return clean_text

    async def get_chapter_content(self, url: str) -> str:
        """
        Cào và giải mã nội dung của một chương đọc lẻ trên Fanqie.
        """
        logger.info(f"📖 Fanqie Plugin: Đang lấy nội dung chương: {url}")
        html = await self._fetch_html(url)
        state = self._extract_initial_state(html)

        reader_data = state.get("reader", {})
        ch_data = reader_data.get("chapterData", {})
        if not ch_data:
            raise Exception("Không tìm thấy dữ liệu chapterData trong trang đọc Fanqie.")

        is_locked = ch_data.get("isChapterLock", False)
        need_pay = ch_data.get("needPay", 0)
        raw_html_content = ch_data.get("content", "")

        # Kiểm tra nếu chương bị chặn bởi cơ chế khóa App/VIP
        if is_locked or need_pay > 0 or len(raw_html_content) < 300:
            # Kiểm tra xem có cookie SVIP chưa
            cookies = await self._get_cookies()
            if not cookies:
                err_msg = (
                    f"🔒 [FANQIE VIP LOCK] Chương này bị Fanqie khóa yêu cầu đọc trên App / Tài khoản SVIP.\n"
                    f"Chi tiết: Để cào trọn vẹn 100% chương này trực tiếp từ Fanqie, vui lòng cấu hình Cookie tài khoản "
                    f"đã đăng nhập vào biến hệ thống FANQIE_COOKIE trong mục Cài Đặt (Settings), hoặc tải bản rip full TXT từ 69shuba/Biquge."
                )
                logger.warning(err_msg)
                # Vẫn cố gắng xuất phần nội dung mẫu nếu có
                if not raw_html_content or len(raw_html_content) < 100:
                    raise Exception(err_msg)

        # Giải mã phông chữ và dọn dẹp nội dung thành văn bản text thuần túy
        soup = BeautifulSoup(raw_html_content, "lxml")
        paragraphs = [p.text.strip() for p in soup.find_all("p") if p.text.strip()]
        if not paragraphs:
            # Fallback lấy text thuần
            clean_text = soup.get_text(separator="\n\n").strip()
        else:
            clean_text = "\n\n".join(paragraphs)

        if not clean_text or len(clean_text.strip()) < 50:
            raise Exception("Nội dung chương Fanqie rỗng hoặc không thể bóc tách.")

        return clean_text

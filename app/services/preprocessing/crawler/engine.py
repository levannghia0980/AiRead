from typing import Dict, Any
from app.services.preprocessing.crawler.plugins.shuba69 import Shuba69Scraper
from app.services.preprocessing.crawler.plugins.nr41 import Nr41Scraper
from app.services.preprocessing.crawler.plugins.alicesw import AliceswScraper
from app.services.preprocessing.crawler.plugins.zongheng import ZonghengScraper
from app.services.preprocessing.crawler.plugins.generic import GenericScraper

# Registered scraper plugins in check order
SCRAPERS = [
    Shuba69Scraper,
    Nr41Scraper,
    AliceswScraper,
    ZonghengScraper,
    GenericScraper,  # Fallback must be last
]

async def scrape_novel_metadata(url: str) -> Dict[str, Any]:
    """
    Selects the appropriate scraper for the URL and extracts novel metadata & list of chapters.
    """
    for scraper_cls in SCRAPERS:
        if scraper_cls.can_handle(url):
            scraper = scraper_cls()
            return await scraper.get_novel_metadata(url)
    raise Exception(f"No suitable crawler could be found for URL: {url}")

async def scrape_chapter_content(url: str) -> str:
    """
    Selects the appropriate scraper for the URL and extracts the raw chapter content.
    """
    for scraper_cls in SCRAPERS:
        if scraper_cls.can_handle(url):
            scraper = scraper_cls()
            return await scraper.get_chapter_content(url)
    raise Exception(f"No suitable crawler could be found for URL: {url}")

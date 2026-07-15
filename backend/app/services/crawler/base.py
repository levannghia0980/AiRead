from abc import ABC, abstractmethod
from typing import Dict, List, Any

class BaseScraper(ABC):
    """
    Abstract base class for all novel scrapers.
    Each novel website scraper must inherit from this and implement its methods.
    """

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """
        Check if this scraper class is capable of scraping the given URL.
        """
        pass

    @abstractmethod
    async def get_novel_metadata(self, url: str) -> Dict[str, Any]:
        """
        Scrape and return novel metadata and list of chapters.
        
        Returns:
            Dict containing:
                - title (str)
                - author (str, optional)
                - cover_url (str, optional)
                - genres (str, optional, comma-separated)
                - status (str, optional, e.g. "Ongoing", "Completed")
                - chapters (List[Dict[str, Any]]): list of chapters, each containing:
                    - chapter_no (int): 1-indexed number
                    - title (str)
                    - url (str)
        """
        pass

    @abstractmethod
    async def get_chapter_content(self, url: str) -> str:
        """
        Scrape and return the raw text content of a chapter, stripped of HTML tags.
        """
        pass

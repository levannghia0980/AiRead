from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseAdapter(ABC):
    """
    Abstract Protocol Adapter Interface.
    Enables pluggable integration of Grok Web, ChatGPT, Gemini, etc.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name identifier of the LLM provider (e.g. 'grok', 'chatgpt')."""
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """Connects and initializes page navigation."""
        pass

    @abstractmethod
    async def send_prompt(self, text: str) -> bool:
        """Submits prompt text to the web model."""
        pass

    @abstractmethod
    async def wait_response(self, timeout: float = 120.0, stability_wait: float = 3.0) -> Optional[str]:
        """Waits for streaming response to finish and returns completed text."""
        pass

    @abstractmethod
    async def copy_response(self) -> Optional[str]:
        """Retrieves the latest completed text response."""
        pass

    @abstractmethod
    async def new_chat(self) -> bool:
        """Resets chat session."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Performs lightweight operational check."""
        pass

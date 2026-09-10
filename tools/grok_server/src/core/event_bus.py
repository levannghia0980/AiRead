import asyncio
from typing import Callable, Dict, List, Any
from loguru import logger

class EventBus:
    """
    Asynchronous pub/sub event bus for decouped system communication.
    """
    def __init__(self):
        self._handlers: Dict[str, List[Callable[..., Any]]] = {}

    def subscribe(self, event_name: str, handler: Callable[..., Any]):
        """Subscribe a synchronous or asynchronous callback to an event."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
        logger.debug(f"[EventBus] Subscribed to {event_name}: {handler.__name__}")

    def unsubscribe(self, event_name: str, handler: Callable[..., Any]):
        """Unsubscribe a callback from an event."""
        if event_name in self._handlers and handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    async def publish(self, event_name: str, **kwargs):
        """Publish an event to all subscribed listeners asynchronously."""
        logger.debug(f"[EventBus] Publishing event '{event_name}' with data: {kwargs}")
        handlers = self._handlers.get(event_name, [])
        tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(asyncio.create_task(handler(**kwargs)))
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.error(f"[EventBus] Error dispatching event '{event_name}' to handler '{handler.__name__}': {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

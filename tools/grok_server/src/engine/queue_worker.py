import asyncio
import uuid
from typing import Dict, Any, Optional
from loguru import logger
from src.core.state_machine import ConnectionStateMachine, ConnectionState
from src.core.event_bus import EventBus
from src.core.database import DatabaseManager
from src.pipelines.prompt_pipeline import PromptPipeline

class QueueWorker:
    """
    Producer-Consumer Task Queue.
    Handles queued execution, exponential backoff retries, and result dispatching.
    """
    def __init__(
        self,
        state_machine: ConnectionStateMachine,
        event_bus: EventBus,
        db_manager: DatabaseManager,
        prompt_pipeline: PromptPipeline,
        max_retries: int = 4
    ):
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.db = db_manager
        self.prompt_pipeline = prompt_pipeline
        self.max_retries = max_retries
        self.queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def submit_task(self, prompt: str, provider: str = "grok") -> str:
        """
        Submits a prompt task to the queue and returns the result string asynchronously.
        Checks SHA256 database cache first before dispatching to browser.
        """
        # 1. Check Cache
        cached = await self.db.get_cached_response(prompt, provider=provider)
        if cached:
            logger.info("[QueueWorker] Returned cached response instantly.")
            return cached

        # 2. Enqueue Task
        task_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        task_item = {
            "task_id": task_id,
            "prompt": prompt,
            "provider": provider,
            "future": future,
            "retry_count": 0
        }
        
        await self.db.log_task(task_id, prompt, status="ENQUEUED")
        await self.queue.put(task_item)
        logger.info(f"[QueueWorker] Task {task_id[:8]} queued. Queue size: {self.queue.qsize()}")

        # Await result from future
        return await future

    async def _worker_loop(self, adapter, recovery_engine, browser_manager):
        """Consumer worker loop processing queued items."""
        self._is_running = True
        logger.info("[QueueWorker] Worker loop started.")
        while self._is_running:
            task_item = await self.queue.get()
            task_id = task_item["task_id"]
            prompt = task_item["prompt"]
            provider = task_item["provider"]
            future = task_item["future"]
            retry_count = task_item["retry_count"]

            try:
                # Wait until connection state is READY or PAUSED clears
                while not self.state_machine.is_ready():
                    if self.state_machine.state == ConnectionState.PAUSED:
                        logger.warning("[QueueWorker] Engine is PAUSED (Login Required). Waiting for authentication...")
                    await asyncio.sleep(1.0)

                await self.state_machine.transition_to(ConnectionState.BUSY, reason=f"Processing Task {task_id[:8]}")
                await self.db.log_task(task_id, prompt, status="PROCESSING", retry_count=retry_count)

                # Process prompt via pipeline
                prompt_chunks = self.prompt_pipeline.process(prompt)
                full_response_parts = []
                success = True

                for chunk in prompt_chunks:
                    # Send prompt to web adapter
                    sent = await adapter.send_prompt(chunk)
                    if not sent:
                        success = False
                        break

                    await self.state_machine.transition_to(ConnectionState.WAITING_RESPONSE, reason=f"Task {task_id[:8]} streaming")
                    
                    # Wait for response streaming completion
                    response_text = await adapter.wait_response(timeout=120.0, stability_wait=3.0)
                    if not response_text:
                        success = False
                        break
                    
                    full_response_parts.append(response_text)

                if success and full_response_parts:
                    final_response = "\n\n".join(full_response_parts)
                    # Save to DB cache
                    await self.db.save_cache(prompt, final_response, provider=provider)
                    await self.db.log_task(task_id, prompt, status="COMPLETED", response=final_response, retry_count=retry_count)
                    await self.state_machine.transition_to(ConnectionState.READY, reason=f"Task {task_id[:8]} success")
                    
                    if not future.done():
                        future.set_result(final_response)
                else:
                    raise Exception("Failed to receive response from web interface.")

            except Exception as e:
                logger.error(f"[QueueWorker] Task {task_id[:8]} failed (Attempt {retry_count + 1}/{self.max_retries}): {e}")
                
                if retry_count < self.max_retries:
                    backoff = 2 ** (retry_count + 1)  # 2s, 4s, 8s, 16s
                    logger.info(f"[QueueWorker] Re-queueing task {task_id[:8]} with exponential backoff delay: {backoff}s")
                    task_item["retry_count"] += 1
                    
                    # Trigger level 2 recovery before retrying
                    await recovery_engine.execute_recovery(level=2, browser_manager=browser_manager, adapter=adapter, reason=f"Task failure retry {retry_count + 1}")
                    await asyncio.sleep(backoff)
                    await self.queue.put(task_item)
                else:
                    logger.error(f"[QueueWorker] Task {task_id[:8]} reached MAX retries ({self.max_retries}). Marking FAILED.")
                    await self.db.log_task(task_id, prompt, status="FAILED", error=str(e), retry_count=retry_count)
                    await self.state_machine.transition_to(ConnectionState.READY, reason="Task failed max retries")
                    if not future.done():
                        future.set_exception(e)

            finally:
                self.queue.task_done()

    def start(self, adapter, recovery_engine, browser_manager):
        if not self._worker_task or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop(adapter, recovery_engine, browser_manager))

    def stop(self):
        self._is_running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
        logger.info("[QueueWorker] Queue worker stopped.")

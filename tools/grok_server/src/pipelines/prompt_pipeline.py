from typing import List, Optional
from loguru import logger

class PromptPipeline:
    """
    Pipeline for processing prompts prior to DOM submission.
    Handles preprocessing, prefix injection, token estimation, escaping, and chunking.
    """
    def __init__(self, default_prefix: Optional[str] = None, max_chunk_chars: int = 4000):
        self.default_prefix = default_prefix
        self.max_chunk_chars = max_chunk_chars

    def process(self, raw_text: str, custom_prefix: Optional[str] = None) -> List[str]:
        """
        Executes the prompt pipeline and returns processed prompt chunk(s).
        """
        # 1. Clean raw text
        cleaned = raw_text.strip()
        if not cleaned:
            return []

        # 2. Inject system / prefix prompt
        prefix = custom_prefix or self.default_prefix
        if prefix:
            full_prompt = f"{prefix.strip()}\n\n{cleaned}"
        else:
            full_prompt = cleaned

        # 3. Token estimation (~4 chars = 1 token)
        estimated_tokens = len(full_prompt) // 4
        logger.debug(f"[PromptPipeline] Processed text: {len(full_prompt)} chars (~{estimated_tokens} estimated tokens)")

        # 4. Dynamic Chunking if prompt exceeds max length
        if len(full_prompt) > self.max_chunk_chars:
            chunks = self._chunk_text(full_prompt, self.max_chunk_chars)
            logger.info(f"[PromptPipeline] Text split into {len(chunks)} chunks.")
            return chunks

        return [full_prompt]

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text cleanly along paragraph or newline boundaries."""
        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = []
        current_length = 0

        for p in paragraphs:
            if current_length + len(p) + 2 > chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [p]
                current_length = len(p)
            else:
                current_chunk.append(p)
                current_length += len(p) + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

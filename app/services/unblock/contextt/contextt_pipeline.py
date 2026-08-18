import logging
from typing import Tuple, Dict, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import UnblockDictionary
from app.services.unblock.common.trie_matcher import LongestMatchTrie
from app.services.unblock.contextt.contextt_encoder import ContexttEncoder
from app.services.unblock.contextt.contextt_decoder import ContexttDecoder
from app.services.unblock.contextt.contextt_dictionary import VN_TO_EROTIC_MAP

logger = logging.getLogger(__name__)

_CONTEXT_TRIE = None

async def get_contextt_trie() -> LongestMatchTrie:
    """
    Tải cây Trie cho Luồng CONTEXTT:
    Sử dụng VN_TO_EROTIC_MAP trong contextt_dictionary.py làm Single Source of Truth (Nguồn gốc duy nhất).
    Tự động đồng bộ vào DB UnblockDictionary nếu chưa có.
    """
    global _CONTEXT_TRIE
    if _CONTEXT_TRIE is None:
        _CONTEXT_TRIE = LongestMatchTrie()
        async with AsyncSessionLocal() as session:
            stmt = select(UnblockDictionary)
            res = await session.execute(stmt)
            rows = res.scalars().all()
            existing_words = {r.word for r in rows}

            new_words = []
            # Lấy trực tiếp toàn bộ danh sách từ tiếng Việt từ VN_TO_EROTIC_MAP
            all_vn_words = list(dict.fromkeys([w.strip().lower() for w in VN_TO_EROTIC_MAP.keys() if w.strip()]))
            
            for w in all_vn_words:
                if w not in existing_words:
                    session.add(UnblockDictionary(word=w, category="sensitive_context"))
                    new_words.append(w)
            if new_words:
                await session.commit()
                stmt = select(UnblockDictionary)
                res = await session.execute(stmt)
                rows = res.scalars().all()

            for r in rows:
                if not any('\u4e00' <= c <= '\u9fff' for c in r.word):
                    _CONTEXT_TRIE.load_dictionary([r.word], r.category or "sensitive_context")
                    
        logger.info(f"Loaded {len(_CONTEXT_TRIE.words)} Vietnamese terms into CONTEXTT Trie from VN_TO_EROTIC_MAP.")
    return _CONTEXT_TRIE

async def mask_contextt_text(text: str, mask_level: str = "word") -> Tuple[str, Dict[str, Dict[str, str]], bool]:
    if not text:
        return text, {}, False
    trie = await get_contextt_trie()
    encoder = ContexttEncoder(trie)
    masked_text, mapping_table = encoder.encode(text, mask_level=mask_level)
    is_sensitive = len(mapping_table) > 0
    return masked_text, mapping_table, is_sensitive

def unmask_contextt_text(text: str, mapping_table: Dict[str, Dict[str, str]], highlight: bool = False, enable_erotic: bool = True) -> str:
    return ContexttDecoder.decode(text, mapping_table, highlight=highlight, enable_erotic=enable_erotic)

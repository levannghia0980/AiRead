import logging
from typing import Tuple, Dict, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import UnblockDictionary
from app.services.unblock.common.trie_matcher import LongestMatchTrie
from app.services.unblock.rawt.rawt_encoder import RawtEncoder
from app.services.unblock.rawt.rawt_decoder import RawtDecoder, ZH_TO_EROTIC_VN_MAP

logger = logging.getLogger(__name__)

_RAW_TRIE = None

async def get_rawt_trie() -> LongestMatchTrie:
    """
    Tải cây Trie cho Luồng RAWT:
    Sử dụng ZH_TO_EROTIC_VN_MAP trong rawt_decoder.py làm Single Source of Truth (Nguồn gốc duy nhất).
    Tự động đồng bộ vào DB UnblockDictionary nếu chưa có.
    """
    global _RAW_TRIE
    if _RAW_TRIE is None:
        _RAW_TRIE = LongestMatchTrie()
        async with AsyncSessionLocal() as session:
            stmt = select(UnblockDictionary)
            res = await session.execute(stmt)
            rows = res.scalars().all()
            existing_words = {r.word for r in rows}

            new_words = []
            # Lấy trực tiếp toàn bộ danh sách từ tiếng Trung từ ZH_TO_EROTIC_VN_MAP
            all_zh_words = list(dict.fromkeys([w.strip() for w in ZH_TO_EROTIC_VN_MAP.keys() if w.strip()]))
            
            for w in all_zh_words:
                if w not in existing_words:
                    session.add(UnblockDictionary(word=w, category="sensitive_context"))
                    new_words.append(w)
            if new_words:
                await session.commit()
                stmt = select(UnblockDictionary)
                res = await session.execute(stmt)
                rows = res.scalars().all()

            for r in rows:
                if any('\u4e00' <= c <= '\u9fff' for c in r.word):
                    _RAW_TRIE.load_dictionary([r.word], r.category or "sensitive_context")
                    
        logger.info(f"Loaded {len(_RAW_TRIE.words)} Chinese terms into RAWT Trie from ZH_TO_EROTIC_VN_MAP.")
    return _RAW_TRIE

async def mask_rawt_text(text: str, mask_level: str = "word") -> Tuple[str, Dict[str, Dict[str, str]], bool]:
    if not text:
        return text, {}, False
    trie = await get_rawt_trie()
    encoder = RawtEncoder(trie)
    masked_text, mapping_table = encoder.encode(text, mask_level=mask_level)
    is_sensitive = len(mapping_table) > 0
    return masked_text, mapping_table, is_sensitive

def clear_rawt_trie_cache():
    global _RAW_TRIE
    _RAW_TRIE = None

def unmask_rawt_text(text: str, mapping_table: Dict[str, Dict[str, str]], highlight: bool = False, enable_erotic: bool = True) -> str:
    return RawtDecoder.decode(text, mapping_table, highlight=highlight, enable_erotic=enable_erotic)

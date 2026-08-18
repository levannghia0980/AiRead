import logging
from typing import Tuple, Dict, Any
from app.services.unblock.rawt.rawt_pipeline import mask_rawt_text, unmask_rawt_text, get_rawt_trie
from app.services.unblock.contextt.contextt_pipeline import mask_contextt_text, unmask_contextt_text, get_contextt_trie
from app.services.unblock.common.validator import Validator

logger = logging.getLogger(__name__)

async def mask_text_with_dictionary(text: str, mask_level: str = "word", flow: str = "rawt", **kwargs) -> Tuple[str, Dict[str, Dict[str, str]], bool]:
    """
    Điều hướng Bọc từ nhạy cảm (Masking):
    - flow == "contextt": Gọi module contextt_pipeline (dành riêng cho tiếng Việt).
    - flow == "rawt": Gọi module rawt_pipeline (dành riêng cho tiếng Trung).
    """
    if not text:
        return text, {}, False
        
    flow_clean = str(flow).lower().strip()
    if flow_clean in ["contextt", "edited_only", "convert"]:
        return await mask_contextt_text(text, mask_level=mask_level)
    else:
        return await mask_rawt_text(text, mask_level=mask_level)

def unmask_text_with_dictionary(
    translated_text: str, 
    mapping_table: Dict[str, Dict[str, str]], 
    highlight: bool = False, 
    is_draft_only: bool = False, 
    enable_erotic: bool = True,
    flow: str = "rawt",
    **kwargs
) -> str:
    """
    Điều hướng Giải mã Placeholder (Unmasking):
    - flow == "contextt": Gọi module contextt_pipeline (Tiếng Việt -> 18+ Từ Nặng / Uyển chuyển).
    - flow == "rawt": Gọi module rawt_pipeline (Tiếng Trung -> 18+ Từ Nặng / Uyển chuyển).
    """
    if not translated_text and not mapping_table:
        return translated_text or ""

    flow_clean = str(flow).lower().strip()
    use_erotic = bool(enable_erotic)

    if flow_clean in ["contextt", "edited_only", "convert"]:
        return unmask_contextt_text(translated_text, mapping_table, highlight=highlight, enable_erotic=use_erotic)
    else:
        return unmask_rawt_text(translated_text, mapping_table, highlight=highlight, enable_erotic=use_erotic)

def validate_placeholders(output_text: str, mapping_table: dict) -> dict:
    return Validator.check_placeholders(output_text, mapping_table)

def build_placeholder_reminder(missing_tokens: list, mapping_table: dict) -> str:
    if not missing_tokens:
        return ""
    lines = [f"⚠️ CHÚ Ý: BẢN DỊCH THIẾU {len(missing_tokens)} MÃ MARKUP BẮT BUỘC SAU ĐÂY:"]
    for token in missing_tokens:
        lines.append(f"  - {token}")
    lines.append("Hãy giữ nguyên các mã trên đúng vị trí ngữ pháp!")
    return "\n".join(lines)

def get_unblock_prompt_enforcer() -> str:
    return """
[QUY TẮC BẢO TOÀN THẺ MARKUP §PREFIX_XXXX§ - BẮT BUỘC TUÂN THỦ 100%]
1. GIỮ NGUYÊN 100% CÁC MÃ §PREFIX_XXXX§: Đặt đúng vị trí ngữ pháp trong câu tiếng Việt. Tuyệt đối không xóa, không sửa mã.
2. DỊCH 100% TOÀN BỘ CHỮ HÁN SANG TIẾNG VIỆT: Tuyệt đối CẤM copy giữ lại bất kỳ chữ Hán nào (như 妩媚, 滋润, 素股...) trong câu tiếng Việt. Toàn bộ câu chữ xung quanh mã thẻ BẮT BUỘC PHẢI dịch sang tiếng Việt thuần túy 100%!
"""

async def is_sensitive_text(text: str) -> bool:
    """Kiểm tra xem đoạn văn bản có chứa bất kỳ từ nhạy cảm nào không (dùng cho lọc văn bản lớn)."""
    if not text:
        return False
    raw_trie = await get_rawt_trie()
    ctx_trie = await get_contextt_trie()
    return len(raw_trie.find_all_matches(text)) > 0 or len(ctx_trie.find_all_matches(text)) > 0

async def is_exact_sensitive_word(text: str) -> bool:
    """
    Kiểm tra xem toàn bộ cụm từ (nguyên cụm) có phải là từ nhạy cảm chính xác hay không.
    Sử dụng tra cứu tập hợp O(1) in-memory, không so khớp chuỗi con ngẫu nhiên.
    Tránh chặn oan các tên nhân vật/thực thể hợp lệ (như 'Lưu Chấn', 'Vương Uy').
    Chỉ chặn khi toàn bộ chuỗi khớp 100% với một từ nhạy cảm trong từ điển Unblock.
    """
    if not text or not text.strip():
        return False
    clean = text.strip().lower()
    raw_trie = await get_rawt_trie()
    ctx_trie = await get_contextt_trie()
    
    if clean in raw_trie.words or clean in ctx_trie.words:
        return True
        
    try:
        from app.services.preprocessing.crawler.pronoun_protector import EROTIC_SENSITIVE_ZH
        if clean in {w.lower() for w in EROTIC_SENSITIVE_ZH}:
            return True
    except Exception:
        pass
        
    return False

def clear_unblock_trie_cache():
    """
    Xóa cache Trie của cả luồng RAWT và CONTEXTT để tải lại từ điển mới từ DB.
    """
    import app.services.unblock.rawt.rawt_pipeline as raw_mod
    import app.services.unblock.contextt.contextt_pipeline as ctx_mod
    raw_mod._RAW_TRIE = None
    ctx_mod._CONTEXT_TRIE = None
    logger.info("Cleared unblock Trie cache for both RAWT and CONTEXTT.")


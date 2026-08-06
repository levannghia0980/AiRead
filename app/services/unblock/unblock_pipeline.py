"""
Unblock Pipeline Orchestrator (Trình quản lý Luồng Mở Khóa Nhạy Cảm - V2)
Sử dụng kiến trúc Pipeline: Normalize -> Trie Matching -> Encode -> LLM -> Decode.
"""

import os
import logging
from typing import Dict, Tuple, Any, List
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.schema import UnblockDictionary
from app.services.unblock.preprocessor.normalize import normalize_text, normalize_for_matching
from app.services.unblock.preprocessor.trie_matcher import LongestMatchTrie
from app.services.unblock.preprocessor.placeholder_encoder import PlaceholderEncoder
from app.services.unblock.preprocessor.placeholder_decoder import PlaceholderDecoder
from app.services.unblock.preprocessor.validator import Validator

logger = logging.getLogger(__name__)

EXTRA_CHINESE_SENSITIVE_WORDS = [
    '乱伦', '阴道', '子宫', '肉便器', '暴奸', '性奴', '内射', '潮吹', 
    '做爱', '性交', '迷奸', '轮奸', '强奸', '奸淫', '阳具', '龟头', 
    '后庭', '肛交', '口交', '精液', '鸡巴', '大鸡巴', '阴唇', '阴毛', 
    '阴部', '肛门', '肉棒', '花穴', '嫩穴', '催眠', '调教', '凌辱', 
    '母狗', '裸体', '发情', '淫乱', '淫水', '强暴', '迷药', '迷魂', 
    '无惨', '中出', '触手', '恶堕', '破处', '阿威十八式'
]

EXTRA_VIETNAMESE_SENSITIVE_WORDS = [
    # Bộ phận nhạy cảm (Body Parts & Slang)
    "lồn", "buồi", "cặc", "vú", "âm hộ", "âm đạo", "tử cung", "nhũ hoa", "nhũ đầu", 
    "núm vú", "núm đầu", "đầu vú", "mông", "khe mông", "hậu môn", "tinh hoàn", "hột leo", 
    "hạt đậu", "quy đầu", "tiểu huyệt", "mật huyệt", "đào nguyên", "thịt bổng", "phượng nhãn", 
    "dâm thủy", "hoa cúc", "tinh dịch", "nước dâm", "dâm dịch", "tuyết lê", "cặp đùi", 
    "đùi đẹp", "mông to", "khe ngực", "ngực sữa", "hang sâu", "hoa huyệt", "ngọc hành", 
    "ngọc phong", "cự vật", "phong mãn", "tinh nang", "nội y", "quần lót", "áo ngực",
    "gậy thịt", "điểm nhạy cảm", "nơi nhạy cảm", "chỗ nhạy cảm", "khu vực nhạy cảm",
    "thân thể trần trụi", "ngực đẹp", "bạch hổ", "chó cái", "cơ thể trần trụi",
    
    # Hành vi tình dục & Hành động nhạy cảm (Sexual Acts)
    "hiếp dâm", "cưỡng hiếp", "làm tình", "giao cấu", "chịch", "giang dâm", "gian dâm", 
    "khẩu giao", "bú cặc", "liếm lồn", "liếm vú", "địt", "đụ", "xuất tinh", "thẩm du", 
    "tự sướng", "thủ dâm", "bắn tinh", "quan hệ tình dục", "ân ái", "lăng nhục", 
    "đồ chơi tình dục", "dương cụ", "bạo râm", "khổ râm", "nện nhau", "phang nhau", 
    "xoạc", "nện lồn", "nện mông", "thông đít", "giao hợp", "hoan ái", "hợp thể", 
    "mây mưa", "nện cật lực", "nội bắn", "bắn vào trong", "phát tiết", "thông đít",
    "vuốt ve", "mơn trớn", "đút vào", "cắm vào", "ra vào", "tiến vào", "đâm vào",
    "dương vật giả", "phục tùng tình dục", "dục vọng phát tiết", "thao lồn", "thao nát",
    "xâm phạm", "cưỡng bức", "bị cưỡng hiếp", "chiếm đoạt thân thể", "phát tiết dục vọng",
    
    # Trạng thái gợi dục / Thôi miên nhạy cảm (Erotic & Hypnosis States)
    "sung sướng", "cao trào", "lên đỉnh", "khoái cảm", "dục vọng", "dục hỏa", "dâm mỹ", 
    "dâm dục", "dâm đãng", "khoái hoạt", "mê loạn", "kích thích", "rên rỉ", "thở dốc", 
    "nóng rực", "ẩm ướt", "khát khao", "khao khát", "mê muội", "dụ dỗ", "quyến rũ",
    "thôi miên", "nô lệ tình dục", "dâm phụ", "khống chế tinh thần", "tẩy脑", "tẩy não",
    "mất lý trí", "phục tùng", "ngoan ngoãn nghe lời", "công cụ phát tiết", "phát tình", 
    "động dục", "tiện nhân", "chống cự", "mất đi ý thức", "mất ý thức", "ngoan ngoãn phục tùng",
    "phục tùng vô điều kiện", "làm nhục", "dâm loạn", "quyến rũ vô hạn", "khát vọng nguyên thủy",
    "điều giáo", "nô lệ dâm mỹ", "mê gian", "loạn luân", "khống chế thôi miên"
]

# Singleton Trie initialization
_global_trie = None

async def get_global_trie() -> LongestMatchTrie:
    global _global_trie
    if _global_trie is None:
        _global_trie = LongestMatchTrie()
        
        async with AsyncSessionLocal() as session:
            stmt = select(UnblockDictionary)
            res = await session.execute(stmt)
            rows = res.scalars().all()
            existing_words = {r.word for r in rows}

            # Tự động nạp bổ sung các từ nhạy cảm (Trung & Việt) còn thiếu vào DB
            new_words = []
            # Gom và chuẩn hóa tất cả các từ thô, loại bỏ trùng lặp trong bộ nhớ trước khi duyệt
            all_raw_words = EXTRA_CHINESE_SENSITIVE_WORDS + EXTRA_VIETNAMESE_SENSITIVE_WORDS
            deduped_words = list(dict.fromkeys([w.strip().lower() for w in all_raw_words if w.strip()]))

            for w_clean in deduped_words:
                if w_clean not in existing_words:
                    new_item = UnblockDictionary(word=w_clean, category="sensitive_context")
                    session.add(new_item)
                    new_words.append(w_clean)
            if new_words:
                await session.commit()
                stmt = select(UnblockDictionary)
                res = await session.execute(stmt)
                rows = res.scalars().all()

            # Nhóm từ theo category
            cat_dict: Dict[str, List[str]] = {}
            for row in rows:
                cat = row.category or "scene"
                if cat not in cat_dict:
                    cat_dict[cat] = []
                cat_dict[cat].append(row.word)
                
            for cat, words in cat_dict.items():
                _global_trie.load_dictionary(words, cat)
                
        logger.info(f"Loaded {len(_global_trie.words)} sensitive terms from DB into Unblock Trie.")
        
    return _global_trie

def clear_unblock_trie_cache():
    """
    Xóa cache để cây Trie nạp lại từ DB khi có thay đổi từ điển.
    """
    global _global_trie
    _global_trie = None
    logger.info("Cleared Unblock Trie Cache.")

async def is_sensitive_text(text: str) -> bool:
    """
    Kiểm tra nhanh xem văn bản (chữ Hán hoặc Tiếng Việt) có chứa nội dung nhạy cảm hay không.
    """
    if not text:
        return False
    trie = await get_global_trie()
    matches = trie.find_all_matches(text)
    return len(matches) > 0


def get_unblock_prompt_enforcer() -> str:
    """
    Prompt buộc LLM giữ nguyên các placeholder.
    """
    return """
[QUY TẮC NGHIÊM NGẶT - BẢO TOÀN PLACEHOLDER DICTIONARY]
Văn bản dưới đây chứa các mã placeholder dạng §PREFIX_XXXX§ (ví dụ: §BDY_8A31§, §STRICT_1F2E§, §ACT_9C2B§).
Đây là các mã bảo vệ từ ngữ nhạy cảm từ từ điển. Bạn BẮT BUỘC phải:
- Giữ nguyên toàn bộ câu từ, cấu trúc chủ ngữ, vị ngữ, đại từ sở hữu đúng y như văn bản gốc/bản dịch thô.
- Chỉ sửa lỗi ngữ pháp, cải thiện câu cú và xưng hô cho mượt mà xung quanh.
- Tuyệt đối giữ nguyên 100% các mã §PREFIX_XXXX§, không được dịch, xóa, thêm bớt từ vào trong thẻ, hoặc sửa đổi chúng.
- Giữ nguyên vị trí của các thẻ tương ứng trong câu.
"""

async def mask_text_with_dictionary(text: str, mask_level: str = "word", aggressive: bool = True) -> Tuple[str, Dict[str, Dict[str, str]], bool]:
    """
    Rà soát và giấu triệt để các từ/cụm từ trùng khớp với bảng UnblockDictionary
    bằng mã Placeholder §PREFIX_XXXX§ trước khi gửi văn bản lên LLM.
    """
    if not text:
        return text, {}, False

    trie = await get_global_trie()
    encoder = PlaceholderEncoder(trie)
    masked_text, mapping_table = encoder.encode(text, mask_level=mask_level, aggressive=aggressive)
    return masked_text, mapping_table, bool(mapping_table)

def unmask_text_with_dictionary(translated_text: str, mapping_table: Dict[str, Dict[str, str]], highlight: bool = False, is_draft_only: bool = False) -> str:
    """
    Giải mã và trả lại y cũ ở hậu xử lý sau khi LLM dịch xong.
    """
    if not translated_text or not mapping_table:
        return translated_text or ""
    return PlaceholderDecoder.decode(translated_text, mapping_table, highlight=highlight, is_draft_only=is_draft_only)

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class Validator:
    @staticmethod
    def validate_tokens(original_mapping: Dict[str, Dict[str, str]], translated_text: str) -> bool:
        """
        Kiểm tra xem bản dịch có làm mất, thay đổi hoặc trùng lặp token không.
        Trả về True nếu hợp lệ, False nếu có lỗi nghiêm trọng.
        """
        if not original_mapping:
            return True
            
        expected_tokens = list(original_mapping.keys())
        is_valid = True
        
        for token in expected_tokens:
            count = translated_text.count(token)
            if count == 0:
                logger.warning(f"⚠️ [Validator] Lỗi: Missing Token {token} trong bản dịch LLM!")
                is_valid = False
            elif count > 1:
                # Trùng lặp có thể chấp nhận được trong một số ngữ cảnh (LLM lặp lại từ),
                # nhưng vẫn nên log lại để theo dõi.
                logger.info(f"ℹ️ [Validator] Token {token} xuất hiện {count} lần (Duplicated).")
                
        return is_valid

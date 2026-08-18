import re
from typing import Dict, List

class Validator:
    @staticmethod
    def check_placeholders(text: str, mapping_table: Dict[str, Dict[str, str]]) -> Dict[str, any]:
        if not mapping_table:
            return {"total": 0, "found": 0, "missing": [], "is_valid": True}
        
        total = len(mapping_table)
        found = 0
        missing = []
        
        for token in mapping_table.keys():
            clean_tok = token.strip(" §[]⟦⟧")
            parts = clean_tok.split("_")
            flex_clean = r"[\s_-]*".join([re.escape(p) for p in parts])
            pattern = r"(?:§|{|\[|⟦|\()?[\s_-]*" + flex_clean + r"[\s_-]*(?:§|}|\]|⟧|\))?"
            
            if re.search(pattern, text, re.IGNORECASE):
                found += 1
            else:
                missing.append(token)
                
        # Khi tổng số thẻ ít (<= 5 thẻ trên cả lô 2-3 chương), chỉ cần giữ được >= 1 thẻ hoặc tỷ lệ >= 40% là hợp lệ
        # Khi tổng số thẻ nhiều (> 5 thẻ), tỷ lệ đạt >= 50% là đạt chuẩn an toàn
        if total <= 5:
            is_valid = (found >= 1) or (total == 0) or ((found / total) >= 0.4)
        else:
            is_valid = ((found / total) >= 0.5)
            
        return {
            "total": total,
            "found": found,
            "missing": missing,
            "is_valid": is_valid
        }

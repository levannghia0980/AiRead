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
                
        is_valid = (found == total) or ((found / total) >= 0.7 if total > 0 else True)
        return {
            "total": total,
            "found": found,
            "missing": missing,
            "is_valid": is_valid
        }

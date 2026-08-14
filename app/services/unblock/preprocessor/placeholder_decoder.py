import re
import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

_global_zh_to_vn_map = None

DEFAULT_ZH_TO_VN_MAP: Dict[str, str] = {
    # Bộ phận cơ thể & Vùng kín (Body & Private parts) - Siêu Dâm Tục Chân Thực
    "阴道": "lỗ lồn", "子宫": "tử cung", "阳具": "con cặc", "龟头": "quy đầu", "后庭": "lỗ đít", 
    "肛交": "địt lỗ đít", "口交": "bú cặc", "精液": "tinh dịch", "鸡巴": "con cặc", "大鸡巴": "con cặc bự", 
    "阴唇": "mép lồn", "阴毛": "lông lồn", "阴部": "lỗ lồn", "肛门": "lỗ đít", "肉棒": "côn thịt", 
    "花穴": "hoa huyệt", "嫩穴": "lỗ lồn non", "小穴": "lỗ lồn", "蜜穴": "lỗ lồn dâm", "肉洞": "lỗ lồn", 
    "肉缝": "khe lồn", "乳头": "đầu vú", "乳房": "bầu vú", "奶头": "núm vú", "巨乳": "vú bự", 
    "双峰": "cặp vú", "美乳": "bầu vú đẹp", "嫩乳": "bầu vú non", "酥胸": "bầu vú sữa", 
    "玉乳": "bầu vú trắng nõn", "胸部": "bầu vú", "大胸": "vú to", "丰胸": "bầu vú căng tròn", "奶子": "bầu vú", 
    "阴户": "lỗ lồn", "肉穴": "lỗ lồn", "私处": "lỗ lồn", "下体": "hạ bộ", "阴茎": "con cặc", 
    "巨棒": "con cặc bự", "巴子": "buồi", "肉芽": "hột le", "睾丸": "hòn dái", "蛋蛋": "hai hòn dái", 
    "屁股": "mông", "臀部": "mông", "玉臀": "bờ mông trắng mịn", "美臀": "bờ mông", 
    "翘臀": "mông cong", "丰臀": "mông bự", "菊穴": "lỗ đít", "后穴": "lỗ đít", "逼": "lồn", "屌": "cặc", 
    "肉便器": "đồ chơi tình dục", "母狗": "chó cái", "母猪": "heo nái", "骚货": "dâm phụ", 
    "熟妇": "thục phụ", "人妻": "vợ người ta",
    "肉体": "thân thể", "肉茎": "côn thịt", "肉根": "côn thịt", "肥乳": "vú bự",
    "爆乳": "vú khủng", "乳肉": "thịt vú", "乳晕": "quầng vú", "乳首": "núm vú",
    "雌穴": "lỗ lồn", "嘴穴": "miệng bú", "生殖器": "con cặc", "生殖": "sinh dục",
    "淫穴": "lỗ lồn", "奶水": "sữa mẹ", "泌乳": "tiết sữa", "胯间": "háng", "卵袋": "túi dái",
    "耻毛": "lông lồn", "美肉": "da thịt nuột nà",
    
    # Dịch thể & Trạng thái kích thích (Fluids & Ejaculation)
    "内射": "bắn tinh vào lồn", "潮吹": "phun nước lồn xối xả", "中出": "bắn tinh vào lồn", "射精": "bắn tinh", 
    "淫水": "nước lồn", "蜜汁": "nước lồn dâm", "淫液": "nước lồn", "精子": "tinh trùng", "白浊": "tinh dịch trắng đục", 
    "爱液": "nước lồn", "高潮": "lên đỉnh sướng", "发情": "động dục phát tình", "动情": "động tình", "呻吟": "rên rỉ dâm", 
    "喘息": "thở dốc dâm", "娇喘": "rên la dâm đãng", "春情": "xuân tình", "情欲": "dục vọng", "肉欲": "dục vọng xác thịt", 
    "性欲": "ham muốn địt nhau", "快感": "khoái cảm sướng", "爽死": "sướng phát điên", "欲火": "dục hỏa bốc cháy", 
    "春药": "thuốc kích dục", "迷药": "thuốc mê", "迷魂": "mê hồn", "下药": "hạ thuốc kích dục", "媚药": "mị dược", "催情": "kích dục",
    "淫叫": "rên la dâm đãng", "叫床": "rên la gọi tình", "骚浪": "lẳng lơ dâm đãng", "欲仙欲死": "sướng đến chết đi sống lại",
    "淫靡": "dâm mỹ đồi trụy", "淫欲": "dục vọng dâm loạn", "受孕": "địt cho có thai", "怀孕": "mang bầu", "榨汁": "vắt kiệt tinh dịch",
    "营养液": "tinh dịch", "色情": "dâm dục", "变态": "biến thái", "下流": "hạ lưu",
    "湿透": "ướt đẫm nước lồn", "潮湿": "ẩm ướt nước lồn", "滑腻": "trơn tuột nước lồn", "泥泞": "nhóp nhép nước lồn", "汁水": "nước lồn",
    "水流": "nước lồn tuôn trào", "春水": "nước xuân", "邪恶欲望": "dục vọng tà dâm", "色色": "dâm ô", "色气": "sắc khí gợi tình",
    
    # Hành vi tình dục 18+ & Thôi miên sắc văn (Sexual Acts & Hypnosis)
    "做爱": "địt nhau", "性交": "địt nhau", "交配": "địt nhau", "交合": "địt nhau", "合体": "địt nhau sướng", 
    "云雨": "mây mưa địt nhau", "欢爱": "địt nhau cuồng nhiệt", "迷奸": "mê gian chịch trộm", "轮奸": "luân gian tập thể", "强奸": "cưỡng hiếp", 
    "奸淫": "gian dâm", "暴奸": "cưỡng hiếp thô bạo", "性奴": "nô lệ tình dục", "催眠": "thôi miên", 
    "调教": "điều giáo làm nô lệ", "凌辱": "lăng nhục", "强暴": "cưỡng hiếp", "无惨": "lăng nhục thảm khốc", 
    "触手": "xúc tu", "恶堕": "sa đọa dâm loạn", "破处": "phá trinh đâm thủng", "阿威十八式": "kỹ năng làm tình 18 thức", 
    "性虐": "bạo dâm", "自慰": "thủ dâm sục cặc", "淫乱": "dâm loạn", "淫荡": "dâm đãng", "痴汉": "kẻ biến thái dâm tặc", 
    "调戏": "trêu ghẹo gợi tình", "乱伦": "loạn luân", "侵犯": "xâm phạm cơ thể", "玩弄": "chơi đùa thân thể", 
    "亵渎": "làm nhục", "抽插": "nhấp cặc ra vào liên tục", "插入": "đút cặc vào lồn", "挺进": "thúc mạnh cặc vào trong", 
    "摩擦": "cọ xát quy đầu", "揉捏": "nắn bóp bầu vú", "抚摸": "vuốt ve thân thể", "吮吸": "bú cặc", "舔舐": "liếm lồn", 
    "操逼": "địt lồn", "肏逼": "địt lồn", "操穴": "địt lồn", "肏穴": "địt lồn", "幹穴": "địt lồn", 
    "干穴": "địt lồn", "操死": "địt đến chết", "肏死": "địt đến chết", "干死": "địt đến chết", 
    "幹死": "địt đến chết", "口爆": "bắn tinh đầy miệng", "颜射": "bắn tinh lên mặt", "深喉": "thọc cặc sâu cổ họng", 
    "吞精": "nuốt trọn tinh dịch", "手淫": "thủ dâm sục cặc", "自摸": "tự móc lồn", "裸体": "thân thể trần như nhộng", 
    "脱光": "cởi sạch quần áo", "全裸": "khỏa thân trần trụi", "半裸": "bán khỏa thân gợi dục", "赤裸": "trần như nhộng", 
    "赤身裸体": "cơ thể trần như nhộng", "一丝不挂": "không mảnh vải che thân", "情趣内衣": "đồ lót gợi dục", 
    "黑丝": "tất đen gợi cảm", "丝袜": "quần tất gợi dục", "丁字裤": "quần lót lọt khe", "内裤": "quần lót", "胸罩": "áo ngực",
    "性爱": "địt nhau", "勾引": "dụ dỗ", "诱惑": "mê hoặc gợi tình", "偷情": "vụng trộm địt nhau", "出轨": "cắm sừng ngoại tình",
    "绿帽": "cắm sừng", "戴绿帽": "bị cắm sừng", "骑乘": "tư thế cưỡi ngựa nhấp cặc", "后入": "địt từ phía sau",
    "上位": "nằm trên nhấp cặc", "女上位": "nữ cưỡi bên trên nhấp cặc", "体位": "tư thế địt nhau", "插进": "đâm sâu cặc vào lồn",
    "狠狠插": "địt cật lực", "猛插": "thúc mạnh cặc vào lồn", "拔出": "rút cặc ra", "抽送": "nhấp cặc liên tục",
    "挺腰": "thúc hông địt mạnh", "套弄": "tuốt cặc liên hồi", "舔吮": "liếm bú cặc", "吸吮": "bú cặc", "舔弄": "liếm lồn",
    "抓揉": "nắn bóp bầu vú", "摸到": "sờ nắn đến", "摸上": "sờ nắn lên", "脱掉": "cởi bỏ", "剥光": "lột sạch trần như nhộng",
    "浪荡": "lẳng lơ dâm đãng", "荡妇": "dâm phụ", "干得": "địt đến mức"
}

def get_zh_to_vn_map() -> Dict[str, str]:
    global _global_zh_to_vn_map
    if _global_zh_to_vn_map is None:
        _global_zh_to_vn_map = dict(DEFAULT_ZH_TO_VN_MAP)
        filepath = os.path.join(os.path.dirname(__file__), "..", "dictionary", "zh_to_vn_map.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    _global_zh_to_vn_map.update(json.load(f))
            except Exception as e:
                logger.error(f"Failed to load zh_to_vn_map.json in decoder: {e}")
    return _global_zh_to_vn_map

VN_UNCENSORED_UPGRADE_MAP = {
    # Hạ bộ nam
    "dương vật": "con cặc",
    "cự vật": "con cặc bự",
    "côn thịt": "con cặc",
    "nhục bổng": "buồi",
    "gậy thịt": "con cặc",
    "quy đầu": "quy đầu",
    "tinh hoàn": "hòn dái",
    "âm nang": "bìu dái",
    "bìu": "bìu dái",
    
    # Hạ bộ nữ & Vú
    "âm đạo": "lỗ lồn",
    "âm hộ": "lỗ lồn",
    "tiểu huyệt": "lỗ lồn",
    "hoa huyệt": "hoa huyệt",
    "mật huyệt": "lỗ lồn",
    "nộn huyệt": "lỗ lồn non",
    "khe lồn": "khe lồn",
    "nhũ hoa": "đầu vú",
    "núm ngực": "núm vú",
    "bồng đảo": "bầu vú",
    "nhũ phòng": "bầu vú",
    "bộ ngực": "bầu vú",
    "cặp ngực": "cặp vú",
    "âm vật": "hột le",
    "hạt đậu": "hột le",
    
    # Hành vi làm tình & ân ái
    "hoan ái": "làm tình",
    "giao hợp": "địt nhau",
    "làm tình": "làm tình",
    "quan hệ tình dục": "địt nhau",
    "giao cấu": "địt nhau",
    "chịch nhau": "chịch nhau",
    "nhấp đâm": "nhấp cặc liên tục",
    "đâm tiến vào": "đâm cặc vào lồn",
    "cắm vào": "cắm buồi vào lồn",
    "đút vào": "đút cặc vào lồn",
    "bắn tinh": "bắn tinh",
    "trào xuy": "phun dâm dịch",
    "mút liếm": "bú liếm",
    "liếm": "liếm lồn",
    "mút": "bú cặc",
    "bú mút": "bú cặc",
    "ngậm mút": "ngậm cặc",
    "bới móc": "móc lồn",
    "mơn trớn": "sờ soạng",
    "nắn bóp": "nắn bóp bầu vú",
    
    # Dịch thể & Trạng thái
    "dâm thủy": "nước lồn",
    "mật dịch": "nước lồn",
    "dịch dâm": "nước lồn",
    "nước nhờn": "nước lồn",
    "rên rỉ": "rên la dâm dục",
    "kiều xuy": "thở dốc dâm mị",
    "thở dốc": "thở dốc dâm dục",
    "cao trào": "lên đỉnh",
    "thôi tình": "kích dục",
    "xuân dược": "thuốc kích dục",
}

def upgrade_vietnamese_sensitive_term(vi_text: str) -> str:
    """
    Nâng cấp từ ngữ sắc văn 18+ mượt mà (chỉ kích hoạt cho luồng CONVERT CONTEXTT).
    """
    if not vi_text:
        return vi_text or ""
    try:
        from app.services.unblock.preprocessor.erotic_dictionary import upgrade_erotic_phrase
        return upgrade_erotic_phrase(vi_text)
    except Exception:
        return vi_text


def deduplicate_sensitive_terms(text: str) -> str:
    """
    Dọn dẹp khoảng trắng trước dấu câu và xóa 100% các từ/cụm từ bị lặp lại đứng liền kề nhau
    (VD: 'cơ thể cơ thể' -> 'cơ thể', 'chịch nhau chịch nhau' -> 'chịch nhau', 'lồn lồn' -> 'lồn').
    """
    if not text:
        return text

    # Dọn dẹp rác khoảng trắng xung quanh dấu câu
    cleaned = re.sub(r" {2,}", " ", text)
    cleaned = re.sub(r"\s+([.,!?:;])", r"\1", cleaned)

    # 1. Tự động xóa các từ đơn trùng lặp đứng cạnh nhau (Unicode boundary)
    vn_char = r'[a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF]'
    cleaned = re.sub(rf'(?<!{vn_char})({vn_char}+)\s+\1(?!{vn_char})', r'\1', cleaned, flags=re.IGNORECASE)

    # 2. Xóa từ thô tục/nhạy cảm lặp lại
    dup_vulgar = ["chịch", "lồn", "cặc", "đụ", "bú", "xoạc", "phịch", "bím", "cu", "dâm ô", "hiếp dâm", "rên rỉ", "thở dốc"]
    for w in dup_vulgar:
        pattern = r"(?<![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])(" + re.escape(w) + r")(?:\s+\1)+(?![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])"
        cleaned = re.sub(pattern, r"\1", cleaned, flags=re.IGNORECASE)

    return cleaned



class PlaceholderDecoder:
    @staticmethod
    def harmonize_pronouns(orig_text: str, context_text: str) -> str:
        # Trả về nguyên bản từ xưng hô mượt mà của LLM, không ép buộc thay đổi đại từ
        return orig_text or ""

    @staticmethod
    def decode(text: str, mapping_table: Dict[str, Dict[str, str]], highlight: bool = False, is_draft_only: bool = False) -> str:
        """
        Giải mã và khôi phục các token §PREFIX_XXXX§:
        - NẾU DỊCH GỐC (is_draft_only = False): Khôi phục về NGUYÊN BẢN HÁN-VIỆT TỰ NHIÊN, sát nghĩa nguyên tác.
        - NẾU DỊCH THÔ (is_draft_only = True): Nâng cấp các từ nhạy cảm Tiếng Việt sang ngôn từ 18+ THÔ TỤC HƠN, ĐÚNG NGHĨA NHẤT SO VỚI GỐC.
        """
        if not text or not mapping_table:
            return text or ""

        zh_map = get_zh_to_vn_map()
        from app.services.preprocessing.dichhan.hanviet_data import build_hanviet_name

        restored_text = text
        for token, data in mapping_table.items():
            clean_token = token.strip("§[]⟦⟧")
            parts = clean_token.split("_")
            flex_clean = r"[\s_-]*".join([re.escape(p) for p in parts])
            token_pattern = r"(?:§|{|\[|⟦|\()?[\s_-]*" + flex_clean + r"[\s_-]*(?:§|}|\]|⟧|\))?"
            
            matched_pattern = None
            if re.search(token_pattern, restored_text, re.IGNORECASE):
                matched_pattern = token_pattern
            elif len(parts) == 2 and len(parts[1]) >= 3 and re.search(rf"(?i)\b{re.escape(parts[1])}\b", restored_text):
                matched_pattern = rf"(?i)\b{re.escape(parts[1])}\b"

            if matched_pattern:

                orig_term = data.get("text", "")
                is_chinese = bool(re.search(r"[\u4e00-\u9fff]", orig_term))
                
                if is_chinese:
                    # Dịch Gốc: Tra cứu zh_to_vn_map nguyên bản / Hán-Việt mượt mà tự nhiên
                    target_replacement = zh_map.get(orig_term) or zh_map.get(orig_term.lower())
                    if not target_replacement:
                        sorted_zh_keys = sorted(zh_map.keys(), key=lambda x: len(x), reverse=True)
                        translated_parts = orig_term
                        for zh_key in sorted_zh_keys:
                            if zh_key in translated_parts:
                                vn_val = zh_map[zh_key]
                                translated_parts = translated_parts.replace(zh_key, f" {vn_val} ")

                        if re.search(r"[\u4e00-\u9fff]", translated_parts):
                            translated_parts = build_hanviet_name(translated_parts) or translated_parts

                        target_replacement = re.sub(r"\s+", " ", translated_parts).strip()
                else:
                    # Trả lại từ nhạy cảm Tiếng Việt (chuyển đổi đụ -> địt theo yêu cầu phong cách)
                    target_replacement = PlaceholderDecoder.harmonize_pronouns(orig_term, restored_text)
                    if target_replacement:
                        target_replacement = re.sub(r'(?i)\bđụ\b', lambda m: 'Địt' if m.group(0)[0].isupper() else 'địt', target_replacement)

                if highlight:
                    replacement = f'<span class="unblock-sensitive" title="Đã khôi phục: {orig_term} → {target_replacement}">{target_replacement}</span>'
                else:
                    replacement = target_replacement
                    
                restored_text = re.sub(matched_pattern, replacement, restored_text, flags=re.IGNORECASE)

        # Bảo đảm 100% tất cả token trong mapping_table nếu còn sót dạng nguyên thể §...§ hoặc biến thể đều được giải mã về từ gốc
        for token, data in mapping_table.items():
            orig_term = data.get("text", "")
            is_chinese = bool(re.search(r"[\u4e00-\u9fff]", orig_term))
            if is_chinese:
                target_rep = zh_map.get(orig_term) or zh_map.get(orig_term.lower())
                if not target_rep:
                    sorted_zh_keys = sorted(zh_map.keys(), key=lambda x: len(x), reverse=True)
                    translated_parts = orig_term
                    for zh_key in sorted_zh_keys:
                        if zh_key in translated_parts:
                            vn_val = zh_map[zh_key]
                            translated_parts = translated_parts.replace(zh_key, f" {vn_val} ")
                    if re.search(r"[\u4e00-\u9fff]", translated_parts):
                        translated_parts = build_hanviet_name(translated_parts) or translated_parts
                    target_rep = re.sub(r"\s+", " ", translated_parts).strip()
            else:
                target_rep = re.sub(r'(?i)\bđụ\b', lambda m: 'Địt' if m.group(0)[0].isupper() else 'địt', orig_term)
            
            # 1. Thay thế trực tiếp token chính xác
            if token in restored_text:
                restored_text = restored_text.replace(token, target_rep)
            
            # 2. Thay thế biến thể token (ví dụ: §BDY_244C§, [BDY_244C], BDY_244C)
            clean_tok = token.strip("§[]⟦⟧")
            tok_parts = clean_tok.split("_")
            tok_flex = r"[\s_-]*".join([re.escape(p) for p in tok_parts])
            tok_pattern = r"(?:§|{|\[|⟦|\()?[\s_-]*" + tok_flex + r"[\s_-]*(?:§|}|\]|⟧|\))?"
            restored_text = re.sub(tok_pattern, target_rep, restored_text, flags=re.IGNORECASE)

        # 3. Quét sạch bất kỳ mã §...§ mồ côi nào còn sót lại trên toàn văn bản
        restored_text = re.sub(r'§[A-Z]+_[A-Z0-9]+§', '', restored_text)
        restored_text = re.sub(r'⟪TAG_MASK_[A-Z0-9]+⟫', '', restored_text)

        restored_text = re.sub(r" {2,}", " ", restored_text)

        # Dọn dẹp rác lặp từ nhạy cảm 2-3 lần & sửa khoảng cách từ bị rách
        restored_text = deduplicate_sensitive_terms(restored_text)
        return restored_text

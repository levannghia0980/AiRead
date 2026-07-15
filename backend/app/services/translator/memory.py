import re
from typing import List, Dict, Any
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Chapter, Glossary

def build_glossary_prompt(raw_text: str, glossaries: List[Glossary]) -> str:
    """
    Scans the Chinese raw text for active glossary terms and formats them
    into a structured string for inclusion in the translation prompt.
    """
    if not raw_text or not glossaries:
        return ""
        
    matched_terms = []
    # Deduplicate terms and sort by length descending to match longest terms first (prevents partial matches)
    sorted_glossaries = sorted(glossaries, key=lambda x: len(x.chinese_term), reverse=True)
    
    seen_chinese = set()
    for g in sorted_glossaries:
        if not g.is_active:
            continue
        if g.chinese_term in seen_chinese:
            continue
            
        # Check if the term exists in raw_text
        if g.chinese_term in raw_text:
            seen_chinese.add(g.chinese_term)
            matched_terms.append(f"- {g.chinese_term} => {g.vietnamese_term} ({g.category})")
            
    if not matched_terms:
        return ""
        
    prompt_snippet = "\n[THUẬT NGỮ & TÊN RIÊNG BẮT BUỘC SỬ DỤNG]\n"
    prompt_snippet += "Dưới đây là danh sách thuật ngữ và tên nhân vật đã được chuẩn hóa. Bạn BẮT BUỘC phải dịch các từ này đúng như từ gợi ý:\n"
    prompt_snippet += "\n".join(matched_terms)
    prompt_snippet += "\n====================\n"
    return prompt_snippet

async def get_previous_chapters_context(
    db: AsyncSession, 
    novel_id: int, 
    chapter_no: int, 
    context_limit: int = 2,
    char_limit: int = 1500
) -> str:
    """
    Fetches the translated text of N previous chapters (up to context_limit)
    and formats them to provide context for the current chapter's translation.
    """
    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .where(Chapter.chapter_no < chapter_no)
        .where(Chapter.status == "COMPLETED")
        .order_by(Chapter.chapter_no.desc())
        .limit(context_limit)
    )
    result = await db.execute(stmt)
    prev_chapters = result.scalars().all()
    
    # Reverse so they appear chronologically: (N-2) then (N-1)
    prev_chapters = list(reversed(prev_chapters))
    
    if not prev_chapters:
        return ""
        
    context_snippet = "\n[NGỮ CẢNH CÁC CHƯƠNG TRƯỚC (Để tham khảo cách xưng hô và mạch truyện)]\n"
    for ch in prev_chapters:
        text = ch.translated_text or ""
        # Get the tail end of the chapter to keep context concise yet relevant
        if len(text) > char_limit:
            text = "..." + text[-char_limit:]
            
        context_snippet += f"--- Chương {ch.chapter_no}: {ch.title} (Bản dịch tiếng Việt) ---\n"
        context_snippet += f"{text}\n\n"
        
    context_snippet += "====================\n"
    return context_snippet

def create_system_instruction(custom_prompt: str = "") -> str:
    """
    Constructs the core system instruction instructing the AI on the translation requirements.
    """
    default_prompt = (
        "Bạn là một biên tập viên dịch thuật truyện chữ Trung-Việt chuyên nghiệp.\n"
        "Nhiệm vụ của bạn là dịch văn bản chương truyện Trung Quốc được cung cấp sang tiếng Việt.\n\n"
        "Yêu cầu chất lượng:\n"
        "- Dịch tự nhiên, thuần Việt, mượt mà, thoát ý, không dịch word-by-word.\n"
        "- Tuyệt đối không giữ nguyên cấu trúc câu chữ Trung Quốc rườm rà (văn phong convert).\n"
        "- Chuyển ngữ các đại từ nhân xưng linh hoạt và hợp lý dựa theo mối quan hệ (hắn, nàng, ông ta, cậu, cô, ngươi, ta, sư phụ, đệ tử...).\n"
        "- Sử dụng các từ Hán-Việt phổ thông và dễ hiểu trong thể loại truyện chữ (tiên hiệp, huyền huyễn, đô thị...).\n"
        "- Không tự ý thêm bớt nội dung cốt truyện hoặc chèn bình luận của người dịch vào văn bản.\n"
        "- Giữ nguyên các dấu câu và cách xuống dòng hội thoại tự nhiên của tác phẩm gốc.\n"
    )
    
    if custom_prompt:
        return f"{default_prompt}\n[YÊU CẦU BỔ SUNG TỪ NGƯỜI DÙNG]:\n{custom_prompt}"
    return default_prompt

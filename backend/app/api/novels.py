from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import io
import re
from urllib.parse import quote
import os
import hashlib
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import Novel, Chapter, Glossary, TranslationCache
from app.services.crawler.engine import scrape_novel_metadata

router = APIRouter(prefix="/api/novels", tags=["Novels"])

# Regex phát hiện chữ Hán còn sót trong bản dịch
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

class AnalyzeRequest(BaseModel):
    url: str

class GlossaryCreate(BaseModel):
    chinese_term: str
    vietnamese_term: str
    category: str = "NAME"

class SaveChapterSchema(BaseModel):
    chapter_no: int
    title: str
    url: str

class SaveNovelRequest(BaseModel):
    title: str
    author: Optional[str] = "Khuyết Danh"
    cover_url: Optional[str] = ""
    source_url: str
    genres: Optional[str] = ""
    status: Optional[str] = "Ongoing"
    chapters: List[SaveChapterSchema]

class ResetChaptersRequest(BaseModel):
    chapter_nos: Optional[List[int]] = None

@router.post("/analyze")
async def analyze_url(payload: AnalyzeRequest):
    """Scrapes novel meta details and lists of chapters from given URL."""
    if not payload.url:
        raise HTTPException(status_code=400, detail="Thiếu đường dẫn URL truyện")
    try:
        data = await scrape_novel_metadata(payload.url)
        return data
    except Exception as e:
        import traceback
        # Ghi log chi tiết lỗi ra file để debug
        log_file = r"d:\NENGHIA0980\AiRead2\error.log"
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích URL: {str(e)}")

@router.get("")
async def list_novels(db: AsyncSession = Depends(get_db)):
    """Retrieves all registered novels from the database."""
    stmt = select(Novel).order_by(Novel.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/save")
async def save_novel(payload: SaveNovelRequest, db: AsyncSession = Depends(get_db)):
    """Saves novel metadata and all chapters to database, facilitating resume operations."""
    # Check if already exists
    stmt = select(Novel).where(Novel.source_url == payload.source_url)
    result = await db.execute(stmt)
    existing_novel = result.scalar_one_or_none()
    
    if existing_novel:
        return {"novel_id": existing_novel.id, "message": "Truyện đã tồn tại sẵn trong hệ thống."}

    # Save new novel
    new_novel = Novel(
        title=payload.title,
        author=payload.author,
        cover_url=payload.cover_url,
        source_url=payload.source_url,
        genres=payload.genres,
        status=payload.status
    )
    db.add(new_novel)
    await db.flush() # populate ID

    # Batch save chapters
    db_chapters = [
        Chapter(
            novel_id=new_novel.id,
            chapter_no=ch.chapter_no,
            title=ch.title,
            source_url=ch.url,
            status="PENDING"
        )
        for ch in payload.chapters
    ]
    db.add_all(db_chapters)
    await db.commit()

    return {"novel_id": new_novel.id, "message": "Đã lưu truyện vào database thành công."}

@router.get("/{novel_id}")
async def get_novel_details(novel_id: int, db: AsyncSession = Depends(get_db)):
    """Gets novel metadata and its list of chapters."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=444, detail="Không tìm thấy bộ truyện")
        
    stmt = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
    result = await db.execute(stmt)
    chapters = result.scalars().all()
    
    return {
        "novel": novel,
        "chapters": chapters
    }

@router.delete("/{novel_id}")
async def delete_novel(novel_id: int, db: AsyncSession = Depends(get_db)):
    """Deletes novel and all its related chapters/glossaries."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ truyện")
        
    await db.delete(novel)
    await db.commit()
    return {"success": True, "message": f"Đã xóa thành công truyện {novel.title}"}

# Glossary endpoints
@router.get("/{novel_id}/glossary")
async def get_glossary(novel_id: int, db: AsyncSession = Depends(get_db)):
    """Gets all glossaries matching this novel (and global ones)."""
    # Fetch terms for this novel or global (novel_id is null)
    stmt = select(Glossary).where((Glossary.novel_id == novel_id) | (Glossary.novel_id == None))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{novel_id}/glossary")
async def add_glossary_term(novel_id: int, payload: GlossaryCreate, db: AsyncSession = Depends(get_db)):
    """Adds a glossary item to the novel (or global if novel_id is 0)."""
    target_novel_id = None if novel_id == 0 else novel_id
    
    # Check if duplicate exists
    stmt = select(Glossary).where(
        Glossary.novel_id == target_novel_id,
        Glossary.chinese_term == payload.chinese_term
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.vietnamese_term = payload.vietnamese_term
        existing.category = payload.category
    else:
        new_term = Glossary(
            novel_id=target_novel_id,
            chinese_term=payload.chinese_term,
            vietnamese_term=payload.vietnamese_term,
            category=payload.category
        )
        db.add(new_term)
        
    await db.commit()
    return {"success": True}

@router.delete("/{novel_id}/glossary/{glossary_id}")
async def delete_glossary_term(novel_id: int, glossary_id: int, db: AsyncSession = Depends(get_db)):
    """Deletes glossary item by ID."""
    stmt = delete(Glossary).where(Glossary.id == glossary_id)
    await db.execute(stmt)
    await db.commit()
    return {"success": True}

@router.get("/{novel_id}/chapters/{chapter_no}/text")
async def get_chapter_text(novel_id: int, chapter_no: int, db: AsyncSession = Depends(get_db)):
    """Gets a single chapter's translated text for reading."""
    stmt = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_no == chapter_no
    )
    result = await db.execute(stmt)
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương")
    return {
        "chapter_no": chapter.chapter_no,
        "title": chapter.title,
        "status": chapter.status,
        "translated_text": chapter.translated_text or "",
        "raw_text": chapter.raw_text or ""
    }

@router.post("/{novel_id}/save-to-folder")
async def save_chapters_to_folder(novel_id: int, db: AsyncSession = Depends(get_db)):
    """Saves all translated chapters as individual .txt files in a folder named after the novel."""
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")
    
    # Create folder with novel title (Unicode-safe)
    invalid_chars = '<>:"/\\|?*\r\n\t'
    safe_title = "".join(c for c in novel.title if c not in invalid_chars).strip()
    safe_title = safe_title.replace("  ", " ")
    
    # Use project-level output directory
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    novel_folder = os.path.join(BASE_DIR, "output", safe_title)
    os.makedirs(novel_folder, exist_ok=True)
    
    # Fetch completed chapters
    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id, Chapter.status == "COMPLETED")
        .order_by(Chapter.chapter_no.asc())
    )
    result = await db.execute(stmt)
    chapters = list(result.scalars().all())
    
    if not chapters:
        raise HTTPException(status_code=400, detail="Chưa có chương nào được dịch xong.")
    
    saved_files = []
    for ch in chapters:
        # Create clean filename: "Chương 001 - Title.txt"
        ch_title = "".join(c for c in ch.title if c not in invalid_chars).strip()
        filename = f"Chương {ch.chapter_no:04d} - {ch_title}.txt"
        filepath = os.path.join(novel_folder, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{ch.title}\n")
            f.write("=" * 40 + "\n\n")
            f.write(ch.translated_text or "")
        
        saved_files.append(filename)
    
    return {
        "success": True,
        "folder": safe_title,
        "folder_path": novel_folder,
        "total_files": len(saved_files),
        "files": saved_files
    }

@router.post("/{novel_id}/chapters/reset")
async def reset_chapters(novel_id: int, payload: ResetChaptersRequest, db: AsyncSession = Depends(get_db)):
    """Resets chapters back to PENDING status and clears text to allow rescraping/retranslation."""
    stmt = select(Chapter).where(Chapter.novel_id == novel_id)
    if payload.chapter_nos is not None:
        stmt = stmt.where(Chapter.chapter_no.in_(payload.chapter_nos))
        
    result = await db.execute(stmt)
    chapters = result.scalars().all()
    
    if not chapters:
        raise HTTPException(status_code=404, detail="Không tìm thấy chương để reset")
        
    for ch in chapters:
        # Clear Translation Cache for this chapter's chunks if raw_text exists
        if ch.raw_text:
            try:
                # Dọn dẹp cache cho cả hai cấu hình chunk 4000 và 8000
                for limit in [4000, 8000]:
                    paragraphs = [p.strip() for p in ch.raw_text.split("\n") if p.strip()]
                    chunks = []
                    current_chunk = []
                    current_len = 0
                    for p in paragraphs:
                        p_len = len(p)
                        if current_len + p_len > limit and current_chunk:
                            if p.startswith('"') and current_chunk[-1].startswith('"') and current_len + p_len < limit * 1.2:
                                current_chunk.append(p)
                                current_len += p_len + 2
                            else:
                                chunks.append("\n\n".join(current_chunk))
                                current_chunk = [p]
                                current_len = p_len
                        else:
                            current_chunk.append(p)
                            current_len += p_len + 2
                    if current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                    
                    # Delete cache entries
                    for chunk in chunks:
                        chunk_hash = hashlib.md5(chunk.encode("utf-8")).hexdigest()
                        await db.execute(
                            delete(TranslationCache).where(TranslationCache.key_hash == chunk_hash)
                        )
            except Exception:
                pass

        ch.status = "PENDING"
        ch.raw_text = None
        ch.translated_text = None
        ch.error_msg = None
        
    # Also delete physical files for these chapters if they exist in the output folder
    novel = await db.get(Novel, novel_id)
    if novel:
        invalid_chars = '<>:"/\\|?*\r\n\t'
        safe_title = "".join(c for c in novel.title if c not in invalid_chars).strip()
        safe_title = safe_title.replace("  ", " ")
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        novel_folder = os.path.join(BASE_DIR, "output", safe_title)
        
        for ch in chapters:
            ch_title = "".join(c for c in ch.title if c not in invalid_chars).strip()
            filename = f"Chương {ch.chapter_no:04d} - {ch_title}.txt"
            filepath = os.path.join(novel_folder, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                    
    await db.commit()
    return {"success": True, "message": f"Đã reset {len(chapters)} chương về trạng thái chờ dịch."}


# ===========================================================================
# KIỂM TRA CHẤT LƯỢNG DỊCH (NHANH — CHỈ DÙNG CODE, KHÔNG GỌI AI)
# ===========================================================================

@router.get("/{novel_id}/check-quality")
async def check_translation_quality(novel_id: int, db: AsyncSession = Depends(get_db)):
    """
    Quét nhanh tất cả chương đã dịch và phát hiện các lỗi phổ biến:
    - Còn chữ Hán (chữ Trung) trong bản dịch
    - Bản dịch rỗng hoặc quá ngắn so với bản gốc (ratio < 0.3)
    - Chương FAILED chưa được dịch lại
    
    Trả về danh sách chương bị lỗi cùng mô tả lỗi.
    """
    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_no.asc())
    )
    result = await db.execute(stmt)
    chapters = result.scalars().all()

    bad_chapters = []

    for ch in chapters:
        issues = []

        # 1. Chương FAILED chưa được dịch lại
        if ch.status == "FAILED":
            issues.append(f"Lỗi dịch: {ch.error_msg or 'Không rõ nguyên nhân'}")

        # 2. Chương COMPLETED nhưng bản dịch bị vấn đề
        if ch.status == "COMPLETED":
            translated = ch.translated_text or ""

            # 2a. Bản dịch rỗng
            if not translated.strip():
                issues.append("Bản dịch rỗng (không có nội dung)")

            else:
                # 2b. Còn chữ Hán trong bản dịch
                chinese_matches = _CHINESE_RE.findall(translated)
                if chinese_matches:
                    sample = "".join(chinese_matches[:20])
                    issues.append(f"Còn {len(chinese_matches)} chữ Hán trong bản dịch (VD: {sample})")

                # 2c. Tỷ lệ độ dài quá thấp (dịch thiếu nội dung)
                raw = ch.raw_text or ""
                if raw.strip() and len(raw) > 100:
                    ratio = len(translated) / len(raw)
                    if ratio < 0.3:
                        issues.append(f"Dịch thiếu nội dung: bản dịch chỉ bằng {ratio:.0%} bản gốc")

        if issues:
            bad_chapters.append({
                "chapter_no": ch.chapter_no,
                "title": ch.title,
                "status": ch.status,
                "issues": issues,
            })

    return {
        "total_chapters": len(chapters),
        "bad_count": len(bad_chapters),
        "bad_chapters": bad_chapters,
    }


# ===========================================================================
# TẢI FILE GỘP (TXT HOẶC DOCX)
# ===========================================================================

@router.get("/{novel_id}/download")
async def download_novel(
    novel_id: int,
    fmt: str = Query("txt", description="Định dạng xuất: 'txt' hoặc 'docx'"),
    db: AsyncSession = Depends(get_db)
):
    """
    Gộp toàn bộ chương đã dịch thành một file duy nhất.
    Mỗi chương bắt đầu bằng tên chương, nội dung tuần tự từ chương 1 đến hết.
    Hỗ trợ định dạng: txt, docx
    """
    novel = await db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Không tìm thấy truyện")

    stmt = (
        select(Chapter)
        .where(Chapter.novel_id == novel_id, Chapter.status == "COMPLETED")
        .order_by(Chapter.chapter_no.asc())
    )
    result = await db.execute(stmt)
    chapters = list(result.scalars().all())

    if not chapters:
        raise HTTPException(status_code=400, detail="Chưa có chương nào được dịch xong.")

    # Tên file an toàn
    invalid_chars = '<>:"/\\|?*\r\n\t'
    safe_title = "".join(c for c in novel.title if c not in invalid_chars).strip()
    safe_title = safe_title.replace("  ", " ") or "novel"

    fmt = fmt.lower().strip()

    # ── TXT ──────────────────────────────────────────────────────────────────
    if fmt == "txt":
        lines = []
        lines.append(novel.title)
        lines.append(f"Tác giả: {novel.author or 'Khuyết Danh'}")
        lines.append("=" * 60)
        lines.append("")

        for ch in chapters:
            lines.append(ch.title)
            lines.append("-" * 40)
            lines.append(ch.translated_text or "")
            lines.append("")
            lines.append("")

        content = "\n".join(lines)
        buf = io.BytesIO(content.encode("utf-8"))
        buf.seek(0)
        filename = f"{safe_title}.txt"
        # RFC 5987: fallback ASCII + UTF-8 encoded filename for non-ASCII chars
        ascii_fallback = "novel.txt"
        encoded_name = quote(filename)

        return StreamingResponse(
            buf,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_name}"}
        )

    # ── DOCX ─────────────────────────────────────────────────────────────────
    elif fmt == "docx":
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Thư viện python-docx chưa được cài. Chạy: pip install python-docx"
            )

        doc = Document()

        # Tiêu đề truyện
        title_para = doc.add_heading(novel.title, level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        author_para = doc.add_paragraph(f"Tác giả: {novel.author or 'Khuyết Danh'}")
        author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("")

        for ch in chapters:
            # Tên chương — Heading 1
            doc.add_heading(ch.title, level=1)

            # Nội dung chương — chia theo dòng để giữ định dạng đoạn
            text = ch.translated_text or ""
            for para_text in text.split("\n"):
                if para_text.strip():
                    doc.add_paragraph(para_text.strip())

            doc.add_paragraph("")  # Khoảng cách giữa các chương

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        filename = f"{safe_title}.docx"
        ascii_fallback = "novel.docx"
        encoded_name = quote(filename)

        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_name}"}
        )

    else:
        raise HTTPException(status_code=400, detail=f"Định dạng không hỗ trợ: {fmt}. Dùng 'txt' hoặc 'docx'.")

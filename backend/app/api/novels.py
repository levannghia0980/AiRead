from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
import hashlib
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.models import Novel, Chapter, Glossary, TranslationCache
from app.services.crawler.engine import scrape_novel_metadata

router = APIRouter(prefix="/api/novels", tags=["Novels"])

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

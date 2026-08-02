from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import ChapterVersion
from app.services.storage.file_storage import read_version_file_content
from app.services.preprocessing.crawler.pipeline import (
    process_novel_link, 
    process_single_chapter_crawl,
    delete_novel_completely,
    delete_novel_version
)

router = APIRouter(prefix="/crawler", tags=["Crawler & Version Management"])

class CrawlNovelRequest(BaseModel):
    url: str

class CrawlChapterRequest(BaseModel):
    novel_id: int
    start_no: Optional[int] = 0
    end_no: Optional[int] = 0

@router.post("/parse-novel")
async def parse_and_store_novel(payload: CrawlNovelRequest):
    """
    Cào link truyện (Mục Lục), khởi tạo bản ghi Novel & Chapter (status = 'WAIT') trong DB.
    """
    try:
        res = await process_novel_link(payload.url)
        return {
            "status": "success",
            "message": f"Đã lưu danh sách chương vào DB cho bộ truyện '{res['title_rough']}'",
            "data": res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cào mục lục truyện: {str(e)}")

@router.post("/crawl-chapter")
async def crawl_chapter_in_range(payload: CrawlChapterRequest):
    """
    Tìm chương có số thứ tự nhỏ nhất (chapter_no thấp nhất) trong khoảng [start_no, end_no] 
    của bộ truyện novel_id mà chưa được cào (status != 'CRAWLED'), sau đó tiến hành cào.
    Nếu start_no và end_no = 0 hoặc rỗng thì cào từ đầu đến cuối.
    Nếu toàn bộ đã cào xong, trả về status: "completed".
    """
    from app.models.schema import Chapter
    
    async with AsyncSessionLocal() as session:
        # Tìm chương có chapter_no thấp nhất mà chưa cào xong (chờ cào hoặc lỗi)
        stmt = (
            select(Chapter)
            .where(
                Chapter.novel_id == payload.novel_id,
                Chapter.status != "CRAWLED"
            )
        )
        
        if payload.start_no and payload.start_no > 0:
            stmt = stmt.where(Chapter.chapter_no >= payload.start_no)
        if payload.end_no and payload.end_no > 0:
            stmt = stmt.where(Chapter.chapter_no <= payload.end_no)
            
        stmt = stmt.order_by(Chapter.chapter_no.asc()).limit(1)
        
        res_ch = await session.execute(stmt)
        chapter = res_ch.scalar_one_or_none()
        
        if not chapter:
            return {
                "status": "completed",
                "message": "Tất cả các chương trong khoảng quy định đã được cào thành công.",
                "chapter_id": None
            }
            
        chapter_id = chapter.id
        chapter_no = chapter.chapter_no

    try:
        # Tiến hành cào chương này
        res = await process_single_chapter_crawl(chapter_id)
        return {
            "status": "success",
            "message": f"Đã tự động cào chương {res['chapter_no']} (chương thấp nhất còn thiếu trong khoảng).",
            "data": res
        }
    except Exception as e:
        if "Không tìm thấy" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi cào chương ID {chapter_id} (Số chương {chapter_no}): {str(e)}"
        )

@router.get("/chapter/{chapter_id}/version/{version_type}")
async def get_chapter_version_content(
    chapter_id: int = Path(..., description="ID chương"),
    version_type: str = Path(..., description="Loại phiên bản: 'RAW', 'GG', 'LLM', 'FINAL', 'AUDIO'")
):
    """
    Đọc trực tiếp nội dung văn bản từ đĩa cứng theo trỏ chỉ mục trong DB (RAW, GG, LLM, FINAL)
    """
    v_type = version_type.upper()
    async with AsyncSessionLocal() as session:
        stmt = select(ChapterVersion).where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.version_type == v_type
        )
        res = await session.execute(stmt)
        ver = res.scalar_one_or_none()

        if not ver:
            raise HTTPException(status_code=404, detail=f"Chưa có phiên bản '{v_type}' cho chương ID {chapter_id}")

        file_path = ver.file_path

    try:
        content = read_version_file_content(file_path)
        return {
            "chapter_id": chapter_id,
            "version_type": v_type,
            "file_path": file_path,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file từ đĩa: {str(e)}")

@router.delete("/novel/{novel_id}")
async def delete_novel(novel_id: int = Path(..., description="ID bộ truyện cần xóa hoàn toàn")):
    """
    Xóa sạch bộ truyện khỏi Database và xóa toàn bộ tất cả thư mục file đĩa trên máy.
    """
    try:
        res = await delete_novel_completely(novel_id)
        return {
            "status": "success",
            "message": res["message"],
            "data": res
        }
    except Exception as e:
        if "Không tìm thấy" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Lỗi xóa bộ truyện ID {novel_id}: {str(e)}")


@router.delete("/novel/{novel_id}/version/{version_type}")
async def delete_version(
    novel_id: int = Path(..., description="ID bộ truyện"),
    version_type: str = Path(..., description="Loại phiên bản cần xóa: 'GG', 'LLM', 'FINAL', 'AUDIO'")
):
    """
    Xóa riêng 1 phiên bản dịch (Ví dụ: Xóa riêng bản dịch 'GG' hoặc 'LLM' để dịch lại), giữ nguyên bản gốc RAW.
    """
    try:
        res = await delete_novel_version(novel_id, version_type)
        return {
            "status": "success",
            "message": res["message"],
            "data": res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa phiên bản '{version_type}' cho bộ truyện ID {novel_id}: {str(e)}")

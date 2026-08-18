from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select, delete, insert
from app.core.database import AsyncSessionLocal
from app.models.schema import PhraseDictionary, NamesDictionary
from app.services.preprocessing.dichhan.translator import clear_translator_caches

router = APIRouter(prefix="/dictionary", tags=["Dictionary Management"])

class PhraseItem(BaseModel):
    chinese_phrase: str
    vietnamese_phrase: str

class NameItem(BaseModel):
    chinese_name: str
    vietnamese_name: str
    novel_id: Optional[int] = None

@router.post("/phrase")
async def add_phrase(payload: PhraseItem):
    """Thêm cụm từ ghép vào từ điển dùng chung"""
    from app.services.unblock.unblock_pipeline import is_exact_sensitive_word
    from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese
    if await is_exact_sensitive_word(payload.chinese_phrase) or await is_exact_sensitive_word(payload.vietnamese_phrase):
        raise HTTPException(status_code=400, detail="Từ ngữ là từ khóa nhạy cảm trong danh sách Unblock, không thể thêm vào từ điển.")

    if payload.vietnamese_phrase:
        payload.vietnamese_phrase = sanitize_entity_vietnamese(payload.vietnamese_phrase, payload.chinese_phrase)

    async with AsyncSessionLocal() as session:
        stmt = select(PhraseDictionary).where(PhraseDictionary.chinese_phrase == payload.chinese_phrase)
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()

        if item:
            item.vietnamese_phrase = payload.vietnamese_phrase
        else:
            item = PhraseDictionary(
                chinese_phrase=payload.chinese_phrase,
                vietnamese_phrase=payload.vietnamese_phrase
            )
            session.add(item)
        await session.commit()
    
    # Xóa cache để cập nhật tức thì
    clear_translator_caches()
    return {"status": "success", "message": "Đã thêm/cập nhật từ ghép thành công."}

@router.post("/name")
async def add_name(payload: NameItem):
    """Thêm tên nhân vật hoặc thuật ngữ riêng (Novel-specific hoặc Global)"""
    from app.services.unblock.unblock_pipeline import is_exact_sensitive_word
    from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese
    if await is_exact_sensitive_word(payload.chinese_name) or await is_exact_sensitive_word(payload.vietnamese_name):
        raise HTTPException(status_code=400, detail="Tên hoặc từ dịch là từ khóa nhạy cảm trong danh sách Unblock, không thể thêm vào từ điển.")

    if payload.vietnamese_name:
        payload.vietnamese_name = sanitize_entity_vietnamese(payload.vietnamese_name, payload.chinese_name)

    async with AsyncSessionLocal() as session:
        stmt = select(NamesDictionary).where(
            NamesDictionary.chinese_name == payload.chinese_name,
            NamesDictionary.novel_id == payload.novel_id
        )
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()

        if item:
            item.vietnamese_name = payload.vietnamese_name
        else:
            item = NamesDictionary(
                novel_id=payload.novel_id,
                chinese_name=payload.chinese_name,
                vietnamese_name=payload.vietnamese_name
            )
            session.add(item)
        await session.commit()
    
    clear_translator_caches()
    return {"status": "success", "message": "Đã thêm/cập nhật tên nhân vật thành công."}

@router.delete("/phrase")
async def delete_phrase(chinese_phrase: str):
    """Xóa từ ghép khỏi từ điển"""
    async with AsyncSessionLocal() as session:
        stmt = delete(PhraseDictionary).where(PhraseDictionary.chinese_phrase == chinese_phrase)
        await session.execute(stmt)
        await session.commit()
    
    clear_translator_caches()
    return {"status": "success", "message": "Đã xóa từ ghép thành công."}

@router.delete("/name")
async def delete_name(chinese_name: str, novel_id: Optional[int] = None):
    """Xóa tên nhân vật khỏi từ điển"""
    async with AsyncSessionLocal() as session:
        stmt = delete(NamesDictionary).where(
            NamesDictionary.chinese_name == chinese_name,
            NamesDictionary.novel_id == novel_id
        )
        await session.execute(stmt)
        await session.commit()
    
    clear_translator_caches()
    return {"status": "success", "message": "Đã xóa tên nhân vật thành công."}

@router.post("/init-seeds")
async def init_seed_dictionaries():
    """Khởi tạo nhanh dữ liệu hạt giống (Seed phrases) để chạy thử nghiệm"""
    seeds = [
        ("掌握", "nắm giữ"),
        ("生活", "cuộc sống"),
        ("催眠", "thôi miên"),
        ("之力", "sức mạnh"),
        ("能力", "năng lực"),
        ("第一章", "Chương 1"),
        ("第二章", "Chương 2"),
        ("第三章", "Chương 3"),
    ]
    
    names_seeds = [
        ("萧炎", "Tiêu Viêm"),
        ("林动", "Lâm Động"),
        ("叶凡", "Diệp Phàm"),
        ("唐三", "Đường Tam"),
    ]
    
    async with AsyncSessionLocal() as session:
        for ch, vi in seeds:
            stmt = select(PhraseDictionary).where(PhraseDictionary.chinese_phrase == ch)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                session.add(PhraseDictionary(chinese_phrase=ch, vietnamese_phrase=vi))
                
        for ch_n, vi_n in names_seeds:
            stmt = select(NamesDictionary).where(
                NamesDictionary.chinese_name == ch_n,
                NamesDictionary.novel_id == None
            )
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                session.add(NamesDictionary(chinese_name=ch_n, vietnamese_name=vi_n, novel_id=None))
                
        await session.commit()
        
    clear_translator_caches()
    return {"status": "success", "message": "Khởi tạo từ điển hạt giống thành công."}

class ProcessChapterEntitiesRequest(BaseModel):
    novel_id: int
    chapter_id: Optional[int] = None
    chapter_ids: Optional[List[int]] = None

@router.post("/process-chapter-entities")
async def process_chapter_entities(payload: ProcessChapterEntitiesRequest):
    """
    Tiền xử lý bóc tách thực thể & gom lỗi GG tự động.
    Hỗ trợ cả trích xuất 1 chương lẻ (chapter_id) hoặc lô nhiều chương (chapter_ids).
    Điều hướng trực tiếp sang _process_evidence_and_save để đảm bảo 100% đồng bộ CSDL.
    """
    try:
        from app.models.schema import Chapter
        from app.services.translation.pipeline import _process_evidence_and_save

        batch_ids = []
        if payload.chapter_ids:
            batch_ids = payload.chapter_ids
        elif payload.chapter_id:
            async with AsyncSessionLocal() as session:
                stmt_ch = select(Chapter.id).where(
                    Chapter.novel_id == payload.novel_id,
                    (Chapter.id == payload.chapter_id) | (Chapter.chapter_no == payload.chapter_id)
                )
                res_ch = await session.execute(stmt_ch)
                found_id = res_ch.scalar_one_or_none()
                if found_id:
                    batch_ids = [found_id]
                else:
                    batch_ids = [payload.chapter_id]
        else:
            raise HTTPException(status_code=400, detail="Thiếu chapter_id hoặc chapter_ids.")

        await _process_evidence_and_save(
            novel_id=payload.novel_id,
            batch=batch_ids,
            enable_llm_extract=True,
            enable_names_dict=True,
            enable_gg_corrections=True
        )

        return {
            "status": "success",
            "message": f"Đã hoàn tất bóc tách thực thể & gom lỗi cho batch {batch_ids}."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/chapter/{chapter_id}/clean-gg")
async def get_sanitized_google_translation(chapter_id: int):
    """
    Lấy ra nội dung bản dịch Google đã được làm sạch và thay thế thực thể đúng chuẩn.
    """
    import os
    try:
        from app.models.schema import ChapterVersion
        async with AsyncSessionLocal() as session:
            stmt = select(ChapterVersion).where(
                ChapterVersion.chapter_id == chapter_id,
                ChapterVersion.version_type == "GG"
            )
            res = await session.execute(stmt)
            ver = res.scalar_one_or_none()
            if not ver:
                raise Exception("Chương này chưa có bản dịch Google Translate.")
            file_path = ver.file_path

        if not os.path.exists(file_path):
            raise Exception("Không tìm thấy file bản dịch Google trên đĩa cứng.")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            clean_text = f.read()

        return {"status": "success", "content": clean_text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

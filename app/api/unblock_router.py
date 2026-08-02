from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict
from sqlalchemy import select, delete, func
from app.core.database import AsyncSessionLocal
from app.models.schema import UnblockDictionary, Setting
from app.services.unblock.unblock_pipeline import (
    mask_text_with_dictionary,
    unmask_text_with_dictionary,
    clear_unblock_trie_cache
)

router = APIRouter(prefix="/unblock", tags=["Unblock & Sensitive Words"])

class ToggleUnblockPayload(BaseModel):
    enabled: bool

class AddWordPayload(BaseModel):
    word: str
    category: Optional[str] = "scene"

class TestMaskPayload(BaseModel):
    text: str
    aggressive: Optional[bool] = True

class TestUnmaskPayload(BaseModel):
    translated_text: str
    mapping_table: Dict[str, Dict[str, str]]
    highlight: Optional[bool] = False

@router.get("/status")
async def get_unblock_status():
    """
    Trạng thái tính năng Unblock bảo vệ an toàn (Khóa mặc định luôn BẬT).
    """
    async with AsyncSessionLocal() as session:
        stmt_count = select(func.count(UnblockDictionary.id))
        res_count = await session.execute(stmt_count)
        total_words = res_count.scalar() or 0

    return {
        "enabled": True,
        "total_words": total_words
    }

@router.post("/toggle")
async def toggle_unblock(payload: ToggleUnblockPayload):
    """
    Bảo vệ an toàn LLM - Tính năng Unblock được bật cố định 24/7.
    """
    async with AsyncSessionLocal() as session:
        key = "AIREAD_UNBLOCK_ENABLED"
        stmt = select(Setting).where(Setting.key == key)
        res = await session.execute(stmt)
        setting_row = res.scalar_one_or_none()
        
        if setting_row:
            setting_row.value = "true"
        else:
            session.add(Setting(key=key, value="true"))
        await session.commit()

    return {
        "status": "success",
        "message": "Tính năng Unblock giấu từ nhạy cảm bảo vệ LLM đã được BẬT cố định 24/7.",
        "enabled": True
    }

@router.get("/words")
async def list_unblock_words(
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Danh sách từ nhạy cảm có trong cơ sở dữ liệu.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(UnblockDictionary)
        if query:
            stmt = stmt.where(UnblockDictionary.word.like(f"%{query}%"))
        if category:
            stmt = stmt.where(UnblockDictionary.category == category)
        stmt = stmt.limit(limit).offset(offset)
        res = await session.execute(stmt)
        rows = res.scalars().all()

        words = [
            {"id": r.id, "word": r.word, "category": r.category}
            for r in rows
        ]
        return {"words": words, "count": len(words)}

@router.post("/words")
async def add_unblock_word(payload: AddWordPayload):
    """
    Thêm từ nhạy cảm mới vào từ điển DB.
    """
    word_clean = payload.word.strip()
    if not word_clean:
        raise HTTPException(status_code=400, detail="Từ nhạy cảm không được để trống.")

    async with AsyncSessionLocal() as session:
        stmt = select(UnblockDictionary).where(UnblockDictionary.word == word_clean)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Từ '{word_clean}' đã tồn tại trong từ điển.")

        new_item = UnblockDictionary(word=word_clean, category=payload.category)
        session.add(new_item)
        await session.commit()
        await session.refresh(new_item)

    # Xóa cache Trie để nạp lại
    clear_unblock_trie_cache()

    return {
        "status": "success",
        "message": f"Đã thêm từ '{word_clean}' vào danh sách Unblock.",
        "data": {"id": new_item.id, "word": new_item.word, "category": new_item.category}
    }

@router.delete("/words/{word_id}")
async def delete_unblock_word(word_id: int):
    """
    Xóa một từ khỏi danh sách Unblock.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(UnblockDictionary).where(UnblockDictionary.id == word_id)
        res = await session.execute(stmt)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Không tìm thấy từ với ID tương ứng.")

        word = item.word
        await session.delete(item)
        await session.commit()

    # Xóa cache Trie để nạp lại
    clear_unblock_trie_cache()

    return {
        "status": "success",
        "message": f"Đã xóa từ '{word}' (ID: {word_id}) khỏi từ điển."
    }

@router.post("/test-mask")
async def test_mask(payload: TestMaskPayload):
    """
    Thử nghiệm chức năng giấu từ (Mask) với một đoạn văn bản.
    """
    masked_text, mapping_table, is_masked = await mask_text_with_dictionary(
        payload.text,
        mask_level="word",
        aggressive=payload.aggressive
    )
    return {
        "original_text": payload.text,
        "masked_text": masked_text,
        "is_masked": is_masked,
        "mapping_table": mapping_table
    }

@router.post("/test-unmask")
async def test_unmask(payload: TestUnmaskPayload):
    """
    Thử nghiệm chức năng giải mã (Unmask) trả về văn bản ban đầu.
    """
    final_text = unmask_text_with_dictionary(
        payload.translated_text,
        payload.mapping_table,
        highlight=payload.highlight
    )
    return {
        "translated_text": payload.translated_text,
        "unmasked_text": final_text
    }

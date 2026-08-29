import os
import re
import shutil
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, case
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion, NovelEntity
from app.services.postprocessing.post_processor import export_full_novel_txt
from app.services.storage.file_storage import sanitize_filename

router = APIRouter(prefix="/novels", tags=["Novels & Chapters Management"])

class UpdateChapterContentRequest(BaseModel):
    version_type: str = "FINAL"
    content: str

class ResetChaptersRequest(BaseModel):
    chapter_nos: Optional[List[int]] = None
    full_restart: Optional[bool] = False

class UpdateNovelEntityRequest(BaseModel):
    chinese_name: str
    rough_translation: str
    entity_type: str = "NAME"
    gender: Optional[str] = None
    role: Optional[str] = None
    old_vietnamese_term: Optional[str] = None

@router.get("")
async def list_novels() -> Dict[str, Any]:
    """
    Lấy danh sách tất cả các truyện trong DB kèm số lượng chương.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(
            Novel.id,
            Novel.title_raw,
            Novel.title_rough,
            Novel.author,
            Novel.source_url,
            Novel.status,
            Novel.context_profile,
            Novel.created_at,
            func.count(Chapter.id).label("total_chapters"),
            func.sum(case((Chapter.status == "FINAL_DONE", 1), else_=0)).label("completed_chapters")
        ).outerjoin(Chapter, Novel.id == Chapter.novel_id).group_by(Novel.id).order_by(Novel.id.desc())
        
        res = await session.execute(stmt)
        rows = res.all()
        
        novels = []
        for row in rows:
            novels.append({
                "id": row.id,
                "title": row.title_rough or row.title_raw,
                "title_raw": row.title_raw,
                "title_rough": row.title_rough,
                "author": row.author,
                "source_url": row.source_url,
                "status": row.status,
                "context_profile": row.context_profile,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "total_chapters": row.total_chapters,
                "completed_chapters": int(row.completed_chapters or 0)
            })
            
        return {"status": "success", "total": len(novels), "data": novels}


@router.get("/{novel_id}")
async def get_novel_detail(novel_id: int = Path(...)) -> Dict[str, Any]:
    """
    Lấy thông tin chi tiết của 1 truyện kèm danh sách chương và trạng thái dịch/nội dung.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
            
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no.asc())
        res_ch = await session.execute(stmt_ch)
        chapters = res_ch.scalars().all()

        stmt_ver = select(
            ChapterVersion.chapter_id,
            ChapterVersion.version_type,
            ChapterVersion.content,
            ChapterVersion.file_path
        ).join(Chapter).where(Chapter.novel_id == novel_id)
        res_ver = await session.execute(stmt_ver)
        rows_ver = res_ver.all()

        version_types_map: Dict[int, set] = {}
        fallback_map: Dict[int, bool] = {}
        swept_error_map: Dict[int, bool] = {}

        # Ưu tiên phiên bản dịch hiển thị thực tế: FINAL -> EDITED -> CONTEXTT -> LLM -> GG
        version_priority = {"FINAL": 1, "EDITED": 2, "CONTEXTT": 3, "LLM": 4, "GG": 5}
        best_version_map: Dict[int, tuple] = {}

        for ch_id, v_type, content, f_path in rows_ver:
            if ch_id not in version_types_map:
                version_types_map[ch_id] = set()
            version_types_map[ch_id].add(v_type)

            prio = version_priority.get(v_type, 99)
            if prio < 99:
                if ch_id not in best_version_map or prio < best_version_map[ch_id][0]:
                    best_version_map[ch_id] = (prio, content, f_path)

        for ch_id, (prio, content, f_path) in best_version_map.items():
            text_to_check = ""
            if content:
                text_to_check = content
            elif f_path and os.path.exists(f_path):
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        text_to_check = f.read(50000)
                except Exception:
                    pass

            if text_to_check:
                if 'fallback-word' in text_to_check or 'fixed-word' in text_to_check or 'fixed-sentence' in text_to_check:
                    fallback_map[ch_id] = True
                if 'swept-error' in text_to_check or 'swept-chinese' in text_to_check:
                    swept_error_map[ch_id] = True

        chapters_list = []
        for c in chapters:
            c_vtypes = version_types_map.get(c.id, set())
            
            # Xác định status chuẩn cho Frontend ('COMPLETED', 'RESCUED', 'WAIT', etc.)
            final_status = c.status
            if final_status in ["FINAL_DONE", "DONE", "TRANSLATED"]:
                final_status = "COMPLETED"

            has_translation = any(k in c_vtypes for k in ["FINAL", "CONTEXTT", "LLM", "GG"])
            if has_translation and final_status == "WAIT":
                final_status = "COMPLETED"

            chapters_list.append({
                "id": c.id,
                "novel_id": c.novel_id,
                "chapter_no": c.chapter_no,
                "title": c.title_rough or c.title_raw,
                "source_url": getattr(c, "url", ""),
                "raw_text": None,
                "translated_text": None,
                "status": final_status,
                "error_msg": c.error_message,
                "has_fallback_words": fallback_map.get(c.id, False),
                "has_swept_errors": swept_error_map.get(c.id, False),
                "token_count": 0,
                "updated_at": c.updated_at.isoformat() if c.updated_at else ""
            })

        novel_dict = {
            "id": novel.id,
            "title": novel.title_rough or novel.title_raw,
            "title_raw": novel.title_raw,
            "title_rough": novel.title_rough,
            "author": novel.author or "Unknown Author",
            "cover_url": novel.cover_url or "",
            "source_url": novel.source_url,
            "genres": novel.genres or "",
            "status": novel.status,
            "context_profile": novel.context_profile or "",
            "created_at": novel.created_at.isoformat() if novel.created_at else None,
            "total_chapters": len(chapters_list)
        }

        return {
            "status": "success",
            "data": novel_dict,
            "novel": novel_dict,
            "chapters": chapters_list
        }


@router.get("/{novel_id}/chapters")
async def list_chapters(
    novel_id: int = Path(...),
    start: Optional[int] = Query(0, description="Chương bắt đầu (0 là từ đầu)"),
    end: Optional[int] = Query(0, description="Chương kết thúc (0 là đến hết)")
) -> Dict[str, Any]:
    """
    Lấy danh sách các chương của truyện (id, số chương, tiêu đề, trạng thái).
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Chapter).where(Chapter.novel_id == novel_id)
        if start and start > 0:
            stmt = stmt.where(Chapter.chapter_no >= start)
        if end and end > 0:
            stmt = stmt.where(Chapter.chapter_no <= end)
            
        stmt = stmt.order_by(Chapter.chapter_no.asc())
        res = await session.execute(stmt)
        chapters = res.scalars().all()
        
        data = []
        for c in chapters:
            data.append({
                "id": c.id,
                "chapter_no": c.chapter_no,
                "title_raw": c.title_raw,
                "title_rough": c.title_rough,
                "status": c.status,
                "source_url": getattr(c, "url", "")
            })
            
        return {"status": "success", "total": len(data), "data": data}


@router.get("/{novel_id}/entities")
async def list_novel_entities(novel_id: int = Path(...)) -> Dict[str, Any]:
    """
    Lấy toàn bộ danh sách từ điển (nhân vật, địa danh, chiêu thức) của truyện.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(NovelEntity).where(NovelEntity.novel_id == novel_id).order_by(NovelEntity.id.asc())
        res = await session.execute(stmt)
        entities = res.scalars().all()
        
        data = []
        for e in entities:
            data.append({
                "id": e.id,
                "chinese_name": e.chinese_name,
                "rough_translation": e.rough_translation,
                "entity_type": e.entity_type,
                "gender": getattr(e, "gender", None),
                "role": getattr(e, "role", None)
            })
            
        return {"status": "success", "total": len(data), "data": data}


@router.get("/{novel_id}/export-full")
async def export_full_novel(novel_id: int = Path(...)) -> Dict[str, Any]:
    """
    Xuất file .txt truyện hoàn chỉnh của truyện (các chương FINAL) và trả về đường dẫn file.
    """
    try:
        exp_res = await export_full_novel_txt(novel_id)
        file_path = exp_res.get("file_path", "") if isinstance(exp_res, dict) else str(exp_res)
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "message": "Không có chương FINAL nào để xuất file."}
            
        return {
            "status": "success",
            "message": "Đã xuất file truyện hoàn chỉnh.",
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chapters/{chapter_id}/content")
async def get_chapter_content(
    chapter_id: int = Path(...),
    version_type: str = Query("FINAL", description="Loại phiên bản: RAW, GG, LLM, FINAL")
) -> Dict[str, Any]:
    """
    Lấy nội dung văn bản của 1 chương theo version_type.
    Ưu tiên đọc từ DB ver.content, fallback sang đọc file đĩa.
    """
    async with AsyncSessionLocal() as session:
        stmt_chap = select(Chapter).where(Chapter.id == chapter_id)
        res_chap = await session.execute(stmt_chap)
        chap = res_chap.scalar_one_or_none()
        if not chap:
            raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
            
        stmt_ver = select(ChapterVersion).where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.version_type == version_type.upper()
        )
        res_ver = await session.execute(stmt_ver)
        ver = res_ver.scalar_one_or_none()
        
        content = ""
        file_path = ""
        if ver:
            file_path = ver.file_path or ""
            if ver.content:
                content = ver.content
            elif ver.file_path and os.path.exists(ver.file_path):
                with open(ver.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
        return {
            "status": "success",
            "data": {
                "chapter_id": chapter_id,
                "chapter_no": chap.chapter_no,
                "title_raw": chap.title_raw,
                "title_rough": chap.title_rough,
                "version_type": version_type.upper(),
                "content": content,
                "file_path": file_path
            }
        }


@router.put("/chapters/{chapter_id}/content")
async def save_chapter_content(
    chapter_id: int = Path(...),
    req: UpdateChapterContentRequest = None
) -> Dict[str, Any]:
    """
    Lưu/cập nhật nội dung văn bản của 1 chương từ Frontend (người dùng sửa thủ công).
    """
    if not req or not req.content:
        raise HTTPException(status_code=400, detail="Nội dung trống.")
        
    async with AsyncSessionLocal() as session:
        stmt_chap = select(Chapter).where(Chapter.id == chapter_id)
        res_chap = await session.execute(stmt_chap)
        chap = res_chap.scalar_one_or_none()
        if not chap:
            raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
            
        stmt_ver = select(ChapterVersion).where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.version_type == req.version_type.upper()
        )
        res_ver = await session.execute(stmt_ver)
        ver = res_ver.scalar_one_or_none()
        
        if ver:
            ver.content = req.content
            if ver.file_path:
                os.makedirs(os.path.dirname(ver.file_path), exist_ok=True)
                with open(ver.file_path, "w", encoding="utf-8") as f:
                    f.write(req.content)
        else:
            # Tạo đường dẫn file mặc định
            base_dir = r"D:\NENGHIA0980\AIREAD\Output\04_KetQua" if req.version_type.upper() == "FINAL" else r"D:\NENGHIA0980\AIREAD\Output\03_DichAI_LLM"
            file_path = os.path.join(base_dir, f"novel_{chap.novel_id}", "chapters", f"{chap.chapter_no:06d}.txt")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(req.content)
            session.add(ChapterVersion(
                chapter_id=chapter_id,
                version_type=req.version_type.upper(),
                file_path=file_path,
                content=req.content
            ))
            
        await session.commit()
        
    return {"status": "success", "message": "Đã lưu nội dung chương thành công."}


@router.put("/{novel_id}/entities")
async def update_novel_entity_and_apply(
    novel_id: int = Path(...), 
    payload: UpdateNovelEntityRequest = None
):
    """
    Sửa hoặc thêm tên nhân vật/địa danh/chiêu thức cho truyện và hồi tố áp dụng lại 
    vào TẤT CẢ bản dịch (GG, LLM, FINAL) trong DB và file đĩa.
    Khi đổi tên → tự động thay thế tên cũ → tên mới trong mọi chương đã dịch.
    """
    try:
        from app.services.unblock.unblock_pipeline import is_exact_sensitive_word
        from app.services.preprocessing.dichhan.hanviet_data import sanitize_entity_vietnamese
        from app.services.preprocessing.dichhan.translator import clear_translator_caches
        import re
        
        # Chỉ chặn khi tên thực thể là từ nhạy cảm nguyên cụm chính xác (không so khớp chuỗi con)
        if await is_exact_sensitive_word(payload.chinese_name) or await is_exact_sensitive_word(payload.rough_translation):
            raise HTTPException(status_code=400, detail="Tên hoặc từ dịch là từ khóa nhạy cảm trong danh sách Unblock, không thể lưu.")
        
        # Tự động chuẩn hóa Hán-Việt nếu tên còn dính Hán tự lai tạp
        if payload.rough_translation:
            payload.rough_translation = sanitize_entity_vietnamese(payload.rough_translation, payload.chinese_name)
        
        old_translation = None
        saved_entity_id = None
        async with AsyncSessionLocal() as session:
            stmt = select(NovelEntity).where(
                NovelEntity.novel_id == novel_id,
                NovelEntity.chinese_name == payload.chinese_name
            )
            res = await session.execute(stmt)
            entity = res.scalar_one_or_none()
            
            if entity:
                old_translation = entity.rough_translation
                entity.rough_translation = payload.rough_translation
                entity.entity_type = payload.entity_type
                if payload.gender is not None:
                    entity.gender = payload.gender
                if payload.role is not None:
                    entity.role = payload.role
                await session.commit()
                saved_entity_id = entity.id
            else:
                new_ent = NovelEntity(
                    novel_id=novel_id,
                    chinese_name=payload.chinese_name,
                    rough_translation=payload.rough_translation,
                    entity_type=payload.entity_type,
                    gender=payload.gender,
                    role=payload.role
                )
                session.add(new_ent)
                await session.commit()
                saved_entity_id = new_ent.id
            
        clear_translator_caches()
        
        updated_files = 0
        search_terms = []
        if payload.entity_type == "CORRECTION" and payload.chinese_name:
            search_terms.append(payload.chinese_name)
        if old_translation and old_translation != payload.rough_translation:
            search_terms.append(old_translation)
        # Hỗ trợ old_vietnamese_term từ frontend (khi user đổi tên Việt)
        if payload.old_vietnamese_term and payload.old_vietnamese_term != payload.rough_translation:
            if payload.old_vietnamese_term not in search_terms:
                search_terms.append(payload.old_vietnamese_term)

        if search_terms:
            async with AsyncSessionLocal() as session:
                # Hồi tố thay tên trong TẤT CẢ bản dịch: GG, LLM, FINAL
                target_version_types = ["GG", "LLM", "FINAL"]
                stmt_versions = select(ChapterVersion).join(Chapter).where(
                    Chapter.novel_id == novel_id,
                    ChapterVersion.version_type.in_(target_version_types)
                )
                res_versions = await session.execute(stmt_versions)
                all_versions = res_versions.scalars().all()
                
                for ver in all_versions:
                    content = ver.content
                    if not content and ver.file_path and os.path.exists(ver.file_path):
                        with open(ver.file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            
                    if content:
                        modified = False
                        for st in search_terms:
                            pattern = r'(?i)(?<![a-zA-Z0-9À-ỹ])' + re.escape(st) + r'(?![a-zA-Z0-9À-ỹ])'
                            new_content, count = re.subn(pattern, payload.rough_translation, content)
                            if count > 0:
                                content = new_content
                                modified = True
                        if modified:
                            ver.content = content
                            if ver.file_path:
                                os.makedirs(os.path.dirname(ver.file_path), exist_ok=True)
                                with open(ver.file_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                            updated_files += 1

                await session.commit()

        # Sync metadata cache sau khi thay đổi entity
        try:
            from app.services.storage.metadata_cache import sync_novel_metadata
            await sync_novel_metadata(novel_id)
        except Exception:
            pass
                            
        version_label = "GG/LLM/FINAL" if search_terms else "DB"
        return {
            "status": "success",
            "message": f"Đã cập nhật tên '{payload.chinese_name}' → '{payload.rough_translation}' vào DB và thay tên trên {updated_files} chương ({version_label}).",
            "entity_id": saved_entity_id,
            "affected_chapters": updated_files
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{novel_id}/entities/{entity_id}")
async def delete_novel_entity(
    novel_id: int = Path(...), 
    entity_id: int = Path(...)
):
    """
    Xóa 1 từ điển nhân vật/địa danh khỏi bộ truyện.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(NovelEntity).where(
            NovelEntity.id == entity_id,
            NovelEntity.novel_id == novel_id
        )
        res = await session.execute(stmt)
        entity = res.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=404, detail="Không tìm thấy thực thể.")
            
        await session.delete(entity)
        await session.commit()
        
    from app.services.preprocessing.dichhan.translator import clear_translator_caches
    clear_translator_caches()

    # Sync metadata cache
    try:
        from app.services.storage.metadata_cache import sync_novel_metadata
        await sync_novel_metadata(novel_id)
    except Exception:
        pass
    
    return {"status": "success", "message": "Đã xóa thực thể khỏi truyện."}


@router.get("/{novel_id}/metadata")
async def get_novel_metadata(novel_id: int = Path(...)) -> Dict[str, Any]:
    """
    Đọc metadata truyện từ SQLite cache riêng (nhanh hơn query DB chính).
    Tự động sync nếu cache chưa tồn tại.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
        novel_title = novel.title_rough or novel.title_raw

    from app.services.storage.metadata_cache import (
        load_novel_entities_fast,
        load_novel_context_fast,
        sync_novel_metadata,
        get_metadata_entities_path
    )

    # Auto-sync nếu chưa có cache (entities.json)
    entities_path = get_metadata_entities_path(novel_title)
    if not entities_path.exists():
        await sync_novel_metadata(novel_id)

    entities = load_novel_entities_fast(novel_title)
    context = load_novel_context_fast(novel_title)

    return {
        "status": "success",
        "novel_id": novel_id,
        "novel_title": novel_title,
        "entities": entities,
        "context": context
    }


@router.delete("/{novel_id}")
async def delete_novel(novel_id: int = Path(...)):
    """
    Xóa toàn bộ truyện (thông tin, mục lục, tất cả các phiên bản dịch và file trên đĩa).
    """
    from app.services.preprocessing.crawler.pipeline import delete_novel_completely
    try:
        await delete_novel_completely(novel_id)
        return {"status": "success", "message": f"Đã xóa hoàn toàn truyện ID {novel_id} khỏi DB và đĩa cứng."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{novel_id}/translations")
async def reset_novel_translations(novel_id: int = Path(...)):
    """
    Xóa toàn bộ các phiên bản đã dịch (GG, LLM, CONTEXTT, FINAL) của cả bộ truyện, CHỈ ĐỂ LẠI BẢN GỐC (RAW)
    và đặt lại trạng thái chương về CRAWLED để có thể dịch lại từ đầu.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(ChapterVersion).join(Chapter).where(
                Chapter.novel_id == novel_id,
                ChapterVersion.version_type != "RAW"
            )
            res = await session.execute(stmt)
            versions = res.scalars().all()
            for ver in versions:
                if ver.file_path and os.path.exists(ver.file_path):
                    try:
                        os.remove(ver.file_path)
                    except Exception:
                        pass
                await session.delete(ver)
                
            # Lấy thông tin truyện để xóa đúng tên thư mục
            stmt_novel = select(Novel).where(Novel.id == novel_id)
            res_novel = await session.execute(stmt_novel)
            novel = res_novel.scalar_one_or_none()
            novel_title = novel.title_rough or novel.title_raw if novel else ""
            
            stmt_chaps = select(Chapter).where(Chapter.novel_id == novel_id)
            res_chaps = await session.execute(stmt_chaps)
            chaps = res_chaps.scalars().all()
            for chap in chaps:
                chap.status = "CRAWLED"
                
            await session.commit()
            
        if novel_title:
            from app.services.storage.file_storage import delete_version_disk_files
            for v_type in ["GG", "LLM", "FINAL", "TTS_TEXT", "AUDIO"]:
                delete_version_disk_files(v_type, novel_title)
                
        return {
            "status": "success",
            "message": f"Đã xóa toàn bộ bản dịch của truyện ID {novel_id}, chỉ để lại bản gốc (RAW)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chapters/{chapter_id}/translations")
async def reset_chapter_translations(chapter_id: int = Path(...)):
    """
    Xóa toàn bộ các phiên bản đã dịch của 1 chương cụ thể, CHỈ ĐỂ LẠI BẢN GỐC (RAW)
    và đặt lại trạng thái về CRAWLED để dịch lại chương đó.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt_chap = select(Chapter).where(Chapter.id == chapter_id)
            res_chap = await session.execute(stmt_chap)
            chap = res_chap.scalar_one_or_none()
            if not chap:
                raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
                
            stmt_novel = select(Novel).where(Novel.id == chap.novel_id)
            res_novel = await session.execute(stmt_novel)
            novel = res_novel.scalar_one_or_none()
            novel_title = novel.title_rough or novel.title_raw if novel else ""

            stmt_vers = select(ChapterVersion).where(
                ChapterVersion.chapter_id == chapter_id,
                ChapterVersion.version_type != "RAW"
            )
            res_vers = await session.execute(stmt_vers)
            versions = res_vers.scalars().all()
            
            for ver in versions:
                if ver.file_path and os.path.exists(ver.file_path):
                    try:
                        os.remove(ver.file_path)
                    except Exception:
                        pass
                await session.delete(ver)
                
            chap.status = "CRAWLED"
            await session.commit()

            # Dọn dẹp các tệp đĩa liên quan đến chương này trong các thư mục Output
            if novel_title:
                from app.services.storage.file_storage import OUTPUT_ROOT, VERSION_FOLDER_MAP, sanitize_filename
                folder_novel = sanitize_filename(novel_title)
                for folder_type in VERSION_FOLDER_MAP.values():
                    if folder_type == "01_BanGoc":
                        continue
                    for sub in ["", "chapters"]:
                        p_txt = OUTPUT_ROOT / folder_type / folder_novel / sub / f"{chap.chapter_no:06d}.txt" if sub else OUTPUT_ROOT / folder_type / folder_novel / f"{chap.chapter_no:06d}.txt"
                        if p_txt.exists():
                            try: p_txt.unlink()
                            except Exception: pass
                        p_mp3 = OUTPUT_ROOT / folder_type / folder_novel / sub / f"{chap.chapter_no:06d}.mp3" if sub else OUTPUT_ROOT / folder_type / folder_novel / f"{chap.chapter_no:06d}.mp3"
                        if p_mp3.exists():
                            try: p_mp3.unlink()
                            except Exception: pass
            
        return {
            "status": "success",
            "message": f"Đã xóa toàn bộ bản dịch của chương ID {chapter_id}, chỉ để lại bản gốc (RAW)."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS BỔ SUNG ĐỒNG BỘ FRONTEND REACT
# ==========================================

class AnalyzeUrlRequest(BaseModel):
    url: str

@router.post("/analyze")
async def analyze_novel_url(payload: AnalyzeUrlRequest):
    from app.services.preprocessing.crawler.pipeline import process_novel_link
    try:
        res = await process_novel_link(payload.url)
        return {
            "title": res.get("title_rough") or res.get("title_raw", ""),
            "author": res.get("author", "Unknown Author"),
            "cover_url": res.get("cover_url", ""),
            "source_url": payload.url,
            "genres": res.get("genres", ""),
            "status": res.get("status", "Ongoing"),
            "total_chapters": res.get("total_chapters", 0),
            "novel_id": res.get("novel_id"),
            "chapters": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích URL: {str(e)}")

class SaveNovelRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    cover_url: Optional[str] = None
    source_url: str
    genres: Optional[str] = None
    status: Optional[str] = None
    chapters: Optional[List[Any]] = None

@router.post("/save")
async def save_analyzed_novel(payload: SaveNovelRequest):
    from app.services.preprocessing.crawler.pipeline import process_novel_link
    try:
        res = await process_novel_link(payload.source_url)
        return {
            "status": "success",
            "message": "Đã lưu truyện vào CSDL.",
            "novel_id": res.get("novel_id")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu truyện: {str(e)}")

class UpdateGenreRequest(BaseModel):
    genre: str

@router.put("/{novel_id}/genre")
async def update_novel_genre(novel_id: int = Path(...), payload: UpdateGenreRequest = ...):
    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy truyện.")
        novel.genres = payload.genre
        novel.context_profile = payload.genre.lower()
        await session.commit()
    return {"status": "success", "message": f"Đã cập nhật thể loại '{payload.genre}' thành công."}

class ResetChaptersRequest(BaseModel):
    chapter_nos: Optional[List[int]] = None
    full_restart: Optional[bool] = False

@router.post("/{novel_id}/chapters/reset")
async def reset_chapters(novel_id: int = Path(...), payload: ResetChaptersRequest = ...):
    """
    Reset chương truyện. 
    - Mặc định: xóa ChapterVersion, ChapterCorrection, file đĩa, đặt status = WAIT
    - full_restart=true: Xóa THÊM NovelEntity, ChapterEntityLink, TTSChunk, metadata SQLite
      → Dịch lại hoàn toàn từ đầu
    """
    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        
        stmt = select(Chapter).where(Chapter.novel_id == novel_id)
        if payload.chapter_nos:
            stmt = stmt.where(Chapter.chapter_no.in_(payload.chapter_nos))
        res = await session.execute(stmt)
        chapters = res.scalars().all()
        
        chap_ids = [c.id for c in chapters]
        if chap_ids:
            # Xóa sạch bảng ChapterCorrection của các chương reset
            from app.models.schema import ChapterCorrection, ChapterEntityLink, TTSChunk
            stmt_corr_del = select(ChapterCorrection).where(ChapterCorrection.chapter_id.in_(chap_ids))
            res_corr_del = await session.execute(stmt_corr_del)
            corrs = res_corr_del.scalars().all()
            for corr in corrs:
                await session.delete(corr)

            # Xóa ChapterEntityLink của các chương reset
            stmt_link_del = select(ChapterEntityLink).where(ChapterEntityLink.chapter_id.in_(chap_ids))
            res_link_del = await session.execute(stmt_link_del)
            links = res_link_del.scalars().all()
            for link in links:
                await session.delete(link)

            # Lấy tất cả các phiên bản (kể cả RAW, GG, LLM, FINAL, CONTEXTT, AUDIO) để xóa tệp đĩa và DB
            stmt_ver = select(ChapterVersion).where(ChapterVersion.chapter_id.in_(chap_ids))
            res_ver = await session.execute(stmt_ver)
            versions = res_ver.scalars().all()
            
            for ver in versions:
                if ver.file_path and os.path.exists(ver.file_path):
                    try:
                        os.remove(ver.file_path)
                    except Exception:
                        pass
                await session.delete(ver)

            for ch in chapters:
                ch.status = "WAIT"
                ch.error_message = ""

        # === FULL RESTART: Xóa thêm entities, TTS chunks, metadata ===
        if payload.full_restart and novel:
            # Xóa toàn bộ NovelEntity của truyện
            stmt_ent_del = select(NovelEntity).where(NovelEntity.novel_id == novel_id)
            res_ent_del = await session.execute(stmt_ent_del)
            entities = res_ent_del.scalars().all()
            for ent in entities:
                await session.delete(ent)

            # Xóa toàn bộ TTSChunk của truyện
            stmt_tts_del = select(TTSChunk).where(TTSChunk.novel_id == novel_id)
            res_tts_del = await session.execute(stmt_tts_del)
            tts_chunks = res_tts_del.scalars().all()
            for chunk in tts_chunks:
                await session.delete(chunk)
                
        await session.commit()

        # Nếu reset tất cả các chương của bộ truyện, dọn dẹp luôn các thư mục chứa tệp đĩa tương ứng
        if novel and not payload.chapter_nos:
            from app.services.storage.file_storage import delete_novel_disk_files
            novel_title_rough = novel.title_rough or novel.title_raw
            delete_novel_disk_files(novel_title_rough)

            # Full restart: xóa thêm metadata JSON cache
            if payload.full_restart:
                from app.services.storage.metadata_cache import invalidate_metadata
                invalidate_metadata(novel_title_rough)
        
    msg = f"Đã xóa sạch tất cả phiên bản/file đĩa và đặt lại trạng thái cho {len(chapters)} chương."
    if payload.full_restart:
        msg = f"🔄 RESTART TOÀN BỘ: Đã xóa sạch {len(chapters)} chương, thực thể, audio, metadata. Sẵn sàng dịch lại từ đầu."
    return {"status": "success", "message": msg}


@router.post("/{novel_id}/save-to-folder")
async def save_novel_to_folder(novel_id: int = Path(...)):
    try:
        exp = await export_full_novel_txt(novel_id)
        return {
            "success": True,
            "folder": "Output/",
            "folder_path": exp.get("file_path", ""),
            "total_files": 1,
            "message": f"Đã xuất file truyện hoàn chỉnh vào thư mục {exp.get('file_path')}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{novel_id}/chapters/{chapterNo}/text")
async def get_chapter_text(novel_id: int = Path(...), chapterNo: int = Path(...)):
    async with AsyncSessionLocal() as session:
        stmt = select(Chapter).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapterNo)
        res = await session.execute(stmt)
        ch = res.scalar_one_or_none()
        if not ch:
            raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
        
        stmt_ver = select(ChapterVersion).where(ChapterVersion.chapter_id == ch.id)
        res_ver = await session.execute(stmt_ver)
        versions = res_ver.scalars().all()
        
        version_map: Dict[str, ChapterVersion] = {v.version_type: v for v in versions}
        
        from app.services.storage.file_storage import read_version_file_content
        raw_text = ""
        if "RAW" in version_map:
            v_raw = version_map["RAW"]
            raw_text = v_raw.content or ""
            if not raw_text and v_raw.file_path and os.path.exists(v_raw.file_path):
                try:
                    raw_text = read_version_file_content(v_raw.file_path)
                except Exception:
                    pass

        translated_text = ""
        for v_type in ["FINAL", "CONTEXTT", "LLM", "GG"]:
            if v_type in version_map:
                v_trans = version_map[v_type]
                translated_text = v_trans.content or ""
                if not translated_text and v_trans.file_path and os.path.exists(v_trans.file_path):
                    try:
                        translated_text = read_version_file_content(v_trans.file_path)
                    except Exception:
                        pass
                if translated_text:
                    break

        return {
            "chapter_no": ch.chapter_no,
            "title": ch.title_rough or ch.title_raw,
            "raw_text": raw_text,
            "translated_text": translated_text or raw_text
        }

class UpdateTextRequest(BaseModel):
    translated_text: str

@router.put("/{novel_id}/chapters/{chapterNo}/text")
async def update_chapter_text(novel_id: int = Path(...), chapterNo: int = Path(...), payload: UpdateTextRequest = ...):
    if not payload or not payload.translated_text:
        raise HTTPException(status_code=400, detail="Nội dung bản dịch trống.")

    async with AsyncSessionLocal() as session:
        stmt_nov = select(Novel).where(Novel.id == novel_id)
        res_nov = await session.execute(stmt_nov)
        novel = res_nov.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Không tìm thấy tiểu thuyết.")

        stmt = select(Chapter).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapterNo)
        res = await session.execute(stmt)
        ch = res.scalar_one_or_none()
        if not ch:
            raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
            
        novel_folder = sanitize_filename(novel.title_rough or novel.title_raw or f"novel_{novel_id}")
        base_dir = r"D:\NENGHIA0980\AIREAD\Output\04_KetQua"
        out_dir = os.path.join(base_dir, novel_folder, "chapters")
        os.makedirs(out_dir, exist_ok=True)
        file_path = os.path.join(out_dir, f"{chapterNo:06d}.txt")

        # Ghi file ra đĩa
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(payload.translated_text)
        except Exception as e:
            print(f"⚠️ Lỗi ghi file bản dịch {file_path}: {e}")

        # Cập nhật hoặc tạo ChapterVersion loại FINAL
        stmt_ver = select(ChapterVersion).where(
            ChapterVersion.chapter_id == ch.id,
            ChapterVersion.version_type == "FINAL"
        )
        res_ver = await session.execute(stmt_ver)
        ver = res_ver.scalar_one_or_none()
        
        if ver:
            ver.content = payload.translated_text
            ver.file_path = file_path
            ver.status = "COMPLETED"
        else:
            new_ver = ChapterVersion(
                chapter_id=ch.id, 
                version_type="FINAL", 
                file_path=file_path,
                content=payload.translated_text,
                status="COMPLETED"
            )
            session.add(new_ver)

        # Cập nhật thêm content của các version LLM / CONTEXTT nếu có để đồng bộ
        stmt_other_vers = select(ChapterVersion).where(
            ChapterVersion.chapter_id == ch.id,
            ChapterVersion.version_type.in_(["LLM", "CONTEXTT"])
        )
        res_other_vers = await session.execute(stmt_other_vers)
        for ov in res_other_vers.scalars().all():
            ov.content = payload.translated_text

        ch.status = "FINAL_DONE"
        
        # Xóa cache audio TTS cũ của chương (nếu có) để khi nghe lại sẽ đọc bản dịch mới
        try:
            mp3_cache_path = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS", novel_folder, "chapters", f"{chapterNo:06d}.mp3")
            if os.path.exists(mp3_cache_path):
                os.remove(mp3_cache_path)
            tmp_ch_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\05_Audio_TTS", novel_folder, "chapters", f"_tmp_ch{chapterNo:06d}")
            if os.path.exists(tmp_ch_dir):
                shutil.rmtree(tmp_ch_dir, ignore_errors=True)
        except Exception:
            pass

        await session.commit()

    # Cập nhật lại file truyện hoàn chỉnh Full.txt
    try:
        await export_full_novel_txt(novel_id)
    except Exception:
        pass

    return {"status": "success", "message": "Đã lưu bản dịch chỉnh sửa thành công."}

@router.get("/{novel_id}/download")
async def download_novel_file(novel_id: int = Path(...), fmt: str = Query("txt")):
    from fastapi.responses import FileResponse
    exp = await export_full_novel_txt(novel_id)
    file_path = exp.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Chưa có bản dịch hoàn chỉnh để tải về.")
    filename = os.path.basename(file_path)
    return FileResponse(file_path, filename=filename, media_type="text/plain; charset=utf-8")

# ==========================================
# GLOSSARY ENDPOINTS FOR FRONTEND
# ==========================================

class GlossaryTermPayload(BaseModel):
    chinese_term: str
    vietnamese_term: str
    category: Optional[str] = "OTHER"
    old_vietnamese_term: Optional[str] = None
    apply_to_all_chapters: Optional[bool] = False
    chapter_no: Optional[int] = None

@router.get("/{novel_id}/glossary")
async def get_novel_glossary(novel_id: int = Path(...)):
    async with AsyncSessionLocal() as session:
        stmt = select(NovelEntity).where(NovelEntity.novel_id == novel_id).order_by(NovelEntity.id.asc())
        res = await session.execute(stmt)
        entities = res.scalars().all()
        
        type_mapping = {
            "PERSON": "NAME",
            "LOCATION": "PLACE",
            "SECT_SKILL": "SECT",
            "ORGANIZATION": "SECT"
        }
        
        return [
            {
                "id": e.id,
                "novel_id": e.novel_id,
                "chinese_term": e.chinese_name,
                "vietnamese_term": e.rough_translation,
                "category": type_mapping.get(e.entity_type, e.entity_type),
                "is_active": True,
                "gender": getattr(e, "gender", None),
                "role": getattr(e, "role", None)
            } for e in entities
        ]

class ChapterCorrectionPayload(BaseModel):
    wrong_text: str
    correct_text: str

@router.get("/{novel_id}/chapters/{chapter_no}/entities")
async def get_chapter_entities(novel_id: int = Path(...), chapter_no: int = Path(...)):
    async with AsyncSessionLocal() as session:
        stmt_chap = select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapter_no)
        res_chap = await session.execute(stmt_chap)
        chapter_id = res_chap.scalar_one_or_none()
        if not chapter_id:
            return []
            
        from app.models.schema import ChapterEntityLink
        stmt = select(NovelEntity).join(ChapterEntityLink).where(
            ChapterEntityLink.chapter_id == chapter_id
        ).order_by(NovelEntity.id.asc())
        res = await session.execute(stmt)
        entities = res.scalars().all()
        
        type_mapping = {
            "PERSON": "NAME",
            "LOCATION": "PLACE",
            "SECT_SKILL": "SECT",
            "ORGANIZATION": "SECT"
        }
        
        return [
            {
                "id": e.id,
                "novel_id": e.novel_id,
                "chinese_term": e.chinese_name,
                "vietnamese_term": e.rough_translation,
                "category": type_mapping.get(e.entity_type, e.entity_type),
                "is_active": True
            } for e in entities
        ]

@router.get("/{novel_id}/chapters/{chapter_no}/corrections")
async def get_chapter_corrections(novel_id: int = Path(...), chapter_no: int = Path(...)):
    async with AsyncSessionLocal() as session:
        stmt_chap = select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapter_no)
        res_chap = await session.execute(stmt_chap)
        chapter_id = res_chap.scalar_one_or_none()
        if not chapter_id:
            return []
            
        from app.models.schema import ChapterCorrection
        stmt = select(ChapterCorrection).where(
            ChapterCorrection.chapter_id == chapter_id
        ).order_by(ChapterCorrection.id.asc())
        res = await session.execute(stmt)
        corrs = res.scalars().all()
        
        return [
            {
                "id": c.id,
                "chapter_id": c.chapter_id,
                "wrong_text": c.wrong_text,
                "correct_text": c.correct_text
            } for c in corrs
        ]

@router.post("/{novel_id}/chapters/{chapter_no}/corrections")
async def add_chapter_correction(
    novel_id: int = Path(...),
    chapter_no: int = Path(...),
    payload: ChapterCorrectionPayload = None
):
    async with AsyncSessionLocal() as session:
        stmt_chap = select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapter_no)
        res_chap = await session.execute(stmt_chap)
        chapter_id = res_chap.scalar_one_or_none()
        if not chapter_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy chương.")
            
        from app.models.schema import ChapterCorrection
        new_corr = ChapterCorrection(
            chapter_id=chapter_id,
            wrong_text=payload.wrong_text,
            correct_text=payload.correct_text
        )
        session.add(new_corr)
        await session.commit()
    
    from app.services.storage.metadata_cache import sync_novel_metadata
    await sync_novel_metadata(novel_id)
    return {"success": True, "message": "Đã thêm từ sửa lỗi thành công."}

@router.put("/{novel_id}/chapters/{chapter_no}/corrections/{corr_id}")
async def update_chapter_correction(
    novel_id: int = Path(...),
    chapter_no: int = Path(...),
    corr_id: int = Path(...),
    payload: ChapterCorrectionPayload = None
):
    async with AsyncSessionLocal() as session:
        from app.models.schema import ChapterCorrection
        stmt = select(ChapterCorrection).where(ChapterCorrection.id == corr_id)
        res = await session.execute(stmt)
        corr = res.scalar_one_or_none()
        if not corr:
            raise HTTPException(status_code=404, detail="Không tìm thấy lỗi cần sửa.")
            
        corr.wrong_text = payload.wrong_text
        corr.correct_text = payload.correct_text
        await session.commit()
    
    from app.services.storage.metadata_cache import sync_novel_metadata
    await sync_novel_metadata(novel_id)
    return {"success": True, "message": "Đã cập nhật lỗi thành công."}

@router.delete("/{novel_id}/chapters/{chapter_no}/corrections/{corr_id}")
async def delete_chapter_correction(
    novel_id: int = Path(...),
    chapter_no: int = Path(...),
    corr_id: int = Path(...)
):
    async with AsyncSessionLocal() as session:
        from app.models.schema import ChapterCorrection
        stmt = select(ChapterCorrection).where(ChapterCorrection.id == corr_id)
        res = await session.execute(stmt)
        corr = res.scalar_one_or_none()
        if not corr:
            raise HTTPException(status_code=404, detail="Không tìm thấy lỗi cần xóa.")
            
        await session.delete(corr)
        await session.commit()
    
    from app.services.storage.metadata_cache import sync_novel_metadata
    await sync_novel_metadata(novel_id)
    return {"success": True}

@router.post("/{novel_id}/glossary")
async def add_novel_glossary_term(novel_id: int = Path(...), payload: GlossaryTermPayload = ...):
    req = UpdateNovelEntityRequest(
        chinese_name=payload.chinese_term,
        rough_translation=payload.vietnamese_term,
        entity_type=payload.category or "OTHER"
    )
    res = await update_novel_entity_and_apply(novel_id, req)
    ent_id = res.get("entity_id")
    
    if ent_id and payload.chapter_no:
        async with AsyncSessionLocal() as session:
            stmt_chap = select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.chapter_no == payload.chapter_no)
            res_chap = await session.execute(stmt_chap)
            chapter_id = res_chap.scalar_one_or_none()
            if chapter_id:
                from app.models.schema import ChapterEntityLink
                stmt_link = select(ChapterEntityLink).where(
                    ChapterEntityLink.chapter_id == chapter_id,
                    ChapterEntityLink.entity_id == ent_id
                )
                link_res = await session.execute(stmt_link)
                if not link_res.scalar_one_or_none():
                    session.add(ChapterEntityLink(chapter_id=chapter_id, entity_id=ent_id))
                    await session.commit()
                    
    return {"success": True, "message": res.get("message")}

@router.put("/{novel_id}/glossary/{term_id}")
async def update_novel_glossary_term(novel_id: int = Path(...), term_id: int = Path(...), payload: GlossaryTermPayload = ...):
    req = UpdateNovelEntityRequest(
        chinese_name=payload.chinese_term,
        rough_translation=payload.vietnamese_term,
        entity_type=payload.category or "OTHER",
        old_vietnamese_term=payload.old_vietnamese_term
    )
    res = await update_novel_entity_and_apply(novel_id, req)
    return {"success": True, "message": res.get("message"), "affected_chapters": res.get("affected_chapters", 0)}

@router.post("/{novel_id}/glossary/apply-all")
async def apply_glossary_to_all(novel_id: int = Path(...)):
    return {"success": True, "message": "Đã áp dụng từ điển cho tất cả các chương."}

@router.delete("/{novel_id}/glossary/{term_id}")
async def delete_novel_glossary_term(novel_id: int = Path(...), term_id: int = Path(...), chapter_no: Optional[int] = Query(None)):
    if chapter_no:
        async with AsyncSessionLocal() as session:
            stmt_chap = select(Chapter.id).where(Chapter.novel_id == novel_id, Chapter.chapter_no == chapter_no)
            res_chap = await session.execute(stmt_chap)
            chapter_id = res_chap.scalar_one_or_none()
            if chapter_id:
                from app.models.schema import ChapterEntityLink
                from sqlalchemy import delete as sql_delete
                await session.execute(sql_delete(ChapterEntityLink).where(
                    ChapterEntityLink.chapter_id == chapter_id,
                    ChapterEntityLink.entity_id == term_id
                ))
                await session.commit()
        return {"success": True, "message": "Đã hủy liên kết từ khỏi chương."}
    else:
        await delete_novel_entity(novel_id, term_id)
        return {"success": True, "message": "Đã xóa hoàn toàn thực thể."}

class QuickFixAllRequest(BaseModel):
    provider: Optional[str] = "openrouter"
    model: Optional[str] = "openrouter/free"
    api_key: Optional[str] = ""
    prompt: Optional[str] = ""

@router.post("/{novel_id}/quick-fix-all")
async def quick_fix_all_yellow_sentences(novel_id: int = Path(...), payload: QuickFixAllRequest = ...):
    """
    Sửa nhanh các câu dính từ fallback (chữ vàng) cho toàn bộ các chương của bộ truyện trong 1 lượt.
    """
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Chapter).where(Chapter.novel_id == novel_id)
            res = await session.execute(stmt)
            chapters = res.scalars().all()
            
            fixed_count = 0
            for chap in chapters:
                stmt_ver = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == chap.id,
                    ChapterVersion.version_type.in_(["FINAL", "LLM"])
                )
                res_ver = await session.execute(stmt_ver)
                ver = res_ver.scalar_one_or_none()
                if ver and ver.content and 'class="fallback-word"' in ver.content:
                    # Loại bỏ thẻ fallback-word và loại bỏ luôn các tuỳ chọn trong ngoặc đơn (ví dụ: "chữ 1 (chữ 2/chữ 3)") để trả về câu thuần mượt mà
                    def clean_fallback(m):
                        inner_text = m.group(1)
                        cleaned_word = re.sub(r'\s*\([^)]+\)', '', inner_text).strip()
                        return f'<span class="fixed-word" style="color: #10b981; font-weight: bold;">{cleaned_word}</span>'
                        
                    cleaned_content = re.sub(r'<span class="fallback-word"[^>]*>(.*?)</span>', clean_fallback, ver.content)
                    ver.content = cleaned_content
                    if ver.file_path and os.path.exists(ver.file_path):
                        with open(ver.file_path, "w", encoding="utf-8") as f:
                            f.write(cleaned_content)
                    fixed_count += 1
            await session.commit()
            
        return {
            "success": True,
            "message": f"Đã biên tập mượt mà và làm sạch chữ vàng cho {fixed_count} chương thành công."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{novel_id}/chapters/reset")
async def reset_chapters(
    novel_id: int = Path(...),
    payload: Optional[ResetChaptersRequest] = None
):
    """
    Xóa toàn bộ bản dịch (RAW, GG, LLM, FINAL, AUDIO), cache và reset trạng thái của các chương (hoặc toàn bộ truyện)
    về trạng thái WAIT để cào dữ liệu và dịch lại từ đầu.
    """
    try:
        chapter_nos = payload.chapter_nos if payload else None
        full_restart = payload.full_restart if payload else False
        
        async with AsyncSessionLocal() as session:
            stmt_novel = select(Novel).where(Novel.id == novel_id)
            res_novel = await session.execute(stmt_novel)
            novel = res_novel.scalar_one_or_none()
            if not novel:
                raise HTTPException(status_code=404, detail="Không tìm thấy tiểu thuyết.")
                
            novel_title = novel.title_rough or novel.title_raw or "Novel"
            folder_novel = sanitize_filename(novel_title)

            # Lấy danh sách chương cần reset
            if full_restart or not chapter_nos:
                stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id)
            else:
                stmt_ch = select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_no.in_(chapter_nos)
                )
            res_ch = await session.execute(stmt_ch)
            chapters = res_ch.scalars().all()
            
            if not chapters:
                return {"status": "success", "message": "Không tìm thấy chương nào cần reset.", "reset_count": 0}

            target_chapter_ids = [c.id for c in chapters]
            target_chapter_nos = [c.chapter_no for c in chapters]

            # 1. Lấy tất cả ChapterVersion để xóa file vật lý
            stmt_ver = select(ChapterVersion).where(ChapterVersion.chapter_id.in_(target_chapter_ids))
            res_ver = await session.execute(stmt_ver)
            versions = res_ver.scalars().all()

            for ver in versions:
                if ver.file_path and os.path.exists(ver.file_path):
                    try:
                        os.remove(ver.file_path)
                    except Exception as e:
                        print(f"⚠️ Lỗi xóa file version {ver.file_path}: {e}")

            # 2. Xóa các file đĩa tương ứng trong các thư mục Output (bao gồm 04b_VanBanTTS, 05_Audio_TTS...)
            from app.services.storage.file_storage import OUTPUT_ROOT, VERSION_FOLDER_MAP
            for folder_type in VERSION_FOLDER_MAP.values():
                for c_no in target_chapter_nos:
                    # File text .txt (trực tiếp hoặc trong subfolder chapters)
                    txt_path = OUTPUT_ROOT / folder_type / folder_novel / f"{c_no:06d}.txt"
                    if txt_path.exists():
                        try:
                            txt_path.unlink()
                        except Exception:
                            pass
                    txt_sub_path = OUTPUT_ROOT / folder_type / folder_novel / "chapters" / f"{c_no:06d}.txt"
                    if txt_sub_path.exists():
                        try:
                            txt_sub_path.unlink()
                        except Exception:
                            pass
                    # File audio .mp3 (trực tiếp hoặc trong subfolder chapters)
                    mp3_path = OUTPUT_ROOT / folder_type / folder_novel / f"{c_no:06d}.mp3"
                    if mp3_path.exists():
                        try:
                            mp3_path.unlink()
                        except Exception:
                            pass
                    mp3_sub_path = OUTPUT_ROOT / folder_type / folder_novel / "chapters" / f"{c_no:06d}.mp3"
                    if mp3_sub_path.exists():
                        try:
                            mp3_sub_path.unlink()
                        except Exception:
                            pass
                    # File metadata chapter .json
                    json_path = OUTPUT_ROOT / "06_Metadata" / folder_novel / "chapters" / f"{c_no:06d}.json"
                    if json_path.exists():
                        try:
                            json_path.unlink()
                        except Exception:
                            pass

            # 3. Xóa dữ liệu DB liên quan của các chương này
            from sqlalchemy import delete as sql_delete
            from app.models.schema import ChapterCorrection, ChapterEntityLink

            await session.execute(sql_delete(ChapterVersion).where(ChapterVersion.chapter_id.in_(target_chapter_ids)))
            await session.execute(sql_delete(ChapterCorrection).where(ChapterCorrection.chapter_id.in_(target_chapter_ids)))
            await session.execute(sql_delete(ChapterEntityLink).where(ChapterEntityLink.chapter_id.in_(target_chapter_ids)))

            # 4. Reset trạng thái Chapter về "WAIT" để cào và dịch lại từ đầu
            for chap in chapters:
                chap.status = "WAIT"
                chap.title_rough = chap.title_raw
                chap.error_msg = None

            # 5. Nếu là full_restart → xóa sạch cả entities, corrections và metadata cache toàn bộ
            if full_restart:
                await session.execute(sql_delete(NovelEntity).where(NovelEntity.novel_id == novel_id))
                from app.services.storage.file_storage import delete_novel_disk_files
                delete_novel_disk_files(novel_title)
                meta_dir = OUTPUT_ROOT / "06_Metadata" / folder_novel
                if meta_dir.exists():
                    shutil.rmtree(meta_dir, ignore_errors=True)

            await session.commit()

        # 6. Đồng bộ lại metadata cache
        try:
            from app.services.storage.metadata_cache import sync_novel_metadata
            await sync_novel_metadata(novel_id)
        except Exception:
            pass

        return {
            "status": "success",
            "message": f"Đã xóa toàn bộ dữ liệu & cache của {len(chapters)} chương, sẵn sàng cào & dịch lại từ đầu.",
            "reset_count": len(chapters)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi reset chương: {str(e)}")




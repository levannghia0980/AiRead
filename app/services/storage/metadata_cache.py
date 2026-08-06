"""
Metadata Cache Service v2 — Lưu chuẩn theo từng truyện từng chương

Cấu trúc thư mục:
    Output/06_Metadata/
    └── [Tên Truyện]/
        ├── entities.json       ← Toàn bộ thực thể CHUNG của truyện (gửi LLM khi dịch)
        ├── context.json        ← Bối cảnh truyện (genre, profile, title...)
        └── chapters/
            ├── 000001.json     ← corrections + entity_ids của riêng chương 1
            ├── 000002.json     ← corrections + entity_ids của riêng chương 2
            └── ...

Mục tiêu:
- entities.json = gửi cho LLM dịch để đồng bộ tên từ đầu đến cuối truyện
- chapters/XXXXXX.json = chỉ load entities/corrections của chương đó khi cần (nhanh)
- Không cần query DB chính (database.db ~30MB) mỗi lần dịch
"""
import os
import json
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.services.storage.file_storage import OUTPUT_ROOT, sanitize_filename

METADATA_FOLDER = "06_Metadata"


# ─────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────

def _get_novel_meta_dir(novel_title_rough: str) -> Path:
    """Trả về thư mục metadata của truyện, tự tạo nếu chưa có"""
    folder_novel = sanitize_filename(novel_title_rough or "Unknown_Novel")
    meta_dir = OUTPUT_ROOT / METADATA_FOLDER / folder_novel
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "chapters").mkdir(exist_ok=True)
    return meta_dir


def _entities_path(novel_title_rough: str) -> Path:
    """Path file entities.json chung của truyện"""
    return _get_novel_meta_dir(novel_title_rough) / "entities.json"


def _context_path(novel_title_rough: str) -> Path:
    """Path file context.json của truyện"""
    return _get_novel_meta_dir(novel_title_rough) / "context.json"


def _chapter_path(novel_title_rough: str, chapter_no: int) -> Path:
    """Path file JSON của từng chương (000001.json, 000002.json...)"""
    meta_dir = _get_novel_meta_dir(novel_title_rough)
    return meta_dir / "chapters" / f"{chapter_no:06d}.json"


# ─────────────────────────────────────────────
# Write / Read helpers
# ─────────────────────────────────────────────

def _write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ─────────────────────────────────────────────
# SYNC — Export DB chính → JSON cache
# ─────────────────────────────────────────────

async def sync_novel_metadata(novel_id: int) -> Dict[str, Any]:
    """
    Export toàn bộ metadata từ DB chính → JSON files.
    Gọi sau khi thay đổi entities/corrections/context.

    Kết quả:
        entities.json          — danh sách thực thể chung toàn truyện
        context.json           — bối cảnh (genre, profile)
        chapters/000001.json   — corrections + entity_ids riêng từng chương
    """
    from app.core.database import AsyncSessionLocal
    from app.models.schema import Novel, NovelEntity, ChapterEntityLink, ChapterCorrection, Chapter
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Novel).where(Novel.id == novel_id)
        res = await session.execute(stmt)
        novel = res.scalar_one_or_none()
        if not novel:
            return {"status": "error", "message": f"Không tìm thấy truyện ID {novel_id}"}

        novel_title = novel.title_rough or novel.title_raw

        # Lấy tất cả chương (id → chapter_no)
        stmt_ch = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_no)
        res_ch = await session.execute(stmt_ch)
        chapters = res_ch.scalars().all()
        chapter_map: Dict[int, int] = {ch.id: ch.chapter_no for ch in chapters}

        # Lấy tất cả entities của truyện
        stmt_ent = select(NovelEntity).where(NovelEntity.novel_id == novel_id).order_by(NovelEntity.id)
        res_ent = await session.execute(stmt_ent)
        entities = res_ent.scalars().all()
        entity_map: Dict[int, dict] = {}
        entities_list = []
        for e in entities:
            d = {
                "id": e.id,
                "chinese_name": e.chinese_name,
                "rough_translation": e.rough_translation,
                "entity_type": e.entity_type,
                "gender": e.gender,
                "role": e.role,
                "frequency_count": e.frequency_count,
            }
            entities_list.append(d)
            entity_map[e.id] = d

        # Lấy chapter_entity_links, group theo chapter_id
        stmt_links = (
            select(ChapterEntityLink)
            .join(Chapter, ChapterEntityLink.chapter_id == Chapter.id)
            .where(Chapter.novel_id == novel_id)
        )
        res_links = await session.execute(stmt_links)
        links = res_links.scalars().all()
        links_by_chapter: Dict[int, List[int]] = {}
        for lk in links:
            links_by_chapter.setdefault(lk.chapter_id, []).append(lk.entity_id)

        # Lấy corrections, group theo chapter_id
        stmt_corr = (
            select(ChapterCorrection)
            .join(Chapter, ChapterCorrection.chapter_id == Chapter.id)
            .where(Chapter.novel_id == novel_id)
        )
        res_corr = await session.execute(stmt_corr)
        corrections = res_corr.scalars().all()
        corr_by_chapter: Dict[int, List[dict]] = {}
        for c in corrections:
            corr_by_chapter.setdefault(c.chapter_id, []).append({
                "id": c.id,
                "wrong_text": c.wrong_text,
                "correct_text": c.correct_text,
            })

    # Ghi ra file JSON trong thread riêng để không block async loop
    def _write_all():
        # 1. entities.json — thực thể CHUNG toàn truyện
        _write_json(_entities_path(novel_title), {
            "novel_id": novel_id,
            "novel_title": novel_title,
            "total": len(entities_list),
            "entities": entities_list
        })

        # 2. context.json — bối cảnh truyện
        _write_json(_context_path(novel_title), {
            "novel_id": novel_id,
            "title_rough": novel_title,
            "genres": novel.genres or "",
            "context_profile": novel.context_profile or "",
            "author": novel.author or "",
            "status": novel.status or ""
        })

        # 3. chapters/XXXXXX.json — riêng từng chương
        for ch_id, ch_no in chapter_map.items():
            entity_ids = links_by_chapter.get(ch_id, [])
            ch_entities = [entity_map[eid] for eid in entity_ids if eid in entity_map]
            ch_corrections = corr_by_chapter.get(ch_id, [])
            # Chỉ ghi nếu chương có dữ liệu
            if ch_entities or ch_corrections:
                _write_json(_chapter_path(novel_title, ch_no), {
                    "chapter_id": ch_id,
                    "chapter_no": ch_no,
                    "entity_ids": entity_ids,
                    "entities": ch_entities,
                    "corrections": ch_corrections
                })

    await asyncio.to_thread(_write_all)

    return {
        "status": "success",
        "novel_id": novel_id,
        "entities_count": len(entities_list),
        "corrections_count": sum(len(v) for v in corr_by_chapter.values()),
        "chapters_count": len(chapter_map)
    }


# ─────────────────────────────────────────────
# READ — Đọc nhanh từ JSON cache
# ─────────────────────────────────────────────

def load_novel_entities_fast(novel_title_rough: str) -> List[Dict[str, Any]]:
    """
    Đọc nhanh TOÀN BỘ entities từ entities.json chung.
    Dùng khi cần gửi context đầy đủ cho LLM dịch (đồng bộ tên từ đầu đến cuối).
    """
    data = _read_json(_entities_path(novel_title_rough), {})
    return data.get("entities", [])


def load_chapter_entities_fast(novel_title_rough: str, chapter_no: int) -> List[Dict[str, Any]]:
    """
    Đọc nhanh entities của 1 chương từ chapters/XXXXXX.json.
    Dùng khi dịch 1 chương riêng lẻ — nhanh hơn load toàn bộ.
    """
    data = _read_json(_chapter_path(novel_title_rough, chapter_no), {})
    return data.get("entities", [])


def load_chapter_corrections_fast(novel_title_rough: str, chapter_no: int) -> List[Dict[str, Any]]:
    """
    Đọc nhanh corrections của 1 chương từ chapters/XXXXXX.json.
    """
    data = _read_json(_chapter_path(novel_title_rough, chapter_no), {})
    return data.get("corrections", [])


def load_novel_context_fast(novel_title_rough: str) -> Dict[str, str]:
    """
    Đọc nhanh context truyện (genre, profile...) từ context.json.
    """
    return _read_json(_context_path(novel_title_rough), {})


def load_chapter_data_fast(novel_title_rough: str, chapter_no: int) -> Dict[str, Any]:
    """
    Đọc toàn bộ data của 1 chương (entities + corrections) trong 1 lần đọc file.
    """
    return _read_json(_chapter_path(novel_title_rough, chapter_no), {
        "entities": [],
        "corrections": []
    })


# ─────────────────────────────────────────────
# INVALIDATE — Xóa cache khi restart/reset
# ─────────────────────────────────────────────

def invalidate_metadata(novel_title_rough: str):
    """
    Xóa toàn bộ JSON cache của truyện (khi restart toàn bộ).
    Xóa entities.json, context.json, và toàn bộ chapters/
    """
    folder_novel = sanitize_filename(novel_title_rough or "Unknown_Novel")
    meta_dir = OUTPUT_ROOT / METADATA_FOLDER / folder_novel
    if meta_dir.exists():
        try:
            shutil.rmtree(meta_dir, ignore_errors=True)
        except Exception:
            pass


def invalidate_chapter_metadata(novel_title_rough: str, chapter_no: int):
    """
    Xóa cache JSON của 1 chương (khi reset/restart chương đó).
    """
    ch_path = _chapter_path(novel_title_rough, chapter_no)
    if ch_path.exists():
        try:
            os.remove(str(ch_path))
        except Exception:
            pass


# ─────────────────────────────────────────────
# PARTIAL UPDATE — Cập nhật nhanh không sync toàn bộ
# ─────────────────────────────────────────────

def update_entity_in_cache(novel_title_rough: str, entity_id: int, new_translation: str):
    """
    Cập nhật tên dịch của 1 entity trong entities.json và tất cả chapters/*.json.
    Không cần sync lại toàn bộ từ DB — dùng ngay sau khi đổi tên nhân vật.
    """
    # Cập nhật entities.json chung
    ent_path = _entities_path(novel_title_rough)
    data = _read_json(ent_path, {})
    if data and "entities" in data:
        for ent in data["entities"]:
            if ent.get("id") == entity_id:
                ent["rough_translation"] = new_translation
        _write_json(ent_path, data)

    # Cập nhật tất cả chapters/*.json chứa entity này
    meta_dir = _get_novel_meta_dir(novel_title_rough)
    chapters_dir = meta_dir / "chapters"
    if chapters_dir.exists():
        for ch_file in sorted(chapters_dir.glob("*.json")):
            ch_data = _read_json(ch_file, {})
            modified = False
            for ent in ch_data.get("entities", []):
                if ent.get("id") == entity_id:
                    ent["rough_translation"] = new_translation
                    modified = True
            if modified:
                _write_json(ch_file, ch_data)


# ─────────────────────────────────────────────
# Public helpers (dùng trong novel_router)
# ─────────────────────────────────────────────

def get_metadata_entities_path(novel_title_rough: str) -> Path:
    """Kiểm tra entities.json đã tồn tại chưa (để auto-sync)"""
    return _entities_path(novel_title_rough)


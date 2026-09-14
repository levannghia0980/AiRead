import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import asyncio
from app.core.database import AsyncSessionLocal
from app.models.schema import Novel, Chapter, ChapterVersion
from app.services.preprocessing.dichhan.llm_extractor import extract_batch_entities_direct_llm
from sqlalchemy import select

async def run_test(novel_id: int, num_chapters: int = 4):
    async with AsyncSessionLocal() as session:
        novel = (await session.execute(select(Novel).filter(Novel.id == novel_id))).scalar_one_or_none()
        if not novel:
            print(f"Novel ID {novel_id} không tồn tại!")
            return

        print(f"==================================================")
        print(f"Kiểm tra bóc tách thực thể cho bộ truyện: {novel.title_raw} ({novel.title_rough})")
        print(f"Novel ID: {novel_id}")
        print(f"==================================================")

        chaps = (await session.execute(
            select(Chapter)
            .filter(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_no.asc())
            .limit(num_chapters)
        )).scalars().all()

        combined_texts = []
        for c in chaps:
            v = (await session.execute(
                select(ChapterVersion)
                .filter(ChapterVersion.chapter_id == c.id, ChapterVersion.version_type == "RAW")
            )).scalar_one_or_none()
            raw_c = v.content if v and v.content else ""
            if not raw_c:
                # Tìm bất kỳ version nào
                v_any = (await session.execute(
                    select(ChapterVersion)
                    .filter(ChapterVersion.chapter_id == c.id)
                )).scalars().first()
                raw_c = v_any.content if v_any and v_any.content else ""
            combined_texts.append(f"<chapter_{c.chapter_no} title=\"{c.title_raw}\">\n{raw_c[:3500]}\n</chapter_{c.chapter_no}>")

    full_batch_text = "\n\n".join(combined_texts)
    print(f"Độ dài văn bản gửi lên LLM: {len(full_batch_text)} ký tự (~{len(full_batch_text)//4} tokens)")

    start_t = asyncio.get_event_loop().time()
    entities = await extract_batch_entities_direct_llm(full_batch_text)
    duration = asyncio.get_event_loop().time() - start_t

    print(f"\n✅ Hoàn thành bóc tách trong: {duration:.2f}s | Số lượng thực thể: {len(entities)}")
    print("-" * 70)
    
    # Gom nhóm theo entity_type
    by_type = {}
    for e in entities:
        t = e.get("entity_type", "OTHER")
        by_type.setdefault(t, []).append(e)

    for etype, elist in sorted(by_type.items()):
        print(f"\n📂 [{etype}] ({len(elist)} thực thể):")
        for e in elist:
            cn = e.get("chinese_name", "")
            vn = e.get("vietnamese_name", "")
            role = e.get("role", "")
            eval_tag = e.get("evaluation", "")
            print(f"   • {cn} -> {vn} | Vai trò: {role} [{eval_tag}]")

if __name__ == "__main__":
    # Thử trên Novel 10 (Cầu Ma) hoặc Novel 3 (Tôi có một thân bị động kỹ)
    target_id = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(run_test(target_id, 3))

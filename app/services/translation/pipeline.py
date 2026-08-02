import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, Novel
from app.services.preprocessing.dichhan.evidence_collector import collect_batch_entities
from app.services.preprocessing.dichhan.llm_extractor import process_2branch_evidence_via_llm
from app.api.novel_router import update_novel_entity_and_apply, UpdateNovelEntityRequest
from app.services.translation.rawt.llm_translator import translate_batch_llm
from app.services.translation.contextt.llm_context_editor import edit_context_batch_llm
from app.api.translation_router import add_system_log

async def _ensure_chapters_crawled(batch: List[int]):
    """Đảm bảo tất cả các chương trong batch đã có văn bản RAW/GG sẵn sàng trên đĩa"""
    import os
    from app.models.schema import ChapterVersion
    async with AsyncSessionLocal() as session:
        for cid in batch:
            stmt = select(Chapter).where(Chapter.id == cid)
            res = await session.execute(stmt)
            ch = res.scalar_one_or_none()
            if not ch:
                continue

            # Kiểm tra xem bản RAW và GG có tồn tại cả trong DB và đĩa không
            stmt_raw = select(ChapterVersion).where(
                ChapterVersion.chapter_id == cid,
                ChapterVersion.version_type == "RAW"
            )
            res_raw = await session.execute(stmt_raw)
            v_raw = res_raw.scalar_one_or_none()

            stmt_gg = select(ChapterVersion).where(
                ChapterVersion.chapter_id == cid,
                ChapterVersion.version_type == "GG"
            )
            res_gg = await session.execute(stmt_gg)
            v_gg = res_gg.scalar_one_or_none()

            raw_exists = v_raw and v_raw.file_path and os.path.exists(v_raw.file_path)
            gg_exists = v_gg and v_gg.file_path and os.path.exists(v_gg.file_path)

            if not (raw_exists and gg_exists):
                try:
                    from app.services.preprocessing.crawler.pipeline import process_single_chapter_crawl
                    msg = f"🌐 [1/3 TIỀN XỬ LÝ] Tự động cào văn bản cho chương ID {cid} (Chương {ch.chapter_no})..."
                    print(msg)
                    add_system_log(msg, "pre")
                    await process_single_chapter_crawl(cid)
                except Exception as e:
                    err_msg = f"❌ [1/3 TIỀN XỬ LÝ] Lỗi cào chương ID {cid}: {e}"
                    print(err_msg)
                    add_system_log(err_msg, "error")


async def cleanup_failed_chapters(chapter_ids: List[int], novel_id: int):
    """
    Dọn dẹp sạch sẽ dữ liệu của các chương bị lỗi hoặc bị hủy giữa chừng:
    - Xóa ChapterVersion loại FINAL
    - Xóa file vật lý tương ứng trên đĩa
    - Xóa ChapterCorrection
    - Xóa ChapterEntityLink
    - Xóa các NovelEntity mồ côi (không còn liên kết với chương nào khác trong novel)
    - Reset status của Chapter về CRAWLED (nếu có bản RAW) hoặc WAIT (nếu chưa cào)
    """
    import os
    from app.models.schema import ChapterVersion, ChapterCorrection, ChapterEntityLink, NovelEntity
    from sqlalchemy import delete
    
    print(f"🧹 Bắt đầu dọn dẹp dữ liệu lỗi/hủy cho các chương: {chapter_ids}")
    add_system_log(f"🧹 Dọn dẹp dữ liệu dở dang cho các chương: {chapter_ids}", "warning")
    
    async with AsyncSessionLocal() as session:
        for cid in chapter_ids:
            # 1. Lấy ChapterVersion FINAL và xóa file vật lý
            stmt_ver = select(ChapterVersion).where(
                ChapterVersion.chapter_id == cid,
                ChapterVersion.version_type == "FINAL"
            )
            res_ver = await session.execute(stmt_ver)
            ver = res_ver.scalar_one_or_none()
            if ver:
                if ver.file_path and os.path.exists(ver.file_path):
                    try:
                        os.remove(ver.file_path)
                        print(f"  - Đã xóa file: {ver.file_path}")
                    except Exception as e:
                        print(f"  - Lỗi khi xóa file {ver.file_path}: {e}")
                await session.delete(ver)

            # 2. Xóa ChapterCorrection
            await session.execute(delete(ChapterCorrection).where(ChapterCorrection.chapter_id == cid))

            # 3. Xóa ChapterEntityLink
            await session.execute(delete(ChapterEntityLink).where(ChapterEntityLink.chapter_id == cid))

            # 4. Kiểm tra các phiên bản khác (RAW, GG) để phục hồi status của Chapter
            stmt_vers = select(ChapterVersion.version_type).where(ChapterVersion.chapter_id == cid)
            res_vers = await session.execute(stmt_vers)
            version_types = res_vers.scalars().all()

            stmt_chap = select(Chapter).where(Chapter.id == cid)
            res_chap = await session.execute(stmt_chap)
            chap = res_chap.scalar_one_or_none()
            if chap:
                if "RAW" in version_types:
                    chap.status = "CRAWLED"
                else:
                    chap.status = "WAIT"
                chap.error_message = ""

        # 5. Tìm và xóa NovelEntity mồ côi
        stmt_orphans = select(NovelEntity).where(
            NovelEntity.novel_id == novel_id,
            ~NovelEntity.id.in_(select(ChapterEntityLink.entity_id))
        )
        res_orphans = await session.execute(stmt_orphans)
        orphans = res_orphans.scalars().all()
        for orphan in orphans:
            print(f"  - Đã xóa thực thể mồ côi: {orphan.chinese_name} ({orphan.rough_translation})")
            await session.delete(orphan)

        await session.commit()
    print("🧹 Hoàn tất dọn dẹp sạch sẽ.")

async def _process_evidence_and_save(
    novel_id: int,
    batch: List[int],
    enable_llm_extract: bool = True,
    enable_names_dict: bool = True,
    enable_gg_corrections: bool = True
):
    """BƯỚC 1: Tiền xử lý (Bóc tách thực thể & Gom lỗi tự động cho batch)"""
    msg_start = f"🛠️ [1/3 TIỀN XỬ LÝ] Bắt đầu gom từ nghi vấn & bóc tách thực thể cho lô {batch}..."
    print(msg_start)
    add_system_log(msg_start, "pre")
    
    await _ensure_chapters_crawled(batch)
    if not enable_llm_extract:
        msg_skip = f"👌 [1/3 TIỀN XỬ LÝ] Đã tắt AI bóc tách thực thể/lỗi tự động cho lô {batch}."
        print(msg_skip)
        add_system_log(msg_skip, "pre")
        return

    evidence_payload = await collect_batch_entities(batch)
    
    if evidence_payload["branch_1_ner_candidates"] or evidence_payload["branch_2_gg_errors_to_clean"]:
        try:
            llm_res = await process_2branch_evidence_via_llm(evidence_payload)
            entities = llm_res.get("entities", [])
            corrections = llm_res.get("corrections", [])
            
            # Áp dụng Entities nếu bật Từ điển Thực thể
            if enable_names_dict and entities:
                from app.models.schema import ChapterEntityLink
                for ent in entities:
                    ch_name = ent.get("chinese_name")
                    vi_trans = ent.get("vietnamese_name", ent.get("rough_translation", ""))
                    e_type = ent.get("entity_type", "NAME")
                    if not ch_name or not vi_trans:
                        continue
                        
                    req = UpdateNovelEntityRequest(
                        chinese_name=ch_name,
                        rough_translation=vi_trans,
                        entity_type=e_type
                    )
                    try:
                        res_save = await update_novel_entity_and_apply(novel_id, req)
                        ent_id = res_save.get("entity_id") if isinstance(res_save, dict) else None
                        
                        if ent_id:
                            async with AsyncSessionLocal() as session:
                                for cid in batch:
                                    stmt_link = select(ChapterEntityLink).where(
                                        ChapterEntityLink.chapter_id == cid,
                                        ChapterEntityLink.entity_id == ent_id
                                    )
                                    link_res = await session.execute(stmt_link)
                                    if not link_res.scalar_one_or_none():
                                        session.add(ChapterEntityLink(chapter_id=cid, entity_id=ent_id))
                                await session.commit()
                    except Exception as e:
                        print(f"[PREPROCESS] Lỗi update entity {ent}: {e}")
                    
            # Áp dụng Corrections nếu bật Sửa lỗi GG (Lưu riêng vào ChapterCorrection theo từng chương trong batch)
            if enable_gg_corrections and corrections:
                from app.models.schema import ChapterCorrection
                async with AsyncSessionLocal() as session:
                    for corr in corrections:
                        gg_err = corr.get("gg_error")
                        corr_vi = corr.get("correct_vietnamese")
                        if not gg_err or not corr_vi:
                            continue
                        for cid in batch:
                            # Tránh lưu trùng
                            stmt_exist = select(ChapterCorrection).where(
                                ChapterCorrection.chapter_id == cid,
                                ChapterCorrection.wrong_text == gg_err
                            )
                            exist_res = await session.execute(stmt_exist)
                            if not exist_res.scalar_one_or_none():
                                session.add(ChapterCorrection(
                                    chapter_id=cid,
                                    wrong_text=gg_err,
                                    correct_text=corr_vi
                                ))
                    await session.commit()

            msg_done = f"✨ [1/3 TIỀN XỬ LÝ] Đã trích xuất {len(entities)} tên & {len(corrections)} lỗi GG cho lô {batch}. Đã làm sạch & lưu CSDL!"
            print(msg_done)
            add_system_log(msg_done, "pre")
        except Exception as e:
            msg_err = f"⚠️ [1/3 TIỀN XỬ LÝ] Lỗi trích xuất LLM cho lô {batch}: {e}"
            print(msg_err)
            add_system_log(msg_err, "warning")
    else:
        msg_none = f"👌 [1/3 TIỀN XỬ LÝ] Lô {batch} không có từ nghi vấn hoặc lỗi GG mới."
        print(msg_none)
        add_system_log(msg_none, "pre")

async def _translate_batch(translation_flow: str, batch: List[int], enable_names_dict: bool = True, **kwargs):
    """BƯỚC 2: Dịch AI theo 2 kiểu phân định rõ ràng (RAWT vs CONTEXTT)"""
    is_rawt = translation_flow.lower() == "rawt"
    flow_name = "1. Dịch Trực Tiếp từ RAW (RAWT)" if is_rawt else "2. Biên Tập Văn Phong GG (CONTEXTT)"
    msg_trans = f"🚀 [2/3 DỊCH AI] Gửi LLM xử lý lô {batch} ({flow_name})..."
    print(msg_trans)
    add_system_log(msg_trans, "purple")
    
    try:
        from app.services.postprocessing.post_processor import process_and_split_batch
        enable_unblock = kwargs.get("enable_unblock", True)
        if is_rawt:
            res = await translate_batch_llm(batch, enable_names_dict=enable_names_dict, enable_unblock=enable_unblock)
            ver_type = "LLM"
        else:
            res = await edit_context_batch_llm(batch, enable_names_dict=enable_names_dict, enable_unblock=enable_unblock)
            ver_type = "CONTEXTT"
            
        if "status" in res and res["status"] == "success":
            msg_post = f"💾 [3/3 HẬU XỬ LÝ] Đang giải mã §BDY_XXXX§ & bọc đánh dấu cho lô {batch}..."
            print(msg_post)
            add_system_log(msg_post, "post")
            
            saved_files = await process_and_split_batch(
                novel_id=res["novel_id"],
                translated_text_masked=res["translated_text_masked"],
                mapping_table=res.get("mapping_table", {}),
                chapter_map=res["chapter_map"],
                version_type=ver_type
            )
            res["saved_files"] = saved_files
            
            msg_ok = f"✅ [HOÀN THÀNH LÔ] Lô {batch} đã lưu thành công vào CSDL & Ổ đĩa ({len(saved_files)} file)!"
            print(msg_ok)
            add_system_log(msg_ok, "success")
            return res
        else:
            err_res = f"❌ [2/3 DỊCH AI LỖI] Lô {batch} gặp lỗi: {res.get('error') or res.get('message') or res}"
            print(err_res)
            add_system_log(err_res, "error")
            return res
    except Exception as e:
        err_ex = f"❌ [2/3 DỊCH AI LỖI EXCEPTION] Lô {batch}: {e}"
        print(err_ex)
        add_system_log(err_ex, "error")
        return {"error": str(e), "batch": batch}


_PIPELINE_LOCK = asyncio.Lock()

async def run_translation_batch_pipeline(
    novel_id: int,
    translation_flow: str, # "rawt" (Dịch RAW Hán) hoặc "contextt" (Biên tập GG)
    batch_size: int = 3,
    delay_sec: float = 0.5,
    start_chapter: int = 0,
    end_chapter: int = 0,
    enable_llm_extract: bool = True,
    enable_names_dict: bool = True,
    enable_gg_corrections: bool = True,
    **kwargs
):
    """
    Pipeline dịch gối đầu tuần tự (Sequential Overlapping Pipeline):
    - Phân định rõ 2 kiểu dịch: RAWT vs CONTEXTT
    - Tiền xử lý gối đầu lô N+1 trong khi đang chạy Dịch AI cho lô N.
    """
    if _PIPELINE_LOCK.locked():
        return {
            "status": "warning",
            "message": "Đang có luồng dịch đang chạy tuần tự. Vui lòng chờ hoàn tất đợt dịch hiện tại."
        }

    async with _PIPELINE_LOCK:
        config_msg = (
            f"⚙️ [CẤU HÌNH TIẾN TRÌNH DỊCH] Novel ID: {novel_id} | "
            f"Luồng: {translation_flow.upper()} | "
            f"Số chương/Lô (Batch): {batch_size} | "
            f"Delay giữa các lô: {delay_sec}s | "
            f"Phạm vi: Chương {start_chapter if start_chapter > 0 else 'Đầu'} -> {end_chapter if end_chapter > 0 else 'Cuối'}"
        )
        print(config_msg)
        add_system_log(config_msg, "info")

        active_current_batch = []
        active_next_batch = []
        try:
            async with AsyncSessionLocal() as session:
                # 1. Tự động phát hiện chương chưa dịch thấp nhất nếu start_chapter <= 0
                actual_start_chapter = start_chapter or 0
                if actual_start_chapter <= 0:
                    stmt_find = select(Chapter.chapter_no).where(
                        Chapter.novel_id == novel_id,
                        ~Chapter.status.in_(["FINAL_DONE", "DONE", "TRANSLATED"])
                    ).order_by(Chapter.chapter_no.asc()).limit(1)
                    res_find = await session.execute(stmt_find)
                    lowest_untranslated = res_find.scalar_one_or_none()
                    if lowest_untranslated:
                        actual_start_chapter = lowest_untranslated
                        add_system_log(f"🔍 Tự động phát hiện chương chưa dịch thấp nhất: Chương {actual_start_chapter}", "info")
                    else:
                        add_system_log("✅ Tất cả các chương đã được dịch hoàn tất.", "success")
                        return {"status": "completed", "total_batches": 0, "total_chapters": 0, "results": []}

                # 2. Query danh sách chương chưa dịch trong phạm vi chỉ định
                stmt = select(Chapter.id).where(
                    Chapter.novel_id == novel_id,
                    ~Chapter.status.in_(["FINAL_DONE", "DONE", "TRANSLATED"])
                )
                if actual_start_chapter > 0:
                    stmt = stmt.where(Chapter.chapter_no >= actual_start_chapter)
                if end_chapter > 0:
                    stmt = stmt.where(Chapter.chapter_no <= end_chapter)
                    
                stmt = stmt.order_by(Chapter.chapter_no.asc())
                res = await session.execute(stmt)
                chapter_ids = res.scalars().all()
                
            if not chapter_ids:
                add_system_log("✅ Không còn chương nào chưa dịch trong khoảng chỉ định.", "success")
                return {"status": "completed", "total_batches": 0, "total_chapters": 0, "results": []}

            # Phân lô (Batching)
            batches = [chapter_ids[i:i + batch_size] for i in range(0, len(chapter_ids), batch_size)]
            results = []
            
            # BƯỚC 1: Tiền xử lý cho Batch ĐẦU TIÊN (Lô 1)
            init_msg = f"📌 [1/3 TIỀN XỬ LÝ LÔ 1] Khởi chạy tiền xử lý cho Lô 1/{len(batches)} (Chương ID: {batches[0]})..."
            print(init_msg)
            add_system_log(init_msg, "pre")
            
            active_current_batch = batches[0]
            await _process_evidence_and_save(
                novel_id, batches[0],
                enable_llm_extract=enable_llm_extract,
                enable_names_dict=enable_names_dict,
                enable_gg_corrections=enable_gg_corrections
            )
            
            # VÒNG LẶP TUẦN TỰ GỐI ĐẦU
            for idx, current_batch in enumerate(batches):
                batch_num = idx + 1
                active_current_batch = current_batch
                
                next_batch_idx = idx + 1
                next_batch = batches[next_batch_idx] if next_batch_idx < len(batches) else None
                active_next_batch = next_batch or []
                
                start_batch_msg = f"🚀 [LÔ {batch_num}/{len(batches)}] Tiến hành dịch Lô {batch_num} (Chương ID: {current_batch})"
                print(start_batch_msg)
                add_system_log(start_batch_msg, "purple")
                
                tasks = []
                # Task 1: Dịch AI Batch N
                tasks.append(asyncio.create_task(_translate_batch(
                    translation_flow, current_batch,
                    enable_names_dict=enable_names_dict,
                    enable_unblock=kwargs.get("enable_unblock", True)
                )))
                
                # Task 2: Tiền xử lý gối đầu Batch N+1
                if next_batch:
                    overlap_msg = f"🔄 [GỐI ĐẦU SONG SONG] Khởi chạy tiền xử lý trước cho Lô {batch_num + 1}/{len(batches)} (Chương ID: {next_batch})..."
                    print(overlap_msg)
                    add_system_log(overlap_msg, "pre")
                    tasks.append(asyncio.create_task(_process_evidence_and_save(
                        novel_id, next_batch,
                        enable_llm_extract=enable_llm_extract,
                        enable_names_dict=enable_names_dict,
                        enable_gg_corrections=enable_gg_corrections
                    )))
                    
                gathered_results = await asyncio.gather(*tasks)
                translate_res = gathered_results[0]
                results.append(translate_res)
                
                if "error" in translate_res:
                    err_batch = f"❌ [LỖI BATCH {batch_num}] Chi tiết: {translate_res['error']}"
                    print(err_batch)
                    add_system_log(err_batch, "error")
                    raise ValueError(translate_res['error'])
                else:
                    done_batch = f"🎉 [HOÀN THÀNH BATCH {batch_num}] Lô {batch_num} dịch thành công!"
                    print(done_batch)
                    add_system_log(done_batch, "success")
                
                active_next_batch = []
                
                if idx < len(batches) - 1 and delay_sec > 0:
                    delay_msg = f"⏳ Tạm nghỉ {delay_sec:.1f}s trước khi chuyển sang Lô {batch_num + 1}..."
                    print(delay_msg)
                    add_system_log(delay_msg, "warning")
                    await asyncio.sleep(delay_sec)
                    
            return {
                "status": "completed",
                "total_batches": len(batches),
                "total_chapters": len(chapter_ids),
                "results": results
            }
        except (Exception, asyncio.CancelledError) as e:
            cleanup_ids = list(set(active_current_batch + active_next_batch))
            if cleanup_ids:
                cleanup_msg = f"🛑 Phát hiện lỗi hoặc yêu cầu dừng. Bắt đầu dọn dẹp các chương: {cleanup_ids}..."
                print(cleanup_msg)
                add_system_log(cleanup_msg, "error")
                await cleanup_failed_chapters(cleanup_ids, novel_id)
            raise e

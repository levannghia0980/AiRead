import asyncio
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, Novel, NovelEntity, ChapterEntityLink, ChapterVersion
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
                    msg = f"🌐 [1/3 TIỀN XỬ LÝ] Tự động cào văn bản cho Chương {ch.chapter_no}..."
                    print(msg)
                    add_system_log(msg, "pre")
                    await process_single_chapter_crawl(cid)
                except Exception as e:
                    err_msg = f"❌ [1/3 TIỀN XỬ LÝ] Lỗi cào chương {ch.chapter_no}: {e}"
                    print(err_msg)
                    add_system_log(err_msg, "error")


async def _get_chap_numbers(batch: List[int]) -> str:
    """Lấy chuỗi hiển thị số chương từ danh sách chapter_id"""
    if not batch:
        return ""
    async with AsyncSessionLocal() as session:
        stmt = select(Chapter.chapter_no).where(Chapter.id.in_(batch)).order_by(Chapter.chapter_no.asc())
        res = await session.execute(stmt)
        chap_nos = res.scalars().all()
        if not chap_nos:
            return str(batch)
        if len(chap_nos) == 1:
            return str(chap_nos[0])
        if chap_nos[-1] - chap_nos[0] == len(chap_nos) - 1:
            return f"{chap_nos[0]}->{chap_nos[-1]}"
        return ", ".join(str(n) for n in chap_nos)


async def cleanup_failed_chapters(chapter_ids: List[int], novel_id: int, max_retries: int = 3):
    """
    Dọn dẹp an toàn cho các chương trong lô bị lỗi hoặc bị hủy giữa chừng:
    - Nếu chương CHƯA hoàn tất (không phải FINAL_DONE), reset status về CRAWLED (hoặc WAIT).
    - TUYỆT ĐỐI không xóa NovelEntity (từ điển nhân vật/thuật ngữ) hay xóa file FINAL của các chương đã hoàn tất trước đó.
    """
    import os
    from app.models.schema import ChapterVersion, Chapter
    
    if not chapter_ids:
        return
        
    print(f"🧹 Dọn dẹp an toàn cho các chương ID: {chapter_ids}")
    
    for attempt in range(max_retries):
        try:
            async with AsyncSessionLocal() as session:
                for cid in chapter_ids:
                    stmt_chap = select(Chapter).where(Chapter.id == cid)
                    res_chap = await session.execute(stmt_chap)
                    chap = res_chap.scalar_one_or_none()
                    if chap and chap.status != "FINAL_DONE":
                        stmt_vers = select(ChapterVersion.version_type).where(ChapterVersion.chapter_id == cid)
                        res_vers = await session.execute(stmt_vers)
                        version_types = res_vers.scalars().all()
                        if "RAW" in version_types:
                            chap.status = "CRAWLED"
                        else:
                            chap.status = "WAIT"
                        chap.error_message = ""
                await session.commit()
            print("🧹 Hoàn tất dọn dẹp an toàn.")
            return
        except Exception as err:
            if attempt < max_retries - 1:
                print(f"⚠️ Lỗi dọn dẹp (thử lại {attempt + 1}/{max_retries}): {err}")
                await asyncio.sleep(1.0 * (attempt + 1))
            else:
                print(f"❌ Không thể hoàn tất dọn dẹp sau {max_retries} lần thử: {err}")

async def _process_evidence_and_save(
    novel_id: int,
    batch: List[int],
    enable_llm_extract: bool = True,
    enable_names_dict: bool = True,
    enable_gg_corrections: bool = True
):
    """BƯỚC 1: Tiền xử lý (Bóc tách thực thể & Gom lỗi tự động cho batch)"""
    chap_nos = await _get_chap_numbers(batch)
    msg_start = f"🛠️ [1/3 TIỀN XỬ LÝ] Bắt đầu gom từ nghi vấn & bóc tách thực thể cho lô Chương {chap_nos}..."
    print(msg_start)
    add_system_log(msg_start, "pre")
    
    await _ensure_chapters_crawled(batch)
    if not enable_llm_extract:
        msg_skip = f"👌 [1/3 TIỀN XỬ LÝ] Đã tắt AI bóc tách thực thể/lỗi tự động cho lô Chương {chap_nos}."
        print(msg_skip)
        add_system_log(msg_skip, "pre")
        return

    evidence_payload = await collect_batch_entities(batch)
    from app.models.schema import ChapterEntityLink
    
    if evidence_payload["branch_1_ner_candidates"] or evidence_payload["branch_2_gg_errors_to_clean"]:
        try:
            llm_res = await process_2branch_evidence_via_llm(evidence_payload)
            raw_llm_entities = list(llm_res.get("entities", []))
            entities = llm_res.get("entities", [])
            corrections = llm_res.get("corrections", [])
            
            # Validate: Ép tên đã có trong DB → bỏ qua, chỉ chấp nhận tên MỚI từ LLM
            existing_db = evidence_payload.get("existing_db_entities", {})
            validated_entities = []
            for ent in entities:
                ch_name = ent.get("chinese_name")
                if ch_name and ch_name in existing_db:
                    # Entity ĐÃ CÓ trong DB → skip, không ghi đè
                    print(f"[PREPROCESS] ⏭️ Bỏ qua entity đã có trong DB: {ch_name} = {existing_db[ch_name].get('vietnamese_name', '?')}")
                    continue
                validated_entities.append(ent)
            
            skipped_count = len(entities) - len(validated_entities)
            if skipped_count > 0:
                msg_skip_ent = f"[PREPROCESS] 🛡️ Đã bảo vệ {skipped_count} entity đã có trong DB, chỉ chấp nhận {len(validated_entities)} entity MỚI từ LLM."
                print(msg_skip_ent)
                add_system_log(msg_skip_ent, "pre")
            entities = validated_entities
            
            # Áp dụng Entities nếu bật Từ điển Thực thể
            if enable_names_dict and entities:
                from app.models.schema import ChapterEntityLink
                for ent in entities:
                    ch_name = ent.get("chinese_name")
                    vi_trans = ent.get("vietnamese_name", ent.get("rough_translation", ""))
                    e_type = ent.get("entity_type", "NAME")
                    gender = ent.get("gender")
                    role = ent.get("role")
                        
                    req = UpdateNovelEntityRequest(
                        chinese_name=ch_name,
                        rough_translation=vi_trans,
                        entity_type=e_type,
                        gender=gender,
                        role=role
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
                                    if not link_res.scalars().first():
                                        session.add(ChapterEntityLink(chapter_id=cid, entity_id=ent_id))
                                await session.commit()
                    except Exception as e:
                        print(f"[PREPROCESS] Lỗi update entity {ent}: {e}")
                    
            # Lưu ChapterCorrection vào CSDL và áp dụng làm sạch file GG Text
            if enable_gg_corrections and corrections:
                import os
                from app.models.schema import ChapterCorrection, ChapterVersion
                async with AsyncSessionLocal() as session:
                    for cid in batch:
                        for corr in corrections:
                            gg_err = corr.get("gg_error")
                            corr_vi = corr.get("correct_vietnamese")
                            if gg_err and corr_vi:
                                stmt_c = select(ChapterCorrection).where(
                                    ChapterCorrection.chapter_id == cid,
                                    ChapterCorrection.wrong_text == gg_err
                                )
                                res_c = await session.execute(stmt_c)
                                existing_c = res_c.scalar_one_or_none()
                                if not existing_c:
                                    session.add(ChapterCorrection(
                                        chapter_id=cid,
                                        wrong_text=gg_err,
                                        correct_text=corr_vi
                                    ))
                        
                        stmt_gg = select(ChapterVersion).where(
                            ChapterVersion.chapter_id == cid,
                            ChapterVersion.version_type == "GG"
                        )
                        res_gg = await session.execute(stmt_gg)
                        ver_gg = res_gg.scalars().first()
                        
                        if ver_gg:
                            gg_text = ""
                            if ver_gg.file_path and os.path.exists(ver_gg.file_path):
                                with open(ver_gg.file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    gg_text = f.read()
                            elif ver_gg.content:
                                gg_text = ver_gg.content
                                    
                            if gg_text:
                                original_text = gg_text
                                # Sắp xếp từ khóa dài thay trước, ngắn thay sau (Vd: "Mo Yayi" trước, "Yayi" sau)
                                sorted_corrections = sorted(
                                    corrections, 
                                    key=lambda x: len(x.get("gg_error", "") or ""), 
                                    reverse=True
                                )
                                for corr in sorted_corrections:
                                    gg_err = corr.get("gg_error")
                                    corr_vi = corr.get("correct_vietnamese")
                                    if gg_err and corr_vi:
                                        pattern = re.compile(
                                            r'(?<![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])'
                                            + re.escape(gg_err)
                                            + r'(?![a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF])',
                                            re.IGNORECASE
                                        )
                                        gg_text = pattern.sub(corr_vi, gg_text)
                                
                                if gg_text != original_text:
                                    ver_gg.content = gg_text
                                    if ver_gg.file_path:
                                        with open(ver_gg.file_path, "w", encoding="utf-8") as f:
                                            f.write(gg_text)
                    await session.commit()

            # Link entities với chapters trong batch (để làm sạch cache per-chapter)
            if raw_llm_entities:
                async with AsyncSessionLocal() as session:
                    all_ch_names = [e["chinese_name"] for e in raw_llm_entities if e.get("chinese_name")]
                    stmt_ents = select(NovelEntity).where(
                        NovelEntity.novel_id == novel_id,
                        NovelEntity.chinese_name.in_(all_ch_names)
                    )
                    res_ents = await session.execute(stmt_ents)
                    ent_objs = res_ents.scalars().all()
                    
                    for ent_obj in ent_objs:
                        for cid in batch:
                            stmt_link = select(ChapterEntityLink).where(
                                ChapterEntityLink.chapter_id == cid,
                                ChapterEntityLink.entity_id == ent_obj.id
                            )
                            res_link = await session.execute(stmt_link)
                            if not res_link.scalar_one_or_none():
                                session.add(ChapterEntityLink(chapter_id=cid, entity_id=ent_obj.id))
                    await session.commit()

            # Sync lại metadata JSON cache sau khi lưu entities + corrections
            try:
                from app.services.storage.metadata_cache import sync_novel_metadata
                await sync_novel_metadata(novel_id)
                print(f"[PREPROCESS] 💾 Đã sync metadata cache cho truyện ID {novel_id}")
            except Exception as _cache_err:
                print(f"[PREPROCESS] ⚠️ Không thể sync metadata cache: {_cache_err}")

            msg_done = f"✨ [1/3 TIỀN XỬ LÝ] Đã trích xuất {len(entities)} tên & {len(corrections)} lỗi GG cho lô Chương {chap_nos}. Đã làm sạch & lưu CSDL!"
            print(msg_done)
            add_system_log(msg_done, "pre")
        except Exception as e:
            msg_err = f"⚠️ [1/3 TIỀN XỬ LÝ] Lỗi trích xuất LLM cho lô Chương {chap_nos}: {e}"
            print(msg_err)
            add_system_log(msg_err, "warning")
    else:
        msg_none = f"👌 [1/3 TIỀN XỬ LÝ] Lô Chương {chap_nos} không có từ nghi vấn hoặc lỗi GG mới."
        print(msg_none)
        add_system_log(msg_none, "pre")

async def _translate_batch(translation_flow: str, batch: List[int], enable_names_dict: bool = True, **kwargs):
    """BƯỚC 2: Dịch AI theo 2 kiểu phân định rõ ràng (RAWT vs CONTEXTT)"""
    chap_nos = await _get_chap_numbers(batch)
    is_rawt = translation_flow.lower() == "rawt"
    flow_name = "1. Dịch Trực Tiếp từ RAW (RAWT)" if is_rawt else "2. Biên Tập Văn Phong GG (CONTEXTT)"
    msg_trans = f"🚀 [2/3 DỊCH AI] Gửi LLM xử lý lô Chương {chap_nos} ({flow_name})..."
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
            # === LƯU NGAY KẾT QUẢ LLM GỐC TRẢ VỀ VÀO Output/03_DichAI_LLM TRƯỚC KHI SANG HẬU XỬ LÝ ===
            try:
                import os
                from app.services.storage.file_storage import sanitize_filename
                from app.services.unblock.unblock_pipeline import unmask_text_with_dictionary
                
                async with AsyncSessionLocal() as session:
                    stmt_n = select(Novel).where(Novel.id == res["novel_id"])
                    res_n = await session.execute(stmt_n)
                    novel_obj = res_n.scalar_one_or_none()
                    novel_title = novel_obj.title_rough if (novel_obj and novel_obj.title_rough) else (novel_obj.title_raw if novel_obj else "Novel")

                novel_folder = sanitize_filename(novel_title)
                llm_out_dir = os.path.join(r"D:\NENGHIA0980\AIREAD\Output\03_DichAI_LLM", novel_folder)
                os.makedirs(llm_out_dir, exist_ok=True)

                res_chap_nos = sorted(list(res["chapter_map"].values()))
                batch_name = f"batch_ch{'_'.join(map(str, res_chap_nos))}.txt"
                raw_llm_path = os.path.join(llm_out_dir, batch_name)

                # Unmask giải mã sơ bộ để đọc tiếng Việt (bật nâng cấp sắc văn cho luồng CONTEXTT)
                unmasked_text = unmask_text_with_dictionary(res["translated_text_masked"], res.get("mapping_table", {}), is_draft_only=not is_rawt)

                with open(raw_llm_path, "w", encoding="utf-8") as f:
                    f.write(f"=== KẾT QUẢ LLM TRẢ VỀ CHO CHƯƠNG {res_chap_nos} (TRƯỚC HẬU XỬ LÝ) ===\n\n")
                    f.write(unmasked_text)
                
                msg_llm_saved = f"💾 [2/3 DỊCH AI] Đã lưu phản hồi LLM gốc TRƯỚC HẬU XỬ LÝ vào: Output/03_DichAI_LLM/{novel_folder}/{batch_name}"
                print(msg_llm_saved)
                add_system_log(msg_llm_saved, "purple")
            except Exception as save_llm_err:
                print(f"⚠️ Không thể lưu file LLM output trước hậu xử lý: {save_llm_err}")

            msg_post = f"💾 [3/3 HẬU XỬ LÝ] Đang giải mã & bọc đánh dấu cho lô Chương {chap_nos}..."
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
            
            msg_ok = f"✅ [HOÀN THÀNH LÔ] Lô Chương {chap_nos} đã lưu thành công vào CSDL & Ổ đĩa ({len(saved_files)} file)!"
            print(msg_ok)
            add_system_log(msg_ok, "success")
            return res
        else:
            err_res = f"❌ [2/3 DỊCH AI LỖI] Lô Chương {chap_nos} gặp lỗi: {res.get('error') or res.get('message') or res}"
            print(err_res)
            add_system_log(err_res, "error")
            return res
    except Exception as e:
        err_ex = f"❌ [2/3 DỊCH AI LỖI EXCEPTION] Lô ID {batch}: {e}"
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
                # 1. Tự động phát hiện chương chưa dịch thấp nhất nếu không bật force_retranslate
                force_retranslate = kwargs.get("force_retranslate", False)
                actual_start_chapter = start_chapter or 0

                if not force_retranslate:
                    # Chế độ tự động dịch tiếp (Resume): Nếu không chỉ định start_chapter (<=0), tìm chương chưa dịch đầu tiên
                    if actual_start_chapter <= 0:
                        stmt_find = select(Chapter.chapter_no).where(
                            Chapter.novel_id == novel_id,
                            ~Chapter.status.in_(["FINAL_DONE", "DONE", "TRANSLATED"])
                        )
                        if end_chapter > 0:
                            stmt_find = stmt_find.where(Chapter.chapter_no <= end_chapter)
                        stmt_find = stmt_find.order_by(Chapter.chapter_no.asc()).limit(1)
                        res_find = await session.execute(stmt_find)
                        lowest_untranslated = res_find.scalar_one_or_none()
                        if lowest_untranslated:
                            actual_start_chapter = lowest_untranslated
                            add_system_log(f"🔍 Tự động phát hiện chương chưa dịch thấp nhất: Chương {actual_start_chapter}", "info")
                        else:
                            add_system_log("✅ Tất cả các chương trong phạm vi chỉ định đã được dịch hoàn tất.", "success")
                            return {"status": "completed", "total_batches": 0, "total_chapters": 0, "results": []}

                # 2. Query danh sách chương cần dịch
                stmt = select(Chapter.id).where(Chapter.novel_id == novel_id)
                if not force_retranslate:
                    stmt = stmt.where(~Chapter.status.in_(["FINAL_DONE", "DONE", "TRANSLATED"]))

                if actual_start_chapter > 0:
                    stmt = stmt.where(Chapter.chapter_no >= actual_start_chapter)
                if end_chapter > 0:
                    stmt = stmt.where(Chapter.chapter_no <= end_chapter)
                    
                stmt = stmt.order_by(Chapter.chapter_no.asc())
                res = await session.execute(stmt)
                chapter_ids = res.scalars().all()
                
            if not chapter_ids:
                add_system_log("✅ Không có chương nào cần dịch trong khoảng chỉ định.", "success")
                return {"status": "completed", "total_batches": 0, "total_chapters": 0, "results": []}

            # Phân lô (Batching)
            batches = [chapter_ids[i:i + batch_size] for i in range(0, len(chapter_ids), batch_size)]

            results = []
            
            # BƯỚC 1: Tiền xử lý cho Batch ĐẦU TIÊN (Lô 1)
            init_msg = f"📌 [1/3 TIỀN XỬ LÝ LÔ 1] Khởi chạy tiền xử lý cho Lô 1/{len(batches)}..."
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
                
                start_batch_msg = f"🚀 [LÔ {batch_num}/{len(batches)}] Tiến hành dịch Lô {batch_num} ({len(current_batch)} chương)"
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
                    overlap_msg = f"🔄 [GỐI ĐẦU SONG SONG] Khởi chạy tiền xử lý trước cho Lô {batch_num + 1}/{len(batches)}..."
                    print(overlap_msg)
                    add_system_log(overlap_msg, "pre")
                    tasks.append(asyncio.create_task(_process_evidence_and_save(
                        novel_id, next_batch,
                        enable_llm_extract=enable_llm_extract,
                        enable_names_dict=enable_names_dict,
                        enable_gg_corrections=enable_gg_corrections
                    )))
                    
                try:
                    gathered_results = await asyncio.gather(*tasks)
                except BaseException as be:
                    # Hủy tất cả các task con đang chạy dở và chờ dừng hẳn trước khi xử lý ngoại lệ
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise be

                translate_res = gathered_results[0]
                results.append(translate_res)
                
                if "error" in translate_res:
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
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
            cleanup_ids = list(set(active_current_batch))
            if cleanup_ids:
                cleanup_msg = f"🛑 Phát hiện lỗi hoặc yêu cầu dừng. Bắt đầu dọn dẹp..."
                print(cleanup_msg)
                add_system_log(cleanup_msg, "error")
                await cleanup_failed_chapters(cleanup_ids, novel_id)
            raise e

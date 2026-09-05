import asyncio
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, Novel, NovelEntity, ChapterEntityLink, ChapterVersion
from app.services.translation.rawt.llm_translator import translate_batch_llm
from app.api.translation_router import add_system_log

async def _ensure_chapters_crawled(batch: List[int], require_gg: bool = False):
    """
    Đảm bảo 100% các chương trong lô đã có đầy đủ bản gốc RAW (và GG nếu require_gg=True).
    Nếu thiếu chương nào, tự động cào bổ sung trước khi bước vào dịch.
    """
    import os
    from app.models.schema import ChapterVersion
    from app.services.preprocessing.crawler.pipeline import process_single_chapter_crawl
    chap_nos = await _get_chap_numbers(batch)
    
    sweep_round = 1
    while True:
        missing_items = []
        async with AsyncSessionLocal() as session:
            for cid in batch:
                stmt = select(Chapter).where(Chapter.id == cid)
                res = await session.execute(stmt)
                ch = res.scalar_one_or_none()
                if not ch:
                    continue

                stmt_raw = select(ChapterVersion).where(
                    ChapterVersion.chapter_id == cid,
                    ChapterVersion.version_type == "RAW"
                )
                res_raw = await session.execute(stmt_raw)
                v_raw = res_raw.scalar_one_or_none()

                raw_ok = bool(
                    v_raw and (
                        (v_raw.file_path and os.path.exists(v_raw.file_path) and os.path.getsize(v_raw.file_path) > 50)
                        or (v_raw.content and len(v_raw.content.strip()) > 50)
                    )
                )

                if require_gg:
                    stmt_gg = select(ChapterVersion).where(
                        ChapterVersion.chapter_id == cid,
                        ChapterVersion.version_type == "GG"
                    )
                    res_gg = await session.execute(stmt_gg)
                    v_gg = res_gg.scalar_one_or_none()
                    gg_ok = bool(v_gg and v_gg.file_path and os.path.exists(v_gg.file_path) and os.path.getsize(v_gg.file_path) > 50)
                    if not (raw_ok and gg_ok):
                        missing_items.append((cid, ch.chapter_no))
                else:
                    if not raw_ok:
                        missing_items.append((cid, ch.chapter_no))

        # Nếu đã có đủ 100% chương trong lô -> Hoàn tất Giai đoạn 0!
        if not missing_items:
            break

        missing_chap_nos = [m[1] for m in missing_items]
        if sweep_round == 1:
            msg_check = f"📥 [CÀO LÔ ĐẦY ĐỦ] Bắt đầu cào {len(missing_items)}/{len(batch)} chương trong lô {chap_nos} (Chương: {missing_chap_nos})..."
            print(msg_check)
            add_system_log(msg_check, "pre")
        else:
            msg_retry = f"🔁 [CÀO LẠI LÔ - VÒNG {sweep_round}] Đang cào lại {len(missing_items)} chương còn thiếu: {missing_chap_nos}..."
            print(msg_retry)
            add_system_log(msg_retry, "pre")

        for cid, c_no in missing_items:
            try:
                msg_c = f"🌐 [CÀO VĂN BẢN] Đang cào Chương {c_no}..."
                print(msg_c)
                add_system_log(msg_c, "pre")
                await process_single_chapter_crawl(cid, skip_gg=not require_gg)
            except Exception as e_crawl:
                err_msg = f"⚠️ [CÀO TẠM LỖI] Chương {c_no}: {e_crawl}. Sẽ tự động cào lại ở vòng quét tiếp theo..."
                print(err_msg)
                add_system_log(err_msg, "warning")
                await asyncio.sleep(2.0)

        sweep_round += 1
        await asyncio.sleep(2.5)

    msg_ok = f"✅ [CÀO LÔ HOÀN TẤT 100%] Toàn bộ {len(batch)} chương trong lô {chap_nos} đã sẵn sàng bản gốc RAW!"
    print(msg_ok)
    add_system_log(msg_ok, "pre")


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

async def _extract_and_save_batch_entities(novel_id: int, batch: List[int]):
    """
    BƯỚC BẮT BUỘC TRƯỚC KHI KHỞI ĐỘNG LLM DỊCH:
    - Bóc tách thực thể từ bản gốc RAW của các chương trong lô.
    - Chuẩn hóa Hán-Việt, phân loại vai trò, giới tính.
    - Lưu vào CSDL NovelEntity & ChapterEntityLink.
    - Đồng bộ ra Metadata JSON Cache (Output/06_Metadata/.../chapters/*.json và entities.json).
    """
    from app.models.schema import ChapterEntityLink, NovelEntity
    from app.services.preprocessing.dichhan.evidence_collector import collect_batch_entities
    from app.services.preprocessing.dichhan.llm_extractor import process_2branch_evidence_via_llm
    from app.services.storage.metadata_cache import sync_novel_metadata

    chap_nos = await _get_chap_numbers(batch)

    # 1. Kiểm tra xem các chương trong lô này đã có thực thể liên kết chưa
    async with AsyncSessionLocal() as session:
        stmt_chk = select(ChapterEntityLink).where(ChapterEntityLink.chapter_id.in_(batch))
        res_chk = await session.execute(stmt_chk)
        existing_links = res_chk.scalars().all()
        
    if existing_links:
        print(f"ℹ️ [THỰC THỂ] Lô Chương {chap_nos} đã có sẵn {len(existing_links)} liên kết thực thể trên máy.")
        return

    msg_ent_start = f"🔍 [1/2 THỰC THỂ] Đang bóc tách thực thể & lập bảng tên cho lô Chương {chap_nos}..."
    print(msg_ent_start)
    add_system_log(msg_ent_start, "pre")

    try:
        evidence_payload = await collect_batch_entities(batch)
        candidates = evidence_payload.get("branch_1_ner_candidates", [])
        if not candidates:
            print(f"ℹ️ [THỰC THỂ] Không tìm thấy từ nghi vấn trong bản gốc lô Chương {chap_nos}.")
            return

        llm_res = await process_2branch_evidence_via_llm(evidence_payload)
        entities = llm_res.get("entities", [])
        if not entities:
            print(f"ℹ️ [THỰC THỂ] LLM không phát hiện thực thể mới cho lô Chương {chap_nos}.")
            return

        # Lưu entities vào DB
        async with AsyncSessionLocal() as session:
            # Tra cứu các thực thể đã có sẵn trong DB của truyện
            stmt_ex = select(NovelEntity).where(NovelEntity.novel_id == novel_id)
            res_ex = await session.execute(stmt_ex)
            existing_entity_map = {e.chinese_name: e for e in res_ex.scalars().all()}

            saved_count = 0
            for ent in entities:
                ch_name = ent.get("chinese_name", "").strip()
                vi_trans = ent.get("vietnamese_name", ent.get("rough_translation", "")).strip()
                e_type = ent.get("entity_type", "NAME")
                gender = ent.get("gender")
                role = ent.get("role")

                if not ch_name or not vi_trans:
                    continue

                if ch_name in existing_entity_map:
                    ent_obj = existing_entity_map[ch_name]
                    ent_obj.frequency_count += 1
                    ent_id = ent_obj.id
                else:
                    new_ent = NovelEntity(
                        novel_id=novel_id,
                        chinese_name=ch_name,
                        rough_translation=vi_trans,
                        entity_type=e_type,
                        gender=gender,
                        role=role,
                        frequency_count=1
                    )
                    session.add(new_ent)
                    await session.flush()
                    existing_entity_map[ch_name] = new_ent
                    ent_id = new_ent.id
                    saved_count += 1

                # Liên kết với các chương trong batch
                for cid in batch:
                    stmt_link = select(ChapterEntityLink).where(
                        ChapterEntityLink.chapter_id == cid,
                        ChapterEntityLink.entity_id == ent_id
                    )
                    link_res = await session.execute(stmt_link)
                    if not link_res.scalars().first():
                        session.add(ChapterEntityLink(chapter_id=cid, entity_id=ent_id))

            await session.commit()

        # Đồng bộ ra file Metadata JSON cache trên đĩa
        await sync_novel_metadata(novel_id)

        msg_ent_done = f"✅ [THỰC THỂ HOÀN TẤT] Đã bóc tách và lưu {len(entities)} thực thể ({saved_count} mới) vào máy cho lô Chương {chap_nos}!"
        print(msg_ent_done)
        add_system_log(msg_ent_done, "success")

    except Exception as e:
        msg_ent_err = f"⚠️ [THỰC THỂ CẢNH BÁO] Không thể bóc tách thực thể lô Chương {chap_nos}: {e}"
        print(msg_ent_err)
        add_system_log(msg_ent_err, "warning")

async def _translate_batch(batch: List[int], enable_names_dict: bool = True, **kwargs):
    """Dịch AI trực tiếp từ bản gốc RAW (RAWT) sang Tiếng Việt chuẩn"""
    chap_nos = await _get_chap_numbers(batch)
    msg_trans = f"🚀 [1/2 DỊCH AI] Gửi LLM xử lý lô Chương {chap_nos} (Dịch Trực Tiếp từ RAW)..."
    print(msg_trans)
    add_system_log(msg_trans, "purple")
    
    try:
        from app.services.postprocessing.post_processor import process_and_split_batch
        enable_unblock = kwargs.get("enable_unblock", True)
        enable_erotic = kwargs.get("enable_erotic", False)
        res = await translate_batch_llm(batch, enable_names_dict=enable_names_dict, enable_unblock=enable_unblock, enable_erotic=enable_erotic)
        ver_type = "LLM"
            
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

                # Unmask giải mã sơ bộ để đọc tiếng Việt
                unmasked_text = unmask_text_with_dictionary(res["translated_text_masked"], res.get("mapping_table", {}), is_draft_only=False, enable_erotic=enable_erotic, flow="rawt")

                with open(raw_llm_path, "w", encoding="utf-8") as f:
                    f.write(f"=== KẾT QUẢ LLM TRẢ VỀ CHO CHƯƠNG {res_chap_nos} (TRƯỚC HẬU XỬ LÝ) ===\n\n")
                    f.write(unmasked_text)
                
                msg_llm_saved = f"💾 [1/2 DỊCH AI] Đã lưu phản hồi LLM gốc TRƯỚC HẬU XỬ LÝ vào: Output/03_DichAI_LLM/{novel_folder}/{batch_name}"
                print(msg_llm_saved)
                add_system_log(msg_llm_saved, "purple")
            except Exception as save_llm_err:
                print(f"⚠️ Không thể lưu file LLM output trước hậu xử lý: {save_llm_err}")

            msg_post = f"💾 [2/2 HẬU XỬ LÝ] Đang bọc đánh dấu & lưu kết quả cho lô Chương {chap_nos}..."
            print(msg_post)
            add_system_log(msg_post, "post")
            
            saved_files = await process_and_split_batch(
                novel_id=res["novel_id"],
                translated_text_masked=res["translated_text_masked"],
                mapping_table=res.get("mapping_table", {}),
                chapter_map=res["chapter_map"],
                version_type=ver_type,
                enable_erotic=enable_erotic
            )
            res["saved_files"] = saved_files
            
            msg_ok = f"✅ [HOÀN THÀNH LÔ] Lô Chương {chap_nos} đã lưu thành công vào CSDL & Ổ đĩa ({len(saved_files)} file)!"
            print(msg_ok)
            add_system_log(msg_ok, "success")
            return res
        else:
            err_res = f"❌ [DỊCH AI LỖI] Lô Chương {chap_nos} gặp lỗi: {res.get('error') or res.get('message') or res}"
            print(err_res)
            add_system_log(err_res, "error")
            return res
    except Exception as e:
        err_ex = f"❌ [DỊCH AI LỖI EXCEPTION] Lô ID {batch}: {e}"
        print(err_ex)
        add_system_log(err_ex, "error")
        return {"error": str(e), "batch": batch}


_PIPELINE_LOCK = asyncio.Lock()

async def run_translation_batch_pipeline(
    novel_id: int,
    translation_flow: str = "rawt", # Pure RAWT (Dịch RAW Hán tự sang Tiếng Việt)
    batch_size: int = 3,
    delay_sec: float = 0.5,
    start_chapter: int = 0,
    end_chapter: int = 0,
    enable_llm_extract: bool = False,
    enable_names_dict: bool = True,
    enable_gg_corrections: bool = False,
    **kwargs
):
    """
    Pipeline dịch tuần tự thuần RAWT:
    - Dịch trực tiếp từ bản gốc chữ Hán sang Tiếng Việt bằng LLM.
    - Không qua Google Dịch, không quét lỗi trung gian, tối ưu token và tốc độ.
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
            # VÒNG LẶP DỊCH TUẦN TỰ (RAWT)
            for idx, current_batch in enumerate(batches):
                batch_num = idx + 1
                active_current_batch = current_batch
                
                # Đảm bảo lô hiện tại có sẵn file bản gốc RAW
                await _ensure_chapters_crawled(current_batch, require_gg=False)

                # BƯỚC 1: BÓC TÁCH THỰC THỂ LÔ & LƯU VÀO MÁY (BẮT BUỘC HOÀN TẤT TRƯỚC KHI KHỞI ĐỘNG DỊCH)
                if enable_names_dict:
                    await _extract_and_save_batch_entities(novel_id, current_batch)

                # BƯỚC 2: KHỞI ĐỘNG LLM DỊCH LÔ
                start_batch_msg = f"🚀 [LÔ {batch_num}/{len(batches)}] Tiến hành dịch Lô {batch_num} ({len(current_batch)} chương)..."
                print(start_batch_msg)
                add_system_log(start_batch_msg, "purple")
                
                translate_res = await _translate_batch(
                    current_batch,
                    enable_names_dict=enable_names_dict,
                    enable_unblock=kwargs.get("enable_unblock", True),
                    enable_erotic=kwargs.get("enable_erotic", False),
                    custom_prompt=kwargs.get("custom_prompt", "")
                )
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

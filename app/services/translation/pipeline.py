import asyncio
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.schema import Chapter, Novel, NovelEntity, ChapterEntityLink, ChapterVersion
from app.services.translation.rawt.llm_translator import translate_batch_llm
from app.api.translation_router import add_system_log, broadcast_sse
from app.core.config import OUTPUT_DIR

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

async def _extract_and_save_batch_entities(novel_id: int, batch: List[int], force: bool = False):
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

    # 1. Kiểm tra xem các chương trong lô này chương nào chưa có thực thể liên kết
    if force:
        unlinked_batch = list(batch)
    else:
        async with AsyncSessionLocal() as session:
            stmt_chk = select(ChapterEntityLink.chapter_id).where(ChapterEntityLink.chapter_id.in_(batch)).distinct()
            res_chk = await session.execute(stmt_chk)
            linked_cids = set(res_chk.scalars().all())
            
        unlinked_batch = [cid for cid in batch if cid not in linked_cids]
        if not unlinked_batch:
            print(f"ℹ️ [THỰC THỂ] Lô Chương {chap_nos} đã có sẵn đầy đủ liên kết thực thể trên máy.")
            return

    unlinked_chap_nos = await _get_chap_numbers(unlinked_batch)
    msg_ent_start = f"🔍 [1/2 THỰC THỂ] Đang bóc tách thực thể & lập bảng tên cho {len(unlinked_batch)} chương mới: Chương {unlinked_chap_nos}..."
    print(msg_ent_start)
    add_system_log(msg_ent_start, "pre")

    try:
        evidence_payload = await collect_batch_entities(unlinked_batch)
        candidates = evidence_payload.get("branch_1_ner_candidates", [])
        entities = []
        if candidates:
            try:
                llm_res = await process_2branch_evidence_via_llm(evidence_payload)
                entities = llm_res.get("entities", [])
            except Exception as llm_err:
                msg_llm_fail = f"⚠️ [THỰC THỂ LLM LỖI]: {llm_err}. Kích hoạt chế độ Fallback Hán-Việt tự động..."
                print(msg_llm_fail)
                add_system_log(msg_llm_fail, "warning")

        # Chỉ bổ sung các ngoại hiệu giang hồ thật sự (Epithet) nếu LLM bỏ sót, tuyệt đối KHÔNG tự động ép từ ngữ đời thường (như 大..., ...子, ...头) thành tên riêng
        from app.services.preprocessing.dichhan.common_lists import EPITHET_SUFFIXES
        existing_names = {e.get("chinese_name", "").strip() for e in entities}
        for cand in candidates:
            orig = (cand.get("original_han") or cand.get("han") or "").strip()
            sugg = (cand.get("suggested_hanviet_example") or cand.get("db_example") or "").strip()
            if not orig or not sugg or orig in existing_names or orig == sugg:
                continue
            
            # Chỉ bổ sung khi thực sự là ngoại hiệu giang hồ võ hiệp (ví dụ: Ngọc Kỳ Lân, Trí Đa Tinh)
            is_epithet = 2 <= len(orig) <= 5 and any(orig.endswith(ep) for ep in EPITHET_SUFFIXES)
            is_moniker = cand.get("ner_type") == "EPITHET" or cand.get("is_epithet")
            
            if is_epithet or is_moniker:
                entities.append({
                    "chinese_name": orig,
                    "vietnamese_name": sugg,
                    "entity_type": "NAME",
                    "gender": None,
                    "role": None
                })
                existing_names.add(orig)

        if not entities:
            print(f"ℹ️ [THỰC THỂ] Không tìm thấy thực thể mới nào cho lô Chương {chap_nos}.")
            return

        # Lưu entities vào DB (Nguồn 1: SQLite DB)
        async with AsyncSessionLocal() as session:
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

                # Liên kết với các chương trong batch (ChapterEntityLink)
                for cid in batch:
                    stmt_link = select(ChapterEntityLink).where(
                        ChapterEntityLink.chapter_id == cid,
                        ChapterEntityLink.entity_id == ent_id
                    )
                    link_res = await session.execute(stmt_link)
                    if not link_res.scalars().first():
                        session.add(ChapterEntityLink(chapter_id=cid, entity_id=ent_id))

            await session.commit()

        # Đồng bộ ra file Metadata JSON cache trên đĩa (Nguồn 2: entities.json & Nguồn 3: chapters/*.json)
        await sync_novel_metadata(novel_id)

        msg_ent_done = f"✅ [THỰC THỂ HOÀN TẤT] Đã bóc tách và đồng bộ cả 3 file ({len(entities)} thực thể, {saved_count} mới) cho lô Chương {chap_nos}!"
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
                llm_out_dir = os.path.join(str(OUTPUT_DIR / "03_DichAI_LLM"), novel_folder)
                os.makedirs(llm_out_dir, exist_ok=True)

                res_chap_nos = sorted(list(res["chapter_map"].values()))
                batch_tag = "_".join(map(str, res_chap_nos))
                batch_name = f"batch_ch{batch_tag}.txt"
                raw_llm_path = os.path.join(llm_out_dir, batch_name)
                raw_llm_output_path = os.path.join(llm_out_dir, f"batch_ch{batch_tag}_output.txt")

                # Unmask giải mã sơ bộ để đọc tiếng Việt
                unmasked_text = unmask_text_with_dictionary(res["translated_text_masked"], res.get("mapping_table", {}), is_draft_only=False, enable_erotic=enable_erotic, flow="rawt")

                output_content = f"=== KẾT QUẢ LLM TRẢ VỀ CHO CHƯƠNG {res_chap_nos} (TRƯỚC HẬU XỬ LÝ) ===\n\n{unmasked_text}"

                with open(raw_llm_path, "w", encoding="utf-8") as f:
                    f.write(output_content)
                with open(raw_llm_output_path, "w", encoding="utf-8") as f:
                    f.write(output_content)
                
                msg_llm_saved = f"💾 [1/2 DỊCH AI] Đã lưu ĐẦU RA của lô tại: Output/03_DichAI_LLM/{novel_folder}/batch_ch{batch_tag}_output.txt"
                print(msg_llm_saved)
                add_system_log(msg_llm_saved, "purple")
            except Exception as save_llm_err:
                print(f"⚠️ Không thể lưu file LLM output trước hậu xử lý: {save_llm_err}")

            msg_post = f"💾 [2/2 HẬU XỬ LÝ] Đang bọc đánh dấu & lưu kết quả cho lô Chương {chap_nos}..."
            print(msg_post)
            add_system_log(msg_post, "post")
            
            post_result = await process_and_split_batch(
                novel_id=res["novel_id"],
                translated_text_masked=res["translated_text_masked"],
                mapping_table=res.get("mapping_table", {}),
                chapter_map=res["chapter_map"],
                version_type=ver_type,
                enable_erotic=enable_erotic
            )
            saved_files = post_result.get("saved_files", []) if isinstance(post_result, dict) else post_result
            saved_cids = post_result.get("saved_cids", []) if isinstance(post_result, dict) else [cid for cid in batch]
            failed_cids = post_result.get("failed_cids", []) if isinstance(post_result, dict) else []
            
            res["saved_files"] = saved_files
            res["saved_cids"] = saved_cids
            res["failed_cids"] = failed_cids
            
            if saved_cids:
                msg_ok = f"✅ [HOÀN THÀNH LÔ] Đã lưu thành công {len(saved_cids)}/{len(batch)} chương ({len(saved_files)} file)!"
                print(msg_ok)
                add_system_log(msg_ok, "success")
            else:
                res["status"] = "failed"
                res["error"] = "Không có chương nào trong lô đạt chuẩn trọn vẹn để lưu."
                msg_none = f"⚠️ [LÔ KHÔNG ĐẠT CHUẨN] Toàn bộ {len(batch)} chương đều thiếu thẻ hoặc bị cắt cụt."
                print(msg_none)
                add_system_log(msg_none, "warning")
                
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
            # 1. Tự động phát hiện chương chưa dịch thấp nhất nếu không bật force_retranslate
            force_retranslate = kwargs.get("force_retranslate", False)
            actual_start_chapter = start_chapter or 0

            if force_retranslate:
                # Nếu bật force_retranslate, reset các chương trong khoảng về CRAWLED trước
                async with AsyncSessionLocal() as session:
                    stmt_reset = select(Chapter).where(Chapter.novel_id == novel_id)
                    if actual_start_chapter > 0:
                        stmt_reset = stmt_reset.where(Chapter.chapter_no >= actual_start_chapter)
                    if end_chapter > 0:
                        stmt_reset = stmt_reset.where(Chapter.chapter_no <= end_chapter)
                    res_reset = await session.execute(stmt_reset)
                    reset_chaps = res_reset.scalars().all()
                    for ch in reset_chaps:
                        ch.status = "CRAWLED"
                    await session.commit()
                    add_system_log(f"🔄 [FORCE RETRANSLATE] Đã đặt lại trạng thái cho {len(reset_chaps)} chương về CRAWLED để dịch lại.", "info")
            else:
                # Chế độ tự động dịch tiếp (Resume): Nếu không chỉ định start_chapter (<=0), tìm chương chưa dịch đầu tiên
                if actual_start_chapter <= 0:
                    async with AsyncSessionLocal() as session:
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

            # Đếm tổng số chương cần xử lý trong phạm vi
            async with AsyncSessionLocal() as session:
                stmt_total = select(Chapter.id).where(Chapter.novel_id == novel_id)
                if actual_start_chapter > 0:
                    stmt_total = stmt_total.where(Chapter.chapter_no >= actual_start_chapter)
                if end_chapter > 0:
                    stmt_total = stmt_total.where(Chapter.chapter_no <= end_chapter)
                res_total = await session.execute(stmt_total)
                total_target_ids = res_total.scalars().all()
                total_target_count = len(total_target_ids)

            # VÒNG LẶP DỊCH ĐỘNG (DYNAMIC BATCHING LOOP)
            # Không chia cứng batch từ đầu. Mỗi vòng lặp sẽ query các chương chưa hoàn tất nhỏ nhất tiếp theo!
            # Điều này đảm bảo: Nếu chương cuối của lô bị thiếu thẻ (ví dụ lô 1-5 thiếu chương 5),
            # thì các chương 1, 2, 3, 4 đã hoàn tất sẽ lưu ngay, còn chương 5 sẽ tự động được đưa vào ngay đầu lô tiếp theo (5, 6, 7, 8, 9)!
            batch_num = 0
            consecutive_failures = 0
            missing_tag_streak = 0
            results = []
            total_saved_count = 0
            initial_batch_size = max(1, batch_size)
            active_batch_size = initial_batch_size

            while True:
                async with AsyncSessionLocal() as session:
                    stmt = select(Chapter.id).where(
                        Chapter.novel_id == novel_id,
                        ~Chapter.status.in_(["FINAL_DONE", "DONE", "TRANSLATED"])
                    )
                    if actual_start_chapter > 0:
                        stmt = stmt.where(Chapter.chapter_no >= actual_start_chapter)
                    if end_chapter > 0:
                        stmt = stmt.where(Chapter.chapter_no <= end_chapter)
                    stmt = stmt.order_by(Chapter.chapter_no.asc()).limit(active_batch_size)
                    res = await session.execute(stmt)
                    current_batch = res.scalars().all()

                if not current_batch:
                    # Đã dịch hết tất cả các chương trong phạm vi!
                    add_system_log("🎉 [HOÀN TẤT DỊCH TOÀN BỘ] Đã hoàn thành 100% tất cả các chương trong phạm vi chỉ định!", "success")
                    break

                batch_num += 1
                active_current_batch = current_batch
                chap_nos = await _get_chap_numbers(current_batch)

                # Đảm bảo lô hiện tại có sẵn file bản gốc RAW
                await _ensure_chapters_crawled(current_batch, require_gg=False)

                # BƯỚC 1: BÓC TÁCH THỰC THỂ LÔ & LƯU VÀO MÁY (chỉ bóc tách cho các chương chưa có)
                if enable_names_dict:
                    await _extract_and_save_batch_entities(novel_id, current_batch)

                # BƯỚC 2: KHỞI ĐỘNG LLM DỊCH LÔ
                batch_info_str = f"Lô {len(current_batch)} chương (Chương {min(chap_nos)}->{max(chap_nos)})"
                if active_batch_size < initial_batch_size:
                    batch_info_str += f" [Đã tự giảm từ {initial_batch_size}]"

                broadcast_sse("progress", {
                    "isRunning": True,
                    "novelId": novel_id,
                    "stage": "TRANSLATING",
                    "batchSize": active_batch_size,
                    "initialBatchSize": initial_batch_size,
                    "currentBatchChapters": chap_nos,
                    "currentBatchInfo": batch_info_str,
                    "completedChapters": total_saved_count,
                    "totalChapters": total_target_count
                })

                start_batch_msg = f"🚀 [LÔ DỊCH {batch_num} | KÍCH THƯỚC: {len(current_batch)} CHƯƠNG] Đang dịch {len(current_batch)} chương (Chương: {chap_nos})..."
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

                saved_cids = translate_res.get("saved_cids", [])
                failed_cids = translate_res.get("failed_cids", [])

                if saved_cids:
                    consecutive_failures = 0
                    missing_tag_streak = 0
                    total_saved_count += len(saved_cids)

                    # Khôi phục kích thước lô ban đầu nếu trước đó bị giảm
                    if active_batch_size != initial_batch_size:
                        restore_msg = f"🔄 [KHÔI PHỤC KÍCH THƯỚC LÔ DỊCH] Lô vừa qua đã dịch & lưu thành công {len(saved_cids)}/{len(current_batch)} chương. Tự động khôi phục kích thước lô từ {active_batch_size} về {initial_batch_size} chương ban đầu!"
                        print(restore_msg)
                        add_system_log(restore_msg, "info")
                        active_batch_size = initial_batch_size

                    done_batch = f"🎉 [HOÀN THÀNH LÔ DỊCH {batch_num}] Đã lưu thành công {len(saved_cids)}/{len(current_batch)} chương (Đã dịch tổng cộng: {total_saved_count}/{total_target_count} | Lô tiếp theo: {active_batch_size} chương)!"
                    print(done_batch)
                    add_system_log(done_batch, "success")

                    broadcast_sse("progress", {
                        "isRunning": True,
                        "novelId": novel_id,
                        "stage": "TRANSLATING",
                        "batchSize": active_batch_size,
                        "initialBatchSize": initial_batch_size,
                        "completedChapters": total_saved_count,
                        "totalChapters": total_target_count
                    })

                    if failed_cids:
                        failed_chap_nos = await _get_chap_numbers(failed_cids)
                        fail_msg = f"🔁 [TỰ ĐỘNG NỐI LÔ TIẾP THEO] Chương {failed_chap_nos} chưa đạt chuẩn thẻ/nội dung sẽ được đưa ngay vào đầu Lô {batch_num + 1} để xử lý dứt điểm!"
                        print(fail_msg)
                        add_system_log(fail_msg, "warning")
                else:
                    consecutive_failures += 1
                    missing_tag_streak += 1

                    err_batch = f"⚠️ [CẢNH BÁO LÔ DỊCH {batch_num}] Lô Chương {chap_nos} ({len(current_batch)} chương) không có chương nào đạt chuẩn để lưu do thiếu thẻ/ngắt quãng (Bị thiếu thẻ liên tiếp: {missing_tag_streak}/2 lần)."
                    print(err_batch)
                    add_system_log(err_batch, "error")

                    # Giảm 1 chương sau 2 lần liên tục bị thiếu thẻ
                    if missing_tag_streak >= 2:
                        if active_batch_size > 1:
                            old_size = active_batch_size
                            active_batch_size = max(1, active_batch_size - 1)
                            missing_tag_streak = 0  # Reset chu kỳ 2 lần để theo dõi cho kích thước mới
                            shrink_msg = f"⚡ [TỰ ĐỘNG THU HẸP LÔ DỊCH] Đã gặp 2 lần liên tiếp bị thiếu thẻ! Tự động giảm kích thước lô dịch 1 chương (từ {old_size} xuống {active_batch_size} chương | Gốc: {initial_batch_size} chương)!"
                            print(shrink_msg)
                            add_system_log(shrink_msg, "warning")

                            broadcast_sse("progress", {
                                "isRunning": True,
                                "novelId": novel_id,
                                "stage": "TRANSLATING",
                                "batchSize": active_batch_size,
                                "initialBatchSize": initial_batch_size,
                                "completedChapters": total_saved_count,
                                "totalChapters": total_target_count
                            })
                        else:
                            shrink_msg = f"ℹ️ [LÔ DỊCH TỐI THIỂU] Kích thước lô hiện tại đã là 1 chương (tối thiểu). Tiếp tục thử lại với 1 chương..."
                            print(shrink_msg)
                            add_system_log(shrink_msg, "warning")
                    else:
                        retry_same_msg = f"⏳ [THỬ LẠI LÔ DỊCH] Giữ nguyên kích thước lô {active_batch_size} chương để thử lại lần 2 trước khi tự động giảm..."
                        print(retry_same_msg)
                        add_system_log(retry_same_msg, "info")

                    if active_batch_size == 1 and consecutive_failures >= 3:
                        err_stop = f"❌ [DỪNG TIẾN TRÌNH] Đã thử dịch 1 chương đơn lẻ nhưng vẫn thất bại liên tiếp 3 lần tại Chương {chap_nos}. Tạm dừng tiến trình để kiểm tra API hoặc mạng!"
                        print(err_stop)
                        add_system_log(err_stop, "error")
                        raise ValueError(err_stop)

                if delay_sec > 0:
                    delay_msg = f"⏳ Tạm nghỉ {delay_sec:.1f}s trước khi chuyển sang Lô tiếp theo..."
                    print(delay_msg)
                    add_system_log(delay_msg, "warning")
                    await asyncio.sleep(delay_sec)

            return {
                "status": "completed",
                "total_batches": batch_num,
                "total_chapters": total_saved_count,
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

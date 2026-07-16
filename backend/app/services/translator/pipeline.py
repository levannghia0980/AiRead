import asyncio
import hashlib
import logging
import re
from sqlalchemy import delete
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# pyrefly: ignore [missing-import]
from deep_translator import GoogleTranslator
import httpx
from app.models.models import Glossary, TranslationCache
from app.services.translator.client import TranslatorClient
from app.services.translator.text_processor import (
    preprocess_chinese_text,
    build_glossary_context,
    postprocess_translated_text,
    quality_check,
)

logger = logging.getLogger(__name__)

# ============================================================
# SYSTEM INSTRUCTION — 13 quy tắc dịch thuật chất lượng cao
# Tối ưu cho tiểu thuyết Trung Quốc (tiên hiệp, huyền huyễn, đô thị, kiếm hiệp)
# ============================================================
SYSTEM_INSTRUCTION = """Bạn là một biên dịch viên và biên tập viên tiểu thuyết Trung-Việt chuyên nghiệp hàng đầu.
Nhiệm vụ: Dựa vào bản gốc tiếng Trung và bảng thuật ngữ (Glossary) để viết ra bản dịch tiếng Việt hoàn hảo nhất.

NGUYÊN TẮC BẮT BUỘC:

1. GIỮ TUYỆT ĐỐI NỘI DUNG GỐC:
   - KHÔNG thêm nội dung, cảm xúc, miêu tả không có trong nguyên tác.
   - KHÔNG bớt câu, đoạn, lời thoại nào.
   - KHÔNG tự suy diễn hoặc sửa cốt truyện.

2. VĂN PHONG THUẦN VIỆT TỰ NHIÊN:
   - Dịch thoát ý, KHÔNG dịch word-by-word.
   - "抬头" → "ngẩng đầu" (KHÔNG PHẢI "nâng đầu").
   - "轻轻点头" → "khẽ gật đầu" (KHÔNG PHẢI "nhẹ nhàng gật đầu").
   - "吃了一惊" → "giật mình" (KHÔNG PHẢI "ăn một kinh ngạc").
   - "脸色一变" → "sắc mặt biến đổi" (KHÔNG PHẢI "sắc mặt thay đổi").

3. XƯNG HÔ NHẤT QUÁN:
   - Truyện tu tiên/kiếm hiệp: dùng hắn, nàng, ta, ngươi, huynh, đệ, tỷ, muội.
   - KHÔNG dùng anh/tôi/bạn/cậu trừ khi bối cảnh đô thị hiện đại.
   - Giữ nguyên xưng hô xuyên suốt chương, KHÔNG đổi giữa chừng.

4. TÊN RIÊNG & THUẬT NGỮ:
   - ÁP DỤNG CHÍNH XÁC bảng Glossary, không dịch khác dù chỉ một chữ.
   - Tên nhân vật phải đúng âm Hán Việt chuẩn và nhất quán.
   - Thuật ngữ tu luyện (Tiên Thiên, Hậu Thiên, Tông Sư, Linh Nguyên, Linh Kỹ...) phải thống nhất.
   - KHÔNG dịch thuật ngữ tu luyện theo nghĩa đen (ví dụ: "先天" KHÔNG dịch là "bẩm sinh").

5. HỘI THOẠI TỰ NHIÊN:
   - Lời thoại phải sống động, đúng tính cách nhân vật.
   - "你想干什么？" → "Ngươi muốn làm gì?" (KHÔNG PHẢI "Ngươi muốn làm cái gì?").
   - Hội thoại dùng dấu ngoặc kép: "Lời thoại" hoặc gạch ngang đầu dòng: — Lời thoại.

6. GIỮ NHỊP TRUYỆN:
   - Đánh nhau: câu ngắn, dứt khoát ("Ầm!", "Bùm!", "Phựt!").
   - Miêu tả: câu dài, trau chuốt hơn.
   - KHÔNG lặp chủ ngữ liên tục (hắn... hắn... hắn...).

7. GIỮ YẾU TỐ HÀI HƯỚC:
   - Bảo toàn sự hài hước, châm biếm, mỉa mai của tác giả.
   - "他差点把脑袋当西瓜捏爆" → "Hắn suýt nữa tưởng đó là quả dưa hấu mà bóp nát."

8. THÀNH NGỮ VIỆT HÓA:
   - "一箭双雕" → "Một công đôi việc" (KHÔNG PHẢI "Một mũi tên hai chim điêu").
   - "狐假虎威" → "Cáo mượn oai hùm" (KHÔNG PHẢI "Cáo mượn oai hổ").

9. HIỂU SẮC THÁI:
   - "呵呵" tùy ngữ cảnh: cười lạnh / cười nhạt / hừ / khẽ cười.
   - Không phải lúc nào cũng dịch là "Ha ha".

10. DẤU CÂU VĂN HỌC CHUẨN:
    - Dùng dấu gạch ngang "—" (em dash) cho đoạn ngắt câu, không dùng "-" đơn.
    - Dấu ba chấm "..." nhất quán — không trộn "…" và "...".
    - Cảm thán dùng "!" một lần, không viết "!!!" hay "!!!!".

11. ĐOẠN VĂN RÕ RÀNG:
    - Mỗi đoạn văn (paragraph) giữ nguyên từ bản gốc.
    - KHÔNG gộp nhiều đoạn thành một, KHÔNG tự ý tách đoạn.
    - Xuống dòng đúng vị trí như nguyên tác.

12. TỪ LÁY & THÀNH NGỮ THUẦN VIỆT:
    - Ưu tiên từ láy tự nhiên: "lảo đảo", "lẩm bẩm", "thì thầm", "rì rào".
    - Các từ Hán-Việt phổ thông: dùng khi phù hợp với khí quyển tiên hiệp.
    - Tránh Hán Việt quá cứng nhắc trong đoạn hội thoại thường ngày.

13. TUYỆT ĐỐI KHÔNG ĐỂ SÓT CHỮ TRUNG:
    - Dịch toàn bộ văn bản — KHÔNG để lại bất kỳ chữ Hán nào trong bản dịch.
    - Nếu không chắc tên riêng, dùng phiên âm Hán-Việt chuẩn.

CHỈ XUẤT RA VĂN BẢN DỊCH TIẾNG VIỆT. KHÔNG thêm ghi chú, giải thích, hay bình luận."""


class TranslationPipeline:
    """
    Pipeline dịch thuật tiểu thuyết Trung → Việt chất lượng biên tập viên.
    
    Luồng xử lý:
    1. TIỀN XỬ LÝ: Chuẩn hóa văn bản Trung, xóa quảng cáo, chuẩn hóa Unicode.
    2. CHIA CHUNK: Tách thành các đoạn ≤12000 ký tự theo ranh giới đoạn văn.
    3. CACHE: Kiểm tra SQLite cache để tránh dịch lại.
    4. DỊCH SONG SONG: Tất cả chunks dịch cùng lúc với asyncio.gather() → 3-5x nhanh hơn.
    5. HẬU XỬ LÝ: Ép Glossary bằng code, sửa lỗi dịch máy, chuẩn hóa dấu câu.
    6. KIỂM DUYỆT: Kiểm tra tỷ lệ độ dài, Glossary compliance, xưng hô.
    """

    def __init__(self, client: TranslatorClient, db: AsyncSession, http_client: Optional[httpx.AsyncClient] = None):
        self.client = client
        self.db = db
        # 12000 ký tự/chunk → ít API calls hơn, ngữ cảnh liền mạch hơn
        self.chunk_size_limit = 12000
        self.http_client = http_client

    # ==================================================================
    # CHUNKING
    # ==================================================================
    def _split_into_chunks(self, text: str) -> List[str]:
        """Tách văn bản thành các chunk ≤ chunk_size_limit ký tự theo ranh giới đoạn văn.
        Không bao giờ cắt giữa một đoạn hội thoại (dòng bắt đầu bằng dấu ngoặc kép)."""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            
            # Nếu thêm đoạn này vượt giới hạn VÀ chunk hiện tại không rỗng
            if current_len + p_len > self.chunk_size_limit and current_chunk:
                # Không cắt giữa hội thoại: nếu đoạn tiếp theo bắt đầu bằng "
                # và đoạn trước cũng là hội thoại, gom chung
                if p.startswith('"') and current_chunk[-1].startswith('"') and current_len + p_len < self.chunk_size_limit * 1.2:
                    current_chunk.append(p)
                    current_len += p_len + 2
                else:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [p]
                    current_len = p_len
            else:
                current_chunk.append(p)
                current_len += p_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    # ==================================================================
    # CACHE
    # ==================================================================
    _CHINESE_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

    @classmethod
    def _has_chinese_chars(cls, text: str) -> bool:
        """Trả về True nếu văn bản còn chứa chữ Trung Quốc."""
        return bool(cls._CHINESE_RE.search(text))

    def _get_md5_hash(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def _get_cached_translation(self, raw_hash: str) -> Optional[str]:
        try:
            stmt = select(TranslationCache).where(TranslationCache.key_hash == raw_hash)
            result = await self.db.execute(stmt)
            cache_entry = result.scalar_one_or_none()
            if cache_entry:
                if self._has_chinese_chars(cache_entry.translated_text):
                    logger.warning(f"🗑️ Cache {raw_hash[:8]}... còn chữ Trung → xóa và dịch lại.")
                    await self.db.execute(
                        delete(TranslationCache).where(TranslationCache.key_hash == raw_hash)
                    )
                    await self.db.commit()
                    return None
                return cache_entry.translated_text
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        return None

    async def _save_to_cache(self, raw_hash: str, raw_text: str, translated_text: str):
        if self._has_chinese_chars(translated_text):
            logger.warning(f"⚠️ Bỏ qua cache {raw_hash[:8]}...: vẫn còn chữ Trung.")
            return
        try:
            cache_entry = TranslationCache(
                key_hash=raw_hash,
                raw_text=raw_text,
                translated_text=translated_text
            )
            await self.db.merge(cache_entry)
            await self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to write to translation cache: {e}")
            await self.db.rollback()

    # ==================================================================
    # GOOGLE TRANSLATE DRAFT (fallback khi AI thất bại)
    # ==================================================================
    async def _get_draft_translation(self, text: str) -> str:
        """Tạo bản dịch thô bằng Google Translate — chỉ dùng khi AI hoàn toàn thất bại."""
        if not text:
            return ""
            
        max_chars = 1000
        paragraphs = text.split("\n")
        sub_chunks = []
        current_sub = []
        current_len = 0
        
        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > max_chars and current_sub:
                sub_chunks.append("\n".join(current_sub))
                current_sub = [p]
                current_len = p_len
            else:
                current_sub.append(p)
                current_len += p_len + 1
        if current_sub:
            sub_chunks.append("\n".join(current_sub))
            
        translated_sub_chunks = []
        for sub in sub_chunks:
            translated_sub = await self._get_draft_translation_segment(sub)
            translated_sub_chunks.append(translated_sub if translated_sub else "")
                
        return "\n\n".join(translated_sub_chunks)

    async def _get_draft_translation_segment(self, text: str) -> str:
        """Dịch thô một đoạn < 1000 ký tự."""
        if not text.strip():
            return ""
        # 1. Try Google Translate API (POST method, keyless)
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            data = {"client": "gtx", "sl": "zh-CN", "tl": "vi", "dt": "t", "q": text}
            client = self.http_client or httpx.AsyncClient(timeout=10.0)
            if self.http_client:
                resp = await client.post(url, data=data)
            else:
                async with client as c:
                    resp = await c.post(url, data=data)
            if resp.status_code == 200:
                data_json = resp.json()
                translations = []
                if data_json and isinstance(data_json, list) and len(data_json) > 0 and data_json[0]:
                    for item in data_json[0]:
                        if item and len(item) > 0:
                            translations.append(item[0])
                if translations:
                    return "".join(translations)
        except Exception as e:
            logger.warning(f"Google Translate API failed: {e}. Trying fallback...")

        # 2. Fallback to deep-translator
        loop = asyncio.get_running_loop()
        try:
            draft = await loop.run_in_executor(
                None,
                lambda: GoogleTranslator(source='zh-CN', target='vi').translate(text)
            )
            return draft or ""
        except Exception as e:
            logger.warning(f"All Google Translate attempts failed: {e}")
            return ""

    # ==================================================================
    # DỊCH MỘT CHUNK (core logic với retry)
    # ==================================================================
    async def _translate_single_chunk(
        self,
        i: int,
        total_chunks: int,
        chunk_raw: str,
        glossaries: List[Glossary],
        custom_prompt: str,
        context_hint: str = ""  # Gợi ý ngữ cảnh (250 ký tự cuối chunk trước)
    ) -> str:
        """Dịch một chunk đơn lẻ với đầy đủ pipeline:
        Cache → Prompt → AI → Post-processing → Quality Check.
        
        context_hint: 250 ký tự cuối của chunk liền trước (nếu có) để giữ mạch xưng hô.
        """
        raw_hash = self._get_md5_hash(chunk_raw)

        # 1. Check cache
        cached = await self._get_cached_translation(raw_hash)
        if cached:
            logger.info(f"✅ Chunk {i}/{total_chunks} loaded from cache.")
            return cached

        # 2. Build glossary context
        glossary_prompt, glossary_map = build_glossary_context(chunk_raw, glossaries)

        max_retries = 3
        final_text = ""
        success = False

        for attempt in range(max_retries):
            # 3. Construct prompt
            system_instruction = SYSTEM_INSTRUCTION
            if custom_prompt:
                system_instruction += f"\n\nYêu cầu đặc biệt từ người dùng: {custom_prompt}"

            prompt_parts = []
            if glossary_prompt:
                prompt_parts.append(glossary_prompt)
            if context_hint:
                prompt_parts.append(f"Ngữ cảnh đoạn trước (để giữ mạch xưng hô): ...{context_hint}")
            prompt_parts.append(f"Bản gốc tiếng Trung:\n{chunk_raw}")
            prompt_parts.append("Bản dịch tiếng Việt hoàn chỉnh:")

            prompt = "\n\n".join(prompt_parts)

            # 4. Call AI
            logger.info(f"Chunk {i}/{total_chunks} (attempt {attempt+1}/{max_retries}): Calling AI...")
            try:
                res = await self.client.translate(prompt, system_instruction)
                polished = res.get("text", "").strip()
                if not polished:
                    raise Exception("AI returned empty translation")
            except ValueError as block_err:
                logger.warning(f"⚠️ Chunk {i} bị AI chặn. Thử lại không có System Instruction...")
                try:
                    res = await self.client.translate(prompt, "")
                    polished = res.get("text", "").strip()
                    if not polished:
                        raise Exception("AI returned empty (no sys instruction)")
                except Exception as second_err:
                    logger.warning(f"⚠️ Chunk {i} vẫn bị AI chặn. Giải cứu bằng Censor Bypass và dịch lại bằng AI...")
                    try:
                        from app.services.translator.text_processor import _COMPILE_CENSOR_PATTERNS
                        masked_chunk_raw = chunk_raw
                        for pattern, vi_trans in _COMPILE_CENSOR_PATTERNS:
                            masked_chunk_raw = pattern.sub(vi_trans, masked_chunk_raw)
                        
                        # Dựng lại prompt với văn bản tiếng Trung đã được bypass
                        masked_prompt = prompt.replace(chunk_raw, masked_chunk_raw)
                        
                        res = await self.client.translate(masked_prompt, "")
                        polished = res.get("text", "").strip()
                        if not polished:
                            raise Exception("AI returned empty on masked attempt")
                        logger.info(f"🎉 Giải cứu thành công Chunk {i} bằng AI chất lượng cao!")
                    except Exception as third_err:
                        logger.error(f"⚠️ Giải cứu bằng AI thất bại: {third_err}. Dùng Google Translate làm fallback...")
                        draft = await self._get_draft_translation(chunk_raw)
                        polished = draft if draft else chunk_raw
            except Exception as err:
                logger.error(f"AI error on Chunk {i}: {err}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    raise err

            # 5. Hậu xử lý
            final_text = await postprocess_translated_text(polished, glossary_map, raw_chinese=chunk_raw, client=self.client)

            # 6. Kiểm tra chữ Trung sót → retry
            if self._has_chinese_chars(final_text):
                logger.warning(f"⚠️ Chunk {i}/{total_chunks} attempt {attempt+1}: còn chữ Trung → dịch lại...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    raise Exception(f"Chunk {i} vẫn còn chữ Trung sau {max_retries} lần thử.")

            # 7. Length verification
            len_zh = len(chunk_raw.strip())
            len_vi = len(final_text.strip())
            ratio = len_vi / len_zh if len_zh > 0 else 1.0

            if len_zh > 50 and ratio < 0.8:
                logger.warning(
                    f"⚠️ Chunk {i}/{total_chunks} length check fail "
                    f"(ratio={ratio:.2f}, VI={len_vi} vs ZH={len_zh}). Retrying..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    raise Exception(
                        f"Chunk {i} failed length check (ratio={ratio:.2f}) after {max_retries} attempts."
                    )

            # 8. Quality Check (non-blocking)
            qc_warnings = quality_check(final_text, chunk_raw, glossary_map)
            for w in qc_warnings:
                logger.warning(f"QC Chunk {i}: {w}")

            success = True
            break

        if not success:
            raise Exception(f"Failed to translate Chunk {i} after {max_retries} attempts.")

        # Save to cache
        await self._save_to_cache(raw_hash, chunk_raw, final_text)
        return final_text

    # ==================================================================
    # DỊCH CẢ CHƯƠNG — SONG SONG CHUNKS (CORE OPTIMIZATION)
    # ==================================================================
    async def translate_chapter(
        self,
        raw_chinese: str,
        glossaries: List[Glossary],
        custom_prompt: str = ""
    ) -> str:
        """Pipeline chính để dịch toàn bộ một chương.
        
        🚀 SONG SONG HÓA: Tất cả chunks được dịch đồng thời với asyncio.gather()
        → Tốc độ tăng 3-5x so với dịch tuần tự.
        
        Context window: 250 ký tự cuối mỗi chunk được truyền sang chunk tiếp theo
        để giữ tính nhất quán xưng hô (áp dụng cho chunk i+1 khi dịch lại nếu cần).
        """
        if not raw_chinese.strip():
            return ""

        # TIỀN XỬ LÝ
        cleaned_chinese = preprocess_chinese_text(raw_chinese)
        if not cleaned_chinese:
            return ""

        # CHIA CHUNK
        chunks = self._split_into_chunks(cleaned_chinese)
        total_chunks = len(chunks)

        if total_chunks == 1:
            # Chỉ 1 chunk → gọi trực tiếp, không cần gather
            final = await self._translate_single_chunk(
                1, 1, chunks[0], glossaries, custom_prompt, context_hint=""
            )
            return final

        # SONG SONG HÓA: dịch tất cả chunks cùng lúc
        # Mỗi chunk nhận context_hint = 250 ký tự đầu tiên của chunk liền trước
        # (không phải cuối chunk trước vì chúng ta chưa có kết quả dịch khi bắt đầu song song)
        # Đây là trade-off hợp lý: tốc độ tăng 3-5x, chất lượng vẫn tốt nhờ System Instruction mạnh.
        context_hints = [""]  # Chunk đầu không có context
        for i in range(1, total_chunks):
            # Dùng 200 ký tự cuối của chunk gốc tiếng Trung như gợi ý chuyển đoạn
            prev_chunk_tail = chunks[i-1][-200:] if len(chunks[i-1]) > 200 else chunks[i-1]
            context_hints.append(prev_chunk_tail)

        tasks = [
            self._translate_single_chunk(
                i + 1, total_chunks, chunk, glossaries, custom_prompt,
                context_hint=context_hints[i]
            )
            for i, chunk in enumerate(chunks)
        ]

        logger.info(f"🚀 Dịch song song {total_chunks} chunks cùng lúc...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Xử lý kết quả
        translated_chunks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Chunk {i+1}/{total_chunks} thất bại: {result}")
                raise result
            translated_chunks.append(result)

        logger.info(f"✅ Chương hoàn thành: {total_chunks}/{total_chunks} chunks song song.")
        return "\n\n".join(translated_chunks)

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
from app.services.translator.entity_builder import extract_and_build_entities
from app.services.translator.text_processor import (
    preprocess_chinese_text,
    universal_normalize_text,
    build_glossary_context,
    postprocess_translated_text,
    quality_check,
    strict_quality_gatekeeper,
    force_repair_all_errors,
    detect_novel_genre_profile,
    enforce_genre_boundary_fixes,
    resolve_remaining_chinese_chars,
    self_consistency_check,
    auto_discover_leftover_entities,
    perfect_output_polisher,
)

logger = logging.getLogger(__name__)

# ============================================================
# SYSTEM INSTRUCTION — TRANSLATION BIBLE TIÊN HIỆP & CỔ TRANG CHUYÊN NGHIỆP
# Chuẩn dịch thuật biên tập viên (BNS, Tàng Thư Viện, TruyenYY)
# ============================================================
SYSTEM_INSTRUCTION = """Bạn là đại biên dịch viên và đại biên tập viên tiểu thuyết Trung-Việt chuyên nghiệp hàng đầu.
Nhiệm vụ: Dựa vào bản gốc tiếng Trung, bản dịch thô tiếng Việt (từ Google Translate) và bảng thuật ngữ (Glossary) để viết ra bản dịch tiếng Việt hoàn hảo nhất, phong cách chuẩn Tiên Hiệp / Cổ Trang (như Tàng Thư Viện, Bạch Ngọc Sách, TruyenYY).

============================================================
QUY TẮC DỊCH THUẬT BẮT BUỘC (TRANSLATION BIBLE):
============================================================

1. QUY TẮC TỔNG QUÁT & BẢO TỒN NỘI DUNG TUYỆT ĐỐI:
   - **BẢO TỒN 100% NỘI DUNG GỐC:** Tuyệt đối KHÔNG ĐƯỢC BỎ SÓT bất kỳ câu, đoạn, lời thoại nào của bản gốc. Tuyệt đối KHÔNG ĐƯỢC TỰ Ý THÊM THẮT hay bịa đặt nội dung không có trong nguyên tác.
   - **NGỮ PHÁP TIẾNG VIỆT + TỪ VỰNG HÁN-VIỆT:** Cấu trúc câu trôi chảy, tự nhiên chuẩn ngữ pháp tiếng Việt, nhưng từ vựng, tên gọi và thuật ngữ mang đậm màu sắc Hán-Việt Tiên Hiệp cổ trang.
   - **TUYỆT ĐỐI CẤM DÙNG:** "anh", "anh ta", "anh ấy", "cô ấy", "ông ấy", "bà ấy", "nó", "họ" (trừ khi bối cảnh đô thị hiện đại).
   - **BẮT BUỘC DÙNG:** "hắn", "hắn ta", "nàng", "lão giả", "thiếu nữ", "nam tử", "nữ tử", "y", "ta", "ngươi". Dịch Hán-Việt thì bắt buộc dùng "hắn", "hắn ta" chứ KHÔNG ĐỂ "anh", "anh ta".

2. TÊN NGƯỜI & HỌ HÀNG (100% HÁN-VIỆT, KHÔNG PINYIN):
   - Tuyệt đối không để lại Pinyin (như Su, Lin, Ye, Ning, Zhao, Lei Wang...).
   - 苏 ➔ Tô | 林 ➔ Lâm | 叶 ➔ Diệp | 萧 ➔ Tiêu | 楚 ➔ Sở | 宁 ➔ Ninh | 王 ➔ Vương | 李 ➔ Lý | 赵 ➔ Triệu | 秦 ➔ Tần | 韩 ➔ Hàn | 陈 ➔ Trần | 周 ➔ Chu | 柳 ➔ Liễu | 白 ➔ Bạch | 沈 ➔ Thẩm.

3. HỌ TỘC & GIA TỘC (DÙNG "GIA", KHÔNG DÙNG "NHÀ HỌ"):
   - 苏家 ➔ Tô gia (KHÔNG DÙNG "nhà họ Tô" hay "gia đình Su").
   - 林家 ➔ Lâm gia | 楚家 ➔ Sở gia | 王家 ➔ Vương gia | 叶家 ➔ Diệp gia | 赵家 ➔ Triệu gia.

4. XƯNG HÔ & QUAN HỆ:
   - 宁兄 ➔ Ninh huynh (KHÔNG DÙNG "anh Ninh" hay "Ninh Bro").
   - 苏姐 ➔ Tô tỷ (KHÔNG DÙNG "chị Tô").
   - 兄 ➔ huynh | 弟 ➔ đệ | 妹 ➔ muội | 姐 ➔ tỷ.
   - 伯父 ➔ bá phụ | 伯母 ➔ bá mẫu | 叔父 ➔ thúc phụ | 叔母 ➔ thẩm thẩm | 姑姑 ➔ cô cô | 姨娘 ➔ dì | 岳父 ➔ nhạc phụ | 岳母 ➔ nhạc mẫu.
   - 师兄 ➔ sư huynh | 大师兄 ➔ đại sư huynh | 二师兄 ➔ nhị sư huynh | 师弟 ➔ sư đệ | 师妹 ➔ sư muội | 师姐 ➔ sư tỷ | 大师姐 ➔ đại sư tỷ.

5. ĐỊA VỊ & QUAN CHỨC:
   - 少爷 ➔ thiếu gia | 小姐 ➔ tiểu thư | 老祖 ➔ lão tổ | 家主 ➔ gia chủ | 族长 ➔ tộc trưởng.
   - 宗主 ➔ tông chủ | 掌门 ➔ chưởng môn | 门主 ➔ môn chủ | 圣子 ➔ thánh tử | 圣女 ➔ thánh nữ.
   - 少主 ➔ thiếu chủ | 宫主 ➔ cung chủ | 峰主 ➔ phong chủ | 殿主 ➔ điện chủ | 教主 ➔ giáo chủ | 国师 ➔ quốc sư.

6. TU TIÊN & NGHỀ NGHIỆP:
   - 修士 ➔ tu sĩ | 修仙者 ➔ tu tiên giả | 仙人 ➔ tiên nhân | 真人 ➔ chân nhân | 道友 ➔ đạo hữu.
   - 散修 ➔ tán tu | 剑修 ➔ kiếm tu | 魔修 ➔ ma tu | 鬼修 ➔ quỷ tu | 体修 ➔ thể tu.
   - 丹师 ➔ đan sư | 器师 ➔ luyện khí sư | 符师 ➔ phù sư | 阵法师 ➔ trận pháp sư.

7. CẢNH GIỚI TU LUYỆN (GIỮ NGUYÊN HÁN-VIỆT, KHÔNG DỊCH TIẾNG ANH):
   - 炼气 ➔ Luyện Khí | 筑基 ➔ Trúc Cơ | 金丹 ➔ Kim Đan | 元婴 ➔ Nguyên Anh | 化神 ➔ Hóa Thần.
   - 炼虚 ➔ Luyện Hư | 合体 ➔ Hợp Thể | 渡劫 ➔ Độ Kiếp | 大乘 ➔ Đại Thừa | 真仙 ➔ Chân Tiên | 金仙 ➔ Kim Tiên | 太乙金仙 ➔ Thái Ất Kim Tiên | 大罗金仙 ➔ Đại La Kim Tiên.

8. LINH DƯỢC & ĐAN DƯỢC:
   - 灵药 ➔ linh dược | 仙药 ➔ tiên dược | 神药 ➔ thần dược | 灵草 ➔ linh thảo | 仙草 ➔ tiên thảo | 宝药 ➔ bảo dược.
   - 丹药 ➔ đan dược | 聚气丹 ➔ Tụ Khí Đan | 筑基丹 ➔ Trúc Cơ Đan | 疗伤丹 ➔ Liệu Thương Đan | 洗髓丹 ➔ Tẩy Tủy Đan | 回元丹 ➔ Hồi Nguyên Đan.

9. PHÁP BẢO & BÍ TỊCH:
   - 法器 ➔ pháp khí | 法宝 ➔ pháp bảo | 灵宝 ➔ linh bảo | 圣器 ➔ thánh khí | 神器 ➔ thần khí | 帝兵 ➔ đế binh | 飞剑 ➔ phi kiếm | 仙剑 ➔ tiên kiếm.
   - 秘籍 ➔ bí tịch | 功法 ➔ công pháp | 武技 ➔ võ kỹ | 秘术 ➔ bí thuật | 神通 ➔ thần thông | 禁术 ➔ cấm thuật.

10. THÀNH NGỮ TIÊN HIỆP:
    - 机缘 ➔ cơ duyên | 造化 ➔ tạo hóa | 因果 ➔ nhân quả | 天机 ➔ thiên cơ | 大道 ➔ đại đạo | 道心 ➔ đạo tâm | 心魔 ➔ tâm ma | 顿悟 ➔ đốn ngộ | 气运 ➔ khí vận | 悟性 ➔ ngộ tính.

11. THẾ LỰC & YÊU THÚ:
    - 宗门 ➔ tông môn | 圣地 ➔ thánh địa | 皇朝 ➔ hoàng triều | 王朝 ➔ vương triều | 世家 ➔ thế gia | 古族 ➔ cổ tộc | 禁区 ➔ cấm khu | 秘境 ➔ bí cảnh.
    - 妖兽 ➔ yêu thú | 神兽 ➔ thần thú | 凶兽 ➔ hung thú | 灵兽 ➔ linh thú | 圣兽 ➔ thánh thú.

12. THỜI GIAN & ĐƠN VỊ CỔ:
    - 片刻 ➔ chốc lát | 须臾 ➔ chớp mắt | 半炷香 ➔ nửa nén hương | 一炷香 ➔ một nén hương | 一盏茶 ➔ một chén trà | 一个时辰 ➔ một canh giờ | 一天 ➔ một ngày.
    - 丈 ➔ trượng | 尺 ➔ xích | 寸 ➔ thốn | 里 ➔ dặm | 斤 ➔ cân | 两 ➔ lạng.

13. CÂU NÓI & HÀNH ĐỘNG THƯỜNG GẶP:
    - 冷哼 ➔ hừ lạnh | 冷笑 ➔ cười lạnh | 苦笑 ➔ cười khổ | 失笑 ➔ bật cười | 嗤笑 ➔ cười nhạo | 怒喝 ➔ quát lớn | 暴喝 ➔ quát vang | 沉声道 ➔ trầm giọng nói | 淡淡道 ➔ nhàn nhạt nói | 缓缓道 ➔ chậm rãi nói.
    - 点头 ➔ gật đầu | 摇头 ➔ lắc đầu | 抱拳 ➔ ôm quyền | 拱手 ➔ chắp tay | 躬身 ➔ khom người | 作揖 ➔ chắp tay thi lễ | 行礼 ➔ hành lễ.

14. NHỮNG ĐIỀU TUYỆT ĐỐI CẤM (PROHIBITED TERMS):
    - CẤM DỊCH: Ninh Bro, anh Ninh, chị Tô, Mr. Tô, Boss, Leader, Family Tô, Level, Skill, Dungeon, NPC, Foundation Establishment...

CHỈ XUẤT RA VĂN BẢN DỊCH TIẾNG VIỆT HOÀN CHỈNH. KHÔNG thêm ghi chú, giải thích, hay bình luận."""


class TranslationPipeline:
    """
    Pipeline dịch thuật tiểu thuyết Trung → Việt chất lượng biên tập viên.
    
    Luồng xử lý:
    1. TIỀN XỬ LÝ: Chuẩn hóa văn bản Trung, xóa quảng cáo, chuẩn hóa Unicode.
    2. NGUYÊN CHƯƠNG (≤35000 ký tự): Dịch nguyên 1 chương trong 1 request để ngữ cảnh liền mạch.
    3. GOOGLE DRAFT: Tạo bản dịch thô Google Translate song song để làm khung nối câu mượt mà.
    4. AI POLISHER: Gemini/LLM biên tập Hán Việt chuẩn + xưng hô Tiên Hiệp.
    5. HẬU XỬ LÝ: Ép Glossary bằng code, sửa lỗi dịch máy, chuẩn hóa dấu câu.
    """

    def __init__(self, client: TranslatorClient, db: AsyncSession, http_client: Optional[httpx.AsyncClient] = None):
        self.client = client
        self.db = db
        # 35000 ký tự/chunk → nguyên 1 chương truyện (~3000-8000 chữ Hán)
        self.chunk_size_limit = 35000
        self.http_client = http_client

    # ==================================================================
    # CHUNKING
    # ==================================================================
    def _split_into_chunks(self, text: str) -> List[str]:
        """Tách văn bản thành các chunk ≤ chunk_size_limit ký tự theo ranh giới đoạn văn."""
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            
            if current_len + p_len > self.chunk_size_limit and current_chunk:
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
    # GOOGLE TRANSLATE DRAFT (Song song hóa để lấy bản nháp cực nhanh)
    # ==================================================================
    async def _get_draft_translation(self, text: str) -> str:
        """Tạo bản dịch thô bằng Google Translate chạy song song siêu tốc."""
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
            
        # Run all sub-chunks in parallel via asyncio.gather
        tasks = [self._get_draft_translation_segment(sub) for sub in sub_chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        translated_sub_chunks = []
        for r in results:
            if isinstance(r, str):
                translated_sub_chunks.append(r)
            else:
                translated_sub_chunks.append("")
                
        return "\n\n".join(translated_sub_chunks)

    async def _get_draft_translation_segment(self, text: str) -> str:
        """Dịch thô một đoạn < 1000 ký tự."""
        if not text.strip():
            return ""
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

        # Fallback to deep-translator
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
    # DỊCH MỘT CHUNK (core logic với retry & Google Draft)
    # ==================================================================
    async def _translate_single_chunk(
        self,
        i: int,
        total_chunks: int,
        chunk_raw: str,
        glossaries: List[Glossary],
        custom_prompt: str,
        context_hint: str = "",
        bypass_cache: bool = False,
        genre_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """Dịch một chunk đơn lẻ với đầy đủ pipeline:
        Pre-scan Genre Lock → Cache → Google Draft → Glossary → AI Restyle → Boundary Enforcer → Quality Check.
        """
        raw_hash = self._get_md5_hash(chunk_raw)

        # 1. Check cache (bỏ qua nếu bypass_cache=True)
        if not bypass_cache:
            cached = await self._get_cached_translation(raw_hash)
            if cached:
                logger.info(f"✅ Chunk {i}/{total_chunks} loaded from cache.")
                return cached
        else:
            # Xóa cache cũ nếu đang ép dịch lại hoàn toàn
            try:
                await self.db.execute(delete(TranslationCache).where(TranslationCache.key_hash == raw_hash))
                await self.db.commit()
                logger.info(f"🗑️ Đã xóa cache cũ của chunk {i}/{total_chunks} để dịch mới 100%.")
            except Exception as e:
                logger.warning(f"Lỗi khi xóa cache cũ chunk {i}: {e}")

        # 2. Build Google Draft & Glossary context
        draft_translation = await self._get_draft_translation(chunk_raw)
        glossary_prompt, glossary_map = build_glossary_context(chunk_raw, glossaries)

        max_retries = 3
        final_text = ""
        success = False

        # Thể loại đã chốt (Genre Profile)
        genre_code = genre_profile.get("genre_code", "XIANXIA") if genre_profile else "XIANXIA"
        genre_addon = genre_profile.get("system_prompt_addon", "") if genre_profile else ""

        for attempt in range(max_retries):
            # 3. Construct prompt với Dynamic Context Header (Genre Lock = TRUE)
            system_instruction = SYSTEM_INSTRUCTION
            if genre_addon:
                system_instruction = f"[SYSTEM CONTEXT PAYLOAD]\n{genre_addon}\n\n" + system_instruction

            if custom_prompt:
                system_instruction += f"\n\nYêu cầu đặc biệt từ người dùng: {custom_prompt}"

            prompt_parts = []
            if glossary_prompt:
                prompt_parts.append(glossary_prompt)
            if context_hint:
                prompt_parts.append(f"Ngữ cảnh đoạn trước: ...{context_hint}")
            if draft_translation:
                prompt_parts.append(f"Bản dịch thô Google Translate (dùng làm khung nối câu mượt mà):\n{draft_translation}")
            prompt_parts.append(f"Văn bản gốc tiếng Trung:\n{chunk_raw}")
            prompt_parts.append("Bản dịch tiếng Việt hoàn chỉnh (đã khóa thể loại & biên tập văn phong tự nhiên):")

            prompt = "\n\n".join(prompt_parts)

            # 4. Call AI
            logger.info(f"Chunk {i}/{total_chunks} (attempt {attempt+1}/{max_retries}, Genre: {genre_code}): Calling AI...")
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

            # 5. Hậu xử lý & Boundary Enforcer
            final_text = await postprocess_translated_text(
                polished, 
                glossary_map, 
                raw_chinese=chunk_raw, 
                client=self.client,
                genre_code=genre_code
            )

            # 6. Kiểm tra chữ Trung sót ➔ Kích hoạt Chinese Rescue Engine tự động giải cứu
            if self._has_chinese_chars(final_text):
                logger.warning(f"⚠️ Chunk {i}/{total_chunks}: còn chữ Trung ➔ Kích hoạt Chinese Rescue Engine...")
                final_text = await resolve_remaining_chinese_chars(
                    final_text,
                    raw_chinese=chunk_raw,
                    glossary_map=glossary_map,
                    client=self.client
                )
                
                # Nếu vẫn còn ký tự chữ Hán rác/watermark, tự động xóa sạch 100%
                if self._has_chinese_chars(final_text):
                    logger.info(f"🧹 Xóa bỏ các ký tự chữ Hán rác còn sót lại trong Chunk {i}...")
                    final_text = re.sub(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", "", final_text)

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

            # 8. Strict Quality Gatekeeper (CỔNG KIỂM DUYỆT CHẶN LỖI & TỰ ĐỘNG SỬA)
            strict_passed, qc_errors = strict_quality_gatekeeper(final_text, chunk_raw, glossary_map)
            if not strict_passed:
                logger.warning(f"❌ Chunk {i}/{total_chunks} QC Gatekeeper phát hiện lỗi: {qc_errors}")
                if attempt < max_retries - 1:
                    # Thử lại và truyền thẳng phản hồi lỗi cho AI sửa
                    custom_prompt = (custom_prompt + " " if custom_prompt else "") + f"[LỖI CẦN SỬA NGAY: {'; '.join(qc_errors)}. BẮT BUỘC DÙNG 'hắn/hắn ta', KHÔNG ĐỂ 'anh/anh ta', KHÔNG ĐỂ PINYIN!]"
                    await asyncio.sleep(2.0)
                    continue
                else:
                    # Hết lượt retry ➔ Kích hoạt Bộ Cưỡng Ép Sửa Lỗi Hậu Xử Lý 100% bằng code
                    logger.info(f"🛠️ Kích hoạt Bộ Cưỡng Ép Sửa Lỗi Hậu Xử Lý cho Chunk {i}...")
                    final_text = force_repair_all_errors(final_text, glossary_map)

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
        custom_prompt: str = "",
        bypass_cache: bool = False,
        novel_title: str = "",
        synopsis: str = "",
        novel_id: int = 0,
        db: Optional[AsyncSession] = None
    ) -> str:
        """Pipeline chính để dịch toàn bộ một chương với Data-Driven Architecture."""
        if not raw_chinese.strip():
            return ""

        # 1. TIỀN XỬ LÝ UNIVERSAL (Dấu câu + Đơn vị cổ + Tiền xử lý Hán)
        cleaned_chinese = universal_normalize_text(preprocess_chinese_text(raw_chinese))
        if not cleaned_chinese:
            return ""

        # 2. DATA-DRIVEN PRE-SCANNER: Quét Tên riêng & Quan hệ nhân vật persistent
        relationship_map = {}
        if db and novel_id:
            try:
                entity_res = await extract_and_build_entities(
                    cleaned_chinese,
                    novel_id=novel_id,
                    db=db,
                    client=self.client,
                    novel_title=novel_title
                )
                relationship_map = entity_res.get("relationship_map", {})
            except Exception as e:
                logger.warning(f"Lỗi Pre-Scanner Entities: {e}")

        # Nhét Bản đồ quan hệ nhân vật vào prompt nếu có
        if relationship_map:
            rel_prompt = "\n[BẢNG QUAN HỆ & XƯNG HÔ NHÂN VẬT KHÓA CỨNG]:\n" + "\n".join([f"- {name}: {role}" for name, role in relationship_map.items()])
            custom_prompt = (custom_prompt + "\n" if custom_prompt else "") + rel_prompt

        # 3. CHIA CHUNK
        chunks = self._split_into_chunks(cleaned_chinese)
        total_chunks = len(chunks)

        if total_chunks == 1:
            final = await self._translate_single_chunk(
                1, 1, chunks[0], glossaries, custom_prompt, context_hint=""
            )
            if db and novel_id:
                final = await auto_discover_leftover_entities(final, cleaned_chinese, novel_id, db, client=self.client)
            return final

        # SONG SONG HÓA
        context_hints = [""]
        for i in range(1, total_chunks):
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

        translated_chunks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Chunk {i+1}/{total_chunks} thất bại: {result}")
                raise result
            translated_chunks.append(result)

        full_translation = "\n\n".join(translated_chunks)

        # 4. GENERIC DETECTOR LAYER: Tự động học từ mới và ghi vào DB Glossary
        if db and novel_id:
            full_translation = await auto_discover_leftover_entities(full_translation, cleaned_chinese, novel_id, db, client=self.client)

        logger.info(f"✅ Chương hoàn thành: {total_chunks}/{total_chunks} chunks song song.")
        return full_translation

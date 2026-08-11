import httpx
import asyncio
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

CLIENT_ENGINES = ["dict-chrome-ex", "at", "gtx"]


def _chunk_text_by_paragraphs(text: str, max_chars: int = 2500) -> List[str]:
    """
    Chia nhỏ văn bản thành các chunk không vượt quá max_chars,
    ưu tiên tách theo đoạn (\n\n) hoặc dòng (\n) để giữ nguyên ngữ cảnh câu.
    """
    if not text:
        return []

    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for line in lines:
        line_len = len(line) + 1  # tính cả ký tự \n
        if current_length + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


async def _translate_single_chunk(
    client: httpx.AsyncClient, 
    chunk: str, 
    client_engine: str = "dict-chrome-ex",
    source_lang: str = "zh-CN", 
    target_lang: str = "vi"
) -> Optional[str]:
    """
    Gửi 1 đoạn văn bản tới Google Translate API bằng HTTP POST.
    Hỗ trợ format dj=1 (trả về JSON sentences) hoặc mảng legacy.
    """
    if not chunk or not chunk.strip():
        return ""

    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": client_engine,
        "sl": source_lang,
        "tl": target_lang,
        "dt": "t",
        "dj": "1",
    }
    data = {
        "q": chunk
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "Accept": "*/*",
    }

    try:
        resp = await client.post(url, params=params, data=data, headers=headers, timeout=30.0)
        if resp.status_code == 200:
            res_json = resp.json()
            if isinstance(res_json, dict) and "sentences" in res_json:
                sentences = res_json.get("sentences", [])
                translated_parts = [s.get("trans", "") for s in sentences if s.get("trans")]
                return "".join(translated_parts)
            elif isinstance(res_json, list) and len(res_json) > 0 and res_json[0]:
                translated_parts = [p[0] for p in res_json[0] if p and len(p) > 0 and p[0]]
                return "".join(translated_parts)
        elif resp.status_code == 429:
            logger.warning(f"[TRANSLATOR-{client_engine}] ⚠️ Rate limited (429).")
            return None
        else:
            logger.warning(f"[TRANSLATOR-{client_engine}] ⚠️ HTTP {resp.status_code}.")
            return None
    except Exception as e:
        logger.warning(f"[TRANSLATOR-{client_engine}] ⚠️ Exception: {e}")
        return None


async def translate_text_via_google_nmt(
    text: str, 
    source_lang: str = "zh-CN", 
    target_lang: str = "vi",
    client_engine: str = "dict-chrome-ex"
) -> Optional[str]:
    """
    Dịch văn bản bằng NMT Engine của Chrome / Google Translate (client='dict-chrome-ex' hoặc 'at').
    Bảo toàn ngắt đoạn và định dạng văn bản gốc.
    """
    if not text or not text.strip():
        return ""

    chunks = _chunk_text_by_paragraphs(text, max_chars=2800)
    translated_chunks = []

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                translated_chunks.append("")
                continue

            result = await _translate_single_chunk(
                client, 
                chunk, 
                client_engine=client_engine, 
                source_lang=source_lang, 
                target_lang=target_lang
            )

            if result is None:
                return None

            translated_chunks.append(result)

            # Delay nhẹ giữa các chunk để chống rate-limit
            if i < len(chunks) - 1:
                await asyncio.sleep(0.3)

    return "\n".join(translated_chunks)


async def translate_text_via_google(text: str, source_lang: str = "zh-CN", target_lang: str = "vi") -> str:
    """
    Fallback dịch bằng GTX legacy endpoint (hỗ trợ cả GET & POST).
    """
    if not text or not text.strip():
        return ""

    chunks = _chunk_text_by_paragraphs(text, max_chars=1800)
    translated_chunks = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            if not chunk.strip():
                translated_chunks.append("")
                continue

            res = await _translate_single_chunk(
                client, 
                chunk, 
                client_engine="gtx", 
                source_lang=source_lang, 
                target_lang=target_lang
            )

            if res is not None:
                translated_chunks.append(res)
            else:
                translated_chunks.append(chunk)

            await asyncio.sleep(0.2)

    return "\n".join(translated_chunks)


async def translate_text_best_quality(text: str, source_lang: str = "zh-CN", target_lang: str = "vi") -> str:
    """
    Hàm dịch tối ưu chất lượng tốt nhất có thể:
    1. Thử client 'dict-chrome-ex' (Chrome Extension NMT model - chuẩn xưng hô và câu văn nhất)
    2. Thử client 'at' (Google Web Translate NMT model)
    3. Fallback sang 'gtx' (Legacy Google Translate API)
    """
    if not text or not text.strip():
        return ""

    for engine in ["dict-chrome-ex", "at"]:
        try:
            res = await translate_text_via_google_nmt(
                text, 
                source_lang=source_lang, 
                target_lang=target_lang, 
                client_engine=engine
            )
            if res and res.strip():
                latin_chars = len(re.findall(r'[a-zA-ZÀ-ỹ]', res))
                total_chars = len(res.strip())
                if total_chars > 0 and (latin_chars / total_chars) > 0.2:
                    logger.info(f"[TRANSLATOR] ✅ Dịch thành công bằng engine '{engine}' ({len(text)} -> {len(res)} ký tự)")
                    return res
        except Exception as e:
            logger.warning(f"[TRANSLATOR] Engine '{engine}' gặp lỗi: {e}")

    # Fallback cuối cùng sang GTX
    logger.info("[TRANSLATOR] 🔄 Fallback sang GTX endpoint...")
    return await translate_text_via_google(text, source_lang, target_lang)

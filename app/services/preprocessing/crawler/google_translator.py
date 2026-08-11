import httpx
import asyncio
import re
import random
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.0.0 Safari/537.36",
]


def _chunk_text_by_paragraphs(text: str, max_chars: int = 2200) -> List[str]:
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
        line_len = len(line) + 1
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
    client_engine: str = "gtx",
    source_lang: str = "zh-CN", 
    target_lang: str = "vi",
    max_retries: int = 2
) -> Optional[str]:
    """
    Gửi 1 đoạn văn bản tới Google Translate API bằng HTTP GET hoặc POST với retry.
    """
    if not chunk or not chunk.strip():
        return ""

    url = "https://translate.googleapis.com/translate_a/single"

    for attempt in range(max_retries):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        try:
            if client_engine == "dict-chrome-ex":
                params = {
                    "client": client_engine,
                    "sl": source_lang,
                    "tl": target_lang,
                    "dt": "t",
                    "dj": "1",
                    "q": chunk
                }
                resp = await client.get(url, params=params, headers=headers, timeout=25.0)
            else:
                params = {
                    "client": client_engine,
                    "sl": source_lang,
                    "tl": target_lang,
                    "dt": "t",
                    "dj": "1",
                }
                data = {"q": chunk}
                headers["Content-Type"] = "application/x-www-form-urlencoded;charset=utf-8"
                resp = await client.post(url, params=params, data=data, headers=headers, timeout=25.0)

            if resp.status_code == 200:
                res_json = resp.json()
                if isinstance(res_json, dict) and "sentences" in res_json:
                    sentences = res_json.get("sentences", [])
                    translated_parts = [s.get("trans", "") for s in sentences if s.get("trans")]
                    if translated_parts:
                        return "".join(translated_parts)
                elif isinstance(res_json, list) and len(res_json) > 0 and res_json[0]:
                    translated_parts = [p[0] for p in res_json[0] if p and len(p) > 0 and p[0]]
                    if translated_parts:
                        return "".join(translated_parts)
            elif resp.status_code in (429, 503):
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                return None
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return None
        except Exception:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
                continue
            return None

    return None


async def translate_text_via_google_nmt(
    text: str, 
    source_lang: str = "zh-CN", 
    target_lang: str = "vi",
    client_engine: str = "at"
) -> Optional[str]:
    """
    Dịch văn bản bằng NMT Engine của Google Translate.
    """
    if not text or not text.strip():
        return ""

    chunks = _chunk_text_by_paragraphs(text, max_chars=2400)
    translated_chunks = []

    async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
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

            if i < len(chunks) - 1:
                await asyncio.sleep(0.25)

    return "\n".join(translated_chunks)


async def translate_text_via_google(text: str, source_lang: str = "zh-CN", target_lang: str = "vi") -> str:
    """
    Fallback dịch bằng GTX legacy endpoint (GET/POST với User-Agent rotation).
    """
    if not text or not text.strip():
        return ""

    chunks = _chunk_text_by_paragraphs(text, max_chars=1800)
    translated_chunks = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
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
    1. Thử client 'at' (NMT Engine chất lượng cao)
    2. Thử client 'dict-chrome-ex' (Chrome Extension Engine)
    3. Fallback sang 'gtx' (Legacy Google Engine)
    """
    if not text or not text.strip():
        return ""

    for engine in ["at", "dict-chrome-ex"]:
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
        except Exception:
            pass

    return await translate_text_via_google(text, source_lang, target_lang)

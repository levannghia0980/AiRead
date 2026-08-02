import httpx
import asyncio
from typing import List

async def translate_text_via_google(text: str, source_lang: str = "zh-CN", target_lang: str = "vi") -> str:
    """
    Dịch văn bản tiếng Trung sang tiếng Việt bằng API Google Translate miễn phí (GTX).
    Tách văn bản thành các đoạn nhỏ để tránh giới hạn độ dài URL.
    """
    if not text or not text.strip():
        return ""

    # Tách văn bản thành các dòng/đoạn để dịch an toàn
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for line in lines:
        if current_length + len(line) > 1500:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line)
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    translated_chunks = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in chunks:
            if not chunk.strip():
                translated_chunks.append("")
                continue
                
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": source_lang,
                "tl": target_lang,
                "dt": "t",
                "q": chunk
            }
            
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    res_json = resp.json()
                    # Google trả về danh sách các đoạn dịch nhỏ ở index 0
                    translated_parts = []
                    if res_json and len(res_json) > 0 and res_json[0]:
                        for part in res_json[0]:
                            if part and len(part) > 0:
                                translated_parts.append(part[0])
                    translated_chunks.append("".join(translated_parts))
                else:
                    translated_chunks.append(chunk) # Fallback nếu lỗi
            except Exception:
                translated_chunks.append(chunk)
                await asyncio.sleep(0.5)

    return "\n".join(translated_chunks)

"""
Multi-Source Proxy Scraper for Edge-TTS
Tập hợp danh sách lớn các proxy HTTPS/HTTP từ các nguồn API và GitHub uy tín.
Tự động kiểm tra trực tiếp với máy chủ Edge-TTS và lọc ra các proxy siêu tốc (< 3s).
"""

import asyncio
import os
import sys
import time
import urllib.request
import edge_tts
from typing import List, Tuple, Set

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]


async def _test_fast_proxy(proxy_url: str, max_timeout: float = 4.5) -> Tuple[bool, float, str]:
    """Kiểm tra proxy trực tiếp với Edge-TTS"""
    tmp_out = os.path.join(os.environ.get("TEMP", "."), f"_pf_{abs(hash(proxy_url)) % 100000}.mp3")
    t0 = time.time()
    try:
        comm = edge_tts.Communicate("Hi", "vi-VN-HoaiMyNeural", proxy=proxy_url)
        await asyncio.wait_for(comm.save(tmp_out), timeout=max_timeout)
        dur = time.time() - t0
        if os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 500:
            return True, dur, proxy_url
    except Exception:
        pass
    finally:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
    return False, 999.0, proxy_url


async def fetch_fast_proxy_pool(
    target_count: int = 10,
    max_check: int = 150,
    exclude_proxies: Set[str] = None
) -> List[str]:
    """
    Cào & test nhanh hàng loạt proxy song song bằng asyncio.gather.
    """
    raw_proxies = []

    def _fetch_url(url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    loop = asyncio.get_event_loop()
    fetch_tasks = [loop.run_in_executor(None, _fetch_url, u) for u in PROXY_SOURCES]
    results = await asyncio.gather(*fetch_tasks)

    for text in results:
        if not text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line and ":" in line and not line.startswith("#"):
                if not line.startswith("http") and not line.startswith("socks"):
                    line = f"http://{line}"
                if not exclude_proxies or line not in exclude_proxies:
                    raw_proxies.append(line)

    import random
    unique = list(dict.fromkeys(raw_proxies))
    random.shuffle(unique)
    check_list = unique[:max_check]
    if not check_list:
        return []

    sem = asyncio.Semaphore(20)
    async def _bound_test(p):
        async with sem:
            return await _test_fast_proxy(p, max_timeout=3.5)

    tasks = [_bound_test(p) for p in check_list]
    test_results = await asyncio.gather(*tasks, return_exceptions=True)

    working = [res for res in test_results if isinstance(res, tuple) and res[0]]
    working.sort(key=lambda x: x[1])

    fast_proxies = [res[2] for res in working[:target_count]]
    return fast_proxies

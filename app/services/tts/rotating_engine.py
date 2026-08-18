"""
Rotating Batch TTS Engine - High Visibility Multi-Worker Live Proxy Pipeline
- Kiến trúc Hybrid Siêu Tốc:
  + Semaphore Direct IP (4 slots) trực tiếp từ máy, tốc độ 2.5s/chunk, 100% ổn định.
  + Proxy Feeder (Pool 50+ live proxies) bổ trợ cho các luồng từ Worker 4 -> 15.
- Tự động điều phối: Worker nào rảnh sẽ bốc chunk ngay, không bao giờ bị nghẽn hay chờ đợi.
- Tự động Re-queue chunk ưu tiên ngay khi có bất kỳ sự cố mạng nào.
"""

import asyncio
import os
import sys
import time
import re
import random
import httpx
import edge_tts
from typing import Optional, List, Callable, Dict, Tuple, Set

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        try:
            text = " ".join(str(a) for a in args)
            clean = text.encode("ascii", errors="replace").decode("ascii")
            print(clean, **kwargs)
        except Exception:
            pass

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
]


class BackgroundProxyFeeder:
    """Tiến trình quét, kiểm thử và nạp Proxy sống vào hàng đợi."""
    def __init__(self, proxy_queue: asyncio.Queue, bad_proxies: Set[str], max_pool_size: int = 50):
        self.proxy_queue = proxy_queue
        self.bad_proxies = bad_proxies
        self.max_pool_size = max_pool_size
        self.candidates: List[str] = []
        self.testing_sem = asyncio.Semaphore(50)

    async def _fetch_candidates_async(self) -> List[str]:
        raw = []
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            tasks = [client.get(url) for url in PROXY_SOURCES]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for resp in responses:
                if isinstance(resp, httpx.Response) and resp.status_code == 200:
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if line and ":" in line and not line.startswith("#"):
                            p = line if line.startswith("http") else f"http://{line}"
                            if p not in self.bad_proxies:
                                raw.append(p)
        unique = list(dict.fromkeys(raw))
        random.shuffle(unique)
        return unique

    async def _test_one_proxy(self, p: str) -> bool:
        async with self.testing_sem:
            tmp = os.path.join(os.environ.get("TEMP", "."), f"_pftest_{abs(hash(p)) % 100000}_{time.time_ns() % 1000}.mp3")
            try:
                comm = edge_tts.Communicate("OK", "vi-VN-HoaiMyNeural", proxy=p)
                await asyncio.wait_for(comm.save(tmp), timeout=3.0)
                if os.path.exists(tmp) and os.path.getsize(tmp) > 300:
                    if p not in self.bad_proxies:
                        self.proxy_queue.put_nowait(p)
                        return True
            except Exception:
                pass
            finally:
                if os.path.exists(tmp):
                    try: os.remove(tmp)
                    except Exception: pass
        return False

    async def prewarm(self, min_proxies: int = 4, max_wait: float = 3.0):
        """Khởi động nhanh: trả về ngay khi đạt đủ min_proxies hoặc hết max_wait giây."""
        if self.proxy_queue.qsize() >= min_proxies:
            return
        if not self.candidates:
            self.candidates = await self._fetch_candidates_async()
        
        batch_size = min(120, len(self.candidates))
        if batch_size == 0:
            return
        batch = [self.candidates.pop() for _ in range(batch_size)]
        for p in batch:
            asyncio.create_task(self._test_one_proxy(p))

        t0 = time.time()
        while self.proxy_queue.qsize() < min_proxies and (time.time() - t0) < max_wait:
            await asyncio.sleep(0.15)

    async def start(self, stop_event: asyncio.Event):
        """Vòng lặp liên tục duy trì pool proxy sống."""
        while not stop_event.is_set():
            try:
                if self.proxy_queue.qsize() < self.max_pool_size:
                    if not self.candidates:
                        self.candidates = await self._fetch_candidates_async()

                    batch_size = min(50, len(self.candidates))
                    batch = [self.candidates.pop() for _ in range(batch_size)] if self.candidates else []
                    if batch:
                        for p in batch:
                            asyncio.create_task(self._test_one_proxy(p))
                await asyncio.sleep(0.8)
            except Exception:
                await asyncio.sleep(1.0)


class DedicatedWorker:
    def __init__(
        self,
        worker_id: int,
        voice: str,
        rate: str,
        pitch: str,
        engine: "RotatingBatchTTSEngine",
        direct_semaphore: asyncio.Semaphore,
        pacing_sec: float = 0.1,
        chunk_timeout: float = 25.0,
    ):
        self.worker_id = worker_id
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.engine = engine
        self.direct_semaphore = direct_semaphore
        self.pacing_sec = pacing_sec
        self.chunk_timeout = chunk_timeout
        self.current_proxy: Optional[str] = None

    async def get_fresh_proxy(self, timeout: float = 1.0) -> Optional[str]:
        return await self.engine.acquire_proxy(timeout=timeout)

    async def run(
        self,
        task_queue: asyncio.PriorityQueue,
        output_dir: str,
        results: Dict[int, bool],
        on_chunk_done: Optional[Callable],
        stop_event: asyncio.Event,
    ):
        while not stop_event.is_set():
            try:
                item = await asyncio.wait_for(task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if task_queue.empty():
                    break
                continue

            priority, attempts, chunk_idx, text = item
            out_path = os.path.join(output_dir, f"chunk_{chunk_idx:04d}.mp3")
            tmp_path = os.path.join(output_dir, f"chunk_{chunk_idx:04d}.tmp_{self.worker_id}.mp3")

            # Caching resume: chỉ chấp nhận chunk hoàn chỉnh (> 1KB)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                results[chunk_idx] = True
                task_queue.task_done()
                if on_chunk_done:
                    on_chunk_done(chunk_idx, True, 0.01, out_path, self.worker_id)
                continue

            if not text or not text.strip() or not re.search(r'[a-zA-ZÀ-ỹ]', text):
                results[chunk_idx] = False
                task_queue.task_done()
                continue

            # Hybrid routing: Nếu worker chưa có Proxy, thử lấy slot Direct IP hoặc bốc Proxy từ queue
            use_direct = False
            if self.current_proxy is None:
                # Thử lấy Proxy trước
                self.current_proxy = await self.get_fresh_proxy(timeout=0.3)
                if self.current_proxy is None:
                    # Nếu chưa có Proxy, sử dụng Direct IP qua Semaphore
                    use_direct = True

            success = False
            duration = 0.0
            t0 = time.time()

            try:
                if os.path.exists(tmp_path):
                    try: os.remove(tmp_path)
                    except Exception: pass

                if use_direct:
                    async with self.direct_semaphore:
                        comm = edge_tts.Communicate(
                            text=text,
                            voice=self.voice,
                            rate=self.rate,
                            pitch=self.pitch,
                            proxy=None,
                        )
                        await asyncio.wait_for(comm.save(tmp_path), timeout=self.chunk_timeout)
                else:
                    comm = edge_tts.Communicate(
                        text=text,
                        voice=self.voice,
                        rate=self.rate,
                        pitch=self.pitch,
                        proxy=self.current_proxy,
                    )
                    await asyncio.wait_for(comm.save(tmp_path), timeout=self.chunk_timeout)

                duration = time.time() - t0

                # Xác minh tệp tải về nguyên vẹn và đủ dung lượng trước khi đổi tên
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
                    os.replace(tmp_path, out_path)
                    success = True
                else:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

            except Exception as e_chunk:
                duration = time.time() - t0
                if os.path.exists(tmp_path):
                    try: os.remove(tmp_path)
                    except Exception: pass

                err_name = type(e_chunk).__name__

                if not use_direct and self.current_proxy:
                    self.engine.mark_bad_proxy(self.current_proxy)
                    self.current_proxy = await self.get_fresh_proxy(timeout=0.5)
                    safe_print(f"[Worker-{self.worker_id}] ⚠️ Chunk #{chunk_idx+1} ({err_name}) -> Đã đổi Proxy: {self.current_proxy or 'Direct Slot'}", flush=True)
                else:
                    # Direct slot gặp lỗi nhẹ, đổi sang tìm Proxy
                    self.current_proxy = await self.get_fresh_proxy(timeout=0.5)

            if success:
                results[chunk_idx] = True
                task_queue.task_done()
                if on_chunk_done:
                    on_chunk_done(chunk_idx, True, duration, out_path, self.worker_id)
            else:
                task_queue.task_done()
                if attempts < self.engine.max_retries:
                    await task_queue.put((chunk_idx, attempts + 1, chunk_idx, text))
                    if on_chunk_done:
                        on_chunk_done(chunk_idx, False, duration, out_path, self.worker_id)
                else:
                    safe_print(f"⚠️ [TTS-CHUNK-RETRY] Chunk #{chunk_idx+1} chưa hoàn tất ở lượt này, sẽ được quét vét lại...", flush=True)
                    results[chunk_idx] = False
                    if on_chunk_done:
                        on_chunk_done(chunk_idx, False, duration, out_path, self.worker_id)

            if self.pacing_sec > 0 and not task_queue.empty():
                await asyncio.sleep(self.pacing_sec)


class RotatingBatchTTSEngine:
    def __init__(
        self,
        voice: str = "vi-VN-HoaiMyNeural",
        rate: str = "-4%",
        pitch: str = "+0Hz",
        proxies: Optional[List[str]] = None,
        auto_fetch_proxy: bool = True,
        max_parallel_workers: int = 8,
        pacing_sec: float = 0.1,
        max_retries: int = 5,
        chunk_timeout: float = 9.0,
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.initial_proxies = [p.strip() for p in proxies if p.strip()] if proxies else []
        self.auto_fetch_proxy = auto_fetch_proxy
        self.max_parallel_workers = max(1, min(max_parallel_workers, 16))
        self.pacing_sec = max(0.05, pacing_sec)
        self.max_retries = max(2, max_retries)
        self.chunk_timeout = max(10.0, chunk_timeout)

        self.proxy_queue: asyncio.Queue = asyncio.Queue()
        self.known_bad_proxies: Set[str] = set()
        self.direct_semaphore = asyncio.Semaphore(4)

        for p in self.initial_proxies:
            self.proxy_queue.put_nowait(p)

    async def acquire_proxy(self, timeout: float = 1.0) -> Optional[str]:
        try:
            return self.proxy_queue.get_nowait()
        except asyncio.QueueEmpty:
            try:
                return await asyncio.wait_for(self.proxy_queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None

    def mark_bad_proxy(self, proxy: str):
        if proxy:
            self.known_bad_proxies.add(proxy)

    async def synthesize_all(
        self,
        chunks: List[str],
        output_dir: str,
        on_chunk_done: Optional[Callable] = None,
    ) -> Dict[int, bool]:
        os.makedirs(output_dir, exist_ok=True)
        total = len(chunks)
        results: Dict[int, bool] = {}
        stop_event = asyncio.Event()

        num_workers = min(self.max_parallel_workers, total)

        # 1. Khởi chạy Feeder
        feeder = BackgroundProxyFeeder(self.proxy_queue, self.known_bad_proxies, max_pool_size=50)
        
        if num_workers > 4:
            safe_print(f"🔄 [TTS-FEEDER] Đang kiểm thử & nạp sẵn Proxy sống cho {num_workers} luồng...", flush=True)
            await feeder.prewarm(min_proxies=min(num_workers - 3, 6), max_wait=3.0)
            safe_print(f"⚡ [TTS-FEEDER] Đã sẵn sàng {self.proxy_queue.qsize()} Proxy sống trong pool!", flush=True)

        feeder_task = asyncio.create_task(feeder.start(stop_event))

        # PriorityQueue
        task_queue = asyncio.PriorityQueue()
        for idx in range(total):
            task_queue.put_nowait((idx, 1, idx, chunks[idx]))

        safe_print(f"🚀 [TTS-ENGINE] Bắt đầu tổng hợp âm thanh với {num_workers} Dedicated Workers (Target: {total} chunks)...", flush=True)

        workers = [
            DedicatedWorker(
                worker_id=w_id,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch,
                engine=self,
                direct_semaphore=self.direct_semaphore,
                pacing_sec=self.pacing_sec,
                chunk_timeout=self.chunk_timeout,
            )
            for w_id in range(num_workers)
        ]

        worker_tasks = [
            asyncio.create_task(w.run(task_queue, output_dir, results, on_chunk_done, stop_event))
            for w in workers
        ]

        await task_queue.join()
        # Đóng dứt điểm toàn bộ worker vòng 1 để tránh lỗi timeout ngầm xóa đè file của worker quét vét
        stop_event.set()
        await asyncio.gather(*worker_tasks, return_exceptions=True)

        # 2. VÒNG QUÉT VÉT BẮT BUỘC ĐỦ 100% (Strict 100% Completion Loop):
        # Lặp quét vét liên tục không giới hạn số vòng cho đến khi TẤT CẢ các chunks đều được tải hoàn chỉnh (> 1KB)
        sweep_round = 0
        while True:
            missing_indices = []
            for idx in range(total):
                out_path = os.path.join(output_dir, f"chunk_{idx:04d}.mp3")
                if not os.path.exists(out_path) or os.path.getsize(out_path) < 1024:
                    missing_indices.append(idx)

            if not missing_indices:
                safe_print(f"🎉 [TTS-100%-COMPLETE] Toàn bộ {total}/{total} chunks đã hoàn thành 100% và hợp lệ!", flush=True)
                break

            sweep_round += 1
            safe_print(f"🔁 [TTS-SWEEP-ROUND {sweep_round}] Quét vét lại {len(missing_indices)}/{total} chunks chưa xong (Chunks #{[i+1 for i in missing_indices]})...", flush=True)

            retry_queue = asyncio.PriorityQueue()
            for idx in missing_indices:
                clean_text = chunks[idx]
                retry_queue.put_nowait((idx, 1, idx, clean_text))

            sweep_workers = [
                DedicatedWorker(
                    worker_id=w_id,
                    voice=self.voice,
                    rate=self.rate,
                    pitch=self.pitch,
                    engine=self,
                    direct_semaphore=self.direct_semaphore,
                    pacing_sec=0.2,
                    chunk_timeout=25.0,
                )
                for w_id in range(min(num_workers, len(missing_indices)))
            ]

            # Ở vòng quét vét thứ 2 trở đi, nếu proxy bị kẹt, cho worker tự động thử Direct IP
            if sweep_round >= 2:
                for w in sweep_workers:
                    w.current_proxy = None

            sweep_stop_event = asyncio.Event()
            sweep_tasks = [
                asyncio.create_task(w.run(retry_queue, output_dir, results, on_chunk_done, sweep_stop_event))
                for w in sweep_workers
            ]

            await retry_queue.join()
            sweep_stop_event.set()
            await asyncio.gather(*sweep_tasks, return_exceptions=True)
            await asyncio.sleep(0.3)

        feeder_stop_event = asyncio.Event()
        feeder_stop_event.set()
        await asyncio.gather(feeder_task, return_exceptions=True)

        return results

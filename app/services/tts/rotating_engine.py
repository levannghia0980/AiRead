"""
Rotating Batch TTS Engine - Unified High-Throughput Multi-Worker Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kiến trúc Unified (thống nhất, tối ưu):

  Workers: Proxy Pool (ưu tiên) → Xẻng kim cương Direct IP (phương án cuối)

Xẻng kim cương (Direct IP) - Gate-Lock pattern:
  - Hỏng → nghỉ 180s (cooldown). Tất cả workers BỎ QUA, đi lấy proxy.
  - Cooldown hết → CHỈ 1 worker vào kiểm tra qua _gate_lock:
      ✔ Dùng được → mark_success → _verified_ok=True → bọn sau tự đến lấy
      ✘ Hỏng → gia hạn thêm 180s + báo bọn kia KHÔNG cần check
  - Trong cooldown: workers tự động đi lấy proxy, KHÔNG chờ, KHÔNG check

Workers - Nguyên tắc "không nghỉ":
  ① Giữ proxy cũ → dùng luôn
  ② Queue có proxy → get_nowait()
  ③ Queue trống → kích feeder khẩn + chờ tối đa 5s
  ④ Vẫn không có → thử xẻng kim cương (gate-lock)
  ⑤ Không có gì → trả task lại, ngủ 0.2s, lặp lại
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
import time
import re
import random
import json
import httpx
import edge_tts
from typing import Optional, List, Callable, Dict, Set, Any
from app.services.tts.tts_exporter import cues_to_segments_and_words


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
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
]


def _calc_timeout(text: str) -> float:
    """
    Adaptive timeout [15s, 90s]:
    - Tối thiểu 15s: đảm bảo đủ thời gian bắt tay TLS/WebSocket.
    - An toàn theo độ dài: ~10 chars/s + 15s buffer.
    - Với chunk 650 chars: 650 / 10 + 15 = 80s timeout, đủ thời gian cho câu có ngắt nghỉ sâu.
    """
    return min(max(len(text) / 10.0 + 15.0, 15.0), 90.0)


# ─────────────────────────────────────────────────────────────────────────────
# BackgroundProxyFeeder
# ─────────────────────────────────────────────────────────────────────────────

class BackgroundProxyFeeder:
    """
    Quét, kiểm thử song song và nạp Proxy sống vào hàng đợi liên tục.
    - trigger_urgent(): Workers gọi khi pool cạn → Feeder refill ngay.
    - urgent_threshold: Ngưỡng tối thiểu để tự động kích hoạt refill.
    """

    def __init__(self, proxy_queue: asyncio.Queue, bad_proxies: Set[str], max_pool_size: int = 80):
        self.proxy_queue = proxy_queue
        self.bad_proxies = bad_proxies
        self.max_pool_size = max(80, max_pool_size)
        self.candidates: List[str] = []
        self.testing_sem = asyncio.Semaphore(250)
        self._urgent_event = asyncio.Event()

    async def _fetch_candidates_async(self) -> List[str]:
        raw = []
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
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
            import tempfile, uuid
            tmp = os.path.join(tempfile.gettempdir(), f"_pftest_{uuid.uuid4().hex[:8]}.mp3")
            try:
                comm = edge_tts.Communicate("OK", "vi-VN-HoaiMyNeural", proxy=p)
                await asyncio.wait_for(comm.save(tmp), timeout=4.0)
                if os.path.exists(tmp) and os.path.getsize(tmp) > 300:
                    if p not in self.bad_proxies:
                        self.proxy_queue.put_nowait(p)
                        return True
            except Exception:
                pass
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
        return False

    def trigger_urgent(self):
        """Kích hoạt refill khẩn cấp ngay lập tức."""
        self._urgent_event.set()

    async def prewarm(self, min_proxies: int = 12, max_wait: float = 10.0):
        """Khởi động nhanh: quét song song 1000 candidates để lọc proxy sống."""
        if self.proxy_queue.qsize() >= min_proxies:
            return
        if not self.candidates:
            self.candidates = await self._fetch_candidates_async()

        batch_size = min(1000, len(self.candidates))
        if batch_size == 0:
            return
        batch = [self.candidates.pop() for _ in range(batch_size)]
        for p in batch:
            asyncio.create_task(self._test_one_proxy(p))
        t0 = time.time()
        while self.proxy_queue.qsize() < min_proxies and (time.time() - t0) < max_wait:
            await asyncio.sleep(0.2)

    async def start(self, stop_event: asyncio.Event, urgent_threshold: int = 12):
        """
        Vòng lặp nền duy trì pool proxy sống liên tục.
        urgent_threshold = num_workers: luôn cố duy trì đủ proxy cho mọi worker.
        Workers giữ proxy mãi (không trả lại queue) → feeder phải liên tục bù vào.
        """
        while not stop_event.is_set():
            try:
                # Chờ urgent signal hoặc timeout 0.5s rồi tự check
                try:
                    await asyncio.wait_for(self._urgent_event.wait(), timeout=0.5)
                    self._urgent_event.clear()
                except asyncio.TimeoutError:
                    pass

                # Refill khi queue < urgent_threshold (= num_workers)
                # Vì workers giữ proxy mãi, queue cạn rất nhanh → phải refill liên tục
                if self.proxy_queue.qsize() < urgent_threshold:
                    if not self.candidates or len(self.candidates) < 200:
                        more_cands = await self._fetch_candidates_async()
                        self.candidates.extend(more_cands)

                    # Test nhiều candidates hơn để bù tỉ lệ proxy chết cao
                    batch_size = min(500, len(self.candidates))
                    batch = [self.candidates.pop() for _ in range(batch_size)] if self.candidates else []
                    if batch:
                        for p in batch:
                            asyncio.create_task(self._test_one_proxy(p))
            except Exception:
                await asyncio.sleep(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# DirectIPManager  — Xẻng kim cương
# ─────────────────────────────────────────────────────────────────────────────

class DirectIPManager:
    """
    Xẻng kim cương (Direct IP) - Gate-Lock pattern:

    • Khi hỏng (Timeout/TypeError): đánh dấu nghỉ 180s bảo vệ IP.
    • Trong cooldown: can_use_direct()=False → workers BỎ QUA ngay, đi lấy proxy.
    • Cooldown hết → CHỈ 1 worker vào kiểm tra qua _gate_lock:
        ✔ Dùng được → mark_success() → _verified_ok=True → bọn sau tự đến lấy slot bình thường.
        ✘ Hỏng     → mark_failed() → gia hạn +180s → bọn kia KHÔNG cần check thêm.
    • _verified_ok=True: xẻng đang tốt, workers lấy slot semaphore tự do.
    """

    def __init__(self, max_concurrent: int = 4, cooldown_seconds: float = 180.0):
        self.cooldown_seconds = cooldown_seconds
        self.cooldown_until: float = 0.0
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._gate_lock = asyncio.Lock()   # chỉ 1 worker đi kiểm tra sau cooldown
        self._verified_ok: bool = False    # True khi đã verify hoạt động

    def is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def mark_failed(self, reason: str = "timeout"):
        """Xẻng hỏng: gia hạn cooldown, reset verified → lần sau chỉ 1 worker check."""
        self.cooldown_until = time.time() + self.cooldown_seconds
        self._verified_ok = False
        safe_print(f"⚡ [DIRECT-IP] Xẻng bị {reason} → Nghỉ {int(self.cooldown_seconds)}s bảo vệ IP máy.", flush=True)

    def mark_success(self):
        """Xẻng hoạt động tốt: reset cooldown, báo bọn sau có thể vào dùng."""
        self.cooldown_until = 0.0
        self._verified_ok = True

    async def try_acquire(self) -> bool:
        """
        Thử lấy 1 slot Direct IP.
        - Đang cooldown        → False ngay (không chờ).
        - _verified_ok=True    → lấy thẳng semaphore slot.
        - Chưa verified        → chỉ 1 worker qua _gate_lock kiểm tra;
                                  worker khác thấy gate đóng → bỏ qua, đi lấy proxy.
        Caller phải gọi release() sau khi dùng xong.
        """
        if self.is_in_cooldown():
            return False

        if self._verified_ok:
            # Xẻng đã được xác nhận → lấy slot bình thường
            try:
                await asyncio.wait_for(self.semaphore.acquire(), timeout=0.05)
                return True
            except (asyncio.TimeoutError, Exception):
                return False

        # Chưa verified (vừa ra khỏi cooldown)
        if self._gate_lock.locked():
            return False  # Worker khác đang kiểm tra → bỏ qua, đi lấy proxy

        try:
            async with self._gate_lock:
                # Double-check sau khi vào gate
                if self.is_in_cooldown():
                    return False
                if self._verified_ok:
                    # Worker trước đã verify thành công trong lúc chờ lock
                    try:
                        await asyncio.wait_for(self.semaphore.acquire(), timeout=0.05)
                        return True
                    except Exception:
                        return False
                # Mình là worker đầu tiên kiểm tra sau cooldown
                try:
                    await asyncio.wait_for(self.semaphore.acquire(), timeout=0.1)
                    # Đặt verified_ok=True NGAY LẬP TỨC (optimistic) để các worker
                    # tiếp theo vào gate thấy True → đi thẳng vào fast path, không in
                    # "sẵn sàng" nhiều lần. Nếu TTS thực sự fail → mark_failed() reset lại.
                    self._verified_ok = True
                    safe_print("✨ [DIRECT-IP] Xẻng kim cương sẵn sàng → 1 worker đến kiểm tra!", flush=True)
                    return True
                except (asyncio.TimeoutError, Exception):
                    return False
        except Exception:
            return False

    def release(self):
        """Trả lại slot semaphore sau khi dùng xong."""
        try:
            self.semaphore.release()
        except Exception:
            pass


GLOBAL_DIRECT_IP_MANAGER = DirectIPManager(max_concurrent=4, cooldown_seconds=180.0)


# ─────────────────────────────────────────────────────────────────────────────
# DedicatedWorker
# ─────────────────────────────────────────────────────────────────────────────

class DedicatedWorker:
    """
    Worker bất tử: KHÔNG bao giờ bị tắt/tái tạo giữa chừng.
    Nguyên tắc "không nghỉ":
      ① Giữ proxy cũ → dùng luôn
      ② Queue có proxy → get_nowait()
      ③ Queue trống → kích feeder khẩn + chờ tối đa 5s
      ④ Vẫn không có → thử xẻng kim cương (gate-lock, chỉ 1 worker check)
      ⑤ Không có gì → trả task lại queue, ngủ 0.2s, lặp lại
    """

    def __init__(
        self,
        worker_id: int,
        voice: str,
        rate: str,
        pitch: str,
        engine: "RotatingBatchTTSEngine",
        direct_semaphore: asyncio.Semaphore,
        pacing_sec: float = 0.2,
    ):
        self.worker_id = worker_id
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.engine = engine
        self.direct_semaphore = direct_semaphore
        self.pacing_sec = pacing_sec
        self.current_proxy: Optional[str] = None

    async def _wait_for_proxy(self, timeout: float = 5.0) -> Optional[str]:
        """Chờ proxy từ queue, đồng thời kích hoạt feeder khẩn cấp."""
        if self.engine.feeder:
            self.engine.feeder.trigger_urgent()
        return await self.engine.acquire_proxy(timeout=timeout)

    async def run(
        self,
        task_queue: asyncio.PriorityQueue,
        output_dir: str,
        results: Dict[Any, bool],
        on_chunk_done: Optional[Callable],
        stop_event: asyncio.Event,
    ):
        while not stop_event.is_set():
            try:
                item = await asyncio.wait_for(task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            priority, attempts, task_id, task_data = item

            # Hỗ trợ cả dict task (multi-chapter) và raw text (legacy)
            if isinstance(task_data, dict):
                cur_output_dir = task_data.get("output_dir", output_dir)
                chunk_idx = task_data.get("chunk_idx", 0)
                text = task_data.get("text", "")
                task_ref = task_data
            else:
                cur_output_dir = output_dir
                chunk_idx = task_id if isinstance(task_id, int) else 0
                text = task_data
                task_ref = chunk_idx

            os.makedirs(cur_output_dir, exist_ok=True)
            out_path = os.path.join(cur_output_dir, f"chunk_{chunk_idx:04d}.mp3")
            tmp_path = os.path.join(cur_output_dir, f"chunk_{chunk_idx:04d}.tmp_{self.worker_id}.mp3")

            # Nếu chương đã hoàn tất (file MP3 cả chương > 10KB), bỏ qua
            ch_mp3 = task_data.get("chapter_mp3", "") if isinstance(task_data, dict) else ""
            if ch_mp3 and os.path.exists(ch_mp3) and os.path.getsize(ch_mp3) > 10240:
                results[task_id] = True
                task_queue.task_done()
                continue

            # Nếu chunk MP3 đã tồn tại và hợp lệ (> 1KB), kiểm tra cả tính toàn vẹn từ vựng nếu có json
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                json_path_check = os.path.join(cur_output_dir, f"chunk_{chunk_idx:04d}.json")
                chunk_valid = True
                if os.path.exists(json_path_check):
                    try:
                        with open(json_path_check, "r", encoding="utf-8") as _f_cj:
                            _chk_data = json.load(_f_cj)
                        _chk_exp = len(re.findall(r'[\wÀ-ỹ]+', text))
                        _chk_words = [w["word"] for w in _chk_data.get("words", []) if isinstance(w, dict) and "word" in w]
                        _chk_act = len(re.findall(r'[\wÀ-ỹ]+', " ".join(_chk_words))) if _chk_words else len(_chk_data.get("words", []))
                        if _chk_exp >= 10 and _chk_act < _chk_exp * 0.88:
                            chunk_valid = False
                    except Exception:
                        pass
                if chunk_valid:
                    results[task_id] = True
                    task_queue.task_done()
                    if on_chunk_done:
                        try:
                            on_chunk_done(task_ref, True, 0.01, out_path, self.worker_id)
                        except Exception:
                            pass
                    continue
                else:
                    try:
                        os.remove(out_path)
                        if os.path.exists(json_path_check):
                            os.remove(json_path_check)
                    except Exception:
                        pass

            # Nếu chunk rỗng hoàn toàn → tạo silence
            if not text or not text.strip() or not re.search(r'[\wÀ-ỹ]', text):
                results[task_id] = True
                task_queue.task_done()
                try:
                    import subprocess as _sp
                    try:
                        import imageio_ffmpeg as _iff
                        _ffmpeg = _iff.get_ffmpeg_exe()
                    except Exception:
                        _ffmpeg = "ffmpeg"
                    _r = _sp.run(
                        [_ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                         "-t", "0.1", "-ar", "24000", "-ac", "1",
                         "-c:a", "libmp3lame", "-b:a", "48k",
                         "-id3v2_version", "3", "-write_xing", "1",
                         out_path],
                        stdout=_sp.PIPE, stderr=_sp.PIPE
                    )
                    if _r.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) < 100:
                        with open(out_path, "wb") as f_dummy:
                            f_dummy.write(b'\xff\xfb\x90\x64' + b'\x00' * 1024)
                except Exception:
                    try:
                        with open(out_path, "wb") as f_dummy:
                            f_dummy.write(b'\xff\xfb\x90\x64' + b'\x00' * 1024)
                    except Exception:
                        pass
                if on_chunk_done:
                    try:
                        on_chunk_done(task_ref, True, 0.01, out_path, self.worker_id)
                    except Exception:
                        pass
                continue

            # ── Chọn kênh kết nối ─────────────────────────────────────────
            # Proxy ưu tiên → Xẻng kim cương chỉ là phương án cuối cùng
            used_direct = False
            direct_acquired = False

            # Bước 1: Dùng proxy hiện tại đang giữ (nếu có)
            if self.current_proxy is not None:
                pass  # giữ nguyên proxy cũ

            # Bước 2: Lấy proxy mới từ queue không chặn
            elif not self.engine.proxy_queue.empty():
                try:
                    self.current_proxy = self.engine.proxy_queue.get_nowait()
                except asyncio.QueueEmpty:
                    self.current_proxy = None

            # Bước 3: Queue trống → kích feeder khẩn cấp + chờ tối đa 5s
            if self.current_proxy is None:
                self.current_proxy = await self._wait_for_proxy(timeout=5.0)

            # Bước 4: Vẫn không có proxy → thử xẻng kim cương
            # (gate-lock: chỉ 1 worker kiểm tra sau cooldown, bọn khác bỏ qua đi lấy proxy)
            if self.current_proxy is None:
                direct_acquired = await GLOBAL_DIRECT_IP_MANAGER.try_acquire()
                used_direct = direct_acquired

            # Bước 5: Hoàn toàn không có kênh → trả task lại queue, chờ ngắn
            if not used_direct and self.current_proxy is None:
                task_queue.put_nowait((priority, attempts, task_id, task_data))
                task_queue.task_done()
                await asyncio.sleep(0.2)
                continue
            # ──────────────────────────────────────────────────────────────

            success = False
            duration = 0.0
            t0 = time.time()

            # Chuẩn bị văn bản cho TTS (Edge-TTS tự ngắt nghỉ tự nhiên theo đúng dấu câu chuẩn)
            tts_text = text.strip()
            if tts_text and tts_text[-1] not in '.!?…"':
                tts_text += '.'
            # Thêm khoảng đệm cuối chunk để Edge-TTS giải phóng 100% âm tiết cuối
            tts_text += ' '

            cur_timeout = _calc_timeout(tts_text)
            if self.engine and hasattr(self.engine, "chunk_timeout") and self.engine.chunk_timeout:
                cur_timeout = max(cur_timeout, float(self.engine.chunk_timeout))

            try:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                json_path = os.path.join(cur_output_dir, f"chunk_{chunk_idx:04d}.json")
                submaker = edge_tts.SubMaker()

                async def _download_stream(c_instance):
                    _sub_fallback = None
                    with open(tmp_path, "wb") as f_mp3:
                        async for chunk in c_instance.stream():
                            if chunk["type"] == "audio":
                                f_mp3.write(chunk["data"])
                            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                                try:
                                    submaker.feed(chunk)
                                except ValueError:
                                    # SubMaker rejects mixed types - use fallback
                                    if _sub_fallback is None:
                                        _sub_fallback = edge_tts.SubMaker()
                                    try:
                                        _sub_fallback.feed(chunk)
                                    except Exception:
                                        pass
                    # If primary submaker got nothing but fallback did, swap
                    if not submaker.cues and _sub_fallback and _sub_fallback.cues:
                        submaker.cues = _sub_fallback.cues
                        submaker.type = _sub_fallback.type

                if used_direct:
                    comm = edge_tts.Communicate(text=tts_text, voice=self.voice, rate=self.rate, pitch=self.pitch, proxy=None)
                else:
                    comm = edge_tts.Communicate(text=tts_text, voice=self.voice, rate=self.rate, pitch=self.pitch, proxy=self.current_proxy)

                await asyncio.wait_for(_download_stream(comm), timeout=cur_timeout)

                duration = time.time() - t0

                # ── KIỂM TRA ĐỘ TOÀN VẸN 100% CỦA ÂM THANH & TỪ VỰNG ──
                text_len = len(tts_text.strip())
                min_expected_bytes = max(1500, int(text_len * 130))
                actual_bytes = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0

                if actual_bytes < min_expected_bytes:
                    raise RuntimeError(
                        f"Âm thanh bị cụt/thiếu ({actual_bytes} bytes < tối thiểu {min_expected_bytes} bytes cho {text_len} ký tự). Cần thử lại!"
                    )

                # Chuyển đổi cues sang segments & words để kiểm tra nội dung
                c_segs, c_words = cues_to_segments_and_words(submaker.cues, tts_text)

                # Kiểm tra độ bao phủ thời gian của cues (tối thiểu 0.04s / ký tự cho tiếng Việt)
                if submaker.cues and text_len > 100:
                    total_cue_sec = (submaker.cues[-1].end.total_seconds() - submaker.cues[0].start.total_seconds())
                    min_expected_sec = text_len * 0.04
                    if total_cue_sec < min_expected_sec:
                        raise RuntimeError(
                            f"Subtitle cues bị cụt ({total_cue_sec:.1f}s < tối thiểu {min_expected_sec:.1f}s cho {text_len} ký tự). Cần thử lại!"
                        )

                # KIỂM TRA TỪ VỰNG CHÍNH XÁC (Chống rớt từ, nuốt câu, ngắt stream sớm)
                input_words = re.findall(r'[\wÀ-ỹ]+', tts_text)
                actual_words = [w["word"] for w in c_words] if c_words else []
                act_words_normalized = re.findall(r'[\wÀ-ỹ]+', " ".join(actual_words)) if actual_words else []
                actual_count = len(act_words_normalized) if act_words_normalized else len(actual_words)

                if len(input_words) >= 10:
                    if not actual_words:
                        raise RuntimeError(
                            f"Subchunk {chunk_idx} không thu được từ vựng nào từ subtitle cues! Cần thử lại!"
                        )
                    word_ratio = actual_count / len(input_words)
                    if word_ratio < 0.88:
                        raise RuntimeError(
                            f"Subchunk {chunk_idx} bị thiếu từ nghiêm trọng! "
                            f"Chỉ nhận {actual_count}/{len(input_words)} từ ({word_ratio:.1%}). Cần thử lại!"
                        )

                    # KIỂM TRA ĐUÔI CÂU CUỐI (Tail Verification - Đảm bảo phát âm trọn vẹn đến câu cuối cùng)
                    if len(input_words) >= 5:
                        tail_candidates = [w.lower() for w in input_words[-4:]]
                        recent_tokens = act_words_normalized[-12:] if act_words_normalized else actual_words[-12:]
                        recent_actual = " ".join([w.lower() for w in recent_tokens])
                        if not any(tw in recent_actual for tw in tail_candidates):
                            raise RuntimeError(
                                f"Subchunk {chunk_idx} bị cắt đuôi! "
                                f"Đuôi kỳ vọng: '{' '.join(tail_candidates)}' nhưng audio dừng tại: '{recent_actual[-30:]}'. Cần thử lại!"
                            )

                if os.path.exists(tmp_path) and actual_bytes >= min_expected_bytes:
                    os.replace(tmp_path, out_path)
                    try:
                        with open(json_path, "w", encoding="utf-8") as f_cj:
                            json.dump({"segments": c_segs, "words": c_words, "duration": duration}, f_cj, ensure_ascii=False)
                    except Exception:
                        pass
                    success = True
                else:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass

            except Exception as e_chunk:
                duration = time.time() - t0
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                err_name = type(e_chunk).__name__
                ch_num = task_data.get("chapter_no") if isinstance(task_data, dict) else None
                ch_pfx = f"Ch{ch_num} " if ch_num is not None else ""
                safe_print(
                    f"⚠️ [W#{self.worker_id:02d}] {ch_pfx}đoạn {chunk_idx+1:02d} gặp lỗi ({err_name}): {e_chunk} (Lần thử {attempts}/{self.engine.max_retries})",
                    flush=True
                )
                if attempts < self.engine.max_retries:
                    high_prio = priority - 100_000_000
                    task_queue.put_nowait((high_prio, attempts + 1, task_id, task_data))
                    task_queue.task_done()
                    if on_chunk_done:
                        try:
                            on_chunk_done(task_ref, False, duration, out_path, self.worker_id)
                        except Exception:
                            pass
                else:
                    results[task_id] = False
                    task_queue.task_done()
                    if on_chunk_done:
                        try:
                            on_chunk_done(task_ref, False, duration, out_path, self.worker_id)
                        except Exception:
                            pass

                if used_direct:
                    GLOBAL_DIRECT_IP_MANAGER.mark_failed(reason=err_name)
                else:
                    if self.current_proxy:
                        self.engine.mark_bad_proxy(self.current_proxy)
                        self.current_proxy = None
                continue
            finally:
                if direct_acquired:
                    GLOBAL_DIRECT_IP_MANAGER.release()

            if success:
                if used_direct:
                    GLOBAL_DIRECT_IP_MANAGER.mark_success()
                results[task_id] = True
                task_queue.task_done()
                if on_chunk_done:
                    channel_label = "DIRECT" if used_direct else (
                        f"Proxy..{self.current_proxy[-8:]}" if self.current_proxy else "Proxy"
                    )
                    try:
                        on_chunk_done(task_ref, True, duration, out_path, self.worker_id, channel_label)
                    except Exception:
                        pass

            if used_direct and not task_queue.empty():
                await asyncio.sleep(self.pacing_sec)


# ─────────────────────────────────────────────────────────────────────────────
# RotatingBatchTTSEngine
# ─────────────────────────────────────────────────────────────────────────────

class RotatingBatchTTSEngine:
    def __init__(
        self,
        voice: str = "vi-VN-HoaiMyNeural",
        rate: str = "-4%",
        pitch: str = "+0Hz",
        proxies: Optional[List[str]] = None,
        auto_fetch_proxy: bool = True,
        max_parallel_workers: int = 8,
        pacing_sec: float = 0.5,
        max_retries: int = 5,
        chunk_timeout: float = 45.0,
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.initial_proxies = [p.strip() for p in proxies if p.strip()] if proxies else []
        self.auto_fetch_proxy = auto_fetch_proxy
        self.max_parallel_workers = max(1, min(max_parallel_workers, 128))
        self.pacing_sec = max(0.1, pacing_sec)
        self.max_retries = max(2, max_retries)
        self.chunk_timeout = chunk_timeout

        self.proxy_queue: asyncio.Queue = asyncio.Queue()
        self.known_bad_proxies: Set[str] = set()
        self.direct_semaphore = asyncio.Semaphore(1)
        self.feeder: Optional[BackgroundProxyFeeder] = None

        for p in self.initial_proxies:
            self.proxy_queue.put_nowait(p)

    async def acquire_proxy(self, timeout: float = 5.0) -> Optional[str]:
        """Lấy proxy từ queue. timeout<=0 → không chặn."""
        try:
            return self.proxy_queue.get_nowait()
        except asyncio.QueueEmpty:
            if timeout <= 0:
                return None
            try:
                return await asyncio.wait_for(self.proxy_queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None

    def mark_bad_proxy(self, proxy: str):
        if proxy:
            self.known_bad_proxies.add(proxy)

    async def synthesize_tasks(
        self,
        tasks: List[dict],
        on_chunk_done: Optional[Callable] = None,
    ) -> Dict[Any, bool]:
        """
        Xử lý đồng thời danh sách chunk tasks (hỗ trợ nhiều chương).
        Workers + Feeder khởi chạy SONG SONG — không worker nào bị nghỉ.
        """
        total = len(tasks)
        if total == 0:
            return {}

        results: Dict[Any, bool] = {}
        stop_event = asyncio.Event()
        num_workers = min(self.max_parallel_workers, total)

        feeder = BackgroundProxyFeeder(
            self.proxy_queue,
            self.known_bad_proxies,
            max_pool_size=max(80, num_workers * 2)
        )
        self.feeder = feeder

        if num_workers > 1:
            safe_print(f"🔄 [TTS-FEEDER] Khởi động Proxy Feeder ({num_workers} workers) song song với workers...", flush=True)

        # Feeder chạy ngay lập tức để cấp proxy liên tục
        # urgent_threshold = num_workers: luôn duy trì đủ proxy cho mọi worker
        feeder_task = asyncio.create_task(feeder.start(stop_event, urgent_threshold=num_workers))

        # Prewarm chạy SONG SONG với workers (không chặn)
        # Mục tiêu: tìm đủ proxy cho càng nhiều worker càng tốt trong 3s đầu
        prewarm_task = asyncio.create_task(
            feeder.prewarm(min_proxies=num_workers, max_wait=3.0)
        )

        task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        for t in tasks:
            prio = t.get("priority", 0)
            t_id = t.get("id", f"{t.get('chapter_no', 0)}_{t.get('chunk_idx', 0)}")
            task_queue.put_nowait((prio, 1, t_id, t))

        safe_print(f"🚀 [TTS-ENGINE] Khởi chạy song song {num_workers} workers cho {total} phân đoạn...", flush=True)

        workers = [
            DedicatedWorker(
                worker_id=w_id,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch,
                engine=self,
                direct_semaphore=self.direct_semaphore,
                pacing_sec=self.pacing_sec,
            )
            for w_id in range(num_workers)
        ]

        worker_tasks = [
            asyncio.create_task(w.run(task_queue, "", results, on_chunk_done, stop_event))
            for w in workers
        ]

        try:
            sweep_round = 0
            while True:
                await task_queue.join()

                missing_tasks = []
                for t in tasks:
                    t_id = t.get("id", f"{t.get('chapter_no', 0)}_{t.get('chunk_idx', 0)}")

                    ch_mp3 = t.get("chapter_mp3", "")
                    if ch_mp3 and os.path.exists(ch_mp3) and os.path.getsize(ch_mp3) > 10240:
                        results[t_id] = True
                        continue

                    t_out_dir = t.get("output_dir", "")
                    t_idx = t.get("chunk_idx", 0)
                    p = os.path.join(t_out_dir, f"chunk_{t_idx:04d}.mp3")
                    if os.path.exists(p) and os.path.getsize(p) > 1024:
                        results[t_id] = True
                        continue

                    missing_tasks.append(t)

                if not missing_tasks:
                    safe_print(f"🎉 [TTS-100%-COMPLETE] Toàn bộ {total} phân đoạn đã hoàn thành!", flush=True)
                    break

                if sweep_round >= 10:
                    safe_print(f"⚠️ [TTS-SWEEP-MAX] Đã quét tối đa 10 vòng, còn {len(missing_tasks)} chunks chưa xong.", flush=True)
                    break

                sweep_round += 1
                safe_print(
                    f"🔁 [TTS-SWEEP-{sweep_round}] Còn {len(missing_tasks)}/{total} phân đoạn chưa xong → Nạp lại vào queue...",
                    flush=True
                )

                for t in missing_tasks:
                    prio = t.get("priority", 0)
                    high_prio = prio - 100_000_000
                    t_id = t.get("id", f"{t.get('chapter_no', 0)}_{t.get('chunk_idx', 0)}")
                    results[t_id] = None
                    task_queue.put_nowait((high_prio, 1, t_id, t))

                if self.proxy_queue.qsize() < num_workers:
                    feeder.trigger_urgent()
                    await asyncio.sleep(1.5)
        finally:
            stop_event.set()
            for wt in worker_tasks:
                if not wt.done():
                    wt.cancel()
            if feeder_task and not feeder_task.done():
                feeder_task.cancel()
            if prewarm_task and not prewarm_task.done():
                prewarm_task.cancel()
            await asyncio.gather(*worker_tasks, feeder_task, prewarm_task, return_exceptions=True)
            self.feeder = None

        return results

    async def synthesize_all(
        self,
        chunks: List[str],
        output_dir: str,
        on_chunk_done: Optional[Callable] = None,
    ) -> Dict[int, bool]:
        tasks = [
            {
                "id": idx,
                "chunk_idx": idx,
                "text": chunks[idx],
                "output_dir": output_dir,
                "priority": idx
            }
            for idx in range(len(chunks))
        ]
        res = await self.synthesize_tasks(tasks, on_chunk_done=on_chunk_done)
        return {idx: res.get(idx, True) for idx in range(len(chunks))}

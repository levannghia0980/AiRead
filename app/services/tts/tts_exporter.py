# -*- coding: utf-8 -*-
"""
TTS_EXPORTER.PY - Bóc tách JSON Subtitle chuẩn mili-giây từ Edge-TTS & Hỗ trợ xuất Timeline Karaoke
"""
import os
import re
import json
import math
import asyncio
from typing import List, Dict, Any, Optional
import edge_tts


def calculate_word_timings(segment_text: str, start_sec: float, end_sec: float) -> List[Dict[str, Any]]:
    """Tính mốc thời gian từng từ chuẩn âm vị học tiếng Việt trong câu."""
    words = segment_text.strip().split()
    if not words:
        return []

    total_dur = max(0.05, end_sec - start_sec)
    # Tính trọng số âm vị: phụ thuộc vào độ dài ký tự và độ phức tạp âm tiết
    weights = [max(1.0, math.sqrt(len(re.sub(r'[^\w\s]', '', w)) or 1) * 1.5) for w in words]
    total_weight = sum(weights) or 1.0

    word_timings = []
    curr = start_sec
    for i, w in enumerate(words):
        dur = max(0.06, total_dur * (weights[i] / total_weight))
        w_start = round(curr, 3)
        w_end = round(end_sec if i == len(words) - 1 else min(end_sec, curr + dur), 3)
        word_timings.append({
            "word": w,
            "start": w_start,
            "end": w_end
        })
        curr = w_end
    return word_timings


def cues_to_segments_and_words(cues: list, chunk_text: str = "") -> tuple:
    """Chuyển đổi danh sách cues từ edge_tts.SubMaker thành segments và words."""
    segments = []
    all_words = []

    if not cues:
        return segments, all_words

    for cue in cues:
        s_sec = cue.start.total_seconds()
        e_sec = cue.end.total_seconds()
        cue_text = cue.content.strip()
        # Loại bỏ các thẻ SSML break khỏi hiển thị subtitle
        cue_text = re.sub(r'<break[^>]*/>', '', cue_text).strip()
        cue_text = re.sub(r'\s+', ' ', cue_text)

        if e_sec <= s_sec or not cue_text:
            continue

        words = calculate_word_timings(cue_text, s_sec, e_sec)
        seg_obj = {
            "start": round(s_sec, 3),
            "end": round(e_sec, 3),
            "text": cue_text,
            "words": words
        }
        segments.append(seg_obj)
        all_words.extend(words)

    return segments, all_words


def merge_subchunks_json_to_chapter(
    subchunk_data_list: List[Dict[str, Any]],
    chapter_no: int,
    chapter_title: str,
    output_json_path: str,
    voice: str = "vi-VN-HoaiMyNeural",
    chunk_durations: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Gộp dữ liệu segments của các sub-chunks (trong cùng 1 chương) thành file JSON chương hoàn chỉnh.
    Cộng dồn offset thời gian theo độ dài thực tế của từng sub-chunk audio.
    """
    current_offset = 0.0
    merged_segments = []
    merged_words = []

    for i, chunk_info in enumerate(subchunk_data_list):
        chunk_segs = chunk_info.get("segments", [])
        
        # Xác định độ dài của subchunk này
        if chunk_durations and i < len(chunk_durations):
            c_dur = chunk_durations[i]
        elif chunk_segs:
            c_dur = chunk_segs[-1]["end"]
        else:
            c_dur = chunk_info.get("duration", 0.0)

        for seg in chunk_segs:
            s_val = round(seg["start"] + current_offset, 3)
            e_val = round(seg["end"] + current_offset, 3)
            w_list = []
            for w in seg.get("words", []):
                w_obj = {
                    "word": w["word"],
                    "start": round(w["start"] + current_offset, 3),
                    "end": round(w["end"] + current_offset, 3)
                }
                w_list.append(w_obj)
                merged_words.append(w_obj)

            merged_segments.append({
                "start": s_val,
                "end": e_val,
                "text": seg["text"],
                "words": w_list
            })

        current_offset = round(current_offset + c_dur, 3)

    total_dur = merged_segments[-1]["end"] if merged_segments else current_offset

    chapter_data = {
        "chapter_id": chapter_no,
        "chapter_no": chapter_no,
        "title": chapter_title,
        "duration": round(total_dur, 3),
        "voice": voice,
        "total_sentences": len(merged_segments),
        "total_words": len(merged_words),
        "segments": merged_segments,
        "words": merged_words
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(chapter_data, f, ensure_ascii=False, indent=2)

    return chapter_data


def estimate_chapter_json_from_text(
    text: str,
    total_duration_sec: float,
    chapter_no: int,
    chapter_title: str,
    output_json_path: str,
    voice: str = "vi-VN-HoaiMyNeural"
) -> Dict[str, Any]:
    """
    Fallback ước tính mốc thời gian nếu chương đã có MP3 nhưng chưa có file JSON từ trước.
    Chia câu theo dấu câu và phân bổ thời gian tỷ lệ thuận theo độ dài câu và từ ngữ.
    """
    sentences = [s.strip() for s in re.split(r'(?<=[.!?…\n])\s+', text) if s.strip()]
    if not sentences:
        sentences = [text.strip()] if text.strip() else ["..."]

    # Tính trọng số độ dài từng câu
    sent_weights = [max(1, len(s)) for s in sentences]
    tot_weight = sum(sent_weights) or 1.0

    segments = []
    all_words = []
    curr = 0.0

    for i, s_text in enumerate(sentences):
        s_text = re.sub(r'\s+', ' ', s_text).strip()
        if not s_text:
            continue
        dur = total_duration_sec * (sent_weights[i] / tot_weight)
        s_start = round(curr, 3)
        s_end = round(total_duration_sec if i == len(sentences) - 1 else curr + dur, 3)
        words = calculate_word_timings(s_text, s_start, s_end)

        segments.append({
            "start": s_start,
            "end": s_end,
            "text": s_text,
            "words": words
        })
        all_words.extend(words)
        curr = s_end

    chapter_data = {
        "chapter_id": chapter_no,
        "chapter_no": chapter_no,
        "title": chapter_title,
        "duration": round(total_duration_sec, 3),
        "voice": voice,
        "total_sentences": len(segments),
        "total_words": len(all_words),
        "segments": segments,
        "words": all_words
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(chapter_data, f, ensure_ascii=False, indent=2)

    return chapter_data


def merge_chapters_timeline(
    chapters_data_list: List[Dict[str, Any]],
    output_json_path: Optional[str] = None,
    novel_title: str = "Toàn Bộ Chuỗi Chương",
    actual_durations: Optional[List[float]] = None,
    speed: float = 1.0
) -> Dict[str, Any]:
    """
    Tự động cộng dồn timeline của toàn bộ danh sách chương thành 1 JSON gộp hoàn chỉnh.
    Tự động scale tỷ lệ câu chữ theo độ dài MP3 thực tế và hệ số tốc độ (speed) để đồng bộ 100% mili-giây.
    """
    current_offset = 0.0
    merged_segments = []
    merged_words = []
    chapters_meta = []
    effective_speed = max(0.25, min(4.0, float(speed))) if speed else 1.0

    for i, chap in enumerate(chapters_data_list):
        chap_start = current_offset
        chap_id = chap.get("chapter_id", chap.get("chapter_no", i + 1))
        chap_title = chap.get("title", f"Chương {chap_id}")
        if re.search(r'[\u4e00-\u9fff]', chap_title):
            chap_title = f"Chương {chap_id}"

        raw_segs = chap.get("segments", [])
        raw_chap_dur = float(chap.get("duration", 0.0))
        if raw_chap_dur <= 0 and raw_segs:
            raw_chap_dur = raw_segs[-1]["end"]

        if actual_durations and i < len(actual_durations) and actual_durations[i] > 0:
            chap_dur = actual_durations[i]
        else:
            chap_dur = raw_chap_dur

        time_scale = (chap_dur / raw_chap_dur) if (raw_chap_dur > 0 and abs(chap_dur - raw_chap_dur) > 0.05) else 1.0

        for seg in raw_segs:
            orig_s = float(seg.get("start", 0.0))
            orig_e = float(seg.get("end", 0.0))

            scaled_s = orig_s * time_scale
            scaled_e = orig_e * time_scale

            raw_s = scaled_s + current_offset
            raw_e = scaled_e + current_offset

            # Áp dụng hệ số tốc độ (speed) cho từng mốc thời gian
            new_s = round(raw_s / effective_speed, 3)
            new_e = round(raw_e / effective_speed, 3)

            new_words = []
            for w in seg.get("words", []):
                w_text = w.get("word", "")
                clean_w = re.sub(r'[\u4e00-\u9fff]', '', w_text).strip() or w_text
                w_orig_s = float(w.get("start", 0.0))
                w_orig_e = float(w.get("end", 0.0))

                w_scaled_s = w_orig_s * time_scale
                w_scaled_e = w_orig_e * time_scale

                w_raw_s = w_scaled_s + current_offset
                w_raw_e = w_scaled_e + current_offset

                word_obj = {
                    "word": clean_w,
                    "start": round(w_raw_s / effective_speed, 3),
                    "end": round(w_raw_e / effective_speed, 3)
                }
                new_words.append(word_obj)
                merged_words.append(word_obj)

            clean_seg_text = re.sub(r'[\u4e00-\u9fff]', '', seg.get("text", ""))
            clean_seg_text = re.sub(r' +', ' ', clean_seg_text).strip() or seg.get("text", "")

            merged_segments.append({
                "chapter_id": chap_id,
                "start": new_s,
                "end": new_e,
                "text": clean_seg_text,
                "words": new_words
            })

        chap_end = round(chap_start + chap_dur, 3)
        chapters_meta.append({
            "chapter_id": chap_id,
            "title": chap_title,
            "start": round(chap_start / effective_speed, 3),
            "end": round(chap_end / effective_speed, 3),
            "duration": round(chap_dur / effective_speed, 3)
        })

        current_offset = chap_end

    merged_data = {
        "title": novel_title,
        "speed": effective_speed,
        "total_chapters": len(chapters_data_list),
        "total_duration": round(current_offset / effective_speed, 3),
        "total_sentences": len(merged_segments),
        "chapters": chapters_meta,
        "segments": merged_segments
    }

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)

    return merged_data

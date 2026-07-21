import asyncio
import os
import re
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Novel, Chapter

logger = logging.getLogger(__name__)

# Giọng đọc chuẩn Microsoft Edge Neural TTS Việt Nam
# vi-VN-NamMinhNeural: Giọng nam trầm ấm, truyền cảm, siêu hợp đọc truyện Tiên Hiệp / Cổ Trang
# vi-VN-HoaiMyNeural: Giọng nữ trong trẻo, dịu dàng, ấm áp
DEFAULT_AUDIO_VOICE = "vi-VN-NamMinhNeural"
AUDIO_RATE = "+50%"  # Tốc độ đọc tự nhiên, ấm áp

def strip_html_and_clean_text(text: str) -> str:
    """Làm sạch văn bản tiếng Việt trước khi đưa vào TTS đọc."""
    if not text:
        return ""
    # Xóa thẻ HTML
    clean = re.sub(r"<[^>]+>", "", text)
    # Xóa ký tự đặc biệt thừa
    clean = re.sub(r"[\r\t]", " ", clean)
    clean = re.sub(r" {2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def estimate_chapter_words(text: str) -> int:
    """Đếm số từ tiếng Việt trong chương."""
    if not text:
        return 0
    words = text.split()
    return len(words)


class AudioBatcher:
    """
    Gom các chương thành các Tập Audio dài 3 đến 4 tiếng (ở tốc độ 1.75x).
    
    Ở tốc độ 1.75x (rate=+75%), tốc độ đọc trung bình là ~220-250 từ/phút (~14.000 từ/giờ).
    Mỗi tập 3.5 - 4 tiếng nghe tương đương 45.000 - 55.000 từ.
    """
    TARGET_WORDS_PER_VOLUME = 45000  # Khoảng ~3.5 đến 4 tiếng nghe
    MAX_WORDS_PER_VOLUME = 58000

    @classmethod
    def group_chapters_into_volumes(cls, chapters: List[Chapter]) -> List[Dict[str, Any]]:
        volumes = []
        current_volume_chaps = []
        current_word_count = 0
        volume_idx = 1

        for ch in chapters:
            if not ch.translated_text:
                continue

            cleaned_txt = strip_html_and_clean_text(ch.translated_text)
            word_count = estimate_chapter_words(cleaned_txt)

            if current_word_count + word_count > cls.MAX_WORDS_PER_VOLUME and current_volume_chaps:
                # Đóng tập hiện tại
                start_no = current_volume_chaps[0].chapter_no
                end_no = current_volume_chaps[-1].chapter_no
                est_hours = round(current_word_count / 14000.0, 1)

                volumes.append({
                    "volume_no": volume_idx,
                    "start_chapter": start_no,
                    "end_chapter": end_no,
                    "word_count": current_word_count,
                    "estimated_hours": est_hours,
                    "chapters": current_volume_chaps
                })
                volume_idx += 1
                current_volume_chaps = [ch]
                current_word_count = word_count
            else:
                current_volume_chaps.append(ch)
                current_word_count += word_count

        if current_volume_chaps:
            start_no = current_volume_chaps[0].chapter_no
            end_no = current_volume_chaps[-1].chapter_no
            est_hours = round(current_word_count / 14000.0, 1)

            volumes.append({
                "volume_no": volume_idx,
                "start_chapter": start_no,
                "end_chapter": end_no,
                "word_count": current_word_count,
                "estimated_hours": est_hours,
                "chapters": current_volume_chaps
            })

        return volumes


class AudioTTSManager:
    """
    Quản lý sinh Audio bằng edge-tts giọng Hoài My (vi-VN-HoaiMyNeural) @ 1.75x speed.
    """

    def __init__(self, output_base_dir: str = "output"):
        self.output_base_dir = output_base_dir

    async def generate_chapter_audio_mp3(self, text: str, output_filepath: str, voice: str = DEFAULT_AUDIO_VOICE) -> bool:
        """Sinh 1 file mp3 từ văn bản chương bằng edge-tts."""
        import edge_tts
        
        cleaned = strip_html_and_clean_text(text)
        if not cleaned:
            return False

        try:
            communicate = edge_tts.Communicate(
                cleaned,
                voice=voice,
                rate=AUDIO_RATE
            )
            await communicate.save(output_filepath)
            return os.path.exists(output_filepath) and os.path.getsize(output_filepath) > 0
        except Exception as e:
            logger.error(f"Lỗi khi sinh Audio edge-tts: {e}")
            return False

    async def generate_volume_audio(
        self,
        novel_title: str,
        volume_info: Dict[str, Any],
        voice: str = DEFAULT_AUDIO_VOICE,
        progress_callback=None
    ) -> Optional[str]:
        """
        Sinh trọn vẹn 1 Tập Audio (3-4 tiếng) và ghép nối thành file MP3 duy nhất.
        Tên file: <Tên Truyện> - Tập XX (Chương AAA - Chương BBB).mp3
        """
        invalid_chars = '<>:"/\\|?*\r\n\t'
        safe_title = "".join(c for c in novel_title if c not in invalid_chars).strip().replace("  ", " ")
        novel_folder = os.path.join(self.output_base_dir, safe_title, "audio")
        os.makedirs(novel_folder, exist_ok=True)

        vol_no = volume_info["volume_no"]
        start_ch = volume_info["start_chapter"]
        end_ch = volume_info["end_chapter"]
        
        volume_filename = f"{safe_title} - Tập {vol_no:02d} (Chương {start_ch:04d} - Chương {end_ch:04d}).mp3"
        final_mp3_path = os.path.join(novel_folder, volume_filename)

        temp_dir = os.path.join(novel_folder, f"_temp_vol_{vol_no}")
        os.makedirs(temp_dir, exist_ok=True)

        chapters = volume_info["chapters"]
        total_ch = len(chapters)
        temp_files = []

        logger.info(f"🎧 Bắt đầu sinh Audio Tập {vol_no:02d} ({start_ch} - {end_ch}) cho truyện '{safe_title}'...")

        # Sinh Audio siêu tốc độ 25 luồng song song (gấp 20x thực tế) cho edge-tts
        semaphore = asyncio.Semaphore(25)

        async def _gen_ch(ch: Chapter, idx: int):
            async with semaphore:
                temp_path = os.path.join(temp_dir, f"ch_{ch.chapter_no:04d}.mp3")
                
                # Tiêu đề chương đọc đầu mỗi chương
                heading_intro = f"Chương {ch.chapter_no}. {ch.title}.\n\n"
                full_text = heading_intro + (ch.translated_text or "")
                
                ok = await self.generate_chapter_audio_mp3(full_text, temp_path, voice=voice)
                if progress_callback:
                    await progress_callback(idx + 1, total_ch, ch.chapter_no)
                return temp_path if ok else None

        tasks = [_gen_ch(ch, i) for i, ch in enumerate(chapters)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Thu thập danh sách file mp3 hợp lệ theo thứ tự
        for r in results:
            if isinstance(r, str) and os.path.exists(r) and os.path.getsize(r) > 0:
                temp_files.append(r)

        if not temp_files:
            logger.error(f"Không thể sinh Audio cho Tập {vol_no}")
            return None

        # Sắp xếp temp_files theo thứ tự chương
        temp_files.sort()

        # Ghép nối các file MP3 thành 1 file tập duy nhất
        try:
            with open(final_mp3_path, "wb") as outfile:
                for tf in temp_files:
                    with open(tf, "rb") as infile:
                        outfile.write(infile.read())
                    try:
                        os.remove(tf)
                    except Exception:
                        pass
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

            logger.info(f"🎉 Đã tạo xong Tập Audio MP3: {volume_filename} (Dung lượng: {os.path.getsize(final_mp3_path)/1024/1024:.2f} MB)")
            return final_mp3_path
        except Exception as e:
            logger.error(f"Lỗi ghép file MP3 Tập {vol_no}: {e}")
            return None

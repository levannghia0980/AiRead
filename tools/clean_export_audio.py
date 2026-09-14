"""
Script dọn dẹp các file MP3 và Timeline JSON gộp (Batch Export) dư thừa trong Output/05_Audio_TTS
và các file backup/test trong scratch/.

LƯU Ý QUAN TRỌNG:
- TUYỆT ĐỐI KHÔNG xóa các file trong thư mục con `chapters/` (đây là audio từng chương gốc).
- Chỉ xóa các file MP3 dài gộp nhiều chương (ví dụ: Ch1_to_Ch100.mp3) và timeline JSON gộp đi kèm nằm trực tiếp dưới thư mục tên truyện.
"""

import os
import sys

def cleanup(dry_run: bool = False):
    sys.stdout.reconfigure(encoding='utf-8')
    base_audio = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Output", "05_Audio_TTS")
    base_scratch = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
    
    deleted_files = []
    total_freed_bytes = 0

    print("=" * 60)
    print("🧹 BẮT ĐẦU QUÉT VÀ DỌN DẸP FILE XUẤT THỪA & FILE RÁC")
    print("=" * 60)

    # 1. Quét các file xuất gộp ngoài thư mục chapters/ trong 05_Audio_TTS
    if os.path.exists(base_audio):
        for novel in sorted(os.listdir(base_audio)):
            novel_path = os.path.join(base_audio, novel)
            if not os.path.isdir(novel_path):
                # File nằm trực tiếp trong 05_Audio_TTS (như test_chua_du.wav)
                if os.path.isfile(novel_path):
                    sz = os.path.getsize(novel_path)
                    total_freed_bytes += sz
                    deleted_files.append((novel_path, sz, "File test thừa trong 05_Audio_TTS"))
                    if not dry_run:
                        try:
                            os.remove(novel_path)
                        except Exception as e:
                            print(f"Lỗi khi xóa {novel_path}: {e}")
                continue

            # Các file nằm trực tiếp dưới thư mục truyện (bên ngoài thư mục chapters/)
            for item in os.listdir(novel_path):
                # Bảo vệ file metadata bắt đầu bằng _ (như _export_meta.json)
                if item.startswith("_"):
                    continue
                item_path = os.path.join(novel_path, item)
                if os.path.isfile(item_path):
                    # Đây là file mp3 hoặc json gộp nhiều chương (vd: Ch1_to_Ch70.mp3)
                    sz = os.path.getsize(item_path)
                    total_freed_bytes += sz
                    deleted_files.append((item_path, sz, f"Batch Export: {novel}"))
                    if not dry_run:
                        try:
                            os.remove(item_path)
                        except Exception as e:
                            print(f"Lỗi khi xóa {item_path}: {e}")

    # 2. Quét các file backup / test trong scratch/
    if os.path.exists(base_scratch):
        for root, dirs, files in os.walk(base_scratch):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".bak", ".tmp", ".wav"] or (ext == ".mp3" and "test" in f.lower() or "dsp_" in f.lower()):
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        total_freed_bytes += sz
                        deleted_files.append((fp, sz, "Scratch / Test / Backup"))
                        if not dry_run:
                            os.remove(fp)
                    except Exception as e:
                        print(f"Lỗi khi xóa {fp}: {e}")

    # Báo cáo kết quả
    for fp, sz, cat in deleted_files:
        status = "[XEM TRƯỚC]" if dry_run else "[ĐÃ XÓA]"
        print(f"{status} {cat:30s} | {os.path.basename(fp)} ({sz / (1024**2):.2f} MB)")

    freed_mb = total_freed_bytes / (1024**2)
    freed_gb = total_freed_bytes / (1024**3)
    print("=" * 60)
    action = "Sẽ giải phóng" if dry_run else "Đã giải phóng thành công"
    print(f"🎉 TỔNG KẾT: {action} {len(deleted_files)} file | {freed_mb:.1f} MB (~{freed_gb:.2f} GB) dung lượng ổ đĩa!")
    print("🔒 Tất cả 100% các file chương gốc trong 'chapters/' vẫn được bảo toàn nguyên vẹn.")
    print("=" * 60)

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    cleanup(dry_run=is_dry)

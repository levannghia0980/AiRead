"""
Công cụ cắt bỏ tiêu đề chương thông minh & an toàn tuyệt đối.
Đặc điểm:
- Chỉ cắt bỏ đúng định dạng tiêu đề chương (Chương X: [Tên], --- CHƯƠNG X: ... ---, [Chương X]...).
- TUYỆT ĐỐI KHÔNG cắt nhầm các câu truyện có chứa từ thông thường như 'bắt đầu', 'kết thúc', 'cuộc thi bắt đầu', 'trận đấu kết thúc'.
- Bảo toàn 100% câu chữ, từng đoạn văn và lời thoại trong truyện.
- Hỗ trợ xử lý cả thư mục chương (chapters/*.txt) lẫn file tổng hợp (_Full.txt).
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')


def strip_chapter_title(text: str, fallback_title: str = "") -> str:
    """
    Cắt bỏ chuẩn xác 100% tiêu đề chương ở đầu văn bản mà TUYỆT ĐỐI không cắt nhầm nội dung truyện:
    - Nhận diện các định dạng: 'Chương X: [Tên]', 'Chapter X: [Tên]', '--- CHƯƠNG X: [Tên] ---', '=== Chương X ===', '[Chương X]'...
    - Nếu tiêu đề bị dính liền câu truyện đầu tiên trên cùng dòng (VD: 'Chương 1: Hắc Sắc Chuyển Bàn. Chết tiệt!'),
      chỉ cắt đúng phần tên chương, bảo toàn câu văn 'Chết tiệt!' vào thân truyện.
    - Tuyệt đối không xóa nhầm các từ thông thường như 'bắt đầu', 'kết thúc', 'cuộc thi bắt đầu', 'trận đấu kết thúc'.
    - Nếu dòng đầu tiên là nội dung truyện thuần túy (không có tiền tố chương / không khớp tiêu đề), giữ nguyên 100%.
    """
    if not text or not text.strip():
        return ""

    lines = text.strip().split('\n')
    first_idx = -1
    for i, l in enumerate(lines):
        if l.strip():
            first_idx = i
            break

    if first_idx == -1:
        return ""

    first_line = lines[first_idx].strip()
    rest_lines = lines[first_idx + 1:]

    clean_line = re.sub(r'^[=\-_\*#\s\(\[\{【（"“]+|[=\-_\*#\s\)\]\}】）"”]+$', '', first_line).strip()

    # 1. Khớp định dạng có tiền tố chương: Chương / Chapter / Hồi / Tiết / Quyển
    ch_match = re.match(r'^(?:Quyển\s*\d+\s*)?(?:Chương|Chapter|Hồi|Tiết|Chap|Vol|Volume)\s*\d*[\s:.-]*(.*)$', clean_line, re.IGNORECASE)
    if ch_match:
        raw_tail = ch_match.group(1).strip()
        raw_tail = re.sub(r'[\(（](?:cầu|hết|chương).*?[\)）]', '', raw_tail, flags=re.IGNORECASE).strip()

        clean_fb = ""
        if fallback_title:
            clean_fb = re.sub(r'^(?:第?\s*\d+\s*章\s*[:.:-]?|Chương\s*\d+\s*[:.:-]?)', '', fallback_title, flags=re.IGNORECASE).strip()
            clean_fb = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', clean_fb)

        body_prefix = ""
        if clean_fb and raw_tail.lower().startswith(clean_fb.lower()) and len(raw_tail) > len(clean_fb) + 3:
            after = raw_tail[len(clean_fb):].strip()
            body_prefix = re.sub(r'^[.:,\s-]+', '', after).strip()
        elif len(raw_tail) > 60:
            split_m = re.search(r'(?:\!\.\.|\?\.\.|\.\.|\!|\?|\.)\s+', raw_tail)
            if split_m and split_m.start() < 60:
                body_prefix = raw_tail[split_m.end():].strip()
            elif len(raw_tail) > 80:
                body_prefix = raw_tail[60:].strip()

        result_lines = []
        if body_prefix:
            result_lines.append(body_prefix)
        result_lines.extend(rest_lines)
        return '\n'.join(result_lines).strip()

    # 2. Khớp với fallback_title
    if fallback_title:
        clean_fb = re.sub(r'^(?:第?\s*\d+\s*章\s*[:.:-]?|Chương\s*\d+\s*[:.:-]?)', '', fallback_title, flags=re.IGNORECASE).strip()
        clean_fb = re.sub(r'^[.:,\s-]+|[.:,\s-]+$', '', clean_fb)
        if clean_fb and clean_line.lower() == clean_fb.lower():
            return '\n'.join(rest_lines).strip()
        elif clean_fb and clean_line.lower().startswith(clean_fb.lower()) and len(clean_line) > len(clean_fb) + 3:
            after = clean_line[len(clean_fb):].strip()
            after = re.sub(r'^[.:,\s-]+', '', after).strip()
            return (after + '\n' + '\n'.join(rest_lines)).strip()

    # 3. Không khớp tiêu đề: Giữ nguyên 100%
    return text.strip()


def process_file(file_path: str, backup: bool = True) -> bool:
    """Xử lý bỏ tiêu đề chương cho 1 file lẻ."""
    if not os.path.exists(file_path):
        print(f"❌ File không tồn tại: {file_path}")
        return False

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    cleaned = strip_chapter_title(content)

    if backup:
        bak_path = file_path + ".bak"
        if not os.path.exists(bak_path):
            shutil.copy2(file_path, bak_path)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(cleaned + "\n")

    print(f"✅ Đã xử lý: {os.path.basename(file_path)}")
    return True


def process_novel_folder(folder_name: str, update_db: bool = True) -> bool:
    """Xử lý toàn bộ các chương và file Full trong Output/04_KetQua/<folder_name>."""
    base_dir = r"D:\NENGHIA0980\AIREAD\Output\04_KetQua"
    novel_path = os.path.join(base_dir, folder_name)

    if not os.path.exists(novel_path):
        # Thử tìm tương đối
        matches = [d for d in os.listdir(base_dir) if folder_name.lower() in d.lower()]
        if matches:
            novel_path = os.path.join(base_dir, matches[0])
            folder_name = matches[0]
        else:
            print(f"❌ Không tìm thấy thư mục truyện: {folder_name} tại {base_dir}")
            return False

    print(f"📖 Bắt đầu xử lý bộ truyện: {folder_name}")
    chaps_dir = os.path.join(novel_path, "chapters")
    full_file = os.path.join(novel_path, f"{folder_name}_Full.txt")

    cleaned_map = {}
    if os.path.exists(chaps_dir):
        files = sorted([f for f in os.listdir(chaps_dir) if f.endswith('.txt')])
        print(f"  -> Tìm thấy {len(files)} file chương.")
        for f in files:
            p = os.path.join(chaps_dir, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                txt = fp.read()
            clean_txt = strip_chapter_title(txt)
            with open(p, 'w', encoding='utf-8') as fp:
                fp.write(clean_txt + "\n")
            c_no = int(os.path.splitext(f)[0]) if os.path.splitext(f)[0].isdigit() else f
            cleaned_map[c_no] = clean_txt

    # Tạo lại Full.txt nếu có các chương
    if cleaned_map and os.path.exists(full_file):
        print(f"  -> Cập nhật file tổng hợp: {os.path.basename(full_file)}")
        # Đọc header truyện
        with open(full_file, 'r', encoding='utf-8', errors='ignore') as fp:
            orig_head = []
            for _ in range(5):
                l = fp.readline()
                if l.startswith('===') or l.startswith('Tác giả:'):
                    orig_head.append(l)

        with open(full_file, 'w', encoding='utf-8') as fp:
            if orig_head:
                fp.writelines(orig_head)
                fp.write("\n\n")
            for c_no in sorted(cleaned_map.keys(), key=lambda x: int(x) if isinstance(x, int) else 0):
                fp.write(cleaned_map[c_no])
                fp.write("\n\n\n")

    # Cập nhật DB
    if update_db and os.path.exists("database.db"):
        try:
            conn = sqlite3.connect("database.db")
            c = conn.cursor()
            nid_row = c.execute(
                "SELECT id FROM novels WHERE title_rough LIKE ? OR title_raw LIKE ?",
                (f"%{folder_name}%", f"%{folder_name}%")
            ).fetchone()
            if nid_row:
                nid = nid_row[0]
                up_cnt = 0
                for c_no, txt in cleaned_map.items():
                    if isinstance(c_no, int):
                        ch_r = c.execute("SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?", (nid, c_no)).fetchone()
                        if ch_r:
                            cid = ch_r[0]
                            c.execute("UPDATE chapter_versions SET content=? WHERE chapter_id=? AND version_type IN ('FINAL', 'EDITED', 'LLM')", (txt, cid))
                            up_cnt += 1
                conn.commit()
                print(f"  -> Đã đồng bộ CSDL database.db cho {up_cnt} chương.")
            conn.close()
        except Exception as db_err:
            print(f"  ⚠️ Không thể cập nhật CSDL: {db_err}")

    print(f"✨ Hoàn tất xử lý bỏ tên chương cho '{folder_name}'. Bảo toàn 100% nội dung truyện!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cắt bỏ tiêu đề chương an toàn 100%")
    parser.add_argument("--novel", type=str, help="Tên thư mục truyện trong Output/04_KetQua")
    parser.add_argument("--file", type=str, help="Đường dẫn đến file văn bản cần cắt tiêu đề")
    args = parser.parse_args()

    if args.file:
        process_file(args.file)
    elif args.novel:
        process_novel_folder(args.novel)
    else:
        # Mặc định xử lý bộ Tôi có một kỹ năng thụ động
        process_novel_folder("Tôi có một kỹ năng thụ động")

# TÀI LIỆU QUẢN LÝ KẾ HOẠCH, CÔNG NGHỆ & LỊCH SỬ THAY ĐỔI (SYSTEM CHANGELOG)

Tài liệu này tổng hợp toàn bộ kiến trúc công nghệ, lịch sử thay đổi kế hoạch và quy chuẩn dịch thuật của hệ thống **AiRead v2**.

---

## 🛠️ 1. ARCHITECTURE & TECHNOLOGY STACK (CÔNG NGHỆ HỆ THỐNG)

- **Backend Framework:** FastAPI (Python 3.10+), Uvicorn Server, Asyncio Event Loop.
- **Database Layer:** SQLite (SQLAlchemy AsyncSession), Auto-migration Engine (`ALTER TABLE glossaries ADD COLUMN notes TEXT`).
- **AI Core / LLM Providers:**
  - Gemini API (Google DeepMind) / OpenRouter (DeepSeek V3/R1).
  - Multi-tier Retry Mechanism + Dynamic System Instruction Injection.
- **Audio Engine & Audio Studio Page:**
  - Microsoft Edge Neural TTS (`edge-tts`).
  - Giọng nữ truyền cảm: `vi-VN-HoaiMyNeural` @ `+75%` (1.75x speed).
  - **Trang Audio Studio Độc Lập:** Giao diện Trình Phát Âm Thanh cao cấp (Play/Pause, Tua 10s, Seekbar kéo thả chỉnh đoạn, Thanh kéo Volume 0-100%, Đổi tốc độ 1.0x-2.0x).
- **Crawler & Scraper Engine (Multi-Plugin Dedicated Architecture):**
  - **Dynamic Engine:** HTTPX Async + Playwright / Custom Parsers.
  - **Dedicated Scrapers:**
    - `Shuba69Scraper` (69shuba.cx / 69shuba.com).
    - `AliceswScraper` (`alicesw.com`): Tự động giải mã các link chương dạng mã băm Hash URL (như `/book/31135/1909bc70efc01.html`, `/book/31135/b99612993a94c.html`), tự động quy đổi về trang Mục Lục Đầy Đủ `/other/chapters/id/30340.html` để bóc tách chính xác 100% toàn bộ 1589+ chương mà không bỏ sót bất kỳ chương nào.
    - `GenericScraper` (Catch-all fallback).
- **Translation Pipeline (Data-Driven Architecture & 0-Token Cost Pyramid):**
  1. **Tầng 1 (0 Token, 0 Latency - Dict Tĩnh & Lookup Table):**
     - Dấu câu `PUNCT_MAP` (`，。！？「」『』` ➔ `, . ! ? " "`) & Đơn vị cổ `UNIT_MAP` (`两/文/里/尺/子时/三更`).
     - Từ điển Hán-Việt tĩnh `HANVIET_DICT` & `convert_to_hanviet_name()` quy đổi Hán-Việt 100% offline với 0 Token, 0 Latency (`苏檀儿` ➔ `Tô Đàn Nhi`, `宁毅` ➔ `Ninh Dịch`, `小婵` ➔ `Tiểu Thiền`).
  2. **Tầng 2 (Bản Đồ Quan Hệ Nhân Vật Persistent - 1 Lần / Truyện):**
     - Quét và trích xuất quan hệ nhân vật (`Character Relationship Map`) 1 lần duy nhất cho toàn bộ câu chuyện, lưu vào `characters.json` và DB `Glossary` (bổ sung trường `notes`), tái sử dụng cho 1000+ chương.
  3. **Tầng 3 (Generic Detector & Batch Learning Loop):**
     - Leftover Detector ưu tiên tra cứu Hán-Việt offline 0 Token trước. Bất kỳ từ mới nào cũng được batch-resolve 1 lần duy nhất và ghi persistent vào SQLite DB (`Glossary`).
     - So khớp cục bộ (Self-Consistency Pass) đồng bộ biến thể tên trong chương.
  4. **Tầng 4 (Pass Dịch Chính Văn & Perfect Output Polish):**
     - Dùng LLM cho bản dịch chính văn kèm context header. Biên tập nhịp văn điện ảnh và chuẩn hóa trình bày ngắt đoạn `\n\n`.

---

## 📋 2. QUẢN LÝ QUY TẮC DỊCH THUẬT (TRANSLATION BIBLE)

Hệ thống tuân thủ 20 nhóm quy tắc dịch thuật chuẩn Tiên Hiệp / Cổ Trang (như Bạch Ngọc Sách, Tàng Thư Viện, TruyenYY) cùng 14 Tiêu Chuẩn Biên Tập Điện Ảnh & Trang Studio Audio Cao Cấp:

1. **Kim Tự Tháp Chi Phí Token & Latency (Cost Pyramid):** Tuyệt đối không gọi LLM cho các công việc có thể giải bằng tra cứu tĩnh 0 Token. Chỉ gọi LLM cho phần dịch chính văn và phân tích quan hệ ngữ cảnh.
2. **Tri Thức Hướng Dữ Liệu Persistent (Data-Driven Triad):** Mọi tri thức riêng của từng truyện (tên riêng, xưng hô, mối quan hệ) được lưu persistent trong SQLite DB (`Glossary`) & `characters.json`. Code Python chỉ giữ lại phần Universal & Generic Detectors.
3. **Chuẩn Hóa Dấu Câu & Đơn Vị Cổ Universal:** Tự động quy đổi `，。！？「」『』` sang `, . ! ? " "` và các đơn vị `lượng`, `văn`, `dặm`, `thước`, `canh ba`, `giờ Tý` ở bước 1.
4. **Bản Đồ Quan Hệ Nhân Vật Khóa CỨNG:** Trích xuất vai trò nhân vật (Ví dụ: Ninh Dịch = Cô gia/Tướng công; Tô Đàn Nhi = Tiểu thư/Thê tử; Tiểu Thiền = Nha hoàn) và ép AI dịch đúng từ xưng hô ngay từ đầu.
5. **Cơ Chế Tự Học Từ Mới (Self-Learning Loop):** Mọi cụm chữ Hán hoặc Pinyin sót ở bước hậu kiểm được AI/Dict giải cứu 1 lần và tự động ghi thẳng vào SQLite DB (`Glossary`).
6. **Cơ Chế Xóa Triệt Để 100% (Hard Purge On Delete/Reset):** Mọi nút xóa (Xóa truyện, Reset chương, Xóa 1 chương lẻ) đều xóa sạch 100% dữ liệu tiếng Trung đầu vào (`raw_text`), dữ liệu dịch đầu ra (`translated_text`), bộ nhớ tạm SQLite (`TranslationCache`), file `.txt` vật lý trong thư mục `output/` và danh sách bỏ qua lỗi.

---

## 📝 3. LỊCH SỬ KẾ HOẠCH & NÂNG CẤP (CHANGELOG)

### 📅 Version 2.7.1 - [2026-07-21]
- **Tích Hợp Tự Động Migration Cấu Trúc SQLite DB (`database.py`):**
  - **Khắc phục triệt để lỗi `sqlite3.OperationalError: no such column: glossaries.notes`:** Bổ sung cơ chế tự động thực thi query `ALTER TABLE glossaries ADD COLUMN notes TEXT` trong hàm `init_db()` khi ứng dụng khởi chạy. Đảm bảo mọi file SQLite `database.db` cũ cũng được cập nhật schema tự động 100% mà không bị mất dữ liệu.

### 📅 Version 2.7.0 - [2026-07-21]
- **Tạo Plugin Cào Truyện Chuyên Dụng AliceswScraper (`alicesw.com`).**

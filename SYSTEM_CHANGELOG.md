# TÀI LIỆU QUẢN LÝ KẾ HOẠCH, CÔNG NGHỆ & LỊCH SỬ THAY ĐỔI (SYSTEM CHANGELOG)

Tài liệu này tổng hợp toàn bộ kiến trúc công nghệ, lịch sử thay đổi kế hoạch và quy chuẩn dịch thuật của hệ thống **AiRead v2**.

---

## 🛠️ 1. ARCHITECTURE & TECHNOLOGY STACK (CÔNG NGHỆ HỆ THỐNG)

- **Backend Framework:** FastAPI (Python 3.10+), Uvicorn Server, Asyncio Event Loop.
- **Database Layer:** SQLite (SQLAlchemy AsyncSession), Pydantic schemas.
- **AI Core / LLM Providers:**
  - Gemini API (Google DeepMind) / OpenRouter (DeepSeek V3/R1).
  - Multi-tier Retry Mechanism + Dynamic System Instruction Injection.
- **Audio Engine & Audio Studio Page:**
  - Microsoft Edge Neural TTS (`edge-tts`).
  - Giọng nữ truyền cảm: `vi-VN-HoaiMyNeural` @ `+75%` (1.75x speed).
  - **Trang Audio Studio Độc Lập:** Giao diện Trình Phát Âm Thanh cao cấp (Play/Pause, Tua 10s, Seekbar kéo thả chỉnh đoạn, Thanh kéo Volume 0-100%, Đổi tốc độ 1.0x-2.0x).
  - **Quản lý Tập Đã Tạo vs. Chưa Tạo:** Phân biệt rõ các Tập MP3 3-4 tiếng đã tạo (`✅ Đã Tạo MP3`) vs chưa tạo (`⏳ Chưa Tạo`). Hỗ trợ nút **▶ Tạo Tập Này** độc lập và nút **🚀 Tạo Tất Cả Các Tập**.
- **Crawler & Scraper Engine:** Playwright / HTTPX Async + Custom Parsers (69shuba, twkan, etc.).
- **Translation Pipeline (3-Pass Multi-Genre Auto-Pipeline):**
  1. **Pass 1 (Pre-processing Fast-Scanner <10ms):** Quét Tên + Tóm tắt + 500 ký tự đầu ➔ Khóa 1 trong 5 thể loại (`XIANXIA`, `HISTORICAL`, `MODERN_URBAN`, `ROMANCE`, `SCI_FI_SYSTEM`) và chốt `Translation Context Payload` ngay từ dòng 1 của Chương 1.
  2. **Pass 2 (In-processing Stream Translation):** Dịch với Context Header (`GENRE_LOCK: TRUE`), điều hướng xưng hô linh hoạt theo thể loại đã chốt.
  3. **Pass 3 (Post-processing Boundary Enforcer & Gatekeeper):** TỰ ĐỘNG SỬA 100% các từ "lạc quẻ" theo thể loại bằng code (Đô thị ➔ tôi/nhà/công ty; Tiên hiệp ➔ ta/ngươi/đan điền) + Strict Quality Gatekeeper.

---

## 📋 2. QUẢN LÝ QUY TẮC DỊCH THUẬT (TRANSLATION BIBLE)

Hệ thống tuân thủ 20 nhóm quy tắc dịch thuật chuẩn Tiên Hiệp / Cổ Trang (như Bạch Ngọc Sách, Tàng Thư Viện, TruyenYY) cùng 14 Tiêu Chuẩn Biên Tập Điện Ảnh & Trang Studio Audio Cao Cấp:

1. **Trang Audio Studio Độc Lập & Player Cao Cấp:** Giao diện phát audio chuyên nghiệp có thanh Seekbar kéo thả, Volume, Tua 10s, tốc độ đọc linh hoạt và bộ lọc tập đã tạo/chưa tạo.
2. **Audio Engine Giọng Hoài My (1.75x):** Sinh audio truyền cảm bằng Microsoft Edge Neural TTS, tốc độ 1.75x, nghe không đau tai, tự động gom 3-4 tiếng/tập.
3. **Khóa Thể Loại Tự Động (Multi-Genre Profile Locker):** Tự động phân loại 5 dòng truyện chính (*Tiên Hiệp, Cổ Trang, Đô Thị Hiện Đại, Ngôn Tình, Mạt Thế/Game Hệ Thống*).
4. **Hậu Xử Lý Tự Động 100% (Genre Boundary Enforcer):** Tự động phát hiện và sửa sạch các từ sai lệch thể loại trước khi trả bản dịch về cho người dùng.
5. **Bảo Tồn Nội Dung Tuyệt Đối (Zero Omission & Zero Hallucination):** Tuyệt đối KHÔNG ĐƯỢC BỎ SÓT bất kỳ câu, đoạn, lời thoại nào. Tuyệt đối KHÔNG ĐƯỢC TỰ Ý THÊM THẮT hay bịa đặt nội dung.

---

## 📝 3. LỊCH SỬ KẾ HOẠCH & NÂNG CẤP (CHANGELOG)

### 📅 Version 2.5.0 - [2026-07-21]
- **Tạo Trang Audio Studio Độc Lập & Trình Phát Âm Thanh Cao Cấp (Dedicated Audio Studio):**
  - **Tab Menu Độc Lập:** Đưa Audio ra trang riêng **"🎧 Audio Studio"** ở thanh điều hướng chính.
  - **Advanced Player Interface:** Trình phát nhạc cao cấp tích hợp Play/Pause, Tua 10s, Seekbar kéo thả nhảy đoạn, Thanh kéo Volume (0-100%) & nút Mute, chọn Tốc độ phát (`1.0x`, `1.25x`, `1.5x`, `1.75x`, `2.0x`).
  - **Quản lý Tập Đã Tạo vs Chưa Tạo:** Hiển thị thẻ phân biệt `✅ Đã Tạo MP3` (có nút Phát Ngay & Tải MP3) và `⏳ Chưa Tạo` (có nút `▶ Tạo Tập Này` độc lập).
  - **Backend Endpoints Mới:** `GET /api/novels/{novel_id}/audio/volumes` và `POST /api/novels/{novel_id}/audio/generate_volume/{volume_no}`.

### 📅 Version 2.4.0 - [2026-07-21]
- **Tích Hợp Module Tạo Audio Truyện Tự Động (Edge Neural TTS Audio Engine):**
  - **Giọng nữ Hoài My (`vi-VN-HoaiMyNeural`) @ 1.75x:** Tạo file âm thanh 24kHz/48kHz trong trẻo, êm ái, đeo tai nghe nghe liên tục không gây đau mệt tai.
  - **Tự động Phân Tập 3-4 Tiếng:** Viết lớp `AudioBatcher` gom các chương đã dịch thành các file MP3 tập dài 3.5 - 4 tiếng nghe.

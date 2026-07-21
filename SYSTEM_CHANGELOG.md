# TÀI LIỆU QUẢN LÝ KẾ HOẠCH, CÔNG NGHỆ & LỊCH SỬ THAY ĐỔI (SYSTEM CHANGELOG)

Tài liệu này tổng hợp toàn bộ kiến trúc công nghệ, lịch sử thay đổi kế hoạch và quy chuẩn dịch thuật của hệ thống **AiRead v2**.

---

## 🛠️ 1. ARCHITECTURE & TECHNOLOGY STACK (CÔNG NGHỆ HỆ THỐNG)

- **Backend Framework:** FastAPI (Python 3.10+), Uvicorn Server, Asyncio Event Loop.
- **Database Layer:** SQLite (SQLAlchemy AsyncSession), Auto-migration Engine (`ALTER TABLE glossaries ADD COLUMN notes TEXT`).
- **AI Core / LLM Providers:**
  - Gemini API (Google DeepMind) / OpenRouter (DeepSeek V3/R1).
  - Multi-tier Retry Mechanism + Dynamic System Instruction Injection.
- **Audio Engine & Audio Studio Page (SIÊU TỐC NÂNG CẤP GẤP 20X):**
  - Microsoft Edge Neural TTS (`edge-tts`).
  - **Giọng đọc trầm ấm, truyền cảm:** `vi-VN-NamMinhNeural` (giọng nam truyền cảm chuẩn Tiên Hiệp/Cổ Trang) / `vi-VN-HoaiMyNeural`.
  - **Tốc độ sinh Audio siêu tốc 25 luồng song song (gấp 20-50x thực tế):** Xử lý trọn vẹn 1 tập Audio dài 3-4 tiếng chỉ trong vài chục giây.
  - **Trang Audio Studio & API Streaming:** Tự động nạp và hiển thị ngay trên giao diện web ngay sau khi sinh xong (phát trực tiếp, tua 10s, seekbar kéo thả, tải file MP3).
  - **Endpoint Liệt Kê File MP3:** `/api/novels/{novel_id}/audio/files` cập nhật danh sách tập đã tạo theo thời gian thực (Real-time polling UI refresh).
- **Crawler & Scraper Engine (Multi-Plugin Dedicated Architecture):**
  - **Dynamic Engine:** HTTPX Async + Playwright / Custom Parsers.
  - **Dedicated Scrapers:**
    - `Shuba69Scraper` (69shuba.cx / 69shuba.com).
    - `AliceswScraper` (`alicesw.com`): Tự động giải mã các link chương dạng mã băm Hash URL.
    - `GenericScraper` (Catch-all fallback).

---

## 📝 2. LỊCH SỬ KẾ HOẠCH & NÂNG CẤP (CHANGELOG)

### 📅 Version 2.8.1 - [2026-07-21]
- **Tự Động Cập Nhật Danh Sách Tập Audio Đã Tạo Lên Giao Diện Theo Thời Gian Thực (Real-Time Audio UI Sync):**
  - **Thêm endpoint `/api/novels/{novel_id}/audio/files`:** Trả về danh sách tất cả các tập MP3 đã được sinh thành công trong thư mục `output/<Tên truyện>/audio/`.
  - **Cập nhật Real-Time Polling trong `AudioStudio.tsx`:** Ngay khi 1 Tập Audio sinh xong, thẻ tập đó sẽ tự động chuyển màu xanh **`✅ Đã Tạo MP3`** lập tức kèm nút Nghe trực tiếp và nút Tải MP3 trên giao diện.

### 📅 Version 2.8.0 - [2026-07-21]
- Nâng cấp Audio Engine siêu tốc 25 luồng song song (gấp 20-50x thực tế) & giọng đọc Nam Minh trầm ấm.

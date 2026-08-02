# 🚀 AiRead v2 - Hệ Thống Dịch Truyện AI Quy Mô Lớn & Tạo AudioBook Tự Động

**AiRead v2** là giải pháp toàn diện cho phép cào truyện, dịch thuật tự động quy mô lớn (hàng trăm ngàn chương) bằng AI (Gemini / OpenAI), áp dụng Từ điển chuẩn (Glossary) và tạo AudioBook giọng đọc AI đỉnh cao với tốc độ siêu nhanh (xử lý 4+ giờ âm thanh chỉ trong ~8 phút).

---

## ✨ Tính Năng Nổi Bật

- 🕷️ **Async Crawler & Unblocker**: Cào dữ liệu truyện từ các nguồn web tốc độ cao, hỗ trợ Playwright vượt Cloudflare / Anti-bot.
- 🤖 **AI Translation Engine**: Tích hợp Google Gemini & OpenAI API, hỗ trợ cân bằng tải nhiều API key (Load Balancing), chia batch tự động, giữ nguyên ngữ cảnh tiên hiệp / huyền huyễn.
- 📚 **Glossary / Terminology System**: Quản lý từ điển nhân vật, địa danh, chiêu thức để dịch nhất quán 100%.
- 🎙️ **Edge-TTS Audio Studio Multi-Worker**:
  - Khởi chạy 24 công nhân (workers) song song tạo Audio.
  - Tự động chia nhỏ văn bản (Chunking) theo dấu ngắt câu tự nhiên.
  - Tự động ghép nối các file âm thanh thành Audiobook MP3 chất lượng cao bằng FFmpeg concat demuxer.
  - Báo phần trăm tiến độ (% hoàn thành), tốc độ chunk/phút và thời gian còn lại (ETA) thời gian thực trên UI.
- 💻 **Modern UI & Responsive**: Giao diện React + TailwindCSS sang trọng, hiển thị tối ưu trên cả Máy tính và Điện thoại di động.
- 📲 **LAN Sharing**: Tự động mở mạng LAN (`0.0.0.0`) cho phép điện thoại kết nối nghe truyện trực tiếp qua Wi-Fi.

---

## 📂 Cấu Trúc Luồng Xử Lý & Thư Mục Output

Trong quá trình dịch và tạo Audio, hệ thống sẽ tự động tạo và lưu trữ kết quả qua 5 giai đoạn độc lập tại thư mục `Output/`:

```text
Output/
├── 01_BanGoc/      # Chứa văn bản thô (Tiếng Trung/Anh) cào về từ web
├── 02_DichMau_GG/   # Bản dịch thô Google Translate (làm bản lót đối chiếu)
├── 03_DichAI_LLM/   # Bản dịch AI (Gemini/OpenAI) qua từng chương
├── 04_KetQua/       # Bản dịch hoàn thiện đã gộp chương & tinh chỉnh
└── 05_Audio_TTS/    # Thư mục tạm & file Audiobook MP3 đầu ra cuối cùng
```

> 💡 **Lưu ý:** Các file văn bản dịch thuật và file âm thanh MP3 đầu ra sẽ **không được tải lên GitHub** để giữ repository nhẹ và sạch. Hệ thống sẽ tự động khởi tạo các thư mục này khi bạn chạy code.

---

## 🛠️ Yêu Cầu Hệ Thống (Prerequisites)

1. **Python 3.10+** (Khuyên dùng Python 3.11 hoặc 3.12)
2. **Node.js 18+** & `npm`
3. **FFmpeg**: Cần thiết cho tính năng ghép file âm thanh AudioBook MP3.
   - *Windows:* Tải FFmpeg và thêm thư mục `bin` của FFmpeg vào biến môi trường `PATH`.
   - *Linux / Mac:* `sudo apt install ffmpeg` hoặc `brew install ffmpeg`.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Code (Quick Start)

Dành cho người dùng mới khi clone repository này về máy tính:

### Bước 1: Clone Repository
```bash
git clone https://github.com/levannghia0980/AiRead.git
cd AiRead
```

### Bước 2: Cài Đặt Môi Trường Python (Backend)
```bash
# Tạo môi trường ảo (Virtual Environment)
python -m venv venv

# Kích hoạt môi trường ảo:
# Trên Windows:
.\venv\Scripts\activate
# Trên Linux/Mac:
# source venv/bin/activate

# Cài đặt các thư viện Python cần thiết
pip install -r requirements.txt
```

### Bước 3: Cài Đặt Thư viện Frontend (React)
```bash
cd frontend
npm install
cd ..
```

### Bước 4: Cấu Hình File Môi Trường `.env`
Sao chép file `.env.example` thành `.env`:
```bash
# Trên Windows CMD/PowerShell:
copy .env.example .env

# Trên Linux/Mac:
cp .env.example .env
```
Mở file `.env` và điền **API Key** của bạn:
```env
AIREAD_PROVIDER=gemini
AIREAD_MODEL=gemini-2.0-flash
AIREAD_API_KEYS=your_gemini_api_key_here
```

### Bước 5: Chạy Ứng Dụng (1 Lệnh Duy Nhất)
Quay lại thư mục gốc dự án và chạy:
```bash
python run.py
```

Lệnh trên sẽ tự động khởi chạy cả **Backend (FastAPI)** và **Frontend (React)** cùng lúc!

---

## 🖥️ Truy Cập Giao Diện Ứng Dụng

Sau khi chạy `python run.py`:

- **Trên Máy Tính:** Mở trình duyệt và truy cập:
  👉 `http://localhost:8000`

- **Trên Điện Thoại (Cùng mạng Wi-Fi):** Mở trình duyệt điện thoại và truy cập địa chỉ IP LAN hiển thị trên màn hình Console:
  👉 `http://<IP_LAN_MAY_TINH>:8000` *(Ví dụ: `http://192.168.61.110:8000`)*

> ⚠️ **Mẹo khi Điện thoại không kết nối được:**
> Nếu điện thoại không truy cập được, nguyên nhân thường do mạng Wi-Fi trên máy tính Windows đang để chế độ `Public Network`. 
> Bạn chỉ cần vào **Wi-Fi Properties** trên Windows và đổi loại mạng từ **Public** sang **Private Network** (Mạng riêng tư).

---

## 🛠️ Công Nghệ Sử Dụng

- **Backend:** FastAPI, AsyncIO, SQLAlchemy, SQLite (aiosqlite), Edge-TTS, FFmpeg, Playwright, Loguru.
- **Frontend:** React 18, Vite, TypeScript, TailwindCSS, Zustand, Lucide Icons.

---

## 📄 License

Dự án được phát hành theo giấy phép Open Source MIT.

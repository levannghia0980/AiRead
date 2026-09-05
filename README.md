# 📚 AiRead - Nền Tảng Dịch Thuật Văn Học AI & Tạo Sách Nói (AudioBook)

**AiRead** là ứng dụng mã nguồn mở hỗ trợ biên dịch tự động văn bản văn học, tiểu thuyết và tài liệu đa ngôn ngữ bằng AI (Google Gemini, OpenAI), tích hợp hệ thống quản lý từ điển ngữ cảnh (Glossary) và chuyển đổi văn bản thành giọng đọc tự nhiên (Text-to-Speech) chất lượng cao.

---

## ✨ Tính Năng Chính

- 🤖 **AI Translation Engine**: Hỗ trợ Google Gemini & OpenAI API với cơ chế cân bằng tải đa khóa (Multi-Key Load Balancing), dịch thuật mượt mà, bảo toàn văn phong và ngữ cảnh văn học.
- 📖 **Quản Lý Thuật Ngữ & Từ Điển (Glossary)**: Tự động trích xuất và quản lý tên nhân vật, địa danh, thuật ngữ chuyên ngành để đảm bảo tính nhất quán trong toàn bộ tác phẩm.
- 🎙️ **Studio Tạo Sách Nói (AudioBook TTS)**:
  - Tích hợp công nghệ Text-to-Speech AI đa luồng (Multi-Worker) xử lý nhanh và ổn định.
  - Tự động phân đoạn câu, tối ưu hóa nhịp thở và ngắt nghỉ tự nhiên.
  - Xuất file Audio MP3 chất lượng phòng thu (Stream Copy) nguyên bản 100%, không suy hao chất lượng.
  - Trình phát tích hợp trên web hỗ trợ tua nhanh, hẹn giờ và phát tuần tự.
- 🖥️ **Giao Diện Hiện Đại & Tương Thích Di Động**: Thiết kế giao diện trực quan bằng React + TailwindCSS, hỗ trợ chế độ Dark Mode và tối ưu trải nghiệm trên cả Máy tính lẫn Điện thoại.
- 📡 **Chia Sẻ Mạng Nội Bộ (LAN Sharing)**: Nghe sách nói và đọc truyện trực tiếp từ điện thoại thông qua mạng Wi-Fi gia đình.

---

## 📂 Cấu Trúc Thư Mục Kết Quả (`Output/`)

Trong quá trình dịch và tạo Audio, hệ thống lưu trữ kết quả qua các giai đoạn rõ ràng:

```text
Output/
├── 01_BanGoc/      # Văn bản gốc tiếng Trung nhập vào hệ thống
├── 03_DichAI_LLM/   # Bản dịch AI trực tiếp (RAWT) theo từng lô chương
├── 04_KetQua/       # Bản dịch hoàn thiện đã chuẩn hóa dấu câu & ngữ điệu
├── 04b_VanBanTTS/   # Văn bản xử lý riêng biệt tối ưu cho giọng đọc TTS
└── 05_Audio_TTS/    # File Audio MP3 thành phẩm
```

---

## 🛠️ Yêu Cầu Hệ Thống

1. **Python 3.10+** (Khuyên dùng Python 3.11 hoặc 3.12)
2. **Node.js 18+** & `npm`
3. **FFmpeg**: Cần thiết cho tính năng ghép và xử lý file âm thanh AudioBook.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### Bước 1: Tải Mã Nguồn
```bash
git clone https://github.com/levannghia0980/AiRead.git
cd AiRead
```

### Bước 2: Cài Đặt Môi Trường Python (Backend)
```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo:
# Trên Windows:
.\venv\Scripts\activate
# Trên Linux/Mac:
# source venv/bin/activate

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### Bước 3: Cài Đặt Thư Viện Frontend
```bash
cd frontend
npm install
cd ..
```

### Bước 4: Cấu Hình File `.env`
Sao chép `.env.example` thành `.env`:
```bash
# Trên Windows:
copy .env.example .env

# Trên Linux/Mac:
cp .env.example .env
```

Điền API Key của bạn vào file `.env`:
```env
AIREAD_PROVIDER=gemini
AIREAD_MODEL=gemini-2.0-flash
AIREAD_API_KEYS=your_api_key_here
```

### Bước 5: Khởi Chạy Ứng Dụng
Chạy lệnh khởi động duy nhất:
```bash
python run.py
```

Ứng dụng sẽ tự động mở tại địa chỉ: `http://localhost:8000`

> 📡 **Truy cập qua mạng nội bộ (LAN):** Mở trình duyệt điện thoại và truy cập địa chỉ IP LAN hiển thị trên màn hình Console:
> 👉 `http://<IP_LAN_MAY_TINH>:8000` *(Ví dụ: `http://192.168.61.110:8000`)*
>
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

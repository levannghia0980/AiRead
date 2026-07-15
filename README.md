# AiRead v2 📚🤖

Hệ thống cào và dịch truyện chữ Trung - Việt thông minh, tự động tối ưu hóa tốc độ và văn phong chất lượng biên tập viên cao cấp.

---

## 🚀 Tính Năng Nổi Bật

### ⚡ Tốc Độ Tối Đa
- **Dịch song song chunks**: Tự động chia chương truyện thành các đoạn văn nhỏ và dịch song song sử dụng `asyncio.gather()`. Tăng tốc độ dịch một chương lên **3 - 5 lần**.
- **Adaptive Limiter**: Bộ điều tiết thông minh tự động điều chỉnh số lượng request song song (tối đa 30) dựa trên phản hồi của API để tránh bị nghẽn hoặc vượt giới hạn.
- **Worker đa luồng**: 15 worker đồng thời giúp cào và dịch nhiều chương cùng lúc với độ trễ cực thấp (từ 0.05 giây).

### ✍️ Chất Lượng Biên Tập Cao
- **Hệ thống 13 quy tắc dịch**: AI được định hướng dịch thoát ý, tự nhiên, thuần Việt, tự động chọn xưng hô phù hợp bối cảnh cổ trang/tiên hiệp/đô thị.
- **Bộ sửa lỗi dịch máy tự động**: Tự động sửa hơn 20 lỗi dịch thô phổ biến (vd: *ăn một kinh ngạc* ➡️ *giật mình*...).
- **Glossary bắt buộc**: Ép bảng thuật ngữ (tên nhân vật, địa danh, chiêu thức) chính xác 100% bằng code sau khi dịch xong.
- **Dọn dẹp thông minh (Cleaner)**: Xóa hoàn toàn các watermark quảng cáo tiếng Trung, liên kết website trước khi đưa vào dịch.

### 🔑 Quản Lý API Key & Bảo Mật
- **Key Rotation**: Xoay vòng khóa API tự động giữa các key trong pool khi gặp lỗi Rate Limit (HTTP 429) hoặc hết hạn mức.
- **Per-key Cooldown**: Đánh dấu khóa bị quá tải để tạm nghỉ, giúp tăng tối đa số lượng chương dịch được trên mỗi key.
- **Bảo mật `.env`**: Lưu trữ khóa bí mật trong file `.env` cục bộ, ngăn chặn rò rỉ khóa lên GitHub.

---

## 🛠️ Công Nghệ Sử Dụng

- **Backend**: Python 3.x, FastAPI, Uvicorn, SQLAlchemy (Async), SQLite.
- **Frontend**: React, Vite, TypeScript, TailwindCSS, Zustand.
- **AI Integrations**: OpenRouter (DeepSeek v3/free, etc.), Gemini, OpenAI, Claude.

---

## 💻 Hướng Dẫn Cài Đặt

### 1. Chuẩn bị Môi trường
Tạo file `.env` bên trong thư mục `frontend` để lưu API Key mặc định của bạn:
`frontend/.env`:
```env
VITE_OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 2. Khởi Chạy Hệ Thống
Hệ thống tích hợp tập lệnh tự động khởi động song song cả Backend và Frontend:

Chỉ cần chạy tập lệnh `run.py` ở thư mục gốc:
```powershell
python run.py
```
*Tập lệnh sẽ tự động chuyển hướng và khởi chạy bên trong môi trường ảo `venv` nếu có.*

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend (API Docs)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📁 Cấu Trúc Thư Mục Chính

```
AiRead2/
├── backend/               # FastAPI Backend
│   ├── app/
│   │   ├── api/          # Các endpoint API (novels, translation...)
│   │   ├── models/       # Database Models
│   │   └── services/     # Logic cào, dịch và xử lý văn bản
│   └── test_pipeline.py  # Script kiểm thử lõi
├── frontend/              # React + Vite Frontend
│   ├── src/
│   │   ├── store/        # Quản lý state (Zustand)
│   │   └── App.tsx       # Giao diện chính
│   └── .env              # File cấu hình keys cục bộ (được bỏ qua bởi Git)
├── run.py                 # Script chạy cả 2 server cùng lúc
└── .gitignore             # Cấu hình loại bỏ file rác và file bảo mật
```

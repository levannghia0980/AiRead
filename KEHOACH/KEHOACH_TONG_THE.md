# KẾ HOẠCH CÔNG NGHỆ & LỘ TRÌNH PHÁT TRIỂN HỆ THỐNG AIREAD (READ2 REFRACTOR)

---

## I. MỤC TIÊU HỆ THỐNG
* **Quy mô**: Cào & Dịch 100.000+ chương.
* **Thời gian vận hành**: 24/7 liên tục không restart.
* **Tối ưu RAM**: Không rò rỉ bộ nhớ (Memory Leak), RAM duy trì ổn định.
* **Tối ưu DB**: Không dính DB lock hay corruption.
* **Khả năng tự khôi phục**: Resume tự động dựa trên trạng thái DB khi mất điện/sự cố.

---

## II. KIẾN TRÚC THÀNH PHẦN (MULTI-SERVICE PIPELINE)

```
               +----------------+
               |   Scheduler    |
               +-------+--------+
                       |
          thêm truyện/chương
                       |
               Queue(Database)
                       |
        +--------------+-------------+
        |                            |
        |                            |
  Crawl Worker                 Translate Worker
        |                            |
        |                            |
      HTML                     Văn bản Việt
        |                            |
        +--------------+-------------+
                       |
                 Save Database
                       |
                Web/API đọc DB
```

---

## III. TECH STACK CHÍNH THỨC

| Thành phần | Công nghệ chọn lựa | Lý do lựa chọn |
| :--- | :--- | :--- |
| **Backend & Dashboard** | FastAPI + Uvicorn | Cực nhẹ, async native, hiệu năng cao, dễ quản lý service |
| **HTTP Client** | `httpx.AsyncClient` | Async hoàn toàn, hỗ trợ HTTP/2, connection pooling tốt |
| **HTML Parser** | `selectolax` | Nhanh gấp 5-10 lần BeautifulSoup, tiêu tốn cực ít RAM |
| **Async Core** | `asyncio` | Quản lý coroutine bất đồng bộ cho crawler, translator & writer |
| **Database & ORM** | PostgreSQL (`asyncpg`) / SQLite (`aiosqlite`) + SQLAlchemy 2.0 Async | Tránh lock, hỗ trợ transaction, connection pool chuẩn |
| **Cache & State** | Redis (hoặc DB Queue Fallback) | Đẩy rate limit, session data, lock key ra khỏi RAM Python |
| **Logging** | `loguru` | Ghi log bất đồng bộ, phân chia channel `crawl.log`, `translate.log`, `error.log` |
| **Retry System** | `tenacity` | Tự động retry exponential backoff khi gặp lỗi mạng/API 429/5xx |
| **Validation & Config** | Pydantic v2 & `pydantic-settings` | Quản lý cấu hình tập trung qua file `.env` |
| **System Monitor** | `psutil` | Giám sát RAM/CPU thực tế, tự giảm worker khi RAM > 80% |

---

## IV. NGUYÊN TẮC THIẾT KẾ CỐT LÕI (CORE RULES)

1. **Tách biệt Process hoàn toàn**: Mỗi worker chỉ đảm nhận 1 nhiệm vụ độc lập (`Crawler`, `Translator`, `Writer`, `Monitor`, `Exporter`).
2. **Persistence Queue**: Trạng thái chương lưu trực tiếp trong DB (`WAIT` -> `CRAWLING` -> `CRAWLED` -> `TRANSLATING` -> `DONE` -> `FAILED`).
3. **No Memory Aggregation**: Không gom 10.000 chương vào mảng RAM. Xử lý dạng Streaming / Single Chapter / Batch nhỏ, thu dọn memory (`del html`, `gc.collect()`) lập tức.
4. **Connection Pooling**: Dùng Pool mở sẵn connection, không connect/disconnect liên tục từng chapter.

---

## V. CÁC GIAI ĐOẠN PHÁT TRIỂN (PHASED ROADMAP)

### 📌 GIAI ĐOẠN 1: Khởi Tạo Cấu Trúc Dự Án, Environment & Core Models
- [ ] Thiết lập cây thư mục dự án chuẩn mô hình Async Multi-Service.
- [ ] Cấu hình Pydantic Settings (`settings.py`), `.env` mẫu.
- [ ] Thiết lập Async Database Engine & Connection Pool với SQLAlchemy 2.0.
- [ ] Định nghĩa DB Schemas (Novel, Chapter, QueueState, SystemMetrics).
- [ ] Thiết lập Loguru logger chia log files.

### 📌 GIAI ĐOẠN 2: Phát Triển Crawler Service & Fetcher Engine
- [ ] Viết `httpx.AsyncClient` wrapper hỗ trợ custom headers, proxy, timeouts.
- [ ] Viết `selectolax` HTML parser để bóc tách tiêu đề & nội dung thô cực nhanh.
- [ ] Viết `Crawler Worker` lấy danh sách chương & nội dung thô, lưu DB với trạng thái `CRAWLED`.

### 📌 GIAI ĐOẠN 3: Phát Triển Translator Service & LLM Adapter
- [ ] Thiết kế LLM Adapter (hỗ trợ OpenAI, Gemini, hoặc Custom/Local LLM).
- [ ] Tích hợp `tenacity` retry handler chống lỗi rate-limit / API drop.
- [ ] Viết `Translator Worker` đọc queue `CRAWLED` -> dịch -> cập nhật trạng thái `DONE`.

### 📌 GIAI ĐOẠN 4: Monitor Service & Anti-Memory Leak Safe Guard
- [ ] Viết `psutil` System Monitor theo dõi lượng RAM/CPU tiêu thụ.
- [ ] Tự động gửi tín hiệu điều tiết (auto-throttle / pause) số lượng coroutines khi RAM > 80%.

### 📌 GIAI ĐOẠN 5: Exporter & Management API (FastAPI)
- [ ] Xây dựng FastAPI Admin endpoints (thêm truyện, kích hoạt crawl/dịch, xem progress).
- [ ] Viết Exporter xuất dữ liệu ra file TXT / EPUB hoàn chỉnh.

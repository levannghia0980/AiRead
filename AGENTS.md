# AGENTS.MD - HƯỚNG DẪN QUẢN TRỊ & QUY TẮC DỰ ÁN AIREAD

## 1. QUY TẮC DỌN DẸP BỘ NHỚ & FILE AUDIO GỘP TRÙNG LẶP (STORAGE CLEANUP)

Khi người dùng yêu cầu:
- *"Xóa file rác"*, *"Dọn dẹp audio gộp"*, *"Xóa các file trùng lặp"*, *"Bộ nhớ đầy rồi dọn bớt đi"*, hoặc bất kỳ câu lệnh nhắc nhở dọn dẹp nào:

👉 **HÀNH ĐỘNG CẦN LÀM NGAY:**
1. Chạy công cụ tự động dọn dẹp đã được cấu hình sẵn:
   ```bash
   python tools/clean_export_audio.py
   ```
2. **Cơ chế hoạt động của `clean_export_audio.py`:**
   - **Vị trí quét:** Quét trực tiếp bên dưới các thư mục truyện trong `Output/05_Audio_TTS/<Tên Truyện>/`.
   - **Mục tiêu xóa:** Xóa tất cả các file MP3 xuất gộp nhiều tập (ví dụ: `*_Ch1_to_Ch70_1.5x.mp3`) và file timeline JSON đi kèm (`*_timeline.json`). Đây là các file sinh ra khi người dùng bấm "Ghép chương" trên Web UI để làm video YouTube, gây nhân đôi/nhân ba dung lượng.
   - **Xóa file rác phụ:** Quét thư mục `scratch/` để xóa các file `.bak`, `.tmp`, `.wav`, các file mp3 test mastering.
   - **NGHIÊM CẤM:** TUYỆT ĐỐI KHÔNG xóa các file trong thư mục con `chapters/` (như `000001.mp3`, `000002.mp3`...) và tuyệt đối không đụng vào `04_KetQua` (bản dịch văn bản chuẩn).

## 2. QUY TẮC DỊCH THUẬT & TTS
- **Mô hình dịch:** Dùng `gemini-3.5-flash-lite` làm việc mặc định.
- **Phong cách dịch:** Văn phong trung thực, chuẩn mực, đúng ngữ cảnh tác phẩm (Điều 5 trong `profiles.py`). TUYỆT ĐỐI CẤM từ lóng hiện đại, teen/gen Z và bắt trend lố bịch làm xuyên tạc nguyên tác. Xưng hô nhân vật đúng thể loại cổ trang/tiên hiệp/võ hiệp, cấm dùng đại từ hiện đại teen ("bọn em", "tụi em", "tụi mình").
- **TTS Audio Integrity:** Giữ nguyên kiểm tra độ toàn vẹn 100% từ vựng giữa file JSON subtitle và văn bản nguồn `04b_VanBanTTS`.

## 3. QUY TẮC ĐỒNG BỘ 3 INSTANCE SONG SONG (AIREAD, AIREAD_2, AIREAD_3)
- Người dùng chạy 3 bản song song tại các thư mục:
  - `d:\NENGHIA0980\AIREAD` (Bản 1)
  - `d:\NENGHIA0980\AIREAD_2` (Bản 2)
  - `d:\NENGHIA0980\AIREAD_3` (Bản 3)
- **MỆNH LỆNH CỨNG:** Bất kỳ khi nào có thay đổi code, logic prompt (`profiles.py`, `llm_translator.py`, v.v.) hoặc cấu hình ở bất kỳ bản nào, **BẮT BUỘC PHẢI TỰ ĐỘNG ĐỒNG BỘ MỚI NHẤT SANG CẢ 2 BẢN CÒN LẠI NGAY LẬP TỨC**. Không được để xảy ra tình trạng lệch code giữa 3 bản.

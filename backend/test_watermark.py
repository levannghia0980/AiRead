"""Quick test to verify watermark stripping works correctly."""
import sys
sys.path.insert(0, ".")

from backend.app.services.translator.text_processor import preprocess_chinese_text, _strip_translated_watermarks

# ============================================================
# TEST 1: Xóa watermark tiếng Trung (tiền xử lý)
# ============================================================
print("=" * 60)
print("TEST 1: Xóa watermark tiếng Trung (preprocess)")
print("=" * 60)

raw_chinese_with_watermark = """苏小小也飞了出来,抬头看着头顶的劫云瞪大了眼睛。

现在它即将成为中州渡劫竞技场。韩域晋升神道跑到了这里。今天,在被雷劈之后,他还在这里跑。

"不是做坏事,这是晋级劫云!"

木子李悄然出现,只看了一眼就露出沉思的表情。

这是从神台晋升到神道的劫云,他不会看错。

现在它即将成为中州渡劫竞技场。韩域晋升神道跑到了这里。今天,在被雷劈之后,他还在这里跑。

如果是普通的劫云,哪有时间给你反应。

现在它即将成为中州渡劫竞技场。韩域晋升神道跑到了这里。今天,在被雷劈之后,他还在这里跑。

"是谁要晋级?"

现在它即将成为中州渡劫竞技场。韩域晋升神道跑到了这里。今天,在被雷劈之后,他还在这里跑。
"""

cleaned = preprocess_chinese_text(raw_chinese_with_watermark)
print(f"Original lines: {len(raw_chinese_with_watermark.strip().split(chr(10)))}")
print(f"Cleaned lines:  {len(cleaned.strip().split(chr(10)))}")

watermark_sentence = "现在它即将成为中州渡劫竞技场"
if watermark_sentence in cleaned:
    print("❌ FAIL: Watermark still present!")
else:
    print("✅ PASS: Watermark successfully removed!")

print()
print("Cleaned text:")
print(cleaned[:500])

# ============================================================
# TEST 2: Xóa watermark bản dịch tiếng Việt (hậu xử lý)
# ============================================================
print()
print("=" * 60)
print("TEST 2: Xóa watermark bản dịch (postprocess)")
print("=" * 60)

translated_with_watermark = """Tô Tiểu Tiểu cũng bay ra ngoài, nhìn lên đỉnh đầu mà trợn mắt há hốc mồm chửi bới.

Bây giờ nó sắp trở thành Central Continent Crossing Robbery Arena. Han Yu được thăng chức lên Thần và chạy đến nơi này. Hôm nay, anh vẫn đang chạy ở đây sau khi bị sét đánh.

"Không phải chuyện thất đức, đây là kiếp vân thăng cấp!"

Mộc Tử Lý lặng lẽ xuất hiện, chỉ liếc mắt một cái đã lộ vẻ trầm tư nhìn về phía đáy biển.

Bây giờ nó sắp trở thành Central Continent Crossing Robbery Arena. Han Yu được thăng chức lên Thần và chạy đến nơi này. Hôm nay, anh vẫn đang chạy ở đây sau khi bị sét đánh.

Nếu là kiếp vân bình thường, làm gì có thời gian cho ngươi phản ứng.

Bây giờ nó sắp trở thành Central Continent Crossing Robbery Arena. Han Yu được thăng chức lên Thần và chạy đến nơi này. Hôm nay, anh vẫn đang chạy ở đây sau khi bị sét đánh.

"Là ai muốn thăng cấp?"

Bây giờ nó sắp trở thành Central Continent Crossing Robbery Arena. Han Yu được thăng chức lên Thần và chạy đến nơi này. Hôm nay, anh vẫn đang chạy ở đây sau khi bị sét đánh.
"""

cleaned_vi = _strip_translated_watermarks(translated_with_watermark)
print(f"Original lines: {len(translated_with_watermark.strip().split(chr(10)))}")
print(f"Cleaned lines:  {len(cleaned_vi.strip().split(chr(10)))}")

watermark_en = "Central Continent Crossing Robbery Arena"
if watermark_en in cleaned_vi:
    print("❌ FAIL: Watermark still present!")
else:
    print("✅ PASS: Watermark successfully removed!")

print()
print("Cleaned Vietnamese text:")
print(cleaned_vi[:500])

print()
print("🎉 ALL WATERMARK TESTS COMPLETED!")

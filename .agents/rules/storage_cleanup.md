# Storage Cleanup Rule

Whenever the user mentions:
- "dọn dẹp", "xóa file rác", "xóa file gộp", "dọn audio", "giải phóng dung lượng", "bộ nhớ đầy"
Run the cleanup script immediately:
```bash
python tools/clean_export_audio.py
```

This cleans:
- Merged batch export MP3 files and timeline JSONs directly under `Output/05_Audio_TTS/<Novel>/`
- Any leftover scratch tests or .bak files
- Never touches `Output/05_Audio_TTS/<Novel>/chapters/` (the individual chapter audios) or `Output/04_KetQua`.

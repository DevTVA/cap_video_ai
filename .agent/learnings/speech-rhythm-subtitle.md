# Speech-Rhythm Subtitle Engine

> Tổng hợp kiến thức về thuật toán ngắt nhịp phụ đề chuẩn theo giọng nói nhân vật và xử lý triệt để lỗi chớp nháy phụ đề.
> Cập nhật lần cuối: 2026-08-16

---

## Architecture

### Phân Cụm Phụ Đề Theo Nhịp Nói (Punctuation & Pause Detection)
- **Ngày**: 2026-07-30
- **Chi tiết**: Thay vì cắt cụm từ cố định (hardcoded 3-4 words), engine nhóm các từ thoại dựa trên dấu câu (`,`, `.`, `!`, `?`, `;`, `:`) và khoảng lặng tự nhiên giữa 2 từ thoại liên tiếp (`next_start - current_end > 0.22s`). Điều này giúp phụ đề tự nhiên, khớp hoàn toàn với nhịp hít thở và ngắt vế câu của thoại.
- **Files liên quan**: `batch_video_cutter/`

### Single Overlay Concat Manifest for PNG Subtitles
- **Ngày**: 2026-08-16
- **Chi tiết**: Thay vì lặp qua N ảnh PNG với N overlay filter tuần tự (gây quá tải CPU và giật/lag), sử dụng FFmpeg Concat Demuxer (`-f concat -safe 0 -i g_subs_concat.txt`) để nối toàn bộ PNG phụ đề karaoke thành 1 luồng video duy nhất kèm kênh `yuva420p` và hòa trộn qua 1 filter `overlay=0:0` duy nhất.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/utils/graphic_subtitle.py`

---

## Bugs & Solutions

### Phụ Đề Xuất Hiện Đè Ở Cuối Phần Outcard
- **Ngày**: 2026-08-16
- **Vấn đề**: Khung phụ đề cuối cùng bị lòi/hiển thị đè bên dưới thẻ Outcard 2.113s cuối video.
- **Root cause**: `generate_concat_manifest` ngắt manifest tại `outcard_start_s` làm FFmpeg overlay filter mặc định (lặp lại/freeze frame cuối) lặp khung phụ đề cuối đến hết video.
- **Fix**: Kéo dài manifest đến hết `clip_duration` với phần thời gian Outcard 100% sử dụng `blank_transparent.png`, dòng cuối cùng luôn là `blank_transparent.png`, và thêm `eof_action=pass` vào overlay filter.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/core/engine.py`

### Cắt Dính Đoạn Station Bumper / Intro Graphic / Promo Show
- **Ngày**: 2026-08-16
- **Vấn đề**: Clip bị cắt dính logo chương trình ("Divorce Court", "Judge Lynn Toler") hoặc nhạc bumper intro.
- **Root cause**: `is_segment_clean_and_valid()` trước đó chỉ gộp chuỗi `spoken_text` chung thay vì check từng dòng thoại lẻ rơi vào khoảng range.
- **Fix**: Mở rộng `INTRO_KEYWORDS` (thêm "divorce court", "courtroom", "music", "bumper", "station id", "applause") và kiểm tra từng dòng thoại trong range segment để loại bỏ triệt để.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`

---

## How-To

### Quy Trình Triển Khai Ngắt Nhịp Phụ Đề Chuẩn CapCut
- **Ngày**: 2026-07-30
- **Bước thực hiện**:
  1. Trích xuất danh sách từ kèm mốc thời gian chi tiết (`start`, `end`, `word`) từ engine ASR/Whisper.
  2. Nhóm từ vào một cụm (chunk) mới khi gặp dấu câu ngắt câu/vế hoặc khi phát hiện khoảng nghỉ giữa 2 từ `> 0.22s`.
  3. Đặt thời gian hiển thị khung phụ đề cố định từ `chunk_start` đến `chunk_end`.
  4. Hiệu ứng Karaoke: Highlight từ tương ứng với mốc thời gian playback hiện tại mà không làm thay đổi vị trí toàn cụm.
- **Files liên quan**: `batch_video_cutter/`

---

## Patterns

### Dynamic Beat Threshold & Concat Overlay Pattern
- **Ngày**: 2026-08-16
- **Chi tiết**: Kết hợp tính động `min_beat_duration` theo tốc độ nói (words_per_sec) và Concat Manifest Demuxer giúp karaoke highlight đuổi kịp giọng nói nhanh mà vẫn mượt mà 100% không chớp nháy.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/utils/graphic_subtitle.py`

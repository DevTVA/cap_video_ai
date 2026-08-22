# Speech-Rhythm Subtitle Engine

> Tổng hợp kiến thức về thuật toán ngắt nhịp phụ đề chuẩn theo giọng nói nhân vật, word-level alignment và vị trí/font size phụ đề đồ họa.
> Cập nhật lần cuối: 2026-08-22

---

## Architecture

### Phân Cụm Phụ Đề Theo Nhịp Nói (Punctuation & Pause Detection)
- **Ngày**: 2026-07-30
- **Chi tiết**: Thay vì cắt cụm từ cố định (hardcoded 3-4 words), engine nhóm các từ thoại dựa trên dấu câu (`,`, `.`, `!`, `?`, `;`, `:`) và khoảng lặng tự nhiên giữa 2 từ thoại liên tiếp (`next_start - current_end > 0.22s`). Điều này giúp phụ đề tự nhiên, khớp hoàn toàn với nhịp hít thở và ngắt vế câu của thoại.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/utils/subtitle.py`

### Single Overlay Concat Manifest for PNG Subtitles
- **Ngày**: 2026-08-16
- **Chi tiết**: Thay vì lặp qua N ảnh PNG với N overlay filter tuần tự (gây quá tải CPU và giật/lag), sử dụng FFmpeg Concat Demuxer (`-f concat -safe 0 -i g_subs_concat.txt`) để nối toàn bộ PNG phụ đề karaoke thành 1 luồng video duy nhất kèm kênh `yuva420p` và hòa trộn qua 1 filter `overlay=0:0` duy nhất.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Forced Whisper Audio Alignment cho Existing Subtitles (SRT/Txt)
- **Ngày**: 2026-08-22
- **Chi tiết**: Khi nạp phụ đề SRT/txt có sẵn chỉ chứa sentence-level timestamp (`words=[]`), hệ thống tự động gọi Whisper audio stream alignment (`align_existing_subtitles_with_whisper`) để trích xuất `words` (word-level timestamp) thực tế từ audio gốc mà không làm mất cấu trúc câu SRT.
- **Files liên quan**: `batch_video_cutter/core/transcriber.py`

---

## Bugs & Solutions

### Lệch Tốc Độ Thoại Phụ Đề Do Nạp SRT Có Sẵn (Empty Words Fallback)
- **Ngày**: 2026-08-22
- **Vấn đề**: Phụ đề dạng karaoke/highlight bị lệch nhịp, trượt khỏi tốc độ thoại thật của nhân vật khi dùng file SRT có sẵn.
- **Root cause**: Nạp SRT khiến `SentenceSegment.words` bị rỗng (`[]`), dẫn đến kích hoạt fallback chia đều thô sơ `duration_per_word = (relative_end - relative_start) / len(raw_words)`.
- **Fix**: Thực hiện alignment word timestamp từ audio bằng Whisper cho SRT. Nếu không align được, thay chia đều thô sơ bằng thuật toán **Char-Weighted + Punctuation Pause Alignment** (phân bổ thời lượng theo `len(word)` và trọng số dấu câu ngắt vế).
- **Files liên quan**: `batch_video_cutter/core/transcriber.py`, `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Phụ Đề Style 5 Bị To VÀ Chênh Cao Lên Giữa Màn Hình
- **Ngày**: 2026-08-22
- **Vấn đề**: Phụ đề Style 5 bị lơ lửng ở 70% chiều cao màn hình (`y = 814px`) và cỡ chữ bị to.
- **Root cause**: `margin_v` bị hardcode 180px cho Canvas 1:1 (`1080x1080`) đẩy phụ đề lên cách đáy 266px; font size 66pt kèm viền 14px + Emoji 3D 68px làm khối phụ đề quá to.
- **Fix**: Thêm `get_margin_v()` vào `BaseStyle` và override `get_margin_v() -> 100` cho Style 5 (hạ phụ đề cách đáy ~130px), điều chỉnh `get_font_size() -> 54` cho thanh thoát.
- **Files liên quan**: `batch_video_cutter/styles/base.py`, `batch_video_cutter/styles/style_5.py`, `batch_video_cutter/pipeline.py`, `batch_video_cutter/utils/subtitle.py`

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
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

---

## Patterns

### Char-Weighted Word Duration Allocation Pattern
- **Ngày**: 2026-08-22
- **Chi tiết**: Tính toán thời lượng từ trong câu không có word-level timestamp dựa trên tổng điểm số ký tự `len(clean_word)` cộng thưởng dấu câu (`,`, `;`, `:`) +1.5, (`.`, `!`, `?`) +2.5. Giúp từ ngắn (`a`, `in`) lướt nhanh, từ dài (`extraordinary`) và khoảng ngắt nghỉ kéo dài tự nhiên như giọng nói thực.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Dynamic Beat Threshold & Concat Overlay Pattern
- **Ngày**: 2026-08-16
- **Chi tiết**: Kết hợp tính động `min_beat_duration` theo tốc độ nói (words_per_sec) và Concat Manifest Demuxer giúp karaoke highlight đuổi kịp giọng nói nhanh mà vẫn mượt mà 100% không chớp nháy.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/utils/graphic_subtitle.py`

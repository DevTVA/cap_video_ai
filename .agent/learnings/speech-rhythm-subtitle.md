# Speech-Rhythm Subtitle Engine

> Tổng hợp kiến thức về thuật toán ngắt nhịp phụ đề chuẩn theo giọng nói nhân vật, word-level alignment, SubtitleLayoutEngine và vị trí/font size phụ đề đồ họa.
> Cập nhật lần cuối: 2026-08-22

---

## Architecture

### Unified SubtitleLayoutEngine & Pixel-Aware Font Line Wrapping
- **Ngày**: 2026-08-22
- **Chi tiết**: Xây dựng `SubtitleLayoutEngine` làm Single Source of Truth cho cả ASS Subtitle generator và PNG Graphic Subtitle generator. Đo độ rộng dòng chữ bằng font pixel thực tế (`font.getbbox()`) từ `assets/fonts/`. Khi cụm từ vượt `max_width_px` (880px), thuật toán tìm điểm ngắt $k$ tối ưu sao cho $\min(|\text{width}(\text{line}_1) - \text{width}(\text{line}_2)|)$ (ưu tiên ngắt sau dấu câu). Giữ nguyên 100% mốc từ `(word, start, end)` gốc.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Clip Offset Clamping & Timestamp Invariants
- **Ngày**: 2026-08-22
- **Chi tiết**: Phụ đề trong từng clip cắt nhỏ luôn sử dụng thời gian tương đối `relative_start = max(0.0, word.start - clip_start)` và `relative_end = min(clip_duration, word.end - clip_start)`. Đảm bảo invariant nghiêm ngặt $0.0 \le \text{start} < \text{end} \le \text{clip\_duration}$. Các từ ngoài ranh giới clip bị loại bỏ an toàn.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`

### Phân Cụm Phụ Đề Theo Nhịp Nói (Punctuation & Pause Detection)
- **Ngày**: 2026-07-30
- **Chi tiết**: Thay vì cắt cụm từ cố định (hardcoded 3-4 words), engine nhóm các từ thoại dựa trên dấu câu (`,`, `.`, `!`, `?`, `;`, `:`) và khoảng lặng tự nhiên giữa 2 từ thoại liên tiếp (`next_start - current_end > 0.35s`). Điều này giúp phụ đề tự nhiên, khớp hoàn toàn với nhịp hít thở và ngắt vế câu của thoại.
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

### Bất Đồng Bộ Layout Giữa ASS Generator và PNG Graphic Subtitle Generator
- **Ngày**: 2026-08-22
- **Vấn đề**: ASS subtitle ngắt cứng 4 từ/cụm và chia đôi `len/2`; PNG graphic subtitle ngắt theo 6 từ / 24 chars. Khiến layout phụ đề bị khác nhau tùy theo chế độ render.
- **Root cause**: Thiếu `SubtitleLayoutEngine` dùng chung giữa hai module render.
- **Fix**: Centralize logic ngắt dòng trong `SubtitleLayoutEngine.layout_subtitle_line()`, ép cả ASS generator và PNG graphic generator dùng chung 100% layout chunks và line splits.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Hardcoded Windows Font Path & Silent Font Measurement Fallback
- **Ngày**: 2026-08-22
- **Vấn đề**: Code hardcode đường dẫn font `C:/Windows/Fonts/impact.ttf` hoặc `arialbd.ttf`, gây fallback ngầm sang PIL default font trên Linux/macOS hoặc máy Windows thiếu font, làm hỏng đo đạc độ rộng pixel.
- **Root cause**: Phụ thuộc font hệ thống thay vì font đóng gói trong repository.
- **Fix**: Tập trung nạp font qua `SubtitleLayoutEngine.get_font()`, ưu tiên tuyệt đối các font TTF trong `assets/fonts/` (`Montserrat-Bold.ttf`, `LuckiestGuy-Regular.ttf`, `Fredoka-Bold.ttf`) và dùng cùng một font instance cho cả measurement và rendering.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Lọc Từ Khóa Intro Quá Tay (Over-aggressive Intro Keyword Hard-banning)
- **Ngày**: 2026-08-22
- **Vấn đề**: Các câu thoại hợp lệ chứa từ đơn như `judge`, `host`, `courtroom`, `facebook` bị hệ thống reject nhầm là intro/promo.
- **Root cause**: Khai báo các từ đơn trong `INTRO_KEYWORDS`.
- **Fix**: Loại bỏ các từ đơn khỏi `INTRO_KEYWORDS`, chỉ giữ lại các cụm từ giới thiệu show thực sự (`welcome back`, `thanks for watching`, `sponsored by`), bảo vệ thoại tòa án và host.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`

### Lệch Tốc Độ Thoại Phụ Đề Do Nạp SRT Có Sẵn (Empty Words Fallback)
- **Ngày**: 2026-08-22
- **Vấn đề**: Phụ đề dạng karaoke/highlight bị lệch nhịp, trượt khỏi tốc độ thoại thật của nhân vật khi dùng file SRT có sẵn.
- **Root cause**: Nạp SRT khiến `SentenceSegment.words` bị rỗng (`[]`), dẫn đến kích hoạt fallback chia đều thô sơ.
- **Fix**: Thực hiện alignment word timestamp từ audio bằng Whisper cho SRT. Nếu không align được, gắn nhãn `timestamp_source = "fallback"` và dùng thuật toán **Char-Weighted + Punctuation Pause Alignment**.
- **Files liên quan**: `batch_video_cutter/core/transcriber.py`, `batch_video_cutter/utils/subtitle.py`

---

## How-To

### Quy Trình Triển Khai Ngắt Nhịp Phụ Đề Chuẩn CapCut
- **Ngày**: 2026-08-22
- **Bước thực hiện**:
  1. Trích xuất danh sách từ kèm mốc thời gian chi tiết (`start`, `end`, `word`) từ engine ASR/Whisper.
  2. Nạp font chỉ định từ `assets/fonts/` qua `SubtitleLayoutEngine.get_font()`.
  3. Gọi `SubtitleLayoutEngine.layout_subtitle_line()` để gom chunk theo dấu câu/pause và tách 2 dòng cân bằng pixel width.
  4. Hiệu ứng Karaoke: Highlight từ tương ứng với mốc thời gian `w_start <= t < w_end` mà không làm thay đổi timing hoặc layout.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

---

## Patterns

### Deterministic Hash-Based Emoji Hashing Pattern
- **Ngày**: 2026-08-22
- **Chi tiết**: Lựa chọn Emoji theo Keyword Map hoặc Deterministic MD5 Hash (`int(hashlib.md5(text.encode()).hexdigest(), 16)`). Đảm bảo 100% trùng khớp kết quả giữa các lần re-run mà không dùng `random.choice`.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Char-Weighted Word Duration Allocation Pattern
- **Ngày**: 2026-08-22
- **Chi tiết**: Tính toán thời lượng từ trong câu không có word-level timestamp dựa trên tổng điểm số ký tự `len(clean_word)` cộng thưởng dấu câu (`,`, `;`, `:`) +1.5, (`.`, `!`, `?`) +2.5. Giúp từ ngắn (`a`, `in`) lướt nhanh, từ dài (`extraordinary`) và khoảng ngắt nghỉ kéo dài tự nhiên như giọng nói thực.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`

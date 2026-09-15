# Speech-Rhythm Subtitle Engine

> Tổng hợp kiến thức về thuật toán ngắt nhịp phụ đề chuẩn theo giọng nói nhân vật, word-level alignment, SubtitleLayoutEngine và vị trí/font size phụ đề đồ họa.
> Cập nhật lần cuối: 2026-09-13

---

## Architecture

### Phase 1 Canonical Word Timing Model & Timestamp Normalization
- **Ngày**: 2026-08-22
- **Chi tiết**: Khai báo `TimingSource` Enum (`WHISPER`, `SRT`, `FALLBACK`) và chuẩn hóa `WordTiming` làm canonical model. Áp dụng quy tắc bất biến $0.0 \le \text{start} < \text{end}$, lọc bỏ `NaN`/`Inf`/text rỗng, sắp xếp monotonic theo thời gian audio, dời `start = prev_end` khi overlap và đảm bảo `end > start` ($end = start + min\_dur$). Tách riêng hàm `fallback_estimate_word_timings` với nhãn `source="fallback"`, tuyệt đối không đè lên mốc thời gian Whisper gốc.
- **Files liên quan**: `batch_video_cutter/utils/word_timing.py`, `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/core/transcriber.py`, `tests/test_word_timing_normalization.py`

### Unified SubtitleChunker & 4-Tier Deterministic Emoji Hierarchy
- **Ngày**: 2026-08-22
- **Chi tiết**: Xây dựng `SubtitleChunker` làm **Single Source of Truth** duy nhất cho cả ASS Subtitle Generator và PNG Graphic Subtitle Generator. Bảo toàn 100% mốc `(start, end)` gốc của Whisper (`timing_source == "whisper"`). Áp dụng quy trình chọn Emoji màu sắc theo 4 tầng ưu tiên giảm dần (1. Semantic Emoji -> 2. Keyword Match -> 3. Emotion/Punctuation -> 4. Fallback Deterministic MD5 Hash), đảm bảo 100% nhất quán qua mọi lần chạy.
- **Files liên quan**: `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/utils/graphic_subtitle.py`, `tests/test_subtitle_timing_layout.py`

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

### Chuẩn Hóa Phụ Đề Toàn Hệ Thống (Standardized Subtitle Styles & Safe Zone)
- **Ngày**: 2026-09-13
- **Chi tiết**: Thống nhất font chữ `Impact` kích cỡ `66pt` và màu highlight `yellow` (`#FFE600`) cho tất cả Style. Chuẩn hóa khoảng cách lề dưới (`get_margin_v()`) tự động cân đối theo chiều cao Canvas để nằm trọn trong Safe Zone của TikTok/Reels/Shorts: Canvas 1:1 (`h <= 1080`): `110px`; Canvas 3:4 (`h == 1440`): `160px`; Canvas 9:16 (`h >= 1920`): `330px`, tránh bị che bởi thanh công cụ UI của mạng xã hội.
- **Files liên quan**: `batch_video_cutter/styles/base.py`, `batch_video_cutter/styles/style_*.py`, `tests/test_standardized_subtitle_styles.py`

### Kiến Trúc Style 6 - 9:16 Full Vertical Viral Shorts (TikTok / Reels)
- **Ngày**: 2026-09-13
- **Chi tiết**: Bổ sung `Style6` xuất video 1080x1920 (9:16) chuẩn dọc toàn màn hình điện thoại. Áp dụng hiệu ứng nền mờ (Background BoxBlur): tối ưu hiệu năng render bằng cách crop và scale thu nhỏ `scale=270:480` trước khi chạy `boxblur=15:2`, sau đó mới scale phóng to `1080:1920` ghép với foreground căn giữa. Bỏ qua 3.0s intro và 25.0s outro, cắt tối đa 3 clips viral.
- **Files liên quan**: `batch_video_cutter/styles/style_6.py`, `batch_video_cutter/styles/factory.py`, `batch_video_cutter/styles/__init__.py`

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

### Lọc YouTube Auto-Captions Thô Cắt Vụn Gây Chớp Tắt Phụ Đề
- **Ngày**: 2026-09-13
- **Vấn đề**: Khi nạp file `subtitles.txt` tải từ YouTube auto-captions, các câu bị cắt vụn 1-2 từ và không có dấu chấm phẩy, gây chớp tắt phụ đề liên tục và lệch nhịp đọc.
- **Root cause**: Hệ thống nạp trực tiếp file `subtitles.txt` có sẵn mà không đánh giá chất lượng dấu câu (punctuation).
- **Fix**: Trong `try_parse_existing_subtitles()`, kiểm tra tỷ lệ kết thúc câu bằng dấu chấm/than/hỏi (`.`, `!`, `?`). Nếu `punct_ratio < 0.20` (< 20%), tự động phát hiện là auto-transcript thô, ghi log cảnh báo và bỏ qua file để Whisper bóc băng trực tiếp từ audio với cấu trúc câu cú hoàn chỉnh.
- **Files liên quan**: `batch_video_cutter/core/transcriber.py`, `tests/test_transcriber_upgrades.py`

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

### Chỉ Định File Phụ Đề Tùy Chỉnh Từ Ngoài (--external-subtitle-file)
- **Ngày**: 2026-09-13
- **Bước thực hiện**:
  1. Thêm cờ CLI `--external-subtitle-file` (hoặc `-sub`) trỏ đến file `.srt` hoặc `.txt`.
  2. Transcriber bỏ qua transcript cache, nạp trực tiếp file phụ đề chỉ định.
  3. Tự động chạy Whisper audio alignment để có word-level timestamps chính xác từ audio gốc, kết hợp gối đầu liền kề triệt tiêu giật lắc.
- **Files liên quan**: `batch_video_cutter/ui/cli.py`, `batch_video_cutter/core/transcriber.py`, `tests/test_external_subtitle_file.py`

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

### Chế Độ Căn Chỉnh Phụ Đề 3 Tầng (auto/fast/deep) & Gắn Nhãn Nguồn
- **Ngày**: 2026-09-06 (Cập nhật: 2026-09-07)
- **Chi tiết**: Phân tách rõ 3 chế độ qua cờ `--subtitle-align [auto|fast|deep]`:
  1. `auto` (Mặc định - Quality & Frame-Accurate First): Khi có SRT/txt, tự động chạy Whisper audio stream alignment để có mốc từ chính xác từng mili-giây khớp 100% với giọng nói nhân vật. Nếu không có SRT, tự động bóc băng bằng Whisper. Tuyệt đối không dùng ước lượng Char-Weighted làm mặc định vì sẽ làm trượt nhịp giọng nói.
  2. `fast`: Bắt buộc dùng Char-Weighted Alignment (<0.01s) cho SRT, tuyệt đối không gọi Whisper (chỉ dùng khi người dùng chủ động yêu cầu tốc độ tối đa).
  3. `deep`: Bắt buộc chạy Whisper audio stream alignment cho SRT/txt.
  - **Bảo vệ Cache & Metadata**: Gán nhãn `timing_source = "estimated"` khi dùng Char-Weighted và `timing_source = "whisper"` khi dùng Whisper thật. Khi chạy ở chế độ `auto` hoặc `deep`, nếu phát hiện cache là `estimated` thì tự động bỏ qua cache ước lượng để chạy Whisper align thật.
- **Files liên quan**: `batch_video_cutter/core/transcriber.py`, `batch_video_cutter/ui/cli.py`, `batch_video_cutter/config.py`

### Multi-Factor Cache Manager & Sweet Spot Concurrency
- **Ngày**: 2026-09-06
- **Chi tiết**: 
  1. **Cache đa yếu tố**: Lưu transcript tại `.cache/transcripts/<hash>.json` và alignment tại `.cache/alignments/<hash>.json` với key SHA-256 từ `(mtime, size, model, lang, version)`. Bỏ qua bóc băng ở các lần chạy sau.
  2. **Global Concurrency Sweet Spot**: Benchmark thực nghiệm chứng minh `TOTAL_RENDER_WORKERS = 2` trên GPU AMD AMF (`h264_amf`) cho thông lượng tối ưu nhất (7.39s/s), tránh nghẽn GPU bus và tràn VRAM khi tăng lên 4 workers.
  3. **PNG I/O Speedup**: Sử dụng `compress_level=1` khi ghi ảnh tạm PNG, giảm 65% thời gian I/O đĩa (từ 1.25s xuống 0.44s cho 80 frame).
  4. **Always Fresh Rendering (Disable Cache & Skip by Default)**: Người dùng thực tế chỉ cắt mỗi folder một lần; nếu cắt lại lần 2 tức là do lần đầu có lỗi hoặc muốn thay đổi. Vì vậy, hệ thống đã loại bỏ hoàn toàn cơ chế Smart Skip và mặc định `force_rerender=True`, `use_cache=False` (cờ CLI `--force` và `--no-cache` mặc định). Đảm bảo mỗi lần chạy là một phiên bản làm mới hoàn toàn, không nạp lại file rác hoặc video cũ.
- **Files liên quan**: `batch_video_cutter/core/cache_manager.py`, `batch_video_cutter/core/telemetry.py`, `batch_video_cutter/pipeline.py`

### Subtitle Timing & Container PTS Zeroing (0.0s Real-Time Baseline)
- **Ngày**: 2026-09-11
- **Chi tiết**: 
  1. **Container PTS Hard-Sync**: Khi FFmpeg video stream (`setpts=PTS-STARTPTS,fps=30`), audio stream (`asetpts=PTS-STARTPTS`) và subtitle PNG stream (`setpts=PTS-STARTPTS,fps=30`) kết hợp `-avoid_negative_ts make_zero` được hard-sync tuyệt đối tại `0.000s`, mốc thời gian Whisper gốc đã **khớp 1:1 theo thời gian thực** với tiếng nói nhân vật.
  2. **Tránh Over-compensation**: Sau khi đã hard-sync PTS, nếu đặt offset âm quá lớn (-0.22s) sẽ đẩy phụ đề chạy trước lời nói ~7 frames. Vì vậy, mốc mặc định chuẩn thời gian thực là `SUBTITLE_TIME_OFFSET = 0.0s`.
  3. **CLI Flexibility**: Cung cấp cờ `--subtitle-offset [float]` (mặc định `0.0`) để người dùng có thể tinh chỉnh theo ý muốn (ví dụ `-0.05` nếu muốn hiện sớm 1-2 frame, hoặc `+0.05` nếu muốn chậm lại một chút).
- **Files liên quan**: `batch_video_cutter/config.py`, `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/core/engine.py`, `batch_video_cutter/ui/cli.py`

### Static Pill Box & Seamless Continuity (Zero-Flicker Subtitles)
- **Ngày**: 2026-09-11
- **Chi tiết**: 
  1. **Triệt tiêu hiện tượng co giãn giật cục của Pill Box**: Hộp nền đen mờ được tính kích thước cố định theo **toàn bộ các từ trong cụm** (`words`), không bị giật dài ra theo từng từ. Các từ xuất hiện theo cơ chế Word-by-Word Reveal: từ đang nói sáng rực màu highlight (Vàng neon `#FFE600`), các từ đã nói màu trắng tinh viền đen. Hộp đen đứng yên 100%, êm dịu hoàn toàn (Zero Jitter).
  2. **Gối đầu liền kề triệt tiêu chớp tắt (< 1.8s)**: Nâng ngưỡng gối đầu liền kề lên `1.8s` (Seamless Continuity). Bất kỳ khoảng nghỉ nói chuyện tự nhiên nào $< 1.8s$ giữa 2 câu liên tiếp sẽ giữ câu trước hiển thị cho đến đúng khi câu sau bắt đầu (`e = next_s`). Triệt tiêu 100% hiện tượng phụ đề tắt ngúm rồi bật lại gây chớp mắt. Với khoảng lặng dài ($> 1.8s$), giữ câu thêm 0.6s để người xem đọc trọn vẹn, không ngắt đột ngột.
  3. **Bỏ hoàn toàn Icon/Emoji**: Toàn bộ hệ thống không chèn hay vẽ bất kỳ emoji/icon nào lên phụ đề (cả ASS và Graphic Subtitle).
  4. **Bỏ Hộp Nền Đen Đằng Sau Chữ & Tối Ưu Viền Stroke Đậm**: Đặt `enable_pill_box = False` làm mặc định, loại bỏ hoàn toàn mảng hộp đen mờ che đằng sau chữ. Đồng thời tăng cường độ dày viền đen (`stroke_w = max(10, int(12 * (font_size / 66.0)))` ở canvas 2x, tương đương 5-6px ở 1x), giúp chữ trắng tinh và từ active màu vàng neon nổi bật rõ ràng, sắc nét trên mọi nền video mà không bị lóa và không che khuất khung hình video.
  5. **Bug Mất Phụ Đề Khi Tắt Emoji & Cách Khắc Phục**: Trước đây `generate_ass_subtitle` có nhánh `if emoji_on_top: return generate_graphic_subtitles(...)`. Khi tắt emoji (`add_emojis = False` -> `emoji_on_top = False`), hệ thống rẽ nhánh sang sinh file `.ass` thô và trả về `timed_emojis = []`. Sau đó style có Top Caption Badge nhét ảnh caption vào `timed_emojis`, khiến `engine.py` nhận diện `if timed_emojis: sub_str = None`, vô tình tắt luôn file `.ass` làm mất 100% phụ đề! Giải pháp: `generate_ass_subtitle` **LUÔN LUÔN** gọi `generate_graphic_subtitles(..., emoji_on_top=emoji_on_top)` để dù có emoji hay không thì phụ đề luôn là Graphic Subtitle Pillow chất lượng cao. Đồng thời trong `engine.py`, chỉ tắt `sub_str` khi thực sự đã có `has_karaoke_png`.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/utils/subtitle.py`, `batch_video_cutter/core/engine.py`, `batch_video_cutter/pipeline.py`

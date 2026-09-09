# Video Subtitle & Outcard Processing

> Tổng hợp kiến thức về hệ thống Phụ đề đồ họa Graphic Subtitle Layer, Emoji màu, Top Caption Badge, Phong cách 5 (Blue Header), tăng âm lượng 1.3x, Quy trình lọc 6 lớp clip và Outcard overlay trong dự án.
> Cập nhật lần cuối: 2026-09-06

---

## Architecture

### Graphic Subtitle Layer bằng Pillow & Commit 1 Restore
- **Ngày**: 2026-07-27
- **Chi tiết**: Phụ đề chữ (kèm 3 màu active word highlight, viền đen mập 8px 2-pass solid stroke) và ảnh HD 3D Color PNG Emoji được render trực tiếp lên **1 tấm ảnh PNG trong suốt (RGBA)** cho mỗi mốc thoại. Đã khôi phục chuẩn bản Commit 1 với `chunk_size = 4`, tự động chia 2 dòng căn giữa giúp phụ đề rõ ràng, đẹp mắt và đúng nguyên bản.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/utils/subtitle.py`

### Top Caption Layout Engine: Bỏ "", Bảo toàn 100% Từ, Soft Constraint (w1 < w2) & Binary Search Font Size
- **Ngày**: 2026-09-03
- **Chi tiết**: Nâng cấp toàn diện Top Caption Engine trong `graphic_subtitle.py`:
  1. **Loại bỏ hoàn toàn dấu ngoặc kép `""`** trong text render trên video ở mọi Style (Style 3, 4, 5).
  2. **Bảo toàn 100% số từ**: Xóa bỏ hoàn toàn việc cắt từ cứng `words[:target_max]` và bỏ deduplicate từ lặp (giữ nguyên cấu trúc tự nhiên như "very very", "had had").
  3. **Soft Constraint Inverted Pyramid ($w_1 < w_2$) với Fallback 2 tầng**: Ưu tiên ngắt 2 dòng có dòng trên ngắn hơn dòng dưới ($w_1 < w_2$) và tỷ lệ tiệm cận $0.88$. Nếu câu có từ bất đối xứng không thể tạo $w_1 < w_2$ (như "Congratulations, bro!"), tự động fallback sang cách chia $w_1 \ge w_2$ cân bằng nhất, đảm bảo text luôn hiển thị đầy đủ và không bao giờ crash.
  4. **Tối ưu hóa hiệu năng bằng Tìm kiếm nhị phân (Binary Search)**: Dò Font Size trong dải `[16, 46]` chỉ trong 4-5 bước đo đạc ($O(\log M)$) kèm tầng Auto-scale co nhỏ font cho các siêu từ không khoảng trắng hoặc câu dài 30 từ.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `tests/test_top_caption_layout.py`

### Phong cách 5 (Style 5 - Canvas 3:4 Blue Header White Title)
- **Ngày**: 2026-08-09
- **Chi tiết**: Phong cách 5 kế thừa khung hình Canvas 3:4 (`1080x1440`), Video Zoom 150% CapCut style và phụ đề Impact highlight màu vàng từ Phong cách 4. Điểm khác biệt là Top Caption có **Dải nền Xanh Dương (`RGB 85, 118, 251` / `#5576FB`)** chiều cao 280px, tiêu đề Montserrat-Bold chữ **TRẮNG** in hoa căn giữa 2 dòng cân đối (không dùng White Badge bo góc và không có dấu nháy kép).
- **Files liên quan**: `batch_video_cutter/styles/style_5.py`, `batch_video_cutter/styles/factory.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Phân Tách Định Dạng Caption 100% Tiếng Anh Giữa Video và File Summary
- **Ngày**: 2026-08-01
- **Chi tiết**: Tiêu đề caption trong toàn bộ hệ thống BẮT BUỘC 100% là Tiếng Anh (`title_en`). Quy định định dạng:
  1. **Trên Video Frame (Top Caption PNG)**: Chữ Tiếng Anh in hoa (`UPPERCASE`), font Montserrat-Bold, không dính emoji trong khung ảnh.
  2. **Trong File Tổng Hợp (`all_clip_titles.txt`)**: Chữ Tiếng Anh ở dạng viết hoa chữ cái đầu câu (Sentence Case), kèm Emoji nổi bật nằm ở vị trí CUỐI CÙNG của chuỗi.
- **Files liên quan**: `batch_video_cutter/pipeline.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Single-Pass FFmpeg Pipeline & Đóng Gói Thành Phẩm
- **Ngày**: 2026-07-27
- **Chi tiết**: Gộp toàn bộ quá trình cắt clip, zoom video 150% (không mất cằm/đầu), nạp lớp phụ đề đồ họa, tăng âm 1.3x và hòa trộn `outcard.mp4` vào một câu lệnh FFmpeg duy nhất. Đóng gói clip thành phẩm vào thư mục phiên làm việc `final_clips/batch_export_YYYYMMDD_HHMMSS/` với tên clip chuẩn dạng `{folder_name}.{clip_idx}.mp4` (Ví dụ: `25.1.mp4`, `25.2.mp4`) giống 100% Phong cách 1 & 2.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/pipeline.py`

### Bộ Lọc Hybrid 2 Lớp Chống Dính Giới Thiệu Show & MC Monologue (Style 3, 4, 5)
- **Ngày**: 2026-08-23
- **Chi tiết**: Kết hợp 2 lớp lọc loại bỏ triệt để các phân đoạn thoại dẫn nhập show, chào mừng MC, court show intros ("All rise for the honorable judge...", "Court is now in session..."), station break hoặc sponsor monologue:
  1. Lớp Local Pre-Filter: Mở rộng `INTRO_KEYWORDS`, phạt điểm `score_dialogue_quality()` (-10.0), tự động gắn nhãn `[SHOW INTRO - DO NOT SELECT]` vào transcript text và lọc bỏ các segment candidate có 10s thoại mở đầu dính intro line.
  2. Lớp LLM Prompt Requirement: Ép cứng điều kiện cấm ngắt các mốc timecode chứa lời chào/dẫn show trong `scipt.txt` và `DEFAULT_PROMPT_TEMPLATE`.
  3. Quản lý Mốc Intro/Outro Theo Style: Style 1 & 2 bỏ 3s đầu, 30s cuối; Style 3, 4, 5 bỏ 35s đầu, 25s cuối.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/core/transcriber.py`, `scipt.txt`, `tests/test_intro_filtering.py`

### Quy Trình Lọc 6 Lớp & Biến Động Số Lượng Clip Thành Phẩm per Folder
- **Ngày**: 2026-08-28
- **Chi tiết**: Số lượng clip xuất ra biến động (1 đến 3 clip/folder) do `analyzer.py` và `pipeline.py` áp dụng 6 lớp kiểm duyệt chất lượng nghiêm ngặt: (1) Bỏ intro 35s / outro 25s; (2) Duration 25s-29s & snap ranh giới câu thoại; (3) Anti-Overlap không trùng lặp thời gian; (4) Local pre-filter chống dính MC intro/monologue; (5) Validation tiêu đề 8-10 từ Tiếng Anh độc bản kèm emoji; (6) Giới hạn max clip theo Style. Hệ thống thà xuất 1 clip chất lượng thay vì giữ lại candidate lỗi.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/pipeline.py`

### First 3-Second Hook & Đa Thể Loại Prompt (Review Shows & Courtroom)
- **Ngày**: 2026-09-06
- **Chi tiết**: Nâng cấp `scipt.txt` và `DEFAULT_PROMPT_TEMPLATE` với quy tắc bắt buộc "Hook 3 giây đầu" (`FIRST 3-SECOND HOOK MANDATE`), cấm bắt đầu clip bằng từ đệm ậm ừ ('um', 'well', 'so'), khoảng lặng hoặc câu chuyển mờ nhạt. Mở rộng hỗ trợ Show Review (phim, xe, công nghệ, ẩm thực): cho phép chọn các đoạn bình luận sắc bén, bóc mẽ hoặc tranh cãi gay gắt của reviewer, trong khi các show courtroom/drama vẫn bắt buộc đối thoại trực tiếp 2 người trở lên. Vẫn duy trì lệnh cấm tuyệt đối intro mở đầu kênh, chào hỏi, kêu gọi like/sub.
- **Files liên quan**: `scipt.txt`, `.agent/scipt.txt`, `batch_video_cutter/core/analyzer.py`

---

## Bugs & Solutions

### Bỏ Quên Outcard & Âm Lượng Do Sai Đường Dẫn Tự Động Tìm File Outcard.mp4
- **Ngày**: 2026-08-09
- **Vấn đề**: Video xuất ra bị thiếu Outcard đè ở 2.113s cuối clip và âm lượng thoại không được tăng 1.3x.
- **Root cause**: `engine.py` và `pipeline.py` trước đây chỉ quét tìm `outcard.mp4` tại đường dẫn hardcode `e:\AI_Agent\outcard.mp4`, trong khi file thực tế nằm ở `E:\cap_video\outcard.mp4`. Kết quả là `outcard_path` bị `None` nên FFmpeg bỏ qua filter overlay outcard.
- **Fix**: Mở rộng danh sách ứng viên quét tự động `outcard.mp4` (`E:\cap_video\outcard.mp4`, `E:\output\outcard.mp4`, `input_dir/outcard.mp4`, v.v.) trong `PipelineOrchestrator` và `engine.py`. Đồng thời bổ sung công thức căn giữa Outcard overlay theo chiều dọc canvas (`overlay=x=0:y=180` trên Canvas 3:4 `1080x1440`).
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/pipeline.py`

### Emoji Nằm Sai Vị Trí Ở Đầu/Giữa Câu Caption
- **Ngày**: 2026-08-01
- **Vấn đề**: Emoji bị nằm lộn xộn ở đầu hoặc giữa chuỗi caption (ví dụ `"sister's 🤯 shocking truth revealed"`).
- **Root cause**: `ensure_caption_has_emoji` cũ chỉ dùng `re.search` kiểm tra boolean sự tồn tại của emoji mà không bóc tách lại vị trí xuất hiện.
- **Fix**: Sử dụng `emoji_pattern.findall()` để trích xuất toàn bộ emoji, bóc tách emoji khỏi phần chữ body, làm sạch khoảng trắng, rồi mới ghép toàn bộ emoji xuống vị trí CUỐI CÙNG của câu caption.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Anti-Flicker Seamless Subtitle & Layout Freezing (CapCut Smooth)
- **Ngày**: 2026-07-30
- **Vấn đề**: Phụ đề bị chớp tắt lóe nháy và giật lệch vị trí ngang/dọc giữa các mốc active word.
- **Root cause**: 
  1. Trừ `-0.01s` trong `e = next_s - 0.01` tạo ra khe hở 10ms giữa 2 ảnh PNG overlay khiến FFmpeg không enable PNG nào ở frame đó (drop frame gây chớp nháy).
  2. Phóng to từ active (`font_2x_active` hoặc `\fscx118\fscy118`) làm độ rộng câu chữ bị thay đổi liên tục, làm dòng chữ rung lắc xô giật ngang/dọc.
- **Fix**: 
  1. Đổi `e = next_s` trong `graphic_subtitle.py` để các mốc PNG gối đầu liền kề 100% không khe hở.
  2. Đóng băng kích thước font size, stroke width và vị trí y của tất cả các từ trong cụm (từ active CHỈ đổi màu `fill=highlight_rgba`), loại bỏ `\fscx118\fscy118` trong ASS generator.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/utils/subtitle.py`

### Dính Từ Rác EXPOSED REVEALED & Lớp Cache Cũ Ở Top Caption
- **Ngày**: 2026-08-01
- **Vấn đề**: Tiêu đề Top Caption bị dán thêm các từ rác thô sơ như `"EXPOSED REVEALED TRUTH"` ở cuối câu (ví dụ: `"HOUSE SITTER DRINKS $2,000 WINE EXPOSED REVEALED"`).
- **Root cause**: 
  1. Đoạn code cũ trong `analyzer.py` tự động nối chuỗi `["EXPOSED", "REVEALED", "TRUTH"]` vào cuối tiêu đề ngắn thay vì sinh lại tiêu đề giật gân tự nhiên.
  2. Đọc file local cache cũ (`.cache/*.json`) giữ lại các tiêu đề cũ chứa từ rác mà không được làm sạch lại trước khi render.
  3. `clean_caption_text` chưa có bộ lọc chủ động xóa từ rác nối đuôi.
- **Fix**: 
  1. Chuyển logic sinh tiêu đề sang **vòng lặp `while True` kiểm tra `8 <= word_count <= 12`** trong `analyzer.py`. Vòng lặp re-prompt AI hoặc mở rộng ngữ cảnh tự nhiên ở đầu câu, chỉ thoát khi độ dài đạt 8-12 từ.
  2. Thêm regex lọc bỏ từ rác nối đuôi ở cuối chuỗi trong `clean_caption_text()` và `clean_caption_text_for_frame()`.
  3. Tự động sanitize và re-validate tiêu đề trong `_read_cache()` khi nạp cache từ đĩa.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/utils/graphic_subtitle.py`

---

## How-To

### Đo Đạc & Validate Top Caption Layout Shape Constraint
- **Ngày**: 2026-08-23
- **Bước thực hiện**:
  1. Gọi `format_top_caption_lines(words, font, max_text_w)`.
  2. Nhận kết quả `CaptionLayoutResult(lines, constraint_unmet, ratio, w1, w2)`.
  3. Kiểm tra `constraint_unmet` để phát hiện fallback layout và kiểm tra tỉ lệ `ratio = w1 / w2`.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `tests/test_top_caption_layout.py`

### Cấu Hình Range Mapping Phong Cách Cho Folder (Chuẩn 1-36:3, 37-42:4, 43-48:5)
- **Ngày**: 2026-09-06
- **Bước thực hiện**:
  1. Khai báo chuỗi mapping phong cách trong `style_mapping_str` của `config.py` (`1-36:3,37-42:4,43-48:5`): Folders 1-36 (Style 3 Canvas 1:1 dải vàng), 37-42 (Style 4 Canvas 3:4 white badge), 43-48 (Style 5 Canvas 1:1 dải xanh).
  2. Chạy `python -m pytest tests/test_style_mapping.py` để xác thực phân giải chính xác từng style instance.
  3. Đồng bộ cờ `--style-map` / `-s` trong `cli.py` khi muốn ghi đè cấu hình dòng lệnh.
- **Files liên quan**: `batch_video_cutter/config.py`, `tests/test_style_mapping.py`, `batch_video_cutter/ui/cli.py`

### Quy trình Đóng gói Clip Thành phẩm & Tên Video Output
- **Ngày**: 2026-07-27
- **Bước thực hiện**:
  1. `pipeline.py` xác định `self.bundle_dir = base_dir / folder_name` (Ví dụ: `batch_export_20260727_014900/`).
  2. Định dạng tên file clip: `clip_filename = f"{video_info.folder_name}.{clip_idx}.mp4"` (Ví dụ: `25.1.mp4`, `25.2.mp4`).
  3. Ghi tổng hợp tiêu đề trích dẫn vào file `all_clip_titles.txt` nằm trực tiếp trong folder đóng gói.
- **Files liên quan**: `batch_video_cutter/pipeline.py`

### Chẩn Đoán Lý Do Folder Chỉ Xuất 1 Video Thay Vì 3 Video
- **Ngày**: 2026-08-28
- **Bước thực hiện**:
  1. Kiểm tra log `analyzer.py`: Tìm các dòng warning `Segment X: ... REJECT!` hoặc `start_time ... nằm trong vùng intro`.
  2. Kiểm tra mốc thoại transcript: Xác định phần thoại chính có bị dính 35s đầu / 25s cuối hay không.
  3. Kiểm tra tiêu đề: Xác định candidate có bị loại do tiêu đề không đạt 8-10 từ Tiếng Anh hay không.
  4. Kiểm tra Style: Xem folder có thuộc Style 3, 4, 5 (giới hạn `max_clips = 2`) hay không.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/pipeline.py`

---

## Patterns

### Hard Shape Constraint & Target Ratio 0.88 Optimization Pattern
- **Ngày**: 2026-08-23
- **Chi tiết**: Pattern lọc các candidate ngắt dòng thỏa mãn Hard Shape Constraint (`w1 < w2`), sau đó sắp xếp theo tuple key 3 cấp:
  ```python
  (
      abs(TARGET_TOP_CAPTION_RATIO - (c["w1"] / c["w2"])),  # Ưu tiên ratio gần 0.88
      abs(len(c["l1_words"]) - len(c["l2_words"])),         # Cân bằng số từ
      abs(c["w1"] - c["w2"])                                # Độ lệch pixel
  )
  ```
  Giúp tiêu đề Top Caption luôn giữ dạng hình nón ngược / thang uốn lượn vừa vặn trong khung badge mà không bị phình ở dòng 1.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Strict Emoji Relocation to End of String Pattern
- **Ngày**: 2026-08-01
- **Chi tiết**: Pattern bóc tách toàn bộ emojiunicode `found = pattern.findall(text)` -> xóa emoji khỏi text body `clean = pattern.sub("", text).strip()` -> ghép lại `f"{clean} {' '.join(found)}"` giúp đảm bảo 100% emoji luôn nằm ở vị trí cuối cùng của chuỗi bất kể vị trí xuất hiện ban đầu.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Vòng Lặp LLM Validation Tiêu Đề 8-10 Từ Khống Dùng Từ Rác Dummy / Hardcode Prefix
- **Ngày**: 2026-08-02
- **Chi tiết**: Áp dụng vòng lặp re-prompt LLM API (`while True`) yêu cầu AI viết lại tiêu đề tự nhiên chuẩn 8-10 từ (8 <= word_count <= 10). TUYỆT ĐỐI KHÔNG ghép thêm các tiền tố/hậu tố rác hardcode như `SHOCKING WITNESS TESTIMONY REVEALS...` hay `REVEALED NOW`, `EXPOSED`. Mọi tiêu đề hiển thị phải là câu tự nhiên 100% do LLM sinh ra. BẮT BUỘC bóc tách toàn bộ emoji ra khỏi chuỗi text trước khi thực hiện regex xóa từ rác ở đuôi chuỗi `r"(?:\s+\b(?:EXPOSED|REVEALED|TRUTH|UNCOVERED|NOW)\b)+\s*$"`, để tránh việc emoji ở cuối câu làm trượt regex match.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/utils/graphic_subtitle.py`, `scipt.txt`

### First 3-Second Retention Hook & Genre-Aware Prompting Pattern
- **Ngày**: 2026-09-06
- **Chi tiết**: Pattern cấu trúc prompt phân tách theo 2 tầng: (1) Ép mốc mở đầu 3s đầu tiên phải chứa cú hook cực mạnh (gây tò mò, tranh cãi, sốc, hoặc câu hỏi ngỏ `curiosity gap`); (2) Phân nhánh thể loại rõ ràng (Show Review chọn nhận định đanh thép/bóc mẽ; Phim/Courtroom chọn đối thoại trực tiếp phản biện). Giúp tăng tỷ lệ giữ chân người xem (retention rate) trên Reels/TikTok mà không làm AI bị reject nhầm video độc thoại review.
- **Files liên quan**: `scipt.txt`, `batch_video_cutter/core/analyzer.py`

### Downscale Fast Blur & Dual-GPU Hardware MFT Balancing Pattern
- **Ngày**: 2026-09-07
- **Chi tiết**: 
  1. **Fast Downscale Blur**: Thay vì chạy `boxblur=25:5` trực tiếp trên canvas 1080x1080 ngốn 175 triệu phép tính/s trên CPU, thu nhỏ nền xuống `270x270:force_original_aspect_ratio=increase,crop=270:270` -> `boxblur=10:1` -> phóng to lại `scale=out_w:out_h`. Giảm 80% tải CPU và tăng tốc render 2.8 lần trong khi độ mịn mờ nền vẫn giữ nguyên chuẩn CapCut.
  2. **Dual-GPU Pipeline Balancing**: Tận dụng `-hwaccel auto` để giải mã phần cứng (DXVA2) và ưu tiên `h264_mf` (Windows Media Foundation Hardware MFT) đạt tốc độ 16.2x khi `h264_nvenc` chưa khả dụng do driver GPU rời chưa cập nhật.
- **Files liên quan**: `batch_video_cutter/styles/style_1.py`, `batch_video_cutter/styles/style_2.py`, `batch_video_cutter/core/engine.py`, `batch_video_cutter/utils/ffmpeg_check.py`

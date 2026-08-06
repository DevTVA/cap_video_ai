# Video Subtitle & Outcard Processing

> Tổng hợp kiến thức về hệ thống Phụ đề đồ họa Graphic Subtitle Layer, Emoji màu, Top Caption Badge, tăng âm lượng 1.3x và Outcard overlay trong dự án.
> Cập nhật lần cuối: 2026-08-01

---

## Architecture

### Graphic Subtitle Layer bằng Pillow & Commit 1 Restore
- **Ngày**: 2026-07-27
- **Chi tiết**: Phụ đề chữ (kèm 3 màu active word highlight, viền đen mập 8px 2-pass solid stroke) và ảnh HD 3D Color PNG Emoji được render trực tiếp lên **1 tấm ảnh PNG trong suốt (RGBA)** cho mỗi mốc thoại. Đã khôi phục chuẩn bản Commit 1 với `chunk_size = 4`, tự động chia 2 dòng căn giữa giúp phụ đề rõ ràng, đẹp mắt và đúng nguyên bản.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/utils/subtitle.py`

### Top Caption Stepped Contour Rounded Badge & Giới hạn 8 - 12 Từ (Style 4)
- **Ngày**: 2026-07-28
- **Chi tiết**: Style 4 dùng Canvas 3:4 (1080x1440) kèm Stepped Contour White Badge uốn lượn uốn góc theo từng dòng (`radius=18`), lề 40px hai bên (max text width 940px), font Montserrat-Bold 40pt. Các dòng chữ được vẽ các khung rounded rectangle đè nhẹ 6px nối liền trên cùng một lớp ảnh trước khi vẽ chữ, tạo dải nền trắng uốn lượn uốn góc liền khối 100% không đứt đoạn và không bị tách rời thành nhiều thẻ độc lập. Số từ Top Caption được đảm bảo nghiêm ngặt từ **8 đến 12 từ**.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/styles/style_4.py`

### Phân Tách Định Dạng Caption 100% Tiếng Anh Giữa Video và File Summary
- **Ngày**: 2026-08-01
- **Chi tiết**: Tiêu đề caption trong toàn bộ hệ thống BẮT BUỘC 100% là Tiếng Anh (`title_en`). Quy định định dạng:
  1. **Trên Video Frame (Top Caption PNG)**: Chữ Tiếng Anh in hoa (`UPPERCASE`), font Montserrat-Bold, không dính emoji trong khung ảnh.
  2. **Trong File Tổng Hợp (`all_clip_titles.txt`)**: Chữ Tiếng Anh ở dạng chữ thường (`lowercase`), kèm Emoji nổi bật nằm ở vị trí CUỐI CÙNG của chuỗi.
- **Files liên quan**: `batch_video_cutter/pipeline.py`, `batch_video_cutter/utils/graphic_subtitle.py`

### Single-Pass FFmpeg Pipeline & Đóng Gói Thành Phẩm
- **Ngày**: 2026-07-27
- **Chi tiết**: Gộp toàn bộ quá trình cắt clip, zoom video 150% (không mất cằm/đầu), nạp lớp phụ đề đồ họa, tăng âm 1.3x và hòa trộn `outcard.mp4` vào một câu lệnh FFmpeg duy nhất. Đóng gói clip thành phẩm vào thư mục phiên làm việc `final_clips/batch_export_YYYYMMDD_HHMMSS/` với tên clip chuẩn dạng `{folder_name}.{clip_idx}.mp4` (Ví dụ: `25.1.mp4`, `25.2.mp4`) giống 100% Phong cách 1 & 2.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/pipeline.py`

---

## Bugs & Solutions

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

### Quy trình Đóng gói Clip Thành phẩm & Tên Video Output
- **Ngày**: 2026-07-27
- **Bước thực hiện**:
  1. `pipeline.py` xác định `self.bundle_dir = base_dir / folder_name` (Ví dụ: `batch_export_20260727_014900/`).
  2. Định dạng tên file clip: `clip_filename = f"{video_info.folder_name}.{clip_idx}.mp4"` (Ví dụ: `25.1.mp4`, `25.2.mp4`).
  3. Ghi tổng hợp tiêu đề trích dẫn vào file `all_clip_titles.txt` nằm trực tiếp trong folder đóng gói.
- **Files liên quan**: `batch_video_cutter/pipeline.py`

---

## Patterns

### Strict Emoji Relocation to End of String Pattern
- **Ngày**: 2026-08-01
- **Chi tiết**: Pattern bóc tách toàn bộ emojiunicode `found = pattern.findall(text)` -> xóa emoji khỏi text body `clean = pattern.sub("", text).strip()` -> ghép lại `f"{clean} {' '.join(found)}"` giúp đảm bảo 100% emoji luôn nằm ở vị trí cuối cùng của chuỗi bất kể vị trí xuất hiện ban đầu.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Vòng Lặp LLM Validation Tiêu Đề 8-10 Từ Khống Dùng Từ Rác Dummy / Hardcode Prefix
- **Ngày**: 2026-08-02
- **Chi tiết**: Áp dụng vòng lặp re-prompt LLM API (`while True`) yêu cầu AI viết lại tiêu đề tự nhiên chuẩn 8-10 từ (8 <= word_count <= 10). TUYỆT ĐỐI KHÔNG ghép thêm các tiền tố/hậu tố rác hardcode như `SHOCKING WITNESS TESTIMONY REVEALS...` hay `REVEALED NOW`, `EXPOSED`. Mọi tiêu đề hiển thị phải là câu tự nhiên 100% do LLM sinh ra. BẮT BUỘC bóc tách toàn bộ emoji ra khỏi chuỗi text trước khi thực hiện regex xóa từ rác ở đuôi chuỗi `r"(?:\s+\b(?:EXPOSED|REVEALED|TRUTH|UNCOVERED|NOW)\b)+\s*$"`, để tránh việc emoji ở cuối câu làm trượt regex match.
- **Files liên quan**: `batch_video_cutter/core/analyzer.py`, `batch_video_cutter/utils/graphic_subtitle.py`, `scipt.txt`


# Video Subtitle & Outcard Processing

> Tổng hợp kiến thức về hệ thống Phụ đề đồ họa Graphic Subtitle Layer, Emoji màu, tăng âm lượng 1.3x và Outcard overlay trong dự án.
> Cập nhật lần cuối: 2026-07-26

---

## Architecture

### Graphic Subtitle Layer bằng Pillow
- **Ngày**: 2026-07-26
- **Chi tiết**: Phụ đề chữ (kèm 3 màu active word highlight, viền đen mập `stroke_width=6`) và ảnh HD 3D Color PNG Emoji được render trực tiếp lên **1 tấm ảnh PNG trong suốt (RGBA 1080x1080)** cho mỗi mốc thoại. Vì chữ và emoji nằm trên cùng 1 tấm ảnh, chúng xuất hiện và biến mất **chính xác từng millisecond cùng lúc 100% (0ms độ trễ)**.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/utils/subtitle.py`

### Single-Pass FFmpeg Pipeline
- **Ngày**: 2026-07-26
- **Chi tiết**: Gộp toàn bộ quá trình cắt clip, zoom video 150%, nạp lớp phụ đề đồ họa, tăng âm lượng 1.3x và hòa trộn `outcard.mp4` ở 2.113s cuối vào **một câu lệnh FFmpeg duy nhất**, đảm bảo tuân thủ `tool-design.md` không ngốn RAM và không rác file tạm.
- **Files liên quan**: `batch_video_cutter/core/engine.py`

---

## Bugs & Solutions

### Monochrome Emoji trong Libass Subtitle
- **Ngày**: 2026-07-26
- **Vấn đề**: Bộ render phụ đề ASS (`libass`) trong FFmpeg trên Windows biến font emoji màu (`Noto Color Emoji`) thành nét vẽ đơn sắc đen trắng.
- **Root cause**: `libass` trên Windows mặc định strip các lớp màu của font emoji.
- **Fix**: Sử dụng Pillow dán ảnh HD 3D Color PNG (`65x65px`) trực tiếp lên bức ảnh phụ đề đồ họa trong suốt.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Màn hình bị Tím Lịm (Magenta Tint) khi dùng FFmpeg `blend` Filter
- **Ngày**: 2026-07-26
- **Vấn đề**: Toàn bộ màn hình video bị biến thành màu hồng/tím lịm khi hòa trộn `outcard.mp4`.
- **Root cause**: Bộ lọc `blend=all_mode=screen` của FFmpeg đi kèm `enable='gte(t,...)'` làm biến đổi không gian màu YUV Chroma ($U, V$ bị đẩy lên 255).
- **Fix**: Thay thế bộ lọc `blend` bằng bộ lọc `colorkey=black:0.15:0.1` kết hợp `overlay`. Bộ lọc `colorkey` biến nền đen của outcard thành trong suốt mà **không can thiệp vào kênh màu YUV của video gốc**, giữ nguyên 100% màu sắc tự nhiên.
- **Files liên quan**: `batch_video_cutter/core/engine.py`

---

## How-To

### Quy trình tạo Phụ đề Đồ họa & Hòa trộn Outcard
- **Ngày**: 2026-07-26
- **Bước thực hiện**:
  1. `generate_graphic_subtitles()` trong `graphic_subtitle.py` render từng mốc thoại thành ảnh PNG trong suốt lưu tại `g_subs_tmp/`.
  2. `cut_and_render_clip()` xây dựng lệnh FFmpeg nạp danh sách ảnh phụ đề và file `outcard.mp4`.
  3. Áp dụng filter âm lượng `[0:a]volume=eval=frame:volume='if(gte(t,outcard_start),0,1.30)'[a_main_vol]` để tăng âm 1.3x và tắt thoại gốc về 0 khi outcard chạy.
  4. Sử dụng `colorkey=black:0.15:0.1` tách nền đen outcard và đè overlay lên video ở 2.113s cuối.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/core/engine.py`

---

## Patterns

### Đo đạc độ rộng chữ chính xác bằng Pillow
- **Ngày**: 2026-07-26
- **Chi tiết**: Dùng `font.getbbox(text)` từ font TTF (`Impact.ttf` / `Montserrat-Bold.ttf`) để đo chính xác chiều rộng pixel dòng chữ chứa dấu chấm `.`, sau đó dán ảnh emoji tại `x = last_line_end_x + 8` sát ngay sau dấu chấm `.`.
- **Ví dụ code**:
  ```python
  bbox = font.getbbox(text)
  text_width = bbox[2] - bbox[0]
  emoji_x = min(canvas_size[0] - 70, last_line_end_x + 8)
  img.paste(emoji_img, (emoji_x, emoji_y), emoji_img)
  ```
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Tắt âm thoại gốc & Trộn âm thanh Outcard
- **Ngày**: 2026-07-26
- **Chi tiết**: Dùng `adelay=delays={start_ms}:all=1` làm trễ luồng âm thanh outcard và dùng `amix=inputs=2:duration=first` để phát âm thanh outcard đúng mốc thời gian.
- **Files liên quan**: `batch_video_cutter/core/engine.py`

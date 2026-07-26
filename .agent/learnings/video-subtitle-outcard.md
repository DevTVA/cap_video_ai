# Video Subtitle & Outcard Processing

> Tổng hợp kiến thức về hệ thống Phụ đề đồ họa Graphic Subtitle Layer, Emoji màu, Top Caption Badge, tăng âm lượng 1.3x và Outcard overlay trong dự án.
> Cập nhật lần cuối: 2026-07-27

---

## Architecture

### Graphic Subtitle Layer bằng Pillow & Commit 1 Restore
- **Ngày**: 2026-07-27
- **Chi tiết**: Phụ đề chữ (kèm 3 màu active word highlight, viền đen mập 8px 2-pass solid stroke) và ảnh HD 3D Color PNG Emoji được render trực tiếp lên **1 tấm ảnh PNG trong suốt (RGBA)** cho mỗi mốc thoại. Đã khôi phục chuẩn bản Commit 1 với `chunk_size = 4`, tự động chia 2 dòng căn giữa giúp phụ đề rõ ràng, đẹp mắt và đúng nguyên bản.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/utils/subtitle.py`

### Top Caption Single White Badge & Giới hạn 8 - 12 Từ (Style 4)
- **Ngày**: 2026-07-27
- **Chi tiết**: Style 4 dùng Canvas 3:4 (1080x1440) kèm Single White Badge bo góc (`radius=18`), lề 40px hai bên (max text width 936px), font Arial Bold 40pt. Số từ Top Caption được đảm bảo nghiêm ngặt từ **8 đến 12 từ** (`min 8, max 12 words`). Nếu tiêu đề ngắn (<8 từ), hệ thống dùng vòng lặp tự động lấy từ nối tiếp từ transcript hoặc viral fillers để mở rộng đủ 8 từ.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`, `batch_video_cutter/styles/style_4.py`

### Single-Pass FFmpeg Pipeline & Đóng Gói Thành Phẩm
- **Ngày**: 2026-07-27
- **Chi tiết**: Gộp toàn bộ quá trình cắt clip, zoom video 150% (không mất cằm/đầu), nạp lớp phụ đề đồ họa, tăng âm 1.3x và hòa trộn `outcard.mp4` vào một câu lệnh FFmpeg duy nhất. Đóng gói clip thành phẩm vào thư mục phiên làm việc `final_clips/batch_export_YYYYMMDD_HHMMSS/` với tên clip chuẩn dạng `{folder_name}.{clip_idx}.mp4` (Ví dụ: `25.1.mp4`, `25.2.mp4`) giống 100% Phong cách 1 & 2.
- **Files liên quan**: `batch_video_cutter/core/engine.py`, `batch_video_cutter/pipeline.py`

---

## Bugs & Solutions

### Anti-Flicker & Trám Khoảng Lặng Trống Phụ Đề
- **Ngày**: 2026-07-27
- **Vấn đề**: Phụ đề bị chớp tắt liên tục quá nhanh khi nhân vật nói lướt hoặc giữa cáctừ thoại có khoảng lặng nhỏ.
- **Root cause**: Mốc thời gian hiển thị từng ảnh ngắn 100ms và có khoảng trống đen không có overlay giữa các từ.
- **Fix**: Áp dụng `Anti-Flicker Seamless Subtitle Engine`: Đảm bảo mốc hiển thị tối thiểu 0.35s cho mỗi ảnh và trám kín khoảng lặng trống (<0.50s) kéo dài sát mốc bắt đầu của ảnh kế tiếp (`next_start - 0.01s`), giúp phụ đề hiển thị êm ái 100% không chớp nháy.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

### Chữ Bị Tràn Hoặc Bị Cắt Ở Các Góc Bo Tròn
- **Ngày**: 2026-07-27
- **Vấn đề**: Chữ ở dòng 1 sát góc bo tròn của White Badge bị mất ký tự đầu/cuối (ví dụ chữ W, D).
- **Root cause**: Ngắt dòng theo số ký tự cố định không tính đến độ rộng pixel thực tế của chữ và padding trong badge.
- **Fix**: Ngắt dòng theo độ rộng pixel thực tế `font.getbbox()` kết hợp `max_text_w = 936px` và padding `pad_w = 32px`, đảm bảo chữ luôn thụt lề 40px và nằm an toàn tuyệt đối bên trong badge bo góc.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

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

### Đo đạc độ rộng chữ pixel width thực tế trong Pillow
- **Ngày**: 2026-07-27
- **Chi tiết**: Sử dụng `font.getbbox(test_string)[2]` để đo độ rộng pixel chính xác của chuỗi chữ trước khi quyết định ngắt dòng, giúp từ tự động lấp đầy Line 1 trước khi đẩy sang Line 2.
- **Files liên quan**: `batch_video_cutter/utils/graphic_subtitle.py`

# API Optimization & Rate Limit Management

> Tổng hợp kiến thức về tối ưu hóa LLM API, Local Caching, chống lỗi Rate Limit 429 và quy trình gộp batch export trong dự án Batch Video Cutter.
> Cập nhật lần cuối: 2026-07-31

---

## Architecture

### Tối ưu hóa LLM API với Multi-tier Failover & Smart Key Rotation
- **Ngày**: 2026-07-31
- **Chi tiết**: Sử dụng cơ chế Smart Key Rotation. Ngay khi 1 API Key bị dính lỗi `429` (Rate limit / Quota Exceeded), hệ thống lập tức ngắt vòng lặp model của key đó và chuyển ngay sang Key tiếp theo. Tích hợp hệ thống dự phòng đa tầng (Gemini ➔ SambaNova ➔ Groq ➔ OpenRouter).
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Tích hợp Bộ Nhớ Tạm Đĩa (Local Disk Caching)
- **Ngày**: 2026-07-31
- **Chi tiết**: Tạo mã Hash SHA-256 duy nhất từ `transcript_text + max_clips + prompt_template`. Trước khi gửi request lên AI API, kiểm tra cache trong `.cache/`. Nếu kết quả đã tồn tại và đủ số lượng clip, trả về ngay lập tức mà không tốn API request.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

---

## Bugs & Solutions

### Spam Retry Loop trên Key đã cạn Quota (Lỗi Rate Limit 429)
- **Ngày**: 2026-07-31
- **Vấn đề**: Khi Key 1 gặp lỗi 429 trên model `gemini-2.0-flash`, code cũ tiếp tục thử `gemini-2.0-flash-lite`, `gemini-1.5-flash`, `gemini-1.5-pro` trên cùng Key 1, gây spam 429 liên tiếp và cạn sạch Quota.
- **Root cause**: Vòng lặp inner models không dừng lại khi key đã bị rate limit.
- **Fix**: Thêm cờ `key_exhausted = True` và `break` ra khỏi vòng lặp model khi gặp lỗi 429/quota để chuyển ngay sang Key tiếp theo.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Lỗi Parse Text Response LLM Không Trích Xuất Được Tiêu Đề 2 Ngôn Ngữ
- **Ngày**: 2026-07-31
- **Vấn đề**: Khi AI trả về response theo đúng prompt `scipt.txt` có chèn dòng trống `\n` giữa timecode và tiêu đề, parser đọc phải dòng trống dẫn tới `title_en` và `title_vi` bị rỗng (`""`), từ đó kích hoạt fallback title mặc định.
- **Root cause**: `_parse_llm_response_text` chỉ đọc dòng `i+1` cố định thay vì duyệt bỏ qua các dòng trống.
- **Fix**: Cập nhật `_parse_llm_response_text` dùng vòng lặp `while` tự động bỏ qua tất cả các dòng trống `\n` để trích xuất chuẩn `title_en` và `title_vi`.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

---

## How-To

### Quy trình Gộp & Tổng hợp Clips từ nhiều Batch Export
- **Ngày**: 2026-07-31
- **Bước thực hiện**:
  1. Quét tất cả file `.mp4` trong các thư mục `batch_export_*` và sắp xếp theo mtime.
  2. Map file theo pattern `folder_id.clip_id.mp4` (file mtime mới hơn sẽ đè file cũ).
  3. Hợp nhất danh sách `completed_videos` và `results_list` trong `pipeline_state.json`.
  4. Ghi lại duy nhất 1 file `all_clip_titles.txt` và `pipeline_state.json` tổng hợp cho toàn bộ 144 clips.
- **Files liên quan**: `scratch/merge_all_final.py`

---

## Patterns

### Text-Based Prompt Response Parsing Pattern
- **Ngày**: 2026-07-31
- **Chi tiết**: Pattern duyệt đệ quy bỏ qua khoảng trắng/dòng trống trong response văn bản của LLM để bóc tách tiêu đề 2 ngôn ngữ và timecode một cách bền vững.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

# API Optimization & Rate Limit Management

> Tổng hợp kiến thức về tối ưu hóa LLM API, Local Caching, chống lỗi Rate Limit 429 và quy trình gộp batch export trong dự án Batch Video Cutter.
> Cập nhật lần cuối: 2026-08-22

---

## Architecture

### Tối ưu hóa LLM API với Multi-tier Failover & Smart Key Rotation
- **Ngày**: 2026-07-31
- **Chi tiết**: Sử dụng cơ chế Smart Key Rotation. Ngay khi 1 API Key bị dính lỗi `429` (Rate limit / Quota Exceeded), hệ thống lập tức ngắt vòng lặp model của key đó và chuyển ngay sang Key tiếp theo. Tích hợp hệ thống dự phòng đa tầng (Gemini ➔ SambaNova ➔ Groq ➔ OpenRouter).
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Phân loại Lỗi HTTP & Session-level Blacklisting cho API Keys/Models
- **Ngày**: 2026-08-22
- **Chi tiết**: Phân loại chính xác các mã lỗi HTTP để xử lý riêng biệt: 401/403 đưa Key vào `_DISABLED_KEYS` ngắt toàn session; 404/Decommissioned đưa Model vào `_DISABLED_MODELS`; 429 Server Busy áp dụng Exponential Backoff Retry (tối đa 3 lần); 429 Quota Exceeded chuyển Key tiếp theo.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Batch Caption Repair Architecture
- **Ngày**: 2026-08-22
- **Chi tiết**: Thay vì gửi N request riêng lẻ để sửa các title chưa đạt chuẩn (8-10 từ Tiếng Anh), hệ thống lọc các `ViralSegment` không đạt chuẩn và gửi 1 Batch API Request duy nhất để LLM sửa đồng loạt tất cả headline cùng lúc, tối ưu số lượng request và chi phí API.
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

### Spam Retry và Treo Ứng Dụng khi Gemini Model 404 / Key 401
- **Ngày**: 2026-08-22
- **Vấn đề**: Khi API Key bị vô hiệu hóa (401) hoặc model bị gỡ bỏ/404, ứng dụng tiếp tục gọi lại ở các lượt request sau làm chậm tiến trình và gây tràn log rác.
- **Root cause**: Không lưu trạng thái vô hiệu hóa của key/model bị lỗi vĩnh viễn trong runtime session.
- **Fix**: Tự động thêm key lỗi 401/403 vào `_DISABLED_KEYS` và model 404 vào `_DISABLED_MODELS`, đồng thời lọc bỏ chúng trước khi thực hiện gọi API trong session.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Lỗi Báo HTTP Error Mập Mờ Không Có Detail Từ Groq API
- **Ngày**: 2026-08-22
- **Vấn đề**: Exception khi gọi Groq API chỉ báo `HTTP 401 Unauthorized` mà không hiển thị lý do chi tiết từ JSON body của response.
- **Root cause**: `urllib.error.HTTPError` chưa được đọc stream để parse JSON message trong thuộc tính error.
- **Fix**: Viết hàm helper `_extract_http_error_detail(err)` đọc và trích xuất JSON message từ HTTP response stream (vd: `HTTP 401: Invalid API Key provided`).
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py), [test_groq_api_error_handling.py](file:///e:/AI_Agent/tests/test_groq_api_error_handling.py)

### Lỗi Parse Text Response LLM Không Trích Xuất Được Tiêu Đề 2 Ngôn Ngữ
- **Ngày**: 2026-07-31
- **Vấn đề**: Khi AI trả về response theo đúng prompt `scipt.txt` có chèn dòng trống `\n` giữa timecode và tiêu đề, parser đọc phải dòng trống dẫn tới `title_en` và `title_vi` bị rỗng (`""`), từ đó kích hoạt fallback title mặc định.
- **Root cause**: `_parse_llm_response_text` chỉ đọc dòng `i+1` cố định thay vì duyệt bỏ qua các dòng trống.
- **Fix**: Cập nhật `_parse_llm_response_text` dùng vòng lặp `while` tự động bỏ qua tất cả các dòng trống `\n` để trích xuất chuẩn `title_en` và `title_vi`.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

---

## How-To

### Test & Mock Đa Kịch Bản HTTP Error Handling Cho LLM API
- **Ngày**: 2026-08-22
- **Bước thực hiện**:
  1. Sử dụng `io.BytesIO` để giả lập response JSON stream từ `urllib.error.HTTPError`.
  2. Gọi helper `_extract_http_error_detail` để kiểm tra chuỗi lỗi format chuẩn `HTTP <status>: <message>`.
  3. Dùng `monkeypatch` của pytest để xoá/thay đổi biến môi trường API keys và verify kịch bản failover ném `RuntimeError`.
- **Files liên quan**: [test_groq_api_error_handling.py](file:///e:/AI_Agent/tests/test_groq_api_error_handling.py)

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

### Session-Scoped Disabled Resource Pattern (Blacklisting Sets)
- **Ngày**: 2026-08-22
- **Chi tiết**: Sử dụng `set` ở module-level (`_DISABLED_KEYS`, `_DISABLED_MODELS`) để lưu trữ tài nguyên bị vô hiệu hóa trong runtime session. Tất cả hàm gọi API đều lọc danh sách tài nguyên hợp lệ trước khi lặp, triệt tiêu overhead từ việc gọi lại các API keys/models bị hỏng.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Text-Based Prompt Response Parsing Pattern
- **Ngày**: 2026-07-31
- **Chi tiết**: Pattern duyệt đệ quy bỏ qua khoảng trắng/dòng trống trong response văn bản của LLM để bóc tách tiêu đề 2 ngôn ngữ và timecode một cách bền vững.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

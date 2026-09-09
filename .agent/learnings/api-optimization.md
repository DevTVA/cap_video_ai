# API Optimization & Rate Limit Management

> Tổng hợp kiến thức về tối ưu hóa LLM API, Pure Local Caching, chống lỗi Rate Limit 429, Waterfall Title Resolution và Supplementary Filler Engine trong dự án Batch Video Cutter.
> Cập nhật lần cuối: 2026-08-28

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

### Pure Cache Layer Separation (Tách Biệt Bộ Nhớ Tạm)
- **Ngày**: 2026-08-28
- **Chi tiết**: Tách biệt hoàn toàn Cache Layer: `_read_cache()` CHỈ đọc/ghi dữ liệu JSON thô từ đĩa đè lên `ViralSegment`, tuyệt đối KHÔNG chứa logic nghiệp vụ tự bù clip hay validate title. Quyết định bù clip và kiểm tra chất lượng thuộc về tầng Analyzer/Orchestrator.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Chiến Lược Tiêu Đề 3 Tầng Tiết Kiệm API & Golden Rule Safeguard
- **Ngày**: 2026-08-28
- **Chi tiết**: Tiêu đề được giải quyết theo 3 tầng ưu tiên: Tầng 1 (Candidate Title có sẵn từ LLM Pool) ➔ Tầng 2 (Spoken Headline từ transcript qua `_extract_spoken_headline`) ➔ Tầng 3 (LLM API Refine đơn lẻ làm Last Resort). Áp dụng Quy tắc vàng: Video gốc hợp lệ không bao giờ bị loại do tiêu đề; tự động pad/trim thoại đảm bảo caption luôn đạt 8–10 từ.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Supplementary Filler Engine 2 Tầng & Rejection Telemetry
- **Ngày**: 2026-08-28
- **Chi tiết**: Khi số clip hợp lệ < mục tiêu, kích hoạt `_fill_missing_segments`: Tier 1 (Strict Search 25–29s, intro chuẩn), Tier 2 (Relaxed Search 22–32s, intro 20s). Tích hợp Enum `CandidateRejectionReason` (INTRO, OUTRO, DURATION, DIALOGUE, DUPLICATE, TITLE, OVERLAP) và `RejectionTracker` xuất bảng thống kê lý do loại bỏ.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py), [pipeline.py](file:///e:/AI_Agent/batch_video_cutter/pipeline.py)

### Batch Caption Repair Architecture
- **Ngày**: 2026-08-22
- **Chi tiết**: Thay vì gửi N request riêng lẻ để sửa các title chưa đạt chuẩn (8-10 từ Tiếng Anh), hệ thống lọc các `ViralSegment` không đạt chuẩn và gửi 1 Batch API Request duy nhất để LLM sửa đồng loạt tất cả headline cùng lúc, tối ưu số lượng request và chi phí API.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

---

## Bugs & Solutions

### Style 2 Cắt Sai Số Lượng 3 Video Do Thiếu Method get_max_clips
- **Ngày**: 2026-08-28
- **Vấn đề**: Khi chạy batch với Style 2, mỗi video bị cắt thành 3 clips thay vì 2 clips.
- **Root cause**: `Style2` thiếu method `get_max_clips()`, thừa kế `None` từ `BaseStyle` và fallback về CLI option `--max-clips` đang để default là 3.
- **Fix**: Khai báo `get_max_clips()` riêng cho từng Style (Style 1, 2, 5: 2 clips; Style 3, 4: 3 clips) và chuẩn hóa default `--max-clips` trong `cli.py` và `base.py`.
- **Files liên quan**: [style_1.py](file:///e:/AI_Agent/batch_video_cutter/styles/style_1.py), [style_2.py](file:///e:/AI_Agent/batch_video_cutter/styles/style_2.py), [style_3.py](file:///e:/AI_Agent/batch_video_cutter/styles/style_3.py), [style_4.py](file:///e:/AI_Agent/batch_video_cutter/styles/style_4.py), [style_5.py](file:///e:/AI_Agent/batch_video_cutter/styles/style_5.py), [cli.py](file:///e:/AI_Agent/batch_video_cutter/ui/cli.py)

### Spam Retry Loop trên Key đã cạn Quota (Lỗi Rate Limit 429)
- **Ngày**: 2026-07-31
- **Vấn đề**: Khi Key 1 gặp lỗi 429 trên model `gemini-2.0-flash`, code cũ tiếp tục thử các model khác trên cùng Key 1, gây spam 429 liên tiếp và cạn sạch Quota.
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

### Quy Trình Cấu Hình & Kiểm Thử Số Lượng Clip Theo Từng Phong Cách
- **Ngày**: 2026-08-28
- **Bước thực hiện**:
  1. Định nghĩa rõ hàm `get_max_clips(self) -> int` trong từng class `StyleX` (ví dụ: Style 1, 2, 5 trả về 2; Style 3, 4 trả về 3).
  2. Đảm bảo `BaseStyle.get_max_clips()` và CLI option `--max-clips` có fallback đồng bộ.
  3. Viết unit test `test_all_styles_clip_counts()` trong `tests/test_style_mapping.py` để verify cấu hình toàn diện.
- **Files liên quan**: [styles/](file:///e:/AI_Agent/batch_video_cutter/styles/), [test_style_mapping.py](file:///e:/AI_Agent/tests/test_style_mapping.py)

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
  4. Ghi lại duy nhất 1 file `all_clip_titles.txt` và `pipeline_state.json` tổng hợp cho toàn bộ clips.
- **Files liên quan**: `scratch/merge_all_final.py`

---

## Patterns

### Pure Cache Layer Separation Pattern
- **Ngày**: 2026-08-28
- **Chi tiết**: Tách biệt hoàn toàn tầng lưu trữ Cache I/O với tầng logic phân tích và bổ sung clip. Hàm cache chỉ đảm nhận nhiệm vụ đọc/ghi đĩa thuần túy, tránh ẩn giấu side-effects hoặc tự ý biến đổi dữ liệu.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Golden Rule Title Safeguard Pattern
- **Ngày**: 2026-08-28
- **Chi tiết**: Tách biệt validation phân đoạn video và validation tiêu đề. Khi phân đoạn video đã hợp lệ về hình ảnh và âm thanh, tiêu đề luôn có phương án fallback tự động pad/trim từ lời thoại thực tế, đảm bảo không bao giờ loại bỏ oan video chỉ vì lỗi định dạng tiêu đề.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Session-Scoped Disabled Resource Pattern (Blacklisting Sets)
- **Ngày**: 2026-08-22
- **Chi tiết**: Sử dụng `set` ở module-level (`_DISABLED_KEYS`, `_DISABLED_MODELS`) để lưu trữ tài nguyên bị vô hiệu hóa trong runtime session. Tất cả hàm gọi API đều lọc danh sách tài nguyên hợp lệ trước khi lặp, triệt tiêu overhead từ việc gọi lại các API keys/models bị hỏng.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

### Text-Based Prompt Response Parsing Pattern
- **Ngày**: 2026-07-31
- **Chi tiết**: Pattern duyệt đệ quy bỏ qua khoảng trắng/dòng trống trong response văn bản của LLM để bóc tách tiêu đề 2 ngôn ngữ và timecode một cách bền vững.
- **Files liên quan**: [analyzer.py](file:///e:/AI_Agent/batch_video_cutter/core/analyzer.py)

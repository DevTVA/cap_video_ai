# Speech-Rhythm Subtitle Engine

> Tổng hợp kiến thức về thuật toán ngắt nhịp phụ đề chuẩn theo giọng nói nhân vật và xử lý triệt để lỗi chớp nháy phụ đề.
> Cập nhật lần cuối: 2026-07-30

---

## Architecture

### Phân Cụm Phụ Đề Theo Nhịp Nói (Punctuation & Pause Detection)
- **Ngày**: 2026-07-30
- **Chi tiết**: Thay vì cắt cụm từ cố định (hardcoded 3-4 words), engine nhóm các từ thoại dựa trên dấu câu (`,`, `.`, `!`, `?`, `;`, `:`) và khoảng lặng tự nhiên giữa 2 từ thoại liên tiếp (`next_start - current_end > 0.22s`). Điều này giúp phụ đề tự nhiên, khớp hoàn toàn với nhịp hít thở và ngắt vế câu của thoại.
- **Files liên quan**: `batch_video_cutter/`

---

## Bugs & Solutions

### Phụ Đề Bị Chớp Nháy / Loạn Vị Trí Khi Hiển Thị
- **Ngày**: 2026-07-30
- **Vấn đề**: Khung hình phụ đề nhấp nháy hoặc thay đổi vị trí liên tục mỗi 100ms do cập nhật vị trí/cụm từ theo từng word frame.
- **Root cause**: Cắt cụm từ cố định làm từ thuộc 2 câu khác nhau bị nhét chung 1 khung, kết hợp với việc thay đổi layout khung hình theo thời lượng từng từ lẻ.
- **Fix**: Hiển thị cố định vị trí cụm từ thoại (chunk) trong suốt khoảng `[chunk_start, chunk_end]`. Áp dụng Karaoke Highlight (đổi màu chữ từ active) di chuyển theo mốc thời gian thoại thực tế mà giữ nguyên vị trí 100% khung chữ.
- **Files liên quan**: `batch_video_cutter/`

---

## How-To

### Quy Trình Triển Khai Ngắt Nhịp Phụ Đề Chuẩn CapCut
- **Ngày**: 2026-07-30
- **Bước thực hiện**:
  1. Trích xuất danh sách từ kèm mốc thời gian chi tiết (`start`, `end`, `word`) từ engine ASR/Whisper.
  2. Nhóm từ vào một cụm (chunk) mới khi gặp dấu câu ngắt câu/vế hoặc khi phát hiện khoảng nghỉ giữa 2 từ `> 0.22s`.
  3. Đặt thời gian hiển thị khung phụ đề cố định từ `chunk_start` đến `chunk_end`.
  4. Hiệu ứng Karaoke: Highlight từ tương ứng với mốc thời gian playback hiện tại mà không làm thay đổi vị trí toàn cụm.
- **Files liên quan**: `batch_video_cutter/`

---

## Patterns

### Karaoke Highlight Over Fixed Frame Pattern
- **Ngày**: 2026-07-30
- **Chi tiết**: Pattern tách biệt giữa Layout Frame (cố định theo cụm câu/vế) và Visual State (thay đổi highlight theo timestamp của word hiện tại) giúp loại bỏ chớp nháy và đạt mượt mà cao như ứng dụng CapCut.
- **Files liên quan**: `batch_video_cutter/`

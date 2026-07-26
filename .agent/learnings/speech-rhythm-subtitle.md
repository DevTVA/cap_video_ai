# Speech-Rhythm Subtitle Engine (Thuật Toán Ngắt Nhịp Phụ Đề Chuẩn Theo Giọng Nói Nhân Vật)

## Nguyên Nhân Phụ Đề Chớp Nháy / Bị Loạn Trước Đây
1. **Cắt cụm từ cố định (Hardcoded 3-4 words)**: Chia cụm ngắt dòng mà bỏ qua dấu câu hoặc khoảng dừng hít thở giữa các vế câu làm cho từ thuộc 2 câu khác nhau bị nhét chung 1 khung.
2. **Khung hình chớp tắt từng 100ms**: Cập nhật frame nhấp nháy cho từng từ làm mất tính ổn định vị trí phụ đề trên màn hình.

## Giải Pháp Đã Áp Dụng (Fix Triệt Để)
1. **Dựa vào Dấu Câu & Khoảng Ngắt Nghỉ (Punctuation & Pause Detection)**:
   - Ngắt cụm khi từ kết thúc có dấu câu: `,`, `.`, `!`, `?`, `;`, `:`.
   - Ngắt cụm khi khoảng lặng giữa 2 từ thoại liên tiếp `next_start - current_end > 0.22s`.
2. **Giữ Vị Trí Cụm Ổn Định + Karaoke Highlight Mượt**:
   - Cụm từ thoại hiển thị liên tục trong khoảng `[chunk_start, chunk_end]`.
   - Màu chữ highlight (Xanh/Vàng/Đỏ) di chuyển theo mốc thời gian thực tế của nhân vật nói từng từ, đảm bảo vị trí phụ đề đứng yên cố định 100% không chớp nháy.

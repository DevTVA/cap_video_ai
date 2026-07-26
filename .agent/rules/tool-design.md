---
trigger: always_on
description: Rule cốt lõi bắt buộc về thiết kế web. AI agent PHẢI tuân thủ 100% khi tạo/chỉnh sửa file web.
globs: "**/*.{html,css,js,jsx,tsx,ts,vue,svelte,astro}"
---

LUẬT KHÔNG THỂ THƯƠNG LƯỢNG. Vi phạm bất kỳ mục nào → tool FAILED.

1. Philosophy — Triết lý phát triển
Performance & Stability First — Xử lý video là tác vụ nặng. Tool phải mượt, không crash, không ngốn sạch RAM của người dùng.

Lossless by Default — Ưu tiên giữ nguyên chất lượng gốc (không re-encode) trừ khi người dùng yêu cầu.

TUYỆT ĐỐI KHÔNG viết code kiểu kịch bản (scripting) "chạy một lần rồi vứt". Code phải có kiến trúc, module hóa để mở rộng sau này (thêm subtitle, ghép video, v.v.).

2. Core Engine — Động cơ cốt lõi
BẮT BUỘC dùng FFmpeg làm lõi xử lý dưới background.

Giao tiếp với FFmpeg qua subprocess (chạy lệnh trực tiếp) hoặc thư viện wrapper chuẩn như ffmpeg-python.

Dùng moviepy hoặc opencv-python CHỈ KHI cần xử lý pixel sâu (thêm hiệu ứng, object tracking). Nếu chỉ cắt/ghép, moviepy quá chậm và ngốn RAM.

❌ KHÔNG tự viết thuật toán parse định dạng MP4/MKV.

3. Precision & Quality — Độ chính xác & Chất lượng
Frame-accurate Cutting: Cắt video phải chính xác đến từng mili-giây hoặc từng frame. (Lưu ý: Cắt bằng -c copy của FFmpeg thường nhảy tới Keyframe gần nhất. Nếu cần cắt chính xác, phải re-encode lại đoạn đầu hoặc toàn bộ).

Khai báo rõ ràng tham số chất lượng (CRF, Bitrate) khi bắt buộc re-encode.

❌ KHÔNG làm giảm chất lượng, thay đổi FPS hoặc sample rate âm thanh một cách thầm lặng (silently).

4. Memory & Resource Management — Quản lý tài nguyên
TUYỆT ĐỐI KHÔNG load toàn bộ video vào RAM. Xử lý video dung lượng 10GB với RAM 4GB vẫn phải chạy được.

Xử lý theo dạng stream/chunk.

Đóng giải phóng tài nguyên ngay khi xong: Bắt buộc dùng with statement cho mọi thao tác file.

Quản lý file tạm (Temporary files) cực kỳ chặt chẽ: Dùng module tempfile và phải dọn dẹp (cleanup) ngay cả khi tool bị crash giữa chừng.

5. Input/Output & Path Handling — Xử lý đường dẫn file
BẮT BUỘC dùng pathlib cho mọi thao tác đường dẫn.

Python
from pathlib import Path
input_path = Path("data/video.mp4")
output_path = input_path.with_name(f"{input_path.stem}_cut{input_path.suffix}")
❌ KHÔNG dùng nối chuỗi (dir + "\\" + file.mp4) hay os.path cũ kỹ.

Xử lý mượt mà các file có dấu cách, ký tự đặc biệt, tiếng Việt (Unicode) trong tên file.

Validate file đầu vào trước khi chạy: File có tồn tại không? Có phải là video hợp lệ không?

6. Asynchronous & Threading — Đa luồng (Đặc biệt nếu có GUI)
Quá trình cắt video (FFmpeg process) PHẢI nằm ở một luồng riêng biệt (Worker Thread / Background Process).

❌ KHÔNG BAO GIỜ để tác vụ cắt video block Main Thread.

Nếu dùng CLI: Hiển thị trạng thái rõ ràng. Nếu dùng GUI (PyQt, Tkinter): Giao diện vẫn phải bấm được (Cancel, Pause) khi đang render.

7. UX, Feedback & Logging — Trải nghiệm & Báo cáo
TUYỆT ĐỐI KHÔNG để màn hình console đen ngòm hoặc im lìm khi tool đang chạy.

Progress Bar Bắt Buộc: Tính toán tổng thời lượng và hiển thị % hoàn thành. Gợi ý dùng tqdm cho CLI hoặc thanh tiến trình của GUI.

Logging System: Không dùng print(). Bắt buộc dùng module logging hoặc thư viện loguru để ghi lại lịch sử lỗi (chia level: INFO, WARNING, ERROR).

Thông báo lỗi cho người dùng bằng ngôn ngữ con người, không ném raw traceback ra màn hình trừ chế độ debug.

8. CLI / GUI Design — Thiết kế giao diện
Nếu làm CLI (Command Line): Dùng argparse hoặc click. Cung cấp cờ -h hoặc --help chi tiết. Định dạng output đẹp mắt bằng thư viện rich.

Nếu làm GUI (Giao diện đồ họa):

Dùng CustomTkinter (hiện đại, có darkmode) hoặc PyQt/PySide.

Phải có nút "Browse" chọn file, hiển thị thumbnail/thời lượng gốc, form nhập timestamp HH:MM:SS, nút "Start" và "Cancel".

9. Code Structure & Typing — Cấu trúc mã nguồn
Type Hinting Bắt Buộc:

Python
def cut_video(input_path: Path, start_time: str, end_time: str, output_path: Path) -> bool:
Tuân thủ PEP 8 (khuyên dùng linter ruff hoặc format black).

Tách biệt logic:

core/engine.py (chứa lệnh gọi FFmpeg)

utils/helpers.py (chuyển đổi timecode, format check)

ui/cli.py hoặc ui/gui.py (chỉ chứa giao diện, gọi hàm từ core).

❌ KHÔNG nhét tất cả logic vào 1 file main.py dài 1000 dòng.

10. Dependency Management — Quản lý thư viện
Sử dụng requirements.txt hoặc poetry/pipenv.

Cố định version của thư viện (ffmpeg-python==0.2.0).

Code phải tự động kiểm tra xem máy tính đã cài FFmpeg vào biến môi trường (PATH) chưa lúc khởi động. Nếu chưa, thông báo cách cài đặt ngay.

11. Checklist bắt buộc trước khi hoàn thành
[ ] Tool có kiểm tra đầu vào (file không tồn tại, định dạng sai) không?

[ ] Cắt video bằng -c copy (nhanh) có hoạt động trơn tru không?

[ ] Parse timecode (00:01:20 sang giây) có chính xác không?

[ ] Tool có progress bar hiển thị % tiến độ rõ ràng không?

[ ] Khi ép buộc dừng (Ctrl+C hoặc nút Cancel), tiến trình ẩn (FFmpeg) có bị kill triệt để không? (Tránh để lại process mồ côi).

[ ] Tool có xử lý được tên file chứa dấu cách và tiếng Việt không?

[ ] Kiến trúc có tách bạch giữa Logic xử lý (Engine) và Giao diện (UI) chưa?

[ ] Đã có Type Hints và Docstring cho các hàm quan trọng chưa?
"""Style 5: Chuẩn 100% theo mẫu phong cách 5.mp4 gốc (Canvas 3:4 1080x1440):
- Top Caption: Dải nền màu Xanh Dương (RGB 85, 118, 251 / #5576FB), Chữ Montserrat-Bold màu TRẮNG tinh Viết Hoa 100%, tự động chia 2 dòng cân đối (không dùng White Badge bo góc và không nháy nháy kép).
- Video Stream: Canvas 3:4 (1080x1440), Video zoom 150% CapCut style đặt cân đối ở trung tâm canvas.
- Graphic Subtitles: Font Impact CapCut (66pt), Active Word Highlight VÀNG ("yellow"), lề chân tĩnh.
"""

from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea


class Style5(BaseStyle):
    """Phong cách 5: Canvas 3:4 + Top Blue Background Banner White Title + Subtitle Highlight Vàng (Chuẩn phong cách 5.mp4)."""

    CAPTION_HEIGHT_RATIO = 0.1944  # 280px / 1440px
    style_index: int = 5

    @property
    def name(self) -> str:
        return "Style 5 - 3:4 Canvas + Top Blue Background Banner White Title + Yellow Highlight Subtitle (Mẫu phong cách 5.mp4)"

    @property
    def aspect_ratio(self) -> str:
        return "3:4"

    def get_output_resolution(self) -> Tuple[int, int]:
        """Output 1080x1440 (3:4)."""
        return (1080, 1440)

    def get_caption_area(self) -> Optional[CaptionArea]:
        out_w, out_h = self.get_output_resolution()
        caption_h = 280
        return CaptionArea(
            x=0,
            y=0,
            width=out_w,
            height=caption_h,
            position="top",
        )

    def get_ffmpeg_filter(
        self,
        input_width: int,
        input_height: int,
        subtitle_path: Optional[str] = None,
        title_text: Optional[str] = None,
    ) -> Tuple[str, str]:
        out_w, out_h = self.get_output_resolution()  # 1080x1440

        if input_width <= 0 or input_height <= 0:
            input_width, input_height = 1920, 1080

        # Công thức Zoom 150% CapCut chuẩn 100% (Width=1620px)
        fit_w = out_w
        fit_h = int(input_height * (out_w / input_width))

        fg_w = int(fit_w * 1.5)
        fg_h = int(fit_h * 1.5)

        final_h = min(fg_h, out_h)
        crop_x = (fg_w - out_w) // 2
        crop_y = (fg_h - final_h) // 2
        overlay_y = (out_h - final_h) // 2  # Căn giữa khung hình trên canvas 1440px

        filters = [
            f"[0:v]scale={fg_w}:{fg_h},crop={out_w}:{final_h}:{crop_x}:{crop_y},"
            f"pad={out_w}:{out_h}:0:{overlay_y}:black[styled]"
        ]
        output_label = "[styled]"

        if subtitle_path:
            ass_filter = self.format_ass_filter(subtitle_path)
            last_lbl = output_label.strip("[]")
            filters.append(f"[{last_lbl}]{ass_filter}[out]")
            output_label = "[out]"

        return ";".join(filters), output_label

    def get_subtitle_position(self) -> str:
        return "bottom"

    def get_highlight_color(self) -> str:
        """Màu Highlight MÀU XANH LÁ ("green")."""
        return "green"

    def get_font_size(self) -> int:
        """Cỡ font 66pt."""
        return 66

    def get_italic_option(self) -> bool:
        return False

    def get_max_clips(self) -> Optional[int]:
        """Phong cách 5 cắt 4 đoạn viral."""
        return 4

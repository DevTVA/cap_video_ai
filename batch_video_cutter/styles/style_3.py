"""Style 3: Chuẩn 100% theo mẫu phong cách 3.mp4 gốc (Canvas 1:1 1080x1080):
- Top Caption: Dải Nền Vàng Tươi (Bright Yellow #FFFF00, 180px), Chữ Đen Viết Hoa Trong Ngoặc Kép "...", Căn giữa dọc 100%.
- Video Stream: Canvas 1:1 (1080x1080), Video zoom 150% CapCut style đặt từ y=180px đến y=1080px.
- Graphic Subtitles: Font Impact CapCut (85pt), Active Word Highlight MÀU ĐỎ ("red"), lề dưới 150px thoáng đẹp.
"""

from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea, HIGHLIGHT_COLOR_GREEN


class Style3(BaseStyle):
    """Phong cách 3: Canvas 1:1 Dải Nền Vàng Tiêu Đề Chữ Đen Trong Ngoặc Kép + Highlight Màu Đỏ (Chuẩn phong cách 3.mp4)."""

    CAPTION_HEIGHT_RATIO = 0.1667  # 180px / 1080px
    style_index: int = 3

    @property
    def name(self) -> str:
        return "Style 3 - 1:1 Yellow Banner Black Quote Title + Red Highlight Subtitle (Mẫu phong cách 3.mp4)"

    @property
    def aspect_ratio(self) -> str:
        return "1:1"

    def get_output_resolution(self) -> Tuple[int, int]:
        """Output 1080x1080 (1:1)."""
        return (1080, 1080)

    def get_caption_area(self) -> Optional[CaptionArea]:
        out_w, out_h = self.get_output_resolution()
        caption_h = 180
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
        out_w, out_h = self.get_output_resolution()  # 1080x1080
        caption_h = 180  # Vùng dải nền vàng phía trên (180px)
        video_area_h = 900  # Vùng video phía dưới (900px)

        if input_width <= 0 or input_height <= 0:
            input_width, input_height = 1920, 1080

        # Công thức Zoom 150% CapCut chuẩn 100% bảo toàn tỷ lệ khung hình gốc (0% méo hình)
        fit_w = out_w
        fit_h = int(input_height * (out_w / input_width))

        fg_w = int(fit_w * 1.5)
        fg_h = int(fit_h * 1.5)

        if fg_h < video_area_h:
            fg_h = video_area_h
            fg_w = int(input_width * (fg_h / input_height))

        # Căn giữa khung hình hiển thị (100% chuẩn, không bị lệch/đẩy sang trái)
        crop_x = (fg_w - out_w) // 2
        crop_y = (fg_h - video_area_h) // 2

        filters = [
            f"[0:v]scale={fg_w}:{fg_h},crop={out_w}:{video_area_h}:{crop_x}:{crop_y},"
            f"pad={out_w}:{out_h}:0:{caption_h}:black[styled]"
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
        """Màu Highlight MÀU XANH LÁ (HIGHLIGHT_COLOR_GREEN)."""
        return HIGHLIGHT_COLOR_GREEN

    def get_font_size(self) -> int:
        """Cỡ font 54pt vừa vặn cho Style 3 Canvas 1:1."""
        return 54

    def get_margin_v(self) -> int:
        """Lề dưới 100px giúp phụ đề hạ xuống vị trí chuẩn đẹp sát chân video 1:1."""
        return 100

    def get_italic_option(self) -> bool:
        return False

    def get_max_clips(self) -> Optional[int]:
        """Phong cách 3 cắt 3 đoạn viral."""
        return 3

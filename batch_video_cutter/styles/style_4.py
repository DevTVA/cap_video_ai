"""Style 4: Chuẩn 100% theo mẫu phong cách 4.mp4 gốc (Canvas 3:4 1080x1440):
- Top Caption: Single Unified White Rounded Badge (Nền Trắng Bo Góc), Chữ Đen Viết Hoa 100%, Trong Ngoặc Kép "..." ở dòng 1.
- Video Stream: Canvas 3:4 (1080x1440), Video zoom 150% CapCut style đặt cân đối ở trung tâm canvas.
- Graphic Subtitles: Font Impact CapCut (85pt), Active Word Highlight XANH LÁ ("green"), lề dưới 160px.
"""

from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea


class Style4(BaseStyle):
    """Phong cách 4: Canvas 3:4 Nền Đen + Top Single White Badge Black Quote Title + Subtitle Highlight Xanh Lá (Chuẩn phong cách 4.mp4)."""

    CAPTION_HEIGHT_RATIO = 0.1944  # 280px / 1440px

    @property
    def name(self) -> str:
        return "Style 4 - 3:4 Black Background + Top Single White Badge Quote Title + Green Highlight Subtitle (Mẫu phong cách 4.mp4)"

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
        caption_h = 280  # Vùng đen phía trên (280px)
        video_area_h = 960  # Vùng video ở giữa (960px)

        if input_width <= 0 or input_height <= 0:
            input_width, input_height = 1920, 1080

        # Scale 150% CapCut zoom chuẩn 100% theo Phong cách 1 & 2
        scale_factor = max((out_w * 1.5) / input_width, (video_area_h * 1.5) / input_height)
        fg_w = int(input_width * scale_factor)
        fg_h = int(input_height * scale_factor)

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
        """Màu Highlight MÀU XANH LÁ ("green") chuẩn 100% theo mẫu phong cách 4.mp4."""
        return "green"

    def get_font_size(self) -> int:
        """Cỡ font 85pt chuẩn CapCut."""
        return 85

    def get_italic_option(self) -> bool:
        return False

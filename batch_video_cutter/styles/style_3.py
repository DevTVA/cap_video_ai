"""Style 3: Scale 150% CapCut-style, tỷ lệ 3:4, nền đen, phần trên để caption.

Video gốc được scale 150% và đặt phía dưới canvas 3:4 (1080x1440).
Phần trên (khoảng 20% canvas) có nền đen để hiển thị caption.
"""

from typing import Optional
from .base import BaseStyle, CaptionArea


class Style3(BaseStyle):
    """Phong cách 3: 3:4 nền đen với vùng caption trên và 150% CapCut zoom."""

    CAPTION_HEIGHT_RATIO = 0.20  # 20% canvas cho caption

    @property
    def name(self) -> str:
        return "Style 3 - 3:4 Black Background + Top Caption (CapCut 150% Zoom)"

    @property
    def aspect_ratio(self) -> str:
        return "3:4"

    def get_output_resolution(self) -> tuple[int, int]:
        """Output 1080x1440 (3:4)."""
        return (1080, 1440)

    def get_caption_area(self) -> Optional[CaptionArea]:
        out_w, out_h = self.get_output_resolution()
        caption_h = int(out_h * self.CAPTION_HEIGHT_RATIO)
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
    ) -> str:
        out_w, out_h = self.get_output_resolution()
        caption_h = int(out_h * self.CAPTION_HEIGHT_RATIO)
        video_area_h = out_h - caption_h

        fit_w = out_w
        fit_h = int(input_height * (out_w / input_width))

        fg_w = int(fit_w * 1.5)
        fg_h = int(fit_h * 1.5)

        overlay_x = (out_w - fg_w) // 2
        overlay_y = caption_h + (video_area_h - fg_h) // 2

        filters = [
            f"color=black:s={out_w}x{out_h}:d=1[canvas]",
            f"[0:v]scale={fg_w}:{fg_h}[fg_scaled]",
            f"[canvas][fg_scaled]overlay={overlay_x}:{overlay_y}:shortest=1[styled]",
        ]

        if subtitle_path:
            ass_filter = self.format_ass_filter(subtitle_path)
            filters.append(f"[styled]{ass_filter}[out]")
            output_label = "[out]"
        else:
            output_label = "[styled]"


        return ";".join(filters), output_label

    def get_subtitle_position(self) -> str:
        return "top"

    def get_highlight_color(self) -> str:
        return "yellow"

    def get_italic_option(self) -> bool:
        return True


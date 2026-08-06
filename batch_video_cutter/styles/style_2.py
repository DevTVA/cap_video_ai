"""Style 2: Scale 150% CapCut-style, tỷ lệ 3:4, nền mờ blur.

Video gốc được scale 150% (phóng to 1.5 lần so với vừa khung) và đặt giữa canvas 3:4 (1080x1440).
Phần nền xung quanh là video gốc bị blur mạnh.
"""

from typing import Optional
from .base import BaseStyle


class Style2(BaseStyle):
    """Phong cách 2: 3:4 với nền blur và 150% CapCut zoom."""

    @property
    def name(self) -> str:
        return "Style 2 - 3:4 Blur Background (CapCut 150% Zoom)"

    @property
    def aspect_ratio(self) -> str:
        return "3:4"

    def get_output_resolution(self) -> tuple[int, int]:
        """Output 1080x1440 (3:4)."""
        return (1080, 1440)

    def get_ffmpeg_filter(
        self,
        input_width: int,
        input_height: int,
        subtitle_path: Optional[str] = None,
    ) -> str:
        out_w, out_h = self.get_output_resolution()

        fit_w = out_w
        fit_h = int(input_height * (out_w / input_width))

        fg_w = int(fit_w * 1.5)
        fg_h = int(fit_h * 1.5)

        overlay_x = (out_w - fg_w) // 2
        overlay_y = (out_h - fg_h) // 2

        filters = [
            f"[0:v]split=2[bg][fg]",
            f"[bg]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},"
            f"boxblur=25:5[bg_blur]",
            f"[fg]scale={fg_w}:{fg_h}[fg_scaled]",
            f"[bg_blur][fg_scaled]overlay={overlay_x}:{overlay_y}[styled]",
        ]

        if subtitle_path:
            ass_filter = self.format_ass_filter(subtitle_path)
            filters.append(f"[styled]{ass_filter}[out]")
            output_label = "[out]"
        else:
            output_label = "[styled]"


        return ";".join(filters), output_label

    def get_subtitle_position(self) -> str:
        return "bottom"

    def get_highlight_color(self) -> str:
        return "red"

    def get_font_size(self) -> int:
        """Kích thước font chữ cho Style 2 (66pt bằng tỉ lệ cỡ chữ Outcard)."""
        return 66


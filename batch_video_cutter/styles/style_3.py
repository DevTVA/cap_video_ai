"""Style 3: Scale 150% CapCut-style, tỷ lệ 3:4 (1080x1440), nền đen, phần trên hiển thị Caption Title.

Video gốc được scale 150% và đặt phía dưới canvas 3:4 (1080x1440).
Phần trên (khoảng 20% canvas = 288px) có nền đen để hiển thị Caption Title rực rỡ.
Phụ đề được đặt ở phía dưới màn hình (bottom) vô cùng thoáng đẹp.
"""

from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea


class Style3(BaseStyle):
    """Phong cách 3: 3:4 nền đen với vùng caption trên và 150% CapCut zoom."""

    CAPTION_HEIGHT_RATIO = 0.20  # 20% canvas cho caption (288px)

    @property
    def name(self) -> str:
        return "Style 3 - 3:4 Black Background + Top Caption (CapCut 150% Zoom)"

    @property
    def aspect_ratio(self) -> str:
        return "3:4"

    def get_output_resolution(self) -> Tuple[int, int]:
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
        title_text: Optional[str] = None,
    ) -> Tuple[str, str]:
        out_w, out_h = self.get_output_resolution()  # 1080x1440
        caption_h = int(out_h * self.CAPTION_HEIGHT_RATIO)  # 288px
        video_area_h = out_h - caption_h  # 1152px

        scaled_w = out_w
        scaled_h = int(input_height * (out_w / input_width)) if input_width > 0 else 1080

        fg_w = int(scaled_w * 1.5)
        fg_h = int(scaled_h * 1.5)

        crop_x = max(0, (fg_w - out_w) // 2)
        crop_y = max(0, (fg_h - video_area_h) // 2)

        # Cắt xén video đúng 1080x1152 trước khi pad 1080x1440 (tránh đứng video & tránh lỗi pad nhỏ hơn input)
        filters = [
            f"[0:v]scale={fg_w}:{fg_h},crop={out_w}:{video_area_h}:{crop_x}:{crop_y},"
            f"pad={out_w}:{out_h}:0:{caption_h}:black[styled]"
        ]
        output_label = "[styled]"

        # Render Top Caption Title màu Vàng rực rỡ ở vùng nền đen trên cùng
        if title_text:
            safe_title = (
                title_text.replace("'", "")
                .replace(":", "\\:")
                .replace("%", "\\%")
                .replace("[", "\\[")
                .replace("]", "\\]")
            )
            font_path = "C\\:/Windows/Fonts/impact.ttf"
            filters.append(
                f"[styled]drawtext=fontfile='{font_path}':text='{safe_title}':fontcolor=yellow:"
                f"fontsize=52:x=(w-text_w)/2:y=110:shadowcolor=black:shadowx=3:shadowy=3[styled_title]"
            )
            output_label = "[styled_title]"

        if subtitle_path:
            ass_filter = self.format_ass_filter(subtitle_path)
            last_lbl = output_label.strip("[]")
            filters.append(f"[{last_lbl}]{ass_filter}[out]")
            output_label = "[out]"

        return ";".join(filters), output_label

    def get_subtitle_position(self) -> str:
        return "bottom"

    def get_highlight_color(self) -> str:
        return "yellow"

    def get_italic_option(self) -> bool:
        return False

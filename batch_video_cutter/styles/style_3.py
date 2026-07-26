"""Style 3: Scale 150% CapCut-style, tỷ lệ 3:4 (1080x1440), nền đen, phần trên hiển thị Top Caption Title.

Video gốc được scale 150% và đặt phía dưới canvas 3:4 (1080x1440).
Phần trên (khoảng 20% canvas = 288px) có nền đen để hiển thị Caption Title rực rỡ (tự động xuống dòng 2-3 dòng không bao giờ tràn khung).
Phụ đề được đặt ở phía dưới màn hình (bottom) vô cùng thoáng đẹp, không bị đè nhau.
"""

import textwrap
from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea


def format_top_caption_title(title_text: str, max_words: int = 9, max_width: int = 24) -> str:
    """Tự động giới hạn tiêu đề Top Caption tối đa 8-10 từ và chia thành các dòng ngắn gọn gàng."""
    if not title_text:
        return ""
    clean_t = title_text.strip()
    words = clean_t.split()
    if len(words) > max_words:
        clean_t = " ".join(words[:max_words])
    lines = textwrap.wrap(clean_t, width=max_width)
    lines = lines[:3]  # Giới hạn tối đa 3 dòng ngắn
    return "\n".join(lines)


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

        if input_width <= 0 or input_height <= 0:
            input_width, input_height = 1920, 1080

        # Đảm bảo scale_factor luôn lớn hơn hoặc bằng target crop cho MỌI resolution video (16:9, 9:16, 1:1, v.v.)
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

        # Render Top Caption Title màu Vàng rực rỡ ở vùng nền đen trên cùng (Tự động xuống dòng chuẩn 100%)
        if title_text:
            formatted_title = format_top_caption_title(title_text, max_width=24)
            safe_title = (
                formatted_title.replace("'", "")
                .replace(":", "\\:")
                .replace("%", "\\%")
                .replace("[", "\\[")
                .replace("]", "\\]")
            )
            font_path = "C\\:/Windows/Fonts/impact.ttf"
            # Cân chỉnh y=75 và line_spacing=12 cho 2-3 dòng tiêu đề vừa vặn trong dải 288px nền đen
            filters.append(
                f"[styled]drawtext=fontfile='{font_path}':text='{safe_title}':fontcolor=yellow:"
                f"fontsize=46:line_spacing=12:x=(w-text_w)/2:y=75:shadowcolor=black:shadowx=3:shadowy=3[styled_title]"
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

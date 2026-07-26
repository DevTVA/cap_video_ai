"""Style 3: Chuẩn 100% Zoom & Phụ đề Phong cách 1, tỷ lệ 3:4 (1080x1440), Nền đen, Top Caption chữ TRẮNG rực rỡ.

Video gốc được scale 150% chuẩn xác theo Phong cách 1 (không bị mất bối cảnh video), đặt trên nền đen canvas 3:4 (1080x1440).
Phần trên (dải 288px) hiển thị tiêu đề Top Caption màu TRẮNG tinh tế, sang trọng (tối đa 8-10 từ, xuống dòng tự động).
Phụ đề đồ họa & Highlight xanh lá CapCut lấy chuẩn 100% theo Phong cách 1, hiển thị ở phía dưới màn hình (bottom).
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
    """Phong cách 3: Chuẩn Zoom & Phụ đề Phong cách 1 trên Canvas 3:4 Nền Đen + Top Caption Chữ Trắng."""

    CAPTION_HEIGHT_RATIO = 0.20  # 20% canvas cho caption (288px)

    @property
    def name(self) -> str:
        return "Style 3 - 3:4 Black Background + Top White Caption (CapCut 150% Zoom)"

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

        # LẤY CHUẨN 100% CÔNG THỨC SCALING ZOOM 150% CỦA PHONG CÁCH 1:
        # Tính kích thước vừa khung width 1080
        fit_w = out_w
        fit_h = int(input_height * (out_w / input_width))

        # Phóng to 150% đúng chuẩn CapCut Phong cách 1
        fg_w = int(fit_w * 1.5)
        fg_h = int(fit_h * 1.5)

        overlay_x = (out_w - fg_w) // 2
        overlay_y = caption_h + (video_area_h - fg_h) // 2

        filters = [
            f"color=c=black:s={out_w}x{out_h}:r=30[canvas]",
            f"[0:v]scale={fg_w}:{fg_h}[fg_scaled]",
            f"[canvas][fg_scaled]overlay={overlay_x}:{overlay_y}:shortest=1[styled]",
        ]
        output_label = "[styled]"

        # Render Top Caption Title CHỮ MÀU TRẮNG sang trọng ở vùng nền đen trên cùng (8-10 từ, xuống dòng tự động)
        if title_text:
            formatted_title = format_top_caption_title(title_text, max_words=9, max_width=24)
            safe_title = (
                formatted_title.replace("'", "")
                .replace(":", "\\:")
                .replace("%", "\\%")
                .replace("[", "\\[")
                .replace("]", "\\]")
            )
            font_path = "C\\:/Windows/Fonts/impact.ttf"
            filters.append(
                f"[styled]drawtext=fontfile='{font_path}':text='{safe_title}':fontcolor=white:"
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
        """Lấy chuẩn 100% màu Highlight Phong cách 1 ("green")."""
        return "green"

    def get_font_size(self) -> int:
        """Lấy chuẩn 100% cỡ font Phong cách 1 (85pt)."""
        return 85

    def get_italic_option(self) -> bool:
        """Lấy chuẩn 100% không nghiêng chữ giống Phong cách 1."""
        return False

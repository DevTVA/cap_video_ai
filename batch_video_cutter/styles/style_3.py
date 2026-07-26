"""Style 3: Layout 3 vùng cân đối (1080x1440 - 3:4 ratio):
- Vùng trên (240px nền đen): Top Caption Title CHỮ VIẾT HOA 100%, KHÔNG EMOJI (tránh ô vuông), chữ TRẮNG nổi bật, căn giữa dọc 100%.
- Vùng giữa (960px): Video stream zoom 150% CapCut style đặt ở giữa cân đối (không che khuất nhân vật).
- Vùng dưới (240px nền đen): Chứa phụ đề đồ họa & active word highlight.
"""

import re
import textwrap
from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea


def strip_emojis(text: str) -> str:
    """Loại bỏ hoàn toàn tất cả biểu tượng emoji để tránh hiển thị ô vuông 🔲 trên font Impact."""
    if not text:
        return ""
    pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"
        "\u2600-\u27BF"
        "\u2300-\u23FF"
        "\u2B00-\u2BFF"
        "\u2000-\u206F"
        "\uFE00-\uFE0F"
        "]+",
        flags=re.UNICODE,
    )
    clean = pattern.sub("", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def format_top_caption_title(title_text: str, max_words: int = 9, max_width: int = 24) -> str:
    """Loại bỏ emoji, viết HOA toàn bộ và chia dòng tiêu đề ngắn gọn (8-9 từ)."""
    if not title_text:
        return ""
    clean_t = strip_emojis(title_text).upper()
    words = clean_t.split()
    if len(words) > max_words:
        clean_t = " ".join(words[:max_words])
    lines = textwrap.wrap(clean_t, width=max_width)
    lines = lines[:3]  # Tối đa 3 dòng ngắn
    return "\n".join(lines)


class Style3(BaseStyle):
    """Phong cách 3: Layout 3 vùng đối xứng 3:4 (Top black 240px, Middle video 960px, Bottom black 240px)."""

    CAPTION_HEIGHT_RATIO = 0.1667  # 240px / 1440px = 1/6

    @property
    def name(self) -> str:
        return "Style 3 - 3:4 Balanced Layout + Top White Upper Caption (No Emoji)"

    @property
    def aspect_ratio(self) -> str:
        return "3:4"

    def get_output_resolution(self) -> Tuple[int, int]:
        """Output 1080x1440 (3:4)."""
        return (1080, 1440)

    def get_caption_area(self) -> Optional[CaptionArea]:
        out_w, out_h = self.get_output_resolution()
        caption_h = 240
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
        caption_h = 240  # Vùng đen trên cùng (240px)
        video_area_h = 960  # Vùng video ở giữa (960px)

        if input_width <= 0 or input_height <= 0:
            input_width, input_height = 1920, 1080

        # Phóng đại 150% CapCut zoom chuẩn 100% theo Phong cách 1 & 2
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

        # Render Top Caption Title CHỮ VIẾT HOA 100%, KHÔNG EMOJI, MÀU TRẮNG sang trọng (Căn giữa dọc y=(240-text_h)/2)
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
                f"fontsize=46:line_spacing=12:x=(w-text_w)/2:y=(240-text_h)/2:shadowcolor=black:shadowx=3:shadowy=3[styled_title]"
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
        """Màu Highlight Phong cách 1 ("green")."""
        return "green"

    def get_font_size(self) -> int:
        """Cỡ font Phong cách 1 (85pt)."""
        return 85

    def get_italic_option(self) -> bool:
        return False

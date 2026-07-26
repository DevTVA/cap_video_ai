"""Style 3: Layout 3 vùng chuẩn mẫu ảnh 100% (Canvas 3:4 1080x1440):
- Top Caption: Badge Nền Trắng Bo Góc + Chữ Đen Viết Hoa 100%, KHÔNG EMOJI (loại bỏ 100% ô vuông), căn giữa dọc 100% trong dải 280px nền đen phía trên.
- Video Stream: Zoom 150% CapCut style căn giữa dọc ở trung tâm canvas 3:4.
- Graphic Subtitles: Font Impact 100pt (tương đương cỡ 15 CapCut), Active Word Highlight Xanh Lá, lề dưới 160px thoáng đẹp.
"""

from typing import Optional, Tuple
from .base import BaseStyle, CaptionArea


class Style3(BaseStyle):
    """Phong cách 3: Canvas 3:4 Nền Đen + Top Caption Badge Nền Trắng Chữ Đen + Phụ đề CapCut 100pt."""

    CAPTION_HEIGHT_RATIO = 0.1944  # 280px / 1440px

    @property
    def name(self) -> str:
        return "Style 3 - 3:4 Black Background + Top White Badge Black Text Caption (No Emoji)"

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

        # Phóng đại 150% CapCut zoom chuẩn 100% theo Phong cách 1 & 2
        fit_w = out_w
        fit_h = int(input_height * (out_w / input_width))

        fg_w = int(fit_w * 1.5)
        fg_h = int(fit_h * 1.5)

        overlay_x = (out_w - fg_w) // 2
        overlay_y = (out_h - fg_h) // 2  # Căn giữa dọc video ở trung tâm canvas 3:4

        filters = [
            f"color=c=black:s={out_w}x{out_h}:r=30[canvas]",
            f"[0:v]scale={fg_w}:{fg_h}[fg_scaled]",
            f"[canvas][fg_scaled]overlay={overlay_x}:{overlay_y}:shortest=1[styled]",
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
        """Màu Highlight Phong cách 1 ("green")."""
        return "green"

    def get_font_size(self) -> int:
        """Cỡ font 100pt chuẩn tương đương cỡ 15 trong CapCut."""
        return 100

    def get_italic_option(self) -> bool:
        return False

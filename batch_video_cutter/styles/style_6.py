"""Style 6: 9:16 Full Vertical Viral Shorts (TikTok / Reels / YouTube Shorts).

Video tỷ lệ dọc 9:16 (1080x1920) chuẩn hiển thị toàn màn hình điện thoại.
Nền video gốc được làm mờ (boxblur) và video chính đặt ở trung tâm kèm zoom nhẹ,
áp dụng 100% mẫu và vị trí phụ đề chuẩn hóa toàn hệ thống (Safe Zone TikTok margin_v=330px).
"""

from typing import Optional
from .base import BaseStyle, HIGHLIGHT_COLOR_BLUE


class Style6(BaseStyle):
    """Phong cách 6: 9:16 Full Vertical Viral Shorts với nền mờ và video trung tâm."""

    style_index: int = 6

    @property
    def name(self) -> str:
        return "Style 6 - 9:16 Full Vertical Viral Shorts (TikTok / Reels)"

    @property
    def aspect_ratio(self) -> str:
        return "9:16"

    def get_output_resolution(self) -> tuple[int, int]:
        """Output Full HD dọc 1080x1920 (9:16)."""
        return (1080, 1920)

    def get_ffmpeg_filter(
        self,
        input_width: int,
        input_height: int,
        subtitle_path: Optional[str] = None,
    ) -> str:
        out_w, out_h = self.get_output_resolution()

        # Tính kích thước vừa khung width 1080 cho foreground
        fg_w = out_w
        fg_h = int(input_height * (out_w / input_width))

        # Đặt foreground căn giữa theo chiều dọc
        overlay_x = (out_w - fg_w) // 2
        overlay_y = (out_h - fg_h) // 2

        filters = [
            f"[0:v]split=2[bg][fg]",
            f"[bg]scale=270:480:force_original_aspect_ratio=increase,"
            f"crop=270:480,"
            f"boxblur=15:2,"
            f"scale={out_w}:{out_h}[bg_blur]",
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

    def get_intro_offset(self) -> float:
        """Bỏ qua 3.0 giây intro video gốc."""
        return 3.0

    def get_outro_offset(self) -> float:
        """Bỏ qua 25.0 giây cuối video gốc."""
        return 25.0

    def get_max_clips(self) -> Optional[int]:
        """Cắt tối đa 3 clips viral."""
        return 3

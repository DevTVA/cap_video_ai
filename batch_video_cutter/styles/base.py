"""Base style class.

Abstract class định nghĩa interface cho các phong cách video.
Mỗi phong cách cần implement FFmpeg filter chain riêng.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


HIGHLIGHT_COLOR_GREEN: str = "green"
HIGHLIGHT_COLOR_YELLOW: str = "yellow"
HIGHLIGHT_COLOR_RED: str = "red"
HIGHLIGHT_COLOR_BLUE: str = "blue"


@dataclass
class CaptionArea:
    """Vùng hiển thị caption trên video.

    Attributes:
        x: Tọa độ x bắt đầu.
        y: Tọa độ y bắt đầu.
        width: Chiều rộng vùng caption.
        height: Chiều cao vùng caption.
        position: "top" hoặc "bottom".
    """
    x: int
    y: int
    width: int
    height: int
    position: str = "top"


class BaseStyle(ABC):
    """Abstract base class cho các phong cách video.

    Mỗi phong cách cần implement:
    - get_ffmpeg_filter(): Trả về filter chain cho FFmpeg
    - get_output_resolution(): Kích thước output
    - get_caption_area(): Vùng caption (nếu có)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên phong cách."""
        ...

    @property
    @abstractmethod
    def aspect_ratio(self) -> str:
        """Tỷ lệ khung hình (ví dụ: '1:1', '3:4')."""
        ...

    @abstractmethod
    def get_output_resolution(self) -> tuple[int, int]:
        """Trả về resolution output (width, height).

        Returns:
            Tuple (width, height) pixels.
        """
        ...

    @abstractmethod
    def get_ffmpeg_filter(
        self,
        input_width: int,
        input_height: int,
        subtitle_path: Optional[str] = None,
    ) -> str:
        """Trả về FFmpeg filter_complex string.

        Args:
            input_width: Chiều rộng video gốc.
            input_height: Chiều cao video gốc.
            subtitle_path: Đường dẫn file .ass subtitle (nếu có).

        Returns:
            FFmpeg filter_complex string.
        """
        ...

    def get_caption_area(self) -> Optional[CaptionArea]:
        """Trả về vùng caption (nếu phong cách có vùng caption riêng).

        Returns:
            CaptionArea hoặc None nếu không có vùng caption riêng.
        """
        return None

    def get_subtitle_position(self) -> str:
        """Vị trí phụ đề mặc định.

        Returns:
            "top" hoặc "bottom".
        """
        return "bottom"

    def get_font_name(self) -> str:
        """Tên font chữ mặc định cho style."""
        return "Impact"

    def get_font_size(self) -> int:
        """Kích thước font chữ chuẩn hóa toàn hệ thống (66pt tỉ lệ chuẩn nét cao)."""
        return 66

    def get_margin_v(self) -> int:
        """Khoảng cách lề dưới phụ đề chuẩn hóa cho toàn bộ Style.

        Tự động cân đối theo chiều cao Canvas để nằm trong Safe Zone của TikTok / Shorts / Reels:
        - Canvas 1:1 (h <= 1080): 110px
        - Canvas 3:4 (h == 1440): 160px
        - Canvas 9:16 (h >= 1920): 330px
        """
        _, h = self.get_output_resolution()
        if h >= 1920:
            return 330
        elif h >= 1440:
            return 160
        return 110


    def get_highlight_color(self) -> str:
        """Màu Highlight từ active chuẩn hóa ("yellow" - Vàng tươi neon #FFE600 nổi bật trên hộp nền Pill Box)."""
        return HIGHLIGHT_COLOR_YELLOW

    def get_italic_option(self) -> bool:
        """Có nghiêng chữ (Italic Slant) hay không."""
        return False

    def get_max_clips(self) -> Optional[int]:
        """Số lượng clip viral tối đa cần cắt cho style này (mặc định 2)."""
        return 2

    def get_intro_offset(self) -> float:
        """Số giây đầu cần bỏ qua (intro video gốc)."""
        return 35.0

    def get_outro_offset(self) -> float:
        """Số giây cuối cần bỏ qua (outro/outcard video gốc)."""
        return 25.0


    def format_ass_filter(self, subtitle_path: str) -> str:
        """Tạo chuỗi filter ass='path':fontsdir='fonts_dir' cho FFmpeg."""
        from pathlib import Path
        fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
        safe_path = subtitle_path.replace("\\", "/").replace(":", "\\:")
        if fonts_dir.exists():
            safe_fonts_dir = str(fonts_dir.resolve()).replace("\\", "/").replace(":", "\\:")
            return f"ass='{safe_path}':fontsdir='{safe_fonts_dir}'"
        return f"ass='{safe_path}'"



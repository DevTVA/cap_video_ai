"""Helper utilities.

Chuyển đổi timecode, kiểm tra file, xử lý đường dẫn.
Sử dụng pathlib cho mọi thao tác đường dẫn (theo rule tool-design.md).
"""

import re
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger


def parse_timecode(timecode: str) -> float:
    """Chuyển timecode string thành giây (float).

    Hỗ trợ các format:
        - "03:39" (mm:ss) → 219.0
        - "1:03:39" (h:mm:ss) → 3819.0
        - "03:39.500" (mm:ss.ms) → 219.5
        - "219.5" (giây thuần) → 219.5

    Args:
        timecode: Chuỗi timecode.

    Returns:
        Số giây tương ứng.

    Raises:
        ValueError: Nếu format không hợp lệ.
    """
    timecode = timecode.strip()

    # Thử parse giây thuần trước
    try:
        return float(timecode)
    except ValueError:
        pass

    # Parse mm:ss hoặc h:mm:ss (có thể có .ms)
    pattern = r"^(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:\.(\d+))?$"
    match = re.match(pattern, timecode)
    if not match:
        raise ValueError(f"Timecode không hợp lệ: '{timecode}'. "
                         f"Hỗ trợ: mm:ss, h:mm:ss, mm:ss.ms, hoặc giây thuần.")

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    ms_str = match.group(4) or "0"
    milliseconds = int(ms_str) / (10 ** len(ms_str))

    return hours * 3600 + minutes * 60 + seconds + milliseconds


def format_timecode(seconds: float) -> str:
    """Chuyển giây thành timecode string mm:ss.

    Args:
        seconds: Số giây.

    Returns:
        Chuỗi timecode "mm:ss".
    """
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def format_timecode_hms(seconds: float) -> str:
    """Chuyển giây thành timecode string h:mm:ss.fff cho FFmpeg.

    Args:
        seconds: Số giây.

    Returns:
        Chuỗi timecode "h:mm:ss.fff".
    """
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:06.3f}"


def validate_video(video_path: Path) -> bool:
    """Kiểm tra file video có hợp lệ không bằng ffprobe.

    Args:
        video_path: Đường dẫn tới file video.

    Returns:
        True nếu file video hợp lệ, False nếu không.
    """
    if not video_path.exists():
        logger.warning(f"File không tồn tại: {video_path}")
        return False

    if not video_path.is_file():
        logger.warning(f"Không phải file: {video_path}")
        return False

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning(f"Không thể kiểm tra video: {video_path}")
        return False


def get_video_duration(video_path: Path) -> Optional[float]:
    """Lấy thời lượng video bằng ffprobe.

    Args:
        video_path: Đường dẫn tới file video.

    Returns:
        Thời lượng tính bằng giây, hoặc None nếu lỗi.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    logger.warning(f"Không thể lấy duration: {video_path}")
    return None


def get_video_resolution(video_path: Path) -> Optional[tuple[int, int]]:
    """Lấy resolution (width, height) của video.

    Args:
        video_path: Đường dẫn tới file video.

    Returns:
        Tuple (width, height) hoặc None nếu lỗi.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("x")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    logger.warning(f"Không thể lấy resolution: {video_path}")
    return None


def sanitize_filename(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file.

    Args:
        name: Tên file gốc.

    Returns:
        Tên file đã sanitize.
    """
    # Loại bỏ ký tự không hợp lệ cho Windows
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()

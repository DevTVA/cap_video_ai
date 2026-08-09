"""FFmpeg availability checker.

Kiểm tra FFmpeg đã cài đặt và có trong PATH chưa.
Nếu chưa → hướng dẫn cài đặt rõ ràng.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def get_ffmpeg_path() -> Optional[Path]:
    """Tìm FFmpeg binary trong PATH.

    Returns:
        Path tới ffmpeg.exe nếu tìm thấy, None nếu không.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return Path(ffmpeg_path)
    return None


def get_ffprobe_path() -> Optional[Path]:
    """Tìm FFprobe binary trong PATH.

    Returns:
        Path tới ffprobe.exe nếu tìm thấy, None nếu không.
    """
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return Path(ffprobe_path)
    return None


def get_ffmpeg_version(ffmpeg_path: Path) -> str:
    """Lấy version string của FFmpeg.

    Args:
        ffmpeg_path: Đường dẫn tới ffmpeg binary.

    Returns:
        Version string (ví dụ: "ffmpeg version 6.1.1").
    """
    try:
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first_line = result.stdout.strip().split("\n")[0]
        return first_line
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return "unknown"


def check_ffmpeg() -> tuple[Path, Path]:
    """Kiểm tra FFmpeg và FFprobe có sẵn trong hệ thống.

    Returns:
        Tuple (ffmpeg_path, ffprobe_path).

    Raises:
        SystemExit: Nếu FFmpeg hoặc FFprobe không tìm thấy.
    """
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()

    if not ffmpeg_path or not ffprobe_path:
        missing = []
        if not ffmpeg_path:
            missing.append("ffmpeg")
        if not ffprobe_path:
            missing.append("ffprobe")

        logger.error(f"Không tìm thấy {', '.join(missing)} trong PATH!")
        logger.error("")
        logger.error("=== HƯỚNG DẪN CÀI ĐẶT FFMPEG ===")
        logger.error("")
        logger.error("Windows:")
        logger.error("  1. Tải từ https://www.gyan.dev/ffmpeg/builds/")
        logger.error("  2. Giải nén vào C:\\ffmpeg")
        logger.error("  3. Thêm C:\\ffmpeg\\bin vào biến môi trường PATH")
        logger.error("  4. Khởi động lại terminal")
        logger.error("")
        logger.error("Hoặc dùng winget:")
        logger.error("  winget install Gyan.FFmpeg")
        logger.error("")
        logger.error("Hoặc dùng choco:")
        logger.error("  choco install ffmpeg")
        sys.exit(1)

    version = get_ffmpeg_version(ffmpeg_path)
    logger.info(f"FFmpeg OK: {version}")
    logger.info(f"  ffmpeg:  {ffmpeg_path}")
    logger.info(f"  ffprobe: {ffprobe_path}")

    return ffmpeg_path, ffprobe_path


_CACHED_ENCODER = None


def detect_gpu_encoder() -> Optional[str]:
    """Kiểm tra FFmpeg hỗ trợ GPU encoder nào (h264_nvenc, h264_qsv, h264_amf)."""
    global _CACHED_ENCODER
    if _CACHED_ENCODER is not None:
        return _CACHED_ENCODER

    try:
        res = subprocess.run(
            ["ffmpeg", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        output = res.stdout.lower()
        if "h264_nvenc" in output:
            _CACHED_ENCODER = "h264_nvenc"
        elif "h264_qsv" in output:
            _CACHED_ENCODER = "h264_qsv"
        elif "h264_amf" in output:
            _CACHED_ENCODER = "h264_amf"
        else:
            _CACHED_ENCODER = None
    except Exception as e:
        logger.warning(f"Không thể kiểm tra GPU encoders từ FFmpeg: {e}")
        _CACHED_ENCODER = None

    return _CACHED_ENCODER


def get_best_video_encoder(enable_gpu: bool = True, cpu_preset: str = "superfast") -> tuple[str, list[str]]:
    """Trả về encoder và flags tối ưu nhất dựa trên phần cứng."""
    if enable_gpu:
        gpu = detect_gpu_encoder()
        if gpu == "h264_nvenc":
            logger.info("Sử dụng GPU Hardware Acceleration: NVIDIA NVENC (h264_nvenc)")
            return "h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22"]
        elif gpu == "h264_qsv":
            logger.info("Sử dụng GPU Hardware Acceleration: Intel QSV (h264_qsv)")
            return "h264_qsv", ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "22"]
        elif gpu == "h264_amf":
            logger.info("Sử dụng GPU Hardware Acceleration: AMD AMF (h264_amf)")
            return "h264_amf", ["-c:v", "h264_amf", "-quality", "speed"]

    logger.info(f"Sử dụng CPU Software Encoder (libx264 - {cpu_preset})")
    return "libx264", ["-c:v", "libx264", "-preset", cpu_preset, "-crf", "22"]


if __name__ == "__main__":
    check_ffmpeg()


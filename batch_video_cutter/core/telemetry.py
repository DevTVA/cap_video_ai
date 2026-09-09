"""Granular Telemetry & Profiling Module for Video Processing Pipeline.

Measures micro-timings per clip:
Total = T_sub_parse + T_whisper + T_align + T_pillow + T_png_io + T_ffmpeg
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any
from loguru import logger


@dataclass
class ClipTelemetry:
    """Detailed micro-timings for a single clip rendering pipeline."""
    folder_name: str = ""
    clip_idx: int = 1
    clip_filename: str = ""
    duration_sec: float = 0.0
    style_name: str = ""

    t_sub_parse: float = 0.0
    t_whisper: float = 0.0
    t_align: float = 0.0
    t_pillow_draw: float = 0.0
    t_png_io: float = 0.0
    t_ffmpeg: float = 0.0
    t_total: float = 0.0

    align_mode: str = "auto"
    timestamp_source: str = "whisper"
    whisper_cached: bool = False
    frames_rendered: int = 0

    def calculate_total(self) -> float:
        self.t_total = (
            self.t_sub_parse +
            self.t_whisper +
            self.t_align +
            self.t_pillow_draw +
            self.t_png_io +
            self.t_ffmpeg
        )
        return self.t_total

    def format_report(self) -> str:
        speed_factor = (self.duration_sec / self.t_total) if self.t_total > 0 else 0.0
        lines = [
            f"📊 CLIP TELEMETRY: {self.clip_filename} ({self.duration_sec:.1f}s - {self.style_name})",
            f"  - Subtitle Discovery / Parse : {self.t_sub_parse:.3f}s",
            f"  - Whisper Transcribe         : {self.t_whisper:.3f}s ({'Cache Hit / Skipped' if self.whisper_cached or self.t_whisper == 0 else 'Fresh'})",
            f"  - Subtitle Alignment         : {self.t_align:.3f}s (Source: {self.timestamp_source} | Mode: {self.align_mode})",
            f"  - Pillow Drawing             : {self.t_pillow_draw:.3f}s ({self.frames_rendered} frames)",
            f"  - PNG Disk Encoding & I/O    : {self.t_png_io:.3f}s (compress_level=1)",
            f"  - FFmpeg Decode/Filter/Encode: {self.t_ffmpeg:.3f}s",
            f"  ──────────────────────────────────────",
            f"  * TOTAL CLIP TIME            : {self.t_total:.3f}s (Tốc độ: {speed_factor:.2f}x real-time)",
        ]
        return "\n".join(lines)

    def log(self):
        logger.info("\n" + self.format_report())

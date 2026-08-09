"""Core video cutting and rendering engine using FFmpeg.

Frame-accurate video cutting, filter application, subtitle burning, and rendering.
Complies with tool-design.md rules for process safety, temporary file cleanup, and path handling.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from ..styles.base import BaseStyle
from ..utils.helpers import get_video_resolution, format_timecode_hms


def cut_and_render_clip(
    video_path: Path,
    start_time: float,
    end_time: float,
    output_path: Path,
    style: BaseStyle,
    subtitle_path: Optional[Path] = None,
    emoji_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    timed_emojis: Optional[list] = None,
    audio_volume: float = 1.3,
    outcard_path: Optional[Path] = None,
    title_text: Optional[str] = None,
) -> Path:
    """Cắt và render clip từ video gốc: tăng âm lượng 1.3x và đè outcard.mp4 ở cuối (âm thanh gốc xuống 0 trong phần outcard, chỉ phát âm thanh outcard)."""
    video_path = Path(video_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Tự động phát hiện outcard.mp4 nếu chưa truyền
    if outcard_path is None or not Path(outcard_path).exists():
        candidates = [
            Path(r"E:\cap_video\outcard.mp4"),
            Path(r"E:\output\outcard.mp4"),
            Path(r"e:\AI_Agent\outcard.mp4"),
            Path(__file__).parent.parent.parent / "outcard.mp4",
            Path.cwd() / "outcard.mp4",
        ]
        for p in candidates:
            if p.exists():
                outcard_path = p.resolve()
                break

    duration = end_time - start_time
    if duration <= 0:
        raise ValueError(f"Duration không hợp lệ: start={start_time}, end={end_time}")

    # Lấy resolution video gốc
    res = get_video_resolution(video_path)
    if not res:
        in_w, in_h = 1920, 1080
        logger.warning(f"Không lấy được resolution của {video_path.name}, mặc định 1920x1080")
    else:
        in_w, in_h = res

    # Lấy filter complex từ style (có nạp title_text nếu phong cách yêu cầu Top Caption)
    sub_str = str(subtitle_path.resolve()) if subtitle_path and subtitle_path.exists() else None
    
    # Kiểm tra xem get_ffmpeg_filter của style có nhận title_text không
    import inspect
    sig = inspect.signature(style.get_ffmpeg_filter)
    if "title_text" in sig.parameters:
        filter_complex, output_label = style.get_ffmpeg_filter(in_w, in_h, sub_str, title_text)
    else:
        filter_complex, output_label = style.get_ffmpeg_filter(in_w, in_h, sub_str)

    # Chuyển đổi timestamp
    start_hms = format_timecode_hms(start_time)
    duration_hms = format_timecode_hms(duration)

    inputs = [
        "-ss", start_hms,
        "-i", str(video_path),
    ]
    current_input_idx = 1

    outcard_dur = 2.113
    outcard_start_s = max(0.0, duration - outcard_dur) if (outcard_path and Path(outcard_path).exists()) else None

    # Render Graphic Subtitle PNG Layer (Text + Color Emoji màu) hoặc Emoji PNG đơn lẻ
    if timed_emojis:
        last_label = output_label.strip("[]")
        for idx, item in enumerate(timed_emojis):
            png_path = item[0]
            start_s = item[1]
            end_s = item[2]
            png_p = Path(png_path).resolve()
            if not png_p.exists():
                continue

            is_top_caption = "top_caption" in png_p.name
            if outcard_start_s is not None and not is_top_caption:
                if start_s >= outcard_start_s:
                    continue
                end_s = min(end_s, outcard_start_s)

            inputs.extend(["-i", str(png_p)])
            out_label = f"v_out_{current_input_idx}"

            if len(item) == 3:
                # Graphic Subtitle Layer PNG 1080x1080 chứa Chữ + Highlight + HD Color Emoji
                filter_complex += (
                    f";[{last_label}][{current_input_idx}:v]overlay="
                    f"0:0:enable='between(t,{start_s:.3f},{end_s:.3f})'[{out_label}]"
                )
            else:
                x_pos = item[3]
                y_pos = item[4]
                scaled_label = f"e_img_{current_input_idx}"
                filter_complex += (
                    f";[{current_input_idx}:v]scale=65:65[{scaled_label}]"
                    f";[{last_label}][{scaled_label}]overlay="
                    f"x={x_pos}:y={y_pos}:"
                    f"enable='between(t,{start_s:.3f},{end_s:.3f})'[{out_label}]"
                )

            last_label = out_label
            current_input_idx += 1
        output_label = f"[{last_label}]"

    # Xử lý Outcard & Audio (Tăng âm lượng 1.3x, đè outcard ở cuối và tắt âm thoại khi outcard chạy)
    audio_label = "[a_final]"
    last_v_label = output_label.strip("[]")

    if outcard_path and Path(outcard_path).exists():
        outcard_p = Path(outcard_path).resolve()
        inputs.extend(["-i", str(outcard_p)])
        outcard_input_idx = current_input_idx
        current_input_idx += 1

        outcard_dur = 2.113
        outcard_start_s = max(0.0, duration - outcard_dur)
        outcard_overlay_y = max(0, (style.get_output_resolution()[1] - 1080) // 2)

        # Video overlay outcard dùng colorkey=black:0.15:0.1 tách nền đen ra trong suốt 100%, giữ nguyên 100% màu sắc tự nhiên của video gốc
        outcard_v_scaled = "outcard_v_scaled"
        outcard_v_out = "v_outcard_final"
        filter_complex += (
            f";[{outcard_input_idx}:v]scale=1080:1080:force_original_aspect_ratio=decrease,"
            f"pad=1080:1080:(1080-iw)/2:(1080-ih)/2:black,colorkey=black:0.15:0.1[{outcard_v_scaled}]"
            f";[{last_v_label}][{outcard_v_scaled}]overlay=x=0:y={outcard_overlay_y}:enable='gte(t,{outcard_start_s:.3f})'[{outcard_v_out}]"
        )
        output_label = f"[{outcard_v_out}]"

        # Audio stream: Tăng âm lượng thoại gốc 1.3x, tắt về 0 khi outcard chạy, phát âm thanh outcard
        filter_complex += (
            f";[0:a]volume=eval=frame:volume='if(gte(t,{outcard_start_s:.3f}),0,{audio_volume:.2f})'[a_main_vol]"
            f";[{outcard_input_idx}:a]adelay=delays={int(outcard_start_s * 1000)}:all=1[a_outcard_delay]"
            f";[a_main_vol][a_outcard_delay]amix=inputs=2:duration=first[a_final]"
        )
    else:
        # Tăng âm lượng video gốc lên 1.3x
        filter_complex += f";[0:a]volume={audio_volume:.2f}[a_final]"

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-t", duration_hms,
        "-filter_complex", filter_complex,
        "-map", output_label,
        "-map", audio_label,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


    logger.info(f"Bắt đầu render clip: {output_path.name} ({duration:.1f}s, {style.name})")
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        _, stderr_output = process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg render lỗi (returncode {process.returncode}):\n{stderr_output}")
            raise RuntimeError(f"FFmpeg render thất bại cho file {output_path.name}")

        logger.info(f"Render hoàn tất: {output_path.name}")
        return output_path

    except Exception as e:
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass
        raise e

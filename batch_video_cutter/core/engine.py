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


from ..utils.ffmpeg_check import get_best_video_encoder


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
    enable_gpu: bool = True,
    cpu_preset: str = "superfast",
    threads: int = 4,
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

    # Ưu tiên hoàn toàn luồng ảnh PNG (nếu có), cấm nạp file ASS cũ để tránh đè lớp kép
    if timed_emojis:
        sub_str = None
    else:
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

    inputs = []
    if enable_gpu:
        inputs.extend(["-hwaccel", "auto"])
    inputs.extend([
        "-ss", start_hms,
        "-i", str(video_path),
    ])
    current_input_idx = 1

    outcard_dur = 2.113
    outcard_start_s = max(0.0, duration - outcard_dur) if (outcard_path and Path(outcard_path).exists()) else None

    # Render Graphic Subtitle PNG Layer (Text + Color Emoji màu) qua Concat Manifest hoặc Emoji PNG đơn lẻ
    if timed_emojis:
        from ..utils.graphic_subtitle import generate_concat_manifest

        last_label = output_label.strip("[]")
        
        # Bước 2: Chuẩn hóa fps=30 cố định cho luồng video chính ngay trước khi overlay
        filter_complex += f";[{last_label}]fps=30[v_fps_norm]"
        last_label = "v_fps_norm"

        karaoke_items = []
        other_items = []

        for item in timed_emojis:
            if not item or not Path(item[0]).exists():
                continue
            png_name = Path(item[0]).name
            if len(item) == 3 and "top_caption" not in png_name:
                karaoke_items.append(item)
            else:
                other_items.append(item)

        # Bước 1: Dùng concat demuxer cho toàn bộ PNG Karaoke để chỉ overlay 1 lần duy nhất
        if karaoke_items:
            tmp_sub_dir = Path(karaoke_items[0][0]).parent
            manifest_path = generate_concat_manifest(
                graphic_results=karaoke_items,
                tmp_dir=tmp_sub_dir,
                canvas_size=style.get_output_resolution(),
                outcard_start_s=outcard_start_s,
                clip_duration=duration,
            )

            inputs.extend(["-f", "concat", "-safe", "0", "-i", str(manifest_path.resolve())])
            concat_input_idx = current_input_idx
            current_input_idx += 1

            out_label = f"v_out_concat"
            filter_complex += (
                f";[{concat_input_idx}:v]format=yuva420p[subs_stream]"
                f";[{last_label}][subs_stream]overlay=0:0:eof_action=pass[{out_label}]"
            )
            last_label = out_label

        # Overlay các item khác (Top Caption PNG hoặc Emoji lẻ nếu có)
        for item in other_items:
            png_p = Path(item[0]).resolve()
            start_s, end_s = item[1], item[2]

            if outcard_start_s is not None and "top_caption" not in png_p.name:
                if start_s >= outcard_start_s:
                    continue
                end_s = min(end_s, outcard_start_s)

            inputs.extend(["-i", str(png_p)])
            out_label = f"v_out_{current_input_idx}"

            if len(item) == 3:
                filter_complex += (
                    f";[{last_label}][{current_input_idx}:v]overlay="
                    f"0:0:enable='between(t,{start_s:.3f},{end_s:.3f})'[{out_label}]"
                )
            else:
                x_pos, y_pos = item[3], item[4]
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

    encoder_name, codec_flags = get_best_video_encoder(enable_gpu=enable_gpu, cpu_preset=cpu_preset)

    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-threads", str(threads),
        *inputs,
        "-t", duration_hms,
        "-filter_complex", filter_complex,
        "-map", output_label,
        "-map", audio_label,
        *codec_flags,
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info(f"Bắt đầu render clip: {output_path.name} ({duration:.1f}s, {style.name}, encoder={encoder_name})")
    logger.debug(f"FFmpeg command: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        _, stderr_output = process.communicate()

        if process.returncode != 0:
            # Nếu dùng GPU mà lỗi → thử lại riêng clip này bằng CPU libx264 (không khóa GPU của các clip khác)
            if enable_gpu and encoder_name != "libx264":
                logger.warning(f"⚠️ FFmpeg GPU render thất bại ({encoder_name}) cho clip {output_path.name}. Đang thử lại riêng clip này bằng CPU (libx264)...")
                return cut_and_render_clip(
                    video_path=video_path,
                    start_time=start_time,
                    end_time=end_time,
                    output_path=output_path,
                    style=style,
                    subtitle_path=subtitle_path,
                    emoji_path=emoji_path,
                    progress_callback=progress_callback,
                    timed_emojis=timed_emojis,
                    audio_volume=audio_volume,
                    outcard_path=outcard_path,
                    title_text=title_text,
                    enable_gpu=False,
                    cpu_preset=cpu_preset,
                    threads=threads,
                )

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

"""CLI interface using Click and Rich.
"""

import os
import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.panel import Panel

from ..config import AppConfig, DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_STYLE_MAPPING
from ..pipeline import PipelineOrchestrator

console = Console()


@click.command(help="Tool cắt hàng loạt video thành clip viral Reels/Shorts.")
@click.option(
    "--input-dir",
    "-i",
    default=DEFAULT_INPUT_DIR,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help=f"Đường dẫn thư mục chứa các folder video nguồn (mặc định: {DEFAULT_INPUT_DIR}).",
)
@click.option(
    "--output-dir",
    "-o",
    default=DEFAULT_OUTPUT_DIR,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help=f"Đường dẫn thư mục xuất clip output (mặc định: {DEFAULT_OUTPUT_DIR}).",
)
@click.option(
    "--style-map",
    "-s",
    default=DEFAULT_STYLE_MAPPING,
    help=f"Mapping dải folder -> phong cách (mặc định: '{DEFAULT_STYLE_MAPPING}').",
)
@click.option(
    "--max-clips",
    default=2,
    type=int,
    help="Số lượng clip tối đa cắt từ 1 video gốc (mặc định: 2).",
)
@click.option(
    "--max-workers",
    default=2,
    type=int,
    help="Số lượng video xử lý đồng thời (mặc định: 2).",
)
@click.option(
    "--whisper-model",
    default="base.en",
    help="Model Whisper để transcribe (mặc định: base.en).",
)
@click.option(
    "--api-key",
    default=None,
    help="Gemini API Key (mặc định đọc từ biến môi trường GEMINI_API_KEY).",
)
@click.option(
    "--prompt-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Đường dẫn file prompt tùy chỉnh (mặc định: scipt.txt).",
)
@click.option(
    "--folder-name",
    "-f",
    default=None,
    help="Tên thư mục đóng gói thành phẩm (mặc định tự tạo theo timestamp: batch_export_YYYYMMDD_HHMMSS).",
)
@click.option(
    "--gpu/--no-gpu",
    default=True,
    help="Bật/tắt tăng tốc phần cứng GPU (NVIDIA NVENC / Intel QSV / AMD AMF) cho FFmpeg (mặc định: --gpu).",
)
@click.option(
    "--preset",
    default="superfast",
    type=click.Choice(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"]),
    help="FFmpeg CPU encoding preset nếu không có GPU (mặc định: superfast).",
)
@click.option(
    "--render-workers",
    default=2,
    type=int,
    help="Số lượng luồng render clip đồng thời (mặc định: 2).",
)
@click.option(
    "--subtitle-align",
    default="auto",
    type=click.Choice(["auto", "fast", "deep"]),
    help="Chế độ căn chỉnh phụ đề: 'auto' (mặc định: align chuẩn xác theo audio bằng Whisper), 'fast' (nội suy mốc từ nhanh theo số ký tự, bỏ qua Whisper), 'deep' (bắt buộc Whisper align).",
)
@click.option(
    "--subtitle-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Đường dẫn file phụ đề tùy chỉnh (.srt hoặc .txt) nạp trực tiếp.",
)
@click.option(
    "--force/--no-force",
    default=True,
    help="Luôn render lại clip mới và ghi đè phiên bản mới nhất, không skip (mặc định: --force).",
)
@click.option(
    "--cache/--no-cache",
    default=False,
    help="Bật/tắt lưu và nạp transcript cache (mặc định: --no-cache để mỗi lần chạy đều được làm mới hoàn toàn).",
)
@click.option(
    "--subtitle-offset",
    default=0.0,
    type=float,
    help="Độ lệch thời gian phụ đề (giây), 0.0 là chuẩn thời gian thực theo mốc Whisper, số âm để hiện sớm hơn, số dương để hiện muộn hơn (mặc định: 0.0s).",
)
def main_cli(
    input_dir: Path,
    output_dir: Path,
    style_map: str,
    max_clips: int,
    max_workers: int,
    whisper_model: str,
    api_key: str,
    prompt_file: Path,
    folder_name: str,
    gpu: bool,
    preset: str,
    render_workers: int,
    subtitle_align: str,
    subtitle_file: Optional[Path],
    force: bool,
    cache: bool,
    subtitle_offset: float,
):
    """Entry point cho CLI."""
    console.print(
        Panel.fit(
            "[bold green]BATCH VIDEO CUTTER[/bold green]\n"
            "[cyan]Cắt hàng loạt video Shorts/Reels tự động với AI[/cyan]",
            border_style="green",
        )
    )

    gemini_key = api_key or os.getenv("GEMINI_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    sambanova_key = os.getenv("SAMBANOVA_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    if not gemini_key and not groq_key and not sambanova_key and not openrouter_key:
        console.print(
            "[bold red]LỖI: Chưa có AI API Key nào![/bold red]\n"
            "Vui lòng truyền `--api-key YOUR_KEY` hoặc cấu hình ít nhất một trong các biến: "
            "`GROQ_API_KEY`, `GEMINI_API_KEY`, `SAMBANOVA_API_KEY`, `OPENROUTER_API_KEY` trong file .env."
        )
        sys.exit(1)

    config = AppConfig(
        input_dir=input_dir or DEFAULT_INPUT_DIR,
        output_dir=output_dir or DEFAULT_OUTPUT_DIR,
        style_mapping_str=style_map,
        max_clips_per_video=max_clips,
        max_workers=max_workers,
        whisper_model=whisper_model,
        gemini_api_key=gemini_key,
        prompt_template_path=prompt_file,
        session_folder_name=folder_name,
        use_gpu=gpu,
        ffmpeg_preset=preset,
        max_render_workers=render_workers,
        subtitle_align=subtitle_align,
        subtitle_file=subtitle_file,
        force_rerender=force,
        use_cache=cache,
        subtitle_time_offset=subtitle_offset,
    )


    orchestrator = PipelineOrchestrator(config)
    orchestrator.run()


if __name__ == "__main__":
    main_cli()

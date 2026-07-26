"""CLI interface using Click and Rich.
"""

import os
import sys
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel

from ..config import AppConfig, DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR
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
    default="1-12:1,13-24:2,25-36:3,37-50:4",
    help="Mapping dải folder -> phong cách. Ví dụ: '1-12:1,13-24:2'",
)
@click.option(
    "--max-clips",
    default=3,
    type=int,
    help="Số lượng clip tối đa cắt từ 1 video gốc (mặc định: 3).",
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
    if not gemini_key:
        console.print(
            "[bold red]LỖI: Chưa có Gemini API Key![/bold red]\n"
            "Vui lòng truyền `--api-key YOUR_KEY` hoặc cài biến môi trường `GEMINI_API_KEY` trong file .env."
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
    )


    orchestrator = PipelineOrchestrator(config)
    orchestrator.run()


if __name__ == "__main__":
    main_cli()

"""Configuration module for Batch Video Cutter.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TITLE_MIN_WORDS = 8
TITLE_MAX_WORDS = 10

env_input = os.getenv("INPUT_DIR")
env_output = os.getenv("OUTPUT_DIR")

DEFAULT_INPUT_DIR = Path(env_input) if env_input else Path(r"E:\output")
DEFAULT_OUTPUT_DIR = Path(env_output) if env_output else Path(r"E:\output\final_clips")


@dataclass
class AppConfig:
    """Application configuration container."""

    input_dir: Path = field(default_factory=lambda: DEFAULT_INPUT_DIR)
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    style_mapping_str: str = "1-12:2,13-24:4,25-36:3,37-48:5"
    max_clips_per_video: int = 2
    max_workers: int = 2
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "base.en"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    prompt_template_path: Optional[Path] = None
    session_folder_name: Optional[str] = None
    use_gpu: bool = True
    ffmpeg_preset: str = "superfast"
    max_render_workers: int = 2
    force_rerender: bool = False
    outcard_path: Optional[Path] = field(default_factory=lambda: Path(os.getenv("OUTCARD_PATH")) if os.getenv("OUTCARD_PATH") else None)

    def __post_init__(self):
        if not self.input_dir:
            self.input_dir = DEFAULT_INPUT_DIR
        self.input_dir = Path(self.input_dir).resolve()

        if not self.output_dir:
            self.output_dir = DEFAULT_OUTPUT_DIR
        self.output_dir = Path(self.output_dir).resolve()

        if self.prompt_template_path:
            self.prompt_template_path = Path(self.prompt_template_path).resolve()
        else:
            default_script = Path(__file__).parent.parent / "scipt.txt"
            if default_script.exists():
                self.prompt_template_path = default_script.resolve()



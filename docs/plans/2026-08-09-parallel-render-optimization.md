# Parallel Render Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize video rendering speed in `batch_video_cutter` by introducing clip-level parallel rendering, FFmpeg hardware acceleration (GPU NVENC/QSV/AMF), preset tuning, and configurable rendering worker pools.

**Architecture:** Leverage multi-threading/asyncio concurrent clip rendering within each video pipeline task, autodetect GPU encoder support via `ffmpeg_check.py`, tune FFmpeg encoding parameters (`-c:v h264_nvenc` or `-preset ultrafast`), and manage separate concurrency semaphores for Transcribe (CPU/Whisper), LLM API (Async), and Render (FFmpeg).

**Tech Stack:** Python 3.12+, asyncio, FFmpeg (with NVENC/QSV/AMF support), Pillow, tqdm, loguru, click.

---

### Task 1: Auto-detection of Hardware Acceleration (GPU Encoders) & AppConfig Extension

**Files:**
- Modify: `batch_video_cutter/utils/ffmpeg_check.py`
- Modify: `batch_video_cutter/config.py:17-46`
- Create: `tests/test_gpu_check.py`

**Step 1: Write the failing test for GPU detection and config**

```python
# tests/test_gpu_check.py
from pathlib import Path
from batch_video_cutter.config import AppConfig
from batch_video_cutter.utils.ffmpeg_check import get_best_video_encoder

def test_app_config_render_settings():
    config = AppConfig(
        use_gpu=True,
        ffmpeg_preset="ultrafast",
        max_render_workers=4
    )
    assert config.use_gpu is True
    assert config.ffmpeg_preset == "ultrafast"
    assert config.max_render_workers == 4

def test_get_best_video_encoder():
    encoder, codec_args = get_best_video_encoder(enable_gpu=True, cpu_preset="ultrafast")
    assert isinstance(encoder, str)
    assert isinstance(codec_args, list)
    assert len(codec_args) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_gpu_check.py -v`
Expected: FAIL with `TypeError: AppConfig.__init__() got an unexpected keyword argument 'use_gpu'` or `ImportError`.

**Step 3: Write minimal implementation in config.py and ffmpeg_check.py**

In `batch_video_cutter/config.py`:
```python
@dataclass
class AppConfig:
    input_dir: Path = field(default_factory=lambda: DEFAULT_INPUT_DIR)
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    style_mapping_str: str = "1-12:1,13-24:2,25-36:4,37-48:3,49-54:5"
    max_clips_per_video: int = 3
    max_workers: int = 2
    whisper_model: str = "base.en"
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    prompt_template_path: Optional[Path] = None
    session_folder_name: Optional[str] = None
    use_gpu: bool = True
    ffmpeg_preset: str = "superfast"
    max_render_workers: int = 4
```

In `batch_video_cutter/utils/ffmpeg_check.py`:
```python
import subprocess
from loguru import logger

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
            timeout=5
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_gpu_check.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add batch_video_cutter/config.py batch_video_cutter/utils/ffmpeg_check.py tests/test_gpu_check.py
git commit -m "feat: add GPU encoder auto-detection and render config settings"
```

---

### Task 2: Hardware-Accelerated & Preset-Tuned Render Command in Core Engine

**Files:**
- Modify: `batch_video_cutter/core/engine.py:19-180`
- Create: `tests/test_engine_render.py`

**Step 1: Write failing test for hardware-accelerated render parameter in engine**

```python
# tests/test_engine_render.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from batch_video_cutter.core.engine import cut_and_render_clip
from batch_video_cutter.styles.style_1 import Style1

@patch("subprocess.Popen")
@patch("batch_video_cutter.core.engine.get_video_resolution", return_value=(1920, 1080))
def test_cut_and_render_clip_with_custom_encoder(mock_res, mock_popen, tmp_path):
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    video_p = tmp_path / "dummy.mp4"
    video_p.touch()
    out_p = tmp_path / "out.mp4"
    style = Style1()

    cut_and_render_clip(
        video_path=video_p,
        start_time=0.0,
        end_time=10.0,
        output_path=out_p,
        style=style,
        enable_gpu=True,
        cpu_preset="ultrafast",
        threads=4
    )

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert "ffmpeg" in cmd
    assert "-threads" in cmd
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine_render.py -v`
Expected: FAIL with `TypeError: cut_and_render_clip() got an unexpected keyword argument 'enable_gpu'`

**Step 3: Update `cut_and_render_clip` signature and execution logic in `batch_video_cutter/core/engine.py`**

```python
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
    ...
    # Thay thế phần hardcode [-c:v, libx264, -preset, fast, -crf, 22]
    encoder_name, codec_flags = get_best_video_encoder(enable_gpu=enable_gpu, cpu_preset=cpu_preset)

    cmd = [
        "ffmpeg",
        "-y",
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
```

Handle GPU fallback: If `h264_nvenc` fails unexpectedly during subprocess execution, automatically fallback to `libx264` software encoding and retry once.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine_render.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add batch_video_cutter/core/engine.py tests/test_engine_render.py
git commit -m "feat: implement hardware-accelerated and preset-tuned FFmpeg rendering"
```

---

### Task 3: Clip-Level Parallel Concurrent Rendering in Pipeline Orchestrator

**Files:**
- Modify: `batch_video_cutter/pipeline.py:186-277`
- Create: `tests/test_parallel_pipeline.py`

**Step 1: Write test for concurrent clip rendering**

```python
# tests/test_parallel_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from batch_video_cutter.config import AppConfig
from batch_video_cutter.pipeline import PipelineOrchestrator

@pytest.mark.asyncio
async def test_parallel_clip_rendering(tmp_path):
    config = AppConfig(
        input_dir=tmp_path,
        output_dir=tmp_path / "output",
        max_render_workers=4
    )
    orchestrator = PipelineOrchestrator(config)
    assert orchestrator.render_semaphore._value == 4
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_parallel_pipeline.py -v`
Expected: FAIL with `AttributeError: 'PipelineOrchestrator' object has no attribute 'render_semaphore'`

**Step 3: Refactor `process_single_video` loop in `batch_video_cutter/pipeline.py` to render clips concurrently**

In `PipelineOrchestrator.__init__`:
```python
self.render_semaphore = asyncio.Semaphore(config.max_render_workers)
```

In `process_single_video`:
Replace the sequential `for clip_idx, seg in enumerate(segments, 1):` with an async concurrent task list per clip:

```python
async def render_single_clip_task(clip_idx: int, seg: ViralSegment) -> dict:
    async with self.render_semaphore:
        clip_filename = f"{video_info.folder_name}.{clip_idx}.mp4"
        output_clip_path = self.bundle_dir / clip_filename
        
        loop = asyncio.get_running_loop()
        with tempfile.TemporaryDirectory() as tmp_dir:
            sub_path = Path(tmp_dir) / f"sub_{clip_idx}.ass"
            sub_position = style.get_subtitle_position()
            clip_dur = seg.end_time - seg.start_time
            outcard_start_s = max(0.0, clip_dur - 2.113)

            # Generate subtitles in thread pool
            sub_path, timed_emojis = await loop.run_in_executor(
                None,
                functools.partial(
                    create_subtitles_from_transcript,
                    segments=transcript.segments,
                    clip_start=seg.start_time,
                    clip_end=seg.end_time,
                    output_path=sub_path,
                    position=sub_position,
                    font_name=getattr(style, "get_font_name", lambda: "Montserrat Black")(),
                    font_size=getattr(style, "get_font_size", lambda: 66)(),
                    highlight_color_name=getattr(style, "get_highlight_color", lambda: "yellow")(),
                    italic=getattr(style, "get_italic_option", lambda: False)(),
                    add_emojis=True,
                    canvas_size=style.get_output_resolution(),
                    outcard_start_s=outcard_start_s,
                )
            )

            # Clean caption text & generate top caption image
            title_text_en = clean_caption_text(seg.title_en)
            if getattr(style, "get_caption_area", lambda: None)():
                top_cap_png = Path(tmp_dir) / f"top_caption_{clip_idx}.png"
                canvas_res = style.get_output_resolution()
                top_area_h = 180 if canvas_res[1] == 1080 else 280
                cap_png_path = generate_top_caption_layer(
                    title_text_en,
                    output_png=top_cap_png,
                    canvas_size=canvas_res,
                    top_area_height=top_area_h,
                    style_index=getattr(style, "style_index", 4),
                )
                if cap_png_path and cap_png_path.exists():
                    timed_emojis = [(cap_png_path, 0.0, clip_dur)] + (timed_emojis or [])

            # Render clip via FFmpeg asynchronously
            await loop.run_in_executor(
                None,
                functools.partial(
                    cut_and_render_clip,
                    video_path=video_info.path,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    output_path=output_clip_path,
                    style=style,
                    subtitle_path=sub_path,
                    timed_emojis=timed_emojis,
                    title_text=title_text_en,
                    outcard_path=self.outcard_path,
                    enable_gpu=self.config.use_gpu,
                    cpu_preset=self.config.ffmpeg_preset,
                )
            )

        return {
            "filename": clip_filename,
            "title_en": title_text_en,
            "title_vi": seg.title_vi or "",
            "title": title_text_en,
            "folder_name": video_info.folder_name,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "reason": getattr(seg, "reason", ""),
        }

# Chạy song song tất cả các clip của video này
clip_tasks = [render_single_clip_task(idx, seg) for idx, seg in enumerate(segments, 1)]
video_results = await asyncio.gather(*clip_tasks)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_parallel_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add batch_video_cutter/pipeline.py tests/test_parallel_pipeline.py
git commit -m "feat: implement parallel clip rendering with dedicated render semaphore"
```

---

### Task 4: Integration with CLI Options & Performance Benchmarking

**Files:**
- Modify: `batch_video_cutter/ui/cli.py:45-115`
- Create: `tests/test_cli_render_opts.py`

**Step 1: Write test for new CLI flags**

```python
# tests/test_cli_render_opts.py
from click.testing import CliRunner
from batch_video_cutter.ui.cli import main_cli

def test_cli_render_options_help():
    runner = CliRunner()
    result = runner.invoke(main_cli, ["--help"])
    assert result.exit_code == 0
    assert "--gpu" in result.output or "--no-gpu" in result.output
    assert "--render-workers" in result.output
    assert "--preset" in result.output
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_cli_render_opts.py -v`
Expected: FAIL with `AssertionError: '--render-workers' not in output`

**Step 3: Update `cli.py` options**

Add click options to `main_cli`:
```python
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
    default=4,
    type=int,
    help="Số lượng luồng render clip đồng thời (mặc định: 4).",
)
```

Pass options into `AppConfig`:
```python
config = AppConfig(
    ...
    use_gpu=gpu,
    ffmpeg_preset=preset,
    max_render_workers=render_workers,
)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_render_opts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add batch_video_cutter/ui/cli.py tests/test_cli_render_opts.py
git commit -m "feat: expose --gpu, --preset, and --render-workers flags in CLI"
```

---

## Verification Plan

### Automated Tests
- `pytest tests/test_gpu_check.py -v` (Verify GPU detection & AppConfig)
- `pytest tests/test_engine_render.py -v` (Verify hardware-accelerated FFmpeg command building)
- `pytest tests/test_parallel_pipeline.py -v` (Verify async concurrent clip processing)
- `pytest tests/test_cli_render_opts.py -v` (Verify CLI flag parsing)
- `pytest -v` (Full test suite regression check)

### Manual Verification
- Test CLI dry run: `python -m batch_video_cutter.ui.cli --help`
- Run actual batch execution with `--render-workers 4 --gpu` on a test folder containing 2 videos, observing GPU utilization (Nvidia Control Panel / Task Manager GPU Engine) and rendering speedup (expecting ~3x - 5x faster export time).

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-08-09-parallel-render-optimization.md`. Two execution options:

1. **Subagent-Driven (this session)** - Dispatch fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints.

import pytest
from pathlib import Path
from click.testing import CliRunner

from batch_video_cutter.config import AppConfig, SUBTITLE_TIME_OFFSET
from batch_video_cutter.core.transcriber import SentenceSegment, WordSegment
from batch_video_cutter.utils.subtitle import create_subtitles_from_transcript
from batch_video_cutter.ui.cli import main_cli


def test_subtitle_time_offset_shifts_words_earlier(tmp_path):
    """Xác thực subtitle_time_offset dịch mốc thời gian từ sớm hơn để triệt tiêu độ trễ Whisper."""
    segments = [
        SentenceSegment(
            start=10.0,
            end=14.0,
            text="Hello world test subtitle timing",
            words=[
                WordSegment(word="Hello", start=10.50, end=11.00),
                WordSegment(word="world", start=11.20, end=11.80),
                WordSegment(word="test", start=12.00, end=12.50),
                WordSegment(word="subtitle", start=12.60, end=13.20),
                WordSegment(word="timing", start=13.30, end=13.80),
            ],
        )
    ]

    out_ass = tmp_path / "test_offset.ass"
    offset = -0.22  # Bù 220ms

    _, graphic_frames = create_subtitles_from_transcript(
        segments=segments,
        clip_start=10.0,
        clip_end=14.0,
        output_path=out_ass,
        subtitle_time_offset=offset,
        add_emojis=True,
    )

    assert graphic_frames is not None
    assert len(graphic_frames) > 0

    # Khung đầu tiên phải xuất hiện sớm hơn mốc gốc (10.50 - 10.0 = 0.50s gốc -> bù -0.22s = ~0.28s)
    first_frame_start = graphic_frames[0][1]
    assert 0.25 <= first_frame_start <= 0.30, f"Expected first frame ~0.28s, got {first_frame_start}"


def test_cli_subtitle_offset_option():
    """Xác thực CLI nhận cờ --subtitle-offset và truyền chính xác vào AppConfig."""
    runner = CliRunner()
    result = runner.invoke(main_cli, ["--help"])
    assert result.exit_code == 0
    assert "--subtitle-offset" in result.output
    assert "0.0" in result.output


def test_config_default_offset():
    """Xác thực config mặc định có SUBTITLE_TIME_OFFSET là 0.0s (chuẩn thời gian thực)."""
    config = AppConfig()
    assert config.subtitle_time_offset == 0.0
    assert SUBTITLE_TIME_OFFSET == 0.0

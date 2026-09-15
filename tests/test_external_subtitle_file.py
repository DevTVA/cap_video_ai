"""Unit tests cho tính năng nạp file phụ đề tùy chỉnh từ bên ngoài (--subtitle-file)."""

from pathlib import Path
from batch_video_cutter.core.transcriber import (
    try_parse_existing_subtitles,
    transcribe_video,
)


def test_try_parse_existing_subtitles_with_external_file(tmp_path: Path):
    """Test nạp file phụ đề SRT bên ngoài với độ ưu tiên cao nhất."""
    fake_video = tmp_path / "video.mp4"
    fake_video.write_bytes(b"dummy video")

    custom_srt = tmp_path / "custom_external.srt"
    custom_srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nDay la phu de tuy chinh ben ngoai\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\nCau thu hai trong phu de\n\n",
        encoding="utf-8"
    )

    res = try_parse_existing_subtitles(fake_video, external_subtitle_file=custom_srt)
    assert res is not None
    assert len(res.segments) == 2
    assert res.segments[0].text == "Day la phu de tuy chinh ben ngoai"
    assert res.segments[0].start == 1.0
    assert res.segments[0].end == 3.5
    assert res.segments[1].text == "Cau thu hai trong phu de"
    assert res.segments[1].start == 4.0
    assert res.segments[1].end == 6.0
    assert res.timestamp_source == "srt"


def test_transcribe_video_with_external_file_fast(tmp_path: Path):
    """Test transcribe_video khi truyền external_subtitle_file ở chế độ subtitle_align='fast'."""
    fake_video = tmp_path / "video.mp4"
    fake_video.write_bytes(b"dummy video")

    custom_srt = tmp_path / "custom.srt"
    custom_srt.write_text(
        "1\n00:00:00,500 --> 00:00:02,000\nXin chao the gioi\n\n",
        encoding="utf-8"
    )

    res = transcribe_video(
        fake_video,
        subtitle_align="fast",
        external_subtitle_file=custom_srt,
        use_cache=False,
    )

    assert res is not None
    assert len(res.segments) == 1
    assert res.segments[0].text == "Xin chao the gioi"
    assert res.has_word_timestamps is True
    assert len(res.segments[0].words) == 4

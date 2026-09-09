"""Unit tests for Fast Subtitle Mode, Subtitle Alignment and Multi-factor Cache Manager."""

import tempfile
from pathlib import Path
import pytest

from batch_video_cutter.core.transcriber import (
    TranscriptResult,
    SentenceSegment,
    WordSegment,
    estimate_words_for_subtitles,
    transcribe_video,
)
from batch_video_cutter.core.cache_manager import (
    compute_transcript_cache_key,
    save_cached_transcript,
    get_cached_transcript,
    compute_alignment_cache_key,
    save_cached_alignment,
    get_cached_alignment,
    TRANSCRIPTS_CACHE_DIR,
    ALIGNMENTS_CACHE_DIR,
)
from batch_video_cutter.core.telemetry import ClipTelemetry


def test_estimate_words_for_subtitles_preserves_structure_and_labels_estimated():
    """Kiểm tra estimate_words_for_subtitles gán nhãn timing_source='estimated' chính xác."""
    seg1 = SentenceSegment(
        text="Hello world this is a test.",
        start=1.0,
        end=4.0,
        words=[],
    )
    seg2 = SentenceSegment(
        text="Fast alignment mode!",
        start=4.5,
        end=6.0,
        words=[],
    )
    res = TranscriptResult(
        segments=[seg1, seg2],
        language="en",
        duration=6.0,
        full_text="Hello world this is a test. Fast alignment mode!",
        has_word_timestamps=False,
        timestamp_source="srt",
    )

    estimated_res = estimate_words_for_subtitles(res)

    assert estimated_res.has_word_timestamps is True
    assert estimated_res.timestamp_source == "estimated"
    assert len(estimated_res.segments[0].words) == 6
    assert len(estimated_res.segments[1].words) == 3

    # Kiểm tra nhãn trên từng từ
    for s in estimated_res.segments:
        for w in s.words:
            assert w.timing_source == "estimated"
            assert w.start >= s.start
            assert w.end <= s.end
            assert w.end > w.start


def test_multi_factor_transcript_cache(tmp_path):
    """Kiểm tra lưu và nạp transcript từ cache đa yếu tố."""
    test_video = tmp_path / "sample.mp4"
    test_video.write_bytes(b"dummy video content for cache key generation")

    cache_key = compute_transcript_cache_key(test_video, whisper_model="base.en", language="en")
    assert isinstance(cache_key, str) and len(cache_key) == 64

    # Tạo TranscriptResult mẫu
    seg = SentenceSegment(
        text="Cached segment test",
        start=0.0,
        end=2.5,
        words=[
            WordSegment(word="Cached", start=0.0, end=0.8, probability=0.99, timing_source="whisper"),
            WordSegment(word="segment", start=0.8, end=1.8, probability=0.98, timing_source="whisper"),
            WordSegment(word="test", start=1.8, end=2.5, probability=0.97, timing_source="whisper"),
        ],
    )
    orig_result = TranscriptResult(
        segments=[seg],
        language="en",
        duration=2.5,
        full_text="Cached segment test",
        has_word_timestamps=True,
        timestamp_source="whisper",
    )

    # Lưu cache
    save_cached_transcript(cache_key, orig_result, test_video, whisper_model="base.en")

    # Đọc lại từ cache
    cached_result = get_cached_transcript(cache_key)
    assert cached_result is not None
    assert cached_result.full_text == "Cached segment test"
    assert cached_result.duration == 2.5
    assert cached_result.timestamp_source == "whisper"
    assert len(cached_result.segments) == 1
    assert len(cached_result.segments[0].words) == 3
    assert cached_result.segments[0].words[0].word == "Cached"
    assert cached_result.segments[0].words[0].timing_source == "whisper"


def test_alignment_cache():
    """Kiểm tra lưu và nạp Alignment Cache."""
    srt_content = "1\n00:00:01,000 --> 00:00:03,000\nTesting alignment cache.\n"
    key = compute_alignment_cache_key(srt_content, align_mode="fast")
    assert len(key) == 64

    segments = [
        SentenceSegment(
            text="Testing alignment cache.",
            start=1.0,
            end=3.0,
            words=[
                WordSegment(word="Testing", start=1.0, end=1.6, probability=1.0, timing_source="estimated"),
                WordSegment(word="alignment", start=1.6, end=2.4, probability=1.0, timing_source="estimated"),
                WordSegment(word="cache.", start=2.4, end=3.0, probability=1.0, timing_source="estimated"),
            ],
        )
    ]

    save_cached_alignment(key, segments)
    cached_segs = get_cached_alignment(key)
    assert cached_segs is not None
    assert len(cached_segs) == 1
    assert cached_segs[0].text == "Testing alignment cache."
    assert cached_segs[0].words[0].timing_source == "estimated"


def test_transcribe_video_with_srt_and_fast_mode(tmp_path):
    """Kiểm tra transcribe_video nạp file SRT và áp dụng fast alignment mà không cần gọi Whisper."""
    folder = tmp_path / "video_folder"
    folder.mkdir()
    video_file = folder / "input.mp4"
    video_file.write_bytes(b"dummy video content")

    srt_file = folder / "input.srt"
    srt_content = """1
00:00:00,500 --> 00:00:02,500
Court is in session now.

2
00:00:02,600 --> 00:00:05,000
Please state your claim clearly.
"""
    srt_file.write_text(srt_content, encoding="utf-8")

    # Chạy transcribe với subtitle_align="fast"
    res = transcribe_video(video_file, subtitle_align="fast", use_cache=True)

    assert res is not None
    assert len(res.segments) == 2
    assert res.has_word_timestamps is True
    assert res.timestamp_source == "estimated"
    assert len(res.segments[0].words) > 0
    assert res.segments[0].words[0].timing_source == "estimated"

    # Lần 2 gọi lại với use_cache=True phải trúng Cache Hit cho fast mode
    res_cached = transcribe_video(video_file, subtitle_align="fast", use_cache=True)
    assert res_cached is not None
    assert res_cached.timestamp_source == "estimated"
    assert len(res_cached.segments) == 2


def test_clip_telemetry():
    """Kiểm tra tính toán micro-timings và format report của ClipTelemetry."""
    telemetry = ClipTelemetry(
        folder_name="25",
        clip_idx=1,
        clip_filename="25.1.mp4",
        duration_sec=28.0,
        style_name="Style 3",
        t_sub_parse=0.005,
        t_whisper=0.0,
        t_align=0.012,
        t_pillow_draw=0.550,
        t_png_io=0.440,
        t_ffmpeg=4.500,
        align_mode="fast",
        timestamp_source="estimated",
        whisper_cached=True,
        frames_rendered=80,
    )

    total = telemetry.calculate_total()
    assert round(total, 3) == round(0.005 + 0.0 + 0.012 + 0.550 + 0.440 + 4.500, 3)
    assert telemetry.t_total == total

    report = telemetry.format_report()
    assert "25.1.mp4" in report
    assert "Cache Hit / Skipped" in report
    assert "Source: estimated | Mode: fast" in report
    assert "TOTAL CLIP TIME" in report

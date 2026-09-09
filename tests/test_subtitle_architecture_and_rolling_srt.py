"""7-Tier Comprehensive Unit Tests for Subtitle Architecture & Rolling SRT Handling.
"""

import pytest
from pathlib import Path
from batch_video_cutter.core.transcriber import (
    WordSegment,
    SentenceSegment,
    TranscriptResult,
    OverlapType,
    classify_overlap,
    _parse_srt_file,
    estimate_words_for_subtitles,
)
from batch_video_cutter.utils.subtitle import SubtitleLine, SubtitleChunker, SubtitleLayoutEngine
from batch_video_cutter.utils.graphic_subtitle import (
    generate_graphic_subtitles,
    generate_concat_manifest,
)
from batch_video_cutter.styles.base import HIGHLIGHT_COLOR_GREEN, HIGHLIGHT_COLOR_YELLOW
from batch_video_cutter.styles.style_3 import Style3
from batch_video_cutter.styles.style_5 import Style5


# =====================================================================
# Group A: SRT Parsing & Overlap Classification
# =====================================================================

def test_srt_exact_duplicate_classification():
    seg1 = SentenceSegment(text="Hello world", start=10.0, end=15.0)
    seg2 = SentenceSegment(text="Hello world", start=10.1, end=15.0)
    assert classify_overlap(seg1, seg2) == OverlapType.EXACT_DUPLICATE


def test_srt_rolling_prefix_classification():
    seg1 = SentenceSegment(text="I don't know", start=10.0, end=15.0)
    seg2 = SentenceSegment(text="I don't know what happened", start=12.0, end=17.0)
    assert classify_overlap(seg1, seg2) == OverlapType.ROLLING_CAPTION


def test_srt_rolling_suffix_classification():
    seg1 = SentenceSegment(text="First phrase hello world", start=10.0, end=15.0)
    seg2 = SentenceSegment(text="hello world this is next", start=13.0, end=18.0)
    assert classify_overlap(seg1, seg2) == OverlapType.ROLLING_CAPTION


def test_srt_true_conflict_classification():
    seg1 = SentenceSegment(text="The judge is speaking", start=10.0, end=15.0)
    seg2 = SentenceSegment(text="Defendant objected loudly", start=12.0, end=16.0)
    assert classify_overlap(seg1, seg2) == OverlapType.TRUE_CONFLICT


def test_parse_srt_rolling_captions_preserves_timing(tmp_path):
    srt_content = """1
00:00:10,000 --> 00:00:15,000
I don't know

2
00:00:10,050 --> 00:00:15,000
I don't know

3
00:00:12,000 --> 00:00:17,000
I don't know what happened
"""
    srt_file = tmp_path / "rolling.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    segments = _parse_srt_file(srt_file)
    # Exact duplicate (block 2) is dropped, block 1 & 3 are preserved
    assert len(segments) == 2
    assert segments[0].start == 10.0
    assert segments[0].end == 15.0  # Timing of A is preserved, NOT chopped to 12.0!
    assert segments[1].start == 12.0
    assert segments[1].end == 17.0


def test_parse_srt_out_of_order_and_invalid_timestamp(tmp_path):
    srt_content = """1
00:00:20,000 --> 00:00:25,000
Second block in time

2
00:00:05,000 --> 00:00:05,000
First block with zero duration

3
00:00:06,000 --> 00:00:10,000
Normal first block
"""
    srt_file = tmp_path / "disordered.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    segments = _parse_srt_file(srt_file)
    assert len(segments) == 3
    # Sắp xếp monotonic
    assert segments[0].start <= segments[1].start <= segments[2].start
    # Block zero-duration được sửa fallback
    assert segments[0].end > segments[0].start


# =====================================================================
# Group B: Word Timing Invariants
# =====================================================================

def test_estimate_words_monotonic_and_non_zero():
    seg = SentenceSegment(
        text="Testing monotonic word timestamps in segment",
        start=5.0,
        end=10.0,
        words=[],
    )
    result = TranscriptResult(
        segments=[seg],
        language="en",
        duration=15.0,
        full_text=seg.text,
    )

    estimated_res = estimate_words_for_subtitles(result)
    words = estimated_res.segments[0].words

    assert len(words) > 0
    for i in range(len(words)):
        # start < end
        assert words[i].end > words[i].start
        # monotonic
        if i < len(words) - 1:
            assert words[i].end <= words[i + 1].start + 0.001


# =====================================================================
# Group C: Anti-Flicker Visual States
# =====================================================================

def test_graphic_subtitles_anti_flicker_seamless(tmp_path):
    line = SubtitleLine(
        text="A quick test for anti-flicker frames",
        start=1.0,
        end=4.0,
        words=[
            ("A", 1.0, 1.05),  # Micro interval
            ("quick", 1.05, 1.8),
            ("test", 1.8, 2.5),
            ("for", 2.5, 2.8),
            ("anti-flicker", 2.8, 3.5),
            ("frames", 3.5, 4.0),
        ],
    )

    results = generate_graphic_subtitles(
        subtitle_lines=[line],
        tmp_dir=tmp_path,
        font_name="Montserrat-Bold",
        font_size=60,
    )

    assert len(results) > 0
    for img_path, s, e in results:
        assert img_path.exists()
        assert e > s


# =====================================================================
# Group D: Timestamp Immutability
# =====================================================================

def test_timestamp_immutability_through_render_pipeline(tmp_path):
    original_words = [
        ("Hello", 2.0, 2.8),
        ("world", 2.8, 3.5),
        ("immutable", 3.5, 4.5),
    ]
    line = SubtitleLine(
        text="Hello world immutable",
        start=2.0,
        end=4.5,
        words=list(original_words),
    )

    _ = generate_graphic_subtitles(
        subtitle_lines=[line],
        tmp_dir=tmp_path,
        font_name="Montserrat-Bold",
        font_size=60,
    )

    # Input line word timestamps must remain 100% identical and unmutated
    assert line.words == original_words
    assert line.start == 2.0
    assert line.end == 4.5


# =====================================================================
# Group E: Concat Manifest Timeline & Gap Coverage
# =====================================================================

def test_concat_manifest_gap_coverage_and_duration(tmp_path):
    # Dummy graphic results: sub1 at 2.0-4.0s, sub2 at 7.0-9.0s in 15.0s clip
    dummy_png1 = tmp_path / "sub1.png"
    dummy_png2 = tmp_path / "sub2.png"
    dummy_png1.write_bytes(b"dummy1")
    dummy_png2.write_bytes(b"dummy2")

    graphic_results = [
        (dummy_png1, 2.0, 4.0),
        (dummy_png2, 7.0, 9.0),
    ]

    manifest = generate_concat_manifest(
        graphic_results=graphic_results,
        tmp_dir=tmp_path,
        clip_duration=15.0,
    )

    assert manifest.exists()
    content = manifest.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Parse durations in manifest
    total_manifest_dur = 0.0
    for line in lines:
        if line.startswith("duration "):
            dur = float(line.split()[1])
            total_manifest_dur += dur

    # Manifest duration should cover entire 15.0s clip
    assert abs(total_manifest_dur - 15.0) < 0.05
    # Manifest must contain blank_transparent.png
    assert "blank_transparent.png" in content


# =====================================================================
# Group F: Style Colors
# =====================================================================

def test_style_highlight_colors_shared_constant():
    s3 = Style3()
    s5 = Style5()

    assert s3.get_highlight_color() == HIGHLIGHT_COLOR_GREEN
    assert s5.get_highlight_color() == HIGHLIGHT_COLOR_GREEN
    assert HIGHLIGHT_COLOR_GREEN == "green"

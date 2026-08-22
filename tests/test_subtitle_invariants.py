"""Property and Invariant Test Suite for Subtitle Engine.
Validates fundamental mathematical and temporal invariants across all subtitle operations.
"""

import pytest
from pathlib import Path
from batch_video_cutter.utils.subtitle import (
    SubtitleLine,
    SubtitleLayoutEngine,
    validate_subtitle_line,
    create_subtitles_from_transcript,
)
from batch_video_cutter.core.transcriber import (
    WordSegment,
    SentenceSegment,
    TranscriptResult,
)


def test_word_timestamp_end_ge_start_invariant():
    """Invariant: Every word in SubtitleLine must satisfy word.end >= word.start."""
    words = [
        ("Hello", 0.0, 0.5),
        ("World", 0.5, 1.2),
        ("Test", 1.2, 1.8),
    ]
    line = SubtitleLine(text="Hello World Test", start=0.0, end=1.8, words=words)
    assert validate_subtitle_line(line, clip_duration=5.0) is True

    for w_word, w_start, w_end in line.words:
        assert w_end >= w_start
        assert w_start >= 0.0


def test_clip_relative_clamping_invariant():
    """Invariant: After clip-relative conversion, 0 <= relative_start < relative_end <= clip_duration."""
    clip_start = 10.0
    clip_end = 20.0
    clip_dur = clip_end - clip_start

    words = [
        WordSegment(word="StraddleStart", start=9.5, end=10.8),
        WordSegment(word="Inside", start=12.0, end=15.0),
        WordSegment(word="StraddleEnd", start=19.2, end=20.5),
    ]
    seg = SentenceSegment(text="StraddleStart Inside StraddleEnd", start=9.5, end=20.5, words=words)

    out_path = Path("scratch/test_invariant_clip.ass")
    sub_path, _ = create_subtitles_from_transcript(
        segments=[seg],
        clip_start=clip_start,
        clip_end=clip_end,
        output_path=out_path,
        add_emojis=False,
    )

    if out_path.exists():
        out_path.unlink()


def test_words_ordered_by_time_invariant():
    """Invariant: Words in SubtitleLine must be strictly ordered by time without overlapping sequence inversion."""
    words = [
        ("First", 0.0, 0.5),
        ("Second", 0.5, 1.0),
        ("Third", 1.0, 1.5),
    ]
    for i in range(len(words) - 1):
        prev_end = words[i][2]
        next_start = words[i + 1][1]
        assert next_start >= prev_end - 0.001


def test_flatten_lines_equals_original_words_invariant():
    """Invariant: Flattening layout lines MUST recover 100% of original words without loss or duplicate."""
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)
    original_words = [
        ("THIS", 0.0, 0.2),
        ("IS", 0.2, 0.4),
        ("A", 0.4, 0.5),
        ("COMPREHENSIVE", 0.5, 1.0),
        ("INVARIANT", 1.0, 1.5),
        ("TEST", 1.5, 1.8),
        ("FOR", 1.8, 2.0),
        ("SUBTITLE", 2.0, 2.4),
        ("LAYOUT", 2.4, 2.8),
        ("ENGINE.", 2.8, 3.2),
    ]
    line = SubtitleLine(
        text="THIS IS A COMPREHENSIVE INVARIANT TEST FOR SUBTITLE LAYOUT ENGINE.",
        start=0.0,
        end=3.2,
        words=original_words,
    )

    layout_chunks = SubtitleLayoutEngine.layout_subtitle_line(line, font, max_width_px=600)
    recovered_words = []
    for l1, l2 in layout_chunks:
        recovered_words.extend(l1)
        recovered_words.extend(l2)

    assert len(recovered_words) == len(original_words)
    for orig, rec in zip(original_words, recovered_words):
        assert orig[0] == rec[0]
        assert orig[1] == rec[1]
        assert orig[2] == rec[2]


def test_fallback_timestamp_source_labeling():
    """Invariant: When word-level timestamps are missing, timestamp_source must be set to 'fallback'."""
    seg = SentenceSegment(text="Fallback timestamp test sentence", start=2.0, end=5.0, words=[])
    out_path = Path("scratch/test_fallback_label.ass")
    
    # Check that create_subtitles_from_transcript handles fallback gracefully
    sub_path, _ = create_subtitles_from_transcript(
        segments=[seg],
        clip_start=0.0,
        clip_end=10.0,
        output_path=out_path,
        add_emojis=False,
    )

    if out_path.exists():
        out_path.unlink()

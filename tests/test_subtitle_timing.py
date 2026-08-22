"""Unit tests for subtitle timing validator, word timestamp estimation, and clip boundary clamping.
"""

import pytest
from batch_video_cutter.utils.subtitle import (
    SubtitleLine,
    SubtitleTimingValidator,
    estimate_word_timings,
    validate_subtitle_line,
)


def test_estimate_word_timings_basic():
    text = "Hello world this is a test"
    words = estimate_word_timings(text, start=1.0, end=3.5)
    assert len(words) == 6
    assert words[0][0] == "Hello"
    assert words[0][1] == 1.0
    assert words[-1][0] == "test"
    assert words[-1][2] == 3.5

    for i in range(len(words)):
        w, s, e = words[i]
        assert s >= 1.0
        assert e > s
        assert e <= 3.5
        if i > 0:
            assert s >= words[i - 1][2] - 0.0001


def test_estimate_word_timings_empty_and_invalid():
    assert estimate_word_timings("", 1.0, 3.0) == []
    assert estimate_word_timings("   ", 1.0, 3.0) == []
    assert estimate_word_timings("Hello", 3.0, 2.0) == []


def test_timing_validator_overlap_clamping():
    words = [
        ("Word1", 1.0, 2.0),
        ("Word2", 1.8, 2.5),  # Overlap 0.2s with Word1
        ("Word3", 2.4, 3.0),  # Overlap 0.1s with Word2
    ]

    fixed = SubtitleTimingValidator.validate_and_fix_words(words, start_boundary=0.0)
    assert len(fixed) == 3
    assert fixed[0] == ("Word1", 1.0, 2.0)
    assert fixed[1][1] == 2.0  # Clamped to prev_end
    assert fixed[1][2] == 2.5
    assert fixed[2][1] == 2.5  # Clamped to prev_end
    assert fixed[2][2] == 3.0


def test_timing_validator_clip_boundary_clamping():
    words = [
        ("Before", -0.5, 0.2),
        ("Inside", 0.5, 2.5),
        ("Over", 2.8, 4.0),
    ]

    # Clip duration 3.0s
    fixed = SubtitleTimingValidator.validate_and_fix_words(
        words,
        start_boundary=0.0,
        end_boundary=3.0,
    )

    for w, s, e in fixed:
        assert s >= 0.0
        assert e > s
        assert e <= 3.0


def test_timing_validator_fix_line():
    line = SubtitleLine(
        text="Sample line",
        start=-0.5,
        end=5.0,
        words=[("Sample", -0.5, 2.0), ("line", 1.5, 5.5)],
    )

    fixed_line = SubtitleTimingValidator.validate_and_fix_line(line, clip_duration=4.0)
    assert fixed_line.start == 0.0
    assert fixed_line.end == 4.0
    assert validate_subtitle_line(fixed_line, clip_duration=4.0) is True

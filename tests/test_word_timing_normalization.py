"""Unit tests cho Phase 1: Canonical Word Timing Model & Timestamp Normalization."""

import pytest
import math
from batch_video_cutter.utils.word_timing import (
    WordTiming,
    TimingSource,
    normalize_word_timings,
)
from batch_video_cutter.utils.subtitle import fallback_estimate_word_timings


def test_valid_timestamps():
    """Kiểm tra mốc thời gian chuẩn hợp lệ."""
    raw = [
        WordTiming(text="Hello", start=1.0, end=1.5, confidence=0.9, timing_source=TimingSource.WHISPER, segment_index=0, word_index=0),
        WordTiming(text="World", start=1.5, end=2.0, confidence=0.95, timing_source=TimingSource.WHISPER, segment_index=0, word_index=1),
    ]
    res = normalize_word_timings(raw)
    assert len(res) == 2
    assert res[0].start == 1.0
    assert res[0].end == 1.5
    assert res[0].timing_source == TimingSource.WHISPER
    assert res[0].confidence == 0.9
    assert res[0].segment_index == 0
    assert res[0].word_index == 0
    assert res[1].start == 1.5
    assert res[1].end == 2.0


def test_negative_start():
    """Kiểm tra sửa mốc start âm (start < 0)."""
    raw = [
        WordTiming(text="First", start=-0.5, end=0.8, timing_source=TimingSource.WHISPER),
    ]
    res = normalize_word_timings(raw)
    assert len(res) == 1
    assert res[0].start == 0.0
    assert res[0].end == 0.8


def test_end_le_start():
    """Kiểm tra sửa end time nhỏ hơn hoặc bằng start time (end <= start)."""
    raw = [
        WordTiming(text="Broken", start=2.0, end=1.5, timing_source=TimingSource.WHISPER),
        WordTiming(text="ZeroDur", start=3.0, end=3.0, timing_source=TimingSource.WHISPER),
    ]
    res = normalize_word_timings(raw, min_word_dur=0.05)
    assert len(res) == 2
    assert res[0].start == 2.0
    assert res[0].end > res[0].start
    assert res[1].start == 3.0
    assert res[1].end == 3.05


def test_overlapping_words():
    """Kiểm tra xử lý overlap giữa các từ liên tiếp và bảo toàn end > start sau khi dời start."""
    raw = [
        WordTiming(text="Word1", start=1.0, end=2.0, timing_source=TimingSource.WHISPER, word_index=0),
        WordTiming(text="Word2", start=1.5, end=2.2, timing_source=TimingSource.WHISPER, word_index=1),  # overlap 1.5 < 2.0
    ]
    res = normalize_word_timings(raw, min_word_dur=0.05)
    assert len(res) == 2
    assert res[0].start == 1.0
    assert res[0].end == 2.0
    # Word2 start phải bị dời lên 2.0 và end phải > 2.0
    assert res[1].start == 2.0
    assert res[1].end >= 2.05


def test_missing_and_nan_timestamps():
    """Kiểm tra lọc bỏ NaN/None/Invalid values."""
    raw = [
        WordTiming(text="Valid", start=1.0, end=1.5, timing_source=TimingSource.WHISPER),
        WordTiming(text="NanStart", start=float("nan"), end=2.0, timing_source=TimingSource.WHISPER),
        WordTiming(text="InfEnd", start=2.5, end=float("inf"), timing_source=TimingSource.WHISPER),
    ]
    res = normalize_word_timings(raw)
    assert len(res) >= 1
    assert res[0].text == "Valid"
    for wt in res:
        assert not math.isnan(wt.start)
        assert not math.isnan(wt.end)
        assert not math.isinf(wt.start)
        assert not math.isinf(wt.end)
        assert wt.end > wt.start


def test_words_none_and_empty():
    """Kiểm tra truyền words=None hoặc danh sách trống."""
    assert normalize_word_timings(None) == []
    assert normalize_word_timings([]) == []
    assert normalize_word_timings([WordTiming(text="", start=1.0, end=2.0)]) == []


def test_fallback_timestamp_source():
    """Kiểm tra hàm cô lập fallback gắn nhãn source="fallback"."""
    text = "This is a fallback test phrase"
    fallback_words = fallback_estimate_word_timings(text, start=0.0, end=2.0)
    assert len(fallback_words) == 6
    for w in fallback_words:
        assert len(w) == 3
        assert w[2] > w[1]


def test_monotonic_ordering():
    """Kiểm tra thứ tự tăng dần monotonic theo thời gian audio."""
    raw = [
        WordTiming(text="Second", start=2.0, end=2.5, word_index=1),
        WordTiming(text="First", start=1.0, end=1.5, word_index=0),
        WordTiming(text="Third", start=3.0, end=3.5, word_index=2),
    ]
    res = normalize_word_timings(raw)
    assert len(res) == 3
    assert res[0].text == "First"
    assert res[1].text == "Second"
    assert res[2].text == "Third"
    assert res[0].start < res[1].start < res[2].start

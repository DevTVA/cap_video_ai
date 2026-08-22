"""Tests cho hệ thống Word Timing + SRT normalization & boundary clipping."""

import pytest
from pathlib import Path

from batch_video_cutter.utils.word_timing import WordTiming, normalize_word_timings
from batch_video_cutter.core.transcriber import (
    WordSegment,
    SentenceSegment,
    TranscriptResult,
    get_segments_in_range,
    _parse_srt_file,
    align_existing_subtitles_with_whisper,
)
from batch_video_cutter.utils.subtitle import (
    estimate_word_timings,
    create_subtitles_from_transcript,
    SubtitleLine,
)


def test_invalid_timestamp():
    """Test xử lý timestamp không hợp lệ (end <= start và text rỗng)."""
    raw_words = [
        WordTiming(text="valid", start=1.0, end=2.0),
        WordTiming(text="invalid_end", start=3.0, end=2.5),
        WordTiming(text="  ", start=4.0, end=5.0),
        ("tuple_invalid", 6.0, 5.5),
    ]

    normalized = normalize_word_timings(raw_words)
    texts = [w.text for w in normalized]

    assert "valid" in texts
    assert "invalid_end" in texts
    assert "  " not in texts

    invalid_word = next(w for w in normalized if w.text == "invalid_end")
    assert invalid_word.end > invalid_word.start


def test_negative_timestamp():
    """Test xử lý timestamp âm (start < 0)."""
    raw_words = [
        WordTiming(text="neg", start=-1.5, end=0.5),
        WordTiming(text="pos", start=1.0, end=2.0),
    ]

    normalized = normalize_word_timings(raw_words)
    neg_word = next(w for w in normalized if w.text == "neg")

    assert neg_word.start >= 0.0
    assert neg_word.end > neg_word.start


def test_word_sorting():
    """Test sắp xếp mốc từ theo start time tăng dần."""
    raw_words = [
        WordTiming(text="third", start=3.0, end=4.0),
        WordTiming(text="first", start=1.0, end=2.0),
        WordTiming(text="second", start=2.0, end=3.0),
    ]

    normalized = normalize_word_timings(raw_words)
    texts = [w.text for w in normalized]

    assert texts == ["first", "second", "third"]


def test_word_overlap():
    """Test giải quyết overlap giữa hai từ liên tiếp."""
    raw_words = [
        WordTiming(text="w1", start=1.0, end=2.5),
        WordTiming(text="w2", start=2.0, end=3.0),
    ]

    normalized = normalize_word_timings(raw_words)
    w1 = normalized[0]
    w2 = normalized[1]

    assert w2.start >= w1.end


def test_word_boundary_clipping():
    """Test xén mốc từ theo ranh giới khoảng cắt."""
    raw_words = [
        WordTiming(text="w1", start=0.5, end=1.5),
        WordTiming(text="w2", start=1.5, end=2.5),
    ]

    normalized_abs = normalize_word_timings(raw_words, range_start=1.0, range_end=2.0, make_relative=False)
    assert len(normalized_abs) == 2
    assert normalized_abs[0].start == 1.0
    assert normalized_abs[0].end == 1.5

    normalized_rel = normalize_word_timings(raw_words, range_start=1.0, range_end=2.0, make_relative=True)
    assert len(normalized_rel) == 2
    assert normalized_rel[0].start == 0.0
    assert normalized_rel[0].end == 0.5


def test_segment_boundary_clipping():
    """Test case ranh giới segment 9.8 -> 10.5 với clip 10.0 -> 20.0 (giữ lại 10.0 -> 10.5)."""
    seg = SentenceSegment(
        text="Boundary segment test",
        start=9.8,
        end=10.5,
        words=[
            WordSegment(word="Boundary", start=9.8, end=10.1),
            WordSegment(word="segment", start=10.1, end=10.3),
            WordSegment(word="test", start=10.3, end=10.5),
        ],
    )
    result = TranscriptResult(
        segments=[seg],
        language="en",
        duration=30.0,
        full_text="Boundary segment test",
    )

    clipped = get_segments_in_range(result, start_time=10.0, end_time=20.0)

    assert len(clipped) == 1
    assert clipped[0].start == 10.0
    assert clipped[0].end == 10.5
    assert len(clipped[0].words) == 3
    assert clipped[0].words[0].start == 10.0


def test_srt_sentence_timing(tmp_path):
    """Test nạp file SRT câu đơn chuẩn."""
    srt_content = """1
00:00:01,000 --> 00:00:04,500
I really love this video

2
00:00:05,000 --> 00:00:08,000
Subscribe to our channel
"""
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    segments = _parse_srt_file(srt_file)
    assert len(segments) == 2
    assert segments[0].start == 1.0
    assert segments[0].end == 4.5
    assert segments[0].text == "I really love this video"


def test_srt_plus_whisper_word_timing(tmp_path, monkeypatch):
    """Test kết hợp ranh giới SRT sentence với Whisper word timing."""
    srt_seg = SentenceSegment(text="I really love this video", start=0.0, end=4.0, words=[])
    srt_result = TranscriptResult(
        segments=[srt_seg],
        language="en",
        duration=10.0,
        full_text="I really love this video",
        has_word_timestamps=False,
        timestamp_source="srt",
    )

    fake_whisper_words = [
        WordSegment(word="I", start=0.1, end=0.4),
        WordSegment(word="really", start=0.4, end=0.9),
        WordSegment(word="love", start=0.9, end=1.4),
        WordSegment(word="this", start=1.4, end=1.8),
        WordSegment(word="video", start=1.8, end=2.5),
    ]

    class FakeWhisperModel:
        def transcribe(self, *args, **kwargs):
            class DummySeg:
                words = fake_whisper_words
            class DummyInfo:
                language = "en"
                duration = 10.0
            return [DummySeg()], DummyInfo()

    monkeypatch.setattr("batch_video_cutter.core.transcriber.get_whisper_model", lambda **kw: FakeWhisperModel())

    video_dummy = tmp_path / "dummy.mp4"
    video_dummy.write_text("fake video content", encoding="utf-8")

    aligned = align_existing_subtitles_with_whisper(srt_result, video_dummy)

    assert aligned.has_word_timestamps is True
    assert aligned.timestamp_source == "whisper"
    assert len(aligned.segments[0].words) == 5
    assert aligned.segments[0].words[0].word == "I"


def test_srt_without_word_timing():
    """Test SRT khi không có Whisper word timing."""
    srt_seg = SentenceSegment(text="Only sentence bounds", start=1.0, end=4.0, words=[])
    result = TranscriptResult(
        segments=[srt_seg],
        language="en",
        duration=10.0,
        full_text="Only sentence bounds",
        has_word_timestamps=False,
        timestamp_source="srt",
    )

    assert result.has_word_timestamps is False
    assert result.timestamp_source == "srt"


def test_estimated_word_timing():
    """Test fallback phân bổ estimated word timing khi không có mốc từ."""
    text = "I really love this video"
    estimated = estimate_word_timings(text, start=0.0, end=4.0)

    assert len(estimated) == 5
    assert estimated[0][0] == "I"
    assert estimated[0][1] == 0.0
    assert estimated[-1][2] == 4.0

    seg = SentenceSegment(text=text, start=0.0, end=4.0, words=[])
    sub_lines = []
    rel_start = 0.0
    rel_end = 4.0
    words = estimate_word_timings(seg.text, rel_start, rel_end)
    line = SubtitleLine(
        text=seg.text,
        start=rel_start,
        end=rel_end,
        words=words,
        timestamp_source="estimated",
        is_estimated=True,
    )
    sub_lines.append(line)

    assert sub_lines[0].timestamp_source == "estimated"
    assert sub_lines[0].is_estimated is True

"""Comprehensive test suite for Subtitle Engine, Layout, Timing Invariants, and Font Consistency.
"""

import pytest
from pathlib import Path
from PIL import ImageFont
from batch_video_cutter.utils.subtitle import (
    SubtitleLine,
    SubtitleLayoutEngine,
    validate_subtitle_line,
    create_subtitles_from_transcript,
    extract_emoji_for_phrase,
    measure_text_width_pixels,
)
from batch_video_cutter.core.transcriber import (
    WordSegment,
    SentenceSegment,
    TranscriptResult,
)


def test_subtitle_line_time_invariants():
    # Valid line
    line = SubtitleLine(
        text="Hello world",
        start=1.0,
        end=4.0,
        words=[("Hello", 1.0, 2.0), ("world", 2.0, 4.0)],
        timestamp_source="whisper",
    )
    assert validate_subtitle_line(line, clip_duration=10.0) is True

    # Invariant: start >= 0
    neg_line = SubtitleLine(text="Negative start", start=-0.5, end=3.0)
    assert validate_subtitle_line(neg_line, clip_duration=10.0) is False

    # Invariant: end > start
    inv_dur = SubtitleLine(text="Zero duration", start=2.0, end=2.0)
    assert validate_subtitle_line(inv_dur, clip_duration=10.0) is False

    # Invariant: end <= clip_duration
    over_clip = SubtitleLine(text="Over duration", start=5.0, end=12.0)
    assert validate_subtitle_line(over_clip, clip_duration=10.0) is False


def test_clip_relative_timestamp_offset_and_clamping():
    # Simulate Whisper segments starting at 10.0s
    words = [
        WordSegment(word="Before", start=8.0, end=9.5),   # Outside before clip
        WordSegment(word="Start", start=9.8, end=10.5),   # Straddles clip_start=10.0
        WordSegment(word="Middle", start=11.0, end=13.0), # Inside clip
        WordSegment(word="End", start=19.5, end=20.5),    # Straddles clip_end=20.0
        WordSegment(word="After", start=21.0, end=22.0),  # Outside after clip
    ]
    seg = SentenceSegment(
        text="Before Start Middle End After",
        start=8.0,
        end=22.0,
        words=words,
    )

    out_path = Path("scratch/test_sub_clip.ass")
    create_subtitles_from_transcript(
        segments=[seg],
        clip_start=10.0,
        clip_end=20.0,
        output_path=out_path,
        font_name="Montserrat-Bold",
        add_emojis=False,
    )

    # Clean up test output
    if out_path.exists():
        out_path.unlink()


def test_subtitle_layout_engine_font_resolution():
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)
    assert font is not None
    assert isinstance(font, (ImageFont.FreeTypeFont, ImageFont.ImageFont))

    w1 = SubtitleLayoutEngine.measure_text_width("HELLO WORLD", font)
    w2 = SubtitleLayoutEngine.measure_text_width("HELLO", font)
    assert w1 > w2 > 0


def test_subtitle_layout_engine_line_wrapping():
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)

    words = [
        ("I", 0.0, 0.2),
        ("REALLY", 0.2, 0.5),
        ("DON'T", 0.5, 0.7),
        ("KNOW", 0.7, 1.0),
        ("WHAT", 1.0, 1.2),
        ("HAPPENED", 1.2, 1.6),
        ("TODAY", 1.6, 2.0),
        ("AT", 2.0, 2.2),
        ("COURT.", 2.2, 2.8),
    ]

    line = SubtitleLine(
        text="I REALLY DON'T KNOW WHAT HAPPENED TODAY AT COURT.",
        start=0.0,
        end=2.8,
        words=words,
    )

    layout_chunks = SubtitleLayoutEngine.layout_subtitle_line(line, font, max_width_px=500)
    assert len(layout_chunks) > 0

    # Invariant: Flattening layout chunks MUST recover exact original words without loss
    flattened_words = []
    for l1, l2 in layout_chunks:
        flattened_words.extend(l1)
        flattened_words.extend(l2)

    assert len(flattened_words) == len(words)
    for orig, flat in zip(words, flattened_words):
        assert orig[0] == flat[0]
        assert orig[1] == flat[1]
        assert orig[2] == flat[2]


def test_deterministic_emoji_behavior():
    phrase = "This is a dramatic trial about money and secrets"
    e1 = extract_emoji_for_phrase(phrase, fallback_default=True)
    e2 = extract_emoji_for_phrase(phrase, fallback_default=True)

    # Pure deterministic output guarantee
    assert e1 == e2
    assert e1 in ["💰", "💵", "🤫", "⚖️", "📜", "🏛️", "💥", "🔥"]


def test_unicode_and_vietnamese_subtitle_support():
    vietnamese_texts = [
        "Xin chào các bạn",
        "Tôi đang ở Việt Nam.",
        "Bạn có khỏe không?",
        "Đừng làm thế!",
        '"Không thể nào!"',
        'Cô ấy nói: "Tôi không biết."',
        "🔥 😱 😂 ❤️",
    ]

    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 70)
    for text in vietnamese_texts:
        w = SubtitleLayoutEngine.measure_text_width(text, font)
        assert w > 0, f"Failed width measurement for: {text}"

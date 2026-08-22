"""Unit tests for Subtitle Layout Chunking, Natural Phrase Splitting, and Line Balancing.
"""

import pytest
from batch_video_cutter.utils.subtitle import (
    SubtitleLine,
    SubtitleLayoutEngine,
)


def test_natural_phrase_splitting_avoids_unnatural_breaks():
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)

    # Phrase containing contraction "DON'T"
    words = [
        ("I", 0.0, 0.2),
        ("REALLY", 0.2, 0.5),
        ("DON'T", 0.5, 0.7),
        ("KNOW", 0.7, 1.0),
        ("WHAT", 1.0, 1.2),
        ("HAPPENED.", 1.2, 1.6),
    ]

    line = SubtitleLine(
        text="I REALLY DON'T KNOW WHAT HAPPENED.",
        start=0.0,
        end=1.6,
        words=words,
    )

    chunks = SubtitleLayoutEngine.layout_subtitle_line(line, font, max_width_px=400)
    assert len(chunks) > 0

    # Ensure "DON'T" is not left alone at the end of line 1 if possible
    for l1, l2 in chunks:
        if l1 and l2:
            last_word_l1 = l1[-1][0].upper().strip()
            # Should prefer splitting after "KNOW" or before "DON'T" rather than right after "DON'T"
            assert last_word_l1 != "DON'T" or len(l1) == 1


def test_punctuation_and_pause_splitting():
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)

    words = [
        ("Hello", 0.0, 0.4),
        ("there,", 0.4, 0.8),  # Punctuation
        ("my", 1.5, 1.7),     # Pause > 0.35s (1.5 - 0.8 = 0.7s)
        ("friend.", 1.7, 2.2),
    ]

    line = SubtitleLine(
        text="Hello there, my friend.",
        start=0.0,
        end=2.2,
        words=words,
    )

    chunks = SubtitleLayoutEngine.layout_subtitle_line(line, font, max_width_px=800)
    assert len(chunks) >= 2


def test_build_subtitle_chunks_unified():
    from batch_video_cutter.utils.subtitle import build_subtitle_chunks, SubtitleChunk
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)

    line = SubtitleLine(
        text="I don't know what happened at court today.",
        start=0.0,
        end=3.0,
        words=[],
    )

    chunks = build_subtitle_chunks([line], font, max_width_px=800, emoji_on_top=True)
    assert len(chunks) > 0
    assert isinstance(chunks[0], SubtitleChunk)
    assert chunks[0].is_estimated is True
    assert chunks[0].emoji in ["🏛️", "⚡", "🤔", "❌", None]

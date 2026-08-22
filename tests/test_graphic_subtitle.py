"""Unit tests for PNG Graphic Subtitle Generator and Rendering Integrity.
"""

import pytest
from pathlib import Path
from batch_video_cutter.utils.subtitle import SubtitleLine
from batch_video_cutter.utils.graphic_subtitle import (
    generate_graphic_subtitles,
    ensure_caption_has_emoji,
)


def test_graphic_subtitle_generation_basic(tmp_path):
    line = SubtitleLine(
        text="This is a test of graphic subtitles.",
        start=0.0,
        end=2.5,
        words=[
            ("This", 0.0, 0.4),
            ("is", 0.4, 0.7),
            ("a", 0.7, 0.9),
            ("test", 0.9, 1.4),
            ("of", 1.4, 1.7),
            ("graphic", 1.7, 2.1),
            ("subtitles.", 2.1, 2.5),
        ],
    )

    results = generate_graphic_subtitles(
        subtitle_lines=[line],
        tmp_dir=tmp_path,
        font_name="Montserrat-Bold",
        font_size=60,
        emoji_on_top=False,
        canvas_size=(1080, 1080),
    )

    assert len(results) > 0
    for img_path, s, e in results:
        assert img_path.exists()
        assert s >= 0.0
        assert e > s
        assert e <= 2.5


def test_graphic_subtitle_outcard_clamping(tmp_path):
    line = SubtitleLine(
        text="Before outcard after outcard",
        start=8.0,
        end=12.0,
        words=[
            ("Before", 8.0, 9.0),
            ("outcard", 9.0, 10.0),
            ("after", 10.0, 11.0),
            ("outcard", 11.0, 12.0),
        ],
    )

    # Outcard starts at 9.5s
    results = generate_graphic_subtitles(
        subtitle_lines=[line],
        tmp_dir=tmp_path,
        font_name="Montserrat-Bold",
        outcard_start_s=9.5,
    )

    for _, s, e in results:
        assert s < 9.5
        assert e <= 9.5


def test_ensure_caption_has_emoji_deterministic():
    from batch_video_cutter.utils.graphic_subtitle import EmojiTracker
    text = "DRAMATIC COURTROOM BATTLE OVER $1,000,000"

    # With same fresh tracker, exact same input produces exact same output
    tracker1 = EmojiTracker()
    res1 = ensure_caption_has_emoji(text, tracker=tracker1)

    tracker2 = EmojiTracker()
    res2 = ensure_caption_has_emoji(text, tracker=tracker2)

    assert res1 == res2
    assert res1.endswith(("💰", "💵", "⚖️", "📜", "🏛️", "💥", "🔥", "💳", "🤑", "😡", "🚨", "⚡", "🥊", "💣"))

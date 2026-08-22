"""Unit tests for the 20-point audit rules and system refinements.
"""

import pytest
from pathlib import Path
from batch_video_cutter.config import AppConfig, TITLE_MIN_WORDS, TITLE_MAX_WORDS
from batch_video_cutter.core.analyzer import (
    ANALYZER_VERSION,
    _get_cache_key,
    count_title_words,
    is_intro_or_monologue_line,
    score_dialogue_quality,
)
from batch_video_cutter.utils.subtitle import SubtitleLine, extract_emoji_for_phrase


def test_title_word_count_constants():
    assert TITLE_MIN_WORDS == 8
    assert TITLE_MAX_WORDS == 10


def test_title_word_count_helper():
    title_7 = "Boss Hogg Loses His Memory And Thinks"
    title_8 = "Boss Hogg Loses His Memory And Thinks Rosco"
    title_10 = "Boss Hogg Loses His Memory And Thinks Rosco Is Family"
    title_11 = "Boss Hogg Loses His Memory And Thinks Rosco Is Family Today"

    assert count_title_words(title_7) == 7
    assert count_title_words(title_8) == 8
    assert count_title_words(title_10) == 10
    assert count_title_words(title_11) == 11


def test_intro_detection_preserves_judge_dialogue():
    # Câu thoại trong tòa án có chứa từ "Judge" KHÔNG được bị intro filter loại bỏ nhầm!
    judge_dialogue = "Judge: Why did you lie to your husband?"
    assert is_intro_or_monologue_line(judge_dialogue) is False

    courtroom_dialogue = "Tell the court what happened that night"
    assert is_intro_or_monologue_line(courtroom_dialogue) is False

    # Các cụm intro/branding thực sự PHẢI bị bắt và loại bỏ
    real_intro_1 = "Welcome back to the show everyone"
    real_intro_2 = "Thanks for watching, don't forget to like and subscribe"
    real_intro_3 = "Today's episode is brought to you by sponsored by"

    assert is_intro_or_monologue_line(real_intro_1) is True
    assert is_intro_or_monologue_line(real_intro_2) is True
    assert is_intro_or_monologue_line(real_intro_3) is True


def test_dialogue_quality_scoring():
    q_and_a_line = "Why did you do that? Did you see who was there?"
    assert score_dialogue_quality(q_and_a_line) > 1.2

    intro_line = "Welcome back to our channel, today we are going to look at"
    assert score_dialogue_quality(intro_line) < 0.5


def test_cache_versioning():
    key1 = _get_cache_key("test transcript", 2, None)
    assert ANALYZER_VERSION == "2.1"
    assert len(key1) == 64  # SHA-256 hex string


def test_deterministic_emoji_reproducibility():
    phrase = "This is a dramatic courtroom argument"
    emoji1 = extract_emoji_for_phrase(phrase, fallback_default=True)
    emoji2 = extract_emoji_for_phrase(phrase, fallback_default=True)

    # Đảm bảo 100% reproducible (cùng text -> cùng emoji)
    assert emoji1 == emoji2
    assert emoji1 is not None


def test_subtitle_line_timestamps():
    sub = SubtitleLine(
        text="Test subtitle",
        start=0.0,
        end=5.0,
        words=[("Test", 0.0, 2.0), ("subtitle", 2.0, 5.0)]
    )
    assert sub.start < sub.end
    assert sub.start >= 0.0
    for w, w_start, w_end in sub.words:
        assert w_start < w_end
        assert w_start >= sub.start
        assert w_end <= sub.end

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
    _extract_spoken_headline,
)
from batch_video_cutter.utils.subtitle import SubtitleLine, extract_emoji_for_phrase, validate_subtitle_line


def test_title_word_count_constants():
    assert TITLE_MIN_WORDS == 8
    assert TITLE_MAX_WORDS == 10


def test_title_word_count_helper():
    title_7 = "Boss Hogg Loses His Memory And Thinks"
    title_8 = "Boss Hogg Loses His Memory And Thinks Rosco"
    title_10 = "Boss Hogg Loses His Memory And Thinks Rosco Is Family"
    title_11 = "Boss Hogg Loses His Memory And Thinks Rosco Is Family Today"
    title_emoji = "Boss Hogg Loses His Memory And Thinks 💥"

    assert count_title_words(title_7) == 7
    assert count_title_words(title_8) == 8
    assert count_title_words(title_10) == 10
    assert count_title_words(title_11) == 11
    # Emoji 💥 không được tính vào word count!
    assert count_title_words(title_emoji) == 7


def test_intro_detection_preserves_judge_and_host_dialogue():
    # Câu thoại tòa án và host KHÔNG bị loại nhầm
    assert is_intro_or_monologue_line("Judge: Why did you lie to your husband?") is False
    assert is_intro_or_monologue_line("Host: Why did you leave the house?") is False
    assert is_intro_or_monologue_line("Judge, what happened that night?") is False

    # Cụm intro/promo thực sự PHẢI bị loại
    assert is_intro_or_monologue_line("Welcome back to the show everyone") is True
    assert is_intro_or_monologue_line("Thanks for watching don't forget to subscribe") is True


def test_no_fabricated_fallback_title():
    # Transcript quá ít từ (< 8 từ) -> trả về "" (không bịa title rác)
    short_transcript = "[00:01] Hello there"
    headline = _extract_spoken_headline(short_transcript, 0.0, 10.0, set())
    assert headline == ""


def test_dialogue_quality_scoring():
    q_and_a_line = "Why did you do that? Did you see who was there?"
    assert score_dialogue_quality(q_and_a_line) > 1.2

    intro_line = "Welcome back to our channel, today we are going to look at"
    assert score_dialogue_quality(intro_line) < 0.5


def test_cache_versioning():
    key1 = _get_cache_key("test transcript", 2, None)
    assert ANALYZER_VERSION == "2.2"
    assert len(key1) == 64  # SHA-256 hex string


def test_deterministic_emoji_reproducibility():
    phrase = "This is a dramatic courtroom argument"
    emoji1 = extract_emoji_for_phrase(phrase, fallback_default=True)
    emoji2 = extract_emoji_for_phrase(phrase, fallback_default=True)

    # Đảm bảo 100% reproducible (cùng text -> cùng emoji)
    assert emoji1 == emoji2
    assert emoji1 is not None


def test_censor_preservation_after_clean():
    from batch_video_cutter.utils.graphic_subtitle import clean_caption_text, censor_sensitive_words
    text = "SHE HAD SEX AND MURDER IN HER HEAD"
    censored = censor_sensitive_words(text)
    assert "SE*" in censored and "MU*DER" in censored
    cleaned = clean_caption_text(censored)
    # clean_caption_text không làm mất dấu * trong từ đã censor
    assert "SE*" in cleaned or "MU*DER" in cleaned


def test_no_forced_max_clips_if_low_quality():
    from batch_video_cutter.core.analyzer import _generate_fallback_segments
    # Transcript ngắn/nghèo thông tin không ép tạo đủ 4 clips
    short_transcript = "[00:40] Welcome to the show today\n[00:45] Thank you for watching"
    segs = _generate_fallback_segments(short_transcript, max_clips=4, video_duration=120.0, intro_offset=35.0, outro_offset=25.0)
    assert len(segs) < 4


def test_subtitle_line_validation():
    # Valid line
    valid = SubtitleLine(text="Test", start=0.0, end=5.0, words=[("Test", 0.0, 2.0)])
    assert validate_subtitle_line(valid, clip_duration=10.0) is True

    # Invalid: start >= end
    invalid_time = SubtitleLine(text="Test", start=5.0, end=5.0)
    assert validate_subtitle_line(invalid_time) is False

    # Invalid: negative start
    invalid_neg = SubtitleLine(text="Test", start=-1.0, end=3.0)
    assert validate_subtitle_line(invalid_neg) is False

    # Invalid: end > clip_duration
    invalid_clip = SubtitleLine(text="Test", start=0.0, end=15.0)
    assert validate_subtitle_line(invalid_clip, clip_duration=10.0) is False

    # Invalid: word overlap
    invalid_overlap = SubtitleLine(
        text="Test overlap",
        start=0.0,
        end=5.0,
        words=[("Test", 0.0, 3.0), ("overlap", 2.0, 5.0)]
    )
    assert validate_subtitle_line(invalid_overlap) is False

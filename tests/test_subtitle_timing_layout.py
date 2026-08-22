"""Unit tests cho hệ thống Subtitle Chunking, Whisper Timestamps, Active-Word Timing, 4 Tầng Emoji và Anti-Fake Title."""

import pytest
from pathlib import Path
from PIL import ImageFont

from batch_video_cutter.utils.word_timing import WordTiming, normalize_word_timings
from batch_video_cutter.utils.subtitle import (
    SubtitleLine,
    SubtitleChunk,
    SubtitleChunker,
    build_subtitle_chunks,
    extract_emoji_for_phrase,
    SubtitleLayoutEngine,
)
from batch_video_cutter.core.analyzer import _extract_spoken_headline, count_title_words


def test_subtitle_chunker_unification():
    """Kiểm tra SubtitleChunker.chunk_lines và build_subtitle_chunks trả về kết quả đồng nhất 100%."""
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 30)
    lines = [
        SubtitleLine(
            text="The quick brown fox jumps over the lazy dog in the courtroom",
            start=1.0,
            end=5.0,
            words=[
                ("The", 1.0, 1.3),
                ("quick", 1.3, 1.7),
                ("brown", 1.7, 2.1),
                ("fox", 2.1, 2.5),
                ("jumps", 2.5, 3.0),
                ("over", 3.0, 3.4),
                ("the", 3.4, 3.7),
                ("lazy", 3.7, 4.1),
                ("dog", 4.1, 4.5),
            ],
            timestamp_source="whisper",
        )
    ]

    chunks_class = SubtitleChunker.chunk_lines(lines, font, max_width_px=880)
    chunks_fn = build_subtitle_chunks(lines, font, max_width_px=880)

    assert len(chunks_class) == len(chunks_fn)
    for c1, c2 in zip(chunks_class, chunks_fn):
        assert c1.start == c2.start
        assert c1.end == c2.end
        assert c1.line1_words == c2.line1_words
        assert c1.line2_words == c2.line2_words
        assert c1.emoji == c2.emoji


def test_whisper_timestamp_source_of_truth():
    """Kiểm tra mốc thời gian (start, end) của từ Whisper được bảo toàn làm Source of Truth."""
    raw_words = [
        WordTiming(text="Hello", start=10.1234, end=10.5678, timing_source="whisper"),
        WordTiming(text="World", start=10.5678, end=11.2345, timing_source="whisper"),
    ]

    normalized = normalize_word_timings(raw_words, range_start=10.0, range_end=12.0)
    assert len(normalized) == 2
    assert normalized[0].start == 10.1234
    assert normalized[0].end == 10.5678
    assert normalized[1].start == 10.5678
    assert normalized[1].end == 11.2345
    assert normalized[0].timing_source == "whisper"


def test_emoji_selection_4_tiers():
    """Kiểm tra quy trình chọn Emoji tuân thủ 4 tầng ưu tiên (Semantic -> Keyword -> Emotion -> Fallback Deterministic MD5)."""
    # Tier 1: Semantic Match
    assert extract_emoji_for_phrase("This is a shocking truth revealed") == "😱"

    # Tier 2: Direct Keyword Match
    assert extract_emoji_for_phrase("He spent a lot of money today") == "💰"

    # Tier 3: Emotion / Punctuation Match (không có keyword Tier 2)
    assert extract_emoji_for_phrase("Why did you do that?") == "🤔"
    assert extract_emoji_for_phrase("That was incredible!") == "🔥"
    assert extract_emoji_for_phrase("We can't accept this offer") == "⚡"

    # Tier 4: Fallback Deterministic Match (MD5 hash 100% nhất quán khi opt-in qua fallback_default=True)
    text_fallback = "The court session resumed after the short break"
    emoji1 = extract_emoji_for_phrase(text_fallback, fallback_default=True)
    emoji2 = extract_emoji_for_phrase(text_fallback, fallback_default=True)
    assert emoji1 is not None
    assert emoji1 == emoji2  # 100% deterministic (không ngẫu nhiên)


def test_no_fake_title_on_llm_fail():
    """Kiểm tra _extract_spoken_headline không tự bịa title giả hoặc từ rác khi transcript rỗng/thiếu từ."""
    # Transcript quá ngắn (< 8 từ)
    short_transcript = "[00:10] Hello world"
    title = _extract_spoken_headline(short_transcript, 0.0, 30.0)
    assert title == ""  # Trả về rỗng thay vì bịa title

    # Transcript rỗng
    empty_title = _extract_spoken_headline("", 0.0, 30.0)
    assert empty_title == ""

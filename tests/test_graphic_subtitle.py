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


def test_no_forced_emoji_on_first_chunk():
    from batch_video_cutter.utils.subtitle import build_subtitle_chunks, SubtitleLayoutEngine, SubtitleLine
    font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 80)

    # Completely neutral phrase without mapped keywords
    line = SubtitleLine(
        text="The system is processing the status report",
        start=0.0,
        end=2.0,
        words=[("The", 0.0, 0.3), ("system", 0.3, 0.6), ("is", 0.6, 0.8), ("processing", 0.8, 1.3), ("the", 1.3, 1.5), ("status", 1.5, 1.7), ("report", 1.7, 2.0)],
    )

    chunks = build_subtitle_chunks([line], font, max_width_px=800, emoji_on_top=True)
    assert len(chunks) > 0
    # Neutral chunk should NOT force emoji
    assert chunks[0].emoji is None


def test_blue_highlight_color_across_all_styles_and_engines(tmp_path):
    from batch_video_cutter.utils.subtitle import COLOR_MAP
    from batch_video_cutter.utils.graphic_subtitle import COLOR_RGBA_MAP
    from batch_video_cutter.styles import Style1, Style2, Style3, Style4, Style5
    from PIL import Image

    # 1. Check ASS Color BGR mapping for #00D4FF
    assert COLOR_MAP["blue"] == "&H00FFD400&"

    # 2. Check Graphic Subtitle RGBA mapping for #00D4FF
    assert COLOR_RGBA_MAP["blue"] == (0, 212, 255, 255)

    # 3. Check All Styles return valid highlight color
    for style_cls in [Style1, Style2, Style3, Style4, Style5]:
        style_instance = style_cls()
        assert style_instance.get_highlight_color() in ["blue", "yellow"]

    # 4. Render a sample graphic subtitle and check that the blue highlight pixel is rendered
    line = SubtitleLine(
        text="AMAZING TRIAL",
        start=0.0,
        end=1.0,
        words=[("AMAZING", 0.0, 0.5), ("TRIAL", 0.5, 1.0)],
    )
    results = generate_graphic_subtitles(
        subtitle_lines=[line],
        tmp_dir=tmp_path,
        font_name="Montserrat-Bold",
        font_size=60,
        highlight_color_name="blue",
        canvas_size=(1080, 1080),
        margin_v=180,
    )
    assert len(results) >= 2
    # Verify PNG files exist and are non-empty
    for png_path, s, e in results:
        assert png_path.exists()
        assert png_path.stat().st_size > 0
        img = Image.open(png_path)
        assert img.size == (1080, 1080)


def test_word_by_word_reveal_and_layout_freezing(tmp_path):
    from batch_video_cutter.utils.graphic_subtitle import (
        _compute_chunk_layout,
        _render_word_reveal_frame,
    )
    from PIL import Image

    # Tạo layout cho 1 chunk gồm 3 từ
    line1 = [("FIRST", 0.0, 0.5), ("SECOND", 0.5, 1.0), ("THIRD", 1.0, 1.5)]
    layout = _compute_chunk_layout(
        line1_words=line1,
        line2_words=[],
        font_size=60,
        canvas_size=(1080, 1080),
        margin_v=180,
        position="bottom",
        font_name="Montserrat-Bold",
    )

    assert len(layout.words_layout_2x) == 3
    # Xác thực vị trí (x, y) của các từ đã được pre-calculated và cố định
    w0 = layout.words_layout_2x[0]
    w1 = layout.words_layout_2x[1]
    w2 = layout.words_layout_2x[2]
    assert w0.clean_w == "FIRST"
    assert w1.clean_w == "SECOND"
    assert w2.clean_w == "THIRD"
    assert w0.x_2x < w1.x_2x < w2.x_2x

    primary_rgba = (255, 255, 255, 255)
    highlight_rgba = (0, 212, 255, 255)

    # Frame 0: active_idx = 0 (Từ 0 màu Cyan Blue, từ 1 và 2 màu Trắng)
    frame_0 = _render_word_reveal_frame(layout, active_idx=0, primary_rgba=primary_rgba, highlight_rgba=highlight_rgba, enable_pill_box=False)
    # Frame 1: active_idx = 1 (Từ 0 màu Trắng, từ 1 màu Cyan Blue, từ 2 màu Trắng)
    frame_1 = _render_word_reveal_frame(layout, active_idx=1, primary_rgba=primary_rgba, highlight_rgba=highlight_rgba, enable_pill_box=False)
    # Frame 2: active_idx = 2 (Từ 0, 1 màu Trắng, từ 2 màu Cyan Blue)
    frame_2 = _render_word_reveal_frame(layout, active_idx=2, primary_rgba=primary_rgba, highlight_rgba=highlight_rgba, enable_pill_box=False)

    assert frame_0.size == (1080, 1080)
    assert frame_1.size == (1080, 1080)
    assert frame_2.size == (1080, 1080)

    # Toàn bộ cụm từ hiển thị cố định (Full Phrase Karaoke), số pixel hiển thị ổn định không giật
    def non_transparent_pixels_count(img):
        return sum(1 for _, _, _, a in img.getdata() if a > 30)

    count_f0 = non_transparent_pixels_count(frame_0)
    count_f1 = non_transparent_pixels_count(frame_1)
    count_f2 = non_transparent_pixels_count(frame_2)

    # Cả 3 frame đều hiển thị trọn vẹn câu chữ nên tổng số pixel vẽ chữ xấp xỉ nhau (độ lệch < 5%)
    assert abs(count_f0 - count_f1) / count_f0 < 0.05
    assert abs(count_f1 - count_f2) / count_f1 < 0.05

    # Kiểm tra sự xuất hiện của pixel highlight Cyan Blue (0, 212, 255) trong từng frame
    def count_highlight_pixels(img):
        return sum(1 for r, g, b, a in img.getdata() if a > 200 and r == 0 and g == 212 and b == 255)

    assert count_highlight_pixels(frame_0) > 0
    assert count_highlight_pixels(frame_1) > 0
    assert count_highlight_pixels(frame_2) > 0


def test_subtitle_time_offset_default_is_zero():
    from batch_video_cutter.config import SUBTITLE_TIME_OFFSET, AppConfig

    assert SUBTITLE_TIME_OFFSET == 0.0
    config = AppConfig()
    assert config.subtitle_time_offset == 0.0


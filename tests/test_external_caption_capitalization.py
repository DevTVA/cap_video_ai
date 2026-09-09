"""Unit tests for external caption formatting and Style 5 yellow highlight.
"""

import pytest
from pathlib import Path
from batch_video_cutter.styles.factory import get_style_by_index
from batch_video_cutter.utils.graphic_subtitle import (
    capitalize_sentence_start,
    format_external_caption,
    generate_graphic_subtitles,
    COLOR_RGBA_MAP,
)
from batch_video_cutter.utils.subtitle import SubtitleLine


def test_capitalize_sentence_start():
    assert capitalize_sentence_start("woman drinks wine") == "Woman drinks wine"
    assert capitalize_sentence_start("“woman drinks wine”") == "“Woman drinks wine”"
    assert capitalize_sentence_start("123 test") == "123 Test"
    assert capitalize_sentence_start("🍷 woman drinks wine") == "🍷 Woman drinks wine"
    assert capitalize_sentence_start("") == ""


def test_format_external_caption():
    raw_title = "woman drinks $2,000 wine"
    res = format_external_caption(raw_title)
    # Phải viết hoa chữ W ở đầu câu và chứa emoji ở cuối
    assert res[0] == "W"
    assert "Woman drinks $2,000 wine" in res


def test_style_5_highlight_color():
    style5 = get_style_by_index(5)
    color_name = style5.get_highlight_color()
    assert color_name == "green"
    assert COLOR_RGBA_MAP[color_name] == (0, 255, 0, 255)


def test_all_styles_highlight_colors():
    for i in range(1, 6):
        s = get_style_by_index(i)
        assert s.get_highlight_color() == "green", f"Style {i} phải có màu highlight là 'green'"


def test_graphic_subtitle_yellow_highlight(tmp_path):
    line = SubtitleLine(
        text="Test yellow subtitle color",
        start=0.0,
        end=2.0,
        words=[
            ("Test", 0.0, 0.5),
            ("yellow", 0.5, 1.0),
            ("subtitle", 1.0, 1.5),
            ("color", 1.5, 2.0),
        ],
    )

    results = generate_graphic_subtitles(
        subtitle_lines=[line],
        tmp_dir=tmp_path,
        font_name="Montserrat-Bold",
        highlight_color_name="yellow",
    )

    assert len(results) > 0
    for img_path, s, e in results:
        assert img_path.exists()

"""Unit tests kiểm tra tính đồng bộ chuẩn vị trí, font và mẫu phụ đề trên toàn bộ Style."""

import pytest
from batch_video_cutter.styles import (
    BaseStyle,
    Style1,
    Style2,
    Style3,
    Style4,
    Style5,
    Style6,
    HIGHLIGHT_COLOR_YELLOW,
    HIGHLIGHT_COLOR_BLUE,
    get_style_by_index,
)
from batch_video_cutter.utils.graphic_subtitle import (
    _compute_chunk_layout,
    _render_word_reveal_frame,
)
from PIL import Image


def test_all_styles_standardized_font_and_position():
    """Kiểm tra toàn bộ Style 1..6 tuân thủ 100% chuẩn font size, position và highlight color."""
    styles = [Style1(), Style2(), Style3(), Style4(), Style5(), Style6()]

    for s in styles:
        # 1. Kích thước font chuẩn hóa toàn hệ thống: 66pt
        assert s.get_font_size() == 66, f"{s.name} không có font size 66"

        # 2. Vị trí phụ đề luôn là bottom
        assert s.get_subtitle_position() == "bottom", f"{s.name} không có position bottom"

        # 3. Màu highlight chuẩn: HIGHLIGHT_COLOR_YELLOW (Vàng tươi neon)
        assert s.get_highlight_color() == HIGHLIGHT_COLOR_YELLOW, f"{s.name} không có highlight yellow"

        # 4. Font name chuẩn
        assert s.get_font_name() in ("Impact", "Montserrat-Bold")


def test_pill_box_rendering():
    """Kiểm tra render frame phụ đề mẫu Pill Box CapCut (hộp nền đen mờ bo góc)."""
    words_line1 = [("CAPCUT", 0.0, 0.5), ("PILL", 0.5, 1.0), ("BOX", 1.0, 1.5)]
    layout = _compute_chunk_layout(
        line1_words=words_line1,
        line2_words=[],
        font_size=66,
        canvas_size=(1080, 1080),
        margin_v=110,
        position="bottom",
    )

    frame = _render_word_reveal_frame(
        layout=layout,
        active_idx=1,
        highlight_rgba=(255, 230, 0, 255),
        enable_pill_box=True,
    )

    assert isinstance(frame, Image.Image)
    assert frame.size == (1080, 1080)
    # Kiểm tra ảnh có alpha channel và không bị rỗng
    bbox = frame.getbbox()
    assert bbox is not None, "Frame Pill Box không được rỗng"


def test_safe_zone_margin_v_by_canvas_height():
    """Kiểm tra khoảng cách lề dưới phụ đề (margin_v) tính tự động chuẩn theo Safe Zone từng Canvas."""
    s1 = Style1()  # 1080x1080 -> 110px
    s2 = Style2()  # 1080x1440 (3:4) -> 160px
    s3 = Style3()  # 1080x1080 -> 110px
    s4 = Style4()  # 1080x1440 (3:4) -> 160px
    s5 = Style5()  # 1080x1080 -> 110px
    s6 = Style6()  # 1080x1920 (9:16) -> 330px (TikTok safe zone)

    assert s1.get_margin_v() == 110
    assert s2.get_margin_v() == 160
    assert s3.get_margin_v() == 110
    assert s4.get_margin_v() == 160
    assert s5.get_margin_v() == 110
    assert s6.get_margin_v() == 330


def test_style_factory_integration():
    """Kiểm tra Factory nhận diện đúng Style 6."""
    s6 = get_style_by_index(6)
    assert isinstance(s6, Style6)
    assert s6.aspect_ratio == "9:16"
    assert s6.get_output_resolution() == (1080, 1920)

    # Filter complex chứa ass filter hoặc overlay
    flt, label = s6.get_ffmpeg_filter(1920, 1080, subtitle_path="test.ass")
    assert "test.ass" in flt
    assert label == "[out]"

"""Unit tests kiểm tra tích hợp font MYRIADPRO-BLACK_0 vào Top Caption Engine."""

import pytest
from pathlib import Path
from PIL import Image
from batch_video_cutter.utils.subtitle import SubtitleLayoutEngine
from batch_video_cutter.utils.graphic_subtitle import (
    generate_top_caption_layer,
    TOP_CAPTION_FONT_NAME,
    format_top_caption_lines,
)


def test_myriad_pro_font_loaded_from_assets():
    """Kiểm tra SubtitleLayoutEngine nạp chính xác font MYRIADPRO-BLACK_0 từ assets/fonts/."""
    font = SubtitleLayoutEngine.get_font("MYRIADPRO-BLACK_0", 36)
    assert font is not None
    font_name_info = font.getname()
    assert font_name_info[0] == "Myriad Pro"
    assert font_name_info[1] == "Black"


def test_top_caption_font_name_constant():
    """Kiểm tra TOP_CAPTION_FONT_NAME mặc định là MYRIADPRO-BLACK_0."""
    assert TOP_CAPTION_FONT_NAME == "MYRIADPRO-BLACK_0"


def test_render_top_caption_myriad_pro_style3(tmp_path: Path):
    """Kiểm tra render Top Caption Style 3 (Dải nền vàng) với font MYRIADPRO-BLACK_0."""
    out_png = tmp_path / "top_cap_s3.png"
    result = generate_top_caption_layer(
        title_text="BABYSITTER ACCUSED OF STEALING EXPENSIVE DIAMOND RING",
        output_png=out_png,
        canvas_size=(1080, 1080),
        top_area_height=180,
        style_index=3,
        font_name="MYRIADPRO-BLACK_0",
    )
    assert result is not None
    assert result.exists()

    with Image.open(result) as img:
        assert img.size == (1080, 1080)
        assert img.mode == "RGBA"
        bbox = img.getbbox()
        assert bbox is not None
        # Kiểm tra nội dung nằm trong dải 180px phía trên
        assert bbox[1] >= 0
        assert bbox[3] <= 181


def test_render_top_caption_myriad_pro_style4(tmp_path: Path):
    """Kiểm tra render Top Caption Style 4 (Stepped White Badge) với font MYRIADPRO-BLACK_0."""
    out_png = tmp_path / "top_cap_s4.png"
    result = generate_top_caption_layer(
        title_text="HUSBAND CAUGHT LYING UNDER OATH DURING DIVORCE TRIAL",
        output_png=out_png,
        canvas_size=(1080, 1440),
        top_area_height=280,
        style_index=4,
        font_name="MYRIADPRO-BLACK_0",
    )
    assert result is not None
    assert result.exists()

    with Image.open(result) as img:
        assert img.size == (1080, 1440)
        assert img.mode == "RGBA"
        bbox = img.getbbox()
        assert bbox is not None
        assert bbox[1] >= 0
        assert bbox[3] <= 280


def test_render_top_caption_myriad_pro_style5(tmp_path: Path):
    """Kiểm tra render Top Caption Style 5 (Dải nền xanh dương chữ trắng) với font MYRIADPRO-BLACK_0."""
    out_png = tmp_path / "top_cap_s5.png"
    result = generate_top_caption_layer(
        title_text="DOCTOR REVEALS SHOCKING MEDICAL TEST RESULTS TO FAMILY",
        output_png=out_png,
        canvas_size=(1080, 1080),
        top_area_height=180,
        style_index=5,
        font_name="MYRIADPRO-BLACK_0",
    )
    assert result is not None
    assert result.exists()

    with Image.open(result) as img:
        assert img.size == (1080, 1080)
        assert img.mode == "RGBA"
        bbox = img.getbbox()
        assert bbox is not None
        assert bbox[1] >= 0
        assert bbox[3] <= 181


def test_top_caption_layout_formatting_with_myriad_pro():
    """Kiểm tra thuật toán ngắt 2 dòng Soft Constraint w1 < w2 với font Myriad Pro Black."""
    font = SubtitleLayoutEngine.get_font("MYRIADPRO-BLACK_0", 36)
    words = ["MEGAN", "RAPINOE", "REACTS", "TO", "CONTROVERSIAL", "WORLD", "CUP", "DRAMA"]
    res = format_top_caption_lines(words, font, max_text_w=936)

    assert len(res) == 2
    assert res.w1 < res.w2
    assert res[0] == "MEGAN RAPINOE REACTS TO"
    assert res[1] == "CONTROVERSIAL WORLD CUP DRAMA"

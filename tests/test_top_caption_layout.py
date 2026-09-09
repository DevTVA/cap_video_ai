"""Unit tests for Top Caption layout:
- Bỏ hoàn toàn dấu ngoặc kép ""
- Bảo toàn 100% từ ngữ (không cắt bớt, không deduplicate từ lặp tự nhiên)
- Ràng buộc Soft Constraint w1 < w2 và Graceful Fallback
- Tìm kiếm nhị phân font size & Auto-scale
- Các edge case: từ bất đối xứng, siêu từ 1 từ, câu siêu dài 30 từ.
"""

from pathlib import Path
import pytest
from PIL import ImageFont
from batch_video_cutter.utils.subtitle import SubtitleLayoutEngine
from batch_video_cutter.utils.graphic_subtitle import (
    format_top_caption_lines,
    generate_top_caption_layer,
    ensure_caption_8_to_10_words,
    CaptionLayoutResult,
    TARGET_TOP_CAPTION_RATIO,
)


@pytest.fixture
def montserrat_font():
    return SubtitleLayoutEngine.get_font("Montserrat-Bold", 36)


def test_no_quotation_marks_in_output(montserrat_font):
    """Kiểm tra không bao giờ có dấu ngoặc kép trong bất kỳ dòng nào của caption."""
    words = ["MEGAN", "RAPINOE", "REACTS", "TO", "CONTROVERSIAL", "WORLD", "CUP", "DRAMA"]
    res = format_top_caption_lines(words, montserrat_font, max_text_w=936)

    for line in res.lines:
        assert '"' not in line, f"Dòng chứa dấu ngoặc kép: {line}"
        assert "'" not in line


def test_megan_rapinoe_example_layout(montserrat_font):
    """Test sample headline: 'MEGAN RAPINOE REACTS TO CONTROVERSIAL WORLD CUP DRAMA'."""
    words = ["MEGAN", "RAPINOE", "REACTS", "TO", "CONTROVERSIAL", "WORLD", "CUP", "DRAMA"]
    res = format_top_caption_lines(words, montserrat_font, max_text_w=936)

    assert isinstance(res, CaptionLayoutResult)
    assert len(res) == 2
    assert res.w1 > 0
    assert res.w2 > 0

    # Invariant check
    if not res.constraint_unmet:
        assert res.w1 < res.w2, f"Expected w1 < w2 but got w1={res.w1}, w2={res.w2}"

    # Kiểm tra chính xác nội dung tách dòng sạch, không có dấu nháy
    assert res[0] == "MEGAN RAPINOE REACTS TO"
    assert res[1] == "CONTROVERSIAL WORLD CUP DRAMA"


def test_preserves_repeated_words():
    """Kiểm tra không tự ý xóa từ lặp tự nhiên (ví dụ 'very very', 'had had')."""
    text = "It was a very very good day and she had had enough"
    words = ensure_caption_8_to_10_words(text)

    # Khẳng định cả hai từ VERY đều được giữ nguyên
    assert words.count("VERY") == 2
    assert words.count("HAD") == 2
    assert len(words) == 12  # Giữ nguyên 100% 12 từ, không bị cắt bớt


def test_asymmetric_words_graceful_fallback(montserrat_font):
    """Edge Case 1: Từ bất đối xứng 'Congratulations, bro!' không thể tạo w1 < w2 -> Fallback mượt mà."""
    words = ["CONGRATULATIONS,", "BRO!"]
    res = format_top_caption_lines(words, montserrat_font, max_text_w=936)

    assert len(res) == 2
    assert res.constraint_unmet is True
    assert res[0] == "CONGRATULATIONS,"
    assert res[1] == "BRO!"
    assert '"' not in res[0] and '"' not in res[1]


def test_single_word_caption(montserrat_font):
    """Kiểm tra trường hợp đặc biệt chỉ có 1 từ duy nhất."""
    words = ["BREAKING"]
    res = format_top_caption_lines(words, montserrat_font, max_text_w=936)

    assert len(res) == 1
    assert res[0] == "BREAKING"
    assert '"' not in res[0]


def test_super_long_single_word_auto_scale(tmp_path):
    """Edge Case 2: Siêu từ không khoảng trắng -> Auto-scale vừa vặn khung mà không bị cắt chữ."""
    super_word = "SUPERCALIFRAGILISTICEXPIALIDOCIOUS"
    out_png = tmp_path / "super_word.png"

    res_path = generate_top_caption_layer(
        title_text=super_word,
        output_png=out_png,
        canvas_size=(1080, 1440),
        style_index=4,
    )

    assert res_path is not None
    assert res_path.exists()
    assert res_path.stat().st_size > 0


def test_super_long_sentence_30_words_preserves_all_words(tmp_path):
    """Edge Case 3: Câu siêu dài 30 từ -> Giữ nguyên 100% từ và tự động scale font."""
    sentence = (
        "THIS IS A VERY DETAILED HEADLINE DESIGNED TO TEST THE MAXIMUM CAPACITY "
        "OF THE TOP CAPTION ENGINE WITH EXACTLY THIRTY WORDS IN TOTAL WITHOUT ANY "
        "DROPPED WORDS EVER AND ALWAYS"
    )
    words = ensure_caption_8_to_10_words(sentence)
    assert len(words) == 30  # Giữ trọn vẹn 30 từ!

    out_png = tmp_path / "long_sentence.png"
    res_path = generate_top_caption_layer(
        title_text=sentence,
        output_png=out_png,
        canvas_size=(1080, 1440),
        style_index=4,
    )

    assert res_path is not None
    assert res_path.exists()


def test_generate_top_caption_all_styles(tmp_path):
    """Kiểm tra render file PNG thực tế trên cả 3 phong cách: Style 3, Style 4, Style 5."""
    title = "JUDGE SHOCKED BY UNEXPECTED CONFESSION IN COURTROOM"

    # Style 3 (1080x1080 - Vàng)
    p3 = generate_top_caption_layer(
        title_text=title,
        output_png=tmp_path / "style_3.png",
        canvas_size=(1080, 1080),
        style_index=3,
    )
    assert p3.exists()

    # Style 4 (1080x1440 - White Badge)
    p4 = generate_top_caption_layer(
        title_text=title,
        output_png=tmp_path / "style_4.png",
        canvas_size=(1080, 1440),
        style_index=4,
    )
    assert p4.exists()

    # Style 5 (1080x1440 - Xanh)
    p5 = generate_top_caption_layer(
        title_text=title,
        output_png=tmp_path / "style_5.png",
        canvas_size=(1080, 1440),
        style_index=5,
    )
    assert p5.exists()

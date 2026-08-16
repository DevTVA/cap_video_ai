"""Test style-specific intro and outro offsets."""

from batch_video_cutter.styles.style_1 import Style1
from batch_video_cutter.styles.style_2 import Style2
from batch_video_cutter.styles.style_3 import Style3
from batch_video_cutter.styles.style_4 import Style4
from batch_video_cutter.styles.style_5 import Style5


def test_style_1_2_offsets():
    s1 = Style1()
    s2 = Style2()

    assert s1.get_intro_offset() == 3.0
    assert s1.get_outro_offset() == 30.0

    assert s2.get_intro_offset() == 3.0
    assert s2.get_outro_offset() == 30.0


def test_style_3_4_5_default_offsets():
    s3 = Style3()
    s4 = Style4()
    s5 = Style5()

    assert s3.get_intro_offset() == 35.0
    assert s3.get_outro_offset() == 25.0

    assert s4.get_intro_offset() == 35.0
    assert s4.get_outro_offset() == 25.0

    assert s5.get_intro_offset() == 35.0
    assert s5.get_outro_offset() == 25.0

import functools
from pathlib import Path
from unittest.mock import patch, MagicMock
from batch_video_cutter.utils.graphic_subtitle import (
    _get_font,
    generate_concat_manifest,
)
from batch_video_cutter.core.engine import cut_and_render_clip
from batch_video_cutter.styles.style_1 import Style1


def test_font_cache():
    # Kiểm tra lru_cache của _get_font
    font1 = _get_font("Impact", 66)
    font2 = _get_font("Impact", 66)
    assert font1 is font2, "Font instance nên được cache từ lru_cache"


def test_generate_concat_manifest(tmp_path):
    png1 = tmp_path / "g_sub_0001.png"
    png1.touch()
    png2 = tmp_path / "g_sub_0002.png"
    png2.touch()

    graphic_results = [
        (png1, 0.0, 1.0),
        (png2, 1.5, 2.5),
    ]

    manifest_p = generate_concat_manifest(
        graphic_results=graphic_results,
        tmp_dir=tmp_path,
        canvas_size=(1080, 1080),
        clip_duration=3.0,
    )

    assert manifest_p.exists()
    content = manifest_p.read_text(encoding="utf-8")
    assert "blank_transparent.png" in content
    assert "g_sub_0001.png" in content
    assert "g_sub_0002.png" in content
    assert "duration 1.000" in content


@patch("subprocess.Popen")
@patch("batch_video_cutter.core.engine.get_video_resolution", return_value=(1920, 1080))
def test_cut_and_render_clip_concat_manifest(mock_res, mock_popen, tmp_path):
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    video_p = tmp_path / "dummy.mp4"
    video_p.touch()
    out_p = tmp_path / "out.mp4"
    style = Style1()

    png1 = tmp_path / "g_sub_0001.png"
    png1.touch()

    timed_emojis = [
        (png1, 0.0, 2.0),
    ]

    cut_and_render_clip(
        video_path=video_p,
        start_time=0.0,
        end_time=5.0,
        output_path=out_p,
        style=style,
        timed_emojis=timed_emojis,
        enable_gpu=False,
    )

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    cmd_str = " ".join(cmd)

    assert "-f concat" in cmd_str
    assert "g_subs_concat.txt" in cmd_str
    assert "fps=30" in cmd_str
    assert "format=yuva420p" in cmd_str

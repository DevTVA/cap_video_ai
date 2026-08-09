from pathlib import Path
from unittest.mock import patch, MagicMock
from batch_video_cutter.core.engine import cut_and_render_clip
from batch_video_cutter.styles.style_1 import Style1

@patch("subprocess.Popen")
@patch("batch_video_cutter.core.engine.get_video_resolution", return_value=(1920, 1080))
def test_cut_and_render_clip_with_custom_encoder(mock_res, mock_popen, tmp_path):
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    video_p = tmp_path / "dummy.mp4"
    video_p.touch()
    out_p = tmp_path / "out.mp4"
    style = Style1()

    cut_and_render_clip(
        video_path=video_p,
        start_time=0.0,
        end_time=10.0,
        output_path=out_p,
        style=style,
        enable_gpu=True,
        cpu_preset="ultrafast",
        threads=4
    )

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert "ffmpeg" in cmd
    assert "-threads" in cmd

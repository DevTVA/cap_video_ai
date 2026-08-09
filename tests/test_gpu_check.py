from pathlib import Path
from batch_video_cutter.config import AppConfig
from batch_video_cutter.utils.ffmpeg_check import get_best_video_encoder

def test_app_config_render_settings():
    config = AppConfig(
        use_gpu=True,
        ffmpeg_preset="ultrafast",
        max_render_workers=4
    )
    assert config.use_gpu is True
    assert config.ffmpeg_preset == "ultrafast"
    assert config.max_render_workers == 4

def test_get_best_video_encoder():
    encoder, codec_args = get_best_video_encoder(enable_gpu=True, cpu_preset="ultrafast")
    assert isinstance(encoder, str)
    assert isinstance(codec_args, list)
    assert len(codec_args) > 0

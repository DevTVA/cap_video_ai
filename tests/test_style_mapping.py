"""Test default style mapping and resolution logic for 48 folders."""

from batch_video_cutter.config import AppConfig
from batch_video_cutter.styles.factory import parse_style_mapping, resolve_style_for_folder
from batch_video_cutter.styles.style_2 import Style2
from batch_video_cutter.styles.style_3 import Style3
from batch_video_cutter.styles.style_4 import Style4
from batch_video_cutter.styles.style_5 import Style5


def test_default_config_style_mapping_string():
    config = AppConfig()
    assert config.style_mapping_str == "1-36:3,37-42:4,43-48:5"


def test_cli_style_map_default_matches_config():
    from batch_video_cutter.ui.cli import main_cli
    from batch_video_cutter.config import DEFAULT_STYLE_MAPPING

    # Tìm param style_map trong click command params
    param = next((p for p in main_cli.params if p.name == "style_map"), None)
    assert param is not None, "Param style_map phải tồn tại trong CLI command"
    assert param.default == DEFAULT_STYLE_MAPPING
    assert param.default == "1-36:3,37-42:4,43-48:5"


def test_parse_and_resolve_48_folders():
    mapping_str = "1-36:3,37-42:4,43-48:5"
    mapping = parse_style_mapping(mapping_str)

    # Folders 1 to 36 should resolve to Style 3
    for f_idx in [1, 18, 36]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style3), f"Folder {f_idx} should be Style3"

    # Folders 37 to 42 should resolve to Style 4
    for f_idx in [37, 40, 42]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style4), f"Folder {f_idx} should be Style4"

    # Folders 43 to 48 should resolve to Style 5
    for f_idx in [43, 45, 48]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style5), f"Folder {f_idx} should be Style5"


def test_all_styles_clip_counts():
    from batch_video_cutter.styles.style_1 import Style1
    from batch_video_cutter.styles.style_2 import Style2
    from batch_video_cutter.styles.style_3 import Style3
    from batch_video_cutter.styles.style_4 import Style4
    from batch_video_cutter.styles.style_5 import Style5

    assert Style1().get_max_clips() == 2
    assert Style2().get_max_clips() == 2
    assert Style3().get_max_clips() == 3
    assert Style4().get_max_clips() == 3
    assert Style5().get_max_clips() == 2





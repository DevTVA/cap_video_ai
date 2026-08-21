"""Test default style mapping and resolution logic for 48 folders."""

from batch_video_cutter.config import AppConfig
from batch_video_cutter.styles.factory import parse_style_mapping, resolve_style_for_folder
from batch_video_cutter.styles.style_2 import Style2
from batch_video_cutter.styles.style_3 import Style3
from batch_video_cutter.styles.style_4 import Style4
from batch_video_cutter.styles.style_5 import Style5


def test_default_config_style_mapping_string():
    config = AppConfig()
    assert config.style_mapping_str == "1-12:2,13-24:4,25-36:3,37-48:5"


def test_parse_and_resolve_48_folders():
    mapping_str = "1-12:2,13-24:4,25-36:3,37-48:5"
    mapping = parse_style_mapping(mapping_str)

    # Folders 1 to 12 should resolve to Style 2
    for f_idx in [1, 6, 12]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style2), f"Folder {f_idx} should be Style2"

    # Folders 13 to 24 should resolve to Style 4
    for f_idx in [13, 18, 24]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style4), f"Folder {f_idx} should be Style4"

    # Folders 25 to 36 should resolve to Style 3
    for f_idx in [25, 30, 36]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style3), f"Folder {f_idx} should be Style3"

    # Folders 37 to 48 should resolve to Style 5
    for f_idx in [37, 42, 48]:
        style = resolve_style_for_folder(f_idx, mapping)
        assert isinstance(style, Style5), f"Folder {f_idx} should be Style5"




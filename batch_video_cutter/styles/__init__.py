from .base import BaseStyle, HIGHLIGHT_COLOR_GREEN, HIGHLIGHT_COLOR_YELLOW, HIGHLIGHT_COLOR_RED, HIGHLIGHT_COLOR_BLUE
from .style_1 import Style1
from .style_2 import Style2
from .style_3 import Style3
from .style_4 import Style4
from .style_5 import Style5
from .style_6 import Style6
from .factory import get_style_by_index, parse_style_mapping, resolve_style_for_folder

__all__ = [
    "BaseStyle",
    "HIGHLIGHT_COLOR_GREEN",
    "HIGHLIGHT_COLOR_YELLOW",
    "HIGHLIGHT_COLOR_RED",
    "HIGHLIGHT_COLOR_BLUE",
    "Style1",
    "Style2",
    "Style3",
    "Style4",
    "Style5",
    "Style6",
    "get_style_by_index",
    "parse_style_mapping",
    "resolve_style_for_folder",
]

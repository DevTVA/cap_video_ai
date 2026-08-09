"""Style factory to retrieve style instances based on style numbers or mapping rules.
"""

from typing import Dict, Optional
from .base import BaseStyle
from .style_1 import Style1
from .style_2 import Style2
from .style_3 import Style3
from .style_4 import Style4
from .style_5 import Style5

STYLES_MAP: Dict[int, BaseStyle] = {
    1: Style1(),
    2: Style2(),
    3: Style3(),
    4: Style4(),
    5: Style5(),
}


def get_style_by_index(index: int) -> BaseStyle:
    """Returns the style instance for a given numeric index (1..5).

    Falls back to Style1 if index is out of range.
    """
    return STYLES_MAP.get(index, STYLES_MAP[1])


def parse_style_mapping(mapping_str: str) -> Dict[range, int]:
    """Parse mapping string like '1-12:1,13-24:2,25-50:3'.

    Returns:
        Dict mapping range objects to style indices (int).
    """
    mapping: Dict[range, int] = {}
    if not mapping_str:
        return mapping

    pairs = mapping_str.split(",")
    for pair in pairs:
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        range_part, style_part = pair.split(":", 1)
        style_idx = int(style_part.strip())

        if "-" in range_part:
            start_str, end_str = range_part.split("-", 1)
            start_idx = int(start_str.strip())
            end_idx = int(end_str.strip())
            mapping[range(start_idx, end_idx + 1)] = style_idx
        else:
            idx = int(range_part.strip())
            mapping[range(idx, idx + 1)] = style_idx

    return mapping


def resolve_style_for_folder(folder_index: int, mapping: Dict[range, int], default_style: int = 1) -> BaseStyle:
    """Resolve the correct BaseStyle for a given folder_index based on range mapping."""
    for rng, style_idx in mapping.items():
        if folder_index in rng:
            return get_style_by_index(style_idx)
    return get_style_by_index(default_style)

"""Emoji Manager to map Unicode Emojis to HD Color PNG files in emojis_cache.

Quản lý và ánh xạ ký tự Emoji sang file PNG màu sắc độ phân giải cao trong emojis_cache.
"""

import re
from pathlib import Path
from typing import Optional
from loguru import logger

PROJECT_ROOT = Path(__file__).parent.parent.parent
EMOJIS_CACHE_DIR = PROJECT_ROOT / "emojis_cache"
ASSETS_EMOJIS_DIR = Path(__file__).parent.parent / "assets" / "emojis"

# Regex match emoji Unicode (bao gồm emoji sequences, modifiers, ZWJ)
_EMOJI_RE = re.compile(
    r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
    r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
    r'\U00002702-\U000027B0\U00002600-\U000026FF\U0000FE00-\U0000FE0F'
    r'\U0000200D\U00002934-\U00002B55\U0000203C-\U00003299]+'
)


def get_emoji_png_path(emoji_str: str) -> Optional[Path]:
    """Lấy đường dẫn file PNG cho ký tự Emoji từ emojis_cache hoặc assets/emojis."""
    if not emoji_str:
        return None

    # Tối ưu hóa chuỗi hex (loại bỏ variation selector 0xfe0f)
    hex_code = "-".join(f"{ord(c):x}" for c in emoji_str if ord(c) != 0xFE0F)

    # 1. Tìm trong emojis_cache
    if EMOJIS_CACHE_DIR.exists():
        target = EMOJIS_CACHE_DIR / f"{hex_code}.png"
        if target.exists():
            return target

        # Thử từng ký tự riêng biệt
        for c in emoji_str:
            target_c = EMOJIS_CACHE_DIR / f"{ord(c):x}.png"
            if target_c.exists():
                return target_c

    # 2. Tìm trong assets/emojis
    if ASSETS_EMOJIS_DIR.exists():
        for c in emoji_str:
            target_asset = ASSETS_EMOJIS_DIR / f"{ord(c):x}.png"
            if target_asset.exists():
                return target_asset

    return None


def extract_emoji_from_text(text: str) -> str:
    """Trích xuất ký tự emoji cuối cùng từ chuỗi text bất kỳ.

    Args:
        text: Chuỗi tiêu đề/caption có chứa emoji (ví dụ: 'Shocking Truth 💥').

    Returns:
        Chuỗi emoji cuối cùng (ví dụ: '💥'), hoặc chuỗi rỗng nếu không tìm thấy.
    """
    if not text:
        return ""
    matches = _EMOJI_RE.findall(text)
    if matches:
        return matches[-1]  # Lấy emoji cuối cùng
    return ""


def copy_cache_to_assets():
    """Đồng bộ các file emoji quan trọng từ emojis_cache sang assets/emojis."""
    if not EMOJIS_CACHE_DIR.exists():
        return

    ASSETS_EMOJIS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for png in EMOJIS_CACHE_DIR.glob("*.png"):
        dest = ASSETS_EMOJIS_DIR / png.name
        if not dest.exists():
            try:
                dest.write_bytes(png.read_bytes())
                count += 1
            except Exception as e:
                logger.warning(f"Lỗi khi copy emoji {png.name}: {e}")

    if count > 0:
        logger.info(f"Đã đồng bộ {count} HD Color Emoji PNGs từ emojis_cache vào assets/emojis")

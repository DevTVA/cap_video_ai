"""Asset downloader for Fonts and HD Color Emoji PNGs.

Tải toàn bộ bộ Font chữ CapCut và các icon Emoji 3D/Color PNG sắc nét.
"""

import urllib.request
from pathlib import Path
from loguru import logger

ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
EMOJIS_DIR = ASSETS_DIR / "emojis"

# Tải Font TTF từ GitHub Google Fonts
VIRAL_FONTS = {
    "LuckiestGuy-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/apache/luckiestguy/LuckiestGuy-Regular.ttf",
    "Bangers-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf",
    "TitanOne-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/titanone/TitanOne-Regular.ttf",
    "Montserrat-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Fredoka-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf",
    "NotoColorEmoji.ttf": "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/fonts/NotoColorEmoji.ttf",
}

# Tải HD Color Emoji PNG từ Twemoji CDN (Sắc nét 100% màu sắc)
COLOR_EMOJIS = {
    "fight.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4a5.png",      # 💥
    "think.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f914.png",      # 🤔
    "fire.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f525.png",       # 🔥
    "puzzle.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f9e9.png",     # 🧩
    "bolt.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/26a1.png",        # ⚡
    "pin.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4cd.png",         # 📍
    "money.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4b0.png",       # 💰
    "rocket.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f680.png",      # 🚀
    "star.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/2b50.png",        # ⭐
    "happy.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f60a.png",       # 😊
    "laugh.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f602.png",       # 😂
    "heart.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/2764.png",        # ❤️
    "crown.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f451.png",       # 👑
    "idea.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4a1.png",        # 💡
    "target.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f3af.png",      # 🎯
    "time.png": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/23f1.png",        # ⏱️
}


def download_all_assets():
    """Tải toàn bộ Fonts và HD Color Emojis."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    EMOJIS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Kiểm tra và tải tài nguyên Fonts & Color Emojis...")

    for filename, url in VIRAL_FONTS.items():
        dest = FONTS_DIR / filename
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, dest)
                logger.info(f"  ✓ Đã tải Font: {filename}")
            except Exception as e:
                logger.warning(f"  ❌ Lỗi tải Font {filename}: {e}")

    for filename, url in COLOR_EMOJIS.items():
        dest = EMOJIS_DIR / filename
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, dest)
                logger.info(f"  ✓ Đã tải Emoji PNG: {filename}")
            except Exception as e:
                logger.warning(f"  ❌ Lỗi tải Emoji {filename}: {e}")

    logger.info("Hoàn tất kiểm tra tài nguyên!")


if __name__ == "__main__":
    download_all_assets()

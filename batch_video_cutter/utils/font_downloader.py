"""Font & Asset downloader helper.

Tự động tải các Font chữ viral CapCut/Shorts từ Google Fonts CDN vào thư mục assets/fonts/.
"""

import urllib.request
from pathlib import Path
from loguru import logger

ASSETS_FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

# Danh sách URL tải Font chuẩn TTF từ Google Fonts CDN
VIRAL_FONTS = {
    "LuckiestGuy-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/apache/luckiestguy/LuckiestGuy-Regular.ttf",
    "Bangers-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf",
    "TitanOne-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/titanone/TitanOne-Regular.ttf",
    "Montserrat-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Fredoka-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf",
}


def download_viral_fonts() -> list[Path]:
    """Tải bộ Font chữ CapCut Viral Shorts về thư mục assets/fonts/ nếu chưa có."""
    ASSETS_FONTS_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for filename, url in VIRAL_FONTS.items():
        font_path = ASSETS_FONTS_DIR / filename
        if not font_path.exists():
            logger.info(f"Đang tải Font CapCut: {filename}...")
            try:
                urllib.request.urlretrieve(url, font_path)
                logger.info(f"  ✓ Đã tải xong: {font_path}")
                downloaded.append(font_path)
            except Exception as e:
                logger.warning(f"  ❌ Lỗi khi tải font {filename}: {e}")
        else:
            downloaded.append(font_path)

    return downloaded


if __name__ == "__main__":
    download_viral_fonts()

"""Graphic Subtitle Layer Generator using Pillow.

Renders subtitle text with classic CapCut Impact font from first commit,
solid 2-pass 8px black stroke (100% solid fill), soft 3D drop shadow,
3-color active word highlighting (Neon Green/Yellow/Red),
and pastes HD Color 3D PNG Emojis directly to the right of the period on a transparent PNG layer.
Ensures 100% frame-accurate timing and exact pixel positioning.
"""

from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from loguru import logger

from .subtitle import SubtitleLine, extract_emoji_for_phrase, COLOR_MAP
from .emoji_manager import get_emoji_png_path


def _hex_to_rgba(color_str: str) -> Tuple[int, int, int, int]:
    """Chuyển đổi định dạng ASS color hex (&H00BBGGRR&) hoặc #RRGGBB sang Tuple RGBA."""
    if color_str.startswith("&H") and color_str.endswith("&"):
        clean = color_str[2:-1]
        if len(clean) == 8:
            a = 255 - int(clean[0:2], 16)
            b = int(clean[2:4], 16)
            g = int(clean[4:6], 16)
            r = int(clean[6:8], 16)
            return (r, g, b, a)
    elif color_str.startswith("#"):
        clean = color_str[1:]
        if len(clean) == 6:
            r = int(clean[0:2], 16)
            g = int(clean[2:4], 16)
            b = int(clean[4:6], 16)
            return (r, g, b, 255)
    
    return (255, 255, 255, 255)


def _get_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    """Tải chính xác font Impact CapCut cổ điển kinh điển từ first commit (C:/Windows/Fonts/impact.ttf)."""
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    win_impact = Path("C:/Windows/Fonts/impact.ttf")
    clean_target = font_name.replace(" ", "").replace("-", "").replace("_", "").lower()

    # 1. Kiểm tra font Impact trong C:/Windows/Fonts trước tiên (Font CapCut bản first commit)
    if win_impact.exists():
        try:
            return ImageFont.truetype(str(win_impact), font_size)
        except Exception:
            pass

    # 2. Match các font khác nếu có
    primary_paths = [
        fonts_dir / "Montserrat-Bold.ttf",
        fonts_dir / "LuckiestGuy-Regular.ttf",
        fonts_dir / "TitanOne-Regular.ttf",
        fonts_dir / "Fredoka-Bold.ttf",
        fonts_dir / "Bangers-Regular.ttf",
    ]

    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            stem_clean = font_file.stem.replace(" ", "").replace("-", "").replace("_", "").lower()
            if clean_target in stem_clean or stem_clean in clean_target:
                try:
                    return ImageFont.truetype(str(font_file), font_size)
                except Exception:
                    pass

    for p in primary_paths:
        if p and p.exists():
            try:
                return ImageFont.truetype(str(p), font_size)
            except Exception:
                pass

    return ImageFont.load_default()


def generate_graphic_subtitles(
    subtitle_lines: List[SubtitleLine],
    tmp_dir: Path,
    font_name: str = "Impact",
    font_size: int = 85,
    primary_color: str = "&H00FFFFFF",
    highlight_color_name: str = "dynamic",
    margin_v: int = 180,
    emoji_on_top: bool = True,
    canvas_size: Tuple[int, int] = (1080, 1080),
) -> List[Tuple[Path, float, float]]:
    """Tạo danh sách các file ảnh PNG phụ đề đồ họa trong suốt chuẩn font Impact bản first commit (Ruột đặc 100%, Viền đen mập 8px, Soft Drop Shadow, HD Emoji màu)."""
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    font = _get_font(font_name, font_size)
    primary_rgba = (255, 255, 255, 255) # Trắng Tươi cho từ chưa active
    stroke_rgba = (0, 0, 0, 255) # Viền đen mập

    # Gam màu Highlight nổi bật: Xanh lá neon (#00FF00), Vàng tươi (#FFFF00), Đỏ rực (#FF0000)
    dynamic_rgbas = [
        (0, 255, 0, 255),   # Xanh lá neon
        (255, 255, 0, 255), # Vàng tươi
        (255, 0, 0, 255),   # Đỏ rực
    ]
    color_counter = 0
    graphic_results: List[Tuple[Path, float, float]] = []
    frame_count = 0

    for line_idx, line in enumerate(subtitle_lines):
        if not line.words:
            continue

        words_list = line.words
        chunk_size = 4
        chunks = [words_list[i:i + chunk_size] for i in range(0, len(words_list), chunk_size)]

        for chunk_idx, chunk in enumerate(chunks):
            if not chunk:
                continue

            # Xác định Emoji màu 3D
            chunk_emoji = None
            emoji_img = None
            if emoji_on_top:
                chunk_text = " ".join(w[0] for w in chunk)
                chunk_emoji = extract_emoji_for_phrase(chunk_text, fallback_default=False, random_prob=0.5)
                if not chunk_emoji and chunk_idx == 0:
                    chunk_emoji = extract_emoji_for_phrase(line.text, fallback_default=True)

                if chunk_emoji:
                    emoji_png_path = get_emoji_png_path(chunk_emoji)
                    if emoji_png_path and Path(emoji_png_path).exists():
                        try:
                            emoji_img = Image.open(emoji_png_path).convert("RGBA")
                            emoji_img = emoji_img.resize((65, 65), Image.Resampling.LANCZOS)
                        except Exception as e:
                            logger.warning(f"Không thể nạp ảnh emoji {emoji_png_path}: {e}")
                            emoji_img = None

            mid_point = len(chunk) // 2 if len(chunk) >= 3 else len(chunk)
            line1_words = chunk[:mid_point]
            line2_words = chunk[mid_point:]

            # Render từng mốc thoại trong chunk
            for active_idx, active_word_info in enumerate(chunk):
                w_word, w_start, w_end = active_word_info
                if w_start >= w_end:
                    continue

                active_rgba = dynamic_rgbas[color_counter % len(dynamic_rgbas)]
                color_counter += 1

                # 1. Layer bóng đổ Soft Drop Shadow
                shadow_img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow_img)

                # 2. Layer chữ chính
                text_img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
                text_draw = ImageDraw.Draw(text_img)

                l1_text = " ".join(w[0].upper().strip() for w in line1_words) if line1_words else ""
                l2_text = " ".join(w[0].upper().strip() for w in line2_words) if line2_words else ""

                bbox1 = font.getbbox(l1_text) if l1_text else (0, 0, 0, 0)
                l1_width = bbox1[2] - bbox1[0]

                bbox2 = font.getbbox(l2_text) if l2_text else (0, 0, 0, 0)
                l2_width = bbox2[2] - bbox2[0]

                base_y = canvas_size[1] - margin_v - font_size * (2 if l2_text else 1) - 20
                y1 = base_y
                y2 = base_y + font_size + 10

                # --- Render Dòng 1 ---
                if l1_text:
                    x_cursor = (canvas_size[0] - l1_width) // 2
                    for idx, (word_text, _, _) in enumerate(line1_words):
                        clean_w = word_text.upper().strip()
                        color = active_rgba if idx == active_idx else primary_rgba

                        # Soft Drop Shadow
                        shadow_draw.text(
                            (x_cursor + 5, y1 + 5),
                            clean_w,
                            font=font,
                            fill=(0, 0, 0, 200),
                            stroke_width=8,
                            stroke_fill=(0, 0, 0, 200),
                        )
                        # Text chính (Kỹ thuật 2-Pass Stroke: Pass 1 viền đen mập 8px, Pass 2 ruột đặc 100%)
                        text_draw.text(
                            (x_cursor, y1),
                            clean_w,
                            font=font,
                            fill=(0, 0, 0, 255),
                            stroke_width=8,
                            stroke_fill=(0, 0, 0, 255),
                        )
                        text_draw.text(
                            (x_cursor, y1),
                            clean_w,
                            font=font,
                            fill=color,
                            stroke_width=0,
                        )
                        w_box = font.getbbox(clean_w + " ")
                        x_cursor += (w_box[2] - w_box[0])

                # --- Render Dòng 2 ---
                last_line_end_x = (canvas_size[0] + l1_width) // 2 if not l2_text else (canvas_size[0] + l2_width) // 2
                last_line_y = y1 if not l2_text else y2

                if l2_text:
                    x_cursor = (canvas_size[0] - l2_width) // 2
                    for idx, (word_text, _, _) in enumerate(line2_words, start=len(line1_words)):
                        clean_w = word_text.upper().strip()
                        color = active_rgba if idx == active_idx else primary_rgba

                        # Soft Drop Shadow
                        shadow_draw.text(
                            (x_cursor + 5, y2 + 5),
                            clean_w,
                            font=font,
                            fill=(0, 0, 0, 200),
                            stroke_width=8,
                            stroke_fill=(0, 0, 0, 200),
                        )
                        # Text chính (Kỹ thuật 2-Pass Stroke: Pass 1 viền đen mập 8px, Pass 2 ruột đặc 100%)
                        text_draw.text(
                            (x_cursor, y2),
                            clean_w,
                            font=font,
                            fill=(0, 0, 0, 255),
                            stroke_width=8,
                            stroke_fill=(0, 0, 0, 255),
                        )
                        text_draw.text(
                            (x_cursor, y2),
                            clean_w,
                            font=font,
                            fill=color,
                            stroke_width=0,
                        )
                        w_box = font.getbbox(clean_w + " ")
                        x_cursor += (w_box[2] - w_box[0])

                # Dán HD Color Emoji 3D ngay sát dấu chấm `.`
                if emoji_img:
                    emoji_x = min(canvas_size[0] - 70, last_line_end_x + 8)
                    emoji_y = int(last_line_y + 10)
                    text_img.paste(emoji_img, (emoji_x, emoji_y), emoji_img)

                # Làm mờ mịn lớp bóng đổ Soft Drop Shadow
                shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(3))

                # Gộp Lớp Bóng Đổ + Lớp Chữ Chính (Font Impact CapCut bản first commit)
                composite = Image.alpha_composite(shadow_img, text_img)

                # Lưu file PNG
                frame_count += 1
                out_png_path = tmp_dir / f"g_sub_{frame_count:04d}.png"
                composite.save(out_png_path, "PNG")
                graphic_results.append((out_png_path, w_start, w_end))

    logger.info(f"Đã tạo {len(graphic_results)} khung ảnh phụ đề đồ họa Impact CapCut (bản first commit) tại {tmp_dir}")
    return graphic_results

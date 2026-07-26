"""Graphic Subtitle Layer Generator using Pillow.

Renders subtitle text with 3-color active word highlighting, thick black stroke,
and pastes HD Color 3D PNG Emojis directly to the right of the period on a transparent PNG layer.
Ensures 100% frame-accurate timing and exact pixel positioning.
"""

from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from .subtitle import SubtitleLine, extract_emoji_for_phrase, COLOR_MAP
from .emoji_manager import get_emoji_png_path


def _hex_to_rgba(color_str: str) -> Tuple[int, int, int, int]:
    """Chuyển đổi định dạng ASS color hex (&H00BBGGRR&) hoặc #RRGGBB sang Tuple RGBA."""
    if color_str.startswith("&H") and color_str.endswith("&"):
        # Format ASS: &HAABBGGRR& (AA=Alpha)
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
    
    # Mặc định Trắng
    return (255, 255, 255, 255)


def _get_font(font_name: str, font_size: int) -> ImageFont.FreeTypeFont:
    """Tải chính xác font TTF CapCut từ thư mục assets/fonts, Windows Fonts hoặc font mặc định."""
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    clean_target = font_name.replace(" ", "").replace("-", "").replace("_", "").lower()

    # 1. Tìm match trong assets/fonts
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            stem_clean = font_file.stem.replace(" ", "").replace("-", "").replace("_", "").lower()
            if clean_target in stem_clean or stem_clean in clean_target:
                try:
                    return ImageFont.truetype(str(font_file), font_size)
                except Exception as e:
                    logger.warning(f"Không thể đọc file font {font_file}: {e}")

    # 2. Kiểm tra font Impact trong C:/Windows/Fonts (Font CapCut cổ điển kinh điển)
    win_impact = Path("C:/Windows/Fonts/impact.ttf")
    if clean_target in ["impact", "capcut", "montserratblack", "montserratbold"] and win_impact.exists():
        try:
            return ImageFont.truetype(str(win_impact), font_size)
        except Exception:
            pass

    # 3. Danh sách ưu tiên mặc định theo font CapCut viral
    fallback_paths = [
        win_impact,
        fonts_dir / "LuckiestGuy-Regular.ttf",
        fonts_dir / "Montserrat-Bold.ttf",
        fonts_dir / "Fredoka-Bold.ttf",
        fonts_dir / "Bangers-Regular.ttf",
        fonts_dir / "TitanOne-Regular.ttf",
    ]
    for p in fallback_paths:
        if p and p.exists():
            try:
                return ImageFont.truetype(str(p), font_size)
            except Exception:
                pass

    return ImageFont.load_default()


def generate_graphic_subtitles(
    subtitle_lines: List[SubtitleLine],
    tmp_dir: Path,
    font_name: str = "Montserrat Black",
    font_size: int = 85,
    primary_color: str = "&H00FFFFFF",
    highlight_color_name: str = "dynamic",
    margin_v: int = 180,
    emoji_on_top: bool = True,
    canvas_size: Tuple[int, int] = (1080, 1080),
) -> List[Tuple[Path, float, float]]:
    """Tạo danh sách các file ảnh PNG phụ đề đồ họa trong suốt chứa Chữ + Highlight + HD Color Emoji màu."""
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    font = _get_font(font_name, font_size)
    primary_rgba = _hex_to_rgba(primary_color)
    stroke_rgba = (0, 0, 0, 255) # Viền đen mập

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

            # Xác định Emoji màu nếu bật emoji_on_top
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
                            # Load HD Color Emoji 3D và resize 65x65
                            emoji_img = Image.open(emoji_png_path).convert("RGBA")
                            emoji_img = emoji_img.resize((65, 65), Image.Resampling.LANCZOS)
                        except Exception as e:
                            logger.warning(f"Không thể nạp ảnh emoji {emoji_png_path}: {e}")
                            emoji_img = None

            # Chia chunk làm 2 dòng nếu có từ 3 từ trở lên
            mid_point = len(chunk) // 2 if len(chunk) >= 3 else len(chunk)
            line1_words = chunk[:mid_point]
            line2_words = chunk[mid_point:]

            # Render ảnh PNG cho từng từ active trong chunk
            for active_idx, active_word_info in enumerate(chunk):
                w_word, w_start, w_end = active_word_info
                if w_start >= w_end:
                    continue

                # Chọn màu Highlight cho từ active
                active_rgba = dynamic_rgbas[color_counter % len(dynamic_rgbas)]
                color_counter += 1

                # Tạo canvas trong suốt RGBA
                img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                # Đo độ rộng dòng 1 và dòng 2 để căn giữa X=540
                l1_text = " ".join(w[0].upper().strip() for w in line1_words) if line1_words else ""
                l2_text = " ".join(w[0].upper().strip() for w in line2_words) if line2_words else ""

                bbox1 = font.getbbox(l1_text) if l1_text else (0, 0, 0, 0)
                l1_width = bbox1[2] - bbox1[0]

                bbox2 = font.getbbox(l2_text) if l2_text else (0, 0, 0, 0)
                l2_width = bbox2[2] - bbox2[0]

                base_y = canvas_size[1] - margin_v - font_size * (2 if l2_text else 1) - 20
                y1 = base_y
                y2 = base_y + font_size + 10

                # Render Dòng 1
                if l1_text:
                    x_cursor = (canvas_size[0] - l1_width) // 2
                    for idx, (word_text, _, _) in enumerate(line1_words):
                        clean_w = word_text.upper().strip()
                        color = active_rgba if idx == active_idx else primary_rgba
                        
                        # Vẽ viền đen mập
                        draw.text(
                            (x_cursor, y1),
                            clean_w,
                            font=font,
                            fill=color,
                            stroke_width=6,
                            stroke_fill=stroke_rgba,
                        )
                        w_box = font.getbbox(clean_w + " ")
                        x_cursor += (w_box[2] - w_box[0])

                # Render Dòng 2
                last_line_end_x = (canvas_size[0] + l1_width) // 2 if not l2_text else (canvas_size[0] + l2_width) // 2
                last_line_y = y1 if not l2_text else y2

                if l2_text:
                    x_cursor = (canvas_size[0] - l2_width) // 2
                    for idx, (word_text, _, _) in enumerate(line2_words, start=len(line1_words)):
                        clean_w = word_text.upper().strip()
                        color = active_rgba if idx == active_idx else primary_rgba
                        
                        draw.text(
                            (x_cursor, y2),
                            clean_w,
                            font=font,
                            fill=color,
                            stroke_width=6,
                            stroke_fill=stroke_rgba,
                        )
                        w_box = font.getbbox(clean_w + " ")
                        x_cursor += (w_box[2] - w_box[0])

                # Dán HD Color Emoji 3D trực tiếp ngay sát bên phải dấu chấm `.` trên cùng bức ảnh
                if emoji_img:
                    emoji_x = min(canvas_size[0] - 70, last_line_end_x + 8)
                    emoji_y = int(last_line_y + 10)
                    img.paste(emoji_img, (emoji_x, emoji_y), emoji_img)

                # Lưu file PNG
                frame_count += 1
                out_png_path = tmp_dir / f"g_sub_{frame_count:04d}.png"
                img.save(out_png_path, "PNG")
                graphic_results.append((out_png_path, w_start, w_end))

    logger.info(f"Đã tạo {len(graphic_results)} khung ảnh phụ đề đồ họa trong suốt tại {tmp_dir}")
    return graphic_results

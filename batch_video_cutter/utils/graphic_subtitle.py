"""Graphic Subtitle Layer Generator using Pillow.

Renders subtitle text with classic CapCut Impact font from first commit,
solid 2-pass 8px black stroke (100% solid fill), soft 3D drop shadow,
3-color active word highlighting (Neon Green/Yellow/Red),
and pastes HD Color 3D PNG Emojis directly to the right of the period on a transparent PNG layer.
Ensures 100% frame-accurate timing and exact pixel positioning.
"""

import re
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
    position: str = "bottom",
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
        words_list = line.words
        if not words_list and line.text.strip():
            raw_words = line.text.strip().split()
            if raw_words and line.end > line.start:
                dur = (line.end - line.start) / len(raw_words)
                words_list = [
                    (w, line.start + i * dur, line.start + (i + 1) * dur)
                    for i, w in enumerate(raw_words)
                ]

        if not words_list:
            continue
        # Tính nhịp nói trung bình của phân đoạn (giây/từ)
        line_duration = line.end - line.start
        avg_word_dur = line_duration / max(1, len(words_list)) if line_duration > 0 else 0.3

        # Nếu nhân vật nói nhanh (<0.28s/từ): gộp 2-3 từ/chunk; nếu nói bình thường: 3-4 từ/chunk
        chunk_size = 3 if avg_word_dur < 0.28 else 4
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

            # Đo độ rộng cả chunk để quyết định hiển thị 1 DÒNG ĐƠN hay 2 dòng
            chunk_full_text = " ".join(w[0].upper().strip() for w in chunk)
            chunk_bbox = font.getbbox(chunk_full_text)
            chunk_w = chunk_bbox[2] - chunk_bbox[0]

            # Ưu tiên 1 DÒNG ĐƠN nếu tổng độ rộng <= 750px hoặc <= 3 từ (tránh nhấp nháy 2 dòng khi nói nhanh)
            if chunk_w <= 750 or len(chunk) <= 3:
                line1_words = chunk
                line2_words = []
            else:
                mid_point = len(chunk) // 2
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

                eff_margin_v = 160 if canvas_size[1] > 1080 else margin_v
                if position == "top":
                    base_y = 45  # Đặt vừa vặn trong dải caption phía trên
                else:
                    base_y = canvas_size[1] - eff_margin_v - font_size * (2 if l2_text else 1) - 20

                y1 = base_y
                y2 = base_y + font_size + 10

                # --- Render Dòng 1 ---
                if l1_text:
                    x_cursor = (canvas_size[0] - l1_width) // 2
                    for idx, (word_text, _, _) in enumerate(line1_words):
                        clean_w = re.sub(r'>>+|[<>\[\]()]', '', word_text).upper().strip()
                        if not clean_w:
                            continue
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
                        clean_w = re.sub(r'>>+|[<>\[\]()]', '', word_text).upper().strip()
                        if not clean_w:
                            continue
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

    # Khử đè thời gian giữa các khung phụ đề (Timing overlap sanitization 100% chống đè chữ)
    if graphic_results:
        graphic_results.sort(key=lambda x: x[1])
        sanitized = []
        for i in range(len(graphic_results)):
            p, s, e = graphic_results[i]
            if i < len(graphic_results) - 1:
                next_s = graphic_results[i + 1][1]
                e = min(e, next_s - 0.02)
            if e > s + 0.01:
                sanitized.append((p, s, e))
        graphic_results = sanitized

    logger.info(f"Đã tạo {len(graphic_results)} khung ảnh phụ đề đồ họa Impact CapCut (bản first commit) tại {tmp_dir}")
    return graphic_results


def clean_caption_text(text: str) -> str:
    """Làm sạch ký tự unicode lạ, emoji, nháy cong để không bao giờ bị ô vuông."""
    if not text:
        return ""
    text = text.replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"').replace("—", "-")
    pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"
        "\u2600-\u27BF"
        "\u2300-\u23FF"
        "\u2B00-\u2BFF"
        "\u2000-\u206F"
        "\uFE00-\uFE0F"
        "]+",
        flags=re.UNICODE,
    )
    clean = pattern.sub("", text)
    clean = re.sub(r"\s+", " ", clean).strip().upper()
    return clean


def generate_top_caption_layer(
    title_text: str,
    output_png: Path,
    canvas_size: Tuple[int, int] = (1080, 1440),
    top_area_height: int = 280,
) -> Optional[Path]:
    """Tạo file PNG chứa Top Caption dạng Badge Nền Trắng Bo Góc + Chữ Đen Viết Hoa giống 100% mẫu ảnh."""
    if not title_text:
        return None
    clean_t = clean_caption_text(title_text)
    words = clean_t.split()
    if len(words) > 9:
        clean_t = " ".join(words[:9])

    import textwrap
    lines = textwrap.wrap(clean_t, width=24)[:3]
    if not lines:
        return None

    font_path = "C:/Windows/Fonts/arialbd.ttf"
    font_size = 44
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    line_boxes = []
    max_line_w = 0
    total_text_h = 0
    for line in lines:
        bbox = font.getbbox(line)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_boxes.append((line, w, h))
        max_line_w = max(max_line_w, w)
        total_text_h += h + 12

    total_text_h -= 12

    pad_h = 16
    pad_w = 32
    badge_w = max_line_w + pad_w * 2
    badge_h = total_text_h + pad_h * 2

    # Căn giữa dọc 100% trong dải 280px nền đen phía trên (giống 100% Ảnh 3 mẫu)
    badge_x1 = (canvas_size[0] - badge_w) // 2
    badge_y1 = max(10, (top_area_height - badge_h) // 2)
    badge_x2 = badge_x1 + badge_w
    badge_y2 = badge_y1 + badge_h

    # Vẽ 1 BADGE NỀN TRẮNG BO GÓC DUY NHẤT BAO BỌC TOÀN BỘ CÁC DÒNG CHỮ (Giống 100% Ảnh 3)
    draw.rounded_rectangle([badge_x1, badge_y1, badge_x2, badge_y2], radius=16, fill=(255, 255, 255, 255))

    # Vẽ các dòng Chữ Đen Viết Hoa ở giữa Badge
    curr_y = badge_y1 + pad_h
    for line, w, h in line_boxes:
        text_x = (canvas_size[0] - w) // 2
        draw.text((text_x, curr_y), line, font=font, fill=(0, 0, 0, 255))
        curr_y += h + 12

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png, "PNG")
    logger.info(f"Đã tạo PNG Top Caption Badge Nền Trắng Chữ Đen: {output_png}")
    return output_png

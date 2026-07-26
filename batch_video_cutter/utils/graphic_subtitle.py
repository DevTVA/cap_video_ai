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
        # Thuật toán ngắt nhịp thoại chuẩn theo nhịp thở, khoảng nghỉ và dấu câu thực tế của nhân vật:
        chunks = []
        curr_chunk = []
        for i, word_info in enumerate(words_list):
            w_text, w_start, w_end = word_info
            curr_chunk.append(word_info)

            # 1. Dấu hiệu ngắt nhịp thoại theo dấu câu (., !, ?, ,, ;, :)
            clean_w = re.sub(r'>>+|[<>\[\]()]', '', w_text).strip()
            has_punctuation = bool(re.search(r'[.,!?;:]$', clean_w))

            # 2. Khoảng ngắt nghỉ tự nhiên giữa 2 từ thoại > 0.22 giây
            has_pause = False
            if i < len(words_list) - 1:
                next_start = words_list[i + 1][1]
                if next_start - w_end > 0.22:
                    has_pause = True

            # 3. Đạt số từ tối đa trong 1 cụm (3-4 từ)
            reached_max_words = len(curr_chunk) >= 4

            if has_punctuation or has_pause or reached_max_words or i == len(words_list) - 1:
                chunks.append(curr_chunk)
                curr_chunk = []

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

            # Render từng mốc thoại trong chunk theo nhịp nói thực tế
            for active_idx, active_word_info in enumerate(chunk):
                w_word, w_start, w_end = active_word_info
                if w_start >= w_end:
                    continue

                # Mốc thời lượng hiển thị khớp từ w_start đến từ kế tiếp (hoặc cuối chunk)
                if active_idx < len(chunk) - 1:
                    frame_end = max(w_end, chunk[active_idx + 1][1] - 0.01)
                else:
                    frame_end = max(w_end, chunk[-1][2])

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
                graphic_results.append((out_png_path, w_start, frame_end))

    # Khử đè thời gian & Gộp các khung chớp nháy quá ngắn khi nhân vật nói nhanh (Chống chớp nháy 100%)
    if graphic_results:
        graphic_results.sort(key=lambda x: x[1])
        merged = []
        for p, s, e in graphic_results:
            # Nếu thời lượng quá ngắn (< 0.35s) và có khung trước đó gần kề:
            if merged and (s - merged[-1][2] < 0.05) and (merged[-1][2] - merged[-1][1] < 0.35):
                # Nối dài thời lượng khung trước đó lên
                prev_p, prev_s, prev_e = merged[-1]
                merged[-1] = (prev_p, prev_s, max(e, prev_s + 0.35))
            else:
                display_end = max(e, s + 0.35)
                merged.append((p, s, display_end))

        # Đảm bảo khung sau đè hợp lý không trùng khớp
        sanitized = []
        for i in range(len(merged)):
            p, s, e = merged[i]
            if i < len(merged) - 1:
                next_s = merged[i + 1][1]
                e = min(e, next_s - 0.02)
            if e > s + 0.02:
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


def ensure_caption_8_to_12_words(title_text: str, fallback_text: str = "") -> list:
    """Vòng lặp đảm bảo 100% Top Caption luôn có từ 8 đến 12 từ."""
    clean_t = clean_caption_text(title_text).replace('"', '').strip()
    words = clean_t.split()

    # Vòng lặp 1: Bổ sung từ từ fallback_text nếu ít hơn 8 từ
    if len(words) < 8 and fallback_text:
        fallback_clean = clean_caption_text(fallback_text)
        extra_words = fallback_clean.split()
        for w in extra_words:
            if w not in words:
                words.append(w)
            if len(words) >= 8:
                break

    # Vòng lặp 2: Nếu vẫn ít hơn 8 từ, bổ sung viral filler words
    viral_fillers = ["MUST", "WATCH", "SHOCKING", "REVEAL", "STORY", "FULL", "UNBELIEVABLE"]
    fill_idx = 0
    while len(words) < 8:
        words.append(viral_fillers[fill_idx % len(viral_fillers)])
        fill_idx += 1

    # Cắt nếu quá 12 từ
    if len(words) > 12:
        words = words[:12]

    return words


def generate_top_caption_layer(
    title_text: str,
    output_png: Path,
    canvas_size: Tuple[int, int] = (1080, 1440),
    top_area_height: int = 280,
    fallback_text: str = "",
) -> Optional[Path]:
    """Tạo file PNG chứa Top Caption Chữ ĐEN Bo Viền TRẮNG Nền ĐEN cho Canvas 3:4 và Nền Vàng cho Canvas 1:1."""
    if not title_text:
        return None
    
    # 1. Chạy vòng lặp đảm bảo 100% số từ từ 8 đến 12 từ
    words = ensure_caption_8_to_12_words(title_text, fallback_text)
    clean_t = " ".join(words)

    font_path = "C:/Windows/Fonts/arialbd.ttf"
    font_size = 44
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    import textwrap
    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Nếu là Canvas 1:1 (1080x1080): Render Dải Nền Vàng + Chữ Đen Ngoặc Kép (Phong cách 3)
    if canvas_size[0] == 1080 and canvas_size[1] == 1080:
        formatted = f'"{clean_t}"'
        lines = textwrap.wrap(formatted, width=28)[:2]
        draw.rectangle([0, 0, canvas_size[0], top_area_height], fill=(255, 255, 0, 255))

        line_boxes = []
        total_text_h = 0
        for line in lines:
            bbox = font.getbbox(line)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_boxes.append((line, w, h))
            total_text_h += h + 8
        total_text_h -= 8

        start_y = max(10, (top_area_height - total_text_h) // 2)
        curr_y = start_y
        for line, w, h in line_boxes:
            text_x = (canvas_size[0] - w) // 2
            draw.text((text_x, curr_y), line, font=font, fill=(0, 0, 0, 255))
            curr_y += h + 8
        logger.info(f"Đã tạo PNG Top Caption Dải Nền Vàng (Style 3): {output_png}")

    # 2. Nếu là Canvas 3:4 (1080x1440): Render SINGLE WHITE BADGE BO GÓC GIÃN ĐẾN LỀ 40PX TRƯỚC KHU XUỐNG DÒNG MỚI (Style 4)
    else:
        font_size = 40
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        # Max text width per line = Canvas 1080 - Margin 80 (40px 2 bên) - Pad 64 (32px 2 bên) = 936px
        max_text_w = canvas_size[0] - 80 - 64

        # Ngắt dòng theo pixel width thực tế của Font (giãn tối đa sát lề 40px mới chịu xuống dòng mới)
        lines = []
        curr_words = []
        for w in words:
            test_words = curr_words + [w]
            test_str = " ".join(test_words)
            if len(lines) == 0:
                test_str = f'"{test_str}"'
            
            bbox = font.getbbox(test_str)
            w_px = bbox[2] - bbox[0]
            
            if w_px <= max_text_w:
                curr_words.append(w)
            else:
                if curr_words:
                    line_text = " ".join(curr_words)
                    if len(lines) == 0:
                        line_text = f'"{line_text}"'
                    lines.append(line_text)
                    curr_words = [w]
                else:
                    lines.append(w)
                    curr_words = []
            if len(lines) >= 3:
                break
                
        if curr_words and len(lines) < 3:
            line_text = " ".join(curr_words)
            if len(lines) == 0:
                line_text = f'"{line_text}"'
            lines.append(line_text)

        line_boxes = []
        max_line_w = 0
        total_text_h = 0
        for line in lines:
            bbox = font.getbbox(line)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_boxes.append((line, w, h))
            max_line_w = max(max_line_w, w)
            total_text_h += h + 10
        total_text_h -= 10

        pad_h = 16
        pad_w = 32
        badge_w = max_line_w + pad_w * 2
        badge_h = total_text_h + pad_h * 2

        # Lề thụt trái & thụt phải tối thiểu 40px mỗi bên
        badge_x1 = (canvas_size[0] - badge_w) // 2
        badge_y1 = max(15, (top_area_height - badge_h) // 2)
        badge_x2 = badge_x1 + badge_w
        badge_y2 = badge_y1 + badge_h

        # Vẽ Single White Rounded Rectangle Badge (radius=18)
        draw.rounded_rectangle([badge_x1, badge_y1, badge_x2, badge_y2], radius=18, fill=(255, 255, 255, 255))

        curr_y = badge_y1 + pad_h
        for line, w, h in line_boxes:
            text_x = (canvas_size[0] - w) // 2
            draw.text((text_x, curr_y), line, font=font, fill=(0, 0, 0, 255))
            curr_y += h + 10
        logger.info(f"Đã tạo PNG Top Caption Single White Badge Pixel Wrap (Style 4): {output_png}")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png, "PNG")
    return output_png

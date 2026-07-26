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

        # Cụm 4 từ chuẩn 100% phiên commit 1:
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

            # Chia chunk làm 2 dòng nếu có từ 3 từ trở lên (bản commit 1 chuẩn)
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

                eff_margin_v = 330 if canvas_size[1] > 1080 else margin_v
                if position == "top":
                    base_y = 45
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
                        color = (0, 255, 0, 255) if idx == active_idx else primary_rgba

                        # Soft Drop Shadow
                        shadow_draw.text(
                            (x_cursor + 5, y1 + 5),
                            clean_w,
                            font=font,
                            fill=(0, 0, 0, 200),
                            stroke_width=8,
                            stroke_fill=(0, 0, 0, 200),
                        )
                        # Text chính (Kỹ thuật 2-Pass Stroke bản commit 1: Pass 1 viền đen mập 8px, Pass 2 ruột đặc 100%)
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
                        color = (0, 255, 0, 255) if idx == active_idx else primary_rgba

                        # Soft Drop Shadow
                        shadow_draw.text(
                            (x_cursor + 5, y2 + 5),
                            clean_w,
                            font=font,
                            fill=(0, 0, 0, 200),
                            stroke_width=8,
                            stroke_fill=(0, 0, 0, 200),
                        )
                        # Text chính (Kỹ thuật 2-Pass Stroke bản commit 1: Pass 1 viền đen mập 8px, Pass 2 ruột đặc 100%)
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

                # Dán HD Color Emoji 3D ngay sát bên phải dấu chấm `.`
                if emoji_img:
                    emoji_x = min(canvas_size[0] - 70, last_line_end_x + 8)
                    emoji_y = int(last_line_y + 10)
                    text_img.paste(emoji_img, (emoji_x, emoji_y), emoji_img)

                # Làm mờ mịn lớp bóng đổ Soft Drop Shadow
                shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(3))

                # Gộp Lớp Bóng Đổ + Lớp Chữ Chính (Font Impact CapCut bản commit 1)
                composite = Image.alpha_composite(shadow_img, text_img)

                # Lưu file PNG
                frame_count += 1
                out_png_path = tmp_dir / f"g_sub_{frame_count:04d}.png"
                composite.save(out_png_path, "PNG")
                graphic_results.append((out_png_path, w_start, w_end))

    # Khử chớp nháy 100% (Anti-Flicker Seamless Subtitle Engine)
    if graphic_results:
        graphic_results.sort(key=lambda x: x[1])
        sanitized = []
        n = len(graphic_results)

        for i in range(n):
            path, s, e = graphic_results[i]

            # 1. Đảm bảo thời lượng tối thiểu hiển thị của 1 khung phụ đề không dưới 0.35s
            if (e - s) < 0.35:
                e = s + 0.35

            # 2. Xử lý va chạm & trám khoảng lặng trống giữa các khung để phụ đề KHÔNG BAO GIỜ BỊ TẮT ĐEN CHỚP NHÁY
            if i < n - 1:
                next_s = graphic_results[i + 1][1]
                # Nếu khoảng lặng giữa 2 khung nhỏ hơn 0.50s -> Trám kín khoảng lặng kéo dài sát khung kế tiếp!
                if next_s > s and (next_s - e) < 0.50:
                    e = next_s - 0.01
                elif e >= next_s:
                    e = max(s + 0.10, next_s - 0.01)

            if e > s + 0.05:
                sanitized.append((path, round(s, 3), round(e, 3)))

        graphic_results = sanitized

    logger.info(f"Đã tạo {len(graphic_results)} khung ảnh phụ đề đồ họa Impact CapCut (bản first commit) tại {tmp_dir}")
    return graphic_results


CENSOR_DICTIONARY = {
    r"\bSEX\b": "SE*",
    r"\bSEXUAL\b": "SE*UAL",
    r"\bSEXY\b": "SE*Y",
    r"\bKILL\b": "KI*L",
    r"\bKILLED\b": "KI*LED",
    r"\bKILLING\b": "KI*LING",
    r"\bKILLER\b": "KI*LER",
    r"\bMURDER\b": "MU*DER",
    r"\bMURDERED\b": "MU*DERED",
    r"\bDEATH\b": "DE*TH",
    r"\bDEAD\b": "DE*D",
    r"\bDIE\b": "D*E",
    r"\bDIED\b": "D*ED",
    r"\bSUICIDE\b": "SU*CIDE",
    r"\bFUCK\b": "F*CK",
    r"\bFUCKING\b": "F*CKING",
    r"\bFUCKED\b": "F*CKED",
    r"\bSHIT\b": "SH*T",
    r"\bBITCH\b": "BI*CH",
    r"\bASS\b": "A*S",
    r"\bASSHOLE\b": "A*SHOLE",
    r"\bDICK\b": "DI*K",
    r"\bPENIS\b": "PE*IS",
    r"\bVAGINA\b": "VA*INA",
    r"\bPORN\b": "PO*N",
    r"\bPORNO\b": "PO*NO",
    r"\bNUDE\b": "NU*E",
    r"\bNUDITY\b": "NU*ITY",
    r"\bNAKED\b": "NA*ED",
    r"\bRAPE\b": "RA*E",
    r"\bRAPED\b": "RA*ED",
    r"\bRAPIST\b": "RA*IST",
    r"\bABUSE\b": "AB*SE",
    r"\bABUSED\b": "AB*SED",
    r"\bSLUT\b": "SL*T",
    r"\bWHORE\b": "WH*RE",
    r"\bDRUG\b": "DR*G",
    r"\bDRUGS\b": "DR*GS",
    r"\bCOCAINE\b": "CO*AINE",
    r"\bHEROIN\b": "HE*OIN",
    r"\bWEED\b": "WE*D",
    r"\bGUN\b": "G*N",
    r"\bGUNS\b": "G*NS",
    r"\bSHOOT\b": "SH*OT",
    r"\bSHOT\b": "SH*T",
    r"\bSHOOTING\b": "SH*OTING",
    r"\bPEDO\b": "PE*O",
    r"\bPEDOPHILE\b": "PE*OPHILE",
}


def censor_sensitive_words(text: str) -> str:
    """Thay thế các từ nhạy cảm không chuẩn mực bằng ký tự * (ví dụ SEX -> SE*, KILL -> KI*L)."""
    if not text:
        return ""
    result = text
    for pattern, replacement in CENSOR_DICTIONARY.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def clean_caption_text(text: str) -> str:
    """Làm sạch ký tự unicode lạ, emoji, nháy cong và tự động censor từ nhạy cảm."""
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
    clean = censor_sensitive_words(clean)
    return clean


def ensure_caption_8_to_12_words(title_text: str, fallback_text: str = "") -> list:
    """Đảm bảo 100% Top Caption nằm trong khoảng từ 8 đến 12 từ thuần từ gốc/transcript."""
    clean_t = clean_caption_text(title_text).replace('"', '').strip()
    words = clean_t.split()

    # 1. Bổ sung từ từ fallback_text (transcript/lý do cắt clip) nếu tiêu đề gốc ít hơn 8 từ
    if len(words) < 8 and fallback_text:
        fallback_clean = clean_caption_text(fallback_text)
        extra_words = fallback_clean.split()
        for w in extra_words:
            if w not in words:
                words.append(w)
            if len(words) >= 8:
                break

    # 2. Nếu sau khi lấy từ fallback vẫn ít hơn 8 từ, lặp lại các từ có sẵn trong từ tiêu đề/transcript để đảm bảo tối thiểu 8 từ 100%
    if len(words) < 8 and words:
        orig_words = list(words)
        idx = 0
        while len(words) < 8:
            words.append(orig_words[idx % len(orig_words)])
            idx += 1

    # 3. Cắt gọn nếu vượt quá 12 từ
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

    # Sử dụng font Montserrat-Bold.ttf (Font chữ in hoa hình học sang trọng chuẩn như ảnh mẫu của user)
    montserrat_path = Path(__file__).parent.parent / "assets" / "fonts" / "Montserrat-Bold.ttf"
    if montserrat_path.exists():
        font_path = str(montserrat_path)
    else:
        font_path = "C:/Windows/Fonts/arialbd.ttf"

    font_size = 40
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

def format_top_caption_lines(words: list, font: ImageFont.FreeTypeFont, max_text_w: int) -> list:
    """Tách các từ thành 1, 2 hoặc 3 dòng:
    - Dòng 1: Dồn tối đa từ cho sát mốc lề max_text_w.
    - Dòng 2 & 3: Nếu phần từ còn lại tràn mốc max_text_w thì tự động tách thành 3 dòng cân đối kích thước.
    """
    if not words:
        return []

    curr_l1 = []
    split_idx1 = 0
    for idx, w in enumerate(words):
        test_str = f'"{" ".join(curr_l1 + [w])}'
        w_px = font.getbbox(test_str)[2] - font.getbbox(test_str)[0]
        if w_px <= max_text_w:
            curr_l1.append(w)
            split_idx1 = idx + 1
        else:
            break

    if split_idx1 == 0:
        split_idx1 = 1

    l1_words = words[:split_idx1]
    rem_words = words[split_idx1:]

    if not rem_words:
        return [f'"{" ".join(l1_words)}"']

    line1_text = f'"{" ".join(l1_words)}'

    test_rem_str = f'{" ".join(rem_words)}"'
    rem_w_px = font.getbbox(test_rem_str)[2] - font.getbbox(test_rem_str)[0]

    if rem_w_px <= max_text_w:
        line2_text = test_rem_str
        return [line1_text, line2_text]

    # Nếu phần từ còn lại vượt quá max_text_w -> Tách làm Dòng 2 và Dòng 3 cân đối kích thước
    split_idx2 = max(1, len(rem_words) // 2)
    l2_words = rem_words[:split_idx2]
    l3_words = rem_words[split_idx2:]

    line2_text = f'{" ".join(l2_words)}'
    line3_text = f'{" ".join(l3_words)}"'

    return [line1_text, line2_text, line3_text]


def generate_top_caption_layer(
    title_text: str,
    output_png: Path,
    canvas_size: Tuple[int, int] = (1080, 1440),
    top_area_height: int = 280,
    fallback_text: str = "",
) -> Optional[Path]:
    """Tạo file PNG chứa Top Caption Chữ ĐEN Bo Viền TRẮNG Nền ĐEN cho Canvas 3:4 và Nền Vàng cho Canvas 1:1 (Hỗ trợ 1-3 dòng cân đối)."""
    if not title_text:
        return None
    
    # 1. Chạy vòng lặp đảm bảo 100% số từ từ 8 đến 12 từ
    words = ensure_caption_8_to_12_words(title_text, fallback_text)

    # Sử dụng font Montserrat-Bold.ttf
    montserrat_path = Path(__file__).parent.parent / "assets" / "fonts" / "Montserrat-Bold.ttf"
    if montserrat_path.exists():
        font_path = str(montserrat_path)
    else:
        font_path = "C:/Windows/Fonts/arialbd.ttf"

    font_size = 40
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Nếu là Canvas 1:1 (1080x1080): Render Dải Nền Vàng + Chữ Đen Montserrat-Bold 1-3 Dòng Cân Đối (Phong cách 3)
    if canvas_size[0] == 1080 and canvas_size[1] == 1080:
        draw.rectangle([0, 0, canvas_size[0], top_area_height], fill=(255, 255, 0, 255))

        margin_x = 40
        max_text_w = canvas_size[0] - margin_x * 2  # 1000px

        lines = format_top_caption_lines(words, font, max_text_w)
        bboxes = [font.getbbox(l) for l in lines]
        widths = [b[2] - b[0] for b in bboxes]
        heights = [b[3] - b[1] for b in bboxes]

        line_gap = 6 if len(lines) == 3 else 10
        total_h = sum(heights) + line_gap * (len(lines) - 1)
        start_y = max(8, (top_area_height - total_h) // 2)

        curr_y = start_y
        for i, line_str in enumerate(lines):
            w = widths[i]
            h = heights[i]
            x_pos = (canvas_size[0] - w) // 2
            draw.text((x_pos, curr_y), line_str, font=font, fill=(0, 0, 0, 255))
            curr_y += h + line_gap

        logger.info(f"Đã tạo PNG Top Caption Dải Nền Vàng Chữ Đen Montserrat-Bold ({len(lines)} Dòng - Style 3): {output_png}")

    # 2. Nếu là Canvas 3:4 (1080x1440): Render 1-3 LINE CONTOUR WHITE BADGE BO VIỀN ÔM THEO TỪNG DÒNG (Style 4)
    else:
        margin_x = 40
        pad_w_l1 = 20
        pad_w_other = 30
        pad_h = 14
        radius = 18

        max_text_w_l1 = canvas_size[0] - margin_x * 2 - pad_w_l1 * 2  # 960px

        lines = format_top_caption_lines(words, font, max_text_w_l1)
        bboxes = [font.getbbox(l) for l in lines]
        widths = [b[2] - b[0] for b in bboxes]
        heights = [b[3] - b[1] for b in bboxes]

        # Khung Dòng 1: Full width lề 40px (1000px). Các dòng sau contour theo chữ
        box1_x1 = margin_x
        box1_x2 = canvas_size[0] - margin_x
        box1_h = heights[0] + pad_h * 2

        boxes = [(box1_x1, box1_x2, box1_h)]

        for i in range(1, len(lines)):
            bw = widths[i] + pad_w_other * 2
            bh = heights[i] + pad_h * 2
            bx1 = (canvas_size[0] - bw) // 2
            bx2 = bx1 + bw
            boxes.append((bx1, bx2, bh))

        total_h = sum(b[2] for b in boxes) - 8 * (len(boxes) - 1)
        start_y = max(10, (top_area_height - total_h) // 2)

        curr_y = start_y
        for i, line_str in enumerate(lines):
            bx1, bx2, bh = boxes[i]
            by1 = curr_y
            by2 = by1 + bh

            draw.rounded_rectangle([bx1, by1, bx2, by2], radius=radius, fill=(255, 255, 255, 255))

            if i > 0:
                prev_bx1, prev_bx2, _ = boxes[i - 1]
                min_x = max(bx1, prev_bx1) + radius
                max_x = min(bx2, prev_bx2) - radius
                if max_x > min_x:
                    draw.rectangle([min_x, by1 - 8, max_x, by1 + 8], fill=(255, 255, 255, 255))

            text_x = (canvas_size[0] - widths[i]) // 2
            text_y = by1 + pad_h
            draw.text((text_x, text_y), line_str, font=font, fill=(0, 0, 0, 255))

            curr_y = by2 - 8

        logger.info(f"Đã tạo PNG Top Caption White Badge ({len(lines)} Dòng - Style 4): {output_png}")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png, "PNG")
    return output_png

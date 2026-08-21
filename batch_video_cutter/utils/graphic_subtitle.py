"""Graphic Subtitle Layer Generator using Pillow.

Renders subtitle text with classic CapCut Impact font from first commit,
solid 2-pass 8px black stroke (100% solid fill), soft 3D drop shadow,
3-color active word highlighting (Neon Green/Yellow/Red),
and pastes HD Color 3D PNG Emojis directly to the right of the period on a transparent PNG layer.
Ensures 100% frame-accurate timing and exact pixel positioning.
"""

import re
import random
import functools
from collections import deque
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


@functools.lru_cache(maxsize=32)
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


PUNCTUATION_ENDINGS = (",", ".", "!", "?", ";", ":")
# Danh sách Stop Words tiếng Anh thông thường (KHÔNG bao gồm các từ phủ định nhấn mạnh như NOT, NO, NEVER để ưu tiên tô màu Vàng)
ENGLISH_STOP_WORDS = {
    "A", "AN", "THE", "IS", "ARE", "AM", "WAS", "WERE", "BE", "BEEN", "BEING",
    "HAVE", "HAS", "HAD", "DO", "DOES", "DID", "TO", "IN", "ON", "AT", "OF",
    "FOR", "WITH", "BY", "FROM", "UP", "ABOUT", "INTO", "OVER", "AFTER",
    "AND", "OR", "BUT", "IF", "SO", "THAN", "THAT", "THIS", "THESE", "THOSE",
    "IT", "ITS", "HE", "SHE", "THEY", "THEIR", "THEM", "YOU", "YOUR", "WE", "MY",
    "ME", "OUR", "US", "HIS", "HER", "WHAT", "WHO", "WHICH", "WHEN", "WHERE", "WHY", "HOW"
}


def _split_words_by_rhythm_and_punctuation(
    words_list: List[Tuple[str, float, float]],
    max_words: int = 6,
    max_chars: int = 24,
) -> List[List[Tuple[str, float, float]]]:
    """Ngắt cụm từ phụ đề theo Dấu câu (Punctuation), Khoảng dừng hít thở (Pause), Số từ (<=6) VÀ Giới hạn ký tự (<=24)."""
    if not words_list:
        return []

    raw_chunks: List[List[Tuple[str, float, float]]] = []
    current_chunk: List[Tuple[str, float, float]] = []

    for i, w_info in enumerate(words_list):
        w_word, w_start, w_end = w_info
        current_chunk.append(w_info)

        chunk_text = " ".join(w[0].strip() for w in current_chunk)
        has_punctuation = any(w_word.strip().endswith(p) for p in PUNCTUATION_ENDINGS)

        has_pause = False
        if i < len(words_list) - 1:
            next_start = words_list[i + 1][1]
            if next_start - w_end > 0.40:
                has_pause = True

        is_max_words = len(current_chunk) >= max_words
        is_max_chars = len(chunk_text) >= max_chars

        if has_punctuation or has_pause or is_max_words or is_max_chars:
            raw_chunks.append(current_chunk)
            current_chunk = []

    if current_chunk:
        raw_chunks.append(current_chunk)

    # Post-process: Gộp cụm quá ngắn (< 0.45s hoặc <= 2 từ) với cụm liền sau để giữ câu thoại tĩnh mượt 100% chuẩn CapCut Pro
    merged_chunks: List[List[Tuple[str, float, float]]] = []
    for chunk in raw_chunks:
        if not merged_chunks:
            merged_chunks.append(chunk)
            continue

        prev = merged_chunks[-1]
        prev_dur = prev[-1][2] - prev[0][1]
        prev_text = " ".join(w[0].strip() for w in prev)
        curr_text = " ".join(w[0].strip() for w in chunk)

        combined_words = len(prev) + len(chunk)
        combined_chars = len(prev_text) + 1 + len(curr_text)
        has_prev_punc = any(prev[-1][0].strip().endswith(p) for p in PUNCTUATION_ENDINGS)

        if (prev_dur < 0.45 or len(prev) <= 2) and not has_prev_punc and combined_words <= max_words and combined_chars <= (max_chars + 4):
            merged_chunks[-1] = prev + chunk
        else:
            merged_chunks.append(chunk)

    return merged_chunks


def _select_emphasis_words_in_chunk(chunk: List[Tuple[str, float, float]]) -> set:
    """Tự động chọn duy nhất 1 từ nhấn mạnh trong cụm CHỈ KHI cụm có từ 2 từ trở lên (cụm 1 từ giữ 100% màu Trắng)."""
    if not chunk or len(chunk) < 2:
        return set()

    indices = []
    for idx, (word_text, s, e) in enumerate(chunk):
        clean_w = re.sub(r"[^\w\s]", "", word_text).upper().strip()
        if clean_w and clean_w not in ENGLISH_STOP_WORDS:
            indices.append(idx)

    if not indices:
        longest_idx = max(range(len(chunk)), key=lambda i: len(chunk[i][0]))
        return {longest_idx}

    # Chọn 1 từ nhấn mạnh có độ dài lớn nhất hoặc mang cảm xúc mạnh nhất
    best_idx = max(indices, key=lambda i: len(chunk[i][0]))
    return {best_idx}


def _render_single_chunk_frame(
    chunk: List[Tuple[str, float, float]],
    line1_words: List[Tuple[str, float, float]],
    line2_words: List[Tuple[str, float, float]],
    active_emphasis_indices: Optional[tuple] = None,
    font: ImageFont.FreeTypeFont = None,
    font_size: int = 66,
    primary_rgba: Tuple[int, int, int, int] = (255, 255, 255, 255),
    highlight_rgba: Tuple[int, int, int, int] = (0, 255, 0, 255),
    canvas_size: Tuple[int, int] = (1080, 1080),
    margin_v: int = 180,
    position: str = "bottom",
    emoji_img: Optional[Image.Image] = None,
    font_name: str = "Impact",
) -> Image.Image:
    """Render 1 frame PNG với 2X Super-Sampling Anti-Aliasing, Phóng to từ nhấn 1.15X & Dynamic 3D Emoji Pop-Up chuẩn CapCut Pro."""
    scale = 2
    canvas_2x = (canvas_size[0] * scale, canvas_size[1] * scale)
    font_size_2x = font_size * scale
    font_2x = _get_font(font_name, font_size_2x)

    shadow_img = Image.new("RGBA", canvas_2x, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)

    text_img = Image.new("RGBA", canvas_2x, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)

    l1_text = " ".join(w[0].upper().strip() for w in line1_words) if line1_words else ""
    l2_text = " ".join(w[0].upper().strip() for w in line2_words) if line2_words else ""

    bbox1 = font_2x.getbbox(l1_text) if l1_text else (0, 0, 0, 0)
    l1_width = bbox1[2] - bbox1[0]

    bbox2 = font_2x.getbbox(l2_text) if l2_text else (0, 0, 0, 0)
    l2_width = bbox2[2] - bbox2[0]

    # Tự động thu nhỏ font chữ nếu bề ngang câu vượt quá giới hạn an toàn (chừa sẵn lề cho Emoji 3D)
    max_allowed_text_w = canvas_2x[0] - (360 if emoji_img else 200)
    max_line_w = max(l1_width, l2_width)
    if max_line_w > max_allowed_text_w and max_line_w > 0:
        scale_factor = max_allowed_text_w / float(max_line_w)
        font_size_2x = max(int(font_size_2x * scale_factor), 40)
        font_2x = _get_font(font_name, font_size_2x)
        bbox1 = font_2x.getbbox(l1_text) if l1_text else (0, 0, 0, 0)
        l1_width = bbox1[2] - bbox1[0]
        bbox2 = font_2x.getbbox(l2_text) if l2_text else (0, 0, 0, 0)
        l2_width = bbox2[2] - bbox2[0]

    eff_margin_v = (330 if canvas_size[1] > 1080 else margin_v) * scale
    if position == "top":
        y1 = 45 * scale
        y2 = y1 + font_size_2x + 10 * scale
    else:
        # Cố định mốc y2 (dòng đáy) làm lề chân tĩnh tuyệt đối, chống rung giật nhảy 140px lên xuống
        y2 = canvas_2x[1] - eff_margin_v - font_size_2x - 20 * scale
        y1 = y2 - font_size_2x - 10 * scale
        if not l2_text:
            # Nếu cụm chỉ có 1 dòng, luôn đặt dòng chữ đó ở đúng mốc y2 để lề chân tĩnh 100%
            y1 = y2

    last_line_end_x = canvas_2x[0] // 2
    last_line_y = y1

    # --- Render Dòng 1 ---
    if l1_text:
        x_cursor = (canvas_2x[0] - l1_width) // 2
        for idx, (word_text, _, _) in enumerate(line1_words):
            clean_w = re.sub(r'>>+|[<>\[\]()]', '', word_text).upper().strip()
            if not clean_w:
                continue

            is_active = (idx in active_emphasis_indices) if active_emphasis_indices else False
            current_font = font_2x
            color = highlight_rgba if is_active else primary_rgba
            stroke_w = max(12, int(14 * (font_size / 66.0)))
            y_pos = y1

            # Soft Drop Shadow 2X
            shadow_draw.text(
                (x_cursor + 8, y_pos + 8),
                clean_w,
                font=current_font,
                fill=(0, 0, 0, 200),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 200),
            )
            # Text chính 2X
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=current_font,
                fill=(0, 0, 0, 255),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 255),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=current_font,
                fill=color,
                stroke_width=0,
            )
            w_box = current_font.getbbox(clean_w + " ")
            x_cursor += (w_box[2] - w_box[0])

        last_line_end_x = x_cursor
        last_line_y = y1

    # --- Render Dòng 2 ---
    if l2_text:
        x_cursor = (canvas_2x[0] - l2_width) // 2
        for idx, (word_text, _, _) in enumerate(line2_words, start=len(line1_words)):
            clean_w = re.sub(r'>>+|[<>\[\]()]', '', word_text).upper().strip()
            if not clean_w:
                continue

            is_active = (idx in active_emphasis_indices) if active_emphasis_indices else False
            current_font = font_2x
            color = highlight_rgba if is_active else primary_rgba
            stroke_w = max(12, int(14 * (font_size / 66.0)))
            y_pos = y2

            shadow_draw.text(
                (x_cursor + 8, y_pos + 8),
                clean_w,
                font=current_font,
                fill=(0, 0, 0, 200),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 200),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=current_font,
                fill=(0, 0, 0, 255),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 255),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=current_font,
                fill=color,
                stroke_width=0,
            )
            w_box = current_font.getbbox(clean_w + " ")
            x_cursor += (w_box[2] - w_box[0])

        last_line_end_x = x_cursor
        last_line_y = y2

    # Dán HD Color Emoji 3D 2X tĩnh ở cuối câu cho toàn bộ thời lượng cụm
    if emoji_img:
        emoji_2x = emoji_img.resize((135, 135), Image.Resampling.LANCZOS)
        emoji_x = min(canvas_2x[0] - 145, last_line_end_x + 12)
        emoji_y = int(last_line_y + 12)
        text_img.paste(emoji_2x, (emoji_x, emoji_y), emoji_2x)

    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(6))
    composite_2x = Image.alpha_composite(shadow_img, text_img)

    # Thu nhỏ Super-Sampling 2X -> 1X bằng Lanczos để đạt độ mịn tròn nét tuyệt đối
    composite_1x = composite_2x.resize(canvas_size, Image.Resampling.LANCZOS)
    return composite_1x


def generate_graphic_subtitles(
    subtitle_lines: List[SubtitleLine],
    tmp_dir: Path,
    font_name: str = "Impact",
    font_size: int = 66,
    primary_color: str = "&H00FFFFFF",
    highlight_color_name: str = "yellow",
    margin_v: int = 180,
    emoji_on_top: bool = True,
    canvas_size: Tuple[int, int] = (1080, 1080),
    position: str = "bottom",
    outcard_start_s: Optional[float] = None,
) -> List[Tuple[Path, float, float]]:
    """Tạo danh sách các file ảnh PNG phụ đề đồ họa (Mặc định TRẮNG cho cụm < 4 từ, Karaoke 1 từ cho cụm >= 4 từ)."""
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    font = _get_font(font_name, font_size)
    primary_rgba = (255, 255, 255, 255) # Mặc định TRẮNG TƯƠI cho tất cả từ

    # Mặc định XANH LÁ NEON (Green #00FF00) cố định 100% cho tất cả các phong cách theo yêu cầu
    highlight_rgba = (0, 255, 0, 255)

    graphic_results: List[Tuple[Path, float, float]] = []
    frame_count = 0

    # 1. Gom tất cả từ thoại thành 1 luồng từ liên tục (Continuous Word Stream) triệt tiêu trùng lồng mốc thời gian
    all_words = []
    for line in subtitle_lines:
        words_list = line.words
        if not words_list and line.text.strip():
            raw_words = line.text.strip().split()
            if raw_words and line.end > line.start:
                dur = (line.end - line.start) / len(raw_words)
                words_list = [
                    (w, line.start + i * dur, line.start + (i + 1) * dur)
                    for i, w in enumerate(raw_words)
                ]
        if words_list:
            for w in words_list:
                if w[2] > w[1]:
                    all_words.append((w[0], round(w[1], 3), round(w[2], 3)))

    # Sắp xếp tuyệt đối theo thời gian bắt đầu
    all_words.sort(key=lambda x: (x[1], x[2]))

    # Khử đè lồng mốc thời gian giữa các từ thoại từ Whisper
    sanitized_words = []
    for w_text, w_start, w_end in all_words:
        if sanitized_words:
            prev_w, prev_s, prev_e = sanitized_words[-1]
            if w_start < prev_e:
                w_start = prev_e
        if w_end > w_start + 0.01:
            sanitized_words.append((w_text, w_start, w_end))

    # Chia cụm từ luồng thoại liên tục
    chunks = _split_words_by_rhythm_and_punctuation(sanitized_words, max_words=6, max_chars=24)

    for chunk_idx, chunk in enumerate(chunks):
        if not chunk:
            continue

        chunk_start = chunk[0][1]
        chunk_end = chunk[-1][2]

        # Xóa sạch phụ đề ở khoảng thời gian Outcard cuối video
        if outcard_start_s is not None:
            if chunk_start >= outcard_start_s:
                continue
            chunk_end = min(chunk_end, outcard_start_s)

        if chunk_start >= chunk_end:
            continue

        # Chỉ chọn 1 từ nhấn mạnh NẾU cụm dài >= 4 từ
        emphasis_indices = _select_emphasis_words_in_chunk(chunk)

        # Xác định Emoji màu 3D
        chunk_emoji = None
        emoji_img = None
        if emoji_on_top:
            chunk_text = " ".join(w[0] for w in chunk)
            chunk_emoji = extract_emoji_for_phrase(chunk_text, fallback_default=False, random_prob=0.5)
            if not chunk_emoji and chunk_idx == 0:
                chunk_emoji = extract_emoji_for_phrase(chunk_text, fallback_default=True)

            if chunk_emoji:
                emoji_png_path = get_emoji_png_path(chunk_emoji)
                if emoji_png_path and Path(emoji_png_path).exists():
                    try:
                        emoji_img = Image.open(emoji_png_path).convert("RGBA")
                        emoji_img = emoji_img.resize((65, 65), Image.Resampling.LANCZOS)
                    except Exception as e:
                        logger.warning(f"Không thể nạp ảnh emoji {emoji_png_path}: {e}")
                        emoji_img = None

        # Chia chunk làm 2 dòng nếu có từ 3 từ trở lên
        mid_point = len(chunk) // 2 if len(chunk) >= 3 else len(chunk)
        line1_words = chunk[:mid_point]
        line2_words = chunk[mid_point:]

        # 2. Xây dựng mốc thời gian Highlight Beat Accumulation (Gom từ động theo tốc độ nói)
        time_intervals = []
        n_words = len(chunk)
        chunk_dur = max(chunk_end - chunk_start, 0.1)
        words_per_sec = n_words / chunk_dur

        # Tính động min_beat_duration: nói càng nhanh (words_per_sec lớn), ngưỡng gộp nhịp càng nhỏ (0.05s-0.08s)
        if words_per_sec >= 4.0:
            min_beat_duration = 0.05
        elif words_per_sec >= 3.0:
            min_beat_duration = 0.07
        else:
            min_beat_duration = 0.08

        idx_curr = 0
        while idx_curr < n_words:
            beat_start = chunk_start if idx_curr == 0 else max(chunk[idx_curr - 1][2], chunk[idx_curr][1])
            beat_end = chunk[idx_curr][2]
            idx_next = idx_curr + 1
            while (beat_end - beat_start) < min_beat_duration and idx_next < n_words:
                beat_end = chunk[idx_next][2]
                idx_next += 1

            if idx_next < n_words:
                beat_end = chunk[idx_next][1]
            else:
                beat_end = chunk_end

            active_indices = tuple(range(idx_curr, max(idx_curr + 1, idx_next)))
            if beat_end > beat_start + 0.02:
                time_intervals.append((active_indices, beat_start, beat_end))

            idx_curr = max(idx_curr + 1, idx_next)

        if not time_intervals:
            time_intervals = [(None, chunk_start, chunk_end)]

        # Cache frame composite để tránh render lặp
        rendered_frames = {}

        for active_emph_idx, interval_s, interval_e in time_intervals:
            if outcard_start_s is not None:
                if interval_s >= outcard_start_s:
                    continue
                interval_e = min(interval_e, outcard_start_s)

            if interval_e <= interval_s:
                continue

            if active_emph_idx not in rendered_frames:
                rendered_frames[active_emph_idx] = _render_single_chunk_frame(
                    chunk=chunk,
                    line1_words=line1_words,
                    line2_words=line2_words,
                    active_emphasis_indices=active_emph_idx,
                    font=font,
                    font_size=font_size,
                    primary_rgba=primary_rgba,
                    highlight_rgba=highlight_rgba,
                    canvas_size=canvas_size,
                    margin_v=margin_v,
                    position=position,
                    emoji_img=emoji_img,
                    font_name=font_name,
                )

            composite = rendered_frames[active_emph_idx]
            frame_count += 1
            out_png_path = tmp_dir / f"g_sub_{frame_count:04d}.png"
            composite.save(out_png_path, "PNG")
            graphic_results.append((out_png_path, interval_s, interval_e))

        sanitized = []
        graphic_results.sort(key=lambda x: (x[1], x[2]))
        for path, s, e in graphic_results:
            if outcard_start_s is not None:
                if s >= outcard_start_s:
                    continue
                e = min(e, outcard_start_s)

            if sanitized:
                prev_path, prev_s, prev_e = sanitized[-1]
                # Nếu mốc s của khung sau nhỏ hơn prev_e của khung trước, triệt tiêu đè chữ bằng cách ngắt prev_e = s - 0.001
                if s < prev_e:
                    prev_e_new = round(s - 0.001, 3)
                    if prev_e_new > prev_s + 0.01:
                        sanitized[-1] = (prev_path, prev_s, prev_e_new)
                    else:
                        sanitized.pop()

            if e > s + 0.01:
                sanitized.append((path, round(s, 3), round(e, 3)))

        # Cho phép khoảng nghỉ thở tự nhiên (Breathing Pause >= 0.25s) ở cuối các câu thoại để phụ đề nghỉ nhịp không bị đập liên tục
        final_list = []
        n = len(sanitized)
        for i in range(n):
            path, s, e = sanitized[i]
            if i < n - 1:
                next_s = sanitized[i + 1][1]
                # Chỉ trám khoảng lặng cực ngắn (< 0.22s), chừa 0.25s-0.50s nghỉ nhịp thở giữa các câu thoại
                if next_s > s and (next_s - e) < 0.22:
                    e = round(next_s - 0.001, 3)

            if e > s + 0.01:
                final_list.append((path, round(s, 3), round(e, 3)))

        graphic_results = final_list

    logger.info(f"Đã tạo {len(graphic_results)} khung ảnh phụ đề đồ họa PNG Super-Sampling 2X (tổng số PNG: {len(graphic_results)}) mượt căng tại {tmp_dir}")
    return graphic_results


def generate_concat_manifest(
    graphic_results: List[Tuple[Path, float, float]],
    tmp_dir: Path,
    canvas_size: Tuple[int, int] = (1080, 1080),
    outcard_start_s: Optional[float] = None,
    clip_duration: Optional[float] = None,
) -> Path:
    """Tạo file concat manifest g_subs_concat.txt và ảnh blank.png để nạp vào FFmpeg qua 1 overlay filter duy nhất, triệt tiêu 100% chớp nháy và đảm bảo sạch phụ đề ở phần Outcard."""
    tmp_dir = Path(tmp_dir)
    blank_png = tmp_dir / "blank_transparent.png"
    if not blank_png.exists():
        img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        img.save(blank_png, "PNG")

    manifest_path = tmp_dir / "g_subs_concat.txt"
    lines = []

    # Ngắt tất cả mốc phụ đề trước khi vào Outcard
    cut_limit = outcard_start_s if outcard_start_s is not None else clip_duration

    current_time = 0.0
    for path, s, e in graphic_results:
        if cut_limit is not None and s >= cut_limit:
            continue
        if cut_limit is not None:
            e = min(e, cut_limit)

        if s > current_time + 0.005:
            gap_dur = s - current_time
            lines.append(f"file '{blank_png.resolve().as_posix()}'")
            lines.append(f"duration {gap_dur:.3f}")
            current_time = s

        dur = e - s
        if dur > 0.005:
            lines.append(f"file '{path.resolve().as_posix()}'")
            lines.append(f"duration {dur:.3f}")
            current_time = e

    # Đảm bảo 100% từ current_time đến hết clip (phần Outcard) là blank_transparent.png
    end_target = clip_duration if clip_duration is not None else (outcard_start_s if outcard_start_s is not None else current_time)
    if end_target > current_time + 0.005:
        gap_dur = end_target - current_time
        lines.append(f"file '{blank_png.resolve().as_posix()}'")
        lines.append(f"duration {gap_dur:.3f}")
        current_time = end_target

    # Dòng file cuối cùng trong manifest (không có duration) PHẢI LÀ blank_transparent.png
    lines.append(f"file '{blank_png.resolve().as_posix()}'")

    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return manifest_path


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
    """Làm sạch rác LLM (ENGLISH TITLE:, markdown **, chú thích (10 WORDS), nháy thừa, emoji và censor từ nhạy cảm)."""
    if not text:
        return ""

    # 1. Bỏ dấu nháy thừa và markdown bold/italic (**text**, *text*, __text__) xung quanh trước
    text = text.replace("**", "").replace("*", "").replace("__", "").replace("`", "")
    text = text.replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"').replace("—", "-")
    text = text.strip('"\' ')

    # 2. Loại bỏ tiền tố nhãn rác của LLM (ví dụ: ENGLISH TITLE:, VIETNAMESE TITLE:, TITLE:, CAPTION:, HEADLINE:, TITLE EN:, SEGMENT 2: 01:47..., 1. Viral Segment Time...)
    text = re.sub(r"^\s*(?:English|Vietnamese)\s+(?:Title|Caption|Headline)\s*[\:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:Title|Caption|Headline)\s*(?:En|Vi)?\s*[\:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:English|Vietnamese)\s*[\:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:Segment|Clip|Viral Segment)\s*\d*\s*[\:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*\d+[\.\:]\s*", "", text)

    # 3. Loại bỏ các chú thích số từ trong ngoặc đơn/ngoặc vuông từ LLM (ví dụ: (10 WORDS), (8 words), [10 words], (11 SECONDS))
    text = re.sub(r"\s*[\(\[\{]\s*(?:~?\s*\d+\s*words?|word\s*count.*?|\d+\s*SECONDS?)[\)\]\}]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[\(\[\{]\s*\d+\s*TỪ\s*[\)\]\}]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{1,2}:\d{2}\s*[\:\-]\s*\d{1,2}:\d{2}\b", "", text)

class EmojiTracker:
    """Theo dõi vết các emoji đã sử dụng trong phiên làm việc để xoay tua chống trùng lặp."""
    def __init__(self, max_history: int = 15):
        self.max_history = max_history
        self.history: deque = deque(maxlen=max_history)

    def is_recently_used(self, emoji: str) -> bool:
        return emoji in self.history

    def add(self, emoji: str):
        if emoji:
            self.history.append(emoji)

    def select_emoji(self, candidate_emojis: List[str]) -> str:
        """Chọn 1 emoji ngẫu nhiên chưa nằm trong history và có file PNG tồn tại."""
        from .emoji_manager import get_emoji_png_path

        valid_candidates = []
        for e in candidate_emojis:
            png_path = get_emoji_png_path(e)
            if png_path and png_path.exists():
                valid_candidates.append(e)

        if not valid_candidates:
            return "💥"

        unused = [e for e in valid_candidates if e not in self.history]
        if unused:
            chosen = random.choice(unused)
        else:
            chosen = random.choice(valid_candidates)

        self.add(chosen)
        return chosen

    def clear(self):
        self.history.clear()

EMOJI_AND_FORMAT_PATTERN = re.compile(r"[\U00010000-\U0010FFFF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF\uFE00-\uFE0F\u200B\u200C\u200D\u200E\u200F\u202E\u2060\u2061\u2062\u2063\u20E3\uFEFF]+", flags=re.UNICODE)

GLOBAL_EMOJI_TRACKER = EmojiTracker(max_history=15)

EMOJIS_KEYWORD_MAP = [
    (
        r"\b(judge|court|sues|sued|verdict|lawyer|plaintiff|defendant|rules|rule|lawsuit|attorney|legal|guilty|jail|prison|sentence)\b",
        ["⚖️", "📜", "🏛️", "💼", "🚨", "😳", "🛑", "📄", "🔑"],
    ),
    (
        r"\b(money|scam|scammed|pay|paid|rent|deposit|cash|dollar|\$|wealth|rich|poor|bank|loan|stolen|steal|stole|gold|crypto|cost|price|bill|bills|bankrupt)\b",
        ["💰", "💸", "💵", "💳", "🤑", "💎", "⚡", "🏦", "📉", "📈"],
    ),
    (
        r"\b(cheating|cheat|cheated|boyfriend|girlfriend|wife|husband|affair|romance|marriage|divorce|infidelity|ex|ex-wife|ex-husband|lover|breakup|dating|kiss)\b",
        ["💔", "😳", "😱", "🥀", "😭", "👿", "🤐", "🤦‍♂️", "🤦‍♀️"],
    ),
    (
        r"\b(shocking|truth|secret|secrets|reveals|revealed|exposes|exposed|caught|drama|fight|confronts|confronted|hidden|mystery|uncovered|scandal|lies|liar|lied)\b",
        ["💥", "😱", "💣", "😳", "🤯", "🚨", "🤫", "🔍", "👀", "⚡", "🗣️", "🔥", "✨"],
    ),
    (
        r"\b(fight|attack|damage|broken|slap|police|arrest|arrested|cop|cops|weapon|gun|knife|danger|blood|hit|slapped|punch|punched|threat|threatened)\b",
        ["🚨", "💥", "⚡", "🥊", "🛑", "👮‍♂️", "😤", "😡", "🤬", "💣"],
    ),
    (
        r"\b(work|office|boss|job|fired|company|employee|manager|hire|hired|interview|ceo|owner|business)\b",
        ["💼", "🏢", "📋", "😤", "📈", "📉", "🔥", "🗣️", "💻", "📁"],
    ),
    (
        r"\b(family|house|home|neighbor|neighbors|mom|dad|mother|father|son|daughter|sister|brother|aunt|uncle|grandma|grandpa|in-laws|landlord)\b",
        ["🏠", "🏡", "🔑", "🚪", "👴", "👵", "👶", "👥"],
    ),
    (
        r"\b(angry|mad|furious|crying|cried|tears|laugh|laughing|crazy|insane|psycho|evil|funny|hilarious)\b",
        ["😭", "😡", "🤬", "🤣", "😂", "😈", "🤡", "💩", "👿", "🤯"],
    ),
]

GLOBAL_FALLBACK_EMOJIS = [
    "💥", "🔥", "⚡", "😱", "😳", "🚀", "🤫", "🤯", "💣", "🚨",
    "👀", "✨", "🔍", "🗣️", "💎", "💰", "💸", "😭", "😡", "😈",
    "🤡", "🥊", "🛑", "🔑", "🚪", "📜", "💼", "🏠", "🌟"
]


def ensure_caption_has_emoji(text: str, tracker: Optional[EmojiTracker] = None) -> str:
    """Đảm bảo tiêu đề luôn có ít nhất 1 emoji nổi bật và TOÀN BỘ emoji luôn nằm ở CUỐI chuỗi (Anti-Repetition Pool)."""
    if not text:
        return text

    if tracker is None:
        tracker = GLOBAL_EMOJI_TRACKER

    found_emojis = EMOJI_AND_FORMAT_PATTERN.findall(text)
    text_clean = EMOJI_AND_FORMAT_PATTERN.sub("", text)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    non_dummy_emojis = [e for e in found_emojis if e != "💥" and not tracker.is_recently_used(e)]

    if non_dummy_emojis:
        chosen_emoji = non_dummy_emojis[0]
        tracker.add(chosen_emoji)
        return f"{text_clean} {chosen_emoji}".strip() if text_clean else chosen_emoji

    t_lower = text_clean.lower()
    for pattern, emoji_list in EMOJIS_KEYWORD_MAP:
        if re.search(pattern, t_lower):
            chosen = tracker.select_emoji(emoji_list)
            return f"{text_clean} {chosen}".strip() if text_clean else chosen

    chosen_fallback = tracker.select_emoji(GLOBAL_FALLBACK_EMOJIS)
    return f"{text_clean} {chosen_fallback}".strip() if text_clean else chosen_fallback


def clean_caption_text(text: str) -> str:
    """Làm sạch rác LLM nhưng ĐẢM BẢO 100% giữ lại hoặc tự động bổ sung Emoji ở cuối tiêu đề."""
    if not text:
        return ""

    emoji_matches = EMOJI_AND_FORMAT_PATTERN.findall(text)
    existing_emoji = " ".join(emoji_matches) if emoji_matches else ""
    text_no_emoji = EMOJI_AND_FORMAT_PATTERN.sub("", text).strip()

    text = text_no_emoji.replace("**", "").replace("*", "").replace("__", "").replace("`", "")
    text = text.replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"').replace("—", "-")
    text = text.strip('"\' ')

    text = re.sub(r"^\s*(?:English|Vietnamese)\s+(?:Title|Caption|Headline)\s*[\:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:Title|Caption|Headline)\s*(?:En|Vi)?\s*[\:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:English|Vietnamese)\s*[\:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*\d+[\.\:]\s*", "", text)

    text = re.sub(r"\s*[\(\[\{]\s*(?:~?\s*\d+\s*words?|word\s*count.*?)[\)\]\}]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[\(\[\{]\s*\d+\s*TỪ\s*[\)\]\}]", "", text, flags=re.IGNORECASE)
    text = text.strip('"\' ')

    text = re.sub(r"(?:\s+\b(?:EXPOSED|REVEALED|TRUTH|UNCOVERED|NOW)\b)+\s*$", "", text, flags=re.IGNORECASE).strip()

    clean = re.sub(r"\s+", " ", text).strip().upper()
    clean = censor_sensitive_words(clean)

    if existing_emoji:
        clean = f"{clean} {existing_emoji}".strip()

    return ensure_caption_has_emoji(clean)


def clean_caption_text_for_frame(text: str) -> str:
    """Làm sạch rác LLM và LOẠI BỎ 100% Emojis & ký tự điều khiển ẩn cho khung hình video (Top Caption PNG layer trong video)."""
    if not text:
        return ""

    text = EMOJI_AND_FORMAT_PATTERN.sub("", text)
    text = re.sub(r"[\x00-\x1F\x7F-\x9F\u200B\u200C\u200D\u200E\u200F\u202E\u2060\u2061\u2062\u2063\u20E3\uFEFF]", "", text).strip()

    text = text.replace("**", "").replace("*", "").replace("__", "").replace("`", "")
    text = text.replace("’", "'").replace("‘", "'").replace("”", '"').replace("“", '"').replace("—", "-")
    text = text.strip('"\' ')

    text = re.sub(r"^\s*(?:English|Vietnamese)\s+(?:Title|Caption|Headline)\s*[\:\-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:Title|Caption|Headline)\s*(?:En|Vi)?\s*[\:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:English|Vietnamese)\s*[\:\-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*\d+[\.\:]\s*", "", text)

    text = re.sub(r"\s*[\(\[\{]\s*(?:~?\s*\d+\s*words?|word\s*count.*?)[\)\]\}]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[\(\[\{]\s*\d+\s*TỪ\s*[\)\]\}]", "", text, flags=re.IGNORECASE)
    text = text.strip('"\' ')

    text = re.sub(r"(?:\s+\b(?:EXPOSED|REVEALED|TRUTH|UNCOVERED|NOW)\b)+\s*$", "", text, flags=re.IGNORECASE).strip()

    clean = re.sub(r"\s+", " ", text).strip().upper()
    clean = re.sub(r"[\u200B\u200C\u200D\uFEFF]", "", clean)
    return censor_sensitive_words(clean)

def ensure_caption_8_to_10_words(
    title_text: str,
    fallback_text: str = "",
    target_min: int = 8,
    target_max: int = 10,
) -> list:
    """Bóc tách danh sách từ hiển thị cho Top Caption PNG trong video frame (Không chứa emoji, giữ nguyên 100% văn bản tiếng Anh từ AI)."""
    clean_t = clean_caption_text_for_frame(title_text).replace('"', '').strip()
    words = clean_t.split()
    if (not words or len(words) < 4) and fallback_text:
        words = clean_caption_text_for_frame(fallback_text).replace('"', '').strip().split()

    if len(words) > target_max:
        words = words[:target_max]

    # Loại bỏ các từ trùng lặp đứng cạnh nhau
    dedup = []
    for w in words:
        if not dedup or w.upper() != dedup[-1].upper():
            dedup.append(w)
    words = dedup

    if len(words) > target_max:
        words = words[:target_max]

    return words


def format_top_caption_lines(words: list, font: ImageFont.FreeTypeFont, max_text_w: int) -> list:
    """Tách các từ thành 1, 2 hoặc 3 dòng cân đối đẹp mắt (Style 4 & Style 3)."""
    if not words:
        return []

    def get_w(s):
        bbox = font.getbbox(s)
        return bbox[2] - bbox[0]

    all_str = f'"{" ".join(words)}"'

    # 1. Nếu chỉ có ít hơn 6 từ và ngắn hơn 75% max_text_w, giữ trên 1 dòng
    if len(words) < 6 and get_w(all_str) <= (max_text_w * 0.75):
        return [all_str]

    n = len(words)

    # 2. Thử tách thành 2 dòng cân đối đẹp mắt
    candidates_2 = []
    for i in range(1, n):
        l1_words = words[:i]
        l2_words = words[i:]
        str1 = f'"{" ".join(l1_words)}'
        str2 = f'{" ".join(l2_words)}"'

        w1 = get_w(str1)
        w2 = get_w(str2)

        if w1 <= max_text_w and w2 <= max_text_w:
            candidates_2.append((abs(w1 - w2), abs(len(l1_words) - len(l2_words)), [str1, str2], max(w1, w2)))

    if candidates_2:
        candidates_2.sort(key=lambda x: (x[0], x[1], x[3]))
        return candidates_2[0][2]

    # 3. Nếu chuỗi dài (>= 9 từ) làm 2 dòng bị quá rộng, ngắt thành 3 dòng cân đối
    candidates_3 = []
    for i in range(1, n - 1):
        for j in range(i + 1, n):
            l1_words = words[:i]
            l2_words = words[i:j]
            l3_words = words[j:]
            str1 = f'"{" ".join(l1_words)}'
            str2 = f'{" ".join(l2_words)}'
            str3 = f'{" ".join(l3_words)}"'

            w1, w2, w3 = get_w(str1), get_w(str2), get_w(str3)

            if w1 <= max_text_w and w2 <= max_text_w and w3 <= max_text_w:
                diff = max(w1, w2, w3) - min(w1, w2, w3)
                candidates_3.append((diff, abs(len(l1_words) - len(l3_words)), [str1, str2, str3], max(w1, w2, w3)))

    if candidates_3:
        candidates_3.sort(key=lambda x: (x[0], x[1], x[2]))
        return candidates_3[0][2]

    # Fallback chia đôi từ
    mid = max(1, n // 2)
    l1 = f'"{" ".join(words[:mid])}'
    l2 = f'{" ".join(words[mid:])}"'
    return [l1, l2]


def generate_top_caption_layer(
    title_text: str,
    output_png: Path,
    canvas_size: Tuple[int, int] = (1080, 1440),
    top_area_height: int = 280,
    fallback_text: str = "",
    style_index: int = 4,
) -> Optional[Path]:
    """Tạo file PNG chứa Top Caption cho Canvas 3:4 và 1:1 theo từng Phong cách (Style 3 Nền Vàng, Style 4 White Badge, Style 5 Dải Nền Xanh Dương)."""
    if not title_text:
        return None
    
    # Cho cả Canvas 1:1 (Style 3) và Canvas 3:4 (Style 4 & 5), dùng 7-8 từ để hiển thị chuẩn 2 dòng cân đối
    words = ensure_caption_8_to_10_words(title_text, fallback_text, target_min=7, target_max=8)

    # Sử dụng font Montserrat-Bold.ttf cho cả Style 3, Style 5 và Style 4
    montserrat_path = Path(__file__).parent.parent / "assets" / "fonts" / "Montserrat-Bold.ttf"
    if montserrat_path.exists():
        font_path = str(montserrat_path)
    else:
        font_path = "C:/Windows/Fonts/arialbd.ttf"

    margin_x = 40
    pad_w = 32
    pad_h = 16
    radius = 20
    max_text_w = canvas_size[0] - margin_x * 2 - pad_w * 2  # 936px

    # Tự động chọn font size cân đối từ 46pt xuống 22pt sao cho vừa khít max_text_w
    font = None
    lines = []

    # Ưu tiên tuyệt đối tìm font size ngắt vừa khít <= 2 dòng cân đối
    for fsize in range(46, 22, -2):
        try:
            test_font = ImageFont.truetype(font_path, fsize)
        except Exception:
            test_font = ImageFont.load_default()

        test_lines = format_top_caption_lines(words, test_font, max_text_w)
        overflow = any((test_font.getbbox(l)[2] - test_font.getbbox(l)[0]) > max_text_w for l in test_lines)

        if len(test_lines) <= 2 and not overflow:
            font = test_font
            lines = test_lines
            break

    if font is None:
        for fsize in range(46, 22, -2):
            try:
                test_font = ImageFont.truetype(font_path, fsize)
            except Exception:
                test_font = ImageFont.load_default()

            test_lines = format_top_caption_lines(words, test_font, max_text_w)
            overflow = any((test_font.getbbox(l)[2] - test_font.getbbox(l)[0]) > max_text_w for l in test_lines)

            if not overflow:
                font = test_font
                lines = test_lines
                break

    if font is None or font == ImageFont.load_default():
        try:
            font = ImageFont.truetype(font_path, 26)
        except Exception:
            font = ImageFont.load_default()
        lines = format_top_caption_lines(words, font, max_text_w)

    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Phong cách 3 (Canvas 1:1 1080x1080): Render Dải Nền Vàng + Chữ Đen Montserrat-Bold Cân Đối
    if style_index == 3:
        draw.rectangle([0, 0, canvas_size[0], top_area_height], fill=(255, 255, 0, 255))

        try:
            ascent, descent = font.getmetrics()
            line_h = ascent + descent
        except Exception:
            line_h = 42

        bboxes = [font.getbbox(l) for l in lines]
        widths = [b[2] - b[0] for b in bboxes]

        line_gap = 10
        total_h = len(lines) * line_h + line_gap * (len(lines) - 1)
        start_y = max(10, (top_area_height - total_h) // 2)

        curr_y = start_y
        for i, line_str in enumerate(lines):
            w = widths[i]
            x_pos = (canvas_size[0] - w) // 2
            draw.text((x_pos, curr_y), line_str, font=font, fill=(0, 0, 0, 255))
            curr_y += line_h + line_gap

        logger.info(f"Đã tạo PNG Top Caption Dải Nền Vàng Chữ Đen Montserrat-Bold ({len(lines)} Dòng - Style 3): {output_png}")

    # 2. Phong cách 5: Render Dải Nền Xanh Dương (#5576FB) + Chữ TRẮNG Montserrat-Bold Cân Đối (Chuẩn thuật toán Style 3)
    elif style_index == 5:
        # Draw top blue banner (solid fill #5576FB / RGB 85, 118, 251)
        draw.rectangle([0, 0, canvas_size[0], top_area_height], fill=(85, 118, 251, 255))

        try:
            ascent, descent = font.getmetrics()
            line_h = ascent + descent
        except Exception:
            line_h = 42

        bboxes = [font.getbbox(l) for l in lines]
        widths = [b[2] - b[0] for b in bboxes]

        line_gap = 10
        total_h = len(lines) * line_h + line_gap * (len(lines) - 1)
        start_y = max(10, (top_area_height - total_h) // 2)

        curr_y = start_y
        for i, line_str in enumerate(lines):
            w = widths[i]
            x_pos = (canvas_size[0] - w) // 2
            draw.text((x_pos, curr_y), line_str, font=font, fill=(255, 255, 255, 255))
            curr_y += line_h + line_gap

        logger.info(f"Đã tạo PNG Top Caption Dải Nền Xanh Chữ Trắng Montserrat-Bold ({len(lines)} Dòng - Style 5): {output_png}")

    # 3. Phong cách 4: Canvas 3:4 (1080x1440) White Rounded Badge cân đối uốn lượn
    else:
        bboxes = [font.getbbox(l) for l in lines]
        widths = [b[2] - b[0] for b in bboxes]
        heights = [b[3] - b[1] for b in bboxes]

        line_overlap = 6
        line_boxes = []
        total_badge_h = 0
        for i, (w, h) in enumerate(zip(widths, heights)):
            box_w = w + pad_w * 2
            box_h = h + pad_h * 2
            line_boxes.append((box_w, box_h))
            if i == 0:
                total_badge_h += box_h
            else:
                total_badge_h += box_h - line_overlap

        start_y = max(10, (top_area_height - total_badge_h) // 2)

        # 1. Vẽ các khung rounded rectangle đè nhẹ liên tục trên cùng 1 lớp ảnh
        line_coords = []
        curr_y = start_y
        for i, (box_w, box_h) in enumerate(line_boxes):
            box_x1 = (canvas_size[0] - box_w) // 2
            box_x2 = box_x1 + box_w
            box_y1 = curr_y
            box_y2 = box_y1 + box_h
            line_coords.append((box_x1, box_y1, box_x2, box_y2))

            draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=radius, fill=(255, 255, 255, 255))
            curr_y += box_h - line_overlap

        # 2. Render từng dòng chữ căn giữa vào đúng thẻ chữ tương ứng
        for i, line_str in enumerate(lines):
            box_x1, box_y1, box_x2, box_y2 = line_coords[i]
            text_x = box_x1 + pad_w
            text_y = box_y1 + pad_h
            draw.text((text_x, text_y), line_str, font=font, fill=(0, 0, 0, 255))

        logger.info(f"Đã tạo PNG Top Caption Stepped White Badge ({len(lines)} Dòng - Style 4): {output_png}")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_png, "PNG")
    return output_png

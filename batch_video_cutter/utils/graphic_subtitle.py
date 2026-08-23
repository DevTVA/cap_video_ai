"""Graphic Subtitle Layer Generator using Pillow.

Renders subtitle text with classic CapCut Impact font from first commit,
solid 2-pass 8px black stroke (100% solid fill), soft 3D drop shadow,
3-color active word highlighting (Neon Green/Yellow/Red),
and pastes HD Color 3D PNG Emojis directly to the right of the period on a transparent PNG layer.
Ensures 100% frame-accurate timing and exact pixel positioning.
"""

import os
import re
import random
import hashlib
import functools
from collections import deque
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from loguru import logger

from .subtitle import SubtitleLine, SubtitleLayoutEngine, extract_emoji_for_phrase, COLOR_MAP
from .emoji_manager import get_emoji_png_path

# Global in-memory cache for chunk base layers
_CHUNK_BASE_CACHE: Dict[str, Tuple[Image.Image, List[Tuple[str, int, int, int]], int]] = {}
RENDERER_VERSION = "base-layer-v2"


def compute_multi_factor_cache_key(
    text_norm: str,
    font_name: str,
    font_size: int,
    primary_rgba: Tuple[int, int, int, int],
    canvas_size: Tuple[int, int],
    margin_v: int,
    position: str,
    emoji: str,
    renderer_version: str = RENDERER_VERSION,
) -> str:
    """Compute strict multi-factor cache key for chunk base layers."""
    raw_key = (
        f"{text_norm}|{font_name}|{font_size}|{primary_rgba}|"
        f"{canvas_size[0]}x{canvas_size[1]}|{margin_v}|{position}|"
        f"emoji={emoji}|v={renderer_version}"
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


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
    """Tải font chuẩn thông qua SubtitleLayoutEngine."""
    return SubtitleLayoutEngine.get_font(font_name, font_size)


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





NEGATION_WORDS = {
    "NEVER", "CAN'T", "DON'T", "WON'T", "NOT", "NO", "NOTHING", "NOBODY", "NEITHER", "NOR",
    "SHOULDN'T", "WOULDN'T", "COULDN'T", "DIDN'T", "HAVEN'T", "HASN'T", "HADN'T",
    "CANT", "DONT", "WONT", "ISNT", "ARENT", "WASNT", "WERENT", "HAVENT", "HASNT", "HADNT",
    "SHOULDNT", "WOULDNT", "COULDNT", "DIDNT"
}

EMOTIONAL_WORDS = {
    "LOVE", "HATE", "CRAZY", "AMAZING", "WORST", "BEST", "INSANE", "SHOCKING", "TERRIBLE",
    "AWFUL", "BEAUTIFUL", "HORRIBLE", "SCARED", "FEAR", "FURIOUS", "DISGUSTING", "UNBELIEVABLE"
}

ACTION_PUNCHLINE_WORDS = {
    "WHY", "HOW", "WHAT", "MONEY", "LIE", "LIAR", "CHEAT", "CHEATING", "DIVORCE", "COURT",
    "JUDGE", "KILL", "KILLED", "STEAL", "STOLE", "JAIL", "PRISON", "SCAM", "TRUTH", "SECRET",
    "EXPOSED", "REVEALED", "PROOF", "GUILTY", "POLICE", "LAWSUIT", "MURDER", "DEATH"
}


def calculate_word_semantic_score(word_text: str, duration: float = 0.0) -> float:
    """Tính điểm ý nghĩa ngữ pháp / cảm xúc / tác động của một từ để chọn từ highlight."""
    clean_w = re.sub(r"[^\w]", "", word_text).upper().strip()
    if not clean_w:
        return -100.0

    score = 0.0

    if clean_w in NEGATION_WORDS:
        score += 5.0
    elif clean_w in EMOTIONAL_WORDS:
        score += 4.5
    elif clean_w in ACTION_PUNCHLINE_WORDS:
        score += 4.0

    if clean_w in ENGLISH_STOP_WORDS and clean_w not in NEGATION_WORDS:
        score -= 10.0
    else:
        score += 1.0

    score += min(len(clean_w), 8) * 0.2
    if duration > 0.0:
        score += min(duration, 1.5) * 1.5

    return score


def _select_emphasis_words_in_chunk(chunk: List[Tuple[str, float, float]]) -> set:
    """Tự động chọn duy nhất 1 từ nhấn mạnh nhất trong cụm bằng thuật toán Semantic / Emotion / Action Scoring."""
    if not chunk or len(chunk) < 2:
        return set()

    best_idx = 0
    best_score = -float("inf")

    for idx, (word_text, s, e) in enumerate(chunk):
        dur = max(0.0, e - s)
        score = calculate_word_semantic_score(word_text, duration=dur)
        if score > best_score:
            best_score = score
            best_idx = idx

    return {best_idx}


def _render_chunk_base_layer(
    line1_words: List[tuple],
    line2_words: List[tuple],
    font_size: int = 66,
    primary_rgba: Tuple[int, int, int, int] = (255, 255, 255, 255),
    canvas_size: Tuple[int, int] = (1080, 1080),
    margin_v: int = 180,
    position: str = "bottom",
    emoji_img: Optional[Image.Image] = None,
    font_name: str = "Impact",
) -> Tuple[Image.Image, List[Tuple[str, int, int, int]], int]:
    """Tạo ảnh base 1X (gồm Drop Shadow + Black Stroke + Text Trắng + Emoji 3D) và vị trí từ 1X ONCE per chunk."""
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

    max_allowed_text_w = canvas_2x[0] - (360 if emoji_img else 200)
    max_line_w = max(l1_width, l2_width)
    eff_font_size = font_size
    if max_line_w > max_allowed_text_w and max_line_w > 0:
        scale_factor = max_allowed_text_w / float(max_line_w)
        font_size_2x = max(int(font_size_2x * scale_factor), 40)
        eff_font_size = max(int(font_size * scale_factor), 20)
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
        y2 = canvas_2x[1] - eff_margin_v - font_size_2x - 20 * scale
        y1 = y2 - font_size_2x - 10 * scale
        if not l2_text:
            y1 = y2

    last_line_end_x = canvas_2x[0] // 2
    last_line_y = y1
    word_positions = []

    # --- Render Dòng 1 ---
    if l1_text:
        x_cursor = (canvas_2x[0] - l1_width) // 2
        for idx, (word_text, _, _) in enumerate(line1_words):
            clean_w = re.sub(r'>>+|[<>\[\]()]', '', word_text).upper().strip()
            if not clean_w:
                continue

            stroke_w = max(12, int(14 * (font_size / 66.0)))
            y_pos = y1
            word_positions.append((clean_w, x_cursor // scale, y_pos // scale, idx))

            shadow_draw.text(
                (x_cursor + 8, y_pos + 8),
                clean_w,
                font=font_2x,
                fill=(0, 0, 0, 200),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 200),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=font_2x,
                fill=(0, 0, 0, 255),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 255),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=font_2x,
                fill=primary_rgba,
                stroke_width=0,
            )
            w_box = font_2x.getbbox(clean_w + " ")
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

            stroke_w = max(12, int(14 * (font_size / 66.0)))
            y_pos = y2
            word_positions.append((clean_w, x_cursor // scale, y_pos // scale, idx))

            shadow_draw.text(
                (x_cursor + 8, y_pos + 8),
                clean_w,
                font=font_2x,
                fill=(0, 0, 0, 200),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 200),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=font_2x,
                fill=(0, 0, 0, 255),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0, 255),
            )
            text_draw.text(
                (x_cursor, y_pos),
                clean_w,
                font=font_2x,
                fill=primary_rgba,
                stroke_width=0,
            )
            w_box = font_2x.getbbox(clean_w + " ")
            x_cursor += (w_box[2] - w_box[0])

        last_line_end_x = x_cursor
        last_line_y = y2

    if emoji_img:
        emoji_2x = emoji_img.resize((135, 135), Image.Resampling.LANCZOS)
        emoji_x = min(canvas_2x[0] - 145, last_line_end_x + 12)
        emoji_y = int(last_line_y + 12)
        text_img.paste(emoji_2x, (emoji_x, emoji_y), emoji_2x)

    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(6))
    composite_2x = Image.alpha_composite(shadow_img, text_img)
    composite_1x = composite_2x.resize(canvas_size, Image.Resampling.LANCZOS)

    return composite_1x, word_positions, eff_font_size


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
    """Tạo danh sách các file ảnh PNG phụ đề đồ họa từ các SubtitleChunk chuẩn hóa duy nhất."""
    from .subtitle import SubtitleChunker

    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    font = _get_font(font_name, font_size)
    primary_rgba = (255, 255, 255, 255)
    highlight_rgba = (0, 255, 0, 255)

    graphic_results: List[Tuple[Path, float, float]] = []
    frame_count = 0

    chunks = SubtitleChunker.chunk_lines(
        subtitle_lines,
        font,
        max_width_px=880,
        emoji_on_top=emoji_on_top,
        outcard_start_s=outcard_start_s,
    )

    total_words = 0
    estimated_words = 0
    highlighted_count = 0
    emoji_count = 0

    # Step 1: Multi-factor Cache Key Lookup & Bounded Parallel Pre-rendering for Cache Misses
    chunk_cache_keys = []
    miss_items = []

    for chunk in chunks:
        all_words = chunk.all_words
        total_words += len(all_words)
        if chunk.is_estimated:
            estimated_words += len(all_words)
        if chunk.highlighted_indices:
            highlighted_count += len(chunk.highlighted_indices)

        l1_text = " ".join(w[0] for w in chunk.line1_words) if chunk.line1_words else ""
        l2_text = " ".join(w[0] for w in chunk.line2_words) if chunk.line2_words else ""
        text_norm = f"{l1_text}|{l2_text}"
        c_key = compute_multi_factor_cache_key(
            text_norm=text_norm,
            font_name=font_name,
            font_size=font_size,
            primary_rgba=primary_rgba,
            canvas_size=canvas_size,
            margin_v=margin_v,
            position=position,
            emoji=chunk.emoji or "",
        )
        chunk_cache_keys.append(c_key)
        if c_key not in _CHUNK_BASE_CACHE:
            miss_items.append((c_key, chunk))

    if miss_items:
        max_workers = min(os.cpu_count() or 4, 4)

        def _render_task(item):
            k, c = item
            emoji_img = None
            if c.emoji:
                emoji_png_path = get_emoji_png_path(c.emoji)
                if emoji_png_path and Path(emoji_png_path).exists():
                    try:
                        emoji_img = Image.open(emoji_png_path).convert("RGBA")
                        emoji_img = emoji_img.resize((65, 65), Image.Resampling.LANCZOS)
                    except Exception as err:
                        logger.warning(f"Không thể nạp ảnh emoji {emoji_png_path}: {err}")
            b_1x, w_pos_1x, eff_sz = _render_chunk_base_layer(
                line1_words=c.line1_words,
                line2_words=c.line2_words,
                font_size=font_size,
                primary_rgba=primary_rgba,
                canvas_size=canvas_size,
                margin_v=margin_v,
                position=position,
                emoji_img=emoji_img,
                font_name=font_name,
            )
            return k, b_1x, w_pos_1x, eff_sz, bool(emoji_img)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(_render_task, miss_items)
            for k, b_1x, w_pos_1x, eff_sz, had_emoji in results:
                _CHUNK_BASE_CACHE[k] = (b_1x, w_pos_1x, eff_sz)
                if had_emoji:
                    emoji_count += 1

    # Step 2: Render active word interval frames from cached base layers
    for i_chunk, chunk in enumerate(chunks):
        chunk_start = chunk.start
        chunk_end = chunk.end
        all_words = chunk.all_words
        c_key = chunk_cache_keys[i_chunk]

        cached_base_1x, word_positions_1x, eff_font_size = _CHUNK_BASE_CACHE[c_key]
        base_1x = cached_base_1x.copy()
        font_1x = _get_font(font_name, eff_font_size)

        # Xây dựng mốc thời gian Highlight chuẩn word-by-word
        time_intervals = []
        n_words = len(all_words)
        for i_w, w_info in enumerate(all_words):
            w_start, w_end = w_info[1], w_info[2]
            w_start = round(max(chunk_start, w_start), 4)
            w_end = round(min(chunk_end, w_end), 4)
            if i_w < n_words - 1:
                next_start = all_words[i_w + 1][1]
                if 0.0 < (next_start - w_end) <= 0.15:
                    w_end = round(next_start, 4)
            if w_end > w_start + 0.01:
                time_intervals.append(((i_w,), w_start, w_end))

        if not time_intervals:
            time_intervals = [(None, chunk_start, chunk_end)]

        rendered_frames = {}
        for active_emph_idx, interval_s, interval_e in time_intervals:
            if outcard_start_s is not None:
                if interval_s >= outcard_start_s:
                    continue
                interval_e = min(interval_e, outcard_start_s)

            if interval_e <= interval_s:
                continue

            if active_emph_idx not in rendered_frames:
                if not active_emph_idx:
                    rendered_frames[active_emph_idx] = base_1x
                else:
                    frame_img = base_1x.copy()
                    frame_draw = ImageDraw.Draw(frame_img)
                    for clean_w, x_1x, y_1x, idx in word_positions_1x:
                        if idx in active_emph_idx:
                            frame_draw.text(
                                (x_1x, y_1x),
                                clean_w,
                                font=font_1x,
                                fill=highlight_rgba,
                                stroke_width=0,
                            )
                    rendered_frames[active_emph_idx] = frame_img

            composite = rendered_frames[active_emph_idx]
            frame_count += 1
            out_png_path = tmp_dir / f"g_sub_{frame_count:04d}.png"
            composite.save(out_png_path, "PNG", compress_level=1)
            graphic_results.append((out_png_path, interval_s, interval_e))

        # Explicit reference release to keep RAM bounded
        del base_1x
        del rendered_frames

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

    logger.info(f"Subtitle Stats: subtitle_words={total_words}, estimated_words={estimated_words}, subtitle_chunks={len(chunks)}, highlighted_words={highlighted_count}, emoji_count={emoji_count}")
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

    def select_emoji(self, candidate_emojis: List[str], seed_text: str = "") -> str:
        """Chọn 1 emoji có file PNG tồn tại một cách deterministic (deterministic hash)."""
        from .emoji_manager import get_emoji_png_path
        import hashlib

        valid_candidates = []
        for e in candidate_emojis:
            png_path = get_emoji_png_path(e)
            if png_path and png_path.exists():
                valid_candidates.append(e)

        if not valid_candidates:
            return "💥"

        h_key = f"{seed_text}_{len(self.history)}"
        idx = int(hashlib.md5(h_key.encode("utf-8")).hexdigest(), 16)

        unused = [e for e in valid_candidates if e not in self.history]
        if unused:
            chosen = unused[idx % len(unused)]
        else:
            chosen = valid_candidates[idx % len(valid_candidates)]

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
            chosen = tracker.select_emoji(emoji_list, seed_text=text_clean)
            return f"{text_clean} {chosen}".strip() if text_clean else chosen

    chosen_fallback = tracker.select_emoji(GLOBAL_FALLBACK_EMOJIS, seed_text=text_clean)
    return f"{text_clean} {chosen_fallback}".strip() if text_clean else chosen_fallback


def clean_caption_text(text: str) -> str:
    """Làm sạch rác LLM nhưng ĐẢM BẢO 100% giữ lại hoặc tự động bổ sung Emoji ở cuối tiêu đề."""
    if not text:
        return ""

    emoji_matches = EMOJI_AND_FORMAT_PATTERN.findall(text)
    existing_emoji = " ".join(emoji_matches) if emoji_matches else ""
    text_no_emoji = EMOJI_AND_FORMAT_PATTERN.sub("", text).strip()

    text = re.sub(r"\*{2,}", "", text_no_emoji)
    text = text.replace("__", "").replace("`", "")
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
        test_font = SubtitleLayoutEngine.get_font("Montserrat-Bold", fsize)

        test_lines = format_top_caption_lines(words, test_font, max_text_w)
        overflow = any((test_font.getbbox(l)[2] - test_font.getbbox(l)[0]) > max_text_w for l in test_lines)

        if len(test_lines) <= 2 and not overflow:
            font = test_font
            lines = test_lines
            break

    if font is None:
        for fsize in range(46, 22, -2):
            test_font = SubtitleLayoutEngine.get_font("Montserrat-Bold", fsize)
            test_lines = format_top_caption_lines(words, test_font, max_text_w)
            overflow = any((test_font.getbbox(l)[2] - test_font.getbbox(l)[0]) > max_text_w for l in test_lines)

            if not overflow:
                font = test_font
                lines = test_lines
                break

    if font is None:
        font = SubtitleLayoutEngine.get_font("Montserrat-Bold", 26)
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

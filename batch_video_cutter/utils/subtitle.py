"""Subtitle module.

Tạo file ASS subtitle với hiệu ứng CapCut Shorts / Reels word-by-word active highlight
(Font cỡ to gấp đôi 85pt, từ đang nói VÀNG TƯƠI, từ khác TRẮNG TƯƠI, bộ emoji màu sắc sinh động).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger


@dataclass
class SubtitleLine:
    """Một dòng/câu phụ đề."""
    text: str
    start: float
    end: float
    words: List[tuple] = None  # [(word, start, end), ...]

    def __post_init__(self):
        if self.words is None:
            self.words = []


# Bộ Emoji màu sắc đa dạng phong phú theo từ khóa (CapCut Text Your Into Emoji Template)
EMOTION_EMOJI_MAP = {
    # Cảm xúc & Trạng thái
    "happy": "😊", "vui": "😊", "sướng": "😊", "hạnh phúc": "😊",
    "laugh": "😂", "cười": "😂", "funny": "🤣", "hài": "🤣",
    "love": "❤️", "yêu": "❤️", "thương": "❤️", "thích": "❤️",
    "great": "🔥", "amazing": "🤩", "đỉnh": "🤩", "tuyệt": "🤩", "xịn": "🤩",
    "wow": "😲", "cool": "😎", "ngầu": "😎", "bá đạo": "😎",
    "yes": "✅", "chính xác": "✅", "chuẩn": "✅",
    "good": "👍", "tốt": "👍", "hay": "👍",
    "beautiful": "✨", "đẹp": "✨", "xinh": "✨", "ảo": "✨",
    "party": "🎉", "tiệc": "🎉", "ăn mừng": "🎉",
    "win": "🏆", "thắng": "🏆", "vô địch": "🏆", "chiến thắng": "🏆",
    "best": "⭐", "hay nhất": "⭐", "top": "⭐",
    "heart": "💖", "star": "🌟",
    "sad": "😢", "buồn": "😢", "nản": "😢",
    "angry": "😤", "tức": "😤", "bực": "😤", "giận": "😤",
    "shock": "😱", "sốc": "😱", "bất ngờ": "😱", "scared": "😨", "sợ": "😨",
    "cry": "😭", "khóc": "😭",
    "no": "❌", "không": "❌", "chưa": "❌", "đừng": "❌",
    "bad": "👎", "dở": "👎", "tệ": "👎", "cùi": "👎",
    "crazy": "🤯", "điên": "🤯", "ảo tưởng": "🤯",
    "fight": "💥", "đánh": "💥", "vỡ": "💥", "nổ": "💥",
    "dead": "💀", "chết": "💀", "toang": "💀", "tiêu": "💀",
    "fire": "🔥", "cháy": "🔥", "nóng": "🔥", "hot": "🔥",
    "secret": "🤫", "bí mật": "🤫", "giấu": "🤫",
    "ghost": "👻", "ma": "👻",
    "king": "👑", "vua": "👑", "chủ": "👑",
    "idea": "💡", "ý tưởng": "💡", "mẹo": "💡", "bí quyết": "💡",
    "think": "🤔", "suy nghĩ": "🤔", "nghĩ": "🤔", "hiểu": "🤔",
    "question": "❓", "hỏi": "❓", "thắc mắc": "❓",
    "money": "💰", "tiền": "💰", "đô": "💰", "giàu": "💰", "chi phí": "💰", "giá": "💰", "cash": "💵",
    "food": "🍕", "ăn": "🍕", "ngon": "🍕", "bánh": "🍕",
    "music": "🎵", "nhạc": "🎵", "hát": "🎵", "âm thanh": "🎵",
    "time": "⏰", "thời gian": "⏰", "giờ": "⏰", "phút": "⏰", "trễ": "⏰", "muộn": "⏰",
    "look": "👀", "xem": "👀", "nhìn": "👀", "thấy": "👀", "mắt": "👀",
    "rocket": "🚀", "tên lửa": "🚀", "tăng trưởng": "🚀", "bay": "🚀",
    "target": "🎯", "mục tiêu": "🎯", "đích": "🎯",
    "100": "💯", "hoàn hảo": "💯",
    "clap": "👏", "vỗ tay": "👏", "khen": "👏",
    "pray": "🙏", "cầu nguyện": "🙏", "xin": "🙏",
    "strong": "💪", "khỏe": "💪", "mạnh": "💪", "bền": "💪",
    "punch": "🥊", "đấm": "🥊",
    "run": "🏃", "chạy": "🏃", "nhanh": "🏃", "tốc độ": "🏃",
    "piece": "🧩", "puzzle": "🧩", "mảnh ghép": "🧩",
    "bolt": "⚡", "lightning": "⚡", "sét": "⚡", "nhanh như chớp": "⚡",
    "pin": "📍", "location": "📍", "địa điểm": "📍", "chỗ": "📍",
    "what": "🤔", "gì": "🤔", "cái gì": "🤔",
    "why": "🤔", "tại sao": "🤔", "vì sao": "🤔",

    # Vật phẩm, Thiên nhiên & Công nghệ
    "home": "🏠", "house": "🏠", "nhà": "🏠", "building": "🏢",
    "car": "🚗", "xe": "🚗", "ô tô": "🚗",
    "phone": "📱", "điện thoại": "📱", "app": "📱", "ứng dụng": "📱",
    "gift": "🎁", "quà": "🎁", "quà tặng": "🎁",
    "book": "📚", "sách": "📚", "khóa học": "📚", "học": "📚",
    "drink": "🥤", "uống": "🥤", "coffee": "☕", "cà phê": "☕", "beer": "🍺", "bia": "🍺",
    "dinner": "🍴", "lunch": "🍴", "meal": "🍲", "bữa ăn": "🍲",
    "baby": "👶", "em bé": "👶", "trẻ em": "👶",
    "man": "👨", "nam": "👨", "trai": "👨",
    "woman": "👩", "nữ": "👩", "gái": "👩",
    "dog": "🐶", "chó": "🐶", "cat": "🐱", "mèo": "🐱",
    "world": "🌍", "thế giới": "🌍", "toàn cầu": "🌍",
    "game": "🎮", "play": "🎮", "chơi": "🎮",
    "key": "🔑", "khóa": "🔑", "chìa khóa": "🔑",
    "luck": "🍀", "may mắn": "🍀",
    "sun": "☀️", "mặt trời": "☀️", "nắng": "☀️",
    "moon": "🌙", "mặt trăng": "🌙", "đêm": "🌙",
    "rain": "🌧️", "mưa": "🌧️",
}

# Bản đồ màu Highlight hỗ trợ ASS (Định dạng BGR: &H00BBGGRR&)
COLOR_MAP = {
    "green": "&H0000FF00&",   # Xanh lá neon #00FF00
    "red": "&H000000FF&",     # Đỏ rực #FF0000
    "yellow": "&H0000FFFF&",  # Vàng tươi #FFFF00
    "cyan": "&H00FFFF00&",    # Xanh ngọc #00FFFF
    "white": "&H00FFFFFF&",   # Trắng tinh
}


# Danh sách Emoji màu sinh động dùng khi chọn ngẫu nhiên
POPULAR_RANDOM_EMOJIS = [
    "🔥", "✨", "💥", "💡", "🚀", "⭐", "😎", "🤩", "💯", "🎯", "⚡", "😊", "🎉", "🏆", "👑", "🍕", "💰", "🏃", "🤫"
]


def measure_text_width_pixels(text: str, font_name: str = "Impact", font_size: int = 85) -> int:
    """Đo độ rộng thực tế từng pixel của chuỗi văn bản bằng font TTF từ assets/fonts."""
    from PIL import ImageFont

    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    font_path = None

    # Tìm file font TTF tương ứng trong assets/fonts
    font_candidates = [
        f"{font_name}.ttf",
        f"{font_name}-Regular.ttf",
        f"{font_name}-Bold.ttf",
        "Montserrat-Bold.ttf",
        "LuckiestGuy-Regular.ttf",
    ]
    for candidate in font_candidates:
        p = fonts_dir / candidate
        if p.exists():
            font_path = p
            break

    try:
        if font_path:
            font = ImageFont.truetype(str(font_path), font_size)
        else:
            font = ImageFont.load_default()
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]
    except Exception:
        return len(text) * 40


def extract_emoji_for_phrase(phrase_text: str, fallback_default: bool = False, random_prob: float = 0.4) -> Optional[str]:
    """Phân tích cụm từ (2-4 từ) để chọn Emoji màu sắc phù hợp hoặc xuất hiện ngẫu nhiên."""
    import random

    if not phrase_text:
        return None
    text_lower = phrase_text.lower()

    # 1. Ưu tiên khớp từ khóa trực tiếp
    for keyword, emoji in EMOTION_EMOJI_MAP.items():
        if keyword in text_lower:
            return emoji

    # 2. Khớp theo dấu câu hoặc từ phủ định
    if "?" in phrase_text:
        return "🤔"
    elif "!" in phrase_text:
        return "🔥"
    elif any(w in text_lower for w in ["không", "chưa", "đừng", "not", "don't", "can't", "won't", "no"]):
        return "⚡"

    # 3. Xuất hiện ngẫu nhiên nếu được bật (random appearance)
    if fallback_default or (random_prob > 0 and random.random() < random_prob):
        return random.choice(POPULAR_RANDOM_EMOJIS)

    return None


def add_emoji_to_text(text: str) -> str:
    """Thêm emoji sinh động vào câu phụ đề (tương thích ngược)."""
    res = extract_emoji_for_phrase(text, fallback_default=True)
    return res or "✨"



def _seconds_to_ass_time(seconds: float) -> str:
    """Chuyển giây thành format thời gian ASS (h:mm:ss.cc)."""
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def generate_ass_subtitle(
    subtitle_lines: List[SubtitleLine],
    output_path: Path,
    font_name: str = "Impact",
    font_size: int = 85,
    primary_color: str = "&H00FFFFFF",    # TRẮNG TƯƠI
    outline_color: str = "&H00000000",    # VIỀN ĐEN DÀY SIÊU MẬP
    highlight_color_name: str = "dynamic", # "dynamic" (luân chuyển 3 màu), "green", "red", "yellow"
    italic: bool = False,                 # Nghiêng chữ (Slant)
    position: str = "bottom",
    margin_v: int = 180,
    emoji_on_top: bool = True,            # Bật hiển thị Emoji sinh động màu sắc
    canvas_size: Tuple[int, int] = (1080, 1080),
) -> Path:
    """Tạo file ASS subtitle CapCut hoặc Graphic Subtitle PNG Layer chuẩn 100% đồng bộ."""
    import random
    from .emoji_manager import get_emoji_png_path

    output_path = Path(output_path)
    alignment = 8 if position == "top" else 2
    italic_flag = 1 if italic else 0

    # Nếu emoji_on_top được bật, sử dụng Graphic Subtitle Layer bằng Pillow để chữ và emoji là 1 khối duy nhất 100% đồng bộ
    if emoji_on_top:
        from .graphic_subtitle import generate_graphic_subtitles
        tmp_dir = output_path.parent / "g_subs_tmp"
        graphic_frames = generate_graphic_subtitles(
            subtitle_lines,
            tmp_dir=tmp_dir,
            font_name=font_name,
            font_size=font_size,
            primary_color=primary_color,
            highlight_color_name=highlight_color_name,
            margin_v=margin_v,
            emoji_on_top=True,
            canvas_size=canvas_size,
        )
        return output_path, graphic_frames

    # 3 màu Highlight chuẩn CapCut: Xanh lá, Vàng, Đỏ
    dynamic_colors = [COLOR_MAP["green"], COLOR_MAP["yellow"], COLOR_MAP["red"]]
    color_counter = 0

    header = f"""[Script Info]
Title: CapCut Text Your Into Emoji Subtitle Master
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,1,{italic_flag},0,0,100,100,0,0,1,6,2,{alignment},30,30,{margin_v},1
Style: EmojiStyle,Segoe UI Emoji,70,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,{alignment},30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: List[str] = []
    timed_emojis: List[tuple] = []

    for line_idx, line in enumerate(subtitle_lines):
        if not line.words:
            start_time = _seconds_to_ass_time(line.start)
            end_time = _seconds_to_ass_time(line.end)
            text_upper = line.text.upper()
            events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text_upper}")
            continue

        words_list = line.words
        chunk_size = 4
        chunks = [words_list[i:i + chunk_size] for i in range(0, len(words_list), chunk_size)]

        for chunk_idx, chunk in enumerate(chunks):
            if not chunk:
                continue

            for active_idx, active_word_info in enumerate(chunk):
                w_word, w_start, w_end = active_word_info
                start_time = _seconds_to_ass_time(w_start)
                end_time = _seconds_to_ass_time(w_end)

                if highlight_color_name.lower() in COLOR_MAP and highlight_color_name.lower() != "dynamic":
                    active_color_hex = COLOR_MAP[highlight_color_name.lower()]
                else:
                    active_color_hex = dynamic_colors[color_counter % len(dynamic_colors)]
                    color_counter += 1

                mid_point = len(chunk) // 2 if len(chunk) >= 3 else len(chunk)
                line1_words = chunk[:mid_point]
                line2_words = chunk[mid_point:]

                formatted_lines = []
                l1_formatted = []
                for idx, (word_text, _, _) in enumerate(line1_words):
                    clean_word = word_text.upper().strip()
                    if idx == active_idx:
                        l1_formatted.append(f"{{\\fscx118\\fscy118\\c{active_color_hex}}}{clean_word}{{\\r\\c{primary_color}}}")
                    else:
                        l1_formatted.append(clean_word)
                if l1_formatted:
                    formatted_lines.append(" ".join(l1_formatted))

                l2_formatted = []
                for idx, (word_text, _, _) in enumerate(line2_words, start=len(line1_words)):
                    clean_word = word_text.upper().strip()
                    if idx == active_idx:
                        l2_formatted.append(f"{{\\fscx118\\fscy118\\c{active_color_hex}}}{clean_word}{{\\r\\c{primary_color}}}")
                    else:
                        l2_formatted.append(clean_word)
                if l2_formatted:
                    formatted_lines.append(" ".join(l2_formatted))

                main_text = "\\N".join(formatted_lines)
                events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{main_text}")

    content = header + "\n".join(events) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8-sig")

    logger.info(f"Tạo ASS Subtitle CapCut: {output_path} ({len(events)} events)")
    return output_path, timed_emojis




def create_subtitles_from_transcript(
    segments,
    clip_start: float,
    clip_end: float,
    output_path: Path,
    position: str = "bottom",
    font_name: str = "Montserrat Black",
    font_size: int = 80,
    highlight_color_name: str = "green",
    italic: bool = False,
    add_emojis: bool = True,
    canvas_size: Tuple[int, int] = (1080, 1080),
) -> tuple:
    """Tạo file ASS subtitle CapCut Active Word từ transcript segments và trả về (sub_path, timed_emojis)."""
    subtitle_lines: List[SubtitleLine] = []

    for seg in segments:
        if seg.end < clip_start or seg.start > clip_end:
            continue

        relative_start = max(0, seg.start - clip_start)
        relative_end = min(clip_end - clip_start, seg.end - clip_start)

        words = []
        if hasattr(seg, "words") and seg.words:
            for word_seg in seg.words:
                w_start = max(0, word_seg.start - clip_start)
                w_end = min(clip_end - clip_start, word_seg.end - clip_start)
                if w_start < w_end:
                    words.append((word_seg.word, w_start, w_end))

        # FALLBACK: Nếu Whisper không trả về mốc từ chi tiết (cho các video sau như 10, 11, 12), tự tạo mốc thời gian đều
        if not words and seg.text.strip():
            raw_words = seg.text.strip().split()
            if raw_words and relative_end > relative_start:
                duration_per_word = (relative_end - relative_start) / len(raw_words)
                for i, w in enumerate(raw_words):
                    w_start = relative_start + i * duration_per_word
                    w_end = relative_start + (i + 1) * duration_per_word
                    words.append((w, w_start, w_end))

        subtitle_lines.append(SubtitleLine(
            text=seg.text,
            start=relative_start,
            end=relative_end,
            words=words,
        ))

    return generate_ass_subtitle(
        subtitle_lines,
        output_path,
        font_name=font_name,
        font_size=font_size,
        highlight_color_name=highlight_color_name,
        italic=italic,
        position=position,
        emoji_on_top=add_emojis,
        canvas_size=canvas_size,
    )


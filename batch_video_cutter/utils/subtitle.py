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
    timestamp_source: str = "whisper"  # "whisper" hoặc "fallback"

    def __post_init__(self):
        if self.words is None:
            self.words = []


def estimate_word_timings(
    text: str,
    start: float,
    end: float,
) -> List[Tuple[str, float, float]]:
    """Tự động phân bổ thời lượng từ (estimate_word_timings) theo thứ tự ưu tiên:
    1. Trả về rỗng nếu text rỗng hoặc duration <= 0.
    2. Char-Weighted Allocation + Punctuation Pause Weight.
    3. Uniform fallback nếu sum(weights) <= 0.
    Gắn mốc từ hoàn toàn hợp lệ mà không có overlap hay negative duration.
    """
    if not text or not text.strip() or end <= start:
        return []

    raw_words = text.strip().split()
    if not raw_words:
        return []

    total_dur = end - start

    def _calc_word_weight(w: str) -> float:
        clean_w = re.sub(r"[^\w]", "", w)
        weight = max(1.0, float(len(clean_w)))
        if w.endswith((",", ";", ":")):
            weight += 1.5
        elif w.endswith((".", "!", "?")):
            weight += 2.5
        return weight

    weights = [_calc_word_weight(w) for w in raw_words]
    total_weight = sum(weights)
    if total_weight <= 0:
        total_weight = float(len(raw_words))
        weights = [1.0] * len(raw_words)

    words = []
    curr_t = start
    for i, w in enumerate(raw_words):
        w_dur = (weights[i] / total_weight) * total_dur
        w_start = round(curr_t, 4)
        if i == len(raw_words) - 1:
            w_end = round(end, 4)
        else:
            w_end = round(min(end, curr_t + w_dur), 4)

        if w_end <= w_start:
            w_end = round(w_start + 0.05, 4)
            if w_end > end:
                w_end = end

        if w_start < w_end:
            words.append((w, w_start, w_end))
        curr_t = w_end

    return words


class SubtitleTimingValidator:
    """Central validator & timing fixer cho Subtitle Word, Line, Chunk và Clip boundary."""

    @staticmethod
    def validate_and_fix_words(
        words: List[Tuple[str, float, float]],
        start_boundary: float = 0.0,
        end_boundary: Optional[float] = None,
        min_word_dur: float = 0.03,
    ) -> List[Tuple[str, float, float]]:
        """Validate và nắn chỉnh mốc thời gian từng từ:
        - start >= start_boundary
        - end > start
        - clamp overlap (word.start < prev_end)
        - clamp end_boundary
        - loại bỏ word hoàn toàn nằm ngoài boundary
        """
        if not words:
            return []

        fixed_words: List[Tuple[str, float, float]] = []
        prev_end = start_boundary

        for w_tuple in words:
            if len(w_tuple) < 3:
                continue
            w_text, w_start, w_end = w_tuple[0], float(w_tuple[1]), float(w_tuple[2])

            if end_boundary is not None and w_start >= end_boundary:
                continue
            if w_end <= start_boundary:
                continue

            w_start = max(start_boundary, w_start)
            if end_boundary is not None:
                w_end = min(end_boundary, w_end)

            if w_start < prev_end - 0.0001:
                w_start = prev_end

            if w_end <= w_start:
                w_end = round(w_start + min_word_dur, 4)
                if end_boundary is not None and w_end > end_boundary:
                    w_end = end_boundary

            if w_end > w_start:
                w_start_r = round(w_start, 4)
                w_end_r = round(w_end, 4)
                if w_end_r > w_start_r:
                    fixed_words.append((w_text, w_start_r, w_end_r))
                    prev_end = w_end_r

        return fixed_words

    @classmethod
    def validate_and_fix_line(
        cls,
        line: SubtitleLine,
        clip_duration: float = 0.0,
    ) -> SubtitleLine:
        """Validate và clamp mốc thời gian cho SubtitleLine."""
        eff_clip_dur = clip_duration if clip_duration > 0.0 else None

        line_start = max(0.0, float(line.start))
        line_end = float(line.end)

        if eff_clip_dur is not None:
            line_end = min(eff_clip_dur, line_end)

        if line_end <= line_start:
            line_end = line_start + 0.1

        fixed_words = cls.validate_and_fix_words(
            line.words,
            start_boundary=line_start,
            end_boundary=line_end if eff_clip_dur else None,
        )

        return SubtitleLine(
            text=line.text,
            start=round(line_start, 4),
            end=round(line_end, 4),
            words=fixed_words,
            timestamp_source=line.timestamp_source,
        )


def validate_subtitle_line(line: SubtitleLine, clip_duration: float = 0.0) -> bool:
    """Kiểm tra tính hợp lệ mốc thời gian dòng phụ đề và word-level timestamps:
    - start >= 0
    - end > start
    - end <= clip_duration (nếu clip_duration > 0)
    - không có word timestamp bị overlap hoặc start >= end
    """
    if line.start < 0.0 or line.end <= line.start:
        return False
    if clip_duration > 0.0 and line.end > clip_duration + 0.05:
        return False

    prev_w_end = line.start
    for w in line.words:
        if len(w) >= 3:
            _, w_start, w_end = w[0], w[1], w[2]
            if w_start < 0.0 or w_end <= w_start:
                return False
            if w_start < prev_w_end - 0.001:  # Allow 1ms rounding tolerance
                return False
            prev_w_end = w_end

    return True


class SubtitleLayoutEngine:
    """Single Source of Truth Layout Engine cho phụ đề (cả ASS Subtitle và Graphic Subtitle PNG)."""

    @staticmethod
    def get_font(font_name: str, font_size: int):
        """Nạp font chuẩn từ assets/fonts/ với fallback minh bạch, không phụ thuộc C:/Windows/Fonts."""
        from PIL import ImageFont

        fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
        clean_target = font_name.replace(" ", "").replace("-", "").replace("_", "").lower()

        # 1. Quét trong assets/fonts/ trước tiên
        if fonts_dir.exists():
            for font_file in fonts_dir.glob("*.ttf"):
                stem_clean = font_file.stem.replace(" ", "").replace("-", "").replace("_", "").lower()
                if clean_target in stem_clean or stem_clean in clean_target:
                    try:
                        return ImageFont.truetype(str(font_file), font_size)
                    except Exception:
                        pass

        # 2. Fallback sang các font chất lượng cao sẵn có trong assets/fonts
        fallback_names = [
            "Montserrat-Bold.ttf",
            "LuckiestGuy-Regular.ttf",
            "Fredoka-Bold.ttf",
            "Bangers-Regular.ttf",
            "TitanOne-Regular.ttf",
        ]
        for f_name in fallback_names:
            fp = fonts_dir / f_name
            if fp.exists():
                try:
                    return ImageFont.truetype(str(fp), font_size)
                except Exception:
                    pass

        logger.warning(f"⚠️ Không tìm thấy font '{font_name}' hay font thay thế trong assets/fonts. Dùng PIL Default Font.")
        return ImageFont.load_default()

    @classmethod
    def measure_text_width(cls, text: str, font) -> int:
        """Đo độ rộng pixel của chuỗi văn bản bằng font chỉ định."""
        if not text:
            return 0
        try:
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0]
        except Exception:
            return len(text) * 40

    @classmethod
    def layout_subtitle_line(
        cls,
        subtitle_line: SubtitleLine,
        font,
        max_width_px: int = 880,
        max_words_per_chunk: int = 6,
        max_chars_per_chunk: int = 24,
    ) -> List[Tuple[List[Tuple[str, float, float]], List[Tuple[str, float, float]]]]:
        """Chia mốc từ trong SubtitleLine thành các Chunks, mỗi Chunk gồm 2 danh sách dòng [line1_words, line2_words].
        
        Trả về: [(line1_words, line2_words), ...]
        Trong đó line1_words và line2_words là danh sách các tuple (word_text, start, end).
        
        Đảm bảo:
        - 100% giữ nguyên timing mốc từ (word.start, word.end)
        - Ngắt chunk theo Dấu câu, Khoảng nghỉ (pause > 0.35s), Max words, Natural phrase boundaries và Pixel width
        - Tách 2 dòng cân bằng pixel nếu 1 dòng vượt max_width_px
        """
        words = subtitle_line.words
        if not words:
            return []

        raw_chunks: List[List[Tuple[str, float, float]]] = []
        curr_chunk: List[Tuple[str, float, float]] = []

        PUNCTUATION_ENDINGS = (",", ".", "!", "?", ";", ":", "-", "...")
        UNNATURAL_SPLIT_AFTER = {
            "DON'T", "CAN'T", "WON'T", "ISN'T", "AREN'T", "WASN'T", "WEREN'T", "HAVEN'T", "HASN'T", "HADN'T",
            "WOULDN'T", "SHOULDN'T", "COULDN'T", "I'M", "YOU'RE", "HE'S", "SHE'S", "IT'S", "WE'RE", "THEY'RE",
            "THE", "A", "AN", "MY", "YOUR", "HIS", "HER", "ITS", "OUR", "THEIR", "THIS", "THAT", "THESE", "THOSE"
        }

        for i, w_info in enumerate(words):
            w_word, w_start, w_end = w_info[0], w_info[1], w_info[2]
            curr_chunk.append(w_info)

            chunk_text = " ".join(w[0].strip() for w in curr_chunk)
            clean_w_upper = re.sub(r"[^\w]", "", w_word).upper().strip()
            has_punctuation = any(w_word.strip().endswith(p) for p in PUNCTUATION_ENDINGS)

            has_pause = False
            if i < len(words) - 1:
                next_start = words[i + 1][1]
                if next_start - w_end > 0.35:
                    has_pause = True

            is_max_words = len(curr_chunk) >= max_words_per_chunk
            is_max_chars = len(chunk_text) >= max_chars_per_chunk
            is_over_width = cls.measure_text_width(chunk_text, font) >= int(max_width_px * 1.4)

            # Phân tách ưu tiên theo dấu câu / khoảng lặng trước, tránh ngắt giữa phrase nếu dính unnatural split
            should_split = False
            if has_punctuation or has_pause:
                should_split = True
            elif is_max_words or is_max_chars or is_over_width:
                # Nếu từ hiện tại là unnatural split (ví dụ "don't"), trì hoãn 1 từ nếu chưa vượt quá 1.5x giới hạn
                if clean_w_upper in UNNATURAL_SPLIT_AFTER and i < len(words) - 1 and len(curr_chunk) < max_words_per_chunk + 1:
                    should_split = False
                else:
                    should_split = True

            if should_split:
                raw_chunks.append(curr_chunk)
                curr_chunk = []

        if curr_chunk:
            raw_chunks.append(curr_chunk)

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
            combined_text = f"{prev_text} {curr_text}"
            combined_width = cls.measure_text_width(combined_text, font)
            has_prev_punc = any(prev[-1][0].strip().endswith(p) for p in PUNCTUATION_ENDINGS)

            if (prev_dur < 0.45 or len(prev) <= 2) and not has_prev_punc and combined_words <= max_words_per_chunk and combined_width <= int(max_width_px * 1.3):
                merged_chunks[-1] = prev + chunk
            else:
                merged_chunks.append(chunk)

        final_layout_chunks = []
        for chunk in merged_chunks:
            if not chunk:
                continue

            chunk_text = " ".join(w[0].strip() for w in chunk)
            chunk_width = cls.measure_text_width(chunk_text, font)

            if len(chunk) <= 2 or chunk_width <= max_width_px:
                final_layout_chunks.append((chunk, []))
            else:
                best_split = len(chunk) // 2
                best_score = float("inf")

                for k in range(1, len(chunk)):
                    l1 = chunk[:k]
                    l2 = chunk[k:]
                    t1 = " ".join(w[0].strip() for w in l1)
                    t2 = " ".join(w[0].strip() for w in l2)
                    w1 = cls.measure_text_width(t1, font)
                    w2 = cls.measure_text_width(t2, font)

                    penalty = 0.0
                    if w1 > max_width_px:
                        penalty += (w1 - max_width_px) * 10.0
                    if w2 > max_width_px:
                        penalty += (w2 - max_width_px) * 10.0

                    last_w_l1 = re.sub(r"[^\w]", "", l1[-1][0]).upper().strip()
                    if last_w_l1 in UNNATURAL_SPLIT_AFTER:
                        penalty += 80.0

                    diff = abs(w1 - w2) + penalty

                    if l1[-1][0].strip().endswith((",", ";", ":")):
                        diff -= 150.0

                    if diff < best_score:
                        best_score = diff
                        best_split = k

                l1_words = chunk[:best_split]
                l2_words = chunk[best_split:]
                final_layout_chunks.append((l1_words, l2_words))

        return final_layout_chunks


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
    "king": "👑", "vua": "👑", "chủ": "👑", "boss": "👑", "sếp": "👑",
    "idea": "💡", "ý tưởng": "💡", "mẹo": "💡", "bí quyết": "💡",
    "think": "🤔", "suy nghĩ": "🤔", "nghĩ": "🤔", "hiểu": "🤔",
    "question": "❓", "hỏi": "❓", "thắc mắc": "❓",
    "money": "💰", "tiền": "💰", "đô": "💰", "giàu": "💰", "chi phí": "💰", "giá": "💰", "cash": "💵", "kinh doanh": "💰", "bán hàng": "💰",
    "food": "🍕", "ăn": "🍕", "ngon": "🍕", "bánh": "🍕",
    "music": "🎵", "nhạc": "🎵", "hát": "🎵", "âm thanh": "🎵",
    "time": "⏰", "thời gian": "⏰", "giờ": "⏰", "phút": "⏰", "trễ": "⏰", "muộn": "⏰",
    "look": "👀", "xem": "👀", "nhìn": "👀", "thấy": "👀", "mắt": "👀",
    "rocket": "🚀", "tên lửa": "🚀", "tăng trưởng": "🚀", "bay": "🚀", "tương lai": "🚀", "future": "🚀",
    "target": "🎯", "mục tiêu": "🎯", "đích": "🎯",
    "100": "💯", "hoàn hảo": "💯",
    "clap": "👏", "vỗ tay": "👏", "khen": "👏",
    "pray": "🙏", "cầu nguyện": "🙏", "xin": "🙏",
    "strong": "💪", "khỏe": "💪", "mạnh": "💪", "bền": "💪", "kỹ năng": "💪", "skill": "💪",
    "punch": "🥊", "đấm": "🥊",
    "run": "🏃", "chạy": "🏃", "nhanh": "🏃", "tốc độ": "🏃",
    "piece": "🧩", "puzzle": "🧩", "mảnh ghép": "🧩",
    "bolt": "⚡", "lightning": "⚡", "sét": "⚡", "nhanh như chớp": "⚡",
    "pin": "📍", "location": "📍", "địa điểm": "📍", "chỗ": "📍",
    "what": "🤔", "gì": "🤔", "cái gì": "🤔",
    "why": "🤔", "tại sao": "🤔", "vì sao": "🤔",
    "ai": "🤖", "bot": "🤖", "robot": "🤖", "công nghệ": "💻", "tech": "💻", "computer": "💻", "máy tính": "💻", "code": "💻", "coder": "💻", "lập trình": "💻",

    # Vật phẩm, Thiên nhiên & Công nghệ
    "home": "🏠", "house": "🏠", "nhà": "🏠", "building": "🏢",
    "car": "🚗", "xe": "🚗", "ô tô": "🚗",
    "phone": "📱", "điện thoại": "📱", "app": "📱", "ứng dụng": "📱",
    "gift": "🎁", "quà": "🎁", "quà tặng": "🎁",
    "book": "📚", "sách": "📚", "khóa học": "📚", "học": "📚", "bài học": "📚", "kiến thức": "📚",
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
    """Đo độ rộng thực tế từng pixel của chuỗi văn bản bằng font nạp từ SubtitleLayoutEngine."""
    font = SubtitleLayoutEngine.get_font(font_name, font_size)
    return SubtitleLayoutEngine.measure_text_width(text, font)


def extract_emoji_for_phrase(
    phrase_text: str,
    fallback_default: bool = False,
    random_prob: float = 0.0,
    allow_random: bool = False,
) -> Optional[str]:
    """Phân tích cụm từ (2-4 từ) để chọn Emoji màu sắc phù hợp (Deterministic Mode mặc định)."""
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

    # 3. Xuất hiện ngẫu nhiên CHỈ KHI được opt-in (allow_random=True hoặc random_prob > 0)
    if allow_random and (fallback_default or random_prob > 0):
        import hashlib
        h = int(hashlib.md5(phrase_text.encode("utf-8")).hexdigest(), 16)
        rnd_val = (h % 1000) / 1000.0
        if fallback_default or rnd_val < random_prob:
            idx = h % len(POPULAR_RANDOM_EMOJIS)
            return POPULAR_RANDOM_EMOJIS[idx]

    return None


def add_emoji_to_text(text: str) -> str:
    """Thêm emoji sinh động vào câu phụ đề (tương thích ngược)."""
    res = extract_emoji_for_phrase(text, fallback_default=True, allow_random=True)
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
    highlight_color_name: str = "yellow", # Màu Vàng tươi cố định chuẩn
    italic: bool = False,                 # Nghiêng chữ (Slant)
    position: str = "bottom",
    margin_v: int = 180,
    emoji_on_top: bool = True,            # Bật hiển thị Emoji sinh động màu sắc
    canvas_size: Tuple[int, int] = (1080, 1080),
    outcard_start_s: Optional[float] = None,
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
            position=position,
            outcard_start_s=outcard_start_s,
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
    font = SubtitleLayoutEngine.get_font(font_name, font_size)

    for line_idx, line in enumerate(subtitle_lines):
        if not line.words:
            start_time = _seconds_to_ass_time(line.start)
            end_time = _seconds_to_ass_time(line.end)
            text_upper = line.text.upper()
            events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text_upper}")
            continue

        layout_chunks = SubtitleLayoutEngine.layout_subtitle_line(line, font, max_width_px=880)

        for line1_words, line2_words in layout_chunks:
            chunk = line1_words + line2_words
            if not chunk:
                continue

            for active_idx, active_word_info in enumerate(chunk):
                w_word, w_start, w_end = active_word_info
                start_time = _seconds_to_ass_time(w_start)
                end_time = _seconds_to_ass_time(w_end)

                active_color_hex = COLOR_MAP.get(highlight_color_name, COLOR_MAP["yellow"])

                formatted_lines = []
                l1_formatted = []
                for idx, (word_text, _, _) in enumerate(line1_words):
                    clean_word = word_text.upper().strip()
                    if idx == active_idx:
                        l1_formatted.append(f"{{\\c{active_color_hex}}}{clean_word}{{\\r\\c{primary_color}}}")
                    else:
                        l1_formatted.append(clean_word)
                if l1_formatted:
                    formatted_lines.append(" ".join(l1_formatted))

                l2_formatted = []
                for idx, (word_text, _, _) in enumerate(line2_words, start=len(line1_words)):
                    clean_word = word_text.upper().strip()
                    if idx == active_idx:
                        l2_formatted.append(f"{{\\c{active_color_hex}}}{clean_word}{{\\r\\c{primary_color}}}")
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
    outcard_start_s: Optional[float] = None,
    margin_v: int = 110,
) -> tuple:
    """Tạo file ASS subtitle CapCut Active Word từ transcript segments và trả về (sub_path, timed_emojis)."""
    subtitle_lines: List[SubtitleLine] = []
    clip_dur = max(0.0, clip_end - clip_start)

    for seg in segments:
        if seg.end <= clip_start or seg.start >= clip_end:
            continue

        relative_start = round(max(0.0, seg.start - clip_start), 4)
        relative_end = round(min(clip_dur, seg.end - clip_start), 4)

        if relative_end <= relative_start:
            continue

        words = []
        if hasattr(seg, "words") and seg.words:
            for word_seg in seg.words:
                if word_seg.end <= clip_start or word_seg.start >= clip_end:
                    continue
                w_start = round(max(0.0, word_seg.start - clip_start), 4)
                w_end = round(min(clip_dur, word_seg.end - clip_start), 4)
                if w_start < w_end:
                    words.append((word_seg.word, w_start, w_end))

            words = SubtitleTimingValidator.validate_and_fix_words(
                words,
                start_boundary=relative_start,
                end_boundary=relative_end,
            )

        ts_source = "whisper"
        if not words and seg.text.strip():
            ts_source = "fallback"
            logger.warning(f"⚠️ Transcript thiếu word timestamps thực tế cho segment: '{seg.text[:30]}...'. Đang sử dụng estimate_word_timings.")
            words = estimate_word_timings(seg.text.strip(), relative_start, relative_end)

        line = SubtitleLine(
            text=seg.text,
            start=relative_start,
            end=relative_end,
            words=words,
            timestamp_source=ts_source,
        )
        line = SubtitleTimingValidator.validate_and_fix_line(line, clip_duration=clip_dur)
        subtitle_lines.append(line)

    return generate_ass_subtitle(
        subtitle_lines,
        output_path,
        font_name=font_name,
        font_size=font_size,
        highlight_color_name=highlight_color_name,
        italic=italic,
        position=position,
        margin_v=margin_v,
        emoji_on_top=add_emojis,
        canvas_size=canvas_size,
        outcard_start_s=outcard_start_s,
    )


import math
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union, Any


class TimingSource(str, Enum):
    """Enum xác định nguồn gốc mốc thời gian của từ đơn."""
    WHISPER = "whisper"
    SRT = "srt"
    FALLBACK = "fallback"


@dataclass
class WordTiming:
    """Một từ đơn trong transcript kèm mốc thời gian chuẩn hóa và metadata nguồn gốc.

    Attributes:
        text: Nội dung từ.
        start: Thời điểm bắt đầu (giây).
        end: Thời điểm kết thúc (giây).
        confidence: Độ tin cậy (0.0 - 1.0) hoặc None nếu không có.
        timing_source: Nguồn mốc thời gian (TimingSource.WHISPER, SRT, FALLBACK).
        segment_index: Chỉ mục segment chứa từ.
        word_index: Chỉ mục vị trí từ trong câu.
    """

    text: str
    start: float
    end: float
    confidence: Optional[float] = None
    timing_source: Union[TimingSource, str] = TimingSource.WHISPER
    segment_index: Optional[int] = None
    word_index: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.timing_source, str):
            try:
                self.timing_source = TimingSource(self.timing_source.lower())
            except ValueError:
                self.timing_source = TimingSource.WHISPER

    @property
    def word(self) -> str:
        """Alias tương thích ngược với WordSegment.word."""
        return self.text

    @property
    def probability(self) -> float:
        """Alias tương thích ngược với WordSegment.probability."""
        return self.confidence if self.confidence is not None else 0.0

    def to_tuple(self) -> Tuple[str, float, float]:
        """Chuyển thành tuple (word_text, start, end) chuẩn cho subtitle layout."""
        return (self.text, round(self.start, 4), round(self.end, 4))


def normalize_word_timings(
    words: List[Union[WordTiming, Any, Tuple[str, float, float]]],
    range_start: Optional[float] = None,
    range_end: Optional[float] = None,
    make_relative: bool = False,
    min_word_dur: float = 0.03,
    default_source: Union[TimingSource, str] = TimingSource.WHISPER,
) -> List[WordTiming]:
    """Chuẩn hóa mốc thời gian từng từ qua pipeline 9 bước:
    1. Parse input items sang WordTiming objects.
    2. Validate text không rỗng & lọc bỏ từ không hợp lệ (NaN, None).
    3. Sort danh sách theo start time tăng dần (monotonic).
    4. Sửa timestamp âm (start >= 0).
    5. Fix invalid end time (end <= start -> end = start + min_dur).
    6. Resolve abnormal overlap & đảm bảo end > start sau khi dời start.
    7. Clip to requested range (intersection giữa range_start và range_end).
    8. Convert to clip-relative time (nếu make_relative=True).
    9. Trả về danh sách WordTiming hợp lệ.

    Args:
        words: Danh sách các từ đầu vào (WordTiming, WordSegment, hoặc tuple (text, start, end)).
        range_start: Mốc bắt đầu khoảng thời gian cần cắt/clip (giây).
        range_end: Mốc kết thúc khoảng thời gian cần cắt/clip (giây).
        make_relative: Nếu True, chuyển mốc thời gian về tương đối tính từ range_start.
        min_word_dur: Thời lượng tối thiểu cho một từ (mặc định 0.03s).
        default_source: Nguồn gốc timestamp mặc định ('whisper', 'srt', 'fallback').

    Returns:
        Danh sách WordTiming đã chuẩn hóa hoàn toàn.
    """
    if not words:
        return []

    def _is_invalid_float(val: Any) -> bool:
        if val is None:
            return True
        try:
            f = float(val)
            return math.isnan(f) or math.isinf(f)
        except (ValueError, TypeError):
            return True

    # 1. Parse input sang WordTiming objects
    parsed: List[WordTiming] = []
    for idx, w in enumerate(words):
        if isinstance(w, WordTiming):
            txt = str(w.text or "").strip()
            if _is_invalid_float(w.start) or _is_invalid_float(w.end):
                continue
            s_val = float(w.start)
            e_val = float(w.end)
            conf = float(w.confidence) if (w.confidence is not None and not _is_invalid_float(w.confidence)) else None
            source = w.timing_source or default_source
            seg_idx = w.segment_index
            w_idx = w.word_index if w.word_index is not None else idx
            wt = WordTiming(
                text=txt,
                start=s_val,
                end=e_val,
                confidence=conf,
                timing_source=source,
                segment_index=seg_idx,
                word_index=w_idx,
            )
        elif isinstance(w, (tuple, list)) and len(w) >= 3:
            txt = str(w[0] or "").strip()
            if _is_invalid_float(w[1]) or _is_invalid_float(w[2]):
                continue
            s_val = float(w[1])
            e_val = float(w[2])
            wt = WordTiming(
                text=txt,
                start=s_val,
                end=e_val,
                confidence=None,
                timing_source=default_source,
                word_index=idx,
            )
        elif hasattr(w, "start") and hasattr(w, "end"):
            txt = str(getattr(w, "text", getattr(w, "word", "")) or "").strip()
            if _is_invalid_float(w.start) or _is_invalid_float(w.end):
                continue
            s_val = float(w.start)
            e_val = float(w.end)
            conf_raw = getattr(w, "confidence", getattr(w, "probability", None))
            conf = float(conf_raw) if (conf_raw is not None and not _is_invalid_float(conf_raw)) else None
            source = getattr(w, "timing_source", default_source)
            seg_idx = getattr(w, "segment_index", None)
            w_idx = getattr(w, "word_index", idx)
            wt = WordTiming(
                text=txt,
                start=s_val,
                end=e_val,
                confidence=conf,
                timing_source=source,
                segment_index=seg_idx,
                word_index=w_idx,
            )
        else:
            continue

        # 2. Loại bỏ từ có text rỗng
        if not wt.text:
            continue
        parsed.append(wt)

    if not parsed:
        return []

    # 3. Sort theo start time tăng dần (monotonic) và theo word_index nếu trùng start
    parsed.sort(key=lambda x: (x.start, x.end, x.word_index or 0))

    # 4. Intersection check với range_start và range_end trước khi clamp
    filtered_and_clamped: List[WordTiming] = []
    for wt in parsed:
        if range_start is not None and wt.end <= range_start:
            continue
        if range_end is not None and wt.start >= range_end:
            continue

        w_start = wt.start
        w_end = wt.end

        # Clamp theo ranh giới
        if range_start is not None:
            w_start = max(range_start, w_start)
        if range_end is not None:
            w_end = min(range_end, w_end)

        # Không cho phép timestamp âm
        w_start = max(0.0, w_start)

        # Fix invalid end time (end <= start -> end = start + min_dur)
        if w_end <= w_start:
            w_end = round(w_start + min_word_dur, 4)
            if range_end is not None and w_end > range_end:
                w_end = range_end

        if w_end > w_start:
            wt.start = round(w_start, 4)
            wt.end = round(w_end, 4)
            filtered_and_clamped.append(wt)

    if not filtered_and_clamped:
        return []

    # 5. Resolve abnormal overlap & đảm bảo end > start sau khi dời start
    fixed_overlap: List[WordTiming] = []
    prev_end = 0.0
    if range_start is not None:
        prev_end = max(0.0, range_start)

    for wt in filtered_and_clamped:
        # Nếu start bị trùng/nhỏ hơn prev_end, dời start = prev_end
        if wt.start < prev_end - 0.0001:
            wt.start = prev_end

        # Phải đảm bảo end luôn lớn hơn start sau khi đã dời start
        if wt.end <= wt.start:
            wt.end = round(wt.start + min_word_dur, 4)
            if range_end is not None and wt.end > range_end:
                wt.end = range_end

        if wt.end > wt.start:
            wt.start = round(wt.start, 4)
            wt.end = round(wt.end, 4)
            fixed_overlap.append(wt)
            prev_end = wt.end

    if not fixed_overlap:
        return []

    # 6. Convert to clip-relative time nếu được yêu cầu
    if make_relative and range_start is not None:
        rel_offset = range_start
        clip_dur = (range_end - range_start) if range_end is not None else float("inf")
        final_relative: List[WordTiming] = []

        for wt in fixed_overlap:
            rel_start = round(max(0.0, wt.start - rel_offset), 4)
            rel_end = round(max(rel_start + 0.001, wt.end - rel_offset), 4)
            if clip_dur < float("inf"):
                rel_end = min(clip_dur, rel_end)

            if rel_end > rel_start:
                wt.start = rel_start
                wt.end = rel_end
                final_relative.append(wt)
        return final_relative

    return fixed_overlap

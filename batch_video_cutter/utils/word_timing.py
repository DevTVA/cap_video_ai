"""Word timing model và module chuẩn hóa mốc thời gian từ (Word-level timestamps).

Cung cấp dữ liệu chuẩn hóa cho pipeline phụ đề (ASS / PNG Graphic Subtitle).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union, Any


@dataclass
class WordTiming:
    """Một từ đơn trong transcript kèm mốc thời gian chuẩn hóa và metadata nguồn gốc.

    Attributes:
        text: Nội dung từ.
        start: Thời điểm bắt đầu (giây).
        end: Thời điểm kết thúc (giây).
        confidence: Độ tin cậy (0.0 - 1.0).
        timing_source: Nguồn mốc thời gian ('whisper', 'srt', 'estimated').
    """

    text: str
    start: float
    end: float
    confidence: float = 0.0
    timing_source: str = "whisper"

    @property
    def word(self) -> str:
        """Alias tương thích ngược với WordSegment.word."""
        return self.text

    @property
    def probability(self) -> float:
        """Alias tương thích ngược với WordSegment.probability."""
        return self.confidence

    def to_tuple(self) -> Tuple[str, float, float]:
        """Chuyển thành tuple (word_text, start, end) chuẩn cho subtitle layout."""
        return (self.text, round(self.start, 4), round(self.end, 4))


def normalize_word_timings(
    words: List[Union[WordTiming, Any, Tuple[str, float, float]]],
    range_start: Optional[float] = None,
    range_end: Optional[float] = None,
    make_relative: bool = False,
    min_word_dur: float = 0.03,
    default_source: str = "whisper",
) -> List[WordTiming]:
    """Chuẩn hóa mốc thời gian từng từ qua pipeline 9 bước:
    1. Parse input items sang WordTiming objects.
    2. Validate text không rỗng & lọc bỏ từ không hợp lệ.
    3. Sort danh sách theo start time tăng dần.
    4. Sửa timestamp âm (start >= 0).
    5. Fix invalid end time (end <= start -> end = start + min_dur).
    6. Resolve abnormal overlap (clamp w[i].start = prev_end).
    7. Clip to requested range (intersection giữa range_start và range_end).
    8. Convert to clip-relative time (nếu make_relative=True).
    9. Trả về danh sách WordTiming hợp lệ.

    Args:
        words: Danh sách các từ đầu vào (WordTiming, WordSegment, hoặc tuple (text, start, end)).
        range_start: Mốc bắt đầu khoảng thời gian cần cắt/clip (giây).
        range_end: Mốc kết thúc khoảng thời gian cần cắt/clip (giây).
        make_relative: Nếu True, chuyển mốc thời gian về tương đối tính từ range_start.
        min_word_dur: Thời lượng tối thiểu cho một từ (mặc định 0.03s).
        default_source: Nguồn gốc timestamp mặc định ('whisper', 'srt', 'estimated').

    Returns:
        Danh sách WordTiming đã chuẩn hóa hoàn toàn.
    """
    if not words:
        return []

    # 1. Parse input sang WordTiming objects
    parsed: List[WordTiming] = []
    for w in words:
        if isinstance(w, WordTiming):
            wt = WordTiming(
                text=w.text.strip(),
                start=float(w.start),
                end=float(w.end),
                confidence=float(w.confidence),
                timing_source=w.timing_source or default_source,
            )
        elif isinstance(w, (tuple, list)) and len(w) >= 3:
            wt = WordTiming(
                text=str(w[0]).strip(),
                start=float(w[1]),
                end=float(w[2]),
                confidence=0.0,
                timing_source=default_source,
            )
        elif hasattr(w, "start") and hasattr(w, "end"):
            txt = getattr(w, "text", getattr(w, "word", ""))
            conf = getattr(w, "confidence", getattr(w, "probability", 0.0))
            source = getattr(w, "timing_source", default_source)
            wt = WordTiming(
                text=str(txt).strip(),
                start=float(w.start),
                end=float(w.end),
                confidence=float(conf),
                timing_source=source,
            )
        else:
            continue

        # 2. Loại bỏ từ có text rỗng
        if not wt.text:
            continue
        parsed.append(wt)

    if not parsed:
        return []

    # 3. Sort theo start time tăng dần (và end time nếu trùng start)
    parsed.sort(key=lambda x: (x.start, x.end))

    # 4. Intersection check với range_start và range_end trước khi clamp
    filtered_and_clamped: List[WordTiming] = []
    for wt in parsed:
        # Nếu truyền range, kiểm tra intersection: segment.end > range_start và segment.start < range_end
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

        # Fix invalid end time
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

    # 5. Resolve abnormal overlap
    fixed_overlap: List[WordTiming] = []
    prev_end = 0.0
    if range_start is not None:
        prev_end = max(0.0, range_start)

    for wt in filtered_and_clamped:
        if wt.start < prev_end - 0.0001:
            wt.start = prev_end

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

"""Transcriber module.

Sử dụng faster-whisper để chuyển đổi giọng nói thành text
với word-level timestamps. Xử lý theo stream, không load toàn bộ vào RAM.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from loguru import logger


@dataclass
class WordSegment:
    """Một từ đơn trong transcript.

    Attributes:
        word: Nội dung từ.
        start: Thời điểm bắt đầu (giây).
        end: Thời điểm kết thúc (giây).
        probability: Độ tin cậy (0-1).
    """
    word: str
    start: float
    end: float
    probability: float = 0.0


@dataclass
class SentenceSegment:
    """Một câu trong transcript.

    Attributes:
        text: Nội dung câu.
        start: Thời điểm bắt đầu (giây).
        end: Thời điểm kết thúc (giây).
        words: Danh sách từ trong câu.
    """
    text: str
    start: float
    end: float
    words: List[WordSegment] = field(default_factory=list)


@dataclass
class TranscriptResult:
    """Kết quả transcript từ Whisper.

    Attributes:
        segments: Danh sách câu/đoạn.
        language: Ngôn ngữ phát hiện được.
        duration: Tổng thời lượng audio (giây).
        full_text: Toàn bộ text nối lại.
    """
    segments: List[SentenceSegment]
    language: str
    duration: float
    full_text: str


_MODEL_CACHE = {}


def get_whisper_model(
    model_name: str = "base.en",
    device: str = "cpu",
    compute_type: str = "int8",
):
    """Lấy hoặc khởi tạo instance WhisperModel từ cache."""
    key = (model_name, device, compute_type)
    if key not in _MODEL_CACHE:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "Chưa cài faster-whisper. Chạy: pip install faster-whisper"
            )
        logger.info(f"Nạp WhisperModel vào bộ nhớ (Singleton Cache): {model_name} | {device} | {compute_type}")
        _MODEL_CACHE[key] = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )
    return _MODEL_CACHE[key]


def cleanup_whisper_model():
    """Dọn dẹp giải phóng bộ nhớ model Whisper."""
    global _MODEL_CACHE
    _MODEL_CACHE.clear()


import re


def _parse_srt_file(srt_path: Path) -> List[SentenceSegment]:
    """Parse file phụ đề chuẩn SRT thành các SentenceSegment."""
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    blocks = content.strip().split("\n\n")
    segments: List[SentenceSegment] = []
    tc_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})')
    for b in blocks:
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        if len(lines) >= 2:
            for l in lines:
                m = tc_pattern.search(l)
                if m:
                    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
                    start = float(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0)
                    end = float(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0)
                    text_idx = lines.index(l) + 1
                    text = " ".join(lines[text_idx:])
                    if text.strip():
                        segments.append(SentenceSegment(
                            text=text.strip(),
                            start=start,
                            end=end,
                            words=[],
                        ))
                    break
    return segments


def _parse_subtitles_txt_file(txt_path: Path) -> List[SentenceSegment]:
    """Parse file chép lời subtitles.txt dạng [mm:ss] text thành các SentenceSegment."""
    content = txt_path.read_text(encoding="utf-8", errors="replace")
    raw_segments = []
    tc_pattern = re.compile(r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)')
    for line in content.splitlines():
        match = tc_pattern.match(line.strip())
        if match:
            tc, text = match.groups()
            parts = tc.split(':')
            if len(parts) == 2:
                sec = float(int(parts[0]) * 60 + int(parts[1]))
            else:
                sec = float(int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
            if text.strip():
                raw_segments.append((sec, text.strip()))

    segments: List[SentenceSegment] = []
    for i, (sec, text) in enumerate(raw_segments):
        if i < len(raw_segments) - 1:
            end_sec = raw_segments[i + 1][0]
        else:
            end_sec = sec + 3.0
        segments.append(SentenceSegment(
            text=text,
            start=sec,
            end=max(sec + 0.5, end_sec),
            words=[],
        ))
    return segments


def try_parse_existing_subtitles(video_path: Path) -> Optional[TranscriptResult]:
    """Kiểm tra và nạp phụ đề từ file *.srt hoặc subtitles.txt có sẵn trong folder video."""
    folder = Path(video_path).parent

    # 1. Thử nạp từ file SRT (*.srt)
    srt_files = list(folder.glob("*.srt"))
    if srt_files:
        srt_file = srt_files[0]
        try:
            segments = _parse_srt_file(srt_file)
            if segments:
                logger.info(f"⚡ Phát hiện file phụ đề SRT có sẵn: {srt_file.name}. Nạp trực tiếp trong 0.01s!")
                duration = segments[-1].end if segments else 0.0
                full_text = " ".join(s.text for s in segments)
                return TranscriptResult(
                    segments=segments,
                    language="en",
                    duration=duration,
                    full_text=full_text,
                )
        except Exception as e:
            logger.warning(f"Không thể đọc file SRT {srt_file.name}: {e}")

    # 2. Thử nạp từ file subtitles.txt
    txt_file = folder / "subtitles.txt"
    if txt_file.exists():
        try:
            segments = _parse_subtitles_txt_file(txt_file)
            if segments:
                logger.info(f"⚡ Phát hiện file chép lời subtitles.txt có sẵn. Nạp trực tiếp trong 0.01s!")
                duration = segments[-1].end if segments else 0.0
                full_text = " ".join(s.text for s in segments)
                return TranscriptResult(
                    segments=segments,
                    language="en",
                    duration=duration,
                    full_text=full_text,
                )
        except Exception as e:
            logger.warning(f"Không thể đọc file subtitles.txt: {e}")

    return None


def transcribe_video(
    video_path: Path,
    model_name: str = "base.en",
    device: str = "cpu",
    compute_type: str = "int8",
) -> TranscriptResult:
    """Chuyển đổi audio từ video thành text với word-level timestamps.

    Sử dụng faster-whisper để xử lý. Tự động extract audio từ video.
    Xử lý theo stream — KHÔNG load toàn bộ audio vào RAM.

    Args:
        video_path: Đường dẫn tới file video.
        model_name: Tên model Whisper (ví dụ: "base.en", "small.en").
        device: Thiết bị xử lý ("cpu" hoặc "cuda").
        compute_type: Kiểu tính toán ("int8", "float16", "float32").

    Returns:
        TranscriptResult chứa segments, words, language.

    Raises:
        FileNotFoundError: Nếu video_path không tồn tại.
        RuntimeError: Nếu transcription thất bại.
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video không tồn tại: {video_path}")

    # Ưu tiên kiểm tra và nạp file phụ đề có sẵn trong folder để chạy tức thì (0.01s)
    existing_result = try_parse_existing_subtitles(video_path)
    if existing_result:
        return existing_result

    logger.info(f"Bắt đầu transcribe bằng Whisper: {video_path.name}")

    # Lấy model từ Singleton cache
    model = get_whisper_model(model_name=model_name, device=device, compute_type=compute_type)

    # Transcribe — faster-whisper xử lý stream, không load hết vào RAM
    segments_generator, info = model.transcribe(
        str(video_path),
        language="en",
        word_timestamps=True,
        vad_filter=True,  # Lọc khoảng im lặng
    )

    logger.info(
        f"  Ngôn ngữ: {info.language} "
        f"(confidence: {info.language_probability:.2f}) "
        f"Duration: {info.duration:.1f}s"
    )

    all_segments: List[SentenceSegment] = []
    full_text_parts: List[str] = []
    last_logged_sec = 0.0
    total_dur = max(1.0, info.duration)

    logger.info(f"  Đang tiến hành bóc băng thoại (Vui lòng chờ CPU bóc {total_dur:.1f}s audio)...")

    for segment in segments_generator:
        words: List[WordSegment] = []

        if segment.words:
            for word_info in segment.words:
                words.append(WordSegment(
                    word=word_info.word.strip(),
                    start=word_info.start,
                    end=word_info.end,
                    probability=word_info.probability,
                ))

        sentence = SentenceSegment(
            text=segment.text.strip(),
            start=segment.start,
            end=segment.end,
            words=words,
        )
        all_segments.append(sentence)
        full_text_parts.append(segment.text.strip())

        # In log tiến độ bóc băng thoại mỗi khi đi được thêm ~180s (3 phút) nội dung audio
        if (segment.end - last_logged_sec >= 180.0) or (segment.end >= total_dur - 2.0):
            percent = min(100, int((segment.end / total_dur) * 100))
            logger.info(f"  [Whisper Progress] Đã bóc thoại: {segment.end:.1f}s / {total_dur:.1f}s ({percent}%)")
            last_logged_sec = segment.end

    full_text = " ".join(full_text_parts)

    logger.info(
        f"  Transcribe xong: {len(all_segments)} segments, "
        f"{sum(len(s.words) for s in all_segments)} words"
    )

    return TranscriptResult(
        segments=all_segments,
        language=info.language,
        duration=info.duration,
        full_text=full_text,
    )


def format_transcript_for_llm(
    result: TranscriptResult,
    intro_offset: float = 0.0,
    outro_offset: float = 0.0,
) -> str:
    """Format transcript thành text có timestamp để gửi cho LLM.
    Hỗ trợ lọc bỏ intro (ví dụ 10s đầu) và outro (ví dụ 25s cuối) khi chạy Phong cách 1 & 2.

    Args:
        result: Kết quả transcript.
        intro_offset: Số giây đầu bỏ qua (ví dụ 10s).
        outro_offset: Số giây cuối bỏ qua (ví dụ 25s).

    Returns:
        Chuỗi text có timestamp, mỗi dòng: [mm:ss] text
    """
    lines: List[str] = []
    max_end = max(0.0, result.duration - outro_offset) if (outro_offset > 0.0 and result.duration > outro_offset) else float("inf")
    for seg in result.segments:
        if seg.start >= intro_offset and (outro_offset == 0.0 or seg.end <= max_end):
            minutes = int(seg.start) // 60
            seconds = int(seg.start) % 60
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.text}")

    # Nếu bộ lọc làm rỗng transcript (do video quá ngắn), fallback về full transcript
    if not lines:
        for seg in result.segments:
            minutes = int(seg.start) // 60
            seconds = int(seg.start) % 60
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.text}")

    return "\n".join(lines)


def get_segments_in_range(
    result: TranscriptResult,
    start_time: float,
    end_time: float,
) -> List[SentenceSegment]:
    """Lấy các segments nằm trong khoảng thời gian.

    Args:
        result: Kết quả transcript đầy đủ.
        start_time: Thời điểm bắt đầu (giây).
        end_time: Thời điểm kết thúc (giây).

    Returns:
        Danh sách segments trong khoảng.
    """
    return [
        seg for seg in result.segments
        if seg.start >= start_time and seg.end <= end_time
    ]

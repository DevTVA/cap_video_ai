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

    logger.info(f"Bắt đầu transcribe: {video_path.name}")
    logger.info(f"  Model: {model_name} | Device: {device} | Compute: {compute_type}")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "Chưa cài faster-whisper. Chạy: pip install faster-whisper"
        )

    # Khởi tạo model
    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
    )

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


def format_transcript_for_llm(result: TranscriptResult) -> str:
    """Format transcript thành text có timestamp để gửi cho LLM.

    Args:
        result: Kết quả transcript.

    Returns:
        Chuỗi text có timestamp, mỗi dòng: [mm:ss] text
    """
    lines: List[str] = []
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

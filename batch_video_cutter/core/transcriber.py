"""Transcriber module.

Sử dụng faster-whisper để chuyển đổi giọng nói thành text
với word-level timestamps. Xử lý theo stream, không load toàn bộ vào RAM.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from loguru import logger


class OverlapType(str, Enum):
    """Phân loại quan hệ overlap giữa các subtitle segment."""
    NONE = "none"
    EXACT_DUPLICATE = "exact_duplicate"
    ROLLING_CAPTION = "rolling_caption"
    TRUE_CONFLICT = "true_conflict"


def classify_overlap(seg_a: "SentenceSegment", seg_b: "SentenceSegment") -> OverlapType:
    """Phân loại quan hệ overlap giữa 2 segment liên tiếp."""
    # 1. Không có overlap thời gian
    if seg_b.start >= seg_a.end - 0.01:
        return OverlapType.NONE

    # Chuẩn hóa text để so sánh
    text_a = seg_a.text.strip().lower()
    text_b = seg_b.text.strip().lower()

    # 2. Exact Duplicate: text giống nhau và timing trùng/gần trùng
    if text_a == text_b and abs(seg_a.start - seg_b.start) < 0.5:
        return OverlapType.EXACT_DUPLICATE

    # 3. Rolling Caption / Incremental Caption:
    # Câu B mở rộng hoặc kế thừa nội dung câu A (rolling prefix/suffix)
    words_a = text_a.split()
    words_b = text_b.split()
    if words_a and words_b:
        if text_b.startswith(text_a):
            return OverlapType.ROLLING_CAPTION
        for k in range(min(len(words_a), len(words_b)), 0, -1):
            if words_a[-k:] == words_b[:k]:
                return OverlapType.ROLLING_CAPTION

    # 4. True Conflict
    return OverlapType.TRUE_CONFLICT


@dataclass
class WordSegment:
    """Một từ đơn trong transcript.

    Attributes:
        word: Nội dung từ.
        start: Thời điểm bắt đầu (giây).
        end: Thời điểm kết thúc (giây).
        probability: Độ tin cậy (0-1).
        timing_source: Nguồn mốc thời gian ('whisper', 'srt', 'estimated').
    """
    word: str
    start: float
    end: float
    probability: float = 0.0
    timing_source: str = "whisper"

    @property
    def text(self) -> str:
        """Alias tương thích ngược."""
        return self.word

    @property
    def confidence(self) -> float:
        """Alias tương thích ngược."""
        return self.probability



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
        has_word_timestamps: Có mốc từ thực tế hay không.
        timestamp_source: Nguồn mốc thời gian ('whisper' hoặc 'fallback').
    """
    segments: List[SentenceSegment]
    language: str
    duration: float
    full_text: str
    has_word_timestamps: bool = True
    timestamp_source: str = "whisper"


_MODEL_CACHE = {}


def _setup_nvidia_dlls():
    """Tự động thêm thư mục DLL nvidia trong site-packages vào Windows PATH & DLL directory."""
    import os
    user_site = Path(os.path.expanduser("~")) / "AppData/Roaming/Python"
    for p in user_site.glob("**/site-packages/nvidia/*/bin"):
        if p.exists():
            try:
                os.add_dll_directory(str(p.resolve()))
            except Exception:
                pass
            os.environ["PATH"] = str(p.resolve()) + os.path.pathsep + os.environ.get("PATH", "")


def detect_whisper_device_and_compute_type(requested_device: str = "auto", requested_compute: str = "auto") -> tuple[str, str]:
    """Tự động phát hiện và chọn device ('cuda' hoặc 'cpu') cùng compute_type phù hợp nhất."""
    _setup_nvidia_dlls()

    if requested_device == "cpu":
        compute = "int8" if requested_compute == "auto" else requested_compute
        return "cpu", compute

    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            dev = "cuda"
            compute = "float16" if requested_compute == "auto" else requested_compute
            logger.info(f"⚡ Tự động phát hiện GPU NVIDIA — Chọn Whisper device: {dev} ({compute})")
            return dev, compute
    except Exception as e:
        logger.debug(f"Không thể kiểm tra CUDA ctranslate2: {e}")

    compute = "int8" if requested_compute == "auto" else requested_compute
    return "cpu", compute


def get_whisper_model(
    model_name: str = "base.en",
    device: str = "auto",
    compute_type: str = "auto",
):
    """Lấy hoặc khởi tạo instance WhisperModel từ cache (hỗ trợ tự động phát hiện CUDA)."""
    if device == "auto" or compute_type == "auto":
        device, compute_type = detect_whisper_device_and_compute_type(device, compute_type)

    key = (model_name, device, compute_type)
    if key not in _MODEL_CACHE:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "Chưa cài faster-whisper. Chạy: pip install faster-whisper"
            )
        
        try:
            logger.info(f"Nạp WhisperModel vào bộ nhớ (Singleton Cache): {model_name} | device={device} | compute={compute_type}")
            _MODEL_CACHE[key] = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )
        except Exception as e:
            if device != "cpu":
                logger.warning(f"⚠️ Khởi tạo WhisperModel trên {device} thất bại: {e}. Tự động fallback sang CPU int8...")
                return get_whisper_model(model_name=model_name, device="cpu", compute_type="int8")
            raise e

    return _MODEL_CACHE[key]


def cleanup_whisper_model():
    """Dọn dẹp giải phóng bộ nhớ model Whisper và VRAM CUDA."""
    global _MODEL_CACHE
    _MODEL_CACHE.clear()
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


import re


def _parse_srt_file(srt_path: Path) -> List[SentenceSegment]:
    """Parse file phụ đề chuẩn SRT thành các SentenceSegment có phân loại OverlapType."""
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    blocks = content.strip().split("\n\n")
    raw_segments: List[SentenceSegment] = []
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
                        raw_segments.append(SentenceSegment(
                            text=text.strip(),
                            start=start,
                            end=end,
                            words=[],
                        ))
                    break

    if not raw_segments:
        return []

    # Sắp xếp monotonic theo start time để xử lý các block bị out-of-order
    raw_segments.sort(key=lambda s: (s.start, s.end))

    # Chuẩn hóa mốc thời gian & phân loại overlap
    normalized_segments: List[SentenceSegment] = []
    n = len(raw_segments)
    for i in range(n):
        curr = raw_segments[i]

        # Sửa invalid timestamp: end <= start theo ngữ cảnh
        if curr.end <= curr.start:
            next_start = raw_segments[i + 1].start if i < n - 1 else None
            if next_start is not None and next_start > curr.start + 0.05:
                curr.end = min(curr.start + 0.5, next_start - 0.01)
            else:
                curr.end = curr.start + 0.5

        if curr.end <= curr.start:
            # Vẫn invalid -> Drop invalid segment
            continue

        if not normalized_segments:
            normalized_segments.append(curr)
            continue

        prev = normalized_segments[-1]
        overlap_type = classify_overlap(prev, curr)

        if overlap_type == OverlapType.EXACT_DUPLICATE:
            # Bỏ qua block trùng lặp hoàn toàn
            continue
        elif overlap_type == OverlapType.ROLLING_CAPTION:
            # Rolling caption: bảo toàn timing hợp lệ của câu prev (không cắt prev.end = curr.start)
            normalized_segments.append(curr)
        elif overlap_type == OverlapType.TRUE_CONFLICT:
            # Overlap xung đột thực sự: giữ cả 2 segment với timestamp hợp lệ của từng câu
            normalized_segments.append(curr)
        else:
            normalized_segments.append(curr)

    return normalized_segments


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
                    has_word_timestamps=False,
                    timestamp_source="srt",
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
                    has_word_timestamps=False,
                    timestamp_source="srt",
                )
        except Exception as e:
            logger.warning(f"Không thể đọc file subtitles.txt: {e}")

    return None


def align_existing_subtitles_with_whisper(
    existing_result: TranscriptResult,
    video_path: Path,
    model_name: str = "base.en",
    device: str = "auto",
    compute_type: str = "auto",
) -> TranscriptResult:
    """Thực hiện alignment audio với Whisper cho SRT sẵn có để lấy word-level timestamps chuẩn từ audio."""
    try:
        model = get_whisper_model(model_name=model_name, device=device, compute_type=compute_type)
        prompt_text = existing_result.full_text[:500] if existing_result.full_text else ""
        segments_generator, info = model.transcribe(
            str(video_path),
            language="en",
            word_timestamps=True,
            vad_filter=True,
            initial_prompt=prompt_text if prompt_text else None,
        )

        whisper_words: List[WordSegment] = []
        for seg in segments_generator:
            if seg.words:
                for w in seg.words:
                    whisper_words.append(WordSegment(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        probability=w.probability,
                    ))

        if not whisper_words:
            return existing_result

        has_any_words = False
        for seg in existing_result.segments:
            tol = 0.3
            seg_words = [
                WordSegment(
                    word=w.word,
                    start=max(seg.start, w.start),
                    end=min(seg.end, w.end),
                    probability=w.probability,
                    timing_source="whisper",
                )
                for w in whisper_words
                if (w.end > (seg.start - tol) and w.start < (seg.end + tol))
                and (min(seg.end, w.end) > max(seg.start, w.start))
            ]
            if seg_words:
                has_any_words = True
                seg.words = seg_words

        if has_any_words:
            existing_result.has_word_timestamps = True
            existing_result.timestamp_source = "whisper"
            logger.info(f"  ⚡ [Word Alignment Success] Đã bổ sung mốc từ audio thực tế cho SRT có sẵn!")
        return existing_result
    except Exception as e:
        logger.warning(f"Word alignment cho SRT thất bại: {e}")
        return existing_result


def estimate_words_for_subtitles(existing_result: TranscriptResult) -> TranscriptResult:
    """Nội suy word timestamps cho phụ đề SRT bằng Char-Weighted Alignment.
    
    Phân bổ thời lượng theo độ dài từ và dấu câu.
    Bảo đảm:
    - Loại bỏ hoàn toàn từ có zero-duration (end <= start).
    - Mốc thời gian đơn điệu tăng dần trong từng segment: start_k < end_k <= start_{k+1}.
    - Gán timing_source = 'estimated' cho từng WordSegment và TranscriptResult.
    """
    from ..utils.subtitle import fallback_estimate_word_timings

    for seg in existing_result.segments:
        if not seg.words:
            raw_words = fallback_estimate_word_timings(seg.text, seg.start, seg.end)
            seg_words: List[WordSegment] = []
            for w, ws, we in raw_words:
                ws_r = round(ws, 4)
                we_r = round(we, 4)
                if we_r > ws_r + 0.001:  # Loại bỏ zero-duration
                    seg_words.append(WordSegment(
                        word=w,
                        start=ws_r,
                        end=we_r,
                        probability=1.0,
                        timing_source="estimated",
                    ))

            # Bảo đảm monotonic trong từng segment
            for iw in range(len(seg_words) - 1):
                if seg_words[iw].end > seg_words[iw + 1].start:
                    seg_words[iw].end = seg_words[iw + 1].start
                if seg_words[iw].end <= seg_words[iw].start:
                    seg_words[iw].end = round(seg_words[iw].start + 0.01, 4)

            seg.words = seg_words

    existing_result.has_word_timestamps = True
    existing_result.timestamp_source = "estimated"
    return existing_result


def transcribe_video(
    video_path: Path,
    model_name: str = "base.en",
    device: str = "auto",
    compute_type: str = "auto",
    subtitle_align: str = "auto",
    use_cache: bool = True,
) -> TranscriptResult:
    """Chuyển đổi audio từ video thành text với word-level timestamps.

    Sử dụng faster-whisper để xử lý. Tự động extract audio từ video.
    Xử lý theo stream — KHÔNG load toàn bộ audio vào RAM.

    Hỗ trợ 3 chế độ subtitle_align:
    - 'auto': Mặc định. Tự động align SRT/txt có sẵn với audio bằng Whisper để đảm bảo 100% khớp nhịp giọng nói. Nếu không có SRT, chạy Whisper.
    - 'fast': Buộc dùng fast Char-Weighted alignment cho SRT/txt (gán timing_source='estimated', bỏ qua Whisper để tối đa tốc độ).
    - 'deep': Buộc dùng Whisper audio stream alignment cho SRT/txt (gán timing_source='whisper').

    Args:
        video_path: Đường dẫn tới file video.
        model_name: Tên model Whisper (ví dụ: "base.en", "small.en").
        device: Thiết bị xử lý ("cpu" hoặc "cuda").
        compute_type: Kiểu tính toán ("int8", "float16", "float32").
        subtitle_align: Chế độ căn chỉnh phụ đề ("auto", "fast", "deep").
        use_cache: Kích hoạt multi-factor disk cache (.cache/transcripts/).

    Returns:
        TranscriptResult chứa segments, words, language.

    Raises:
        FileNotFoundError: Nếu video_path không tồn tại.
        RuntimeError: Nếu transcription thất bại.
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video không tồn tại: {video_path}")

    from .cache_manager import (
        compute_transcript_cache_key,
        get_cached_transcript,
        save_cached_transcript,
    )

    # 1. Kiểm tra Multi-Factor Transcript Cache trên đĩa
    cache_key = compute_transcript_cache_key(video_path, whisper_model=model_name, language="en")
    if use_cache:
        cached = get_cached_transcript(cache_key)
        if cached is not None:
            # Nếu người dùng chạy ở chế độ auto hoặc deep, mà cache lại là 'estimated' -> Bỏ qua cache ước lượng để chạy Whisper align thật
            if subtitle_align in ("auto", "deep") and getattr(cached, "timestamp_source", "whisper") == "estimated":
                logger.info(f"🔄 Cache transcript hiện tại là bản ước lượng (estimated). Chế độ '{subtitle_align}' yêu cầu Whisper align thật -> Bỏ qua cache ước lượng để căn chỉnh chính xác theo audio.")
            else:
                logger.info(f"⚡ [Cache Hit] Nạp transcript từ cache ({cached.timestamp_source}): {cache_key[:12]}... (bỏ qua bóc băng)")
                return cached

    # 2. Ưu tiên kiểm tra và nạp file phụ đề có sẵn trong folder
    existing_result = try_parse_existing_subtitles(video_path)
    if existing_result:
        if not existing_result.has_word_timestamps:
            if subtitle_align == "fast":
                logger.info("⚡ [Fast Subtitle Mode] Tự động suy biến mốc từ cho SRT bằng Char-Weighted Alignment (timing_source='estimated'). Bỏ qua Whisper!")
                res = estimate_words_for_subtitles(existing_result)
                if use_cache:
                    save_cached_transcript(cache_key, res, video_path, whisper_model="srt_estimated")
                return res
            else:  # "auto" và "deep": Ưu tiên Whisper audio stream alignment để đảm bảo 100% khớp nhịp giọng nói
                logger.info(f"🔍 [{subtitle_align.upper()} Subtitle Alignment] Đang align SRT với audio bằng Whisper để khớp từng mili-giây với giọng nói thật...")
                res = align_existing_subtitles_with_whisper(
                    existing_result,
                    video_path,
                    model_name=model_name,
                    device=device,
                    compute_type=compute_type,
                )
                if use_cache:
                    save_cached_transcript(cache_key, res, video_path, whisper_model=model_name)
                return res
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

    res = TranscriptResult(
        segments=all_segments,
        language=info.language,
        duration=info.duration,
        full_text=full_text,
        has_word_timestamps=True,
        timestamp_source="whisper",
    )

    if use_cache:
        save_cached_transcript(cache_key, res, video_path, whisper_model=model_name)

    return res


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
    from .analyzer import is_intro_or_monologue_line
    for seg in result.segments:
        if seg.start >= intro_offset and (outro_offset == 0.0 or seg.end <= max_end):
            minutes = int(seg.start) // 60
            seconds = int(seg.start) % 60
            seg_text = seg.text
            if is_intro_or_monologue_line(seg_text):
                seg_text = f"{seg_text} [SHOW INTRO - DO NOT SELECT]"
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg_text}")

    # Nếu bộ lọc làm rỗng transcript (do video quá ngắn), fallback chấp nhận đoạn ngắn sau mốc intro_offset
    if not lines:
        eff_intro = intro_offset if result.duration > intro_offset + 20.0 else 0.0
        for seg in result.segments:
            if seg.start >= eff_intro:
                minutes = int(seg.start) // 60
                seconds = int(seg.start) % 60
                lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.text}")

    return "\n".join(lines)


def get_segments_in_range(
    result: TranscriptResult,
    start_time: float,
    end_time: float,
) -> List[SentenceSegment]:
    """Lấy các segments nằm trong khoảng thời gian (dùng giao cắt intersection và boundary clamping).

    Segment và word timestamps được giữ lại nếu có bất kỳ đoạn giao cắt nào với khoảng [start_time, end_time].
    Các mốc thời gian bắt đầu/kết thúc được clamp vừa khít với ranh giới [start_time, end_time].

    Args:
        result: Kết quả transcript đầy đủ.
        start_time: Thời điểm bắt đầu (giây).
        end_time: Thời điểm kết thúc (giây).

    Returns:
        Danh sách segments trong khoảng với mốc thời gian đã được clamp.
    """
    clipped_segments: List[SentenceSegment] = []

    for seg in result.segments:
        # Kiểm tra giao cắt intersection: seg.end > start_time và seg.start < end_time
        if seg.end <= start_time or seg.start >= end_time:
            continue

        c_start = max(seg.start, start_time)
        c_end = min(seg.end, end_time)

        if c_end <= c_start:
            continue

        # Intersection và clamp tương tự cho word-level timestamp
        clipped_words: List[WordSegment] = []
        if seg.words:
            for w in seg.words:
                if w.end <= start_time or w.start >= end_time:
                    continue
                w_start = max(w.start, start_time)
                w_end = min(w.end, end_time)
                if w_end > w_start:
                    w_source = getattr(w, "timing_source", "whisper")
                    clipped_words.append(WordSegment(
                        word=w.word,
                        start=w_start,
                        end=w_end,
                        probability=w.probability,
                        timing_source=w_source,
                    ))

        clipped_segments.append(SentenceSegment(
            text=seg.text,
            start=round(c_start, 4),
            end=round(c_end, 4),
            words=clipped_words,
        ))

    return clipped_segments

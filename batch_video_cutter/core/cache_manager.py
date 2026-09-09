"""Multi-Factor Cache Manager for Batch Video Cutter.

Handles:
1. Transcript Cache (.cache/transcripts/<key>.json): SHA256(mtime + size + model + lang + version)
2. Alignment Cache (.cache/alignments/<key>.json): SHA256(srt_hash + align_mode + range)
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

from .transcriber import TranscriptResult, SentenceSegment, WordSegment

CACHE_BASE_DIR = Path(__file__).parent.parent.parent / ".cache"
TRANSCRIPTS_CACHE_DIR = CACHE_BASE_DIR / "transcripts"
ALIGNMENTS_CACHE_DIR = CACHE_BASE_DIR / "alignments"
PIPELINE_CACHE_VERSION = "2.2.0"


def compute_transcript_cache_key(
    video_path: Path,
    whisper_model: str,
    language: str = "en",
    version: str = PIPELINE_CACHE_VERSION,
) -> str:
    """Compute strict multi-factor cache key for a video's transcript."""
    video_path = Path(video_path).resolve()
    stat = video_path.stat()
    raw = f"{stat.st_mtime_ns}_{stat.st_size}_{whisper_model}_{language}_{version}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_cached_transcript(cache_key: str) -> Optional[TranscriptResult]:
    """Retrieve cached TranscriptResult from disk."""
    cache_file = TRANSCRIPTS_CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        segments = []
        for s in data.get("segments", []):
            words = [
                WordSegment(
                    word=w["word"],
                    start=w["start"],
                    end=w["end"],
                    probability=w.get("probability", 1.0),
                    timing_source=w.get("timing_source", "whisper"),
                )
                for w in s.get("words", [])
            ]
            segments.append(
                SentenceSegment(
                    text=s["text"],
                    start=s["start"],
                    end=s["end"],
                    words=words,
                )
            )

        return TranscriptResult(
            segments=segments,
            language=data.get("language", "en"),
            duration=data.get("duration", 0.0),
            full_text=data.get("full_text", ""),
            has_word_timestamps=data.get("has_word_timestamps", True),
            timestamp_source=data.get("timestamp_source", "whisper"),
        )
    except Exception as e:
        logger.warning(f"Lỗi khi đọc Transcript Cache ({cache_key}): {e}")
        return None


def save_cached_transcript(
    cache_key: str,
    result: TranscriptResult,
    video_path: Path,
    whisper_model: str,
) -> None:
    """Save TranscriptResult to disk cache with complete metadata."""
    try:
        TRANSCRIPTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = TRANSCRIPTS_CACHE_DIR / f"{cache_key}.json"

        data = {
            "cache_key": cache_key,
            "video_path": str(video_path),
            "whisper_model": whisper_model,
            "language": result.language,
            "duration": result.duration,
            "full_text": result.full_text,
            "has_word_timestamps": result.has_word_timestamps,
            "timestamp_source": result.timestamp_source,
            "pipeline_version": PIPELINE_CACHE_VERSION,
            "segments": [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "words": [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "probability": w.probability,
                            "timing_source": w.timing_source,
                        }
                        for w in s.words
                    ],
                }
                for s in result.segments
            ],
        }

        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"Đã lưu Transcript Cache: {cache_file.name}")
    except Exception as e:
        logger.warning(f"Không thể ghi Transcript Cache: {e}")


def compute_alignment_cache_key(
    srt_content: str,
    align_mode: str,
    clip_range: str = "",
) -> str:
    """Compute cache key for subtitle alignment."""
    raw = f"{srt_content.strip()}_{align_mode}_{clip_range}_{PIPELINE_CACHE_VERSION}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_cached_alignment(cache_key: str) -> Optional[List[SentenceSegment]]:
    """Retrieve cached SentenceSegments with aligned words."""
    cache_file = ALIGNMENTS_CACHE_DIR / f"{cache_key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        segments = []
        for s in data.get("segments", []):
            words = [
                WordSegment(
                    word=w["word"],
                    start=w["start"],
                    end=w["end"],
                    probability=w.get("probability", 1.0),
                    timing_source=w.get("timing_source", "estimated"),
                )
                for w in s.get("words", [])
            ]
            segments.append(
                SentenceSegment(
                    text=s["text"],
                    start=s["start"],
                    end=s["end"],
                    words=words,
                )
            )
        return segments
    except Exception as e:
        logger.warning(f"Lỗi khi đọc Alignment Cache ({cache_key}): {e}")
        return None


def save_cached_alignment(cache_key: str, segments: List[SentenceSegment]) -> None:
    """Save aligned SentenceSegments to disk cache."""
    try:
        ALIGNMENTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = ALIGNMENTS_CACHE_DIR / f"{cache_key}.json"

        data = {
            "cache_key": cache_key,
            "pipeline_version": PIPELINE_CACHE_VERSION,
            "segments": [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "words": [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "probability": w.probability,
                            "timing_source": w.timing_source,
                        }
                        for w in s.words
                    ],
                }
                for s in segments
            ],
        }

        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"Đã lưu Alignment Cache: {cache_file.name}")
    except Exception as e:
        logger.warning(f"Không thể ghi Alignment Cache: {e}")

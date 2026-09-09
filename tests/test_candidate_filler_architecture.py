"""Unit tests for Candidate Filler Architecture, Pure Cache Layer, Title Resolution Waterfall, and Rejection Telemetry."""

import json
from pathlib import Path
import pytest

from batch_video_cutter.core.analyzer import (
    CandidateRejectionReason,
    REJECTION_TRACKER,
    get_rejection_summary,
    reset_rejection_tracker,
    _read_cache,
    _write_cache,
    resolve_segment_title,
    _fill_missing_segments,
    ViralSegment,
    TITLE_MIN_WORDS,
    TITLE_MAX_WORDS,
)


def test_pure_cache(tmp_path, monkeypatch):
    """Xác minh _read_cache() thuần túy đọc JSON từ đĩa mà không gọi filler/converter."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("batch_video_cutter.core.analyzer._CACHE_DIR", cache_dir)

    test_key = "dummy_cache_key_123"
    raw_data = [
        {
            "index": 1,
            "start_time": 40.0,
            "end_time": 67.0,
            "title_en": "SHORT TITLE 💥",
            "title_vi": "SHORT TITLE 💥",
            "start_timecode": "00:40",
            "end_timecode": "01:07",
        }
    ]

    cache_file = cache_dir / f"{test_key}.json"
    cache_file.write_text(json.dumps(raw_data), encoding="utf-8")

    # Read cache
    segments = _read_cache(test_key)
    assert segments is not None
    assert len(segments) == 1
    # Pure cache MUST return raw data without modifying title or dropping segment
    assert segments[0].title_en == "SHORT TITLE 💥"
    assert segments[0].start_time == 40.0
    assert segments[0].end_time == 67.0


def test_title_resolution_waterfall():
    """Xác minh chiến lược Tiêu đề 3 Tầng & Quy tắc vàng (Safeguard không reject candidate hợp lệ)."""
    seen_titles = set()
    sample_transcript = (
        "[00:40] Where were you at midnight on Tuesday night sir?\n"
        "[00:45] I was standing right next to the red sports car when the incident happened.\n"
        "[00:50] Did you see who fired the gun inside the building?"
    )

    # 1. Tier 1: Candidate title hợp lệ 8-10 từ tiếng Anh
    t1_title = resolve_segment_title(
        raw_title="SHOCKING COURTROOM CONFRONTATION BETWEEN THE WITNESS AND ATTORNEY 💥",
        transcript_text=sample_transcript,
        start_time=40.0,
        end_time=67.0,
        seen_titles=seen_titles,
    )
    assert "SHOCKING COURTROOM CONFRONTATION BETWEEN THE WITNESS AND ATTORNEY" in t1_title
    seen_titles.add(t1_title.lower())

    # 2. Tier 2: Spoken headline từ transcript khi candidate title không hợp lệ/rỗng
    t2_title = resolve_segment_title(
        raw_title="INVALID SHORT TITLE",
        transcript_text=sample_transcript,
        start_time=40.0,
        end_time=67.0,
        seen_titles=seen_titles,
    )
    assert t2_title != ""
    assert TITLE_MIN_WORDS <= len(t2_title.split()) <= TITLE_MAX_WORDS + 2  # Includes emoji
    seen_titles.add(t2_title.lower())

    # 3. Golden Rule Safeguard: When title inputs are missing/short, auto-pad spoken text so segment is valid
    t3_title = resolve_segment_title(
        raw_title="",
        transcript_text=sample_transcript,
        start_time=40.0,
        end_time=67.0,
        seen_titles=seen_titles,
    )
    assert t3_title != ""
    words_cnt = len([w for w in t3_title.split() if w.strip()])
    assert words_cnt >= TITLE_MIN_WORDS


def test_rejection_telemetry():
    """Xác minh Enum CandidateRejectionReason ghi nhận đúng từng loại lỗi và xuất bảng summary."""
    reset_rejection_tracker()

    REJECTION_TRACKER.record(CandidateRejectionReason.INTRO)
    REJECTION_TRACKER.record(CandidateRejectionReason.INTRO)
    REJECTION_TRACKER.record(CandidateRejectionReason.DURATION)
    REJECTION_TRACKER.record(CandidateRejectionReason.DIALOGUE)
    REJECTION_TRACKER.record(CandidateRejectionReason.DUPLICATE)
    REJECTION_TRACKER.record(CandidateRejectionReason.OUTRO)
    REJECTION_TRACKER.record(CandidateRejectionReason.TITLE)
    REJECTION_TRACKER.record(CandidateRejectionReason.OVERLAP)

    summary_dict = REJECTION_TRACKER.get_summary()
    assert summary_dict["INTRO"] == 2
    assert summary_dict["DURATION"] == 1
    assert summary_dict["DIALOGUE"] == 1
    assert summary_dict["DUPLICATE"] == 1
    assert summary_dict["OUTRO"] == 1
    assert summary_dict["TITLE"] == 1
    assert summary_dict["OVERLAP"] == 1

    table_text = get_rejection_summary()
    assert "📊 TỔNG HỢP LÝ DO LOẠI CANDIDATE (REJECTION TELEMETRY):" in table_text
    assert "- INTRO     : 2" in table_text
    assert "- DURATION  : 1" in table_text

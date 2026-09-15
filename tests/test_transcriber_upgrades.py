"""Unit tests cho các nâng cấp của Transcriber module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from batch_video_cutter.core.cache_manager import (
    TRANSCRIPTS_CACHE_DIR,
    compute_transcript_cache_key,
    get_cached_transcript,
)
from batch_video_cutter.core.transcriber import (
    TranscriptResult,
    SentenceSegment,
    WordSegment,
    align_existing_subtitles_with_whisper,
    transcribe_video,
)


def test_cache_cleanup_on_empty_or_corrupted(tmp_path: Path):
    """Test cơ chế tự động dọn dẹp cache khi file rỗng hoặc không có segments."""
    fake_key = "test_corrupt_cache_key_9999"
    TRANSCRIPTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = TRANSCRIPTS_CACHE_DIR / f"{fake_key}.json"

    # 1. Trường hợp file rỗng/chỉ chứa duration = 0 và segments = []
    empty_payload = {
        "duration": 0.0,
        "segments": [],
        "full_text": "",
    }
    cache_file.write_text(json.dumps(empty_payload), encoding="utf-8")
    assert cache_file.exists()

    result = get_cached_transcript(fake_key)
    assert result is None
    assert not cache_file.exists(), "Cache rỗng phải bị xóa tự động"

    # 2. Trường hợp file JSON bị lỗi cú pháp
    cache_file.write_text("{corrupted_json_syntax...", encoding="utf-8")
    assert cache_file.exists()

    result2 = get_cached_transcript(fake_key)
    assert result2 is None
    assert not cache_file.exists(), "Cache hỏng cú pháp phải bị xóa tự động"


def test_language_and_condition_on_previous_text(tmp_path: Path):
    """Test tham số language, condition_on_previous_text=False và vad_parameters truyền đúng vào model.transcribe."""
    mock_model = MagicMock()
    mock_info = MagicMock()
    mock_info.language = "vi"
    mock_info.language_probability = 0.98
    mock_info.duration = 10.0

    mock_seg = MagicMock()
    mock_seg.words = [MagicMock(word="Xin", start=0.0, end=0.3, probability=0.9)]
    mock_seg.text = "Xin chào"
    mock_seg.start = 0.0
    mock_seg.end = 1.0

    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    fake_video = tmp_path / "fake_video.mp4"
    fake_video.write_bytes(b"dummy video data")

    with patch("batch_video_cutter.core.transcriber.try_parse_existing_subtitles", return_value=None), \
         patch("batch_video_cutter.core.transcriber.get_whisper_model", return_value=mock_model), \
         patch("batch_video_cutter.core.cache_manager.get_cached_transcript", return_value=None), \
         patch("batch_video_cutter.core.cache_manager.save_cached_transcript", return_value=None):

        # Test model đa ngữ với language="vi"
        res = transcribe_video(
            fake_video,
            model_name="small",
            language="vi",
            use_cache=False,
        )

        assert res is not None
        assert mock_model.transcribe.called
        call_kwargs = mock_model.transcribe.call_args[1]

        assert call_kwargs["language"] == "vi"
        assert call_kwargs["condition_on_previous_text"] is False
        assert call_kwargs["vad_filter"] is True
        assert call_kwargs["vad_parameters"] == {"min_silence_duration_ms": 500}


def test_english_model_forces_en_language(tmp_path: Path):
    """Test model kết thúc bằng .en luôn truyền language='en'."""
    mock_model = MagicMock()
    mock_info = MagicMock(language="en", language_probability=1.0, duration=5.0)
    mock_model.transcribe.return_value = ([], mock_info)

    fake_video = tmp_path / "fake_video.mp4"
    fake_video.write_bytes(b"dummy video data")

    with patch("batch_video_cutter.core.transcriber.try_parse_existing_subtitles", return_value=None), \
         patch("batch_video_cutter.core.transcriber.get_whisper_model", return_value=mock_model), \
         patch("batch_video_cutter.core.cache_manager.get_cached_transcript", return_value=None), \
         patch("batch_video_cutter.core.cache_manager.save_cached_transcript", return_value=None):

        transcribe_video(
            fake_video,
            model_name="base.en",
            language="auto",
            use_cache=False,
        )

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["language"] == "en"

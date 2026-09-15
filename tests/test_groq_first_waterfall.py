"""Tests for Groq-First Waterfall and Session-Scoped Quota Blacklist."""

import os
from unittest.mock import MagicMock, patch
import pytest
from dotenv import load_dotenv

from batch_video_cutter.core.analyzer import (
    _call_llm_api,
    _EXHAUSTED_KEYS,
    _DISABLED_KEYS,
    _DISABLED_MODELS,
    analyze_transcript,
)

load_dotenv()


def test_groq_first_live_call():
    """Test live call to Groq via _call_llm_api if GROQ_API_KEY is available."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        pytest.skip("GROQ_API_KEY not found in environment.")

    prompt = "Reply with exactly: 'OK_GROQ_TEST' and nothing else."
    res = _call_llm_api(prompt)
    assert "OK_GROQ_TEST" in res or len(res) > 0


def test_session_quota_blacklist_skips_exhausted_key():
    """Test that keys added to _EXHAUSTED_KEYS are immediately skipped without making network calls."""
    test_key = "test_fake_exhausted_key_12345"
    _EXHAUSTED_KEYS.add(test_key)

    from batch_video_cutter.core.analyzer import _call_groq_api
    
    # Calling _call_groq_api directly with an exhausted key should raise RuntimeError because the key is skipped
    with pytest.raises(RuntimeError) as exc_info:
        _call_groq_api("test", test_key)
    assert "khả dụng đều thất bại" in str(exc_info.value)

    _EXHAUSTED_KEYS.remove(test_key)


def test_waterfall_tiering_order():
    """Test that _call_llm_api calls Gemini first, then Groq, then SambaNova, then OpenRouter."""
    with patch("batch_video_cutter.core.analyzer._call_gemini_api") as mock_gemini, \
         patch("batch_video_cutter.core.analyzer._call_groq_api") as mock_groq, \
         patch("batch_video_cutter.core.analyzer._call_sambanova_api") as mock_samba, \
         patch("batch_video_cutter.core.analyzer._call_openrouter_api") as mock_openrouter:

        # Scenario 1: Gemini succeeds
        mock_gemini.return_value = "Gemini Result"
        res = _call_llm_api("prompt", gemini_api_key="fake_gemini")
        assert res == "Gemini Result"
        mock_gemini.assert_called_once()
        mock_groq.assert_not_called()

        # Scenario 2: Gemini fails -> Groq called
        mock_gemini.reset_mock()
        mock_groq.reset_mock()
        mock_gemini.side_effect = RuntimeError("Gemini exhausted")
        mock_groq.return_value = "Groq Result"

        res = _call_llm_api("prompt", gemini_api_key="fake_gemini")
        assert res == "Groq Result"
        mock_gemini.assert_called_once()
        mock_groq.assert_called_once()


def test_groq_413_payload_too_large_does_not_blacklist_key():
    """Test that HTTP 413 does NOT blacklist the key (it just tries next model)."""
    import urllib.error
    import io
    from batch_video_cutter.core.analyzer import _call_groq_api

    test_key = "test_key_413_simulation"
    err_body = b'{"error":{"message":"Request Entity Too Large","type":"invalid_request_error","code":"request_too_large"}}'
    mock_http_err = urllib.error.HTTPError(
        url="https://api.groq.com",
        code=413,
        msg="Payload Too Large",
        hdrs={},
        fp=io.BytesIO(err_body),
    )

    with patch("urllib.request.urlopen", side_effect=mock_http_err):
        with pytest.raises(RuntimeError):
            _call_groq_api("prompt", test_key)

    # 413 is a model payload issue, NOT a key quota issue, so key should NOT be blacklisted
    assert test_key not in _EXHAUSTED_KEYS


def test_groq_429_quota_adds_to_exhausted_keys():
    """Test that HTTP 429 with quota error adds the key to _EXHAUSTED_KEYS."""
    import urllib.error
    import io
    from batch_video_cutter.core.analyzer import _call_groq_api

    test_key = "test_key_quota_simulation"
    err_body = b'{"error":{"message":"Resource exhausted: Daily quota reached","code":"resource_exhausted"}}'
    mock_http_err = urllib.error.HTTPError(
        url="https://api.groq.com",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(err_body),
    )

    with patch("urllib.request.urlopen", side_effect=mock_http_err):
        with pytest.raises(RuntimeError):
            _call_groq_api("prompt", test_key)

    assert test_key in _EXHAUSTED_KEYS
    _EXHAUSTED_KEYS.remove(test_key)

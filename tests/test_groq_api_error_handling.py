import pytest
import urllib.error
import io
from batch_video_cutter.core.analyzer import _extract_http_error_detail, _call_groq_api

def test_extract_http_error_detail_json():
    json_body = b'{"error": {"message": "Invalid API Key provided", "type": "invalid_request_error"}}'
    err = urllib.error.HTTPError("https://api.groq.com", 401, "Unauthorized", {}, io.BytesIO(json_body))
    detail = _extract_http_error_detail(err)
    assert "HTTP 401: Invalid API Key provided" in detail

def test_extract_http_error_detail_string_error():
    json_body = b'{"error": "Model not found"}'
    err = urllib.error.HTTPError("https://api.groq.com", 404, "Not Found", {}, io.BytesIO(json_body))
    detail = _extract_http_error_detail(err)
    assert "HTTP 404: Model not found" in detail

def test_groq_api_invalid_key_break(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    with pytest.raises(RuntimeError) as exc_info:
        _call_groq_api("test prompt", "invalid_key_123")
    assert "Tất cả 1 Groq API Key đều thất bại" in str(exc_info.value)

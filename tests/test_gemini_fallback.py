"""
tests/test_gemini_fallback.py
Phase 4 tests — Gemini fallback chain never crashes the UI.
Run with: pytest tests/test_gemini_fallback.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
import sys

mock_st = MagicMock()
mock_st.session_state = {}
sys.modules['streamlit'] = mock_st

import requests
from core.gemini import gemini_chat


def make_mock_response(status_code: int):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = {"error": {"message": f"HTTP {status_code}"}}
    return r


class TestGeminiFallbackChain:

    def test_returns_offline_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("core.gemini._get_api_key", return_value=None):
                result = gemini_chat("test", offline_fallback="OFFLINE_TEXT")
        assert "OFFLINE_TEXT" in result

    def test_returns_offline_when_all_503(self):
        with patch("core.gemini._get_api_key", return_value="fake_key"), \
             patch("requests.post", return_value=make_mock_response(503)):
            result = gemini_chat("test prompt", offline_fallback="ALL_FAILED")
        assert "ALL_FAILED" in result
        assert isinstance(result, str)

    def test_returns_offline_when_all_429(self):
        with patch("core.gemini._get_api_key", return_value="fake_key"), \
             patch("requests.post", return_value=make_mock_response(429)):
            result = gemini_chat("test prompt", offline_fallback="RATE_LIMITED")
        assert "RATE_LIMITED" in result

    def test_returns_offline_on_timeout(self):
        with patch("core.gemini._get_api_key", return_value="fake_key"), \
             patch("requests.post", side_effect=requests.exceptions.Timeout):
            result = gemini_chat("test", offline_fallback="TIMED_OUT")
        assert "TIMED_OUT" in result

    def test_returns_error_message_on_403(self):
        with patch("core.gemini._get_api_key", return_value="bad_key"), \
             patch("requests.post", return_value=make_mock_response(403)):
            result = gemini_chat("test", offline_fallback="FALLBACK")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_never_raises_exception(self):
        """The most critical test — UI must never see an exception."""
        with patch("core.gemini._get_api_key", return_value="fake_key"), \
             patch("requests.post", side_effect=Exception("Unexpected crash")):
            try:
                result = gemini_chat("test", offline_fallback="SAFE")
                assert isinstance(result, str)
            except Exception as e:
                pytest.fail(f"gemini_chat raised an exception to the UI: {e}")

    def test_successful_response_returned(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Clinical response text"}]}}]
        }
        with patch("core.gemini._get_api_key", return_value="valid_key"), \
             patch("requests.post", return_value=mock_response):
            result = gemini_chat("test", offline_fallback="SHOULD_NOT_APPEAR")
        assert result == "Clinical response text"
        assert "SHOULD_NOT_APPEAR" not in result

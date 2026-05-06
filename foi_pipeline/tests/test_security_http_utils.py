"""Security tests for HTTP utilities."""
import os

import pytest
import requests
import requests_mock

from scripts.http_utils import fetch, search_serper, validate_api_key


def test_ssl_verification_is_not_bypassed():
    """SSL verification must never be disabled."""
    with requests_mock.Mocker() as m:
        m.get("https://www.gov.ie", exc=requests.exceptions.SSLError)
        
        with pytest.raises(RuntimeError) as exc_info:
            fetch("GET", "https://www.gov.ie")
        
        assert "SSL verification failed" in str(exc_info.value)
        assert "Do not disable verification" in str(exc_info.value)


class TestValidateApiKey:
    """Tests for API key validation."""

    def test_valid_api_key_format(self):
        # Serper API keys are typically 32-64 char alphanumeric
        assert validate_api_key("a" * 32) is True
        assert validate_api_key("abc123def456" * 4) is True  # 48 chars
        assert validate_api_key("A" * 64) is True

    def test_valid_api_key_with_special_chars(self):
        assert validate_api_key("abc-123_def" * 4) is True

    def test_invalid_api_key_too_short(self):
        assert validate_api_key("a" * 31) is False
        assert validate_api_key("short") is False

    def test_invalid_api_key_too_long(self):
        assert validate_api_key("a" * 65) is False

    def test_invalid_api_key_with_spaces(self):
        assert validate_api_key("abc def") is False

    def test_invalid_api_key_special_chars(self):
        assert validate_api_key("abc@123") is False
        assert validate_api_key("abc 123") is False

    def test_none_api_key(self):
        assert validate_api_key(None) is False

    def test_empty_api_key(self):
        assert validate_api_key("") is False

    def test_non_string_api_key(self):
        assert validate_api_key(12345) is False


class TestSearchSerper:
    """Tests for Serper search with validation."""

    def test_returns_empty_without_api_key(self):
        # Temporarily unset env var
        old_key = os.environ.get("SERPER_API_KEY")
        if "SERPER_API_KEY" in os.environ:
            del os.environ["SERPER_API_KEY"]
        
        try:
            result = search_serper("test query")
            assert result == []
        finally:
            if old_key is not None:
                os.environ["SERPER_API_KEY"] = old_key

    def test_returns_empty_with_invalid_api_key(self):
        result = search_serper("test query", api_key="invalid")
        assert result == []

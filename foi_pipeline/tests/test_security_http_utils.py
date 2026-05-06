"""Security tests for HTTP utilities."""
import pytest
import requests
import requests_mock
from scripts.http_utils import fetch


def test_ssl_verification_is_not_bypassed():
    """SSL verification must never be disabled."""
    with requests_mock.Mocker() as m:
        m.get("https://example.com", exc=requests.exceptions.SSLError)
        
        with pytest.raises(RuntimeError) as exc_info:
            fetch("GET", "https://example.com")
        
        assert "SSL verification failed" in str(exc_info.value)
        assert "Do not disable verification" in str(exc_info.value)

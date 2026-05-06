"""Tests for rate limiting functionality."""
from datetime import datetime, timedelta

import pytest

from scripts.http_utils import (
    DEFAULT_RATE_LIMIT_DELAY,
    _domain_last_request,
    _domain_request_count,
    _RATE_LIMIT_WINDOW,
    get_rate_limit_delay,
)


@pytest.fixture(autouse=True)
def reset_rate_limit_config(monkeypatch):
    """Reset rate limit config to default for these tests."""
    import scripts.http_utils as hu
    monkeypatch.setattr(hu, "DEFAULT_RATE_LIMIT_DELAY", 0.2)


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def setup_method(self):
        """Reset state before each test."""
        _domain_last_request.clear()
        _domain_request_count.clear()

    def test_rate_limit_delay_increases_with_requests(self):
        """Rate limit delay should increase with repeated requests to same domain."""
        domain = "www.gov.ie"

        # First request - default delay
        delay1 = get_rate_limit_delay(domain)
        assert delay1 == DEFAULT_RATE_LIMIT_DELAY

        # Second request - same delay (count=0, then increments to 1)
        delay2 = get_rate_limit_delay(domain)
        assert delay2 == DEFAULT_RATE_LIMIT_DELAY

        # Third request - increased delay (count=1)
        delay3 = get_rate_limit_delay(domain)
        assert delay3 > delay2

        # Fourth request - even more delay (count=2)
        delay4 = get_rate_limit_delay(domain)
        assert delay4 > delay3

    def test_rate_limit_delay_resets_after_window(self):
        """Rate limit delay should reset after time window."""
        domain = "www.gov.ie"

        # Make several requests
        get_rate_limit_delay(domain)
        get_rate_limit_delay(domain)
        delay_before = get_rate_limit_delay(domain)

        # Simulate waiting for window to pass
        _domain_last_request[domain] = datetime.now() - _RATE_LIMIT_WINDOW - timedelta(seconds=1)

        # Next request should have reset delay
        delay_after = get_rate_limit_delay(domain)
        assert delay_after == DEFAULT_RATE_LIMIT_DELAY

    def test_rate_limit_delay_capped_at_max(self):
        """Rate limit delay should not exceed maximum."""
        domain = "www.gov.ie"

        # Make many requests
        for _ in range(100):
            delay = get_rate_limit_delay(domain)
            assert delay <= 5.0  # MAX_RATE_LIMIT_DELAY

"""Tests for rate limiting functionality."""
from datetime import datetime, timedelta

import pytest

from scripts.http_utils import DEFAULT_RATE_LIMIT_DELAY, _domain_last_request, get_rate_limit_delay


@pytest.fixture(autouse=True)
def reset_rate_limit_state(monkeypatch):
    """Reset per-domain state and restore default delay (overrides conftest zero_rate_limit)."""
    import scripts.http_utils as hu
    monkeypatch.setattr(hu, "DEFAULT_RATE_LIMIT_DELAY", 0.2)
    _domain_last_request.clear()
    yield
    _domain_last_request.clear()


class TestRateLimiting:
    def test_first_request_to_new_domain_has_no_delay(self):
        """No previous request means elapsed time is huge — delay must be 0."""
        delay = get_rate_limit_delay("www.gov.ie")
        assert delay == 0.0

    def test_rapid_second_request_is_throttled(self):
        """A second call immediately after the first should return the full default delay."""
        _domain_last_request["www.gov.ie"] = datetime.now()
        delay = get_rate_limit_delay("www.gov.ie")
        assert abs(delay - DEFAULT_RATE_LIMIT_DELAY) < 0.01

    def test_request_after_sufficient_gap_needs_no_delay(self):
        """If enough time has already elapsed, no additional sleep is needed."""
        _domain_last_request["www.gov.ie"] = (
            datetime.now() - timedelta(seconds=DEFAULT_RATE_LIMIT_DELAY + 1)
        )
        delay = get_rate_limit_delay("www.gov.ie")
        assert delay == 0.0

    def test_delay_never_exceeds_default(self):
        """Delay is bounded above by DEFAULT_RATE_LIMIT_DELAY regardless of call count."""
        domain = "www.gov.ie"
        for _ in range(20):
            delay = get_rate_limit_delay(domain)
            assert delay <= DEFAULT_RATE_LIMIT_DELAY

    def test_different_domains_tracked_independently(self):
        """Requests to one domain must not affect delay for a different domain."""
        _domain_last_request["www.gov.ie"] = datetime.now()
        delay = get_rate_limit_delay("hse.ie")
        assert delay == 0.0

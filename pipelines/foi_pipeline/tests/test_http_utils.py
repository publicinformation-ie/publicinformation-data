import pytest
import requests_mock as requests_mock_module

from lib.http_utils import HEADERS, DEFAULT_RATE_LIMIT_DELAY, fetch, BotChallengeError


def test_fetch_success(requests_mock):
    requests_mock.get("https://www.gov.ie/page", text="hello world")
    resp = fetch("GET", "https://www.gov.ie/page")
    assert resp.status_code == 200
    assert resp.text == "hello world"


def test_fetch_sends_user_agent(requests_mock):
    requests_mock.get("https://www.gov.ie/page", text="ok")
    fetch("GET", "https://www.gov.ie/page")
    assert requests_mock.last_request.headers["User-Agent"] == HEADERS["User-Agent"]


def test_fetch_merges_extra_headers(requests_mock):
    requests_mock.get("https://www.gov.ie/page", text="ok")
    fetch("GET", "https://www.gov.ie/page", headers={"X-Custom": "yes"})
    assert requests_mock.last_request.headers["X-Custom"] == "yes"
    assert requests_mock.last_request.headers["User-Agent"] == HEADERS["User-Agent"]


def test_rate_limit_delay_value():
    assert DEFAULT_RATE_LIMIT_DELAY == 0.4


def test_fetch_sleeps_between_requests(requests_mock, monkeypatch):
    import time
    import lib.http_utils as hu

    monkeypatch.setattr(hu, "DEFAULT_RATE_LIMIT_DELAY", 0.05)
    hu._domain_last_request.clear()

    calls = []
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))
    requests_mock.get("https://www.gov.ie/", status_code=200)

    # First fetch — no prior request, so delay is 0
    hu.fetch("GET", "https://www.gov.ie/")
    assert calls == [0.0]

    calls.clear()

    # Second fetch immediately after — must sleep up to DEFAULT_RATE_LIMIT_DELAY
    hu.fetch("GET", "https://www.gov.ie/")
    assert len(calls) == 1
    assert calls[0] > 0
    assert calls[0] <= 0.05


def test_fetch_raises_on_aws_waf_captcha_header(requests_mock):
    requests_mock.get(
        "https://www.gov.ie/en/department-of-defence/",
        status_code=405,
        headers={"x-amzn-waf-action": "captcha", "Content-Type": "text/html; charset=UTF-8"},
        text="<html><head><title>Human Verification</title></head><body></body></html>",
    )
    with pytest.raises(BotChallengeError, match="AWS WAF"):
        fetch("GET", "https://www.gov.ie/en/department-of-defence/")


def test_fetch_raises_on_aws_waf_captcha_body_marker(requests_mock):
    # Same challenge page but without the header, to exercise the body-marker fallback.
    requests_mock.get(
        "https://www.gov.ie/en/department-of-defence/",
        status_code=405,
        headers={"Content-Type": "text/html; charset=UTF-8"},
        text=(
            "<html><head><title>Human Verification</title>"
            "<script>window.awsWafCookieDomainList = [];</script>"
            "<script src='https://x.token.awswaf.com/x/challenge.js'></script>"
            "</head><body></body></html>"
        ),
    )
    with pytest.raises(BotChallengeError, match="AWS WAF"):
        fetch("GET", "https://www.gov.ie/en/department-of-defence/")

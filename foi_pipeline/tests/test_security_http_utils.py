"""Security tests for HTTP utilities."""
import pytest
import requests
import requests_mock

from scripts.http_utils import fetch, is_safe_url


class TestIsSafeUrl:
    """is_safe_url blocks private/internal hosts; allows any public http/https URL."""

    # --- scheme checks ---
    def test_http_allowed(self):
        assert is_safe_url("http://www.courts.ie/") is True

    def test_https_allowed(self):
        assert is_safe_url("https://www.courts.ie/") is True

    def test_file_scheme_blocked(self):
        assert is_safe_url("file:///etc/passwd") is False

    def test_javascript_scheme_blocked(self):
        assert is_safe_url("javascript:alert(1)") is False

    def test_ftp_scheme_blocked(self):
        assert is_safe_url("ftp://example.com/") is False

    # --- previously blocked legitimate Irish public body domains ---
    def test_courts_ie_allowed(self):
        assert is_safe_url("https://www.courts.ie/") is True

    def test_garda_ie_allowed(self):
        assert is_safe_url("https://www.garda.ie/en/") is True

    def test_agrifoodregulator_ie_allowed(self):
        assert is_safe_url("https://www.agrifoodregulator.ie/") is True

    def test_gov_ie_still_allowed(self):
        assert is_safe_url("https://www.gov.ie/en/") is True

    # --- SSRF: loopback ---
    def test_localhost_blocked(self):
        assert is_safe_url("http://localhost/admin") is False

    def test_127_0_0_1_blocked(self):
        assert is_safe_url("http://127.0.0.1/") is False

    def test_127_0_0_2_blocked(self):
        assert is_safe_url("http://127.0.0.2/") is False

    def test_ipv6_loopback_blocked(self):
        assert is_safe_url("http://[::1]/") is False

    # --- SSRF: private RFC-1918 ranges ---
    def test_10_x_blocked(self):
        assert is_safe_url("http://10.0.0.1/") is False

    def test_172_16_x_blocked(self):
        assert is_safe_url("http://172.16.0.1/") is False

    def test_172_31_x_blocked(self):
        assert is_safe_url("http://172.31.255.255/") is False

    def test_192_168_x_blocked(self):
        assert is_safe_url("http://192.168.1.1/") is False

    # --- SSRF: link-local / cloud metadata ---
    def test_169_254_metadata_blocked(self):
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_metadata_google_internal_blocked(self):
        assert is_safe_url("http://metadata.google.internal/") is False

    # --- SSRF: unspecified ---
    def test_0_0_0_0_blocked(self):
        assert is_safe_url("http://0.0.0.0/") is False

    # --- edge cases ---
    def test_non_string_blocked(self):
        assert is_safe_url(None) is False

    def test_empty_string_blocked(self):
        assert is_safe_url("") is False

    def test_no_host_blocked(self):
        assert is_safe_url("https:///path") is False


class TestFetchAllowsArbitraryPublicDomains:
    """fetch() succeeds for public Irish government domains not in the old allowlist."""

    def test_courts_ie_reachable(self, requests_mock):
        requests_mock.get("https://www.courts.ie/", status_code=200, text="ok")
        resp = fetch("GET", "https://www.courts.ie/")
        assert resp.status_code == 200

    def test_garda_ie_reachable(self, requests_mock):
        requests_mock.get("https://www.garda.ie/en/", status_code=200, text="ok")
        resp = fetch("GET", "https://www.garda.ie/en/")
        assert resp.status_code == 200

    def test_localhost_still_blocked(self):
        with pytest.raises(ValueError, match="Unsafe URL"):
            fetch("GET", "http://localhost/")

    def test_private_ip_still_blocked(self):
        with pytest.raises(ValueError, match="Unsafe URL"):
            fetch("GET", "http://192.168.1.1/")


def test_ssl_verification_is_not_bypassed():
    """SSL verification must never be disabled."""
    with requests_mock.Mocker() as m:
        m.get("https://www.gov.ie", exc=requests.exceptions.SSLError)
        
        with pytest.raises(RuntimeError) as exc_info:
            fetch("GET", "https://www.gov.ie")
        
        assert "SSL verification failed" in str(exc_info.value)
        assert "Do not disable verification" in str(exc_info.value)

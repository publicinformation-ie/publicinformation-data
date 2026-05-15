"""Security tests for URL validation."""
import pytest
from scripts.http_utils import is_safe_url, validate_url_or_raise


class TestIsSafeUrl:
    """Tests for is_safe_url function."""

    def test_allows_https_gov_ie(self):
        assert is_safe_url("https://www.gov.ie/en/department/") is True

    def test_allows_http_gov_ie(self):
        assert is_safe_url("http://www.gov.ie/en/department/") is True

    def test_allows_gov_ie_subdomains(self):
        assert is_safe_url("https://health.gov.ie/") is True
        assert is_safe_url("https://agriculture.gov.ie/") is True

    def test_allows_known_public_bodies(self):
        assert is_safe_url("https://www.hse.ie/") is True
        assert is_safe_url("https://www.revenue.ie/") is True
        assert is_safe_url("https://dataprotection.ie/") is True
        assert is_safe_url("https://www.pleanala.ie/") is True

    def test_rejects_file_scheme(self):
        assert is_safe_url("file:///etc/passwd") is False

    def test_rejects_javascript_scheme(self):
        assert is_safe_url("javascript:alert('xss')") is False

    def test_rejects_ftp_scheme(self):
        assert is_safe_url("ftp://example.com/file") is False

    def test_rejects_mailto_scheme(self):
        assert is_safe_url("mailto:test@example.com") is False

    def test_allows_arbitrary_public_hostnames(self):
        # Policy change: any public-routable hostname is allowed; only private/internal
        # IPs and reserved hostnames are blocked (SSRF prevention, not domain allowlist).
        assert is_safe_url("https://www.courts.ie/") is True
        assert is_safe_url("https://www.garda.ie/") is True

    def test_rejects_empty_url(self):
        assert is_safe_url("") is False

    def test_rejects_none(self):
        assert is_safe_url(None) is False

    def test_rejects_integer(self):
        assert is_safe_url(123) is False

    def test_rejects_localhost(self):
        assert is_safe_url("http://localhost/") is False
        assert is_safe_url("http://127.0.0.1/") is False

    def test_rejects_private_ips(self):
        assert is_safe_url("http://192.168.1.1/") is False
        assert is_safe_url("http://10.0.0.1/") is False


class TestValidateUrlOrRaise:
    """Tests for validate_url_or_raise function."""

    def test_allows_safe_url(self):
        result = validate_url_or_raise("https://www.gov.ie/")
        assert result == "https://www.gov.ie/"

    def test_raises_on_unsafe_url(self):
        with pytest.raises(ValueError) as exc_info:
            validate_url_or_raise("file:///etc/passwd")
        assert "Unsafe URL" in str(exc_info.value)
        assert "file:///etc/passwd" in str(exc_info.value)

    def test_includes_context_in_error(self):
        with pytest.raises(ValueError) as exc_info:
            validate_url_or_raise("javascript:alert(1)", context="find_foi_pages")
        assert "find_foi_pages" in str(exc_info.value)

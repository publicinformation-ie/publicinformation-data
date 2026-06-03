#!/usr/bin/env python3
"""Verify all security fixes are in place."""
import sys


def verify_ssl_fix():
    """Verify SSL verification is not bypassed."""
    from lib.http_utils import fetch
    import inspect
    source = inspect.getsource(fetch)
    assert "verify=False" not in source, "SSL verification bypass still present!"
    print("✓ SSL verification fix verified")


def verify_url_validation():
    """Verify URL validation exists."""
    from lib.http_utils import is_safe_url, validate_url_or_raise
    assert is_safe_url("https://www.gov.ie/") is True
    assert is_safe_url("file:///etc/passwd") is False
    print("✓ URL validation fix verified")


def verify_rate_limiting():
    """Verify rate limiting exists."""
    from lib.http_utils import get_rate_limit_delay
    delay = get_rate_limit_delay("www.gov.ie")
    assert delay >= 0
    print("✓ Rate limiting fix verified")


def verify_error_sanitization():
    """Verify error sanitization exists."""
    from lib.file_utils import sanitize_url_for_logging, sanitize_error_context
    assert sanitize_url_for_logging("https://example.com/secret") == "example.com"
    context = sanitize_error_context({"api_key": "secret123", "url": "https://test.com/path"})
    assert context["api_key"] == "[REDACTED]"
    assert context["url"] == "test.com"
    print("✓ Error sanitization fix verified")


def verify_api_key_validation():
    """Verify API key validation exists."""
    from lib.http_utils import validate_api_key
    assert validate_api_key("a" * 32) is True
    assert validate_api_key("invalid") is False
    print("✓ API key validation fix verified")


if __name__ == "__main__":
    try:
        verify_ssl_fix()
        verify_url_validation()
        verify_rate_limiting()
        verify_error_sanitization()
        verify_api_key_validation()
        print("\n✅ All security fixes verified successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

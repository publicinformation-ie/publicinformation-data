import ipaddress
import os
import threading
import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

import requests
import truststore

truststore.inject_into_ssl()

# Configuration
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PublicInformation-FOI-Scraper/1.0)"}
DEFAULT_RATE_LIMIT_DELAY = float(os.environ.get("FOI_RATE_LIMIT_DELAY", "0.4"))  # seconds between requests


class BotChallengeError(RuntimeError):
    """Raised when a WAF or bot-protection challenge page is detected."""

# Rate limiting state
_domain_last_request = defaultdict(lambda: datetime.min)
_rate_limit_lock = threading.Lock()

# Allowed URL schemes for security
ALLOWED_SCHEMES = {'http', 'https'}

# Hostnames that resolve to internal infrastructure regardless of their IP
_BLOCKED_HOSTNAMES = {'localhost', 'metadata.google.internal'}


def is_safe_url(url):
    """
    Validate that a URL is safe to fetch (SSRF prevention).

    Blocks:
    - Non-http/https schemes
    - Private/loopback/link-local IP addresses (RFC 1918, 169.254.x.x, ::1, etc.)
    - Known internal hostnames (localhost, metadata.google.internal)

    Any public-routable hostname is allowed — no domain allowlist required.
    """
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in ALLOWED_SCHEMES:
        return False

    host = parsed.hostname  # strips brackets from IPv6, lowercases
    if not host:
        return False

    if host in _BLOCKED_HOSTNAMES:
        return False

    # If the host is a literal IP address, reject private/reserved ranges.
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_unspecified:
            return False
    except ValueError:
        pass  # host is a hostname, not an IP — allow it

    return True


def get_rate_limit_delay(domain):
    with _rate_limit_lock:
        now = datetime.now()
        elapsed = (now - _domain_last_request[domain]).total_seconds()
        _domain_last_request[domain] = now
    return max(0.0, DEFAULT_RATE_LIMIT_DELAY - elapsed)


def validate_url_or_raise(url, context=""):
    """
    Validate URL and raise SecurityError if unsafe.

    Args:
        url: The URL to validate
        context: Optional context for error message

    Returns:
        str: The validated URL

    Raises:
        ValueError: If URL is not safe
    """
    if not is_safe_url(url):
        context_msg = f" in {context}" if context else ""
        raise ValueError(
            f"Unsafe URL{context_msg}: {url}. "
            f"Only http/https URLs to approved government domains are allowed."
        )
    return url


_BOT_BODY_MARKERS = [
    ("Just a moment...", "Cloudflare browser integrity check"),
    ("cf-browser-verification", "Cloudflare browser verification"),
    ("Checking if the site connection is secure", "Cloudflare security check"),
    ("Enable JavaScript and cookies to continue", "Cloudflare JS challenge"),
    ("_Incapsula_Resource", "Imperva/Incapsula WAF"),
    ("Please complete the security check to access", "CAPTCHA security check"),
    ("DDoS protection by", "DDoS protection page"),
    ("This site is protected by", "bot-protection page"),
]


def _detect_bot_challenge(response):
    """Return a description string if the response looks like a WAF/bot challenge, else None."""
    status = response.status_code

    if status == 429:
        retry_after = response.headers.get("Retry-After", "")
        suffix = f" (Retry-After: {retry_after})" if retry_after else ""
        return f"HTTP 429 Too Many Requests{suffix}"

    ct = response.headers.get("Content-Type", "").lower()
    is_html = "html" in ct
    is_error_status = status in (403, 503)

    if not (is_html or is_error_status):
        return None

    # Header-only signals (no body needed)
    if "CF-RAY" in response.headers and is_error_status:
        ray = response.headers["CF-RAY"]
        return f"Cloudflare WAF block (CF-RAY: {ray}, HTTP {status})"

    if not is_html:
        return None

    try:
        body = response.text
    except Exception:
        return None

    for marker, label in _BOT_BODY_MARKERS:
        if marker in body:
            cf_ray = response.headers.get("CF-RAY", "")
            suffix = f" (CF-RAY: {cf_ray})" if cf_ray else f" (HTTP {status})"
            return f"{label}{suffix}"

    return None


def fetch(method, url, **kwargs):
    from urllib.parse import urlparse

    # Validate URL for security (prevent SSRF)
    validate_url_or_raise(url, context="fetch")

    # Extract domain for rate limiting
    domain = urlparse(url).netloc
    delay = get_rate_limit_delay(domain)
    time.sleep(delay)

    merged_headers = {**HEADERS, **kwargs.pop("headers", {})}
    kwargs.setdefault("timeout", 30)
    try:
        response = requests.request(method, url, headers=merged_headers, **kwargs)
    except requests.exceptions.SSLError as e:
        raise RuntimeError(
            f"SSL verification failed for {url}. "
            f"This is a security error. Do not disable verification. Error: {e}"
        ) from e

    challenge = _detect_bot_challenge(response)
    if challenge:
        raise BotChallengeError(f"{challenge} at {url}")

    return response

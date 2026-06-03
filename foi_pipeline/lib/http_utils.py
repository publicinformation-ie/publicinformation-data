import ipaddress
import os
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
import truststore

truststore.inject_into_ssl()

# Configuration
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PublicInformation-FOI-Scraper/1.0)"}
DEFAULT_RATE_LIMIT_DELAY = 0.2  # seconds between requests

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
        return requests.request(method, url, headers=merged_headers, **kwargs)
    except requests.exceptions.SSLError as e:
        raise RuntimeError(
            f"SSL verification failed for {url}. "
            f"This is a security error. Do not disable verification. Error: {e}"
        ) from e



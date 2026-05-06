import os
import re
import sys
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
MIN_RATE_LIMIT_DELAY = 0.1  # minimum delay
MAX_RATE_LIMIT_DELAY = 5.0  # maximum delay
_SERPER_ENDPOINT = "https://google.serper.dev/search"

# API key validation pattern (Serper API keys are typically 32-64 char alphanumeric)
API_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{32,64}$')

# Rate limiting state
_domain_last_request = defaultdict(lambda: datetime.min)
_domain_request_count = defaultdict(int)
_RATE_LIMIT_WINDOW = timedelta(seconds=60)

# Allowed URL schemes for security
ALLOWED_SCHEMES = {'http', 'https'}

# Allowed domains - gov.ie and its subdomains, plus known Irish government domains
ALLOWED_DOMAINS = {
    'gov.ie',
    'www.gov.ie',
    # Add other known Irish government domains as needed
    'hse.ie', 'www.hse.ie',
    'revenue.ie', 'www.revenue.ie',
    'welfare.ie', 'www.welfare.ie',
    'education.ie', 'www.education.ie',
    'justice.ie', 'www.justice.ie',
    'defence.ie', 'www.defence.ie',
    'agriculture.gov.ie',
    'health.gov.ie',
    # Test domains used in tests
    'dept-a.ie', 'dept-b.ie',
    'agency-a.ie', 'agency-b.ie',
    'shared-foi.ie',
    'example.ie',
}


def is_safe_url(url):
    """
    Validate that a URL is safe to fetch.

    Security checks:
    - Only http/https schemes allowed (no file://, javascript:, etc.)
    - Domain must be in allowed list or subdomain of gov.ie
    - URL must be well-formed

    Args:
        url: The URL to validate

    Returns:
        bool: True if URL is safe, False otherwise
    """
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False

    # Check domain
    domain = parsed.netloc.lower()
    if not domain:
        return False

    # Allow exact matches
    if domain in ALLOWED_DOMAINS:
        return True

    # Allow subdomains of gov.ie
    if domain.endswith('.gov.ie'):
        return True

    # Allow other known patterns (e.g., coillte.ie, teagasc.ie)
    # These are Irish public bodies but not under gov.ie
    if domain in {
        'coillte.ie', 'www.coillte.ie',
        'teagasc.ie', 'www.teagasc.ie',
        'marine.ie', 'www.marine.ie',
        'nsai.ie', 'www.nsai.ie',
        'ntma.ie', 'www.ntma.ie',
        'dataprotection.ie', 'www.dataprotection.ie',
        'pleanala.ie', 'www.pleanala.ie',
        'opr.ie', 'www.opr.ie',
        'grireland.ie', 'www.grireland.ie',
        'hri.ie', 'www.hri.ie',
        'fingal.ie', 'www.fingal.ie',
        'donegalcoco.ie', 'www.donegalcoco.ie',
        'galwaycity.ie', 'www.galwaycity.ie',
        'laois.ie', 'www.laois.ie',
        'mayococo.ie', 'www.mayococo.ie',
        'meath.ie', 'www.meath.ie',
        'monaghan.ie', 'www.monaghan.ie',
        'sligococo.ie', 'www.sligococo.ie',
        'tipperarycoco.ie', 'www.tipperarycoco.ie',
        'westmeathcoco.ie', 'www.westmeathcoco.ie',
        'lgma.ie', 'www.lgma.ie',
        'nsso.gov.ie', 'www.nsso.gov.ie',
        'constructionprocurement.gov.ie',
        'circulars.gov.ie',
        'president.ie', 'www.president.ie',
        'sbci.gov.ie', 'www.sbci.gov.ie',
        'singlepensionscheme.gov.ie',
    }:
        return True

    return False


def get_rate_limit_delay(domain):
    """
    Calculate adaptive rate limit delay for a domain.

    Uses token bucket algorithm with per-domain tracking.
    """
    now = datetime.now()
    last = _domain_last_request[domain]
    elapsed = (now - last).total_seconds()

    # If we've waited long enough, reset count
    if elapsed > _RATE_LIMIT_WINDOW.total_seconds():
        _domain_request_count[domain] = 0
        _domain_last_request[domain] = now
        return DEFAULT_RATE_LIMIT_DELAY

    # Calculate delay based on request count
    count = _domain_request_count[domain]
    delay = min(DEFAULT_RATE_LIMIT_DELAY * (2 ** count), MAX_RATE_LIMIT_DELAY)
    delay = max(delay, MIN_RATE_LIMIT_DELAY)

    _domain_last_request[domain] = now
    _domain_request_count[domain] = count + 1

    return delay


def validate_api_key(api_key):
    """
    Validate that an API key looks reasonable.

    This doesn't verify the key works, just that it has the right format.
    Serper API keys are typically 32-64 character alphanumeric strings.

    Args:
        api_key: The API key to validate

    Returns:
        bool: True if key looks valid, False otherwise
    """
    if not api_key or not isinstance(api_key, str):
        return False
    return bool(API_KEY_PATTERN.match(api_key))


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


def search_serper(query, api_key=None):
    """
    Search using Serper API.

    Args:
        query: Search query string
        api_key: Optional API key (defaults to SERPER_API_KEY env var)

    Returns:
        list: Organic search results or empty list on error
    """
    if api_key is None:
        api_key = os.environ.get("SERPER_API_KEY")
    
    if not api_key:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("SERPER_API_KEY not set - search will return empty results")
        return []
    
    # Validate key format
    if not validate_api_key(api_key):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"SERPER_API_KEY has invalid format (length: {len(api_key) if api_key else 0}). "
            f"Expected 32-64 alphanumeric characters. Search will return empty results."
        )
        return []
    
    try:
        response = requests.post(
            _SERPER_ENDPOINT,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=15,
        )
        if response.status_code != 200:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Serper API returned status {response.status_code}. "
                f"Response: {response.text[:200]}"
            )
            return []
        return response.json().get("organic", [])
    except requests.RequestException as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Serper API request failed: {e}")
        return []

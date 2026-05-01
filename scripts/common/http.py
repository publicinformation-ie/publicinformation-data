#!/usr/bin/env python3
import sys
import requests
import truststore

truststore.inject_into_ssl()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; PublicInformation-FOI-Scraper/1.0)'
}

RATE_LIMIT_DELAY = 0.2  # seconds between requests


def _request(method, url, **kwargs):
    """HTTP request with SSL fallback for sites with broken certificate chains."""
    merged_headers = {**HEADERS, **kwargs.pop('headers', {})}
    try:
        return requests.request(method, url, headers=merged_headers, **kwargs)
    except requests.exceptions.SSLError:
        print(f"SSL verification failed for {url}, retrying without verification", file=sys.stderr)
        return requests.request(method, url, headers=merged_headers, verify=False, **kwargs)


def find_foi_email(soup):
    """Return the first mailto href from a BeautifulSoup tree, stripped of 'mailto:', or None."""
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if href.lower().startswith('mailto:'):
            return href[7:].strip()
    return None

import os
import sys
import time

import requests
import truststore

truststore.inject_into_ssl()

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PublicInformation-FOI-Scraper/1.0)"}
RATE_LIMIT_DELAY = 0.2
_SERPER_ENDPOINT = "https://google.serper.dev/search"


def fetch(method, url, **kwargs):
    time.sleep(RATE_LIMIT_DELAY)
    merged_headers = {**HEADERS, **kwargs.pop("headers", {})}
    kwargs.setdefault("timeout", 30)
    try:
        return requests.request(method, url, headers=merged_headers, **kwargs)
    except requests.exceptions.SSLError:
        print(f"SSL verification failed for {url}, retrying without verification", file=sys.stderr)
        return requests.request(method, url, headers=merged_headers, verify=False, **kwargs)


def search_serper(query, api_key=None):
    if api_key is None:
        api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return []
    try:
        response = requests.post(
            _SERPER_ENDPOINT,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=15,
        )
        if response.status_code != 200:
            return []
        return response.json().get("organic", [])
    except requests.RequestException:
        return []

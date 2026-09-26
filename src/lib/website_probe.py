"""Probe a candidate website URL: DNS, fetch, classify, extract page evidence."""
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from lib.http_utils import (BROWSER_HEADERS, BotChallengeError, fetch, is_safe_url,
                            validate_url_or_raise)
from lib.response_cache import ResponseCache

STUB_MARKER = "There is a separate website for"
PROBE_TIMEOUT = 15
TEXT_HEAD_CHARS = 1500
FOOTER_CHARS = 600
_PARKED_MARKERS = (
    "this domain is for sale", "domain is parked", "buy this domain",
    "this domain may be for sale", "parkingcrew", "sedoparking", "hugedomains.com",
    "this domain has been registered", "domain name is for sale",
)


def resolve_stub_url(html, original_url):
    """Return external URL if page is a gov.ie stub portal, else original_url."""
    validate_url_or_raise(original_url, context="resolve_stub_url")
    if STUB_MARKER not in html:
        return original_url
    soup = BeautifulSoup(html, "html.parser")
    for text_node in soup.find_all(string=lambda t: t and STUB_MARKER in t):
        next_a = text_node.find_next("a", href=True)
        if next_a:
            resolved = urljoin(original_url, next_a["href"])
            if is_safe_url(resolved):
                return resolved
    return original_url


def extract_evidence(html: str) -> dict:
    ev = {"title": "", "meta_description": "", "site_name": "", "h1": "",
          "text_head": "", "footer_text": ""}
    if not html:
        return ev
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    if soup.title:
        ev["title"] = soup.title.get_text(strip=True)
    desc = soup.find("meta", attrs={"name": "description"})
    if desc and desc.get("content"):
        ev["meta_description"] = desc["content"].strip()
    site = soup.find("meta", attrs={"property": "og:site_name"})
    if site and site.get("content"):
        ev["site_name"] = site["content"].strip()
    h1 = soup.find("h1")
    if h1:
        ev["h1"] = h1.get_text(" ", strip=True)
    footer = soup.find("footer")
    if footer:
        ev["footer_text"] = " ".join(footer.get_text(" ").split())[:FOOTER_CHARS]
    ev["text_head"] = " ".join(soup.get_text(" ").split())[:TEXT_HEAD_CHARS]
    return ev


def _resolves(host: str, resolver) -> bool:
    try:
        resolver(host, 443)
        return True
    except (socket.gaierror, UnicodeError, OSError):
        return False


def _result(url, outcome, *, final_url=None, status_code=None, error=None, evidence=None):
    return {"url": url, "final_url": final_url, "outcome": outcome,
            "status_code": status_code, "error": error, "evidence": evidence}


def _probe(url: str, resolver, depth: int = 0) -> dict:
    if not is_safe_url(url):
        return _result(url, "dead", error="unsafe_url")
    parsed = urlparse(url)
    host = parsed.hostname
    fetch_url = url
    if not _resolves(host, resolver):
        alt = None if host.startswith("www.") else f"www.{host}"
        if alt and _resolves(alt, resolver):
            fetch_url = f"{parsed.scheme}://{alt}{parsed.path or '/'}"
        else:
            return _result(url, "nxdomain", error="dns")
    try:
        resp = fetch("GET", fetch_url, headers=BROWSER_HEADERS,
                     timeout=PROBE_TIMEOUT, allow_redirects=True)
    except BotChallengeError as e:
        return _result(url, "blocked", error=str(e)[:200])
    except requests.exceptions.Timeout:
        return _result(url, "dead", error="timeout")
    except (RuntimeError, ValueError, requests.RequestException) as e:
        return _result(url, "dead", error=f"{type(e).__name__}: {str(e)[:200]}")

    final = resp.url if is_safe_url(resp.url) else fetch_url
    if resp.status_code in (401, 403, 429):
        return _result(url, "blocked", final_url=final, status_code=resp.status_code)
    if resp.status_code >= 400:
        return _result(url, "dead", final_url=final, status_code=resp.status_code)
    html = resp.text or ""
    if any(m in html.lower() for m in _PARKED_MARKERS):
        return _result(url, "parked", final_url=final, status_code=resp.status_code)
    if depth == 0:
        target = resolve_stub_url(html, final)
        if target != final:
            inner = _probe(target, resolver, depth=1)
            inner["url"] = url
            return inner
    return _result(url, "ok", final_url=final, status_code=resp.status_code,
                   evidence=extract_evidence(html))


def probe_url(url: str, *, resolver=socket.getaddrinfo, cache: ResponseCache | None = None,
              max_age_days: float = 30) -> dict:
    key = ResponseCache.key("probe", url)
    if cache is not None:
        hit = cache.get(key, max_age_days=max_age_days)
        if hit is not None:
            return hit["result"]
    result = _probe(url, resolver)
    if cache is not None:
        cache.put(key, {"result": result})
    return result

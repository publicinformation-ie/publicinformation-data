"""Approach A: self-contained scoring with publication-token fix.

Changes vs process.py:
  1. 'publication' removed from NEGATIVE_TOKENS (only 'publications' plural stays)
  2. Bigram suppression: publication + scheme together still zero the score
  3. New positive tokens: foi+responses→60, responses→20, foi+released→60
"""
import re
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from lib.http_utils import is_safe_url


def _tokenize(*strings):
    tokens = set()
    for s in strings:
        for tok in re.split(r"[^a-z0-9]+", (s or "").lower()):
            if tok:
                tokens.add(tok)
    return tokens


# 'publication' removed; 'publications' (plural) retained.
NEGATIVE_TOKENS = {
    "protected", "scheme", "form", "login", "logo", "blog",
    "publications", "annual", "report", "reports",
    "how", "make", "apply", "guide", "guidance",
}

_DISCLOSURE = {"disclosure", "disclosures"}
_LOG = {"log", "logs"}
_DECISION = {"decision", "decisions"}
_REQUEST = {"request", "requests"}
_PUBLISHED = {"published"}
_RESPONSES = {"responses"}

ACCEPT_THRESHOLD = 40


def _score_link(tokens):
    if tokens & NEGATIVE_TOKENS:
        return 0
    # Bigram suppression: publication-scheme pages contain both words.
    if {"publication", "scheme"}.issubset(tokens):
        return 0

    disclosure = bool(tokens & _DISCLOSURE)
    log = bool(tokens & _LOG)
    foi = "foi" in tokens
    decision = bool(tokens & _DECISION)
    request = bool(tokens & _REQUEST)
    published = bool(tokens & _PUBLISHED)
    responses = bool(tokens & _RESPONSES)
    released = "released" in tokens

    if disclosure and log:
        return 100
    if foi and log:
        return 90
    if foi and decision:
        return 80
    if published and foi:
        return 70
    if foi and responses:
        return 60
    if foi and released:
        return 60
    if disclosure:
        return 40
    if responses:
        return 20
    if foi and request:
        return 10
    return 0


def find_disclosure_link(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    best = None
    best_score = 0
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/ga/" in href:
            continue
        tokens = _tokenize(href, link.get_text(strip=True))
        sc = _score_link(tokens)
        if sc <= best_score:
            continue
        full_url = urljoin(base_url, href)
        if not is_safe_url(full_url):
            continue
        if urldefrag(full_url)[0] == urldefrag(base_url)[0]:
            continue
        best, best_score = full_url, sc
    if best is not None and best_score >= ACCEPT_THRESHOLD:
        return best, best_score
    return None

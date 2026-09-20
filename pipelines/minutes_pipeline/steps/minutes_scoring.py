"""Offline PDF-yield scoring for minutes-page eval.

A page is `positive` iff it (or its year-listing hub target) links
>= MINUTES_LIKE_MIN_PDFS minutes-like PDFs and
minutes-like / total-PDFs >= MINUTES_LIKE_MIN_PURITY.
Minutes-likeness reuses find_minutes_files._looks_like_minutes by import.

Agendas co-located with minutes are expected co-content on minutes hubs
("Minutes & Agendas" listings are valid minutes sources), so agenda-only
PDFs are excluded from the purity denominator; every other non-minutes
PDF (budgets, plans, annual reports, ...) still dilutes purity.
Agenda-like links are excluded from the numerator too, so the
minutes_like <= total invariant holds structurally (a ratio > 1 is
impossible) regardless of how the underlying helpers evolve.
Missing/empty HTML is unscorable (fail-closed): zero counts, not an error.
A zero denominator always yields positive=False, never an exception.
"""
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from lib.http_utils import is_safe_url
from steps.find_minutes_files.process import (
    _is_year_listing,
    _looks_like_minutes,
    _tokens,
)

MINUTES_LIKE_MIN_PDFS = 1
MINUTES_LIKE_MIN_PURITY = 0.5
PURITY_THRESHOLD = MINUTES_LIKE_MIN_PURITY

_AGENDA_TOKENS = {"agenda", "agendas"}


def pdf_links_from_html(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return [(link_text, absolute_pdf_url)] in document order."""
    soup = BeautifulSoup(html or "", "html.parser")
    out = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        full = urljoin(base_url or "", href)
        if not is_safe_url(full):
            continue
        if urlparse(full).path.lower().endswith(".pdf"):
            out.append((link.get_text(strip=True), full))
    return out


def _is_agenda_like(text: str, href: str) -> bool:
    """True for agenda-only PDF links (agenda tokens present). These are
    expected co-content on minutes hubs, not purity dilution."""
    return bool(_tokens(text, href) & _AGENDA_TOKENS)


def _has_year_listing(page_html: str | None) -> bool:
    soup = BeautifulSoup(page_html or "", "html.parser")
    for link in soup.find_all("a", href=True):
        if _is_year_listing(link.get_text(strip=True), str(link["href"])):
            return True
    return False


def collect_yield(
    page_html: str | None, page_url: str, dest_html: str | None = None
) -> dict:
    """Count minutes-like vs total PDFs; follow one hub when applicable."""
    links = pdf_links_from_html(page_html, page_url)
    if dest_html is not None and _has_year_listing(page_html):
        seen = {u for _, u in links}
        for text, url in pdf_links_from_html(dest_html, page_url):
            if url not in seen:
                seen.add(url)
                links.append((text, url))
    minutes_like = sum(
        1
        for text, href in links
        if _looks_like_minutes(text, href) and not _is_agenda_like(text, href)
    )
    total = sum(1 for text, href in links if not _is_agenda_like(text, href))
    positive = (
        total > 0
        and minutes_like >= MINUTES_LIKE_MIN_PDFS
        and (minutes_like / total) >= PURITY_THRESHOLD
    )
    return {"minutes_like": minutes_like, "total": total, "positive": positive}
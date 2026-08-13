#!/usr/bin/env python3
"""Step: find_plan_pdfs — searches for each plan/strategy listed in
input_plans.md and resolves it to a gov.ie source PDF URL, using a single
batched Apify search run (mirrors find_foi_pages_search's approach).

First step in document_pipeline: the runner passes it `--input <its own
step dir>`, which it ignores — same convention fetch_pdfs used before this
step was inserted ahead of it.

Not fatal: a plan whose search finds no gov.ie PDF is logged to
errors.json (PlanPdfNotFound) and skipped — retried automatically on the
next run. A doc_slug collision between two plans is logged
(DuplicateDocSlug) and the second plan is skipped. Only a malformed
input_plans.md (via plans.load_plans) is fatal, matching documents.py's
posture.
"""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from documents import SLUG_RE, load_documents
from lib.apify_search import batch_search
from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, write_json, write_status
from lib.http_utils import validate_url_or_raise
from plans import load_plans

STEP_NAME = "find_plan_pdfs"

_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    """Slug for a department name or plan title, matching documents.SLUG_RE.
    Mirrors detect_structure.process.slugify's ascii-fallback so a title
    with non-ASCII punctuation (en dash, curly quotes) still yields a valid
    doc_slug segment instead of an empty string."""
    slug = _NON_SLUG_RE.sub("-", text.lower()).strip("-")
    if not slug or not SLUG_RE.match(slug):
        slug = _NON_SLUG_RE.sub("-", text.encode("ascii", "ignore").decode().lower()).strip("-")
    return slug or "plan"


def _build_query(title: str) -> str:
    return f'site:gov.ie "{title}" filetype:pdf'


def _is_gov_ie(netloc: str) -> bool:
    return netloc == "gov.ie" or netloc.endswith(".gov.ie")


def _pick_pdf_url(results: list):
    """Iterate organic search results in rank order; return the first link
    that is a safe URL, on a gov.ie (sub)domain, and ends in .pdf.
    Mirrors find_foi_pages_search._pick_foi_url's candidate-picking shape."""
    for r in results:
        link = r.get("link", "")
        if not link:
            continue
        try:
            validate_url_or_raise(link, context="apify_result")
        except ValueError:
            continue
        parsed = urlparse(link)
        if not _is_gov_ie(parsed.netloc):
            continue
        if not parsed.path.lower().endswith(".pdf"):
            continue
        return link
    return None

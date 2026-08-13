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


def _build_query(department: str, title: str) -> str:
    return f'site:gov.ie "{department}" "{title}" filetype:pdf'


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
        if not _is_gov_ie(parsed.hostname or ""):
            continue
        if not parsed.path.lower().endswith(".pdf"):
            continue
        return link
    return None


def process(plans, existing_slugs, step_dir, writer, verbose=False):
    """Resolve each plan to a gov.ie PDF URL via batched Apify search,
    appending one record per success and one errors.json entry per skipped
    plan. Never raises for a single unresolved plan — see module docstring.
    """
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])

    seen_slugs = set()
    query_map = {}  # query string -> (plan, doc_slug)

    for plan in plans:
        dept_slug = _slugify(plan["department"])
        title_slug = _slugify(plan["title"])
        doc_slug = f"{dept_slug}-{title_slug}"

        if doc_slug in existing_slugs:
            continue  # documents.yml wins; not emitted here
        if writer.is_processed(doc_slug):
            continue  # already have a result (prior run or override)
        if doc_slug in seen_slugs:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "DuplicateDocSlug",
                "error_message": f"doc_slug {doc_slug!r} already generated for another "
                                 f"plan; skipping {plan['title']!r}",
                "context": {"doc_slug": doc_slug, "title": plan["title"],
                            "department": plan["department"]},
            })
            continue
        seen_slugs.add(doc_slug)
        query_map[_build_query(plan["department"], plan["title"])] = (plan, doc_slug)

    if not query_map:
        return

    search_results = batch_search(list(query_map.keys()))

    for query, (plan, doc_slug) in query_map.items():
        url = _pick_pdf_url(search_results.get(query, []))

        if url is None:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "PlanPdfNotFound",
                "error_message": f"No gov.ie PDF result found for {plan['title']!r}",
                "context": {"doc_slug": doc_slug, "title": plan["title"],
                            "department": plan["department"]},
            })
            continue

        writer.append([{
            "doc_slug": doc_slug,
            "title": plan["title"],
            "department": plan["department"],
            "url": url,
            "publisher": None,
            "public_body_id": None,
            "published_date": None,
            "source_method": "apify",
        }])


def main():
    parser = argparse.ArgumentParser(
        description="Search for plan/strategy source PDFs using Apify batch search")
    parser.add_argument("--input", required=True,
                        help="Previous step output (unused — first step in pipeline)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    override_path = step_dir / "override.json"

    plans = load_plans()
    existing_slugs = {d["doc_slug"] for d in load_documents()}

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, override_path=override_path,
                               target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(plans, existing_slugs, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} record(s) to {output_path}")


if __name__ == "__main__":
    main()

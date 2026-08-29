#!/usr/bin/env python3
"""Step: fetch_pdfs — downloads (or reuses a cached copy of) each document's
source PDF and writes one metadata record per document.

None of this step's four failure conditions is fatal to the run: a fetch
failure, a non-PDF payload, an encrypted PDF, or a PDF pymupdf cannot open
each log an error to errors.json (with an `error_type` of FetchFailed,
NotAPdf, EncryptedPdf, or UnreadablePdf respectively) and skip that one
document. The run itself always exits 0 — a bad document is a data-quality
issue to triage, not a reason to fail the whole crawl.

Ported from pdf2site's plan (source plan Task 5, lines 1300-1591): the
content-type check, sha256 computation, and hash-cache logic. Adapted to use
this repo's lib.http_utils.fetch (UA string, SSRF guard, rate limiting, and
bot-challenge detection already applied) instead of a bare httpx client, and
to make every failure non-fatal per this pipeline's per-document skip
convention (see fetch_foigovie_bodies/process.py).
"""
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from documents import load_documents
from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_pdfs"

# Response bodies with these Content-Types are treated as plausibly-a-PDF and
# streamed to disk; anything else is rejected before the body is downloaded.
# The final word on "is this actually a PDF" is always the magic-bytes check
# below, since a server can send a wrong-but-plausible header.
_PDF_CONTENT_TYPES = ("application/pdf", "application/x-pdf", "application/octet-stream")
_PDF_MAGIC = b"%PDF-"


class _FetchPdfsError(Exception):
    """Carries the errors.json `error_type` for one of the four non-fatal
    failure conditions this step recognises."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


def download(url: str, dest: Path) -> None:
    """Fetch `url` to `dest`. This is the seam process() calls through and
    tests monkeypatch, so it must remain importable as
    steps.fetch_pdfs.process.download.

    Supports file:// URLs (read straight off disk) as well as http(s)://,
    which is what lets --local-pdf substitute a local file without ever
    reaching lib.http_utils.fetch.
    """
    if url.startswith("file://"):
        from urllib.parse import unquote, urlparse
        local = Path(unquote(urlparse(url).path))
        dest.write_bytes(local.read_bytes())
        return

    response = fetch("GET", url, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type and content_type not in _PDF_CONTENT_TYPES:
        raise ValueError(f"server sent Content-Type {content_type!r}, not a PDF")

    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)


def inspect_pdf(path: Path):
    """Return (page_count, encrypted) for the PDF at `path`.

    Opens and closes the document immediately in a finally — this step does
    not interpret PDF content beyond validating it opens and reporting its
    page count and encryption state.
    """
    doc = pymupdf.open(path)
    try:
        encrypted = bool(doc.needs_pass or doc.is_encrypted)
        page_count = doc.page_count
    finally:
        doc.close()
    return page_count, encrypted


def _remote_unchanged(url: str, dest: Path) -> bool:
    """Best-effort conditional check: True only when a HEAD request's
    Content-Length exactly matches the cached file's size on disk. Matching
    length is not proof of byte-for-byte identity, so this is intentionally
    conservative — a missing header, a mismatch, or a failed HEAD request is
    all treated as inconclusive and triggers a re-download (delta 6:
    correctness over cleverness)."""
    try:
        response = fetch("HEAD", url)
    except Exception:
        return False
    if not response.ok:
        return False
    content_length = response.headers.get("Content-Length")
    if content_length is None:
        return False
    try:
        return int(content_length) == dest.stat().st_size
    except (ValueError, OSError):
        return False


def _cache_hit(doc: dict, dest: Path, prior: dict | None) -> bool:
    """True if the cached pdfs/<doc_slug>.pdf can be reused as-is: it exists
    on disk, its sha256 still matches the previous run's source_sha256, and a
    conditional request confirms the remote copy is unchanged."""
    if prior is None or not dest.exists():
        return False
    try:
        current_sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    except OSError:
        return False
    if current_sha256 != prior.get("source_sha256"):
        return False
    return _remote_unchanged(doc["url"], dest)


def _load_prior_records(output_path: Path) -> dict:
    """Map doc_slug -> previous record, read straight from output.json.

    IncrementalWriter does not preload prior results when force=True (a
    --force rerun starts writer.results empty), so this is the only way
    process() can see the previous run's source_sha256 to hash-cache
    against on a forced rerun.
    """
    if not output_path.exists():
        return {}
    try:
        return {
            r["doc_slug"]: r
            for r in read_json(output_path).get("results", [])
            if "doc_slug" in r
        }
    except (OSError, ValueError):
        return {}


def _load_discovered(input_path) -> list:
    """Read find_plan_pdfs/output.json's results list. Not fatal: if the
    file is missing or unreadable (e.g. find_plan_pdfs never ran, or failed
    before writing output — missing APIFY_TOKEN, a failed Apify run), this
    step should still be able to proceed on documents.yml alone."""
    try:
        return read_json(input_path).get("results", [])
    except (OSError, ValueError):
        return []


def _merge_documents(documents: list, discovered: list) -> list:
    """documents.yml wins on doc_slug collision; a find_plan_pdfs record
    whose doc_slug is not already curated in documents.yml is appended
    unchanged, so process() sees it as an ordinary document (its optional
    fields are already None, same shape documents.py itself produces)."""
    existing_slugs = {d["doc_slug"] for d in documents}
    return documents + [d for d in discovered if d["doc_slug"] not in existing_slugs]


def _doc_metadata(doc: dict) -> dict:
    """The record fields derived from the curated `doc` (documents.yml or a
    find_plan_pdfs result) rather than from the downloaded PDF. These can
    change between runs without the PDF changing, so a cache hit must still
    recompute them — only the download-derived facts (sha256, page_count,
    fetched_at, ...) stay pinned to the original fetch."""
    return {
        "doc_slug": doc["doc_slug"],
        "title": doc["title"],
        "url": doc["url"],
        "publisher": doc.get("publisher") or doc.get("department"),
        "public_body_id": doc.get("public_body_id"),
        "published_date": doc.get("published_date"),
    }


def process(documents, step_dir, writer, verbose=False):
    """Fetch (or reuse) each document's PDF, appending one record per
    success and one errors.json entry per skipped document. Never raises for
    a single bad document — see module docstring."""
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])
    pdfs_dir = step_dir / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    prior_by_slug = _load_prior_records(writer.output_path)

    for doc in documents:
        slug = doc["doc_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {doc['title']} ...", end=" ", flush=True)

        dest = pdfs_dir / f"{slug}.pdf"
        prior = prior_by_slug.get(slug)

        try:
            if _cache_hit(doc, dest, prior):
                record = dict(prior)
                record.update(_doc_metadata(doc))
                writer.append([record])
                if verbose:
                    print("[cached]", flush=True)
                continue

            try:
                download(doc["url"], dest)
            except Exception as e:
                raise _FetchPdfsError("FetchFailed", str(e)) from e

            payload = dest.read_bytes()
            if not payload.startswith(_PDF_MAGIC):
                raise _FetchPdfsError(
                    "NotAPdf", "downloaded content is not a PDF (missing %PDF- header)")

            try:
                page_count, encrypted = inspect_pdf(dest)
            except Exception as e:
                raise _FetchPdfsError("UnreadablePdf", str(e)) from e

            if encrypted:
                raise _FetchPdfsError("EncryptedPdf", f"{doc['url']} is password-protected")

            record = _doc_metadata(doc)
            record.update({
                "pdf_path": str(dest.relative_to(step_dir)),
                "source_sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "page_count": page_count,
                "encrypted": encrypted,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
            writer.append([record])
            if verbose:
                print("[ok]", flush=True)
        except _FetchPdfsError as e:
            dest.unlink(missing_ok=True)
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": e.error_type,
                "error_message": str(e),
                "context": {"doc_slug": slug, "url": doc["url"]},
            })
            writer.append([])
            if verbose:
                print("[error]", flush=True)


def _parse_local_pdf_args(pairs) -> dict:
    """Parse repeated --local-pdf SLUG=PATH options into {slug: path}."""
    overrides = {}
    for pair in pairs:
        slug, sep, path = pair.partition("=")
        if not sep or not slug or not path:
            raise SystemExit(f"--local-pdf must be SLUG=PATH, got {pair!r}")
        overrides[slug] = path
    return overrides


def main():
    parser = argparse.ArgumentParser(
        description="Fetch (or reuse a cached copy of) each document's source PDF")
    parser.add_argument("--input", required=True,
                        help="find_plan_pdfs/output.json — discovered plans merged with "
                             "documents.yml (documents.yml wins on doc_slug collision)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-download every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    parser.add_argument(
        "--local-pdf", action="append", default=[], metavar="SLUG=PATH", dest="local_pdf",
        help="Substitute a local file for SLUG's download instead of fetching its url "
             "(repeatable; test-only escape hatch so end-to-end tests never touch the network)")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    documents = load_documents()
    discovered = _load_discovered(args.input)
    documents = _merge_documents(documents, discovered)
    if args.doc is not None:
        documents = [d for d in documents if d["doc_slug"] == args.doc]

    local_overrides = _parse_local_pdf_args(args.local_pdf)
    for doc in documents:
        if doc["doc_slug"] in local_overrides:
            doc["url"] = Path(local_overrides[doc["doc_slug"]]).resolve().as_uri()

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(documents, step_dir, writer, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(documents)} document PDF record(s) to {output_path}")


if __name__ == "__main__":
    main()

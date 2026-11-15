#!/usr/bin/env python3
"""Fetch every document in the committed publication list into a local cache.

The cache is keyed by the document URL, so a URL that has already been fetched
is never requested again; the bytes are re-hashed on every run and the observed
digest is published with each record rather than pinned in configuration, so a
reissued PDF shows up as a digest change instead of blocking the annual run.
"""
import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

from allocations import CACHE_DIR, PIPELINE_DIR, flatten_documents, load_publications, make_error
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "fetch_grant_documents"
STEP_DIR = Path(__file__).parent
USER_AGENT = "publicinformation.ie-pipeline/1.0 (+https://www.publicinformation.ie)"
TIMEOUT_SECONDS = 120


def cache_path(url: str) -> Path:
    """One cache file per document URL, named by the URL digest."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.pdf"


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def collect(documents: list[dict], fetcher=fetch_bytes) -> tuple[list[dict], list[dict]]:
    """Return (document entries, errors) for the documents passed in."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    errors: list[dict] = []

    for document in documents:
        path = cache_path(document["url"])
        entry = dict(document)
        try:
            entry["cache_file"] = str(path.relative_to(PIPELINE_DIR))
        except ValueError:  # a cache outside the pipeline directory is still usable
            entry["cache_file"] = str(path)
        try:
            if path.exists() and path.stat().st_size > 0:
                data = path.read_bytes()
                entry["source"] = "cache"
            else:
                data = fetcher(document["url"])
                if not data:
                    raise ValueError("empty response body")
                path.write_bytes(data)
                entry["source"] = "network"
        except Exception as exc:  # noqa: BLE001 - any fetch failure is a data error
            entry.update(available=False, sha256=None, byte_size=None, error=str(exc))
            entries.append(entry)
            errors.append(make_error(
                STEP_NAME, "DocumentFetchError",
                f"{document['document_id']}: could not fetch or read the document",
                document_id=document["document_id"], year=document["year"],
                url=document["url"], reason=str(exc),
            ))
            continue

        entry.update(
            available=True,
            sha256=hashlib.sha256(data).hexdigest(),
            byte_size=len(data),
            error=None,
        )
        entries.append(entry)
    return entries, errors


def run(input_data: dict | None = None, document: str | None = None,
        fetcher=fetch_bytes) -> tuple[dict, list[dict]]:
    """`input_data` is unused: the committed list is the only ingestion source."""
    documents = flatten_documents(load_publications())
    if document is not None:
        documents = [d for d in documents if d["document_id"] == document]
        if not documents:
            raise ValueError(f"document {document!r} is not in publications.json")
    entries, errors = collect(documents, fetcher=fetcher)
    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": None,
            "documents": len(entries),
            "available": sum(1 for e in entries if e.get("available")),
        },
        "documents": entries,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the committed NTA allocation documents")
    add_common_args(parser)
    add_doc_arg(parser)
    args = parser.parse_args()

    input_data = {}
    if Path(args.input).is_file():
        input_data = read_json(args.input)

    output, errors = run(input_data, document=args.doc)

    errors_path = STEP_DIR / "errors.json"
    if errors_path.exists():
        errors_path.unlink()
    if errors:
        append_errors(STEP_DIR, errors)

    from allocations import now_iso

    output["metadata"]["completed_at"] = now_iso()
    write_json(args.output, output)
    write_status(STEP_DIR, len(output["documents"]))
    print(f"{output['metadata']['available']}/{output['metadata']['documents']} documents available")


if __name__ == "__main__":
    main()

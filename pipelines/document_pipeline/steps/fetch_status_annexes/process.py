#!/usr/bin/env python3
"""Step: fetch_status_annexes — downloads each report's declared status
workbook (`status_annex` in documents.yml) and writes one record per annex.

An annex is an attachment of its report, so this step runs beside the PDF
steps and never feeds them. Validation is of the *payload*, not the declared
Content-Type: gov.ie serves workbooks as `application/octet-stream`. A payload
is accepted only if it is a zip container (`PK\\x03\\x04`) that openpyxl can open.

Failures are per document and write **no record**, so the document stays
unprocessed and is retried on the next run (`AnnexUnreachable`,
`AnnexWrongFormat` naming expected and received, `AnnexChecksumMismatch`
naming declared and observed sha256, `AnnexUnreadable`).

`annexes/` is a git-ignored download cache, not committed data: each annex is
declared by url and sha256 in documents.yml. A cached file whose sha256 matches
the declaration is reused without any network request; otherwise the file is
downloaded and verified. A downloaded file that does not match the declared
sha256 is rejected, never read as that source.

Staleness: the runner only compares mtimes against an input step, and this step
has none that reflects documents.yml. It therefore lists itself in
`always_run`, and decides per document whether the cached workbook still
matches the curated `status_annex` (same url and format); a changed or removed
declaration is evicted and refetched.
"""
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from documents import load_documents
from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fetch_status_annexes"

_XLSX_CONTENT_TYPES = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
    "application/zip",
    "application/x-zip-compressed",
)
_ZIP_MAGIC = b"PK\x03\x04"


class _AnnexError(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


def download(url: str, dest: Path) -> None:
    """Fetch `url` to `dest`. The seam process() calls and tests monkeypatch."""
    if url.startswith("file://"):
        from urllib.parse import unquote, urlparse
        dest.write_bytes(Path(unquote(urlparse(url).path)).read_bytes())
        return
    response = fetch("GET", url, stream=True)
    response.raise_for_status()
    # A wrong Content-Type is not rejected here: the payload check is the
    # authority, and it names what was actually received.
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)


def received_format(payload: bytes) -> str:
    if payload.startswith(b"%PDF-"):
        return "pdf"
    if payload.startswith(_ZIP_MAGIC):
        return "zip"
    head = payload[:64].lstrip().lower()
    if head.startswith((b"<!doctype html", b"<html")):
        return "html"
    return "unknown"


def inspect_workbook(path: Path) -> list:
    """Sheet names of the workbook at `path`; raises if openpyxl cannot open it."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _declared(doc: dict) -> dict:
    annex = doc["status_annex"]
    return {"url": annex["url"], "format": annex["format"], "sha256": annex["sha256"]}


def process(documents, step_dir, writer, verbose=False):
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])
    annex_dir = step_dir / "annexes"
    annex_dir.mkdir(parents=True, exist_ok=True)

    declared = {d["doc_slug"]: _declared(d) for d in documents if d.get("status_annex")}

    # Evict records whose declaration changed or was removed (documents.yml is
    # the input this step is stale against), or whose file has gone.
    keep = []
    for record in writer.results:
        slug = record.get("doc_slug")
        want = declared.get(slug)
        if (want is not None and record.get("status_annex") == want
                and (step_dir / record.get("annex_path", "")).is_file()):
            keep.append(record)
        else:
            writer.processed_keys.discard(slug)
    writer.results = keep

    for doc in documents:
        slug = doc["doc_slug"]
        if slug not in declared or writer.is_processed(slug):
            continue
        want = declared[slug]
        if verbose:
            print(f"  {slug} ...", end=" ", flush=True)
        dest = annex_dir / f"{slug}.xlsx"
        try:
            payload = dest.read_bytes() if dest.is_file() else b""
            from_cache = bool(payload) and hashlib.sha256(payload).hexdigest() == want["sha256"]
            if not from_cache:
                try:
                    download(want["url"], dest)
                except Exception as e:
                    raise _AnnexError("AnnexUnreachable", str(e)) from e
                payload = dest.read_bytes()
                if not payload.startswith(_ZIP_MAGIC):
                    raise _AnnexError(
                        "AnnexWrongFormat",
                        f"expected {want['format']}, received {received_format(payload)}")
                observed = hashlib.sha256(payload).hexdigest()
                if observed != want["sha256"]:
                    raise _AnnexError(
                        "AnnexChecksumMismatch",
                        f"{slug}: declared sha256 {want['sha256']}, observed {observed}")
            try:
                sheets = inspect_workbook(dest)
            except Exception as e:
                raise _AnnexError("AnnexUnreadable", f"{type(e).__name__}: {e}") from e
            writer.append([{
                "doc_slug": slug,
                "status_annex": want,
                "annex_path": str(dest.relative_to(step_dir)),
                "source_sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "sheet_names": sheets,
                "fetched_at": None if from_cache else datetime.now(timezone.utc).isoformat(),
            }])
            if verbose:
                print("[cached]" if from_cache else "[ok]", flush=True)
        except _AnnexError as e:
            dest.unlink(missing_ok=True)
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": e.error_type,
                "error_message": str(e),
                "context": {"doc_slug": slug, "url": want["url"],
                            "expected_format": want["format"]},
            })
            writer.append([])
            if verbose:
                print("[error]", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch each report's declared status annex workbook")
    parser.add_argument("--input", default=None,
                        help="Ignored: reads only documents.yml")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-download every annex")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    documents = load_documents()
    if args.doc is not None:
        documents = [d for d in documents if d["doc_slug"] == args.doc]

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    process(documents, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} status annex record(s) to {output_path}")


if __name__ == "__main__":
    main()

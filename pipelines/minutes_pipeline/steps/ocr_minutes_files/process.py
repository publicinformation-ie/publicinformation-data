#!/usr/bin/env python3
import argparse
import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "ocr_minutes_files"

#: Minimum stripped-text length for a record to count as usable minutes
#: content. Triage basis (2026-10-07): signed-scan PDFs yield only a
#: signature date (12-26 chars); the shortest genuine minutes text in the
#: corpus is 1,587 chars. Records below this threshold after an OCR attempt
#: are quarantined (error-only, never emitted downstream) so the LLM step
#: never spends calls on them.
MIN_TEXT_CHARS = 200

#: Sidecar listing quarantined file_urls. Loaded at startup (except under
#: --force, which re-attempts everything) so quarantined files are never
#: re-OCR'd on subsequent runs. Delete to force re-attempts.
QUARANTINE_FILENAME = "quarantined_ids.json"


def _usable_text(text) -> bool:
    return len((text or "").strip()) >= MIN_TEXT_CHARS

_OCR_DPI = 300
_OCR_LANG = "eng"


def _cache_path(cache_dir, url):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"{digest}.pdf"


_PDF_MAGIC = b"%PDF-"


def _download(url, cache_dir):
    """Fetch a PDF into this step's cache (temp file + rename)."""
    path = _cache_path(cache_dir, url)
    if path.exists():
        return path.read_bytes()
    response = fetch("GET", url, allow_redirects=True)
    data = response.content
    if not data.strip().startswith(_PDF_MAGIC):
        raise ValueError(f"response from {url} is not a PDF (missing %PDF- magic bytes)")
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(path)
    return data


def _pdf_bytes_for(file_url, step_dir):
    """Return PDF bytes, preferring the upstream transform cache to avoid
    re-downloading files already fetched by transform_minutes_files."""
    upstream = (
        Path(step_dir).parent / "transform_minutes_files" / "pdf_cache"
    )
    upstream_path = _cache_path(upstream, file_url)
    if upstream_path.exists():
        return upstream_path.read_bytes()
    cache_dir = Path(step_dir) / "pdf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return _download(file_url, cache_dir)


def ocr_pdf_bytes(pdf_bytes: bytes, lang: str = _OCR_LANG) -> str:
    """Render each page to an image (~300 dpi) and OCR with Tesseract.

    Returns the per-page texts joined in page order. Blank pages contribute
    nothing. Raises on failure (caller maps to OcrFailed)."""
    import pymupdf
    from PIL import Image
    import pytesseract

    parts: list[str] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=_OCR_DPI)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang=lang)
            if text and text.strip():
                parts.append(text.strip())
    return "\n".join(parts)


def _process_one(item, step_dir):
    """Return (file_url, record_or_None, failure_or_None).

    Records with usable text pass through untouched. Anything else gets one
    OCR attempt (a near-empty text layer may sit beside recoverable scanned
    pages); a still-unusable result, or an infra exception, yields no record.
    failure is None on success, an Exception on infra failure, or a dict
    with quarantine details (input/ocr char counts) for unusable text.
    """
    file_url = item["file_url"]
    if _usable_text(item.get("text")):
        return file_url, dict(item), None
    input_chars = len((item.get("text") or "").strip())
    try:
        pdf_bytes = _pdf_bytes_for(file_url, step_dir)
        ocr_text = ocr_pdf_bytes(pdf_bytes)
        if _usable_text(ocr_text):
            return file_url, {**item, "text": ocr_text, "extractor": "tesseract"}, None
        return file_url, None, {"reason": "quarantine",
                                "input_chars": input_chars,
                                "ocr_chars": len((ocr_text or "").strip())}
    except Exception as e:
        return file_url, None, e


def _quarantine_error(file_url, public_body_id, failure):
    """Build the errors.json entry for a quarantined record."""
    if isinstance(failure, Exception):
        return {
            "step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": "OcrFailed",
            "error_message": f"{type(failure).__name__}: {failure}",
            "context": {"file_url": file_url,
                        "public_body_id": public_body_id},
        }
    if failure["input_chars"] == 0 and failure["ocr_chars"] == 0:
        message = "pdfplumber text was empty and tesseract OCR returned empty text"
        error_type = "EmptyTextExtraction"
    else:
        message = (f"text unusable after OCR attempt "
                   f"(text_layer_chars={failure['input_chars']}, "
                   f"ocr_chars={failure['ocr_chars']}, "
                   f"minimum={MIN_TEXT_CHARS})")
        error_type = "NearEmptyText"
    return {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": {"file_url": file_url,
                    "public_body_id": public_body_id},
    }


def process(input_data, step_dir, writer, quarantined=None, verbose=False, max_workers=2):
    """Run OCR over pending input records.

    quarantined: set of file_urls to skip (never re-attempted). Extended in
    place with newly quarantined urls and returned, so main() can persist it.
    Records that fail (unusable text or infra exception) are error-only:
    logged to errors.json and never emitted, so downstream steps never see
    them. Exceptions are transient (not quarantined) and retried next run.
    """
    if quarantined is None:
        quarantined = set()
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["file_url"])
               and item["file_url"] not in quarantined]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, item, step_dir): item for item in pending}
        for future in as_completed(futures):
            item = futures[future]
            file_url, record, failure = future.result()
            if failure is None:
                writer.append([record])
            else:
                append_error(step_dir, _quarantine_error(
                    file_url, item.get("public_body_id"), failure))
                writer.append([])
                if not isinstance(failure, Exception):
                    quarantined.add(file_url)
            if verbose:
                print(".", end="", flush=True)
    return quarantined


def _load_quarantine(step_dir) -> set:
    """Return quarantined file_urls, tolerating a missing/corrupt sidecar."""
    try:
        data = read_json(Path(step_dir) / QUARANTINE_FILENAME)
    except Exception:
        return set()
    return {u for u in data} if isinstance(data, list) else set()


def _save_quarantine(step_dir, quarantined) -> None:
    write_json(Path(step_dir) / QUARANTINE_FILENAME, sorted(quarantined))


def _evict_thin_output_records(writer):
    """Remove already-emitted output records that fail the usability gate.

    Needed because resume skips processed keys: without eviction, thin-text
    records emitted by older runs would flow downstream forever. Returns the
    evicted records so the caller can log quarantine errors for them.
    """
    thin = [r for r in writer.results if not _usable_text(r.get("text"))]
    if not thin:
        return []
    thin_keys = {r["file_url"] for r in thin if "file_url" in r}
    writer.results = [r for r in writer.results if r.get("file_url") not in thin_keys]
    writer.processed_keys -= thin_keys
    write_json(writer.output_path,
               {"metadata": {"step": STEP_NAME}, "results": writer.results})
    return thin


def main():
    parser = argparse.ArgumentParser(description="OCR image-only minutes PDFs with Tesseract")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (input_data.get("results")):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="file_url", force=args.force,
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
                               target_public_body=args.public_body)

    if args.force:
        # Clean slate: previously quarantined urls get a fresh OCR attempt.
        quarantined = set()
    else:
        quarantined = _load_quarantine(step_dir)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, quarantined, verbose=args.verbose,
            max_workers=args.workers)

    if not args.force:
        # Evict after process(): process() resets errors.json on entry, so
        # eviction errors logged beforehand would be wiped.
        evicted = _evict_thin_output_records(writer)
        for record in evicted:
            append_error(step_dir, _quarantine_error(
                record.get("file_url"), record.get("public_body_id"),
                {"reason": "quarantine",
                 "input_chars": len((record.get("text") or "").strip()),
                 "ocr_chars": 0}))
            if record.get("file_url"):
                quarantined.add(record["file_url"])
        if evicted:
            print(f"Quarantined {len(evicted)} pre-existing thin-text record(s), "
                  f"skipping downstream...")

    _save_quarantine(step_dir, quarantined)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()

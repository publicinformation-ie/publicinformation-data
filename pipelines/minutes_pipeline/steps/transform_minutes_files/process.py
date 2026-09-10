#!/usr/bin/env python3
import argparse
import hashlib
import io
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "transform_minutes_files"


def _extract_marker(pdf_bytes: bytes) -> str:
    """Primary extractor (no API key). Returns '' on any failure/empty."""
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output.text import TextOutput
        from marker.config.parser import ConfigParser
        config = ConfigParser({})
        converter = PdfConverter(
            config=config.get_general_config(),
            artifact_dict=create_model_dict(),
            processor_list=config.get_processors(),
            renderer=config.get_renderer(),
        )
        rendered = converter(io.BytesIO(pdf_bytes))
        text = rendered.markdown
        return text if isinstance(text, str) else ""
    except Exception:
        return ""


def _extract_pdfplumber(pdf_bytes: bytes) -> str:
    """Fallback extractor. Returns '' on failure/empty."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""


def extract_text(pdf_bytes: bytes):
    """Return (text, extractor). marker-pdf first, pdfplumber fallback on
    failure or empty result."""
    text = _extract_marker(pdf_bytes)
    if text and text.strip():
        return text, "marker_pdf"
    text = _extract_pdfplumber(pdf_bytes)
    if text and text.strip():
        return text, "pdfplumber"
    return "", "pdfplumber"


def _cache_path(cache_dir, url):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"{digest}.pdf"


_PDF_MAGIC = b"%PDF-"


def _download(url, cache_dir):
    """Fetch a PDF, persisting it to the pdf_cache so re-runs don't re-fetch.

    Fails closed on a non-PDF body (e.g. an HTML error page served with a
    200) and writes via a temp file + rename so an interrupted download can
    never leave a truncated file as a valid cache entry."""
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


def _process_one(item, cache_dir):
    url = item["file_url"]
    try:
        pdf_bytes = _download(url, cache_dir)
        text, extractor = extract_text(pdf_bytes)
        return item["file_url"], {**item, "text": text, "extractor": extractor}, None
    except Exception as e:
        return item["file_url"], None, e


def process(input_data, step_dir, writer, verbose=False, max_workers=4):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    cache_dir = step_dir / "pdf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["file_url"])]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, item, cache_dir): item for item in pending}
        for future in as_completed(futures):
            file_url, record, exc = future.result()
            if exc is not None:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "context": {"file_url": file_url,
                                "public_body_id": record["public_body_id"]
                                if record else None},
                })
                writer.append([])
            else:
                if not (record.get("text") or "").strip():
                    append_error(step_dir, {
                        "step": STEP_NAME,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error_type": "EmptyTextExtraction",
                        "error_message": "marker-pdf and pdfplumber both returned empty text",
                        "context": {"file_url": file_url,
                                    "public_body_id": record.get("public_body_id")},
                    })
                writer.append([record])
            if verbose:
                print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Extract prose text from minutes PDFs")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=4)
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

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()

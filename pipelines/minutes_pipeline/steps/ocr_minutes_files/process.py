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
    file_url = item["file_url"]
    if (item.get("text") or "").strip():
        return file_url, dict(item), None
    try:
        pdf_bytes = _pdf_bytes_for(file_url, step_dir)
        ocr_text = ocr_pdf_bytes(pdf_bytes)
        if ocr_text and ocr_text.strip():
            return file_url, {**item, "text": ocr_text, "extractor": "tesseract"}, None
        return file_url, {**item, "text": "", "extractor": item.get("extractor", "pdfplumber")}, "empty"
    except Exception as e:
        return file_url, {**item, "text": ""}, e


def process(input_data, step_dir, writer, verbose=False, max_workers=2):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["file_url"])]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, item, step_dir): item for item in pending}
        for future in as_completed(futures):
            item = futures[future]
            file_url, record, exc = future.result()
            public_body_id = item.get("public_body_id")
            if exc is not None and not isinstance(exc, str):
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "OcrFailed",
                    "error_message": f"{type(exc).__name__}: {exc}",
                    "context": {"file_url": file_url,
                                "public_body_id": public_body_id},
                })
                writer.append([record])
            elif exc == "empty":
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "EmptyTextExtraction",
                    "error_message": "pdfplumber text was empty and tesseract OCR returned empty text",
                    "context": {"file_url": file_url,
                                "public_body_id": public_body_id},
                })
                writer.append([record])
            else:
                writer.append([record])
            if verbose:
                print(".", end="", flush=True)


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

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()

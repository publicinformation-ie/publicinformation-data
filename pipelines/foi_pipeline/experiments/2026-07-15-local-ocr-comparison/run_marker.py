#!/usr/bin/env python3
"""Extract sampled PDFs with marker-pdf (VikParuchuri/marker).

Loads marker's model artifacts once, then converts each sampled PDF's bytes
(fetched via pdf_utils, downloading on a cache miss) to markdown, and caches
the raw markdown + elapsed_s to ocr_cache/marker-pdf/<sha256>.json —
mirrors steps/transform_disclosure_files/mistral_ocr.py's ocr_cache/ pattern.

Setup (not a production dependency — screening experiment only):
    uv pip install marker-pdf

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-local-ocr-comparison/run_marker.py
"""
import datetime
import json
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_FOI_PIPELINE))

import pdf_utils
from steps.transform_disclosure_files.mistral_ocr import markdown_to_rows

_PDF_CACHE_DIR = _FOI_PIPELINE / "steps/verify_disclosure_files/cache"
_SAMPLE_PATH = _HERE / "sample.json"
_OCR_CACHE_DIR = _HERE / "ocr_cache" / "marker-pdf"


def _cache_path(sha256: str) -> Path:
    return _OCR_CACHE_DIR / f"{sha256}.json"


def extract_file(converter, file_url: str, sha256: str) -> dict:
    from marker.output import text_from_rendered

    cache_path = _cache_path(sha256)
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    pdf_bytes = pdf_utils.get_pdf_bytes(_PDF_CACHE_DIR, file_url, sha256)

    t0 = time.time()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        rendered = converter(tmp.name)
    markdown, _, _ = text_from_rendered(rendered)
    elapsed = time.time() - t0

    entry = {
        "file_url": file_url,
        "markdown": markdown,
        "elapsed_s": round(elapsed, 2),
        "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(entry))
    return entry


def main() -> int:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    sample = json.loads(_SAMPLE_PATH.read_text())
    files = sample["files"]

    print("Loading marker-pdf model artifacts (one-time cost)...")
    converter = PdfConverter(artifact_dict=create_model_dict())

    for i, entry in enumerate(files, 1):
        cached = extract_file(converter, entry["file_url"], entry["sha256"])
        rows = markdown_to_rows(cached["markdown"])
        print(f"  [{i}/{len(files)}] {entry['sha256'][:8]}: {len(rows)} rows ({cached['elapsed_s']:.1f}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Extract sampled PDFs with local Ollama vision models.

For each sampled PDF and each model, renders every page to a PNG (via
pdf_utils), sends it to the local Ollama server through its
OpenAI-compatible chat endpoint with a table-extraction prompt, and joins
the per-page markdown with the same '\n---\n' page-break convention
mistral_ocr.markdown_to_rows already parses (matching how Mistral OCR
separates multi-page tables). Caches raw markdown + elapsed_s to
ocr_cache/<model_key>/<sha256>.json so reruns are free — mirrors
steps/transform_disclosure_files/mistral_ocr.py's ocr_cache/ pattern.

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-local-ocr-comparison/run_ollama.py
    uv run python experiments/2026-07-15-local-ocr-comparison/run_ollama.py --model qwen2.5vl:7b
"""
import argparse
import datetime
import json
import sys
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
_OCR_CACHE_DIR = _HERE / "ocr_cache"
_OLLAMA_BASE_URL = "http://localhost:11434/v1"
# ibm/granite-docling dropped 2026-07-15: its real output relies on DocTags
# structural tokens (<otsl>, <fcel>, <doctag>, ...) to mark table cells, but
# Ollama's OpenAI-compatible chat endpoint silently strips them as special
# tokens before returning content, leaving only <loc_N> bounding boxes and
# flattened, undelimited cell text — no table structure is recoverable from
# that response, with or without a docling-core parsing step. Confirmed by
# testing IBM's documented trigger prompt ("Convert this page to docling.")
# directly against the same endpoint: identical stripped output. Getting
# real tables out of granite-docling would require bypassing Ollama and
# running the model through docling's own pipeline — out of scope here.
_MODELS = ["qwen2.5vl:7b"]

_PROMPT = (
    "Extract every table on this page as GitHub-flavored markdown. "
    "Output only the markdown table(s), no commentary. If the page has no "
    "table, output nothing."
)


def _model_key(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def _cache_path(model: str, sha256: str) -> Path:
    return _OCR_CACHE_DIR / _model_key(model) / f"{sha256}.json"


def _call_ollama(client, model: str, png_bytes: bytes) -> str:
    data_uri = pdf_utils.png_to_data_uri(png_bytes)
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
    )
    return resp.choices[0].message.content or ""


def extract_file(client, model: str, file_url: str, sha256: str) -> dict:
    """Return the cached entry for (model, sha256), computing + caching it
    on a miss. Never re-queries a cache hit."""
    cache_path = _cache_path(model, sha256)
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    pdf_bytes = pdf_utils.get_pdf_bytes(_PDF_CACHE_DIR, file_url, sha256)
    pages = pdf_utils.render_pdf_pages_to_png(pdf_bytes)

    t0 = time.time()
    page_markdowns = [_call_ollama(client, model, png) for png in pages]
    elapsed = time.time() - t0
    markdown = "\n---\n".join(page_markdowns)

    entry = {
        "file_url": file_url,
        "model": model,
        "markdown": markdown,
        "elapsed_s": round(elapsed, 2),
        "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(entry))
    return entry


def main() -> int:
    import openai

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models",
                         help="Ollama model to run (repeatable). Defaults to both configured models.")
    args = parser.parse_args()
    models = args.models or _MODELS

    sample = json.loads(_SAMPLE_PATH.read_text())
    files = sample["files"]

    client = openai.OpenAI(api_key="not-needed", base_url=_OLLAMA_BASE_URL)

    for model in models:
        print(f"--- {model} ---")
        for i, entry in enumerate(files, 1):
            cached = extract_file(client, model, entry["file_url"], entry["sha256"])
            rows = markdown_to_rows(cached["markdown"])
            print(f"  [{i}/{len(files)}] {entry['sha256'][:8]}: {len(rows)} rows ({cached['elapsed_s']:.1f}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

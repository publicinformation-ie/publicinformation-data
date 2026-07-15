#!/usr/bin/env python3
"""Arm B extractor for the llm-structuring-repair experiment.

Pipeline per file:
  1. OCR the cached PDF bytes with mistral-ocr-latest, reading INLINE page
     markdown (table_format is deliberately omitted — see spec). Cached in
     ocr_cache/{sha}.json.
  2. Structure that markdown with mistral-large-latest via chat.parse against
     the DisclosureLog schema. Parsed entries + token usage cached in
     parse_cache/{sha}.json.
  3. Capture arm A rows for the same file from prod output.json.
Records tokens + derived cost per file; writes arms.json.

Run from foi_pipeline/ with a byte server exposing the OCR cache dir at
MISTRAL_OCR_PDF_BASE_URL:
    uv run python experiments/2026-07-15-llm-structuring-repair/extract.py
    uv run python experiments/2026-07-15-llm-structuring-repair/extract.py --force
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import requests
from mistralai.client import Mistral

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
_OUTPUT_JSON = _FOI_PIPELINE / "steps/transform_disclosure_files/output.json"
_SAMPLE = _HERE / "sample.json"
_OCR_CACHE = _HERE / "ocr_cache"
_PARSE_CACHE = _HERE / "parse_cache"
_ARMS_OUT = _HERE / "arms.json"

OCR_MODEL = "mistral-ocr-latest"
STRUCT_MODEL = "mistral-large-latest"
# mistral-large-latest published pricing (confirmed 2026-07-15).
PRICE_INPUT_PER_1M_USD = 0.5
PRICE_OUTPUT_PER_1M_USD = 1.5

_STRUCT_PROMPT = (
    "You are transcribing an Irish FOI disclosure-log table into structured "
    "rows. Below is the OCR markdown of the document. Return one entry per "
    "data row of the table, in document order. Copy printed values VERBATIM. "
    "Use null for any cell that is blank or absent. Do NOT invent rows, do NOT "
    "merge rows, do NOT normalise, reformat, translate, or infer values. "
    "Ignore repeated header rows.\n\nOCR MARKDOWN:\n"
)


def _load_schema():
    path = _HERE / "schema.py"
    spec = importlib.util.spec_from_file_location("llm_repair_schema", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_schema = _load_schema()
DisclosureLog = _schema.DisclosureLog


def _sha256(file_url: str) -> str:
    return hashlib.sha256(file_url.encode("utf-8")).hexdigest()


def _assert_pdf_reachable(byte_url: str) -> None:
    """Fetch the byte URL and assert it is a real PDF, not an HTML error page."""
    resp = requests.get(byte_url, timeout=60)
    resp.raise_for_status()
    head = resp.content[:5]
    if head != b"%PDF-":
        raise RuntimeError(
            f"byte server did not return a PDF for {byte_url}: "
            f"first bytes were {head!r} (is the byte server running?)"
        )


def ocr_inline_markdown(file_url, base_url, api_key, force=False, max_retries=3):
    """Return inline OCR markdown for file_url, caching in ocr_cache/{sha}.json.

    NOTE: table_format is intentionally omitted so tables stay inline in
    page.markdown rather than being externalised into [tbl-N.md] stubs.
    """
    _OCR_CACHE.mkdir(parents=True, exist_ok=True)
    sha = _sha256(file_url)
    cache_path = _OCR_CACHE / f"{sha}.json"
    if cache_path.exists() and not force:
        return json.loads(cache_path.read_text())["markdown"], False

    byte_url = f"{base_url.rstrip('/')}/{sha}.bytes"
    _assert_pdf_reachable(byte_url)
    client = Mistral(api_key=api_key)

    def _do_call():
        resp = client.ocr.process(
            model=OCR_MODEL,
            document={"type": "document_url", "document_url": byte_url},
            extract_header=True,
            confidence_scores_granularity="page",
        )
        parts = []
        if getattr(resp, "pages", None):
            for page in resp.pages:
                md = getattr(page, "markdown", None)
                if md:
                    parts.append(md)
        return "\n\n".join(parts)

    for attempt in range(max_retries):
        try:
            markdown = _do_call()
            cache_path.write_text(json.dumps({
                "file_url": file_url,
                "markdown": markdown,
                "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }))
            return markdown, True
        except Exception:
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 1)
            else:
                raise


def structure_markdown(file_url, markdown, api_key, force=False):
    """Structure markdown into entries via chat.parse; cache parsed JSON+usage.

    Returns (entries: list[dict] | None, usage: dict | None). entries is None
    on a derailment/empty structured output (counted as a failure downstream).
    """
    _PARSE_CACHE.mkdir(parents=True, exist_ok=True)
    sha = _sha256(file_url)
    cache_path = _PARSE_CACHE / f"{sha}.json"
    if cache_path.exists() and not force:
        cached = json.loads(cache_path.read_text())
        return cached["entries"], cached["usage"]

    client = Mistral(api_key=api_key)
    resp = client.chat.parse(
        model=STRUCT_MODEL,
        messages=[{"role": "user", "content": _STRUCT_PROMPT + (markdown or "")}],
        response_format=DisclosureLog,
    )
    parsed = resp.choices[0].message.parsed if resp.choices else None
    entries = [e.model_dump() for e in parsed.entries] if parsed else None
    usage = {
        "prompt": resp.usage.prompt_tokens,
        "completion": resp.usage.completion_tokens,
        "total": resp.usage.total_tokens,
    }
    cache_path.write_text(json.dumps({
        "file_url": file_url,
        "entries": entries,
        "usage": usage,
        "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }))
    return entries, usage


def cost_for(usage: dict) -> float:
    return round(
        usage["prompt"] / 1_000_000 * PRICE_INPUT_PER_1M_USD
        + usage["completion"] / 1_000_000 * PRICE_OUTPUT_PER_1M_USD,
        6,
    )


def _load_arm_a_rows() -> dict[str, list]:
    data = json.loads(_OUTPUT_JSON.read_text())
    return {
        r["file_url"]: r.get("rows")
        for r in data["results"]
        if r.get("file_url")
    }


def run(force: bool = False) -> int:
    api_key = os.environ.get("MISTRAL_API_KEY")
    base_url = os.environ.get("MISTRAL_OCR_PDF_BASE_URL")
    if not api_key or not base_url:
        print("ERROR: set MISTRAL_API_KEY and MISTRAL_OCR_PDF_BASE_URL "
              "(byte server must be running).", file=sys.stderr)
        return 1

    sample = json.loads(_SAMPLE.read_text())
    arm_a_by_url = _load_arm_a_rows()

    records = []
    for entry in sample["files"]:
        file_url = entry["file_url"]
        rec = {
            "file_url": file_url,
            "sha256": entry["sha256"],
            "stratum": entry["stratum"],
            "arm_a_rows": arm_a_by_url.get(file_url),
            "arm_b_entries": None,
            "ocr_made": False,
            "tokens": None,
            "cost_usd": None,
            "error": None,
        }
        try:
            markdown, made = ocr_inline_markdown(file_url, base_url, api_key, force=force)
            rec["ocr_made"] = made
            entries, usage = structure_markdown(file_url, markdown, api_key, force=force)
            rec["arm_b_entries"] = entries
            rec["tokens"] = usage
            rec["cost_usd"] = cost_for(usage) if usage else None
            if not entries:
                rec["error"] = "empty_structured_output"
        except Exception as exc:  # noqa: BLE001 - record, don't hide
            rec["error"] = f"{type(exc).__name__}: {exc}"
            print(f"  FAIL {file_url}: {rec['error']}", file=sys.stderr)
        records.append(rec)
        print(f"  done {entry['stratum']:18s} {file_url[:70]}")

    _ARMS_OUT.write_text(json.dumps({"records": records}, indent=2))
    n_ok = sum(1 for r in records if r["arm_b_entries"])
    print(f"Wrote {len(records)} records ({n_ok} arm-B ok) to {_ARMS_OUT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Arm B extractor for llm-repair")
    parser.add_argument("--force", action="store_true",
                        help="Ignore caches and re-issue API calls (re-incurs cost)")
    args = parser.parse_args()
    return run(force=args.force)


if __name__ == "__main__":
    sys.exit(main())

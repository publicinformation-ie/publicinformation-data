#!/usr/bin/env python3
"""Build the 15-file stratified sample for the local OCR comparison experiment.

7 currently-clean + 8 currently-flagged PDFs, drawn from the frozen eval
fixture (never the live step output). "Flagged" reuses the exact eval flag
functions so the strata match production's definition of clean/flagged.

Shrunk from an original 30-file (15+15) sample on 2026-07-15 after a
single-file qwen2.5vl:7b diagnostic showed acceptable quality but the full
30-file run was still too slow (~5.3h estimated); see
.superpowers/sdd/HANDOFF-local-ocr-comparison-2026-07-15.md.

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-local-ocr-comparison/sample.py
"""
import hashlib
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.eval.evaluate import (
    has_null_first_row,
    has_null_column,
    has_newline_split_row,
)

_EVAL_INPUT = _FOI_PIPELINE / "steps/transform_disclosure_files/eval/input.json"
_SAMPLE_OUT = _HERE / "sample.json"
_SEED = 42
_N_CLEAN = 7
_N_FLAGGED = 8


def _sha256(file_url: str) -> str:
    return hashlib.sha256(file_url.encode("utf-8")).hexdigest()


def _flags(rows: list) -> list[str]:
    result = []
    if has_null_first_row(rows):
        result.append("null_first_row")
    if has_null_column(rows):
        result.append("null_column")
    if has_newline_split_row(rows):
        result.append("newline_split_row")
    return result


def main() -> int:
    data = json.loads(_EVAL_INPUT.read_text())
    items = [
        r for r in data["results"]
        if r.get("file_type") == "pdf" and r.get("rows") is not None
    ]

    clean_pool = []
    flagged_pool = []
    for item in items:
        flags = _flags(item["rows"])
        (flagged_pool if flags else clean_pool).append((item, flags))

    print(f"Pool: {len(clean_pool)} clean, {len(flagged_pool)} flagged (of {len(items)} PDFs)")

    random.seed(_SEED)
    clean_sample = random.sample(clean_pool, min(_N_CLEAN, len(clean_pool)))
    flagged_sample = random.sample(flagged_pool, min(_N_FLAGGED, len(flagged_pool)))

    entries = []
    for item, flags in clean_sample + flagged_sample:
        entries.append({
            "file_url": item["file_url"],
            "sha256": _sha256(item["file_url"]),
            "public_body_id": item.get("public_body_id"),
            "name": item.get("name", ""),
            "baseline_flags": flags,
            "is_flagged": bool(flags),
        })

    _SAMPLE_OUT.write_text(json.dumps({
        "sample_date": "2026-07-15",
        "seed": _SEED,
        "n_clean": len(clean_sample),
        "n_flagged": len(flagged_sample),
        "files": entries,
    }, indent=2))
    print(f"Wrote {len(entries)} entries to {_SAMPLE_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

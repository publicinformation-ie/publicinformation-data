#!/usr/bin/env python3
"""Seeded stratified draw of broken PDFs for the llm-repair experiment.

Draws ~30 file_urls from steps/transform_disclosure_files/eval/issues.json,
over-weighting the dominant newline_split_row defect. Strata are drawn in a
fixed order (newline_split_row -> null_column -> null_first_row) with dedupe,
so the same seed reproduces byte-identical sample.json.

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-llm-structuring-repair/sample.py
"""
import hashlib
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
_ISSUES = _FOI_PIPELINE / "steps/transform_disclosure_files/eval/issues.json"
_SAMPLE_OUT = _HERE / "sample.json"

SEED = 42
TARGETS = {"newline_split_row": 22, "null_column": 6, "null_first_row": 2}
_STRATUM_ORDER = ["newline_split_row", "null_column", "null_first_row"]


def _sha256(file_url: str) -> str:
    return hashlib.sha256(file_url.encode("utf-8")).hexdigest()


def _pools() -> dict[str, list[str]]:
    """Map each stratum -> its affected_ids list from issues.json.

    The issue records are matched by the stratum name appearing in the
    record's `description` (e.g. "323 files have newline_split_row").
    """
    issues = json.loads(_ISSUES.read_text())
    pools: dict[str, list[str]] = {s: [] for s in _STRATUM_ORDER}
    for record in issues:
        desc = record.get("description", "")
        for stratum in _STRATUM_ORDER:
            if stratum in desc:
                pools[stratum] = list(record.get("affected_ids", []))
    return pools


def build_sample() -> dict:
    pools = _pools()
    rng = random.Random(SEED)
    chosen: list[dict] = []
    seen: set[str] = set()
    for stratum in _STRATUM_ORDER:
        available = [u for u in pools[stratum] if u not in seen]
        available.sort()  # stable base order before seeded shuffle
        n = min(TARGETS[stratum], len(available))
        picked = rng.sample(available, n)
        for url in picked:
            seen.add(url)
            chosen.append({
                "file_url": url,
                "sha256": _sha256(url),
                "stratum": stratum,
            })
    return {
        "sample_date": "2026-07-15",
        "seed": SEED,
        "targets": TARGETS,
        "files": chosen,
    }


def main() -> int:
    result = build_sample()
    _SAMPLE_OUT.write_text(json.dumps(result, indent=2))
    by_stratum: dict[str, int] = {}
    for f in result["files"]:
        by_stratum[f["stratum"]] = by_stratum.get(f["stratum"], 0) + 1
    print(f"Wrote {len(result['files'])} files to {_SAMPLE_OUT}: {by_stratum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

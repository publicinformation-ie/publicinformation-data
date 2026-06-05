#!/usr/bin/env python3
"""_CONTINUATION_NULL_THRESHOLD sweep experiment.

Phase 1 — Diagnostic: classify each InsufficientColumns failure as null_header,
vocab_gap, or not_in_fixture. Outputs diagnostic.csv.

Phase 2 — Sweep: for each threshold in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
run normalize_header_row against the frozen eval fixture, simulate the
InsufficientColumns check, and compute improvements/regressions vs baseline (0.5).
Outputs sweep_results.json.

Run from the experiment directory:
    uv run python run.py
"""
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

import steps.extract_disclosures_normalize_header.process as _nh_process
from steps.extract_disclosures_normalize_header.process import normalize_header_row
from steps.extract_disclosures_canonicalize.column_map import canonicalize_headers

_FIXTURE = _FOI_PIPELINE / "steps/extract_disclosures_normalize_header/eval/input.json"
_NH_OUTPUT = _FOI_PIPELINE / "steps/extract_disclosures_normalize_header/output.json"
_CANON_ERRORS = _FOI_PIPELINE / "steps/extract_disclosures_canonicalize/errors.json"
_DIAGNOSTIC_CSV = _HERE / "diagnostic.csv"
_SWEEP_JSON = _HERE / "sweep_results.json"

_THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
_BASELINE_THRESHOLD = 0.5
_MAX_CONTINUATION_ROWS = 3


def _classify_file(file_url: str, output_index: dict) -> dict:
    """Classify a single InsufficientColumns failure.

    Returns dict with keys: file_url, class, mapped_count, null_count.
    Classes:
      null_header    — header has ≥1 None cell (threshold may fix)
      vocab_gap      — header fully populated, <2 canonical cols map (needs synonyms)
      not_in_fixture — URL absent from normalize_header output (xlsx, non-PDF, etc.)
    """
    if file_url not in output_index:
        return {"file_url": file_url, "class": "not_in_fixture", "mapped_count": 0, "null_count": 0}

    item = output_index[file_url]
    header_row_idx = item.get("header_row_idx")
    rows = item.get("rows") or []

    if header_row_idx is None or header_row_idx >= len(rows):
        return {"file_url": file_url, "class": "not_in_fixture", "mapped_count": 0, "null_count": 0}

    header = rows[header_row_idx]
    null_count = sum(1 for h in header if h is None)

    non_null = [h for h in header if h is not None]
    mapping = canonicalize_headers(non_null)
    mapped_count = sum(1 for v in mapping.values() if v is not None)

    cls = "null_header" if null_count > 0 else "vocab_gap"
    return {"file_url": file_url, "class": cls, "mapped_count": mapped_count, "null_count": null_count}


def _test_classify_file():
    """Inline sanity test — runs before real data."""
    fake_index = {
        "http://null.pdf": {
            "header_row_idx": 0,
            "rows": [["Our Ref", None, "Description"]],
        },
        "http://vocab.pdf": {
            "header_row_idx": 0,
            "rows": [["Column A", "Column B", "Column C"]],
        },
    }
    r1 = _classify_file("http://null.pdf", fake_index)
    assert r1["class"] == "null_header", f"Expected null_header, got {r1['class']}"
    assert r1["null_count"] == 1, f"Expected null_count=1, got {r1['null_count']}"

    r2 = _classify_file("http://vocab.pdf", fake_index)
    assert r2["class"] == "vocab_gap", f"Expected vocab_gap, got {r2['class']}"
    assert r2["null_count"] == 0

    r3 = _classify_file("http://absent.pdf", fake_index)
    assert r3["class"] == "not_in_fixture", f"Expected not_in_fixture, got {r3['class']}"

    print("✓ _classify_file: all assertions passed")


def run_diagnostic() -> dict:
    """Phase 1: classify all InsufficientColumns failures. Writes diagnostic.csv."""
    errors = json.loads(_CANON_ERRORS.read_text())
    failing_urls = [
        e["context"]["file_url"]
        for e in errors
        if e.get("error_type") == "InsufficientColumns"
    ]

    output_data = json.loads(_NH_OUTPUT.read_text())
    output_index = {r["file_url"]: r for r in output_data.get("results", [])}

    rows = [_classify_file(url, output_index) for url in failing_urls]

    with _DIAGNOSTIC_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file_url", "class", "mapped_count", "null_count"])
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    total = len(rows)

    print(f"\n── Diagnostic summary ({total} InsufficientColumns failures) ──")
    for cls in ("null_header", "vocab_gap", "not_in_fixture"):
        n = counts.get(cls, 0)
        pct = 100 * n / total if total else 0
        print(f"  {cls}: {n} ({pct:.1f}%)")

    null_header_n = counts.get("null_header", 0)
    if null_header_n < 0.10 * total:
        print(
            f"\n⚠ null_header < 10% ({null_header_n}/{total}). "
            "Threshold tuning is likely the wrong lever — redirect to synonym expansion."
        )
    else:
        print(f"\n✓ null_header ≥ 10% ({null_header_n}/{total}). Threshold sweep is warranted.")

    print(f"Wrote {_DIAGNOSTIC_CSV}")
    return counts


def main() -> None:
    print(f"Loading fixture: {_FIXTURE}")
    data = json.loads(_FIXTURE.read_text())
    items = [
        r for r in data.get("results", [])
        if r.get("rows") is not None and r.get("header_row_idx") is not None
    ]
    print(f"Loaded {len(items)} records with header rows from eval fixture")

    _test_classify_file()

    print("\n── Phase 1: Diagnostic ──")
    run_diagnostic()


if __name__ == "__main__":
    main()

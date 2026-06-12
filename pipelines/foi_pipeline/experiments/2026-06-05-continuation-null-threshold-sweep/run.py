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


def _insufficient_at_threshold(item: dict, threshold: float) -> bool:
    """Return True if this item would fail InsufficientColumns at the given threshold.

    Monkeypatches _nh_process._CONTINUATION_NULL_THRESHOLD, calls normalize_header_row,
    then replays the exact canonical_to_col_idx logic from extract_disclosures_canonicalize.
    """
    _nh_process._CONTINUATION_NULL_THRESHOLD = threshold

    rows = item.get("rows")
    header_row_idx = item.get("header_row_idx")
    new_rows, new_idx = normalize_header_row(rows, header_row_idx, _MAX_CONTINUATION_ROWS)

    if new_idx >= len(new_rows):
        return True

    headers = new_rows[new_idx]
    mapping = canonicalize_headers(headers)

    canonical_to_col_idx: dict[str, int] = {}
    for col_idx, header in enumerate(headers):
        canonical = mapping.get(header)
        if canonical and canonical not in canonical_to_col_idx:
            canonical_to_col_idx[canonical] = col_idx

    return len(canonical_to_col_idx) < 2


def _run_threshold(items: list, threshold: float, baseline_fails: set) -> dict:
    """Compute metrics for a single threshold value.

    Returns a dict with: threshold, null_header_column_rate,
    insufficient_columns_count, improvements, regressions, net_change.
    """
    fails: set[str] = set()
    null_header_count = 0

    for item in items:
        _nh_process._CONTINUATION_NULL_THRESHOLD = threshold
        rows = item.get("rows")
        header_row_idx = item.get("header_row_idx")
        new_rows, new_idx = normalize_header_row(rows, header_row_idx, _MAX_CONTINUATION_ROWS)

        header = new_rows[new_idx] if new_idx < len(new_rows) else []
        if any(h is None for h in header):
            null_header_count += 1

        mapping = canonicalize_headers(header)
        canonical_to_col_idx: dict[str, int] = {}
        for col_idx, h in enumerate(header):
            canonical = mapping.get(h)
            if canonical and canonical not in canonical_to_col_idx:
                canonical_to_col_idx[canonical] = col_idx

        if len(canonical_to_col_idx) < 2:
            fails.add(item["file_url"])

    total = len(items)
    improvements = len(baseline_fails - fails)
    regressions = len(fails - baseline_fails)

    return {
        "threshold": threshold,
        "null_header_column_rate": round(null_header_count / total, 3) if total else 0.0,
        "insufficient_columns_count": len(fails),
        "improvements": improvements,
        "regressions": regressions,
        "net_change": improvements - regressions,
    }


def run_sweep(items: list) -> list:
    """Phase 2: sweep all thresholds, compute metrics, write sweep_results.json."""
    print(f"\n── Phase 2: Threshold sweep ({len(items)} fixture records) ──")

    # Pre-compute baseline fail set
    baseline_fails: set[str] = set()
    for item in items:
        if _insufficient_at_threshold(item, _BASELINE_THRESHOLD):
            baseline_fails.add(item["file_url"])
    print(f"Baseline (threshold={_BASELINE_THRESHOLD}): {len(baseline_fails)} InsufficientColumns failures")

    results = []
    for threshold in _THRESHOLDS:
        result = _run_threshold(items, threshold, baseline_fails)
        results.append(result)

        is_baseline = threshold == _BASELINE_THRESHOLD
        actionable = result["net_change"] >= 10 and result["regressions"] == 0
        disqualified = result["regressions"] > 0
        tag = " ★ ACTIONABLE" if actionable else (" DISQUALIFIED" if disqualified else "")
        baseline_tag = " (baseline)" if is_baseline else ""
        print(
            f"  threshold={threshold}{baseline_tag}: "
            f"insuff={result['insufficient_columns_count']:3d}  "
            f"improve={result['improvements']:3d}  "
            f"regress={result['regressions']:3d}  "
            f"net={result['net_change']:+3d}  "
            f"null_hdr_rate={result['null_header_column_rate']:.3f}"
            f"{tag}"
        )

    _SWEEP_JSON.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {_SWEEP_JSON}")

    actionable = [r for r in results if r["net_change"] >= 10 and r["regressions"] == 0]
    if actionable:
        best = max(actionable, key=lambda r: r["net_change"])
        print(
            f"\n✓ {len(actionable)} actionable config(s). "
            f"Best: threshold={best['threshold']} (net_change={best['net_change']:+d}, "
            f"regressions={best['regressions']})"
        )
    else:
        print(
            "\n✗ No actionable configuration found. "
            "Conclusion: threshold tuning is not the lever — consider synonym expansion."
        )

    return results


def _test_sweep_baseline_invariant(items: list) -> None:
    """Baseline (0.5) must have improvements=0 and regressions=0 vs itself."""
    baseline_fails = set()
    for item in items:
        if _insufficient_at_threshold(item, _BASELINE_THRESHOLD):
            baseline_fails.add(item["file_url"])
    result = _run_threshold(items, _BASELINE_THRESHOLD, baseline_fails)
    assert result["improvements"] == 0, f"Baseline improvements should be 0, got {result['improvements']}"
    assert result["regressions"] == 0, f"Baseline regressions should be 0, got {result['regressions']}"
    assert result["net_change"] == 0
    print("✓ sweep baseline invariant: improvements=0, regressions=0 at threshold=0.5 vs itself")


def main() -> None:
    print(f"Loading fixture: {_FIXTURE}")
    data = json.loads(_FIXTURE.read_text())
    items = [
        r for r in data.get("results", [])
        if r.get("rows") is not None and r.get("header_row_idx") is not None
    ]
    print(f"Loaded {len(items)} records with header rows from eval fixture")

    _test_classify_file()
    _test_sweep_baseline_invariant(items)

    print("\n── Phase 1: Diagnostic ──")
    run_diagnostic()

    run_sweep(items)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""pdfplumber parameter sweep experiment.

Sweeps 19 configurations (baseline + 18 param combos) across 721 cached PDFs.
Writes results.json and prints a ranked summary to stdout.

Run from project root:
    cd foi_pipeline && uv run python experiments/2026-06-04-pdfplumber-param-sweep/run.py
"""
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]  # foi_pipeline/
sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.process import _extract_pdf
from steps.transform_disclosure_files.eval.evaluate import (
    has_null_first_row,
    has_null_column,
    has_newline_split_row,
)

_CACHE_DIR = _FOI_PIPELINE / "steps" / "transform_disclosure_files" / "cache"
_EVAL_INPUT = _FOI_PIPELINE / "steps" / "transform_disclosure_files" / "eval" / "input.json"
_RESULTS_OUT = _HERE / "results.json"


def _url_cache_path(file_url: str) -> Path:
    sha = hashlib.sha256(file_url.encode("utf-8")).hexdigest()
    return _CACHE_DIR / f"{sha}.bytes"


def _build_configs() -> list[dict]:
    """Return list of config dicts. Config 0 is baseline (pdfplumber defaults)."""
    configs = [{"config_id": 0, "snap_y_tolerance": 3, "snap_tolerance": 3, "edge_min_length": 3}]
    config_id = 1
    for snap_y, snap, edge_min in itertools.product([3, 6, 10], [3, 6], [3, 10, 20]):
        if snap_y == 3 and snap == 3 and edge_min == 3:
            continue  # skip — this is the baseline, already config 0
        configs.append({
            "config_id": config_id,
            "snap_y_tolerance": snap_y,
            "snap_tolerance": snap,
            "edge_min_length": edge_min,
        })
        config_id += 1
    return configs


def _score_bytes(file_bytes: bytes, table_settings: dict) -> dict:
    """Extract and score a single PDF. Returns flags dict. All flags True on extraction failure."""
    try:
        _, rows, _, _ = _extract_pdf(file_bytes, table_settings=table_settings)
    except Exception:
        return {"null_first_row": True, "null_column": True, "newline_split_row": True}
    return {
        "null_first_row": has_null_first_row(rows),
        "null_column": has_null_column(rows),
        "newline_split_row": has_newline_split_row(rows),
    }


def _table_settings_from_config(config: dict) -> dict:
    return {
        "snap_y_tolerance": config["snap_y_tolerance"],
        "snap_tolerance": config["snap_tolerance"],
        "edge_min_length": config["edge_min_length"],
    }


def main() -> None:
    data = json.loads(_EVAL_INPUT.read_text())
    items = [
        r for r in data["results"]
        if r.get("file_type") == "pdf" and r.get("rows") is not None
    ]
    print(f"Loaded {len(items)} PDF records from eval fixture")

    # Load cached bytes (skip PDFs not in cache)
    print("Loading cached bytes...", end="", flush=True)
    records = []
    missing = 0
    for item in items:
        cache_path = _url_cache_path(item["file_url"])
        if not cache_path.exists():
            missing += 1
            continue
        records.append((item["file_url"], cache_path.read_bytes()))
    print(f" {len(records)} loaded, {missing} missing from cache")

    configs = _build_configs()
    print(f"Running {len(configs)} configurations × {len(records)} PDFs...")

    results = []
    baseline_clean_urls: set[str] = set()

    for config in configs:
        ts = _table_settings_from_config(config)
        t0 = time.time()
        clean = 0
        null_first_row_count = 0
        null_col_count = 0
        newline_split_count = 0
        flagged_urls: set[str] = set()

        for file_url, file_bytes in records:
            flags = _score_bytes(file_bytes, ts)
            any_flag = any(flags.values())
            if not any_flag:
                clean += 1
            else:
                flagged_urls.add(file_url)
            if flags["null_first_row"]:
                null_first_row_count += 1
            if flags["null_column"]:
                null_col_count += 1
            if flags["newline_split_row"]:
                newline_split_count += 1

        total = len(records)
        elapsed = time.time() - t0

        if config["config_id"] == 0:
            baseline_clean_urls = {url for url, _ in records} - flagged_urls

        regressions = len(baseline_clean_urls & flagged_urls)

        result = {
            **config,
            "clean_extraction_rate": round(clean / total, 3),
            "null_first_row_rate": round(null_first_row_count / total, 3),
            "null_column_rate": round(null_col_count / total, 3),
            "newline_split_row_rate": round(newline_split_count / total, 3),
            "regressions": regressions,
            "clean": clean,
            "total": total,
            "elapsed_s": round(elapsed, 1),
        }
        results.append(result)
        print(
            f"  config {config['config_id']:2d} "
            f"(snap_y={config['snap_y_tolerance']:2d} snap={config['snap_tolerance']} edge_min={config['edge_min_length']:2d}): "
            f"clean={result['clean_extraction_rate']:.3f} regressions={regressions} ({elapsed:.1f}s)"
        )

    _RESULTS_OUT.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} rows to {_RESULTS_OUT}")

    ranked = sorted(results, key=lambda r: (-r["clean_extraction_rate"], r["regressions"]))

    print("\n── Ranked results (by clean_extraction_rate desc, regressions asc) ──")
    header = f"{'cfg':>3}  {'snap_y':>6}  {'snap':>4}  {'edge_min':>8}  {'clean_rate':>10}  {'null_1st':>8}  {'null_col':>8}  {'newline':>7}  {'regress':>7}"
    print(header)
    print("-" * len(header))
    for r in ranked:
        actionable = " ★" if r["clean_extraction_rate"] >= 0.40 and r["regressions"] == 0 else ""
        print(
            f"{r['config_id']:>3}  "
            f"{r['snap_y_tolerance']:>6}  "
            f"{r['snap_tolerance']:>4}  "
            f"{r['edge_min_length']:>8}  "
            f"{r['clean_extraction_rate']:>10.3f}  "
            f"{r['null_first_row_rate']:>8.3f}  "
            f"{r['null_column_rate']:>8.3f}  "
            f"{r['newline_split_row_rate']:>7.3f}  "
            f"{r['regressions']:>7}"
            f"{actionable}"
        )

    actionable = [r for r in ranked if r["clean_extraction_rate"] >= 0.40 and r["regressions"] == 0]
    if actionable:
        best = actionable[0]
        print(f"\n✓ {len(actionable)} actionable config(s). Best: config {best['config_id']} "
              f"(snap_y={best['snap_y_tolerance']}, snap={best['snap_tolerance']}, "
              f"edge_min={best['edge_min_length']}) → clean_rate={best['clean_extraction_rate']:.3f}")
    else:
        print("\n✗ No actionable configuration found. "
              "Conclusion: pdfplumber settings are not the lever — "
              "extend normalize_header to cover data rows.")


if __name__ == "__main__":
    main()

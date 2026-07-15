#!/usr/bin/env python3
"""Run the sample's 15 files through the real downstream pipeline steps
(detect_header_row -> normalize_disclosure_cells -> canonicalize ->
canonicalize_rows -> deduplicate), once using the frozen eval fixture's
baseline `rows` (pdfplumber/mistral, whatever production used) and once
using qwen2.5vl:7b's `rows` (parsed from ocr_cache/qwen2.5vl_7b/*.json via
markdown_to_rows), and compares the errors/issues each downstream step
raises for the *same* files.

Every step function is imported and called directly with a scratch
step_dir per (variant, step) — never the real steps/*/errors.json,
pipeline-status.json etc, since those paths are hardcoded to
Path(__file__).parent inside each step regardless of --input/--output.
Mirrors the in-process pattern already used by
experiments/2025-01-03-mistral-ocr-comparison/run.py.

Run from foi_pipeline/:
    uv run python experiments/2026-07-15-local-ocr-comparison/pipeline_eval.py
"""
import json
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
_REPO_ROOT = _FOI_PIPELINE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_FOI_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from lib.file_utils import IncrementalWriter  # noqa: E402

from steps.extract_disclosures_detect_header_row.process import process as detect_header_process  # noqa: E402
from steps.normalize_disclosure_cells.process import process as normalize_process  # noqa: E402
from steps.extract_disclosures_canonicalize.process import (  # noqa: E402
    process as canonicalize_process,
    load_column_swaps,
    _load_column_mappings,
)
from steps.extract_disclosures_canonicalize_rows.process import process_records as canonicalize_rows_process  # noqa: E402
from steps.extract_disclosures_deduplicate.process import deduplicate_records  # noqa: E402
from steps.transform_disclosure_files.mistral_ocr import markdown_to_rows  # noqa: E402

_SAMPLE_PATH = _HERE / "sample.json"
_EVAL_INPUT = _FOI_PIPELINE / "steps/transform_disclosure_files/eval/input.json"
_OCR_CACHE_DIR = _HERE / "ocr_cache" / "qwen2.5vl_7b"
_SCRATCH = _HERE / "pipeline_eval_scratch"
_REAL_COLUMN_SWAPS_DIR = _FOI_PIPELINE / "steps/extract_disclosures_canonicalize"


def _run_downstream(items: list[dict], variant: str) -> dict:
    """Feed `items` (transform_disclosure_files-output-shaped records) through
    the real downstream steps and return per-file error counts + totals."""
    root = _SCRATCH / variant
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    # --- detect_header_row ---
    step_dir = root / "1_detect_header_row"
    step_dir.mkdir()
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "extract_disclosures_detect_header_row", key_field="file_url")
    detect_header_process({"results": items}, step_dir, writer, verbose=False)
    writer.finalize()
    header_data = json.loads(output_path.read_text())

    # --- normalize_disclosure_cells ---
    step_dir = root / "2_normalize"
    step_dir.mkdir()
    output_path = step_dir / "output.json"
    writer = IncrementalWriter(output_path, "normalize_disclosure_cells", key_field="file_url")
    normalize_process(header_data, step_dir, writer, force=False, verbose=False)
    writer.finalize()
    normalized_data = json.loads(output_path.read_text())

    # --- canonicalize (needs real column_swaps/column_mappings config, read-only) ---
    column_swaps = load_column_swaps(_REAL_COLUMN_SWAPS_DIR)
    column_mappings = _load_column_mappings(_REAL_COLUMN_SWAPS_DIR)
    canon_results: list = []
    canon_errors: list = []
    canonicalize_process(normalized_data, canon_results, canon_errors,
                          column_swaps=column_swaps, column_mappings=column_mappings, verbose=False)

    # --- canonicalize_rows (decision_status normalization) ---
    rows_results: list = []
    rows_errors: list = []
    canonicalize_rows_process({"results": canon_results}, rows_results, rows_errors, verbose=False)

    # --- deduplicate ---
    dedup_results, duplicates_removed, _null_ids = deduplicate_records(rows_results)

    # Per-file error tallies
    errors_by_file: dict[str, int] = {}
    for e in canon_errors + rows_errors:
        url = e.get("context", {}).get("file_url") or e.get("file_url")
        if url:
            errors_by_file[url] = errors_by_file.get(url, 0) + 1

    return {
        "variant": variant,
        "n_input_files": len(items),
        "n_canonicalized_records": len(canon_results),
        "n_canonicalize_errors": len(canon_errors),
        "n_decision_status_errors": len(rows_errors),
        "n_after_dedup": len(dedup_results),
        "duplicates_removed": duplicates_removed,
        "errors_by_file": errors_by_file,
        "canon_errors_sample": canon_errors[:5],
        "rows_errors_sample": rows_errors[:5],
    }


def main() -> int:
    sample = json.loads(_SAMPLE_PATH.read_text())
    files = sample["files"]
    urls = {e["file_url"] for e in files}

    baseline_fixture = json.loads(_EVAL_INPUT.read_text())
    baseline_by_url = {r["file_url"]: r for r in baseline_fixture["results"] if r["file_url"] in urls}

    baseline_items = []
    qwen_items = []
    for e in files:
        base = baseline_by_url.get(e["file_url"])
        if base is None:
            print(f"WARNING: {e['sha256'][:8]} not found in eval fixture, skipping", file=sys.stderr)
            continue
        baseline_items.append(dict(base))  # baseline rows as-is

        cache_path = _OCR_CACHE_DIR / f"{e['sha256']}.json"
        cached = json.loads(cache_path.read_text())
        qwen_rows = markdown_to_rows(cached["markdown"])
        qwen_item = dict(base)
        qwen_item["rows"] = qwen_rows
        qwen_items.append(qwen_item)

    baseline_result = _run_downstream(baseline_items, "baseline")
    qwen_result = _run_downstream(qwen_items, "qwen")

    print(json.dumps({"baseline": baseline_result, "qwen": qwen_result}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

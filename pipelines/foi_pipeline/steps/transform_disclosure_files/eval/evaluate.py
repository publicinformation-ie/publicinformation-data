#!/usr/bin/env python3
"""Evaluate transform_disclosure_files: file-transformation success rate.

Success criterion: a valid table was extracted to JSON. Content quality (null columns,
newline-split rows, etc.) is out of scope here — those are addressed downstream by
normalize_disclosure_cells and extract_disclosures_detect_header_row.

Primary metric: extraction_success_rate (fraction of attempted files that produced rows).
Issues are raised only for hard file-transformation failures (PDFSyntaxError, BadZipFile,
ValueError, etc.) that prevent any table from being extracted.
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

from eval import utils as eval_utils

STEP = "transform_disclosure_files"

# Error types that mean the file could not be transformed at all.
HARD_FAILURE_TYPES = frozenset({
    "ValueError", "PDFSyntaxError", "XLRDError",
    "BadZipFile", "TooManyRedirects", "FileNotFoundError",
})


def build_quality_by_body(items, process_warning_urls, hard_failure_urls):
    by_body = {}
    for item in items:
        bid = item.get("public_body_id")
        if bid not in by_body:
            by_body[bid] = {
                "name": item.get("name", ""),
                "total_pdfs": 0,
                "successful": 0,
                "samples": [],
            }
        entry = by_body[bid]
        entry["total_pdfs"] += 1
        url = item["file_url"]
        if url in hard_failure_urls:
            continue
        entry["successful"] += 1
        rows = item.get("rows") or []
        entry["samples"].append({
            "file_url": url,
            "total_rows": len(rows),
            "has_process_warning": url in process_warning_urls,
            "pdf_extractor": item.get("pdf_extractor", "pdfplumber"),
        })
    return by_body


def run_eval(items, process_warning_urls, input_hash, camelot_fallback_urls=None, hard_failures=None):
    if camelot_fallback_urls is None:
        camelot_fallback_urls = set()
    if hard_failures is None:
        hard_failures = {}

    failure_count = sum(len(urls) for urls in hard_failures.values())
    success_count = len(items)
    total = success_count + failure_count

    hard_failure_urls = {url for urls in hard_failures.values() for url in urls}

    if total == 0:
        metrics = [
            eval_utils.Metric("extraction_success_rate", 1.0, {"successful": 0, "total": 0}, is_primary=True),
            eval_utils.Metric("camelot_fallback_rate", 0.0, {"attempted": 0, "total": 0}),
            eval_utils.Metric("camelot_win_rate", 0.0, {"wins": 0, "total": 0}),
        ]
        results = eval_utils.EvalResults(step=STEP, metrics=metrics, input_hash=input_hash, judge_model=None)
        return results, [], {}

    camelot_fallback_count = sum(1 for item in items if item["file_url"] in camelot_fallback_urls)
    camelot_win_count = sum(1 for item in items if item.get("pdf_extractor") == "camelot_stream")

    metrics = [
        eval_utils.Metric("extraction_success_rate", round(success_count / total, 3),
                          {"successful": success_count, "total": total}, is_primary=True),
        eval_utils.Metric("camelot_fallback_rate", round(camelot_fallback_count / total, 3),
                          {"attempted": camelot_fallback_count, "total": total}),
        eval_utils.Metric("camelot_win_rate", round(camelot_win_count / total, 3),
                          {"wins": camelot_win_count, "total": total}),
    ]

    issues = []
    for error_type, urls in sorted(hard_failures.items()):
        issues.append(eval_utils.Issue(
            severity="error",
            description=f"{len(urls)} files failed: {error_type}",
            affected_count=len(urls),
            affected_ids=urls[:50],
            suggested_upstream_step=STEP,
            suggestion_detail=f"Investigate {error_type} failures during file extraction",
            confidence=1.0,
        ))

    quality_by_body = build_quality_by_body(items, process_warning_urls, hard_failure_urls)
    results = eval_utils.EvalResults(step=STEP, metrics=metrics, input_hash=input_hash, judge_model=None)
    return results, issues, quality_by_body


def _load_errors(errors_path):
    """Return the raw errors list, or [] if the file is absent."""
    if not errors_path.exists():
        return []
    return json.loads(errors_path.read_text())


def _load_process_warning_urls(errors):
    return {
        e["context"]["file_url"]
        for e in errors
        if e.get("error_type") in ("MultipleTableWarning", "CellSerializationWarning")
        and "file_url" in e.get("context", {})
    }


def _load_camelot_fallback_urls(errors):
    return {
        e["context"]["file_url"]
        for e in errors
        if e.get("error_type") == "CamelotFallbackAttempted"
        and "file_url" in e.get("context", {})
    }


def _load_hard_failures(errors):
    """Return {error_type: [file_urls]} for genuine extraction failures."""
    by_type = {}
    for e in errors:
        etype = e.get("error_type")
        if etype in HARD_FAILURE_TYPES:
            url = e.get("context", {}).get("file_url")
            if url:
                by_type.setdefault(etype, []).append(url)
    return by_type


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate transform_disclosure_files PDF extraction quality"
    )
    parser.add_argument("--input-path", dest="input_path", default=str(_HERE / "input.json"))
    parser.add_argument("--errors-path", dest="errors_path", default=str(_HERE.parent / "errors.json"))
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture input.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, _HERE / "input.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    data = json.loads(Path(args.input_path).read_text())
    items = [
        r for r in data["results"]
        if r.get("file_type") == "pdf" and r.get("rows") is not None
    ]
    errors = _load_errors(Path(args.errors_path))
    process_warning_urls = _load_process_warning_urls(errors)
    camelot_fallback_urls = _load_camelot_fallback_urls(errors)
    hard_failures = _load_hard_failures(errors)

    results, issues, quality_by_body = run_eval(
        items, process_warning_urls, eval_utils.input_hash(Path(args.input_path)),
        camelot_fallback_urls=camelot_fallback_urls,
        hard_failures=hard_failures,
    )

    eval_utils.write_eval_outputs(_HERE, results, issues)
    (_HERE / "quality_by_body.json").write_text(json.dumps(quality_by_body, indent=2))

    primary = results.metrics[0]
    print(
        f"{STEP}: extraction_success_rate={primary.value:.3f} "
        f"({primary.counts['successful']}/{primary.counts['total']} files), "
        f"{len(issues)} issues"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

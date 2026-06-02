#!/usr/bin/env python3
"""Evaluate find_disclosure_files: precision via human-verified LLM judgments.

Recall is not measurable (no ground-truth list of all files that should exist);
the funnel + north-star catch large recall losses. Primary metric = precision
over the verified subset. Determinism: judgments cached by file_url in
judgments.json; LLM called only on cache miss.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

import eval_utils
import eval_judge

STEP = "find_disclosure_files"


def _prompt(item):
    return (
        "You are judging whether a discovered file is a genuine FOI disclosure "
        "log/record (not a privacy notice, form, or unrelated PDF).\n"
        f"URL: {item['file_url']}\n"
        f"file_type: {item.get('file_type')}\n"
        "Answer strictly as: <yes|no> | <one-line rationale>"
    )


def _duplicate_metrics(items):
    """Return (metrics_list, issues_list) for duplicate file_url detection.

    Deterministic — no LLM involved. Three metrics:
      duplicate_file_url_count       — distinct URLs appearing more than once
      duplicate_file_url_extra_records — total wasted records from duplicates
      duplicate_file_url_rate        — fraction of total records that are extras
    """
    if not items:
        return [
            eval_utils.Metric("duplicate_file_url_count", 0, {}),
            eval_utils.Metric("duplicate_file_url_extra_records", 0, {}),
            eval_utils.Metric("duplicate_file_url_rate", 0.0, {}),
        ], []

    url_counts = Counter(item["file_url"] for item in items)
    duplicate_urls = {url: count for url, count in url_counts.items() if count > 1}
    duplicate_count = len(duplicate_urls)
    extra_records = sum(count - 1 for count in duplicate_urls.values())
    duplicate_rate = extra_records / len(items)

    metrics = [
        eval_utils.Metric("duplicate_file_url_count", duplicate_count,
                          {"distinct_duplicate_urls": duplicate_count}),
        eval_utils.Metric("duplicate_file_url_extra_records", extra_records,
                          {"extra_records": extra_records, "total": len(items)}),
        eval_utils.Metric("duplicate_file_url_rate", duplicate_rate,
                          {"extra_records": extra_records, "total": len(items)}),
    ]

    issues = []
    if duplicate_count > 0:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{duplicate_count} duplicate file URLs found ({extra_records} extra records)",
            affected_count=extra_records,
            affected_ids=list(duplicate_urls.keys())[:50],
            suggested_upstream_step="find_disclosure_files",
            suggestion_detail="Same file URL discovered multiple times; may indicate redundant crawling or upstream data issues",
            confidence=1.0,
        ))

    return metrics, issues


def run_eval(items, judgments, input_hash, api_fn=eval_judge.default_api_fn):
    # Fill cache misses (judge writes verified='auto').
    for item in items:
        eval_judge.judge(item["file_url"], _prompt(item), judgments, api_fn=api_fn)

    foi = judged = unverified = 0
    non_foi_ids = []
    for item in items:
        entry = judgments[item["file_url"]]
        if entry.get("verified") in ("yes", "no"):
            judged += 1
            if entry["label"] == "yes":
                foi += 1
            else:
                non_foi_ids.append(item["file_url"])
        else:
            unverified += 1

    precision = foi / judged if judged else 0.0
    metrics = [
        eval_utils.Metric("precision", round(precision, 3),
                          {"foi": foi, "judged": judged}, is_primary=True),
        eval_utils.Metric("unverified_coverage", unverified,
                          {"unverified": unverified, "total": len(items)}),
    ]

    issues = []
    if non_foi_ids:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{len(non_foi_ids)} files judged non-FOI",
            affected_count=len(non_foi_ids), affected_ids=non_foi_ids[:50],
            suggested_upstream_step=None,
            suggestion_detail="add a content-type / filename filter to find_disclosure_files",
            confidence=0.8))

    dup_metrics, dup_issues = _duplicate_metrics(items)
    metrics.extend(dup_metrics)
    issues.extend(dup_issues)

    results = eval_utils.EvalResults(step=STEP, metrics=metrics,
                                     input_hash=input_hash,
                                     judge_model=eval_judge.judge_model_id())
    return results, issues


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Evaluate find_disclosure_files precision")
    parser.add_argument("--input-path", dest="input_path", default=str(here / "input.json"))
    parser.add_argument("--judgments", default=str(here / "judgments.json"))
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture input.json from a live output file, then exit")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, here / "input.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    items = json.loads(Path(args.input_path).read_text())["results"]
    judgments_path = Path(args.judgments)
    judgments = json.loads(judgments_path.read_text())

    results, issues = run_eval(items, judgments,
                               eval_utils.input_hash(Path(args.input_path)))

    judgments_path.write_text(json.dumps(judgments, indent=2))  # persist new judgments
    eval_utils.write_eval_outputs(here, results, issues)
    p = results.metrics[0]
    print(f"{STEP}: precision={p.value:.3f} ({p.counts['foi']}/{p.counts['judged']} verified), "
          f"{len(issues)} issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())

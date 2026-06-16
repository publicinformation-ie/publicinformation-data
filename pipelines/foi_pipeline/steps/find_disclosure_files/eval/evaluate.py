#!/usr/bin/env python3
"""Evaluate find_disclosure_files: precision via human-verified LLM judgments.

Recall is not measurable (no ground-truth list of all files that should exist);
the funnel + north-star catch large recall losses. Primary metric = precision
over the verified subset. Determinism: judgments cached by file_url in
judgments.json; LLM called only on cache miss.

Judgment verified values:
  "yes" / "no"  — human-verified; highest confidence.
  "auto"        — LLM-generated, not yet human-reviewed.
  "mock"        — heuristic label applied without an LLM call (e.g. when
                  running offline). Mock labels are intentionally stricter
                  than _url_score: they require a recognisable FOI signal in
                  the URL, whereas _url_score accepts URLs with no keywords.
                  Mock-"no" entries therefore measure genuine filter
                  false-positives (files _url_score passes that a human would
                  reject). All three verified states count toward the precision
                  denominator; only "auto" is treated as unverified.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parents[2]))  # foi_pipeline/ -> imports eval_utils

from eval import utils as eval_utils
from eval import judge as eval_judge

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
    # Mistral: submit all cache misses as one batch job (50% cost saving vs serial calls).
    if eval_judge.judge_provider() == "mistral":
        pairs = [(item["file_url"], _prompt(item)) for item in items]
        eval_judge.batch_judge(pairs, judgments)
    else:
        # Fill cache misses one at a time (judge writes verified='auto').
        for item in items:
            eval_judge.judge(item["file_url"], _prompt(item), judgments, api_fn=api_fn)

    foi = judged = mock_non_foi = 0
    non_foi_ids = []
    for item in items:
        entry = judgments.get(item["file_url"], {})
        verified = entry.get("verified")
        # "yes"/"no" = human-verified; "mock" = heuristic label; all count toward precision.
        # "auto" = LLM-generated but not human-reviewed; treated as unverified.
        if verified in ("yes", "no", "mock"):
            judged += 1
            if entry["label"] == "yes":
                foi += 1
            else:
                non_foi_ids.append(item["file_url"])
                if verified == "mock":
                    mock_non_foi += 1
    unverified = len(items) - judged

    precision = foi / judged if judged else 0.0
    metrics = [
        eval_utils.Metric("precision", round(precision, 3),
                          {"foi": foi, "judged": judged}, is_primary=True),
        eval_utils.Metric("unverified_coverage", unverified,
                          {"unverified": unverified, "total": len(items)}),
        eval_utils.Metric("mock_judgments", mock_non_foi,
                          {"mock": mock_non_foi, "total": len(items)}),
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

    if judged > 0 and mock_non_foi / judged > 0.3:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"{mock_non_foi} non-FOI items identified by mock-heuristic — consider promoting to human-verified labels",
            affected_count=mock_non_foi,
            affected_ids=[],
            suggested_upstream_step=None,
            suggestion_detail="Run evaluate.py with MISTRAL_API_KEY + EVAL_JUDGE_PROVIDER=mistral (batch, 50% cheaper) or ANTHROPIC_API_KEY to replace mock labels with LLM judgments, then human-verify",
            confidence=1.0))

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

#!/usr/bin/env python3
"""Evaluate minutes-page discovery against labels.csv via PDF-yield.

A "positive" prediction = the predicted page (or its year-listing hub
target) links >= 1 minutes-like PDFs with purity >= 0.5 (see score_page).
Correctness depends on the label: has_log=yes -> TP if positive else FN;
has_log=no -> FP if positive else TN. Keys with no record or no pages
fixture are skipped fail-closed (label rot / unscorable), never TN.

Usage (from minutes_pipeline/):
    uv run python steps/find_meeting_minutes_pages_search/eval/evaluate.py
"""
import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MINUTES_PIPELINE = _HERE.parents[2]
_REPO_ROOT = _MINUTES_PIPELINE.parents[1]
sys.path.insert(0, str(_MINUTES_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "pipelines" / "foi_pipeline"))
sys.path.insert(0, str(_HERE))

from eval import utils as eval_utils  # noqa: E402

from capture_fixtures import fixture_key  # noqa: E402
from score_page import collect_yield  # noqa: E402


def _norm(url):
    return (url or "").rstrip("/").lower()


def classify(record, label_row, positive):
    """Return 'TP' | 'FP' | 'FN' | 'TN' for one labelled key."""
    if label_row["has_log"] == "yes":
        return "TP" if positive else "FN"
    return "FP" if positive else "TN"


def _key(row):
    return fixture_key(row["public_body_id"], row["municipal_district"] or None)


def score(records_by_key, labels, yields_by_key):
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    details = {"FP": [], "FN": [], "skipped": []}
    url_matches = 0
    skipped = 0
    for row in labels:
        key = _key(row)
        record = records_by_key.get(key)
        if record is None or key not in yields_by_key:
            skipped += 1
            details["skipped"].append(key)
            continue
        positive = yields_by_key[key]
        outcome = classify(record, row, positive)
        counts[outcome] += 1
        if outcome == "FP":
            details["FP"].append((key, record["minutes_page_url"]))
        elif outcome == "FN":
            details["FN"].append((key, row["expected_url"]))
        if _norm(record.get("minutes_page_url")) == _norm(row.get("expected_url", "")) \
                and row.get("expected_url"):
            url_matches += 1
    tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return counts, precision, recall, f1, details, skipped, url_matches


def run_eval(records_by_key, labels, yields_by_key, fixture_path):
    """Build EvalResults + Issues from scored records. Pure given inputs."""
    counts, precision, recall, f1, details, skipped, url_matches = score(
        records_by_key, labels, yields_by_key)
    metrics = [
        eval_utils.Metric("f1", round(f1, 3),
                          {"TP": counts["TP"], "FP": counts["FP"],
                           "FN": counts["FN"], "TN": counts["TN"],
                           "url_matches": url_matches}, is_primary=True),
        eval_utils.Metric("precision", round(precision, 3),
                          {"TP": counts["TP"], "FP": counts["FP"]}),
        eval_utils.Metric("recall", round(recall, 3),
                          {"TP": counts["TP"], "FN": counts["FN"]}),
    ]
    issues = []
    for key, url in details["FP"]:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"Non-minutes hub scored positive for key {key}",
            affected_count=1, affected_ids=[str(key)],
            suggested_upstream_step=None,
            suggestion_detail=f"returned {url}", confidence=0.6))
    for key, url in details["FN"]:
        issues.append(eval_utils.Issue(
            severity="info",
            description=f"Minutes page missed for key {key}",
            affected_count=1, affected_ids=[str(key)],
            suggested_upstream_step=None,
            suggestion_detail=f"expected {url}", confidence=0.6))
    if skipped:
        issues.append(eval_utils.Issue(
            severity="warning",
            description=f"{skipped} labelled keys had no record or no pages "
                         f"fixture (excluded from metrics — label rot/unscorable)",
            affected_count=skipped, affected_ids=[str(k) for k in details["skipped"]],
            suggested_upstream_step=None,
            suggestion_detail="re-capture fixtures / re-check labels.csv",
            confidence=1.0))
    results = eval_utils.EvalResults(
        step="find_meeting_minutes_pages_search",
        metrics=metrics,
        input_hash=eval_utils.input_hash(fixture_path),
        judge_model=None,
    )
    return results, issues


def _load_labels(path):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("has_log")]


def _load_records(path):
    data = json.loads(Path(path).read_text())
    out = {}
    for r in data["results"]:
        district = r.get("municipal_district") or None
        out[fixture_key(r["public_body_id"], district)] = r
    return out


def _load_yields(labels, records):
    yields = {}
    for row in labels:
        key = _key(row)
        record = records.get(key)
        if record is None:
            continue
        page_path = _HERE / "fixtures" / "pages" / f"{key}.html"
        if not page_path.exists():
            continue
        dest_path = _HERE / "fixtures" / "destinations" / f"{key}.html"
        dest_html = dest_path.read_text(encoding="utf-8") if dest_path.exists() else None
        y = collect_yield(page_path.read_text(encoding="utf-8"),
                          record.get("minutes_page_url", ""), dest_html)
        yields[key] = y["positive"]
    return yields


def main():
    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description="Evaluate minutes-page discovery")
    parser.add_argument("--labels", default=str(here / "labels.csv"))
    parser.add_argument("--input-path", dest="input_path",
                        default=str(here / "matcher_output.json"),
                        help="Frozen fixture to score (default) or a live run path")
    parser.add_argument("--refresh-fixture", metavar="LIVE_OUTPUT",
                        help="Re-capture matcher_output.json from a live output file, then exit")
    parser.add_argument("--force", action="store_true",
                        help="Recompute even when eval_results.json is fresh vs "
                             "evaluate.py/labels.csv/matcher_output.json")
    args = parser.parse_args()

    if args.refresh_fixture:
        import shutil
        shutil.copy(args.refresh_fixture, here / "matcher_output.json")
        print(f"Refreshed fixture from {args.refresh_fixture}")
        return 0

    if not args.force and not eval_utils.is_eval_stale(
            here / "eval_results.json",
            [Path(__file__), Path(args.labels), Path(args.input_path)]):
        print("Eval fresh vs evaluate.py/labels.csv/matcher_output.json; "
              "use --force to recompute")
        return 0

    labels = _load_labels(args.labels)
    records = _load_records(args.input_path)
    yields = _load_yields(labels, records)
    results, issues = run_eval(records, labels, yields, Path(args.input_path))

    primary = next(m for m in results.metrics if m.is_primary)
    counts = primary.counts
    precision = next(m.value for m in results.metrics if m.name == "precision")
    recall = next(m.value for m in results.metrics if m.name == "recall")
    skipped_issues = [i for i in issues if "no record or no pages" in i.description]
    skipped = skipped_issues[0].affected_count if skipped_issues else 0

    print(f"Labelled keys evaluated: {sum(counts.values())}")
    print(f"  TP={counts['TP']}  FP={counts['FP']}  FN={counts['FN']}  TN={counts['TN']}")
    print(f"  precision={precision:.3f}  recall={recall:.3f}  f1={primary.value:.3f}")
    print(f"  url_matches={counts['url_matches']}")
    if skipped:
        print(f"  WARNING: {skipped} labelled keys excluded (no record/fixture)")

    eval_utils.write_eval_outputs(here, results, issues)
    return 0


if __name__ == "__main__":
    sys.exit(main())

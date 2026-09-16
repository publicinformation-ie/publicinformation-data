#!/usr/bin/env python3
"""Minutes-page discovery experiment runner.

Run from minutes_pipeline/:
    uv run python experiments/2026-09-15-minutes-page-discovery/run_experiment.py --approach baseline
    uv run python experiments/2026-09-15-minutes-page-discovery/run_experiment.py --approach all
apify_rerank needs APIFY_TOKEN and consumes Apify credits.
"""
import argparse
import csv
import importlib.util as _ilu
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).parent
_MINUTES_PIPELINE = _HERE.parent.parent
_REPO_ROOT = _MINUTES_PIPELINE.parents[1]
sys.path.insert(0, str(_MINUTES_PIPELINE))
sys.path.insert(0, str(_REPO_ROOT / "src"))

_EVAL_DIR = _MINUTES_PIPELINE / "steps" / "find_meeting_minutes_pages_search" / "eval"
sys.path.insert(0, str(_EVAL_DIR))

from lib.http_utils import fetch  # noqa: E402
from evaluate import classify  # noqa: E402
from score_page import collect_yield  # noqa: E402
from capture_fixtures import fixture_key  # noqa: E402

_LABELS_CSV = _EVAL_DIR / "labels.csv"
_FIXTURES = _EVAL_DIR / "fixtures"
_AUTHORITIES = _MINUTES_PIPELINE / "steps" / "find_local_authorities" / "output.json"
_RESULTS_DIR = _HERE / "results"

APPROACHES = ["baseline", "one_hop", "two_hop", "apify_rerank"]


def _load_approach(name):
    path = _HERE / "approaches" / f"{name}.py"
    spec = _ilu.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_labels():
    with open(_LABELS_CSV, newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("has_log")]


def _authorities_by_id():
    return {int(a["public_body_id"]): a
            for a in json.loads(_AUTHORITIES.read_text())["results"]}


def _read(key, subdir):
    p = _FIXTURES / subdir / f"{key}.html"
    return p.read_text(encoding="utf-8") if p.exists() else None


def _pages_map(live_by_key):
    """Map absolute URL -> cached HTML for hub/destination fixtures.

    Hubs come from fixtures/hub_index.json (URL -> filename); predicted
    pages are keyed by their live minutes_page_url so BFS can step into
    them. URLs without a cached file are absent (fail-closed: skipped)."""
    by_url = {}
    hub_index_path = _FIXTURES / "hub_index.json"
    if hub_index_path.exists():
        for url, fname in json.loads(hub_index_path.read_text()).items():
            p = _FIXTURES / "hubs" / fname
            if p.exists():
                by_url[url] = p.read_text(encoding="utf-8")
    for key, url in live_by_key.items():
        p = _FIXTURES / "pages" / f"{key}.html"
        if p.exists():
            by_url.setdefault(url, p.read_text(encoding="utf-8"))
    return by_url


def _score(keys_results, labels):
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for key, url, _method in keys_results:
        row = next((r for r in labels
                    if fixture_key(r["public_body_id"], r["municipal_district"] or None) == key),
                   None)
        if row is None:
            continue
        page_html = _read(key, "pages")
        if page_html is None:
            continue
        dest_html = _read(key, "destinations")
        positive = collect_yield(page_html, url, dest_html)["positive"]
        counts[classify({"minutes_page_url": url}, row, positive)] += 1
    tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"counts": counts, "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(f1, 3)}


def main():
    parser = argparse.ArgumentParser(description="Minutes-page discovery experiments")
    parser.add_argument("--approach", default="baseline",
                        help="Approach: baseline|one_hop|two_hop|apify_rerank|all")
    args = parser.parse_args()

    labels = _load_labels()
    authorities = _authorities_by_id()
    live_by_key = {}
    for row in labels:
        key = fixture_key(row["public_body_id"], row["municipal_district"] or None)
        if row.get("expected_url"):
            live_by_key[key] = row["expected_url"]
    pages = _pages_map(live_by_key)
    to_run = APPROACHES if args.approach == "all" else [args.approach]
    for a in to_run:
        if a not in APPROACHES:
            print(f"Unknown approach: {a}. Valid: {', '.join(APPROACHES + ['all'])}")
            sys.exit(1)

    _RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    for approach in to_run:
        mod = _load_approach(approach)
        keys_results = []
        for row in labels:
            key = fixture_key(row["public_body_id"], row["municipal_district"] or None)
            home_html = _read(key, "home")
            website = authorities.get(int(row["public_body_id"]), {}).get(
                "official_website_url", "")
            if approach == "apify_rerank":
                print(f"  [{key}] apify_rerank needs live search; skipping offline")
                continue
            url, method = mod.predict(home_html or "", website, pages)
            if url:
                keys_results.append((key, url, method))
            time.sleep(0.1)
        metrics = _score(keys_results, labels)
        out = {"approach": approach,
               "timestamp": datetime.now(timezone.utc).isoformat(),
               "fixture_count": len(keys_results), "metrics": metrics,
               "results": [{"key": k, "minutes_page_url": u, "source_method": m}
                           for k, u, m in keys_results]}
        out_path = _RESULTS_DIR / f"{approach}_{timestamp}.json"
        out_path.write_text(json.dumps(out, indent=2))
        print(f"  {approach}: F1={metrics['f1']:.3f} "
              f"P={metrics['precision']:.3f} R={metrics['recall']:.3f} "
              f"({metrics['counts']}) → {out_path}")


if __name__ == "__main__":
    main()

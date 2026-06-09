#!/usr/bin/env python3
"""run_experiment.py — disclosure page discovery experiment runner.

Run from foi_pipeline/:
    uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach a
    uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach all
    uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py \
        --approach ac1 --bodies 1129,1132,1133,1134,1135,1141,1143,1145,1149,1153,1155,1156,1157
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
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

from lib.http_utils import fetch

_FIXTURES = _FOI_PIPELINE / "steps" / "find_disclosure_pages" / "eval" / "fixtures"
_LABELS_CSV = _FOI_PIPELINE / "steps" / "find_disclosure_pages" / "eval" / "labels.csv"
_OUTPUT_JSON = _FOI_PIPELINE / "steps" / "find_disclosure_pages" / "output.json"
_RESULTS_DIR = _HERE / "results"

TARGET_BODY_IDS = frozenset(
    {1129, 1132, 1133, 1134, 1135, 1141, 1143, 1145, 1149, 1153, 1155, 1156, 1157}
)


def _load_approach(name: str):
    path = _HERE / "approaches" / f"{name}.py"
    spec = _ilu.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ── Labels ──────────────────────────────────────────────────────────────────

def _load_labels() -> dict[int, dict]:
    with open(_LABELS_CSV, newline="") as f:
        return {int(r["public_body_id"]): r for r in csv.DictReader(f) if r.get("label")}


def _load_foi_by_id() -> dict[str, dict]:
    data = json.loads(_OUTPUT_JSON.read_text())
    return {str(r["public_body_id"]): r for r in data["results"]}


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _ensure_fixtures(body_ids: frozenset[int], foi_by_id: dict) -> None:
    missing = [
        pid for pid in body_ids
        if not (_FIXTURES / f"{pid}.html").exists()
        and str(pid) in foi_by_id
    ]
    if not missing:
        return
    print(f"Fetching {len(missing)} missing fixtures...")
    for pid in sorted(missing):
        dest = _FIXTURES / f"{pid}.html"
        url = foi_by_id[str(pid)]["foi_page_url"]
        try:
            resp = fetch("GET", url, allow_redirects=True)
            dest.write_text(resp.text, encoding="utf-8")
            print(f"  [{pid}] fetched {url}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  [{pid}] FAIL {url}: {e}")


# ── Evaluation ───────────────────────────────────────────────────────────────

def _norm(url: str) -> str:
    return (url or "").rstrip("/").lower()


def _classify(predicted_url: str, foi_url: str, label_row: dict) -> str:
    predicted_distinct = _norm(predicted_url) != _norm(foi_url)
    label = label_row["label"]
    expected = label_row.get("expected_url", "")
    if label == "distinct_log":
        if not predicted_distinct:
            return "FN"
        return "TP" if _norm(predicted_url) == _norm(expected) else "FP"
    return "FP" if predicted_distinct else "TN"


def _score_results(body_results: list[dict], labels: dict, body_ids=None) -> dict:
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for r in body_results:
        pid = r["public_body_id"]
        if body_ids is not None and pid not in body_ids:
            continue
        label_row = labels.get(pid)
        if not label_row:
            continue
        outcome = _classify(r["disclosure_page_url"], r["foi_page_url"], label_row)
        counts[outcome] += 1
    tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "counts": counts,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


# ── Approach runners ─────────────────────────────────────────────────────────

def _run_baseline(fixtures: list[Path], foi_by_id: dict) -> list[dict]:
    from steps.find_disclosure_pages.process import find_disclosure_link
    results = []
    for path in fixtures:
        pid = int(path.stem)
        src = foi_by_id.get(str(pid))
        if not src:
            continue
        html = path.read_text(encoding="utf-8")
        match = find_disclosure_link(html, src["foi_page_url"])
        if match:
            url, sc = match
            method, conf = "crawl", ("high" if sc >= 70 else "medium")
        else:
            url, method, conf = src["foi_page_url"], "foi_page_fallback", "none"
        results.append({
            "public_body_id": pid,
            "name": src.get("name", ""),
            "foi_page_url": src["foi_page_url"],
            "disclosure_page_url": url,
            "confidence": conf,
            "source_method": method,
        })
    return results


def _run_approach_a(fixtures: list[Path], foi_by_id: dict) -> list[dict]:
    mod = _load_approach("scoring_fix")
    find_disclosure_link = mod.find_disclosure_link
    results = []
    for path in fixtures:
        pid = int(path.stem)
        src = foi_by_id.get(str(pid))
        if not src:
            continue
        html = path.read_text(encoding="utf-8")
        match = find_disclosure_link(html, src["foi_page_url"])
        if match:
            url, sc = match
            method, conf = "crawl", ("high" if sc >= 70 else "medium")
        else:
            url, method, conf = src["foi_page_url"], "foi_page_fallback", "none"
        results.append({
            "public_body_id": pid,
            "name": src.get("name", ""),
            "foi_page_url": src["foi_page_url"],
            "disclosure_page_url": url,
            "confidence": conf,
            "source_method": method,
        })
    return results


def _run_approach_c1(fixtures: list[Path], foi_by_id: dict) -> list[dict]:
    mod = _load_approach("two_hop_crawl")
    find_disclosure_link_two_hop = mod.find_disclosure_link_two_hop
    results = []
    for path in fixtures:
        pid = int(path.stem)
        src = foi_by_id.get(str(pid))
        if not src:
            continue
        html = path.read_text(encoding="utf-8")
        match = find_disclosure_link_two_hop(html, src["foi_page_url"])
        if match:
            url, sc, meth = match
            conf = "high" if sc >= 70 else "medium"
        else:
            url, meth, conf = src["foi_page_url"], "foi_page_fallback", "none"
        results.append({
            "public_body_id": pid,
            "name": src.get("name", ""),
            "foi_page_url": src["foi_page_url"],
            "disclosure_page_url": url,
            "confidence": conf,
            "source_method": meth,
        })
    return results


def _run_approach_c2(fixtures: list[Path], foi_by_id: dict, api_token: str | None) -> list[dict]:
    mod = _load_approach("apify_depth_crawl")
    run_apify_depth_crawl = mod.run_apify_depth_crawl
    results = []
    for path in fixtures:
        pid = int(path.stem)
        src = foi_by_id.get(str(pid))
        if not src:
            continue
        foi_url = src["foi_page_url"]
        print(f"  C2 crawl: {src.get('name', pid)} ...", end=" ", flush=True)
        try:
            match = run_apify_depth_crawl(foi_url, api_token=api_token)
        except Exception as e:
            print(f"FAIL ({e})")
            match = None
        if match:
            url, sc = match
            conf = "high" if sc >= 70 else "medium"
            meth = "apify_depth"
            print(f"found score={sc}")
        else:
            url, meth, conf = foi_url, "foi_page_fallback", "none"
            print("miss")
        results.append({
            "public_body_id": pid,
            "name": src.get("name", ""),
            "foi_page_url": foi_url,
            "disclosure_page_url": url,
            "confidence": conf,
            "source_method": meth,
        })
    return results


def _run_approach_ac1(fixtures: list[Path], foi_by_id: dict) -> list[dict]:
    # two_hop_crawl already uses scoring_fix for its first pass
    return _run_approach_c1(fixtures, foi_by_id)


def _run_approach_ac2(fixtures: list[Path], foi_by_id: dict, api_token: str | None) -> list[dict]:
    sf_mod = _load_approach("scoring_fix")
    a_find = sf_mod.find_disclosure_link
    c2_mod = _load_approach("apify_depth_crawl")
    run_apify_depth_crawl = c2_mod.run_apify_depth_crawl
    results = []
    for path in fixtures:
        pid = int(path.stem)
        src = foi_by_id.get(str(pid))
        if not src:
            continue
        html = path.read_text(encoding="utf-8")
        foi_url = src["foi_page_url"]

        match = a_find(html, foi_url)
        if match:
            url, sc = match
            conf = "high" if sc >= 70 else "medium"
            meth = "crawl"
        else:
            print(f"  AC2 Apify fallback: {src.get('name', pid)} ...", end=" ", flush=True)
            try:
                match_c2 = run_apify_depth_crawl(foi_url, api_token=api_token)
            except Exception as e:
                print(f"FAIL ({e})")
                match_c2 = None
            if match_c2:
                url, sc = match_c2
                conf = "high" if sc >= 70 else "medium"
                meth = "apify_depth"
                print(f"found score={sc}")
            else:
                url, meth, conf = foi_url, "foi_page_fallback", "none"
                print("miss")

        results.append({
            "public_body_id": pid,
            "name": src.get("name", ""),
            "foi_page_url": foi_url,
            "disclosure_page_url": url,
            "confidence": conf,
            "source_method": meth,
        })
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

_APPROACH_RUNNERS = {
    "baseline": lambda f, fbi, **kw: _run_baseline(f, fbi),
    "a":        lambda f, fbi, **kw: _run_approach_a(f, fbi),
    "c1":       lambda f, fbi, **kw: _run_approach_c1(f, fbi),
    "c2":       lambda f, fbi, **kw: _run_approach_c2(f, fbi, kw.get("api_token")),
    "ac1":      lambda f, fbi, **kw: _run_approach_ac1(f, fbi),
    "ac2":      lambda f, fbi, **kw: _run_approach_ac2(f, fbi, kw.get("api_token")),
}


def main():
    parser = argparse.ArgumentParser(description="Disclosure page discovery experiment runner")
    parser.add_argument("--approach", default="a", help="Approach: baseline|a|c1|c2|ac1|ac2|all")
    parser.add_argument("--bodies", help="Comma-separated body IDs to restrict to")
    parser.add_argument("--apify-token", default=None, help="Override APIFY_TOKEN")
    args = parser.parse_args()

    restrict_ids: frozenset[int] | None = None
    if args.bodies:
        restrict_ids = frozenset(int(x.strip()) for x in args.bodies.split(","))

    labels = _load_labels()
    foi_by_id = _load_foi_by_id()

    _ensure_fixtures(TARGET_BODY_IDS, foi_by_id)

    all_fixtures = sorted(_FIXTURES.glob("*.html"))
    if restrict_ids:
        all_fixtures = [f for f in all_fixtures if int(f.stem) in restrict_ids]

    approaches_to_run = (
        list(_APPROACH_RUNNERS.keys()) if args.approach == "all" else [args.approach]
    )

    api_token = args.apify_token
    _RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    for approach in approaches_to_run:
        if approach not in _APPROACH_RUNNERS:
            print(f"Unknown approach: {approach}. Valid: {', '.join(_APPROACH_RUNNERS)}")
            sys.exit(1)

        print(f"\n── Running approach '{approach}' over {len(all_fixtures)} fixtures ──")
        runner = _APPROACH_RUNNERS[approach]
        body_results = runner(all_fixtures, foi_by_id, api_token=api_token)

        all_metrics = _score_results(body_results, labels)
        target_metrics = _score_results(body_results, labels, body_ids=TARGET_BODY_IDS)

        out = {
            "approach": approach,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fixture_count": len(all_fixtures),
            "target_body_ids": sorted(TARGET_BODY_IDS),
            "metrics": {
                "all_labelled": all_metrics,
                "target_slice": target_metrics,
            },
            "results": body_results,
        }

        out_path = _RESULTS_DIR / f"{approach}_{timestamp}.json"
        out_path.write_text(json.dumps(out, indent=2))
        print(
            f"  all_labelled: F1={all_metrics['f1']:.3f} "
            f"P={all_metrics['precision']:.3f} R={all_metrics['recall']:.3f} "
            f"({all_metrics['counts']})"
        )
        print(
            f"  target_slice: F1={target_metrics['f1']:.3f} "
            f"P={target_metrics['precision']:.3f} R={target_metrics['recall']:.3f} "
            f"({target_metrics['counts']})"
        )
        print(f"  → {out_path}")


if __name__ == "__main__":
    main()

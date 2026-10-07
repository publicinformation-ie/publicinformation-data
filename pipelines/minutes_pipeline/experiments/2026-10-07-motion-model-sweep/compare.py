#!/usr/bin/env python3
"""Deterministic agreement scorer for the motion-model-sweep experiment.

Run from minutes_pipeline/ (FULLY OFFLINE - no LLM calls):
    uv run python experiments/2026-10-07-motion-model-sweep/compare.py

Reads Task 2 `sample.json` (frozen inputs + old-output baseline motions) and
Task 4 `arms.json` (gold + candidate arms with recorded tokens/cost), scores
every combo against the gold arm with `score_combo`, and writes `results.json`
(`{combos: {key: {text_f1, count_mae, field_acc, failure_rate, mean_cost,
extrapolated_2026}}}`, baseline included under key `"baseline"`).

Scoring contract (spec section 7): normalise `motion_text` (lowercase,
collapse whitespace/punctuation), greedy token-set IoU >= 0.8 (inclusive);
unmatched either side counts as dropped/invented. On matched pairs,
proposer/seconder/status_label compare after the same normalisation.
`meeting_date`/`stated_date` are excluded (owned by `resolve_meeting_date`).
A failed extraction (`motions: null`) scores as a full miss for that file
(spec section 8) and counts toward `failure_rate` - the file is never
dropped. Gold null/missing for a file raises ValueError (never silently
shrinks the denominator); missing tokens/cost raises via Task 4
`aggregate_cost` (never zero-filled).

The baseline arm (old production output) has no measured tokens/cost, so
its `mean_cost`/`extrapolated_2026` are null - zero-filling is prohibited by
the missing-cost rule, and 0.0 would falsely win the cost Pareto. Its text
metrics come from the same matcher/quality path as every combo.
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).parent


def _load_aggregate_cost():
    """Task 4 `aggregate_cost` from sibling extract.py (raises on missing
    cost - the never-zero-fill rule). Loaded by path: the experiment
    directory name contains dashes so it is not package-importable."""
    path = _HERE / "extract.py"
    spec = importlib.util.spec_from_file_location("motion_sweep_extract", path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.aggregate_cost


_aggregate_cost = _load_aggregate_cost()

_SAMPLE_JSON = _HERE / "sample.json"
_ARMS_JSON = _HERE / "arms.json"
_RESULTS_JSON = _HERE / "results.json"

#: Match threshold on token-set IoU (inclusive): spec section 7.
MATCH_IOU_THRESHOLD = 0.8
#: Full pending set the per-file mean cost is extrapolated to (spec 5/7).
FULL_2026_FILES = 2026

#: Fields compared on matched pairs (spec section 7).
FIELD_NAMES = ("proposer", "seconder", "status_label")

_NON_WORD_RE = re.compile(r"[^\w\s]")


def _normalize_tokens(text) -> list:
    """Lowercase word tokens with whitespace/punctuation collapsed.

    Punctuation becomes a separator (so "works." and "works" share a
    token); ``\\w`` keeps unicode letters/digits (Irish fadas, "EUR38").
    Non-string input (None) yields no tokens.
    """
    if not isinstance(text, str):
        return []
    return _NON_WORD_RE.sub(" ", text.lower()).split()


def _token_set(text) -> set:
    return set(_normalize_tokens(text))


def _iou(pred_text, gold_text) -> float:
    """Token-set intersection-over-union; two empty texts agree (1.0)."""
    a, b = _token_set(pred_text), _token_set(gold_text)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def match_motions(pred: list, gold: list) -> list:
    """Greedily align pred motions to gold motions.

    Returns one ``(pred_or_None, gold)`` tuple per gold motion, in gold
    order. Each gold takes the unmatched pred with the highest token-set
    IoU >= 0.8 (ties go to the lowest pred index); gold with no pred at or
    above threshold pairs with None (dropped). Unmatched preds are simply
    never taken (invented) - callers derive their count arithmetically.
    """
    pred = list(pred or [])
    unmatched = set(range(len(pred)))
    pairs = []
    for g in gold or []:
        best, best_score = None, MATCH_IOU_THRESHOLD
        for i in sorted(unmatched):
            score = _iou((pred[i] or {}).get("motion_text"), (g or {}).get("motion_text"))
            if score >= MATCH_IOU_THRESHOLD and (best is None or score > best_score):
                best, best_score = i, score
        if best is None:
            pairs.append((None, g))
        else:
            unmatched.discard(best)
            pairs.append((pred[best], g))
    return pairs


def _norm_field(value):
    """Same normalisation as motion text, for one field value.

    None stays None (None == None is a correct field; None vs a value is a
    miss) - never coerced to "" which would conflate the two.
    """
    if value is None:
        return None
    return " ".join(_normalize_tokens(str(value)))


def _score_text(files: list) -> dict:
    """Quality metrics over per-file ``{"pred": arms-record, "gold": [...]}``.

    Raises ValueError on an empty file list, on gold missing/null/non-list
    for any file (never shrinks the denominator), and on a corrupt pred
    record. A failed pred (``motions: null``) scores as a full miss
    (spec section 8): empty prediction plus one failure.
    """
    if not files:
        raise ValueError("score_combo: no files to score")
    tp = fp = fn = 0
    count_err = 0
    field_ok = field_total = 0
    failures = 0
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError(f"score_combo: corrupt file entry {entry!r}")
        rec = entry.get("pred")
        url = rec.get("file_url", "?") if isinstance(rec, dict) else "?"
        gold = entry.get("gold")
        if not isinstance(gold, list):
            raise ValueError(
                f"score_combo: gold motions missing/null for file {url!r} "
                f"(refusing to shrink the denominator)")
        motions = rec.get("motions") if isinstance(rec, dict) else "corrupt"
        if motions is None:
            failures += 1
            pred_list = []
        elif isinstance(motions, list):
            pred_list = motions
        else:
            raise ValueError(
                f"score_combo: corrupt pred motions for file {url!r}")
        pairs = match_motions(pred_list, gold)
        hits = sum(1 for p, _ in pairs if p is not None)
        tp += hits
        fp += len(pred_list) - hits
        fn += len(gold) - hits
        count_err += abs(len(pred_list) - len(gold))
        for p, g in pairs:
            if p is None:
                continue
            for f in FIELD_NAMES:
                field_total += 1
                if _norm_field((p or {}).get(f)) == _norm_field((g or {}).get(f)):
                    field_ok += 1
    n = len(files)
    denom = 2 * tp + fp + fn
    return {
        # No motion on either side anywhere is perfect agreement.
        "text_f1": round(2 * tp / denom, 4) if denom else 1.0,
        "count_mae": round(count_err / n, 4),
        # No matched pairs means no field comparisons: null, not 0.0.
        "field_acc": round(field_ok / field_total, 4) if field_total else None,
        "failure_rate": round(failures / n, 4),
    }


def score_combo(files: list) -> dict:
    """Score one combo's per-file entries -> results.json metric dict.

    ``files`` is a list of ``{"pred": <arms.json record>, "gold": <gold
    motions list>}``. Cost comes from Task 4 `aggregate_cost` over the
    pred records, so any record missing tokens/cost_usd raises ValueError
    (missing cost is an error, never zero-filled).
    """
    quality = _score_text(files)
    agg = _aggregate_cost([f["pred"] for f in files])
    mean_cost = agg["mean_cost_per_file_usd"]
    return {
        **quality,
        "mean_cost": mean_cost,
        "extrapolated_2026": round(mean_cost * FULL_2026_FILES, 2),
    }


def build_results(sample: dict, arms: dict) -> dict:
    """Score every arms.json combo plus the frozen baseline vs the gold arm.

    Baseline pred motions are Task 2 `sample.json` `old_motions` per file
    (old-output-vs-gold for the report's ΔF1 column), scored by the same
    matcher/quality path; its costs are null (no measured tokens/cost -
    see module docstring).
    """
    order = [f["file_url"] for f in sample["files"]]
    gold_by_url = arms.get("gold") or {}
    gold_motions = {}
    for url in order:
        grec = gold_by_url.get(url)
        motions = grec.get("motions") if isinstance(grec, dict) else None
        if not isinstance(motions, list):
            raise ValueError(
                f"build_results: gold motions missing/null for file {url!r}")
        gold_motions[url] = motions
    combos = {}
    for key in sorted((arms.get("combos") or {})):
        recs = arms["combos"][key]
        files = []
        for url in order:
            rec = recs.get(url) if isinstance(recs, dict) else None
            if not isinstance(rec, dict):
                raise ValueError(
                    f"build_results: combo {key!r} missing record for {url!r}")
            files.append({"pred": rec, "gold": gold_motions[url]})
        combos[key] = score_combo(files)
    baseline_files = []
    for f in sample["files"]:
        url = f["file_url"]
        baseline_files.append({
            "pred": {"file_url": url, "motions": f.get("old_motions"),
                     "stated_date": None, "tokens": None, "cost_usd": None,
                     "error": None},
            "gold": gold_motions[url],
        })
    combos["baseline"] = {
        **_score_text(baseline_files),
        "mean_cost": None,
        "extrapolated_2026": None,
    }
    return {"combos": combos}


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the motion model sweep (offline)")
    parser.add_argument("--sample", default=str(_SAMPLE_JSON))
    parser.add_argument("--arms", default=str(_ARMS_JSON))
    parser.add_argument("--results", default=str(_RESULTS_JSON))
    args = parser.parse_args()

    sample = json.loads(Path(args.sample).read_text())
    arms = json.loads(Path(args.arms).read_text())
    results = build_results(sample, arms)
    Path(args.results).write_text(json.dumps(results, indent=2))

    for key, m in results["combos"].items():
        print(f"{key}: text_f1={m['text_f1']} field_acc={m['field_acc']} "
              f"fail={m['failure_rate']} mean_cost={m['mean_cost']} "
              f"x2026={m['extrapolated_2026']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

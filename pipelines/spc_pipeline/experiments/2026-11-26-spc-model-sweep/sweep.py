#!/usr/bin/env python3
"""Measure candidate models against the hand-labelled gold set.

The runner is deliberately free of network calls in its test path: pass a
``runner`` function (or ``--canned-dir``) and it scores the results. A live
sweep calls ``extract_spc_items`` for each candidate model and needs explicit
permission per the cost rule.

Usage:
    uv run python pipelines/spc_pipeline/experiments/2026-11-26-spc-model-sweep/sweep.py \
        --canned-dir ... --report REPORT.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parent
PIPELINE = EXPERIMENT.parents[1]
REPO_ROOT = PIPELINE.parents[1]
for _path in (PIPELINE, REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
GOLD_PATH = EXPERIMENT / "gold.json"
RENDER_OUTPUT = PIPELINE / "steps/render_spc_minutes/output.json"


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


#: A decision counts as found when the model quotes the same span, allowing for
#: a boundary difference (one quote contains the other). The shorter span must
#: either carry most of the longer one or be a phrase long enough to be
#: specific, so a bare "It was agreed" cannot match everything.
MIN_SPAN_RATIO = 0.5
MIN_SPAN_CHARS = 20
MIN_SPAN_TOKENS = 6


def same_decision(left: str, right: str) -> bool:
    left, right = normalise(left), normalise(right)
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) < MIN_SPAN_CHARS:
        return False
    if not (len(shorter) / len(longer) >= MIN_SPAN_RATIO
            or len(shorter.split()) >= MIN_SPAN_TOKENS):
        return False
    # Token-sequence containment: punctuation is not a word, so a correct
    # prefix followed by a full stop still matches, and "the policy be" still
    # cannot match mid-word.
    shorter_tokens, longer_tokens = _tokens(shorter), _tokens(longer)
    width = len(shorter_tokens)
    return any(longer_tokens[start:start + width] == shorter_tokens
               for start in range(len(longer_tokens) - width + 1))


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def decision_metrics(extracted: list[dict], gold: list[dict]) -> dict:
    """Greedy span-tolerant pairing of extracted decisions to gold decisions."""
    unmatched = list(gold)
    pairs = []
    for decision in extracted:
        for candidate in unmatched:
            if (candidate["item_key"] == decision["item_key"]
                    and same_decision(candidate["decision_text"],
                                      decision["decision_text"])):
                pairs.append((decision, candidate))
                unmatched.remove(candidate)
                break
    precision = len(pairs) / len(extracted) if extracted else 1.0
    recall = len(pairs) / len(gold) if gold else 1.0
    type_correct = sum(1 for decision, candidate in pairs
                       if decision["decision_type"] == candidate["decision_type"])
    type_accuracy = type_correct / len(pairs) if pairs else 1.0
    return {"precision": precision, "recall": recall, "type_accuracy": type_accuracy,
            "matched": len(pairs), "extracted": len(extracted), "gold": len(gold)}


def _is_ancestor(ancestor: str, code: str) -> bool:
    return code.startswith(ancestor + ".")


def topic_metrics(item_topics: list[dict], gold_items: dict[str, dict]) -> dict:
    """Strict primary accuracy plus a hierarchy-tolerant agreement rate.

    COFOG group/class choices (04.5 vs 04.5.1) and a differently ordered list
    are defensible, so agreement counts the gold primary when it appears in
    the model's codes or when the two codes are in an ancestor relation.
    """
    by_key = {entry["item_key"]: entry for entry in item_topics}
    exact = 0
    agreed = 0
    scored = 0
    for item_key, gold in gold_items.items():
        entry = by_key.get(item_key)
        if not entry or entry.get("cofog") is None:
            continue
        scored += 1
        gold_primary = gold["cofog"][0]
        codes = entry["cofog"]
        if codes and codes[0] == gold_primary:
            exact += 1
        if (gold_primary in codes
                or any(_is_ancestor(gold_primary, code) or _is_ancestor(code, gold_primary)
                       for code in codes)):
            agreed += 1
    return {"primary_accuracy": exact / scored if scored else 0.0,
            "agreement": agreed / scored if scored else 0.0,
            "scored": scored, "gold": len(gold_items)}


def score_meeting(result: dict, gold: dict, errors: list[dict],
                  cost_usd: float | None = None) -> dict:
    failed = bool(result.get("extraction_failed"))
    decisions = decision_metrics(result.get("decisions", []), gold.get("decisions", []))
    topics = topic_metrics(result.get("item_topics", []), gold.get("items", {}))
    if failed:
        # A failed extraction produced nothing: it must not look like a model
        # that stayed silent but correct (empty precision is conventionally 1).
        decisions["precision"] = 0.0
        decisions["recall"] = 0.0
        decisions["type_accuracy"] = 0.0
        topics["primary_accuracy"] = 0.0
        topics["agreement"] = 0.0
    verbatim_failures = sum(1 for error in errors
                            if error.get("error_type") == "DecisionNotInSource")
    produced = max(1, len(result.get("decisions", [])))
    return {
        "meeting_id": result["meeting_id"],
        "extraction_failed": failed,
        "decision_precision": round(decisions["precision"], 3),
        "decision_recall": round(decisions["recall"], 3),
        "decision_type_accuracy": round(decisions["type_accuracy"], 3),
        "topic_primary_accuracy": round(topics["primary_accuracy"], 3),
        "topic_agreement": round(topics["agreement"], 3),
        "verbatim_failure_rate": None if failed else round(verbatim_failures / produced, 3),
        "cost_usd": cost_usd,
        "matched": decisions["matched"],
        "extracted": decisions["extracted"],
        "gold": decisions["gold"],
        "topics_scored": topics["scored"],
        "topics_gold": topics["gold"],
    }


def aggregate(meetings: list[dict]) -> dict:
    def mean(field):
        values = [row[field] for row in meetings if row[field] is not None]
        return round(sum(values) / len(values), 3) if values else None

    costs = [row["cost_usd"] for row in meetings if row["cost_usd"] is not None]
    failures = sum(1 for row in meetings if row["extraction_failed"])
    return {
        "extraction_failure_rate": round(failures / len(meetings), 3) if meetings else None,
        "decision_precision": mean("decision_precision"),
        "decision_recall": mean("decision_recall"),
        "decision_type_accuracy": mean("decision_type_accuracy"),
        "topic_primary_accuracy": mean("topic_primary_accuracy"),
        "topic_agreement": mean("topic_agreement"),
        "verbatim_failure_rate": mean("verbatim_failure_rate"),
        "cost_usd_per_meeting": round(sum(costs) / len(costs), 4) if costs else None,
    }


def run_sweep(models: list[str], meetings: list[dict], gold: dict,
              runner, prices: dict | None = None) -> dict:
    """Score each model. ``runner(model, meeting) -> (result, errors, usage)``."""
    report = {"models": []}
    for model in models:
        rows = []
        for meeting in meetings:
            gold_meeting = gold["meetings"].get(meeting["meeting_id"], {})
            result, errors, usage = runner(model, meeting)
            cost = None
            if prices and model in prices and usage:
                price = prices[model]
                cost = ((usage.get("prompt_tokens", 0) / 1_000_000) * price["input"]
                        + (usage.get("completion_tokens", 0) / 1_000_000) * price["output"])
            rows.append(score_meeting(result, gold_meeting, errors, cost))
        report["models"].append({"model": model, "meetings": rows,
                                 "aggregate": aggregate(rows)})
    return report


#: Set once the user agrees a model; the report and the step README then carry
#: the same choice.
DECISION_MODEL: str | None = "opencode-go/deepseek-v4.1-flash"
DECISION_THRESHOLDS = (
    "decision recall >= 0.90, decision type accuracy >= 0.90, "
    "topic agreement >= 0.75, verbatim failure rate = 0, extraction failure rate = 0"
)


def render_report(report: dict) -> str:
    lines = [
        "# SPC model sweep",
        "",
        "Candidates scored against the hand-labelled gold set for the six Meath "
        "Transportation and Urban Regeneration SPC meetings (February 2025 to "
        "May 2026). Every call was made once per meeting per model and cached; "
        "re-scoring is offline and free.",
        "",
        "## Method",
        "",
        "- **Decisions.** A gold decision is matched by a same-item decision "
        "whose quote is the same span, allowing a boundary difference: one "
        "quote contains the other and the shorter span is at least half the "
        "longer or six words long. Pairing is greedy, so each gold decision "
        "matches once. Precision and recall follow from that pairing.",
        "- **Decision type** is scored over the matched pairs.",
        "- **Topics.** *Strict* requires the same primary COFOG code. "
        "*Hierarchy-tolerant agreement* also accepts the gold primary appearing "
        "anywhere in the model's list, or a group/class relation (04.5 vs "
        "04.5.1), because both are defensible readings of the item.",
        "- **Verbatim failure rate** is the share of produced decisions the "
        "quote check rejected. **Extraction failure rate** is the share of "
        "meetings whose response violated the schema or its echoed context; a "
        "failed meeting scores zero, never a silent pass.",
        "- **Cost** is a deterministic chars/4 token estimate at the prices in "
        "`prices.json` (repo-recorded, possibly stale). It ranks models "
        "consistently but is not billable.",
        "",
        "## Caveats",
        "",
        "- The gold set was labelled from the minutes by hand and is a floor, "
        "not a ceiling: genuine agreements the labeller did not list count "
        "against precision. Read precision as agreement with the hand labels.",
        "- Six meetings is a small sample. Differences of a few points are "
        "within noise and should not decide a model on their own.",
        "- Procedural items (for example \"Matters Arising\") are labelled "
        "`01.1.1`; models often prefer the substantive transport code. That is "
        "a labelling judgment, so topic numbers understate model quality.",
        "",
    ]
    for model in report["models"]:
        agg = model["aggregate"]
        lines += [
            f"## {model['model']}", "",
            "| Metric | Mean |", "|---|---:|",
            f"| Decision precision | {agg['decision_precision']} |",
            f"| Decision recall | {agg['decision_recall']} |",
            f"| Decision type accuracy | {agg['decision_type_accuracy']} |",
            f"| Topic primary accuracy (strict) | {agg['topic_primary_accuracy']} |",
            f"| Topic agreement (hierarchy-tolerant) | {agg['topic_agreement']} |",
            f"| Verbatim failure rate | {agg['verbatim_failure_rate']} |",
            f"| Extraction failure rate | {agg['extraction_failure_rate']} |",
            f"| Cost per meeting (USD) | {agg['cost_usd_per_meeting']} |",
            "", "| Meeting | Precision | Recall | Type | Topics | Verbatim fail | Cost |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for row in model["meetings"]:
            slug = row["meeting_id"].rsplit("/", 1)[-1]
            if row["extraction_failed"]:
                slug += " (failed)"
            lines.append(
                f"| {slug} | {row['decision_precision']} "
                f"| {row['decision_recall']} | {row['decision_type_accuracy']} "
                f"| {row['topic_primary_accuracy']} | {row['verbatim_failure_rate']} "
                f"| {row['cost_usd']} |"
            )
        lines.append("")
    lines += [
        "## Decision",
        "",
        f"Gate: {DECISION_THRESHOLDS}.",
        "",
        (f"Production model: `{DECISION_MODEL}`." if DECISION_MODEL
         else "Production model: pending user agreement."),
        "",
        "The same choice is recorded in `steps/extract_spc_items/README.md`.",
        "",
    ]
    return "\n".join(lines)


def canned_runner(directory: Path):
    """A runner that reads ``<model>/<meeting-slug>.json`` canned responses."""
    def run(model: str, meeting: dict):
        slug = meeting["meeting_id"].rsplit("/", 1)[-1]
        path = Path(directory) / model / f"{slug}.json"
        payload = json.loads(path.read_text())
        return payload["result"], payload.get("errors", []), payload.get("usage")
    return run


def live_runner():
    from steps.extract_spc_items.extraction import (
        PROMPT_VERSION,
        ExtractionFailed,
        build_prompt,
        cache_path,
        extract_meeting,
        load_taxonomy,
        prompt_hash,
    )
    from steps.resolve_attendees.resolving import load_register

    cofog, subdomains = load_taxonomy(PIPELINE)
    register = load_register(PIPELINE / "reference" / "people.json")
    cache = PIPELINE / "cache"

    def run(model, meeting):
        try:
            result, errors = extract_meeting(meeting, cache, register, cofog,
                                             subdomains, model=model)
        except ExtractionFailed as exc:
            # A model that fails one meeting must score as a failure, not
            # abort the whole sweep.
            result = {
                "meeting_id": meeting["meeting_id"],
                "decisions": [],
                "item_topics": [],
                "minutes_approval_discarded": 0,
                "model": model,
                "prompt_version": PROMPT_VERSION,
                "extraction_failed": True,
            }
            errors = [{"error_type": "ExtractionFailed", "error_message": str(exc)}]
        # The backend exposes no usage object, so tokens are the same
        # deterministic chars/4 estimate the motion sweep used: consistent
        # between models, indicative rather than billable.
        system, user = build_prompt(meeting, cofog, subdomains)
        path = cache_path(cache, meeting["source_sha256"], model,
                          prompt_hash(system, user))
        completion_chars = path.stat().st_size if path.exists() else 0
        usage = {
            "prompt_tokens": (len(system) + len(user)) // 4,
            "completion_tokens": completion_chars // 4,
        }
        return result, errors, usage

    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", default=[],
                        help="model id to sweep (repeatable)")
    parser.add_argument("--canned-dir", type=Path,
                        help="read canned responses instead of calling a model")
    parser.add_argument("--prices", type=Path,
                        help="JSON {model: {input, output}} in USD per 1M tokens")
    parser.add_argument("--report", type=Path, default=EXPERIMENT / "REPORT.md")
    args = parser.parse_args()

    gold = json.loads(GOLD_PATH.read_text())
    meetings = json.loads(RENDER_OUTPUT.read_text())["results"]
    if args.canned_dir:
        runner = canned_runner(args.canned_dir)
    else:
        if not args.model:
            print("error: --model is required for a live sweep", file=sys.stderr)
            return 2
        runner = live_runner()
    prices = json.loads(args.prices.read_text()) if args.prices else None
    report = run_sweep(args.model or ["canned"], meetings, gold, runner, prices)
    args.report.write_text(render_report(report), encoding="utf-8")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Offline scorer/report for the prompt A/B probe (prompt_ab.py).

Fully offline. Reads `prompt_ab.jsonl` (one record per prompt x model x file)
and `sample.json`, groups records by prompt, and scores every candidate model
against the gold model **under the same prompt** using the shared
`compare.py` matcher. Emits a per-prompt table plus a modified-vs-production
delta column.

Run from minutes_pipeline/:
    uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab_report.py
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_MINUTES_PIPELINE = _HERE.parent.parent
_REPO_ROOT = _MINUTES_PIPELINE.parent.parent
if str(_MINUTES_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_MINUTES_PIPELINE))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_compare = _load("motion_sweep_compare", _HERE / "compare.py")
_extract = _load("motion_sweep_extract", _HERE / "extract.py")
GOLD_MODEL = _extract.GOLD_MODEL

_SAMPLE_JSON = _HERE / "sample.json"
_DEFAULT_JSONL = _HERE / "prompt_ab.jsonl"


def load_records(path) -> list:
    """Parse the flush log into records (skips blank/corrupt lines)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"no records at {p} - run prompt_ab.py first")
    records = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("key"):
            records.append(rec)
    return records


def _score_cell(gold_by_url: dict, preds: dict, urls: list):
    """Score one (prompt, model) cell over `urls` where both gold and a pred
    record exist; None if nothing is scorable."""
    entries = []
    for url in urls:
        g = gold_by_url.get(url)
        pred = preds.get(url)
        if isinstance(g, list) and isinstance(pred, dict):
            entries.append({"pred": pred, "gold": g})
    if not entries:
        return None
    metrics = _compare.score_combo(entries)
    metrics["n"] = len(entries)
    return metrics


def build_table(sample: dict, records_path) -> dict:
    """Per-prompt tables plus a *paired* modified-minus-production delta.

    Each prompt is scored against gold under the same prompt. Gold failures
    (timeouts) differ per prompt, so the two prompts can cover different file
    sets; the paired delta is therefore restricted to files with gold under
    BOTH prompts, making the prompt the only variable.
    """
    order = [f["file_url"] for f in sample.get("files", [])]
    records = load_records(records_path)
    prompts = sorted({r["prompt"] for r in records})
    gold_by_prompt = {p: {r["file_url"]: r.get("motions") for r in records
                          if r["prompt"] == p and r["model"] == GOLD_MODEL}
                      for p in prompts}
    preds_by: dict = {}
    for r in records:
        if r["model"] != GOLD_MODEL:
            preds_by.setdefault((r["prompt"], r["model"]), {})[r["file_url"]] = r
    models = sorted({m for (_p, m) in preds_by})

    table: dict = {}
    for prompt in prompts:
        table[prompt] = {}
        for model in models:
            cell = _score_cell(gold_by_prompt[prompt],
                               preds_by.get((prompt, model), {}), order)
            if cell:
                table[prompt][model] = cell

    common = [url for url in order
              if all(isinstance(gold_by_prompt[p].get(url), list)
                     for p in prompts)]
    paired: dict = {"n": len(common), "production": {}, "modified": {},
                    "delta": {}}
    for model in models:
        prod_cell = _score_cell(gold_by_prompt.get("production", {}),
                                preds_by.get(("production", model), {}), common)
        mod_cell = _score_cell(gold_by_prompt.get("exclude_procedural", {}),
                               preds_by.get(("exclude_procedural", model), {}),
                               common)
        if prod_cell and mod_cell:
            paired["production"][model] = prod_cell
            paired["modified"][model] = mod_cell
            paired["delta"][model] = {
                "text_f1": round(mod_cell["text_f1"] - prod_cell["text_f1"], 4),
                "field_acc": _delta(mod_cell.get("field_acc"),
                                    prod_cell.get("field_acc")),
                "count_mae": _delta(mod_cell.get("count_mae"),
                                    prod_cell.get("count_mae")),
            }
    table["paired"] = paired
    table["delta"] = paired["delta"]
    return table


def _delta(a, b):
    return None if a is None or b is None else round(a - b, 4)


def _fmt(v, places=4):
    return "n/a" if v is None else f"{v:.{places}f}"


def _print_prompt(prompt: str, rows: dict):
    print(f"\n== {prompt} (scored vs gold under the same prompt) ==")
    header = (f"{'model':<44}{'n':>3}{'text-F1':>9}{'field-acc':>10}"
              f"{'cnt-mae':>9}{'fail':>7}{'mean_cost':>12}")
    print(header)
    print("-" * len(header))
    for model, m in sorted(rows.items(),
                           key=lambda kv: kv[1].get("mean_cost") or 0.0):
        print(f"{model:<44}{m.get('n', 0):>3}{_fmt(m.get('text_f1')):>9}"
              f"{_fmt(m.get('field_acc')):>10}{_fmt(m.get('count_mae')):>9}"
              f"{_fmt(m.get('failure_rate')):>7}"
              f"{(m.get('mean_cost') or 0.0):>12.6f}")


def report(table: dict) -> None:
    for prompt in sorted(k for k in table if k not in ("delta", "paired")):
        _print_prompt(prompt, table[prompt])
    paired = table.get("paired") or {}
    delta = paired.get("delta") or {}
    if delta:
        n = paired.get("n", 0)
        print(f"\n== Paired: modified - production, same {n} files "
              f"(gold under each prompt) ==")
        header = (f"{'model':<44}{'prod-F1':>9}{'mod-F1':>9}{'ΔF1':>9}"
                  f"{'prod-acc':>10}{'mod-acc':>10}{'Δacc':>9}{'Δmae':>9}")
        print(header)
        print("-" * len(header))
        for model, d in sorted(delta.items()):
            p = paired["production"][model]
            m = paired["modified"][model]
            print(f"{model:<44}{_fmt(p.get('text_f1')):>9}"
                  f"{_fmt(m.get('text_f1')):>9}{_fmt(d.get('text_f1')):>9}"
                  f"{_fmt(p.get('field_acc')):>10}"
                  f"{_fmt(m.get('field_acc')):>10}{_fmt(d.get('field_acc')):>9}"
                  f"{_fmt(d.get('count_mae')):>9}")
    print("\nCaveat: gold is a model reference under the same prompt, not human "
          "ground truth; the paired delta restricts to files with gold under "
          "BOTH prompts. ΔF1 < 0 means the exclusion clause lowered agreement "
          "with that prompt's own gold.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prompt A/B report (offline)")
    parser.add_argument("--sample", default=str(_SAMPLE_JSON))
    parser.add_argument("--records", default=str(_DEFAULT_JSONL))
    args = parser.parse_args()
    sample = json.loads(Path(args.sample).read_text())
    table = build_table(sample, args.records)
    report(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())

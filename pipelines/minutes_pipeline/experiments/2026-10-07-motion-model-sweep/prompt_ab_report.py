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


def build_table(sample: dict, records_path) -> dict:
    """{prompt: {model: metrics-with-n}} for each candidate vs same-prompt gold,
    plus {"delta": {model: {"text_f1": modified - production, ...}}}."""
    order = [f["file_url"] for f in sample.get("files", [])]
    records = load_records(records_path)
    prompts = sorted({r["prompt"] for r in records})
    table: dict = {}
    for prompt in prompts:
        gold = {r["file_url"]: r.get("motions") for r in records
                if r["prompt"] == prompt and r["model"] == GOLD_MODEL}
        models = sorted({r["model"] for r in records
                         if r["prompt"] == prompt and r["model"] != GOLD_MODEL})
        table[prompt] = {}
        for model in models:
            preds = {r["file_url"]: r for r in records
                     if r["prompt"] == prompt and r["model"] == model}
            entries = []
            for url in order:
                g = gold.get(url)
                pred = preds.get(url)
                if isinstance(g, list) and isinstance(pred, dict):
                    entries.append({"pred": pred, "gold": g})
            if entries:
                metrics = _compare.score_combo(entries)
                metrics["n"] = len(entries)
                table[prompt][model] = metrics

    prod = table.get("production", {})
    modified = table.get("exclude_procedural", {})
    delta = {}
    for model in sorted(set(prod) & set(modified)):
        p, m = prod[model], modified[model]
        f1 = (round(m["text_f1"] - p["text_f1"], 4)
              if m["text_f1"] is not None and p["text_f1"] is not None else None)
        fa = (round(m["field_acc"] - p["field_acc"], 4)
              if m["field_acc"] is not None and p["field_acc"] is not None else None)
        delta[model] = {"text_f1": f1, "field_acc": fa}
    table["delta"] = delta
    return table


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
    for prompt in sorted(k for k in table if k != "delta"):
        _print_prompt(prompt, table[prompt])
    delta = table.get("delta") or {}
    if delta:
        print("\n== modified (exclude_procedural) - production ==")
        print(f"{'model':<44}{'Δtext-F1':>10}{'Δfield-acc':>12}")
        print("-" * 66)
        for model, d in sorted(delta.items()):
            print(f"{model:<44}{_fmt(d.get('text_f1')):>10}"
                  f"{_fmt(d.get('field_acc')):>12}")
    print("\nCaveat: n is the number of files scored for that cell; gold is the "
          "reference under the same prompt (not a human ground truth).")


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

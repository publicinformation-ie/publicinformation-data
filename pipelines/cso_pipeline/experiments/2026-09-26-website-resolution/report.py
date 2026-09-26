#!/usr/bin/env python3
"""Print a markdown comparison table of all experiment result files."""
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
HAIKU_IN, HAIKU_OUT, HAIKU_SEARCH = 1.0 / 1e6, 5.0 / 1e6, 10.0 / 1000
APIFY_PAGE = 0.0045


def _fmt(x):
    return "—" if x is None else f"{x:.2f}"


def main():
    print("| approach | judge | n | own cov | own prec | no-own P | no-own R | false not_found | $ |")
    print("|---|---|---|---|---|---|---|---|---|")
    for path in sorted(RESULTS.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        s, sp = d["summary"], d["spend"]
        dollars = (sp["haiku_input_tokens"] * HAIKU_IN + sp["haiku_output_tokens"] * HAIKU_OUT
                   + sp["haiku_searches"] * HAIKU_SEARCH + sp["apify_paid_queries"] * APIFY_PAGE)
        print(f"| {d['approach']} | {d['judge']} | {s['n']} | {_fmt(s['own_coverage'])} | "
              f"{_fmt(s['own_precision'])} | {_fmt(s['no_own_precision'])} | {_fmt(s['no_own_recall'])} | "
              f"{_fmt(s['false_not_found_rate'])} | {dollars:.2f} |")


if __name__ == "__main__":
    main()

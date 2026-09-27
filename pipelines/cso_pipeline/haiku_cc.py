#!/usr/bin/env python3
"""Operator CLI for the Claude Code Haiku exchange (spec §11). Run from the repo root:

    uv run python pipelines/cso_pipeline/haiku_cc.py pending search --batch 5
    uv run python pipelines/cso_pipeline/haiku_cc.py ingest search
    uv run python pipelines/cso_pipeline/haiku_cc.py pending judge --batch 20
    uv run python pipelines/cso_pipeline/haiku_cc.py ingest judge

`pending` prints one line of prompt-file paths per subagent batch. Dispatch one
`haiku-oracle` agent per line (see pipelines/cso_pipeline/README.md), then `ingest`.
"""
import argparse
import json
import sys
from pathlib import Path

_CSO = Path(__file__).resolve().parent
sys.path.insert(0, str(_CSO.parents[1] / "src"))

from lib.haiku_cc_exchange import (exchange_dir, ingest_judge, ingest_search,  # noqa: E402
                                   pending, search_cache)
from lib.response_cache import ResponseCache  # noqa: E402

CACHE_DIR = _CSO / "cache"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pending", "ingest"])
    ap.add_argument("kind", choices=["search", "judge"])
    ap.add_argument("--batch", type=int, default=5, help="pending: prompt files per printed line")
    args = ap.parse_args(argv)
    ex = exchange_dir(CACHE_DIR)
    prompts, answers = ex / f"{args.kind}_prompts", ex / f"{args.kind}_answers"
    if args.command == "pending":
        todo = pending(prompts, answers)
        print(f"# {len(todo)} pending; answers go in {answers}")
        for i in range(0, len(todo), args.batch):
            print(" ".join(str(p) for p in todo[i:i + args.batch]))
        return
    answers.mkdir(parents=True, exist_ok=True)
    if args.kind == "search":
        result = ingest_search(prompts, answers, search_cache(CACHE_DIR))
    else:
        result = ingest_judge(prompts, answers, ResponseCache(CACHE_DIR / "judge"))
    print(json.dumps(result))


if __name__ == "__main__":
    main()

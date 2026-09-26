#!/usr/bin/env python3
"""Bridge between Claude Code Haiku subagents and the experiment caches.

The API path (lib.haiku_search / lib.website_judge) needs ANTHROPIC_API_KEY. This
bridge lets Claude Code Haiku subagents answer the *same* prompts instead:
run_experiment.py exports prompt files, subagents write answer files, and this
script ingests them into caches shaped like the API path's, so interpret_haiku,
verify, decide and score run unchanged. Invalid answers are never cached, so
they surface as pending and get re-dispatched.

Run from the repo root:
    uv run python pipelines/cso_pipeline/experiments/2026-09-26-website-resolution/haiku_cc_bridge.py pending search --batch 5
    uv run python .../haiku_cc_bridge.py ingest search
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CSO = _HERE.parents[1]
_REPO = _CSO.parents[1]
sys.path.insert(0, str(_REPO / "src"))

from lib.haiku_search import HAIKU_MODEL  # noqa: E402
from lib.response_cache import ResponseCache  # noqa: E402
from lib.website_judge import parse_judge_response  # noqa: E402

SOURCE = "claude_code_subagent"
CACHE_DIR = _CSO / "cache"
EXCHANGE = CACHE_DIR / "haiku_cc_exchange"
MAX_SEARCHES = 3  # mirrors lib.haiku_search.WEB_SEARCH_TOOL["max_uses"]
_UNPARSED = ("unparsable response", "invalid json")


def _read(path: Path):
    """Read a subagent answer file; None if unreadable (answers are untrusted)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_spec(path: Path) -> dict:
    """Read one of our own prompt files; a corrupt one is a bug, so let it raise."""
    return json.loads(path.read_text(encoding="utf-8"))


def answer_to_raw(prompt: str, answer: dict) -> dict:
    queries = [q for q in answer.get("queries") or [] if isinstance(q, str)]
    seen = [{"type": "web_search_result", "url": r["url"], "title": r.get("title") or ""}
            for r in answer.get("results_seen") or []
            if isinstance(r, dict) and isinstance(r.get("url"), str)]
    return {"model": HAIKU_MODEL, "source": SOURCE, "prompt": prompt, "queries": queries,
            "responses": [{"stop_reason": "end_turn",
                           "content": [{"type": "web_search_tool_result", "content": seen},
                                       {"type": "text", "text": str(answer.get("final_text") or "")}],
                           "usage": {"input_tokens": 0, "output_tokens": 0,
                                     "server_tool_use": {"web_search_requests": len(queries)}}}]}


def pending(prompts_dir: Path, answers_dir: Path) -> list[Path]:
    return [p for p in sorted(Path(prompts_dir).glob("*.json"))
            if not (Path(answers_dir) / p.name).exists()]


def ingest_search(prompts_dir: Path, answers_dir: Path, cache: ResponseCache) -> dict:
    out = {"ingested": 0, "missing": [], "invalid": [], "over_budget": []}
    for p in sorted(Path(prompts_dir).glob("*.json")):
        spec = _read_spec(p)
        pid = spec["public_body_id"]
        a_path = Path(answers_dir) / p.name
        if not a_path.exists():
            out["missing"].append(pid)
            continue
        answer = _read(a_path)
        if not isinstance(answer, dict) or answer.get("public_body_id") != pid:
            out["invalid"].append(pid)
            continue
        if len(answer.get("queries") or []) > MAX_SEARCHES:
            out["over_budget"].append(pid)
        cache.put(spec["key"], answer_to_raw(spec["prompt"], answer))
        out["ingested"] += 1
    return out


def ingest_judge(prompts_dir: Path, answers_dir: Path, cache: ResponseCache) -> dict:
    out = {"ingested": 0, "missing": [], "invalid": []}
    for p in sorted(Path(prompts_dir).glob("*.json")):
        spec = _read_spec(p)
        key = spec["key"]
        a_path = Path(answers_dir) / p.name
        if not a_path.exists():
            out["missing"].append(key)
            continue
        answer = _read(a_path)
        if not isinstance(answer, dict) or answer.get("key") != key:
            out["invalid"].append(key)
            continue
        text = str(answer.get("text") or "")
        label, rationale = parse_judge_response(text)
        if label == "unsure" and (rationale in _UNPARSED or rationale.startswith("unknown label")):
            out["invalid"].append(key)
            continue
        cache.put(key, {"result": {"label": label, "rationale": rationale, "judge": spec["backend"]},
                        "source": SOURCE, "raw_text": text})
        out["ingested"] += 1
    return out


_DIRS = {"search": ("search_prompts", "search_answers", CACHE_DIR / "haiku_cc"),
         "judge": ("judge_prompts", "judge_answers", CACHE_DIR / "judge")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["pending", "ingest"])
    ap.add_argument("kind", choices=["search", "judge"])
    ap.add_argument("--batch", type=int, default=5, help="pending: prompt files per printed line")
    args = ap.parse_args()
    p_name, a_name, cache_dir = _DIRS[args.kind]
    prompts, answers = EXCHANGE / p_name, EXCHANGE / a_name
    if args.command == "pending":
        todo = pending(prompts, answers)
        print(f"# {len(todo)} pending; answers go in {answers}")
        for i in range(0, len(todo), args.batch):
            print(" ".join(str(p) for p in todo[i:i + args.batch]))
        return
    answers.mkdir(parents=True, exist_ok=True)
    fn = ingest_search if args.kind == "search" else ingest_judge
    print(json.dumps(fn(prompts, answers, ResponseCache(cache_dir))))


if __name__ == "__main__":
    main()

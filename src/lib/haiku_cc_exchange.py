"""Exchange files between pipeline code and Claude Code Haiku subagents (spec §11).

No Anthropic API is ever called. Pipeline code writes prompt files, the main Claude
Code session dispatches `haiku-oracle` subagents that write answer files, and
ingest_* validates the answers into the caches that pipeline steps read. Invalid
answers are never cached, so their bodies stay pending and get re-dispatched.

Layout under <cache_dir>/haiku_cc_exchange/: search_prompts/, search_answers/,
judge_prompts/, judge_answers/. An answer has the same filename as its prompt.
"""
import json
from pathlib import Path

from lib.haiku_search import HAIKU_MODEL, build_search_prompt
from lib.response_cache import ResponseCache
from lib.website_judge import parse_judge_response

SOURCE = "claude_code_subagent"
CC_JUDGE = "haiku-cc"  # judge backend label for subagent verdicts
SEARCH_NAMESPACE = "haiku_cc"
MAX_SEARCHES = 3  # per body; enforced by the dispatch instruction, flagged at ingest
_UNPARSED = ("unparsable response", "invalid json")


def exchange_dir(cache_dir) -> Path:
    return Path(cache_dir) / "haiku_cc_exchange"


def search_key(body) -> str:
    return ResponseCache.key(SEARCH_NAMESPACE, HAIKU_MODEL, build_search_prompt(body))


def search_cache(cache_dir) -> ResponseCache:
    return ResponseCache(Path(cache_dir) / SEARCH_NAMESPACE)


def write_search_prompt(body, prompts_dir) -> Path:
    prompts_dir = Path(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    path = prompts_dir / f"{body['public_body_id']}.json"
    spec = {"public_body_id": body["public_body_id"], "name": body.get("name"),
            "key": search_key(body), "prompt": build_search_prompt(body)}
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


class JudgePromptRecorder:
    """A judge api_fn for the haiku-cc backend.

    Saves each uncached prompt as an exchange file, then raises. judge() fails
    closed without caching, so the verdict stays 'unsure' until a subagent answer
    is ingested. `misses` counts every call, so a caller can detect a pending
    verdict even for a prompt already recorded earlier in the run.
    """

    def __init__(self, prompts_dir, backend: str = CC_JUDGE):
        self.prompts_dir = Path(prompts_dir)
        self.backend = backend
        self.recorded: list[str] = []
        self.misses = 0

    def __call__(self, prompt: str) -> str:
        self.misses += 1
        key = ResponseCache.key("judge", self.backend, prompt)
        if key not in self.recorded:
            self.recorded.append(key)
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
            (self.prompts_dir / f"{key}.json").write_text(
                json.dumps({"key": key, "backend": self.backend, "prompt": prompt},
                           ensure_ascii=False, indent=1), encoding="utf-8")
        raise RuntimeError("judge prompt recorded for a Claude Code subagent")


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


def pending(prompts_dir, answers_dir) -> list[Path]:
    return [p for p in sorted(Path(prompts_dir).glob("*.json"))
            if not (Path(answers_dir) / p.name).exists()]


def ingest_search(prompts_dir, answers_dir, cache: ResponseCache) -> dict:
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


def ingest_judge(prompts_dir, answers_dir, cache: ResponseCache) -> dict:
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

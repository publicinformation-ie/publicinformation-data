#!/usr/bin/env python3
"""Model x effort extraction matrix for the motion-model-sweep experiment.

Run from minutes_pipeline/ (MANUAL ONLY - issues live LLM calls):
    uv run python experiments/2026-10-07-motion-model-sweep/extract.py

Calls the real `steps/extract_motions/process.py::extract_one` per
(file, model, effort) with model+effort injected - the exact system/user
prompts production uses - and caches results in `arms.json` (+ `errors.json`).
Re-runs skip completed calls via `cache_key`; `compare.py` and `report.py`
are fully offline. Tests use stubbed `api_fn` only (no live calls in CI).

Binary effort semantics (Rulings G + I): GRID = 5 spec models x {default
(effort=None, thinking enabled), "none" (thinking disabled)} + gold
(`opencode-go/deepseek-v4-pro` at default) = 11 arms x 20 files = 220 live
calls (200 candidate + 20 gold). Gradient levels (low/high/...) are NOT
transmittable on /go (Task 1 probes): Task 3 raises ValueError for them and
`run_combo` converts that into a fail-closed error entry, never propagates.

Cost arithmetic uses the spec's $/M figures per recorded tokens, identical
for both levels of a model. Token counts are deterministic char/4 ESTIMATES
(Task 3's `extract_one` exposes no backend usage object), applied identically
to stubbed and live calls - consistent for Pareto comparison, not billing.
"""
import argparse
import datetime
import hashlib
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

from steps.extract_motions.process import build_user_prompt, extract_one  # noqa: E402

_SAMPLE_JSON = _HERE / "sample.json"
_ARMS_JSON = _HERE / "arms.json"
_ERRORS_JSON = _HERE / "errors.json"

#: Candidate models (spec section 3, live price list 2026-10-07).
MODELS = (
    "opencode-go/gpt-6-luna",
    "opencode-go/muse-spark-1.3-contributor",
    "opencode-go/deepseek-v4.1-flash",
    "opencode-go/glm-5.3-flash",
    "opencode-go/qwen3.8-flash",
)
#: Gold reference model (spec section 3).
GOLD_MODEL = "opencode-go/deepseek-v4-pro"
#: The ONLY implementable effort levels: None = default (thinking enabled,
#: current behaviour), "none" = thinking disabled. Anything else raises
#: ValueError in Task 3 plumbing and fail-closes in run_combo.
EFFORTS = (None, "none")
#: (model, effort) candidate grid: 5 models x 2 levels = 10 combos.
GRID = [(model, effort) for model in MODELS for effort in EFFORTS]
#: Gold arm: pro model at default effort.
GOLD_ARM = (GOLD_MODEL, None)

#: In / Out $/M from the spec table (docs/superpowers/specs/...-design.md #3).
COST_PER_M_USD = {
    "opencode-go/gpt-6-luna": (0.10, 0.50),
    "opencode-go/muse-spark-1.3-contributor": (0.10, 0.20),
    "opencode-go/deepseek-v4.1-flash": (0.15, 0.60),
    "opencode-go/glm-5.3-flash": (0.15, 0.50),
    "opencode-go/qwen3.8-flash": (0.15, 0.47),
    "opencode-go/deepseek-v4-pro": (0.66, 1.98),
}

#: Chars per estimated token (deterministic local heuristic; see module doc).
_CHARS_PER_TOKEN = 4


def combo_key(model: str, effort: str | None) -> str:
    """Arms.json combo label: "<model>@default" or "<model>@none"."""
    return f"{model}@{'default' if effort is None else effort}"


def cache_key(file_url: str, model: str, effort: str | None) -> str:
    """sha256 hex over (file_url, model, effort); None and "none" differ."""
    joined = "\x00".join([file_url, model, repr(effort)])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate for `text` (always >= 1)."""
    return max(1, len(text or "") // _CHARS_PER_TOKEN)


def cost_for(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """USD cost for recorded token counts at the spec $/M rates for `model`.

    Effort-independent: both levels of a model share its rates. Raises
    KeyError on an unknown model (fail closed, never price at a guessed rate).
    """
    price_in, price_out = COST_PER_M_USD[model]
    return prompt_tokens / 1_000_000 * price_in + completion_tokens / 1_000_000 * price_out


def _fail_record(file_url: str, key: str, prompt_tokens: int, model: str,
                 error: str) -> dict:
    """Fail-closed per-file record: motions None + error, cost still recorded.

    The prompt was (or would be) sent, so prompt-side cost is always recorded -
    never zero-filled, never missing.
    """
    tokens = {"prompt": prompt_tokens, "completion": 0, "total": prompt_tokens}
    return {
        "file_url": file_url,
        "cache_key": key,
        "motions": None,
        "stated_date": None,
        "tokens": tokens,
        "cost_usd": cost_for(prompt_tokens, 0, model),
        "error": error,
    }


def _run_one(file: dict, model: str, effort: str | None, api_fn=None) -> dict:
    """Extract one file under one model x effort arm; never raises."""
    file_url = file.get("file_url", "?") if isinstance(file, dict) else "?"
    key = cache_key(file_url, model, effort)
    if model not in COST_PER_M_USD:
        # No spec $/M rate: fail closed with cost None (never a guessed rate;
        # aggregate_cost raises on it downstream).
        return {
            "file_url": file_url, "cache_key": key, "motions": None,
            "stated_date": None, "tokens": None, "cost_usd": None,
            "error": f"KeyError: unknown model {model!r} (no spec $/M rate)",
        }
    try:
        prompt_text = build_user_prompt(file)
    except Exception:
        prompt_text = (file.get("text") if isinstance(file, dict) else "") or ""
    prompt_tokens = estimate_tokens(prompt_text)

    captured: dict = {}

    def _wrapped(system, user, session_id):
        try:
            return api_fn(system, user, session_id)
        except Exception as exc:  # record provenance, then fail closed below
            captured["exc"] = exc
            raise

    try:
        out = extract_one(file, api_fn=_wrapped if api_fn is not None else None,
                          model=model, effort=effort)
    except Exception as exc:
        # Backend failure that escaped extract_json, malformed file, or the
        # Task-3 ValueError for an untransmittable effort level: all fail
        # closed into an error entry (never propagate out of the matrix).
        return _fail_record(file_url, key, prompt_tokens, model,
                            f"{type(exc).__name__}: {exc}")
    if not isinstance(out, dict) or out.get("motions") is None:
        exc = captured.get("exc")
        message = (f"{type(exc).__name__}: {exc}" if exc is not None
                   else "LLM returned unparseable/empty motions JSON")
        return _fail_record(file_url, key, prompt_tokens, model, message)
    completion_tokens = estimate_tokens(json.dumps(out["motions"], ensure_ascii=False))
    tokens = {"prompt": prompt_tokens, "completion": completion_tokens,
              "total": prompt_tokens + completion_tokens}
    return {
        "file_url": file_url,
        "cache_key": key,
        "motions": out["motions"],
        "stated_date": out.get("stated_date"),
        "tokens": tokens,
        "cost_usd": cost_for(prompt_tokens, completion_tokens, model),
        "error": None,
    }


def run_combo(files: list, model: str, effort: str | None = None,
              api_fn=None, cache: dict | None = None) -> dict:
    """Run one model x effort combo over `files` (sample entries).

    Returns {file_url: record} where each record is {file_url, cache_key,
    motions, stated_date, tokens, cost_usd, error}. Per-file exceptions
    (backend failure OR Task-3 ValueError on a bad effort level) become
    fail-closed entries (motions None + error naming the cause), never
    propagate. Cache hits (by `cache_key`) are returned as stored, except a
    cached record missing tokens/cost is treated as stale and recomputed -
    missing cost is an error, never zero-filled.
    """
    results = {}
    for file in files:
        file_url = file.get("file_url", "?") if isinstance(file, dict) else "?"
        if cache is not None:
            hit = cache.get(cache_key(file_url, model, effort))
            if (isinstance(hit, dict) and hit.get("tokens") is not None
                    and hit.get("cost_usd") is not None):
                results[file_url] = hit
                continue
        results[file_url] = _run_one(file, model, effort, api_fn=api_fn)
    return results


def aggregate_cost(records: list) -> dict:
    """Aggregate recorded tokens + cost over per-file records (Task 5 input).

    Raises ValueError on any record missing tokens/cost_usd - missing cost is
    an error, never zero-filled (fail-closed per the plan's Review Focus).
    """
    totals = {"prompt": 0, "completion": 0, "total": 0}
    total_cost = 0.0
    for rec in records:
        tokens = rec.get("tokens") if isinstance(rec, dict) else None
        cost = rec.get("cost_usd") if isinstance(rec, dict) else None
        if (not isinstance(tokens, dict)
                or any(tokens.get(k) is None for k in ("prompt", "completion", "total"))
                or cost is None):
            raise ValueError(
                f"missing tokens/cost on record "
                f"{(rec.get('file_url') if isinstance(rec, dict) else '?')!r}")
        for k in totals:
            totals[k] += tokens[k]
        total_cost += cost
    n = len(records)
    return {
        "files_costed": n,
        "total_tokens": totals,
        "mean_tokens_per_file": {k: round(totals[k] / n, 1) if n else 0.0
                                 for k in totals},
        "total_cost_usd": total_cost,
        "mean_cost_per_file_usd": total_cost / n if n else 0.0,
    }


def _load_cache(arms_path: Path) -> dict:
    """Rebuild {cache_key: record} from an existing arms.json ({} if absent)."""
    if not arms_path.exists():
        return {}
    arms = json.loads(arms_path.read_text())
    cache = {}
    for section in ("gold",):
        for url, rec in (arms.get(section) or {}).items():
            if isinstance(rec, dict) and rec.get("cache_key"):
                cache[rec["cache_key"]] = rec
    for combo_recs in (arms.get("combos") or {}).values():
        for url, rec in (combo_recs or {}).items():
            if isinstance(rec, dict) and rec.get("cache_key"):
                cache[rec["cache_key"]] = rec
    return cache


def run_live(sample: dict, cache: dict | None, api_fn=None) -> tuple:
    """Run gold + full GRID over the sample; returns (gold, combos, errors).

    `api_fn=None` uses the real backend (live spend). Callers pass a stubbed
    `api_fn` only in tests; the manual 220-call run leaves it None.
    """
    files = sample["files"]
    errors = []
    gold_model, gold_effort = GOLD_ARM
    print(f"gold {combo_key(gold_model, gold_effort)}: {len(files)} files")
    gold = run_combo(files, gold_model, gold_effort, api_fn=api_fn, cache=cache)
    for url, rec in gold.items():
        if rec["error"] is not None:
            errors.append({"file_url": url, "combo": "gold",
                           "model": gold_model, "effort": gold_effort,
                           "error": rec["error"]})
    combos = {}
    for model, effort in GRID:
        key = combo_key(model, effort)
        print(f"combo {key}: {len(files)} files")
        recs = run_combo(files, model, effort, api_fn=api_fn, cache=cache)
        combos[key] = recs
        for url, rec in recs.items():
            if rec["error"] is not None:
                errors.append({"file_url": url, "combo": key,
                               "model": model, "effort": effort,
                               "error": rec["error"]})
    return gold, combos, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the motion model x effort matrix (MANUAL: live LLM spend)")
    parser.add_argument("--force", action="store_true",
                        help="Ignore arms.json cache and re-issue all API calls (re-incurs cost)")
    args = parser.parse_args()

    sample = json.loads(_SAMPLE_JSON.read_text())
    cache = {} if args.force else _load_cache(_ARMS_JSON)
    if cache:
        print(f"cache: {len(cache)} records loaded from {_ARMS_JSON.name}")

    gold, combos, errors = run_live(sample, cache)

    stamped = [{"step": "motion-model-sweep-extract",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                **e} for e in errors]
    _ARMS_JSON.write_text(json.dumps({"gold": gold, "combos": combos}, indent=2))
    _ERRORS_JSON.write_text(json.dumps(stamped, indent=2))

    n_files = len(sample["files"])
    n_arms = 1 + len(combos)
    n_ok = sum(1 for rec in gold.values() if rec["error"] is None)
    n_ok += sum(1 for recs in combos.values() for rec in recs.values()
                if rec["error"] is None)
    print(f"Wrote {n_arms} arms x {n_files} files "
          f"({n_ok}/{n_arms * n_files} ok, {len(errors)} errors) to {_ARMS_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

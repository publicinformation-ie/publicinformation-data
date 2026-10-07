#!/usr/bin/env python3
"""Prompt A/B probe for the motion-model-sweep experiment.

Runs one extraction call per (prompt, model, file) over a 10-file sample at
default effort, with two system prompts - the production prompt and a variant
that excludes procedural items - so the effect of the prompt change can be
scored against gold under the matching prompt.

Durability: one JSON line per completed call is appended to `prompt_ab.jsonl`
and flushed+fsynced immediately (under a lock), so a crash loses at most the
in-flight calls; a re-run skips keys already present.

Calls run in parallel (ThreadPoolExecutor, default 6 workers). MANUAL ONLY:
live LLM spend. Production prompt/pipeline are untouched - the variant is
script-local.

Run from minutes_pipeline/:
    uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab.py
    uv run python experiments/2026-10-07-motion-model-sweep/prompt_ab_report.py
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_HERE = Path(__file__).parent
_MINUTES_PIPELINE = _HERE.parent.parent
_REPO_ROOT = _MINUTES_PIPELINE.parent.parent
if str(_MINUTES_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_MINUTES_PIPELINE))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from steps.extract_motions.process import _SYSTEM_PROMPT, build_user_prompt  # noqa: E402
from lib.llm_extract import _call_backend_with_effort  # noqa: E402


def _load_extract():
    """Load sibling extract.py for its tested token/cost/pricing helpers
    (directory name has dashes so it is not package-importable)."""
    path = _HERE / "extract.py"
    spec = importlib.util.spec_from_file_location("motion_sweep_extract", path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_extract = _load_extract()
estimate_tokens = _extract.estimate_tokens
cost_for = _extract.cost_for
COST_PER_M_USD = _extract.COST_PER_M_USD
MODELS = _extract.MODELS
GOLD_MODEL = _extract.GOLD_MODEL

_SAMPLE_JSON = _HERE / "sample.json"
_OUT_JSONL = _HERE / "prompt_ab.jsonl"

#: Files drawn from the frozen sample for this probe (option a: first N).
SAMPLE_SIZE = 10

#: System prompt variant: production plus an explicit procedural exclusion.
EXCLUSION_CLAUSE = (
    " Do NOT extract procedural or administrative items as motions — for "
    "example confirmation or adoption of previous minutes, votes merely to "
    "note correspondence, or routine approvals. Include only substantive "
    "motions."
)

#: prompt name -> system prompt text.
PROMPTS = {
    "production": _SYSTEM_PROMPT,
    "exclude_procedural": _SYSTEM_PROMPT + EXCLUSION_CLAUSE,
}


def record_key(prompt_name: str, model: str, file_url: str) -> str:
    """Stable identity for a (prompt, model, file) call."""
    joined = "\x00".join([prompt_name, model, file_url])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def load_done(jsonl_path) -> set:
    """Keys already present in the flush log (skips blank/corrupt lines)."""
    path = Path(jsonl_path)
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("key"):
            done.add(rec["key"])
    return done


def parse_motions(text):
    """(motions, stated_date, error) from raw model text; mirrors extract_json
    parsing but surfaces the reason instead of swallowing it."""
    if not text:
        return None, None, "empty response"
    data = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        fenced = text.strip()
        if fenced.startswith("```"):
            try:
                data = json.loads(fenced.split("```", 2)[1].lstrip("json").strip())
            except (json.JSONDecodeError, TypeError):
                data = None
    if not isinstance(data, dict):
        return None, None, "unparseable JSON"
    motions = data.get("motions")
    if not isinstance(motions, list):
        return None, data.get("meeting_date"), "no motions list"
    return motions, data.get("meeting_date"), None


def extract_call(prompt_name: str, system_prompt: str, model: str, file: dict,
                 backend) -> dict:
    """Run one (prompt, model, file) call; always returns a record (never raises).

    Unknown (unpriced) models fail closed without a call, so no arm is ever
    costed at a guessed rate.
    """
    file_url = file.get("file_url", "?") if isinstance(file, dict) else "?"
    key = record_key(prompt_name, model, file_url)
    prompt_text = build_user_prompt(file) if isinstance(file, dict) else ""
    prompt_tokens = estimate_tokens(prompt_text)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    base = {"key": key, "prompt": prompt_name, "model": model,
            "file_url": file_url, "timestamp": now}

    if model not in COST_PER_M_USD:
        return {**base, "motions": None, "stated_date": None, "tokens": None,
                "cost_usd": None, "elapsed_s": 0.0,
                "error": f"KeyError: unknown model {model!r} (no spec $/M rate)"}

    started = time.time()
    try:
        text = backend(system_prompt, prompt_text, model, None)
    except Exception as exc:  # noqa: BLE001 - fail closed into the record
        motions, stated_date, error = None, None, f"{type(exc).__name__}: {exc}"
    else:
        motions, stated_date, error = parse_motions(text)
    elapsed = round(time.time() - started, 1)

    if motions is None:
        tokens = {"prompt": prompt_tokens, "completion": 0, "total": prompt_tokens}
        cost = cost_for(prompt_tokens, 0, model)
    else:
        completion = estimate_tokens(json.dumps(motions, ensure_ascii=False))
        tokens = {"prompt": prompt_tokens, "completion": completion,
                  "total": prompt_tokens + completion}
        cost = cost_for(prompt_tokens, completion, model)
    return {**base, "motions": motions, "stated_date": stated_date,
            "tokens": tokens, "cost_usd": cost, "elapsed_s": elapsed,
            "error": error}


def run_ab(files, out_path, *, workers=6, backend=None, prompts=None,
           models=None) -> dict:
    """Run the (prompt x model x file) matrix, flushing each result to
    `out_path` as it completes; skip keys already present (resume)."""
    backend = backend or _call_backend_with_effort
    prompts = prompts or PROMPTS
    models = list(models or MODELS)
    out_path = Path(out_path)
    done = load_done(out_path)

    tasks = [(pn, ptext, m, f)
             for pn, ptext in prompts.items()
             for m in models
             for f in files
             if record_key(pn, m, f.get("file_url", "?")) not in done]
    total = len(prompts) * len(models) * len(files)
    skipped = total - len(tasks)
    if skipped:
        print(f"resume: {skipped}/{total} calls already complete, skipping")

    lock = threading.Lock()
    records = []

    def worker(task):
        pn, ptext, model, f = task
        rec = extract_call(pn, ptext, model, f, backend)
        line = json.dumps(rec, ensure_ascii=False)
        with lock:
            with out_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return rec

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, t): t for t in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            records.append(rec)
            status = "ok" if rec["motions"] is not None else "FAIL"
            print(f"[{i}/{len(tasks)}] {rec['prompt']:18} {rec['model']:42} "
                  f"{status} {rec['elapsed_s']:>6.1f}s", flush=True)

    return {"total": total, "submitted": len(tasks), "skipped": skipped,
            "records": records}


def select_files(sample: dict, size: int = SAMPLE_SIZE) -> list:
    """Option a: the first `size` files of the frozen sample order."""
    return list(sample.get("files", []))[:size]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prompt A/B probe (MANUAL: live LLM spend)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--sample", default=str(_SAMPLE_JSON))
    parser.add_argument("--out", default=str(_OUT_JSONL))
    parser.add_argument("--limit", type=int, default=SAMPLE_SIZE,
                        help="take the first N files of the frozen sample")
    args = parser.parse_args()

    sample = json.loads(Path(args.sample).read_text())
    files = select_files(sample, args.limit)
    print(f"files: {len(files)}  prompts: {len(PROMPTS)}  models: {len(MODELS)} "
          f"-> {len(files) * len(PROMPTS) * len(MODELS)} calls "
          f"({args.workers} workers)")
    summary = run_ab(files, Path(args.out), workers=args.workers)
    ok = sum(1 for r in summary["records"] if r["motions"] is not None)
    print(f"\ndone: {ok}/{summary['submitted']} ok, "
          f"{summary['skipped']} skipped, wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

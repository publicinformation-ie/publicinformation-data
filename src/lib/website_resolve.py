"""Shared resolution core for the CSO website pipeline and its experiment (spec §11).

verify (probe + judge) → decide, with pending holds: a body whose haiku-cc verdict
or Haiku search answer isn't ingested yet stays `pending` instead of being decided
from missing evidence. Caches make re-verifying earlier candidates free.
"""
from functools import partial
from pathlib import Path

from lib.haiku_cc_exchange import CC_JUDGE, JudgePromptRecorder, exchange_dir
from lib.response_cache import ResponseCache
from lib.website_decide import OWN_STATUSES, decide
from lib.website_judge import judge_cascade
from lib.website_probe import probe_url
from lib.website_verify import verify_candidates

PRIMARY_JUDGE = "ollama:deepseek-r1:8b"
REQUIRED_TIERS = ("seed", "haiku_search", "apify_search")
SEARCH_SETTLED = OWN_STATUSES  # after seed, only a verified own site skips the Haiku search
RESIDUE_VARIANTS = {
    "measured": OWN_STATUSES | {"no_own_site", "defunct"},  # what the 2026-09-26 experiment ran
    "not_own": OWN_STATUSES | {"defunct"},  # also send Haiku no_own_site verdicts to Apify
}
SETTLED_BEFORE_APIFY = RESIDUE_VARIANTS["measured"]


def empty_gathered() -> dict:
    return {"candidates": [], "directory_hits": [], "signals": {}, "tiers": [], "pending_reason": None}


def merge_gathered(parts) -> dict:
    out = empty_gathered()
    for p in parts:
        out["candidates"] += p["candidates"]
        out["directory_hits"] += p["directory_hits"]
        out["signals"].update({k: v for k, v in p["signals"].items() if v is not None})
        out["tiers"] += p["tiers"]
        out["pending_reason"] = out["pending_reason"] or p["pending_reason"]
    return out


def make_probe(cache_dir):
    return partial(probe_url, cache=ResponseCache(Path(cache_dir) / "probe"))


def make_judge(cache_dir, *, primary: str = PRIMARY_JUDGE, fallback: str | None = CC_JUDGE):
    """judge_fn plus the recorder that captures haiku-cc prompts with no ingested verdict."""
    recorder = JudgePromptRecorder(exchange_dir(cache_dir) / "judge_prompts", CC_JUDGE)
    judge_fn = partial(judge_cascade, primary=primary, fallback=fallback,
                       primary_fn=recorder if primary == CC_JUDGE else None,
                       fallback_fn=recorder if fallback == CC_JUDGE else None,
                       cache=ResponseCache(Path(cache_dir) / "judge"))
    return judge_fn, recorder


def resolve_body(body, gathered, *, probe_fn, judge_fn, recorder=None, parent_site_url=None,
                 required_tiers=REQUIRED_TIERS, hold_reason=None) -> dict:
    before = recorder.misses if recorder is not None else 0
    verified = verify_candidates(body, gathered["candidates"], probe_fn=probe_fn, judge_fn=judge_fn)
    if recorder is not None and recorder.misses > before:
        hold_reason = "judge_pending"
    return decide(body, verified, signals=gathered["signals"], directory_hits=gathered["directory_hits"],
                  parent_site_url=parent_site_url, tiers_exhausted=gathered["tiers"],
                  required_tiers=required_tiers, pending_reason=gathered["pending_reason"],
                  hold_reason=hold_reason)


def evict_pending(writer) -> int:
    """Drop this step's pending records so this run re-processes them."""
    ids = {r["public_body_id"] for r in writer.results if r.get("website_status") == "pending"}
    if ids:
        writer._evict_keys(ids)
    return len(ids)

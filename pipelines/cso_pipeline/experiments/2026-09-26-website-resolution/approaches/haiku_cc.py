"""Haiku web-search tier answered by Claude Code Haiku subagents (unbilled).

Reads records ingested by haiku_cc_bridge.py from cache/haiku_cc/. Never calls
an API: a body without an ingested answer is reported as haiku_error (pending).
"""
from lib.haiku_search import HAIKU_MODEL, build_search_prompt
from lib.response_cache import ResponseCache
from lib.website_candidates import interpret_haiku

TIERS = ("haiku_search",)
NAMESPACE = "haiku_cc"


def search_key(body) -> str:
    return ResponseCache.key(NAMESPACE, HAIKU_MODEL, build_search_prompt(body))


def prefetch(bodies, ctx):
    cache = ResponseCache(ctx["cache_dir"] / NAMESPACE)
    store = ctx.setdefault("_haiku", {})
    for body in bodies:
        pid = body["public_body_id"]
        first = pid not in store
        raw = cache.get(search_key(body))
        if raw is None:
            store[pid] = {"error": "no subagent answer ingested"}
            continue
        interp = interpret_haiku(raw)
        if first:  # --approach all prefetches this tier twice; count searches once
            ctx["spend"]["haiku_searches"] += interp["search_count"]
        store[pid] = interp


def gather(body, ctx):
    got = ctx.get("_haiku", {}).get(body["public_body_id"])
    if not got or "error" in got:
        return {"candidates": [], "directory_hits": [], "signals": {}, "tiers": [],
                "pending_reason": "haiku_error"}
    return {"candidates": got["candidates"], "directory_hits": got["directory_hits"],
            "signals": got["signals"], "tiers": list(TIERS), "pending_reason": None}

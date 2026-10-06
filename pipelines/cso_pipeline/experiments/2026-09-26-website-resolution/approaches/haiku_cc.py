"""Haiku web-search tier answered by Claude Code Haiku subagents (unbilled).

Reads records ingested by haiku_cc_bridge.py from cache/haiku_cc/. Never calls
an API: a body without an ingested answer is reported as haiku_error (pending).
"""
from lib.haiku_cc_exchange import search_cache, search_key  # noqa: F401  (search_key re-exported for tests)
from lib.website_candidates import interpret_haiku

TIERS = ("haiku_search",)


def prefetch(bodies, ctx):
    cache = search_cache(ctx["cache_dir"])
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
                "pending_reason": "haiku_pending"}
    return {"candidates": got["candidates"], "directory_hits": got["directory_hits"],
            "signals": got["signals"], "tiers": list(TIERS), "pending_reason": None}

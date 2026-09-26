"""Haiku web-search tier (paid, cached)."""
from lib.haiku_search import fetch_raw
from lib.response_cache import ResponseCache
from lib.website_candidates import interpret_haiku

TIERS = ("haiku_search",)


def prefetch(bodies, ctx):
    cache = ResponseCache(ctx["cache_dir"] / "haiku")
    store = ctx.setdefault("_haiku", {})
    for body in bodies:
        try:
            raw, paid = fetch_raw(body, cache, refresh=ctx["refresh"])
        except Exception as e:  # recorded as pending, never as not_found
            store[body["public_body_id"]] = {"error": f"{type(e).__name__}: {e}"}
            continue
        interp = interpret_haiku(raw)
        if paid:
            s = ctx["spend"]
            s["haiku_paid_calls"] += 1
            s["haiku_searches"] += interp["search_count"]
            s["haiku_input_tokens"] += interp["usage"]["input_tokens"]
            s["haiku_output_tokens"] += interp["usage"]["output_tokens"]
        store[body["public_body_id"]] = interp


def gather(body, ctx):
    got = ctx.get("_haiku", {}).get(body["public_body_id"])
    if not got or "error" in got:
        return {"candidates": [], "directory_hits": [], "signals": {}, "tiers": [],
                "pending_reason": "haiku_error"}
    return {"candidates": got["candidates"], "directory_hits": got["directory_hits"],
            "signals": got["signals"], "tiers": list(TIERS), "pending_reason": None}

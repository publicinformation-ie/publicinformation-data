"""Apify Google SERP tier (paid, cached, live-budget guarded). Two query variants per body."""
import re

from lib.apify_search import ApifyBudgetExceeded, cached_search
from lib.response_cache import ResponseCache
from lib.website_candidates import candidates_from_apify_item

TIERS = ("apify_search",)
_SUFFIX_RE = re.compile(r"\s*\b(clg|ltd|limited|dac|plc|teo|teoranta|cpt|uc)\b\.?\s*$", re.I)


def queries_for(body) -> list[str]:
    name = body.get("name", "")
    short = _SUFFIX_RE.sub("", name).strip()
    context = body.get("parent_name") or body.get("government_department") or "Ireland"
    return [f'"{name}" site:.ie', f'"{short}" {context}']


def prefetch(bodies, ctx):
    queries = [q for b in bodies for q in queries_for(b)]
    try:
        items, paid = cached_search(queries, ResponseCache(ctx["cache_dir"] / "apify"),
                                    refresh=ctx["refresh"])
    except ApifyBudgetExceeded as e:
        print(f"Apify budget guard: {e}")
        ctx["_apify_items"] = None
        return
    ctx["spend"]["apify_paid_queries"] += paid
    ctx["_apify_items"] = items


def gather(body, ctx):
    items = ctx.get("_apify_items")
    if items is None:
        return {"candidates": [], "directory_hits": [], "signals": {}, "tiers": [],
                "pending_reason": "apify_budget"}
    cands, hits = [], []
    for q in queries_for(body):
        c, h = candidates_from_apify_item(items.get(q))
        cands += c
        hits += h
    return {"candidates": cands, "directory_hits": hits, "signals": {}, "tiers": list(TIERS),
            "pending_reason": None}

"""Interpret raw search responses into website candidates and directory evidence.

Kept separate from the fetch layer so cached raw responses can be re-interpreted
with better logic later at no cost.
"""
from lib.website_domains import listing_kind, registrable_domain


def candidates_from_apify_item(item, origin: str = "apify_search"):
    candidates, hits, seen = [], [], set()
    for r in (item or {}).get("organicResults", []) or []:
        url = r.get("url")
        if not url:
            continue
        domain = registrable_domain(url)
        kind = listing_kind(url)
        if kind:
            hits.append({"domain": domain, "url": url, "title": r.get("title", ""),
                         "snippet": r.get("description", ""), "kind": kind})
            continue
        if not domain or domain in seen:
            continue
        seen.add(domain)
        candidates.append({"url": url, "origin": origin, "rank": r.get("position"),
                           "title": r.get("title", ""), "snippet": r.get("description", "")})
    return candidates, hits

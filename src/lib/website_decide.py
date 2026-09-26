"""Decision rules: verified candidates + evidence -> website_status and output fields (spec §6.5)."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from lib.website_domains import has_dissolution_marker, registrable_domain, root_url, site_key

OWN_STATUSES = {"own_site", "own_site_blocked"}
_RECHECK_DAYS = {"own_site": 90, "own_site_blocked": 180, "no_own_site": 180,
                 "defunct": 180, "not_found": 180}


def canonical_official_url(url: str) -> str:
    return url if registrable_domain(url) == "gov.ie" else root_url(url)


def decide(body, verified, *, signals=None, directory_hits=None, parent_site_url=None,
           tiers_exhausted=(), required_tiers=("seed",), pending_reason=None, now=None) -> dict:
    signals = signals or {}
    directory_hits = directory_hits or []
    now = now or datetime.now(timezone.utc)
    has_parent = bool(body.get("parent_id") or body.get("parent_name"))
    official = effective = kind = parent_id = None
    method = judge = None

    own = next((c for c in verified if c.get("judge_label") == "own_site"), None)
    blocked_origins = defaultdict(set)
    blocked_first = {}
    for c in verified:
        if c.get("probe") == "blocked":
            d = site_key(c["url"])
            blocked_origins[d].add(c["origin"])
            blocked_first.setdefault(d, c)
    blocked = next((blocked_first[d] for d, o in blocked_origins.items() if len(o) >= 2), None)

    defunct = any(has_dissolution_marker(f"{h.get('title', '')} {h.get('snippet', '')}")
                  for h in directory_hits) or \
        (signals.get("defunct") == "yes" and bool(signals.get("defunct_source")))
    parent_evidence = (any(c.get("judge_label") == "parent_site" for c in verified)
                       or signals.get("has_own_site") == "no"
                       or bool(directory_hits))

    if own:
        status, method, judge = "own_site", own["origin"], own.get("judge")
        official = effective = canonical_official_url(own.get("final_url") or own["url"])
        kind = "own"
    elif blocked:
        status, method, judge = "own_site_blocked", blocked["origin"], "none"
        official = effective = canonical_official_url(blocked["url"])
        kind = "own"
    elif defunct:
        status = "defunct"
    elif has_parent and parent_evidence:
        status = "no_own_site"
        if parent_site_url:
            effective, kind, parent_id = parent_site_url, "parent", body.get("parent_id")
            method = "parent_inherit"
    elif set(required_tiers) <= set(tiers_exhausted):
        status = "not_found"
    else:
        status = "pending"
        pending_reason = pending_reason or "not_yet_searched"

    recheck = None
    if status in _RECHECK_DAYS:
        recheck = (now + timedelta(days=_RECHECK_DAYS[status])).date().isoformat()
    return {
        "website_status": status,
        "official_website_url": official,
        "effective_website_url": effective,
        "website_url_kind": kind,
        "parent_public_body_id": parent_id,
        "website_resolution": {
            "status": status, "method": method, "judge": judge,
            "sources": sorted({c["origin"] for c in verified}),
            "candidates_tried": verified,
            "directory_hits": directory_hits,
            "signals": signals,
            "tiers_exhausted": list(tiers_exhausted),
            "pending_reason": pending_reason if status == "pending" else None,
            "checked_at": now.isoformat(),
            "recheck_after": recheck,
        },
    }

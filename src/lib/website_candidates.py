"""Interpret raw search responses into website candidates and directory evidence.

Kept separate from the fetch layer so cached raw responses can be re-interpreted
with better logic later at no cost.
"""
import json
import re

from lib.website_domains import listing_kind, registrable_domain, site_key


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
        key = site_key(url)
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append({"url": url, "origin": origin, "rank": r.get("position"),
                           "title": r.get("title", ""), "snippet": r.get("description", "")})
    return candidates, hits


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_SIGNAL_KEYS = ("has_own_site", "parent_site", "defunct", "defunct_source")


def _last_json(text: str) -> dict:
    m = _JSON_RE.search(text or "")
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def interpret_haiku(raw: dict) -> dict:
    responses = raw.get("responses") or []
    result_urls, hits, seen_hits = [], [], set()
    search_count, usage = 0, {"input_tokens": 0, "output_tokens": 0}
    for resp in responses:
        u = resp.get("usage") or {}
        usage["input_tokens"] += u.get("input_tokens") or 0
        usage["output_tokens"] += u.get("output_tokens") or 0
        search_count += (u.get("server_tool_use") or {}).get("web_search_requests") or 0
        for block in resp.get("content") or []:
            if block.get("type") != "web_search_tool_result":
                continue
            content = block.get("content")
            if not isinstance(content, list):  # error object
                continue
            for r in content:
                url = r.get("url")
                if not url:
                    continue
                result_urls.append(url)
                kind = listing_kind(url)
                if kind and url not in seen_hits:
                    seen_hits.add(url)
                    hits.append({"domain": registrable_domain(url), "url": url,
                                 "title": r.get("title", ""), "snippet": "", "kind": kind})

    text = ""
    if responses:
        text = "".join(b.get("text", "") for b in responses[-1].get("content") or []
                       if b.get("type") == "text")
    data = _last_json(text)
    signals = {k: (str(data[k]) if data.get(k) not in (None, "") else None) for k in _SIGNAL_KEYS}

    cited = {registrable_domain(u) for u in result_urls}
    candidates, rejected = [], []
    own = data.get("own_site")
    if isinstance(own, str) and own.startswith("http") and not listing_kind(own):
        if registrable_domain(own) in cited:
            candidates.append({"url": own, "origin": "haiku_search", "rank": None,
                               "title": "", "snippet": data.get("notes", "") or ""})
        else:
            rejected.append(own)
    return {"candidates": candidates, "directory_hits": hits, "signals": signals,
            "rejected_uncited": rejected, "search_count": search_count, "usage": usage}

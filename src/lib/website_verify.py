"""Probe and judge candidate URLs in priority order, stopping at the first own site."""
from lib.website_domains import listing_kind, registrable_domain


def verify_candidates(body: dict, candidates: list[dict], *, probe_fn, judge_fn) -> list[dict]:
    out, probed_domains = [], set()
    for cand in candidates:
        url = cand["url"]
        if listing_kind(url):
            out.append({**cand, "probe": "skipped", "final_url": None,
                        "judge_label": "directory", "judge": "rule"})
            continue
        domain = registrable_domain(url)
        if domain in probed_domains:
            continue
        probed_domains.add(domain)
        probe = probe_fn(url)
        row = {**cand, "probe": probe["outcome"], "final_url": probe.get("final_url"),
               "judge_label": None, "judge": None}
        if probe["outcome"] == "ok":
            verdict = judge_fn(body, probe.get("final_url") or url, probe.get("evidence"))
            row["judge_label"], row["judge"] = verdict["label"], verdict["judge"]
        out.append(row)
        if row["judge_label"] == "own_site":
            break
    return out

"""Probe and judge candidate URLs in priority order, stopping at the first own site."""
from lib.website_domains import listing_kind, site_key


def verify_candidates(body: dict, candidates: list[dict], *, probe_fn, judge_fn) -> list[dict]:
    out, probed = [], {}
    for cand in candidates:
        url = cand["url"]
        if listing_kind(url):
            out.append({**cand, "probe": "skipped", "final_url": None,
                        "judge_label": "directory", "judge": "rule"})
            continue
        domain = site_key(url)
        if domain in probed:
            # Same domain already probed: carry this candidate's own origin forward
            # (needed for own_site_blocked, which requires >=2 independent origins on
            # one domain) without re-probing or re-judging it.
            prior = probed[domain]
            row = {**cand, "probe": prior["probe"], "final_url": prior["final_url"],
                   "judge_label": prior["judge_label"], "judge": prior["judge"]}
            out.append(row)
            if row["judge_label"] == "own_site":
                break
            continue
        probe = probe_fn(url)
        row = {**cand, "probe": probe["outcome"], "final_url": probe.get("final_url"),
               "judge_label": None, "judge": None}
        if probe["outcome"] == "ok":
            verdict = judge_fn(body, probe.get("final_url") or url, probe.get("evidence"))
            row["judge_label"], row["judge"] = verdict["label"], verdict["judge"]
        probed[domain] = row
        out.append(row)
        if row["judge_label"] == "own_site":
            break
    return out

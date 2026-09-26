"""Seed tier: gov.ie + foi.gov.ie + prior verified URL + domain guesses. Free."""
from lib.domain_guess import guess_domains

TIERS = ("seed",)


def _as_url(value: str) -> str:
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value if value.count("/") > 2 else value + "/"


def prefetch(bodies, ctx):
    return None


def gather(body, ctx):
    bid = body["public_body_id"]
    cands = []
    for origin, source in (("gov_ie", ctx["gov_ie"]), ("foigovie", ctx["foigovie"]), ("prior", ctx["prior"])):
        if source.get(bid):
            cands.append({"url": _as_url(source[bid]), "origin": origin})
    cands += [{"url": u, "origin": "domain_guess"} for u in guess_domains(body.get("name", ""))]
    return {"candidates": cands, "directory_hits": [], "signals": {}, "tiers": list(TIERS),
            "pending_reason": None}

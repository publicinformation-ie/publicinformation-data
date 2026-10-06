from datetime import datetime, timezone

from lib.website_decide import decide, canonical_official_url
from lib.website_verify import verify_candidates

NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)
CHILD = {"public_body_id": 9, "name": "Orliven Ltd", "parent_id": 5, "parent_name": "ESB"}
LONE = {"public_body_id": 8, "name": "Meath Arts Centre", "parent_id": None, "parent_name": None}


def v(url, origin, probe="ok", label=None):
    return {"url": url, "origin": origin, "probe": probe, "final_url": url,
            "judge_label": label, "judge": "fake"}


def test_canonical_official_url():
    assert canonical_official_url("https://www.mac.ie/about/") == "https://www.mac.ie/"
    assert canonical_official_url("https://www.gov.ie/en/organisation/dcedd/") == \
        "https://www.gov.ie/en/organisation/dcedd/"


def test_own_site():
    r = decide(LONE, [v("https://www.mac.ie/about", "haiku_search", label="own_site")],
               tiers_exhausted=["seed", "haiku_search"], now=NOW)
    assert r["website_status"] == "own_site"
    assert r["official_website_url"] == r["effective_website_url"] == "https://www.mac.ie/"
    assert r["website_url_kind"] == "own"
    assert r["website_resolution"]["method"] == "haiku_search"
    assert r["website_resolution"]["recheck_after"] == "2026-12-25"


def test_blocked_needs_two_independent_origins():
    one = decide(LONE, [v("https://w.ie/", "gov_ie", probe="blocked")],
                 tiers_exhausted=["seed"], now=NOW)
    assert one["website_status"] == "not_found"
    two = decide(LONE, [v("https://w.ie/", "gov_ie", probe="blocked"),
                        v("https://www.w.ie/", "haiku_search", probe="blocked")],
                 tiers_exhausted=["seed"], now=NOW)
    assert two["website_status"] == "own_site_blocked"
    assert two["official_website_url"] == "https://w.ie/"


def test_blocked_grouping_does_not_conflate_distinct_gov_ie_organisations():
    # regression: grouping blocked candidates by registrable_domain would treat two
    # unrelated gov.ie org pages as "the same blocked site" and wrongly need only
    # one origin each to together satisfy the >=2-independent-origins rule.
    r = decide(LONE, [v("https://www.gov.ie/en/organisation/dept-a/", "gov_ie", probe="blocked"),
                      v("https://www.gov.ie/en/organisation/dept-b/", "haiku_search", probe="blocked")],
               tiers_exhausted=["seed", "haiku_search"], now=NOW)
    assert r["website_status"] == "not_found"


def test_verify_then_decide_reaches_own_site_blocked():
    # Integration: verify_candidates must itself produce the >=2-origin evidence
    # decide() needs, not just a hand-built `verified` list (regression for the bug
    # where verify_candidates silently dropped a domain's second sighting).
    def probe(url):
        return {"url": url, "final_url": url, "outcome": "blocked", "evidence": None}

    def judge(body, url, evidence):
        raise AssertionError("blocked probes must never reach the judge")

    verified = verify_candidates(LONE, [{"url": "https://w.ie/", "origin": "gov_ie"},
                                        {"url": "https://www.w.ie/", "origin": "haiku_search"}],
                                 probe_fn=probe, judge_fn=judge)
    r = decide(LONE, verified, tiers_exhausted=["seed", "haiku_search"], now=NOW)
    assert r["website_status"] == "own_site_blocked"
    assert r["official_website_url"] == "https://w.ie/"


def test_defunct_from_directory_snippet():
    r = decide(CHILD, [], directory_hits=[{"domain": "solocheck.ie", "url": "u", "title": "",
                                           "snippet": "Status: Dissolved 2019"}],
               tiers_exhausted=["seed"], now=NOW)
    assert r["website_status"] == "defunct" and r["effective_website_url"] is None


def test_no_own_site_falls_back_to_parent_and_is_labelled_parent():
    r = decide(CHILD, [v("https://esb.ie/", "haiku_search", label="parent_site")],
               parent_site_url="https://esb.ie/", tiers_exhausted=["seed", "haiku_search"], now=NOW)
    assert r["website_status"] == "no_own_site"
    assert r["official_website_url"] is None
    assert r["effective_website_url"] == "https://esb.ie/"
    assert r["website_url_kind"] == "parent"
    assert r["parent_public_body_id"] == 5


def test_no_own_site_without_verified_parent_has_no_effective_url():
    r = decide(CHILD, [], signals={"has_own_site": "no"}, tiers_exhausted=["seed"], now=NOW)
    assert r["website_status"] == "no_own_site"
    assert r["effective_website_url"] is None and r["website_url_kind"] is None


def test_body_without_parent_is_never_no_own_site():
    r = decide(LONE, [], signals={"has_own_site": "no"}, tiers_exhausted=["seed"], now=NOW)
    assert r["website_status"] == "not_found"


def test_pending_until_required_tiers_exhausted():
    r = decide(LONE, [], tiers_exhausted=["seed"],
               required_tiers=("seed", "haiku_search", "apify_search"),
               pending_reason="apify_budget", now=NOW)
    assert r["website_status"] == "pending"
    assert r["website_resolution"]["pending_reason"] == "apify_budget"
    assert r["website_resolution"]["recheck_after"] is None


def test_hold_reason_keeps_body_pending_despite_parent_evidence():
    body = {"public_body_id": 1, "name": "X DAC", "parent_name": "P plc"}
    d = decide(body, [], signals={"has_own_site": "no"}, tiers_exhausted=["seed"],
               hold_reason="judge_pending")
    assert d["website_status"] == "pending"
    assert d["website_resolution"]["pending_reason"] == "judge_pending"


def test_hold_reason_does_not_block_a_verified_own_site():
    body = {"public_body_id": 1, "name": "X"}
    own = [{"url": "https://x.ie/", "origin": "domain_guess", "probe": "ok",
            "final_url": "https://x.ie/", "judge_label": "own_site", "judge": "ollama:m"}]
    assert decide(body, own, hold_reason="judge_pending")["website_status"] == "own_site"

from lib.website_verify import verify_candidates

BODY = {"name": "X"}


def probe_map(outcomes):
    calls = []
    def _probe(url):
        calls.append(url)
        outcome = outcomes.get(url, "nxdomain")
        return {"url": url, "final_url": url, "outcome": outcome,
                "evidence": {"title": "t"} if outcome == "ok" else None}
    return _probe, calls


def judge_map(labels):
    def _judge(body, url, evidence):
        return {"label": labels.get(url, "other_entity"), "rationale": "", "judge": "fake"}
    return _judge


def test_stops_at_first_own_site():
    probe, calls = probe_map({"https://a.ie/": "ok", "https://b.ie/": "ok"})
    out = verify_candidates(BODY, [{"url": "https://a.ie/", "origin": "seed"},
                                   {"url": "https://b.ie/", "origin": "seed"}],
                            probe_fn=probe, judge_fn=judge_map({"https://a.ie/": "own_site"}))
    assert len(out) == 1 and out[0]["judge_label"] == "own_site" and calls == ["https://a.ie/"]


def test_non_ok_probe_is_not_judged():
    probe, _ = probe_map({"https://a.ie/": "blocked"})
    out = verify_candidates(BODY, [{"url": "https://a.ie/", "origin": "seed"}], probe_fn=probe,
                            judge_fn=lambda *a: (_ for _ in ()).throw(AssertionError("judged")))
    assert out[0]["probe"] == "blocked" and out[0]["judge_label"] is None


def test_same_domain_probed_once_and_listing_skipped():
    probe, calls = probe_map({"https://a.ie/": "ok"})
    out = verify_candidates(BODY, [{"url": "https://a.ie/", "origin": "seed"},
                                   {"url": "https://www.a.ie/about", "origin": "haiku_search"},
                                   {"url": "https://www.solocheck.ie/x", "origin": "apify_search"}],
                            probe_fn=probe, judge_fn=judge_map({}))
    assert calls == ["https://a.ie/"]
    assert out[-1]["probe"] == "skipped" and out[-1]["judge_label"] == "directory"


def test_distinct_gov_ie_organisations_are_not_deduped_as_one_domain():
    # regression: registrable_domain("gov.ie") alone would treat every gov.ie
    # organisation page as "the same domain" and drop the second one entirely.
    probe, calls = probe_map({"https://www.gov.ie/en/organisation/dept-a/": "ok",
                              "https://www.gov.ie/en/organisation/dept-b/": "ok"})
    out = verify_candidates(BODY, [{"url": "https://www.gov.ie/en/organisation/dept-a/", "origin": "seed"},
                                   {"url": "https://www.gov.ie/en/organisation/dept-b/", "origin": "haiku_search"}],
                            probe_fn=probe, judge_fn=judge_map({}))
    assert calls == ["https://www.gov.ie/en/organisation/dept-a/",
                     "https://www.gov.ie/en/organisation/dept-b/"]
    assert len(out) == 2


def test_blocked_domain_seen_twice_carries_both_origins_without_reprobing():
    # spec §6.4: own_site_blocked needs >=2 independent origins on the SAME domain.
    # verify_candidates must not silently drop the second sighting of an already-probed
    # domain, or decide() can never see the second origin and own_site_blocked can never fire.
    probe, calls = probe_map({"https://w.ie/": "blocked"})
    out = verify_candidates(BODY, [{"url": "https://w.ie/", "origin": "gov_ie"},
                                   {"url": "https://www.w.ie/", "origin": "haiku_search"}],
                            probe_fn=probe, judge_fn=judge_map({}))
    assert calls == ["https://w.ie/"]  # no re-probe of the same domain
    assert [c["origin"] for c in out] == ["gov_ie", "haiku_search"]
    assert all(c["probe"] == "blocked" for c in out)

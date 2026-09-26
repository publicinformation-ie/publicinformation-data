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

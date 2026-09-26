import importlib.util
from pathlib import Path

_EXP = Path(__file__).resolve().parents[1] / "experiments" / "2026-09-26-website-resolution"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


runner = _load("wr_run_experiment", _EXP / "run_experiment.py")


def test_seed_only_end_to_end_with_fakes(tmp_path):
    bodies = [
        {"public_body_id": 1, "name": "Health and Safety Authority", "parent_id": None,
         "parent_name": None, "gold_status": "own_site", "gold_url": "https://www.hsa.ie/"},
        {"public_body_id": 2, "name": "Orliven Ltd", "parent_id": 5, "parent_name": "ESB",
         "gold_status": "no_own_site", "gold_url": ""},
    ]
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={1: "www.hsa.ie"}, prior={}, refresh=False)

    def probe(url):
        ok = "hsa.ie" in url
        return {"url": url, "final_url": url, "outcome": "ok" if ok else "nxdomain",
                "evidence": {"title": "HSA"} if ok else None}

    def judge(body, url, evidence):
        return {"label": "own_site", "rationale": "", "judge": "fake"}

    out = runner.evaluate(bodies, ["seed_only"], ctx, probe, judge, parent_lookup={5: "https://esb.ie/"})
    rows = {r["public_body_id"]: r for r in out["seed_only"]}
    assert rows[1]["website_status"] == "own_site"
    assert rows[1]["official_website_url"] == "https://www.hsa.ie/"
    # seed_only exhausts only the seed tier; the child has no parent evidence from seed alone
    assert rows[2]["website_status"] == "not_found"
    assert ctx["spend"]["apify_paid_queries"] == 0 and ctx["spend"]["haiku_paid_calls"] == 0


def test_foigovie_bare_host_is_normalised(tmp_path):
    ctx = runner.make_ctx(tmp_path, gov_ie={}, foigovie={1: "www.hsa.ie"}, prior={}, refresh=False)
    seed = runner.load_approach("seed_only")
    got = seed.gather({"public_body_id": 1, "name": "HSA Test"}, ctx)
    assert got["candidates"][0] == {"url": "https://www.hsa.ie/", "origin": "foigovie"}

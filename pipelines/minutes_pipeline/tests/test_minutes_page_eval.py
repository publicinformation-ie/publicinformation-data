import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).parent
_PIPELINE_ROOT = _TESTS_DIR.parent
sys.path.insert(0, str(_PIPELINE_ROOT / "steps" / "find_meeting_minutes_pages_search" / "eval"))
sys.path.insert(0, str(_PIPELINE_ROOT / "experiments" / "2026-09-15-minutes-page-discovery" / "approaches"))


def test_grab_skips_cached(tmp_path, monkeypatch):
    import capture_fixtures as cap
    dest = tmp_path / "1.html"
    dest.write_text("cached", encoding="utf-8")
    monkeypatch.setattr(cap, "fetch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert cap._grab("https://example.com/", dest) is None
    assert dest.read_text(encoding="utf-8") == "cached"


def test_fixture_key_slugs_districts():
    from capture_fixtures import fixture_key
    assert fixture_key(1511, None) == "1511"
    assert fixture_key(1511, "Laytown-Bettystown") == "1511__laytown-bettystown"
    assert fixture_key(1511, "Ashbourne") == "1511__ashbourne"


MINUTES_HUB_HTML = """
<html><body>
<a href="/council/minutes-jan-2025.pdf">Council Minutes January 2025</a>
<a href="/council/minutes-feb-2025.pdf">Council Minutes February 2025</a>
<a href="/council/agenda-mar-2025.pdf">Council Agenda March 2025</a>
</body></html>
"""

AGENDA_ONLY_HTML = """
<html><body>
<a href="/council/agenda-jan-2025.pdf">Council Agenda January 2025</a>
<a href="/council/notice.pdf">Meeting Notice</a>
</body></html>
"""

ANNUAL_REPORT_HTML = """
<html><body>
<a href="/pub/annual-report-2024.pdf">Annual Report 2024</a>
<a href="/pub/annual-report-2023.pdf">Annual Report 2023</a>
</body></html>
"""

YEAR_HUB_HTML = """
<html><body>
<a href="/council/meetings-2024">2024 Council Meetings</a>
<a href="/council/budget.pdf">Budget 2024</a>
</body></html>
"""

DEST_HTML = """
<html><body>
<a href="/council/minutes-jun-2024.pdf">Minutes June 2024</a>
</body></html>
"""


def test_minutes_hub_is_positive():
    from score_page import collect_yield
    y = collect_yield(MINUTES_HUB_HTML, "https://www.x.ie/minutes", None)
    assert (y["minutes_like"], y["total"], y["positive"]) == (2, 2, True)


def test_agenda_only_is_negative():
    from score_page import collect_yield
    y = collect_yield(AGENDA_ONLY_HTML, "https://www.x.ie/minutes", None)
    assert y["positive"] is False


def test_annual_report_hub_is_negative():
    from score_page import collect_yield
    y = collect_yield(ANNUAL_REPORT_HTML, "https://www.x.ie/publications", None)
    assert (y["minutes_like"], y["total"], y["positive"]) == (0, 2, False)


def test_purity_edge_one_of_two_is_positive_one_of_three_is_not():
    from score_page import collect_yield
    two = collect_yield(MINUTES_HUB_HTML.replace(
        '<a href="/council/minutes-feb-2025.pdf">Council Minutes February 2025</a>', ""),
        "https://www.x.ie/m", None)
    assert (two["minutes_like"], two["total"], two["positive"]) == (1, 1, True)
    three = MINUTES_HUB_HTML + '<a href="/council/budget.pdf">Budget 2024</a>'
    y = collect_yield(three, "https://www.x.ie/m", None)
    assert (y["minutes_like"], y["total"], y["positive"]) == (2, 3, True)
    four = three + '<a href="/council/plan.pdf">Development Plan</a>'
    y2 = collect_yield(four, "https://www.x.ie/m", None)
    assert (y2["minutes_like"], y2["total"], y2["positive"]) == (2, 4, True)
    five = four + '<a href="/council/extra.pdf">Extra Document</a>'
    y3 = collect_yield(five, "https://www.x.ie/m", None)
    assert (y3["minutes_like"], y3["total"], y3["positive"]) == (2, 5, False)


def test_year_hub_follows_dest():
    from score_page import collect_yield
    without = collect_yield(YEAR_HUB_HTML, "https://www.x.ie/minutes", None)
    assert without["positive"] is False
    with_dest = collect_yield(YEAR_HUB_HTML, "https://www.x.ie/minutes", DEST_HTML)
    assert (with_dest["minutes_like"], with_dest["total"], with_dest["positive"]) == (1, 2, True)


def test_build_records_crawl_hit_and_search_fallback():
    from run_matcher import build_records
    home = {
        "1094": '<html><body><a href="/council-minutes/">Council Meeting Minutes</a></body></html>',
        "9999": '<html><body><a href="/about/">About us</a></body></html>',
    }
    authorities = {
        1094: {"name": "Cavan County Council", "official_website_url": "https://www.cavancoco.ie/"},
        9999: {"name": "Nope Council", "official_website_url": "https://www.nope.ie/"},
    }
    live = {(9999, ""): "https://www.nope.ie/found-minutes"}
    records = build_records(home, authorities, live)
    by_id = {r["public_body_id"]: r for r in records}
    assert by_id[1094]["minutes_page_url"] == "https://www.cavancoco.ie/council-minutes/"
    assert by_id[1094]["source_method"] == "crawl"
    assert by_id[9999]["minutes_page_url"] == "https://www.nope.ie/found-minutes"
    assert by_id[9999]["source_method"] == "apify"


def test_classify_and_score_matrix():
    from evaluate import classify, score
    labels = [
        {"public_body_id": "1", "municipal_district": "", "has_log": "yes",
         "expected_url": "https://a.ie/minutes"},
        {"public_body_id": "2", "municipal_district": "", "has_log": "yes",
         "expected_url": "https://b.ie/minutes"},
        {"public_body_id": "3", "municipal_district": "", "has_log": "no",
         "expected_url": ""},
        {"public_body_id": "4", "municipal_district": "", "has_log": "no",
         "expected_url": ""},
    ]
    records = {
        "1": {"minutes_page_url": "https://a.ie/minutes"},
        "2": {"minutes_page_url": "https://b.ie/other"},
        "3": {"minutes_page_url": "https://c.ie/agendas"},
        "4": {"minutes_page_url": "https://d.ie/nothing"},
    }
    yields = {"1": True, "2": False, "3": True, "4": False}
    assert classify(records["1"], labels[0], True) == "TP"
    assert classify(records["2"], labels[1], False) == "FN"
    assert classify(records["3"], labels[2], True) == "FP"
    assert classify(records["4"], labels[3], False) == "TN"
    counts, p, r, f1, details, skipped, _url_matches = score(records, labels, yields)
    assert counts == {"TP": 1, "FP": 1, "FN": 1, "TN": 1}
    assert (p, r, f1) == (0.5, 0.5, 0.5)
    assert skipped == 0


def test_missing_record_is_skipped_not_tn():
    from evaluate import score
    labels = [{"public_body_id": "9", "municipal_district": "", "has_log": "no",
               "expected_url": ""}]
    counts, _p, _r, _f1, _d, skipped, _u = score({}, labels, {})
    assert skipped == 1
    assert sum(counts.values()) == 0

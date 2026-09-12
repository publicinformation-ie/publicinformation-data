from steps.find_meeting_minutes_pages_search.process import (
    STEP_NAME,
    _build_query,
    _pick_minutes_url,
)


def test_step_name():
    assert STEP_NAME == "find_meeting_minutes_pages_search"


def test_build_query():
    assert _build_query("https://www.dlrcoco.ie/", "Dun Laoghaire Rathdown County Council") == \
        "site:www.dlrcoco.ie Dun Laoghaire Rathdown County Council council meeting minutes"


def test_pick_prefers_explicit_minutes_link():
    results = [
        {"url": "https://www.x.ie/about/", "link": "https://www.x.ie/about/", "title": "About us"},
        {"url": "https://www.x.ie/council-minutes/", "link": "https://www.x.ie/council-minutes/",
         "title": "Council Minutes"},
    ]
    assert _pick_minutes_url(results) == "https://www.x.ie/council-minutes/"


def test_pick_rejects_everything():
    assert _pick_minutes_url([]) is None
    assert _pick_minutes_url([
        {"url": "https://www.x.ie/meeting-stuff/", "link": "https://www.x.ie/meeting-stuff/",
         "title": "Meeting stuff"},
    ]) is None
    assert _pick_minutes_url([
        {"url": "https://www.x.ie/ga/council-minutes/", "link": "https://www.x.ie/ga/council-minutes/",
         "title": "Council Minutes"},
    ]) is None
    assert _pick_minutes_url([
        {"url": "javascript:void(0)", "link": "javascript:void(0)", "title": "Council Minutes"},
    ]) is None

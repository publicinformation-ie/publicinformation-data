from steps.resolve_meeting_date.date_resolver import (
    body_header_daymonth,
    link_text_year_month,
    resolve,
)


def _rec(**kw):
    base = {
        "public_body_id": 1511, "file_url": "https://meath.ie/m.pdf",
        "municipal_district": "Laytown-Bettystown",
        "meeting_date": None, "stated_date": None,
        "link_text": None, "text": "", "motions": [{"motion_text": "x"}],
    }
    base.update(kw)
    return base


# --- link_text_year_month --------------------------------------------------

def test_link_year_month_extracted():
    assert link_text_year_month(
        "Minutes - Laytown-Bettystown MD Ordinary Meeting October 2024"
    ) == ("October", 2024)


def test_link_year_month_none_when_absent():
    assert link_text_year_month("Minutes - Ordinary Meeting") == (None, None)
    assert link_text_year_month(None) == (None, None)


# --- body_header_daymonth ------------------------------------------------

def test_body_daymonth_from_header_no_year():
    text = ("Miontuairiscí / Meeting Minutes\nOrdinary Meeting\n"
            "Laytown-Bettystown Municipal District\n"
            "10.00a.m, 10th October, Duleek Civic Offices\n")
    assert body_header_daymonth(text) == (10, "October", None)


def test_body_daymonth_with_year():
    text = "Ordinary Meeting\n10.15 am, 17th June 2021, County Hall, Navan\n"
    assert body_header_daymonth(text) == (17, "June", 2021)


def test_body_daymonth_none_when_two_distinct_pairs_in_header():
    text = ("Ordinary Meeting held 3rd September, adjourned from 20th August\n")
    assert body_header_daymonth(text) is None


def test_body_daymonth_ignores_dates_below_the_header():
    text = "Ordinary Meeting\n" + ("filler\n" * 20) + "5th May 2019\n"
    assert body_header_daymonth(text) is None


# --- resolve --------------------------------------------------------------

def test_resolve_trusts_deterministic_upstream_date():
    assert resolve(_rec(meeting_date="2024-07-08")) == ("2024-07-08", None)


def test_resolve_trusts_llm_full_date():
    assert resolve(_rec(stated_date="8 July 2024")) == ("2024-07-08", None)


def test_resolve_rejects_llm_month_only_date():
    iso, err = resolve(_rec(stated_date="July 2024", link_text=None, text=""))
    assert iso is None
    assert err["error_type"] == "UnresolvedMeetingDate"


def test_resolve_merges_body_day_month_with_link_year():
    rec = _rec(
        link_text="Minutes - Ordinary Meeting October 2024",
        text="Ordinary Meeting\n10.00a.m, 10th October, Duleek Civic Offices\n",
    )
    assert resolve(rec) == ("2024-10-10", None)


def test_resolve_uses_full_body_date_over_link_year():
    rec = _rec(
        link_text="Minutes - Meeting June 2021",
        text="Ordinary Meeting\n10.15 am, 17th June 2021, County Hall\n",
    )
    assert resolve(rec) == ("2021-06-17", None)


def test_resolve_fails_closed_when_link_month_disagrees_with_body_month():
    # Body says October, link text says November -> do NOT guess a year.
    rec = _rec(
        link_text="Minutes - Ordinary Meeting November 2024",
        text="Ordinary Meeting\n10.00a.m, 10th October, Duleek Civic Offices\n",
    )
    iso, err = resolve(rec)
    assert iso is None
    assert err["error_type"] == "UnresolvedMeetingDate"
    assert err["context"]["file_url"] == "https://meath.ie/m.pdf"


def test_resolve_never_reads_year_from_url_folder():
    # 2017 meeting filed under a 2019 upload folder: year must come from the
    # link text ("March 2017"), never the URL path.
    rec = _rec(
        file_url="https://meath.ie/system/files/media/file-uploads/2019-06/"
                 "03-2017%20Minutes%20March%20Meath%20County%20Council.pdf",
        link_text="Minutes - Meath County Council Meeting March 2017",
        text="Miontuairiscí / Meeting Minutes\nOrdinary Meeting\n"
             "6th March, Council Chamber\n",
    )
    assert resolve(rec) == ("2017-03-06", None)


def test_resolve_silent_when_no_motions_and_no_date():
    iso, err = resolve(_rec(motions=[], link_text=None, text=""))
    assert iso is None
    assert err is None


def test_resolve_silent_when_motions_none_and_no_date():
    iso, err = resolve(_rec(motions=None, link_text=None, text=""))
    assert iso is None
    assert err is None


def test_resolve_impossible_date_fails_closed():
    rec = _rec(
        link_text="Minutes - Ordinary Meeting February 2021",
        text="Ordinary Meeting\n30th February, Somewhere\n",
    )
    iso, err = resolve(rec)
    assert iso is None
    assert err["error_type"] == "UnresolvedMeetingDate"


import json
from steps.resolve_meeting_date.process import run


def test_run_resolves_and_collects_errors(tmp_path):
    records = [
        {  # recovered via header day/month + link-text year
            "public_body_id": 1511, "file_url": "https://meath.ie/a.pdf",
            "municipal_district": "Laytown-Bettystown", "meeting_date": None,
            "stated_date": None,
            "link_text": "Minutes - Ordinary Meeting October 2024",
            "text": "Ordinary Meeting\n10.00a.m, 10th October, Duleek\n",
            "motions": [{"motion_text": "x"}],
        },
        {  # unresolved, has motions -> error row
            "public_body_id": 1511, "file_url": "https://meath.ie/b.pdf",
            "municipal_district": "Trim", "meeting_date": None,
            "stated_date": None, "link_text": "Minutes", "text": "",
            "motions": [{"motion_text": "y"}],
        },
        {  # empty doc, no motions -> passes through, no error
            "public_body_id": 1511, "file_url": "https://meath.ie/c.pdf",
            "municipal_district": "Navan", "meeting_date": None,
            "stated_date": None, "link_text": "Minutes", "text": "",
            "motions": [],
        },
    ]
    in_path = tmp_path / "in.json"
    in_path.write_text(json.dumps({"results": records}))
    out_path = tmp_path / "out.json"

    run(str(in_path), str(out_path), tmp_path, public_body=None, force=True)

    out = json.loads(out_path.read_text())["results"]
    assert [r["meeting_date"] for r in out] == ["2024-10-10", None, None]
    assert all("stated_date" not in r for r in out)
    errs = json.loads((tmp_path / "errors.json").read_text())
    assert [e["error_type"] for e in errs] == ["UnresolvedMeetingDate"]
    assert errs[0]["context"]["file_url"] == "https://meath.ie/b.pdf"

import json
from unittest import mock

import steps.find_meeting_minutes_pages.process as meeting_mod
from steps.find_meeting_minutes_pages.process import STEP_NAME as MEETING_STEP, process as meeting_process
from lib.file_utils import errors_outside_bodies, read_json


def _write(path, data):
    path.write_text(data if isinstance(data, str) else json.dumps(data))


def test_errors_outside_bodies_keeps_other_bodies_only(tmp_path):
    p = tmp_path / "errors.json"
    _write(p, [
        {"context": {"public_body_id": 1511}},
        {"context": {"public_body_id": 1716}},
        {"context": None},
        {"error_type": "NoContext"},
    ])
    kept = errors_outside_bodies(p, {1716})
    assert kept == [{"context": {"public_body_id": 1511}}]


def test_errors_outside_bodies_missing_file_is_empty(tmp_path):
    assert errors_outside_bodies(tmp_path / "nope.json", {1716}) == []


def test_errors_outside_bodies_corrupt_or_non_list_is_empty(tmp_path):
    p = tmp_path / "errors.json"
    _write(p, "{not json")
    assert errors_outside_bodies(p, {1716}) == []
    _write(p, {"not": "a list"})
    assert errors_outside_bodies(p, {1716}) == []


def test_scoped_meeting_run_skips_other_overrides_and_keeps_errors(tmp_path, monkeypatch, make_writer):
    sligo = "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/"
    _write(tmp_path / "override.json", [{
        "public_body_id": 1716, "municipal_district": None,
        "minutes_page_url": sligo, "child_pages": r"/Minutes/Minutes\d{4}/$",
    }])
    _write(tmp_path / "errors.json", [
        {"context": {"public_body_id": 1716}},  # out of scope: must survive
        {"context": {"public_body_id": 1511}},  # in scope: replaced by this run
    ])
    fetched = []

    def fake_fetch(method, url, **kw):
        fetched.append(url)
        return mock.Mock(text='<a href="/minutes">Council Minutes</a>')

    monkeypatch.setattr(meeting_mod, "fetch", fake_fetch)
    authorities = [{"public_body_id": 1511, "name": "Meath", "slug": "meath",
                    "official_website_url": "https://www.meath.ie/", "municipal_districts": []}]
    writer = make_writer(MEETING_STEP)
    meeting_process({"results": authorities}, tmp_path, writer)
    writer.finalize()

    assert sligo not in fetched
    assert all(r["public_body_id"] == 1511 for r in read_json(tmp_path / "output.json")["results"])
    assert read_json(tmp_path / "errors.json") == [{"context": {"public_body_id": 1716}}]

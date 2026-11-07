import hashlib
import json
import pytest
import requests as req
from steps.fingerprint_disclosure_pages.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "find_disclosure_pages", "completed_at": "2026-06-29T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "disclosure_page_url": "https://dept-a.ie/disc/"},
        {"public_body_id": 1002, "name": "Dept B", "disclosure_page_url": "https://dept-b.ie/disc/"},
    ],
}

HTML_WITH_ONE_FILE = '<html><body><a href="/disclosures/foi-log-2024.pdf">FOI Log 2024</a></body></html>'
HTML_WITH_TWO_FILES = (
    '<html><body>'
    '<a href="/disclosures/foi-log-2024.pdf">FOI Log 2024</a>'
    '<a href="/disclosures/foi-log-2023.pdf">FOI Log 2023</a>'
    '</body></html>'
)
HTML_NO_FILES = '<html><body><p>No files here</p></body></html>'


def _hash(urls):
    raw = "\n".join(sorted(set(urls)))
    return "sha256-" + hashlib.sha256(raw.encode()).hexdigest()


def test_hash_stability_body_not_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    expected_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: expected_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 not in dirty_ids


def test_new_link_marks_body_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_TWO_FILES)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 in dirty_ids


def test_removed_link_marks_body_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash([
        "https://dept-a.ie/disclosures/foi-log-2024.pdf",
        "https://dept-a.ie/disclosures/foi-log-2023.pdf",
    ])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 in dirty_ids


def test_new_body_no_previous_hash_is_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes={})
    assert 1001 in dirty_ids


def test_fetch_error_body_not_dirty_error_logged(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", exc=req.exceptions.ConnectionError("timeout"))
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    assert 1001 not in dirty_ids
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME
    assert errors[0]["context"]["public_body_id"] == 1001


def test_fetch_error_preserves_previous_hash_in_output(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", exc=req.exceptions.ConnectionError("timeout"))
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes)
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    assert result_1001["page_hash"] == old_hash


def test_output_record_has_required_fields(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes={})
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    assert {"public_body_id", "name", "disclosure_page_url", "page_hash", "file_count"} <= result_1001.keys()
    assert result_1001["page_hash"].startswith("sha256-")
    assert result_1001["file_count"] == 1


def test_force_clears_hashes_all_dirty(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_WITH_ONE_FILE)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    current_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    previous_hashes = {1001: current_hash, 1002: _hash([])}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes, force=True)
    assert 1001 in dirty_ids
    assert 1002 in dirty_ids


def test_force_with_fetch_error_preserves_previous_hash(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", exc=req.exceptions.ConnectionError("timeout"))
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    old_hash = _hash(["https://dept-a.ie/disclosures/foi-log-2024.pdf"])
    preserved = {1001: old_hash}
    results, dirty_ids = process(INPUT, tmp_path, previous_hashes={}, preserved_hashes=preserved, force=True)
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    assert result_1001["page_hash"] == old_hash
    assert 1001 not in dirty_ids


def test_page_with_no_files_hash_is_stable(requests_mock, tmp_path):
    requests_mock.get("https://dept-a.ie/disc/", text=HTML_NO_FILES)
    requests_mock.get("https://dept-b.ie/disc/", text=HTML_NO_FILES)
    results, _ = process(INPUT, tmp_path, previous_hashes={})
    result_1001 = next(r for r in results if r["public_body_id"] == 1001)
    empty_hash = _hash([])
    assert result_1001["page_hash"] == empty_hash
    assert result_1001["file_count"] == 0


# ---- main()-level tests -------------------------------------------------

import sys
from steps.fingerprint_disclosure_pages import process as fp_mod

INPUT3 = {
    "metadata": {"step": "find_disclosure_pages"},
    "results": [
        {"public_body_id": i, "name": f"D{i}", "disclosure_page_url": f"https://d{i}.ie/disc/"}
        for i in (1001, 1002, 1003)
    ],
}
PDF_URL = "https://d{}.ie/a.pdf"
HTML_PDF = '<a href="/a.pdf">x</a>'


def _prev_output(hash_overrides=None):
    hash_overrides = hash_overrides or {}
    return {"metadata": {}, "results": [
        {"public_body_id": i, "name": f"D{i}", "disclosure_page_url": f"https://d{i}.ie/disc/",
         "page_hash": hash_overrides.get(i, _hash([PDF_URL.format(i)])), "file_count": 1}
        for i in (1001, 1002, 1003)]}


def _run(tmp_path, *extra):
    d = tmp_path / "step"
    d.mkdir(exist_ok=True)
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(INPUT3))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(d / "output.json"), *extra]
    fp_mod.main()
    return d


def _setup(tmp_path, prev=None, dirty=None, mock=None):
    d = tmp_path / "step"
    d.mkdir(exist_ok=True)
    if prev is not None:
        (d / "output.json").write_text(json.dumps(prev))
    if dirty is not None:
        (d / "dirty_ids.json").write_text(json.dumps(dirty))
    return d


def _mock_all(requests_mock):
    for i in (1001, 1002, 1003):
        requests_mock.get(f"https://d{i}.ie/disc/", text=HTML_PDF)


def test_dirty_file_unions_with_previous(requests_mock, tmp_path):
    _mock_all(requests_mock)
    _setup(tmp_path, _prev_output({1001: "sha256-old"}), [1002])
    d = _run(tmp_path)
    assert json.loads((d / "dirty_ids.json").read_text()) == [1001, 1002]


def test_unchanged_run_keeps_pending_dirty_ids(requests_mock, tmp_path):
    _mock_all(requests_mock)
    _setup(tmp_path, _prev_output(), [1002])
    d = _run(tmp_path)
    assert json.loads((d / "dirty_ids.json").read_text()) == [1002]


def test_corrupt_previous_dirty_file_raises(requests_mock, tmp_path):
    _mock_all(requests_mock)
    d = _setup(tmp_path, _prev_output(), {"a": 1})
    with pytest.raises(ValueError, match="dirty_ids.json"):
        _run(tmp_path)


def test_scoped_run_preserves_other_bodies_records_and_hashes(requests_mock, tmp_path):
    requests_mock.get("https://d1002.ie/disc/", text=HTML_PDF)
    _setup(tmp_path, _prev_output({1001: "sha256-x", 1003: "sha256-y", 1002: "sha256-z"}))
    d = _run(tmp_path, "--public-body", "1002")
    res = json.loads((d / "output.json").read_text())["results"]
    assert [r["public_body_id"] for r in res] == [1001, 1002, 1003]
    by = {r["public_body_id"]: r for r in res}
    assert by[1001]["page_hash"] == "sha256-x"
    assert by[1003]["page_hash"] == "sha256-y"
    assert by[1002]["page_hash"] == _hash([PDF_URL.format(1002)])
    assert [r.url for r in requests_mock.request_history] == ["https://d1002.ie/disc/"]


def test_scoped_run_then_unscoped_run_marks_nothing_new_dirty(requests_mock, tmp_path):
    _mock_all(requests_mock)
    _setup(tmp_path, _prev_output({1002: "sha256-z"}))
    d = _run(tmp_path, "--public-body", "1002")
    assert json.loads((d / "dirty_ids.json").read_text()) == [1002]
    (d / "dirty_ids.json").write_text("[]")
    _run(tmp_path)
    assert json.loads((d / "dirty_ids.json").read_text()) == []


def test_scoped_run_preserves_other_bodies_errors(requests_mock, tmp_path):
    requests_mock.get("https://d1002.ie/disc/", exc=req.exceptions.ConnectionError("x"))
    d = _setup(tmp_path, _prev_output())
    err = lambda b: {"step": STEP_NAME, "context": {"public_body_id": b}}
    (d / "errors.json").write_text(json.dumps([err(1001), err(1002)]))
    _run(tmp_path, "--public-body", "1002")
    errs = json.loads((d / "errors.json").read_text())
    ids = sorted(e["context"]["public_body_id"] for e in errs)
    assert ids == [1001, 1002]
    assert "ConnectionError" in [e for e in errs if e["context"]["public_body_id"] == 1002][0].get("error_type", "")


def test_scoped_forced_run_preserves_other_bodies(requests_mock, tmp_path):
    requests_mock.get("https://d1002.ie/disc/", text=HTML_PDF)
    _setup(tmp_path, _prev_output({1001: "sha256-x", 1003: "sha256-y"}))
    d = _run(tmp_path, "--force", "--public-body", "1002")
    res = json.loads((d / "output.json").read_text())["results"]
    assert [r["public_body_id"] for r in res] == [1001, 1002, 1003]
    assert res[0]["page_hash"] == "sha256-x" and res[2]["page_hash"] == "sha256-y"
    assert json.loads((d / "dirty_ids.json").read_text()) == [1002]


def test_scoped_run_with_unreadable_previous_output_exits(requests_mock, tmp_path, capsys):
    _mock_all(requests_mock)
    d = _setup(tmp_path)
    (d / "output.json").write_text("{not json")
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, "--public-body", "1002")
    assert exc.value.code == 1
    assert str(d / "output.json") in capsys.readouterr().err


def test_dirty_file_written_before_output(requests_mock, tmp_path, monkeypatch):
    _mock_all(requests_mock)
    d = _setup(tmp_path, _prev_output({1001: "sha256-old"}), [1002])
    real = fp_mod.write_json

    def boom(path, data):
        if str(path).endswith("output.json"):
            raise RuntimeError("crash")
        return real(path, data)

    monkeypatch.setattr(fp_mod, "write_json", boom)
    with pytest.raises(RuntimeError, match="crash"):
        _run(tmp_path)
    assert json.loads((d / "dirty_ids.json").read_text()) == [1001, 1002]


def test_scoped_run_target_absent_from_previous_output_appended_once(requests_mock, tmp_path):
    requests_mock.get("https://d1003.ie/disc/", text=HTML_PDF)
    prev = _prev_output()
    prev["results"] = [r for r in prev["results"] if r["public_body_id"] != 1003]
    d = _setup(tmp_path, prev)
    _run(tmp_path, "--public-body", "1003")
    res = json.loads((d / "output.json").read_text())["results"]
    assert [r["public_body_id"] for r in res] == [1001, 1002, 1003]
    assert json.loads((d / "dirty_ids.json").read_text()) == [1003]

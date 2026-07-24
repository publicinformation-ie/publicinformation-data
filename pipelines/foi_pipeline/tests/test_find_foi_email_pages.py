def test_step_name_is_find_foi_email_pages():
    from steps.find_foi_email_pages.process import STEP_NAME
    assert STEP_NAME == "find_foi_email_pages"


import json
from steps.find_foi_email_pages.process import process, STEP_NAME

INPUT = {
    "metadata": {"step": "get_foi_emails", "completed_at": "2026-07-24T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "foi_page_url": "https://dept-a.ie/foi/",
         "foi_email": None, "email_status": "not_found"},
        {"public_body_id": 1002, "name": "Dept B", "foi_page_url": "https://dept-b.ie/foi/",
         "foi_email": "foi@dept-b.ie", "email_status": "found"},
        {"public_body_id": 1003, "name": "Dept C", "foi_page_url": "https://dept-c.ie/foi/",
         "foi_email": None, "email_status": "multiple_found"},
    ],
}

FOI_PAGE_WITH_OFFICER_LINK = '<html><body><a href="/foi-officer">FOI Officer</a></body></html>'
FOI_PAGE_NO_LINKS = '<html><body><p>No links here</p></body></html>'
CANDIDATE_PAGE_WITH_EMAIL = '<html><body><a href="mailto:foi@dept-a.ie">FOI</a></body></html>'
CANDIDATE_PAGE_NO_EMAIL = '<html><body><p>No contact info</p></body></html>'


def test_passes_through_found_record_unchanged(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    process(INPUT, tmp_path, writer)
    b = next(r for r in writer.results if r["public_body_id"] == 1002)
    assert b == INPUT["results"][1]
    assert "confidence" not in b
    assert "source_page_url" not in b


def test_passes_through_multiple_found_record_unchanged(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    process(INPUT, tmp_path, writer)
    c = next(r for r in writer.results if r["public_body_id"] == 1003)
    assert c == INPUT["results"][2]


def test_upgrades_not_found_record_when_candidate_has_email(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=FOI_PAGE_WITH_OFFICER_LINK)
    requests_mock.get("https://dept-a.ie/foi-officer", text=CANDIDATE_PAGE_WITH_EMAIL)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["foi_email"] == "foi@dept-a.ie"
    assert a["email_status"] == "found"
    assert a["confidence"] == "high"
    assert a["source_page_url"] == "https://dept-a.ie/foi-officer"


def test_leaves_not_found_when_no_candidate_links(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=FOI_PAGE_NO_LINKS)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["email_status"] == "not_found"
    assert a["foi_email"] is None
    assert "confidence" not in a


def test_leaves_not_found_when_candidate_has_no_email(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=FOI_PAGE_WITH_OFFICER_LINK)
    requests_mock.get("https://dept-a.ie/foi-officer", text=CANDIDATE_PAGE_NO_EMAIL)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["email_status"] == "not_found"
    assert "confidence" not in a


def test_falls_through_to_second_candidate_when_first_has_no_email(requests_mock, tmp_path, make_writer):
    html = """<html><body>
      <a href="/contact-officer">Contact Officer</a>
      <a href="/foi-officer">FOI Officer</a>
    </body></html>"""
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=html)
    requests_mock.get("https://dept-a.ie/foi-officer", text=CANDIDATE_PAGE_NO_EMAIL)
    requests_mock.get("https://dept-a.ie/contact-officer", text=CANDIDATE_PAGE_WITH_EMAIL)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["email_status"] == "found"
    assert a["source_page_url"] == "https://dept-a.ie/contact-officer"


def test_binary_foi_page_leaves_record_unchanged(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", content=b"%PDF-1.5\n%garbage",
                       headers={"Content-Type": "application/pdf"})
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["email_status"] == "not_found"
    assert a["foi_email"] is None


def test_connection_error_logs_and_skips_body(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", exc=req.exceptions.ConnectionError("x"))
    process(INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 1001 for r in writer.results)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors[0]["step"] == STEP_NAME


def test_candidate_fetch_error_tries_next_candidate(requests_mock, tmp_path, make_writer):
    import requests as req
    html = """<html><body>
      <a href="/contact-officer">Contact Officer</a>
      <a href="/foi-officer">FOI Officer</a>
    </body></html>"""
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=html)
    requests_mock.get("https://dept-a.ie/foi-officer", exc=req.exceptions.ConnectionError("x"))
    requests_mock.get("https://dept-a.ie/contact-officer", text=CANDIDATE_PAGE_WITH_EMAIL)
    process(INPUT, tmp_path, writer)
    a = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert a["email_status"] == "found"
    assert a["source_page_url"] == "https://dept-a.ie/contact-officer"


def test_all_bodies_produce_one_result_each(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/foi/", text=FOI_PAGE_NO_LINKS)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 3


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from lib.file_utils import write_json, IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "foi_page_url": "https://dept-a.ie/foi/",
                     "foi_email": None, "email_status": "not_found"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0


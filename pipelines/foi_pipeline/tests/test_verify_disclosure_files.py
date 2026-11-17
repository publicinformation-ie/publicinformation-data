import pytest
import unittest.mock
from steps.verify_disclosure_files.process import (
    _score_text, _is_non_foi_document, _verify_one, DisclosureFileCache,
    load_exclusions, _sync_exclusions, process, EXCLUSION_SIGNAL,
)


class TestScoreTextUnverified:
    def test_none_text(self):
        status, signal = _score_text(None)
        assert status == "unverified"
        assert signal is None

    def test_empty_string(self):
        status, signal = _score_text("")
        assert status == "unverified"
        assert signal is None

    def test_whitespace_only(self):
        status, signal = _score_text("   \n  ")
        assert status == "unverified"
        assert signal is None


class TestScoreTextTierA:
    def test_disclosure_log(self):
        status, signal = _score_text("This is the Disclosure Log for Q1 2024")
        assert status == "verified"
        assert signal == "disclosure log"

    def test_foi_log(self):
        status, signal = _score_text("Welcome to our FOI Log page")
        assert status == "verified"
        assert signal == "foi log"

    def test_foi_disclosure(self):
        status, signal = _score_text("FOI Disclosure register updated monthly")
        assert status == "verified"
        assert signal == "foi disclosure"

    def test_non_personal_foi(self):
        status, signal = _score_text("Non-Personal FOI requests processed below")
        assert status == "verified"
        assert signal == "non-personal foi"

    def test_freedom_of_information_disclosure(self):
        status, signal = _score_text("Freedom of Information Disclosure log 2024")
        assert status == "verified"
        assert signal == "freedom of information disclosure"

    def test_case_insensitive(self):
        status, signal = _score_text("DISCLOSURE LOG ANNUAL REPORT")
        assert status == "verified"
        assert signal == "disclosure log"

    def test_tier_a_beats_tier_b_combo(self):
        # "foi disclosure" (Tier A) present alongside other Tier B signals
        status, signal = _score_text("FOI Disclosure date received date of decision freedom of information")
        assert status == "verified"
        assert signal == "foi disclosure"


class TestScoreTextTierB:
    def test_two_tier_b_matches(self):
        status, signal = _score_text(
            "Freedom of Information requests with Date Received and outcome"
        )
        assert status == "verified"
        assert "freedom of information" in signal

    def test_one_tier_b_match_rejected(self):
        status, signal = _score_text("Freedom of information requests filed by citizens")
        assert status == "rejected"
        assert signal is None

    def test_foi_plus_decision_verifies(self):
        status, signal = _score_text("FOI request, Decision: granted")
        assert status == "verified"
        assert signal is not None

    def test_date_received_plus_date_of_decision(self):
        status, signal = _score_text("Date Received: 01/01/2024. Date of Decision: 15/01/2024.")
        assert status == "verified"
        assert signal is not None

    def test_request_reference_plus_decision(self):
        status, signal = _score_text("Request Reference: FOI/001. Decision: granted.")
        assert status == "verified"
        assert signal is not None


class TestScoreTextRejected:
    def test_no_signals(self):
        status, signal = _score_text("Annual Report 2024 - Heritage Services Visitor Numbers")
        assert status == "rejected"
        assert signal is None

    def test_financial_stability_content(self):
        status, signal = _score_text(
            "Financial Stability Review 2024: The Central Bank of Ireland"
        )
        assert status == "rejected"
        assert signal is None


class TestIsNonFoiDocument:
    def test_calendar_in_filename(self):
        assert _is_non_foi_document(
            "https://assets.gov.ie/Minister_Morans_Calendar_Q1_2025.pdf",
            None, None
        ) is True

    def test_calendar_hyphenated_in_filename(self):
        assert _is_non_foi_document(
            "https://www.louthcoco.ie/community-connect-calendar-2025.pdf",
            None, None
        ) is True

    def test_visitor_numbers_hyphenated_in_filename(self):
        assert _is_non_foi_document(
            "https://www.heritagecouncil.ie/heritage-services-visitor-numbers-2021.pdf",
            None, None
        ) is True

    def test_faq_in_filename(self):
        assert _is_non_foi_document(
            "https://www.irishprisons.ie/wp-content/uploads/foi_faq2.pdf",
            None, None
        ) is True

    def test_individual_decision_letter_by_content(self):
        text = (
            "Page No  Description of Document  Deletions  "
            "Relevant Sections of FOI Acts  "
            "Reason for Decision  Decision maker's decision"
        )
        assert _is_non_foi_document(
            "https://www.fiosru.ie/foi-004-24.pdf",
            None, text
        ) is True

    def test_genuine_disclosure_log_not_rejected(self):
        assert _is_non_foi_document(
            "https://www.gov.ie/non-personal-foi-disclosure-log-2024.pdf",
            "FOI Disclosure Log", None
        ) is False

    def test_disclosure_log_with_foi_in_url_not_rejected(self):
        assert _is_non_foi_document(
            "https://www.gov.ie/foi-requests-q1-2025.pdf",
            None, None
        ) is False

    def test_none_text_calendar_still_rejected(self):
        # URL pattern check does not require content
        assert _is_non_foi_document(
            "https://www.gov.ie/Q1_January_-_March.pdf",
            None, None
        ) is False  # "january" alone is not a rejection pattern

    def test_calendar_in_link_text(self):
        # "calendar" appearing only in link_text (not URL path) should also reject
        assert _is_non_foi_document(
            "https://www.gov.ie/documents/Q1_2025.pdf",
            "Ministerial Calendar Q1 2025", None
        ) is True

    def test_visitor_number_in_link_text(self):
        assert _is_non_foi_document(
            "https://www.gov.ie/report.pdf",
            "Heritage Visitor Numbers 2021", None
        ) is True

    def test_content_check_requires_all_three_phrases(self):
        # Only two of the three decision-letter phrases present — should not reject
        text = "Relevant Sections of FOI Acts  Reason for Decision  some other content"
        assert _is_non_foi_document(
            "https://www.fiosru.ie/some-doc.pdf",
            None, text
        ) is False


class TestVerifyOneNonFoiRejection:
    def test_calendar_url_returns_rejected(self, tmp_path):
        """_verify_one must return rejected/non_foi_pattern for a calendar URL."""
        # Create a temp file with empty bytes to represent the "downloaded" file
        fake_file = tmp_path / "fake.pdf"
        fake_file.write_bytes(b"")

        item = {
            "file_url": "https://www.gov.ie/Minister_Calendar_Q1.pdf",
            "file_type": "pdf",
            "link_text": None,
        }

        cache = unittest.mock.MagicMock(spec=DisclosureFileCache)
        cache.get_file_path.return_value = fake_file

        result = _verify_one(item, cache, str(tmp_path))

        assert result is not None
        assert result["verification_status"] == "rejected"
        assert result["verification_signal"] == "non_foi_pattern"


# --- per-file exclusion list -------------------------------------------------

URL_A = "https://x/a.pdf"
URL_B = "https://x/b.pdf"
ENTRY = {"reason": "form", "class": "not_foi_log", "date": "2026-11-17"}
ITEM = {"file_url": URL_A, "file_type": "pdf", "link_text": "a", "public_body_id": 1}


def _rec(url, body, status="verified", signal="disclosure log"):
    return {"public_body_id": body, "file_url": url, "file_type": "pdf", "link_text": "t",
            "verification_status": status, "verification_signal": signal}


class FakeWriter:
    def __init__(self, results):
        self.results = results
        self.processed_keys = {r["file_url"] for r in results}
        self.dirty_body_ids = set()


def test_excluded_url_rejected_without_download(tmp_path):
    cache = unittest.mock.Mock()
    out = _verify_one(ITEM, cache, tmp_path, exclusions={URL_A: ENTRY})
    assert (out["verification_status"], out["verification_signal"]) == ("rejected", "manual_exclusion")
    cache.get_file_path.assert_not_called()


def test_unlisted_url_unaffected(tmp_path):
    f = tmp_path / "f.pdf"
    f.write_bytes(b"")
    cache = unittest.mock.MagicMock(spec=DisclosureFileCache)
    cache.get_file_path.return_value = f
    item = {**ITEM, "file_url": "https://x/Calendar.pdf"}
    assert _verify_one(item, cache, str(tmp_path), exclusions={}) == _verify_one(item, cache, str(tmp_path))


def test_load_exclusions_missing_file_is_empty(tmp_path):
    assert load_exclusions(tmp_path) == {}


def test_load_exclusions_valid(tmp_path):
    (tmp_path / "excluded_files.json").write_text('{"u": %s}' % __import__("json").dumps(ENTRY))
    assert load_exclusions(tmp_path) == {"u": ENTRY}


@pytest.mark.parametrize("bad", [
    '[]',
    '{"u": {"class": "not_foi_log", "date": "2026-11-17"}}',
    '{"u": {"reason": "", "class": "not_foi_log", "date": "2026-11-17"}}',
    '{"u": {"reason": "form", "class": "scan", "date": "2026-11-17"}}',
    '{"u": {"reason": "form", "class": "not_foi_log", "date": "17/11/2026"}}',
    '{not json',
])
def test_load_exclusions_malformed_raises(tmp_path, bad):
    (tmp_path / "excluded_files.json").write_text(bad)
    with pytest.raises(ValueError):
        load_exclusions(tmp_path)


def test_sync_rejects_already_verified_record_and_marks_body_dirty():
    a, b = _rec(URL_A, 1), _rec(URL_B, 2)
    b_before = dict(b)
    w = FakeWriter([a, b])
    _sync_exclusions(w, {URL_A: ENTRY}, {URL_A, URL_B})
    assert (a["verification_status"], a["verification_signal"]) == ("rejected", EXCLUSION_SIGNAL)
    assert b == b_before
    assert w.dirty_body_ids == {1}


def test_sync_removed_entry_is_reverified():
    w = FakeWriter([_rec(URL_A, 1, "rejected", EXCLUSION_SIGNAL)])
    _sync_exclusions(w, {}, {URL_A})
    assert w.results == []
    assert URL_A not in w.processed_keys
    assert w.dirty_body_ids == {1}


def test_sync_idempotent():
    w = FakeWriter([_rec(URL_A, 1, "rejected", EXCLUSION_SIGNAL)])
    before = [dict(r) for r in w.results]
    _sync_exclusions(w, {URL_A: ENTRY}, {URL_A})
    assert w.results == before
    assert w.dirty_body_ids == set()


def test_sync_warns_on_url_not_in_input(capsys):
    _sync_exclusions(FakeWriter([]), {"https://x/typo%20.pdf": ENTRY}, set())
    out = capsys.readouterr().out
    assert "WARNING: excluded_files.json lists a URL not in the input: https://x/typo%20.pdf" in out


def test_sync_leaves_pattern_rejections_alone():
    r = _rec(URL_A, 1, "rejected", "non_foi_pattern")
    w = FakeWriter([r])
    _sync_exclusions(w, {}, {URL_A})
    assert w.results == [_rec(URL_A, 1, "rejected", "non_foi_pattern")]
    assert w.dirty_body_ids == set()


def test_sync_scoped_touches_only_target_body_and_does_not_warn(capsys):
    a, b = _rec(URL_A, 1), _rec(URL_B, 2, "rejected", EXCLUSION_SIGNAL)
    w = FakeWriter([a, b])
    # scoped to body 3: A listed (body 1), B unlisted exclusion (body 2), plus an unknown URL
    _sync_exclusions(w, {URL_A: ENTRY, "https://x/other.pdf": ENTRY}, set(), public_body=3)
    assert a["verification_status"] == "verified"
    assert b["verification_signal"] == EXCLUSION_SIGNAL
    assert w.results == [a, b]
    assert w.dirty_body_ids == set()
    assert "WARNING" not in capsys.readouterr().out


def test_sync_scoped_applies_to_target_body():
    a, b = _rec(URL_A, 1), _rec(URL_B, 2)
    w = FakeWriter([a, b])
    _sync_exclusions(w, {URL_A: ENTRY, URL_B: ENTRY}, {URL_A}, public_body=1)
    assert a["verification_signal"] == EXCLUSION_SIGNAL
    assert b["verification_status"] == "verified"
    assert w.dirty_body_ids == {1}


def test_process_scoped_run_only_changes_target_body(tmp_path):
    import json
    from lib.file_utils import IncrementalWriter
    out = tmp_path / "output.json"
    a, b = _rec(URL_A, 1), _rec(URL_B, 2)
    out.write_text(json.dumps({"metadata": {"step": "x"}, "results": [a, b]}))
    (tmp_path / "excluded_files.json").write_text(json.dumps({URL_A: ENTRY, URL_B: ENTRY}))
    w = IncrementalWriter(out, "verify_disclosure_files", key_field="file_url", target_public_body=2)
    # target eviction removed body 2's record; scoped input holds only body 2
    process({"results": [dict(b)]}, tmp_path, w, public_body=2)
    by_url = {r["file_url"]: r for r in w.results}
    assert by_url[URL_A]["verification_status"] == "verified"
    assert by_url[URL_B]["verification_signal"] == EXCLUSION_SIGNAL
    assert w.dirty_body_ids == {2}

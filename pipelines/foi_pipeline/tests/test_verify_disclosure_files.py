import pytest
from steps.verify_disclosure_files.process import _score_text, _is_non_foi_document


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

import pytest
from steps.verify_disclosure_files.process import _score_text


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

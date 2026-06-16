import pytest
from steps.find_disclosure_files.process import _score_link


class TestTier1HardRejects:
    def test_rejects_protected_disclosure(self):
        assert _score_link("https://dept.ie/protected-disclosures/report.pdf", "") < 0

    def test_rejects_irishstatutebook(self):
        assert _score_link("http://www.irishstatutebook.ie/pdf/2007/en.si.2007.0133.pdf", "") < 0

    def test_rejects_application_form_hyphen(self):
        assert _score_link("https://dept.ie/freedom-of-information/foi-application-form.pdf", "") < 0

    def test_rejects_application_form_underscore(self):
        assert _score_link("https://dept.ie/foi_application_form.pdf", "") < 0

    def test_rejects_form_filename_with_foi_keyword(self):
        # Filename contains '-form' and URL contains FOI keyword — spec: FOI-Application-Form-English.pdf
        assert _score_link(
            "https://www.garda.ie/en/freedom-of-information/FOI-Application-Form-English.pdf", ""
        ) < 0

    def test_rejects_foi_request_pdf_filename(self):
        assert _score_link("https://www.offaly.ie/app/uploads/FOI-request.pdf", "") < 0

    def test_rejects_foi_application_pdf_filename(self):
        assert _score_link("https://body.ie/uploads/foi-application.pdf", "") < 0

    def test_rejects_non_irish_domain(self):
        assert _score_link(
            "https://www.cookcountystatesattorney.org/sites/g/files/ywwepo351/files/foia.pdf", ""
        ) < 0

    def test_accepts_genuine_foi_log_url(self):
        assert _score_link("https://dept.ie/foi-log/2024-q1.pdf", "") > 0

    def test_accepts_disclosure_log_url(self):
        assert _score_link("https://body.ie/foi-disclosure-2024.pdf", "") > 0

    def test_form_filename_without_foi_keyword_not_rejected_by_form_pattern(self):
        # '-form' in filename but no FOI keyword — the form-filename pattern must NOT fire
        # (URL may still be rejected by other Tier 3 negative keywords, but not by form pattern)
        # We verify only that it doesn't raise and returns a valid score
        result = _score_link("https://dept.ie/registration-form.pdf", "")
        assert result in (1, -1000)


class TestTier2LinkText:
    def test_positive_link_text_accepts_opaque_url(self):
        # No FOI signal in URL — positive link text must override and accept
        result = _score_link(
            "https://assets.cpsa.ie/media/266670/e482e8d6-44ae-4359-9a93-31dfd6498fb4.pdf",
            "Disclosure Log",
        )
        assert result > 0

    def test_positive_link_text_case_insensitive(self):
        assert _score_link("https://assets.example.ie/file.pdf", "FOI Log 2024") > 0

    def test_positive_link_text_foi_disclosure(self):
        assert _score_link("https://assets.example.ie/abc123.pdf", "FOI Disclosure") > 0

    def test_positive_link_text_published_requests(self):
        assert _score_link("https://assets.example.ie/abc123.pdf", "Published Requests") > 0

    def test_negative_link_text_election_results(self):
        assert _score_link(
            "https://www.corkcity.ie/media/rp1n0cju/results-north-west.pdf",
            "Election Results North-West 2024",
        ) < 0

    def test_negative_link_text_visitor_numbers(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/beded0fc/Q1.pdf",
            "Visitor Numbers Q1",
        ) < 0

    def test_negative_link_text_financial_stability(self):
        assert _score_link(
            "https://www.centralbank.ie/docs/fsr.pdf",
            "Financial Stability Review 2022",
        ) < 0

    def test_negative_link_text_economic_letter(self):
        assert _score_link(
            "https://www.centralbank.ie/docs/letter.pdf",
            "Economic Letter Vol 2017 No 1",
        ) < 0

    def test_negative_link_text_quarterly_bulletin(self):
        assert _score_link("https://www.centralbank.ie/docs/qb.pdf", "Quarterly Bulletin") < 0

    def test_negative_link_text_heritage_services(self):
        assert _score_link("https://assets.gov.ie/static/heritage.pdf", "Heritage Services Visitor Numbers") < 0

    def test_negative_link_text_emergency_number(self):
        assert _score_link("http://docstore.kerrycoco.ie/KCCWebsite/emergencynumbersnew.pdf", "Emergency Numbers") < 0


class TestTier3UrlNegativeKeywords:
    def test_rejects_heritage_visitor_numbers_empty_link_text(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/heritage-services-visitor-numbers-2018-2019-2020.pdf", ""
        ) < 0

    def test_rejects_heritage_visitor_numbers_2021(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/heritage-services-visitor-numbers-2021-2022-2023.pdf", ""
        ) < 0

    def test_rejects_cork_schools_heritage_project(self):
        assert _score_link(
            "https://www.corkcity.ie/media/eg4est5c/cork_schools_heritage_project_2026.pdf", ""
        ) < 0

    def test_rejects_minister_calendar(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/Minister_Morans_Calendar_-_Q1_2025.pdf", ""
        ) < 0

    def test_rejects_quarter_range_january_march(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/beded0fc/Q1_January_-_March.pdf", ""
        ) < 0

    def test_rejects_quarter_range_april_june(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/0850f8ab/Q2_April_-_June.pdf", ""
        ) < 0

    def test_rejects_quarter_range_july_september(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/e3e16689/Q3_July_-_September.pdf", ""
        ) < 0

    def test_rejects_quarter_range_october_december(self):
        assert _score_link(
            "https://assets.gov.ie/static/documents/5a616961/Q4_October_-_December.pdf", ""
        ) < 0

    def test_heritage_with_foi_keyword_still_accepted(self):
        # Heritage body's actual FOI log — 'disclosure' in URL → has_positive=True → heritage keyword doesn't fire
        assert _score_link(
            "https://www.heritagecouncil.ie/uploads/foi-disclosure-log-2024.pdf", ""
        ) > 0

    def test_visitor_numbers_with_foi_keyword_still_accepted(self):
        # Unlikely in practice, but if URL also has 'foi-log' it should be accepted
        assert _score_link(
            "https://body.ie/foi-log/visitor-numbers-query-response.pdf", ""
        ) > 0

    def test_generic_link_text_falls_through_to_url_accept(self):
        # Generic text → Tier 3 fires; FOI keyword in URL → accepted
        assert _score_link("https://dept.ie/foi-log.pdf", "Download") > 0

    def test_generic_link_text_falls_through_to_url_reject(self):
        # Generic text → Tier 3 fires; negative URL keyword with no FOI keyword → rejected
        assert _score_link("https://dept.ie/policy.pdf", "Download") < 0

    def test_empty_link_text_falls_through_to_url(self):
        assert _score_link("https://dept.ie/foi-log.pdf", "") > 0

    def test_tier1_still_fires_with_positive_link_text(self):
        # Tier 1 fires unconditionally — positive link text must NOT override it
        assert _score_link(
            "https://www.irishstatutebook.ie/pdf/2007/en.si.2007.0133.pdf",
            "Disclosure Log",
        ) < 0

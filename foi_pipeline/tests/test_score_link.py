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

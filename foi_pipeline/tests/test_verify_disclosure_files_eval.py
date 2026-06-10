import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from steps.verify_disclosure_files.eval.evaluate import run_eval


FAKE_HASH = "abc123"


def _item(url, status, signal=None, file_type="pdf", body_id=1):
    return {
        "file_url": url,
        "verification_status": status,
        "verification_signal": signal,
        "public_body_id": body_id,
        "file_type": file_type,
        "name": "Test Body",
        "disclosure_page_url": "https://example.com/foi",
        "link_text": "",
    }


def _judgment(label, verified="yes"):
    return {"label": label, "rationale": "test", "verified": verified}


class TestTrueRejectionRate:
    def test_perfect_rejection(self):
        items = [_item("https://a.ie/fsr.pdf", "rejected")]
        judgments = {"https://a.ie/fsr.pdf": _judgment("no")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        primary = next(m for m in results.metrics if m.is_primary)
        assert primary.value == 1.0
        assert primary.counts["rejected"] == 1
        assert primary.counts["total_judged_no"] == 1

    def test_zero_rejection_when_all_unverified(self):
        items = [_item("https://a.ie/scanned.pdf", "unverified")]
        judgments = {"https://a.ie/scanned.pdf": _judgment("no")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        primary = next(m for m in results.metrics if m.is_primary)
        assert primary.value == 0.0

    def test_no_judged_entries_returns_zero(self):
        items = [_item("https://a.ie/foi.pdf", "verified")]
        results, issues = run_eval(items, {}, FAKE_HASH)
        primary = next(m for m in results.metrics if m.is_primary)
        assert primary.value == 0.0
        assert primary.counts["total_judged_no"] == 0

    def test_auto_verified_not_counted(self):
        items = [_item("https://a.ie/fsr.pdf", "rejected")]
        judgments = {"https://a.ie/fsr.pdf": _judgment("no", verified="auto")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        primary = next(m for m in results.metrics if m.is_primary)
        assert primary.counts["total_judged_no"] == 0


class TestFalseRejectionRate:
    def test_false_rejection_raises_error_issue(self):
        items = [_item("https://a.ie/foi.pdf", "rejected")]
        judgments = {"https://a.ie/foi.pdf": _judgment("yes")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 1
        assert "https://a.ie/foi.pdf" in error_issues[0].affected_ids

    def test_false_rejection_metric_equals_one(self):
        items = [_item("https://a.ie/foi.pdf", "rejected")]
        judgments = {"https://a.ie/foi.pdf": _judgment("yes")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        fr_metric = next(m for m in results.metrics if m.name == "false_rejection_rate")
        assert fr_metric.value == 1.0

    def test_unverified_judged_yes_not_a_false_rejection(self):
        items = [_item("https://a.ie/scanned.pdf", "unverified")]
        judgments = {"https://a.ie/scanned.pdf": _judgment("yes")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0

    def test_no_false_rejections_produces_no_error_issues(self):
        items = [
            _item("https://a.ie/foi.pdf", "verified"),
            _item("https://a.ie/fsr.pdf", "rejected"),
        ]
        judgments = {
            "https://a.ie/foi.pdf": _judgment("yes"),
            "https://a.ie/fsr.pdf": _judgment("no"),
        }
        results, issues = run_eval(items, judgments, FAKE_HASH)
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0


class TestFalseNegatives:
    def test_judged_no_but_verified_raises_warning(self):
        items = [_item("https://a.ie/fsr.pdf", "verified")]
        judgments = {"https://a.ie/fsr.pdf": _judgment("no")}
        results, issues = run_eval(items, judgments, FAKE_HASH)
        warning_issues = [i for i in issues if i.severity == "warning"]
        assert len(warning_issues) == 1
        assert "https://a.ie/fsr.pdf" in warning_issues[0].affected_ids

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from steps.sync_backlog.run import make_key, score_issue, SEVERITY_WEIGHT


PIPELINE_STEPS = ["find_public_bodies", "find_disclosure_pages", "db_upload"]


class TestMakeKey:
    def test_uses_error_type_when_present(self):
        issue = {"error_type": "MissingField", "description": "something else"}
        assert make_key("find_public_bodies", issue) == "find_public_bodies:missingfield"

    def test_falls_back_to_description(self):
        issue = {"description": "123 records have unrecognized values"}
        assert make_key("db_upload", issue) == "db_upload:123_records_have_unrecognized_values"

    def test_replaces_spaces_and_slashes(self):
        issue = {"description": "some/thing with spaces"}
        key = make_key("step", issue)
        assert " " not in key
        assert "/" not in key

    def test_truncates_slug_to_40_chars(self):
        issue = {"description": "a" * 60}
        key = make_key("step", issue)
        slug = key.split(":", 1)[1]
        assert len(slug) <= 40

    def test_empty_description(self):
        issue = {}
        key = make_key("step", issue)
        assert key == "step:"


class TestScoreIssue:
    def test_error_severity_weighted_3(self):
        issue = {"severity": "error", "affected_count": 10}
        # first of 3 steps → weight 2.0
        score = score_issue("find_public_bodies", issue, PIPELINE_STEPS)
        assert score == 3 * 10 * 2.0

    def test_warning_severity_weighted_2(self):
        issue = {"severity": "warning", "affected_count": 5}
        score = score_issue("find_public_bodies", issue, PIPELINE_STEPS)
        assert score == 2 * 5 * 2.0

    def test_info_severity_weighted_1(self):
        issue = {"severity": "info", "affected_count": 100}
        score = score_issue("find_public_bodies", issue, PIPELINE_STEPS)
        assert score == 1 * 100 * 2.0

    def test_last_step_weight_is_1(self):
        issue = {"severity": "error", "affected_count": 1}
        score = score_issue("db_upload", issue, PIPELINE_STEPS)
        assert score == 3 * 1 * 1.0

    def test_middle_step_interpolated(self):
        issue = {"severity": "error", "affected_count": 1}
        score = score_issue("find_disclosure_pages", issue, PIPELINE_STEPS)
        # index 1 of 3, weight = 2.0 - 1/2 = 1.5
        assert score == 3 * 1 * 1.5

    def test_missing_affected_count_treated_as_zero(self):
        issue = {"severity": "error"}
        score = score_issue("find_public_bodies", issue, PIPELINE_STEPS)
        assert score == 0.0

    def test_unknown_step_uses_index_zero(self):
        issue = {"severity": "error", "affected_count": 1}
        score = score_issue("unknown_step", issue, PIPELINE_STEPS)
        assert score == 3 * 1 * 2.0

    def test_single_step_list_weight_is_2(self):
        issue = {"severity": "error", "affected_count": 1}
        score = score_issue("find_public_bodies", issue, ["find_public_bodies"])
        assert score == 3 * 1 * 2.0

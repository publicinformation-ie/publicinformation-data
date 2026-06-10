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


from steps.sync_backlog.run import assign_priority_tiers


class TestAssignPriorityTiers:
    def _make_items(self, scores):
        return [{"key": f"k{i}", "score": s} for i, s in enumerate(scores)]

    def test_empty_returns_empty(self):
        assert assign_priority_tiers([]) == []

    def test_single_item_gets_high(self):
        result = assign_priority_tiers(self._make_items([5.0]))
        assert result[0]["priority"] == "high"

    def test_three_items_one_each(self):
        items = self._make_items([1.0, 2.0, 3.0])
        result = assign_priority_tiers(items)
        priorities = {r["key"]: r["priority"] for r in result}
        assert priorities["k0"] == "low"
        assert priorities["k1"] == "medium"
        assert priorities["k2"] == "high"

    def test_nine_items_three_each(self):
        items = self._make_items(list(range(1, 10)))
        result = assign_priority_tiers(items)
        by_priority = {"low": 0, "medium": 0, "high": 0}
        for r in result:
            by_priority[r["priority"]] += 1
        assert by_priority["low"] == 3
        assert by_priority["medium"] == 3
        assert by_priority["high"] == 3

    def test_preserves_all_keys(self):
        items = self._make_items([10.0, 20.0, 30.0, 40.0, 50.0])
        result = assign_priority_tiers(items)
        keys = {r["key"] for r in result}
        assert keys == {"k0", "k1", "k2", "k3", "k4"}

    def test_original_fields_preserved(self):
        items = [{"key": "x", "score": 5.0, "step_name": "foo"}]
        result = assign_priority_tiers(items)
        assert result[0]["step_name"] == "foo"

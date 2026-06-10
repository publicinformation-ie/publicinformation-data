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


import json
import pytest
from steps.sync_backlog.run import collect_issues


class TestCollectIssues:
    def _write_pipeline(self, tmp_path, steps):
        (tmp_path / "pipeline.json").write_text(json.dumps({"steps": steps}))

    def _write_issues(self, tmp_path, step_name, issues):
        step_eval = tmp_path / "steps" / step_name / "eval"
        step_eval.mkdir(parents=True, exist_ok=True)
        (step_eval / "issues.json").write_text(json.dumps(issues))

    def test_returns_scored_dict_and_steps_with_eval(self, tmp_path):
        self._write_pipeline(tmp_path, ["step_a", "step_b"])
        self._write_issues(tmp_path, "step_a", [
            {"severity": "error", "description": "bad records", "affected_count": 5}
        ])
        scored, steps_with_eval = collect_issues(tmp_path)
        assert len(scored) == 1
        assert "step_a" in steps_with_eval
        assert "step_b" not in steps_with_eval

    def test_key_format(self, tmp_path):
        self._write_pipeline(tmp_path, ["step_a"])
        self._write_issues(tmp_path, "step_a", [
            {"description": "some problem", "affected_count": 1, "severity": "warning"}
        ])
        scored, _ = collect_issues(tmp_path)
        assert "step_a:some_problem" in scored

    def test_scored_item_has_required_fields(self, tmp_path):
        self._write_pipeline(tmp_path, ["step_a"])
        self._write_issues(tmp_path, "step_a", [
            {"description": "foo", "affected_count": 10, "severity": "error"}
        ])
        scored, _ = collect_issues(tmp_path)
        item = list(scored.values())[0]
        assert "key" in item
        assert "step_name" in item
        assert "issue" in item
        assert "score" in item
        assert "priority" in item

    def test_missing_issues_json_skipped(self, tmp_path):
        self._write_pipeline(tmp_path, ["step_a", "step_b"])
        self._write_issues(tmp_path, "step_a", [
            {"description": "x", "affected_count": 1, "severity": "info"}
        ])
        # step_b has no eval/issues.json
        scored, steps_with_eval = collect_issues(tmp_path)
        assert len(scored) == 1
        assert "step_b" not in steps_with_eval

    def test_multiple_issues_from_same_step(self, tmp_path):
        self._write_pipeline(tmp_path, ["step_a"])
        self._write_issues(tmp_path, "step_a", [
            {"description": "problem one", "affected_count": 5, "severity": "error"},
            {"description": "problem two", "affected_count": 3, "severity": "warning"},
        ])
        scored, _ = collect_issues(tmp_path)
        assert len(scored) == 2

    def test_empty_issues_json_yields_nothing(self, tmp_path):
        self._write_pipeline(tmp_path, ["step_a"])
        self._write_issues(tmp_path, "step_a", [])
        scored, steps_with_eval = collect_issues(tmp_path)
        assert len(scored) == 0
        assert "step_a" in steps_with_eval

import pytest
import sys
import json
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from steps.sync_backlog.run import make_key, score_issue
from steps.sync_backlog.run import assign_priority_tiers
from steps.sync_backlog.run import collect_issues
from steps.sync_backlog.run import load_backlog, save_backlog, reconcile


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


class TestLoadBacklog:
    def test_returns_empty_list_when_file_missing(self, tmp_path):
        result = load_backlog(tmp_path / "backlog.yml")
        assert result == []

    def test_returns_empty_list_for_empty_file(self, tmp_path):
        p = tmp_path / "backlog.yml"
        p.write_text("")
        result = load_backlog(p)
        assert result == []

    def test_loads_issues_list(self, tmp_path):
        p = tmp_path / "backlog.yml"
        p.write_text(yaml.dump({
            "last_updated": "2026-06-10T12:00:00+00:00",
            "issues": [
                {"key": "step_a:foo", "status": "open", "step_name": "step_a"}
            ]
        }))
        result = load_backlog(p)
        assert len(result) == 1
        assert result[0]["key"] == "step_a:foo"

    def test_returns_empty_when_no_issues_key(self, tmp_path):
        p = tmp_path / "backlog.yml"
        p.write_text(yaml.dump({"last_updated": "2026-06-10T12:00:00+00:00"}))
        result = load_backlog(p)
        assert result == []


class TestSaveBacklog:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "backlog.yml"
        save_backlog(p, [], "2026-06-10T12:00:00+00:00")
        assert p.exists()

    def test_roundtrip(self, tmp_path):
        p = tmp_path / "backlog.yml"
        issues = [{"key": "step_a:bar", "status": "open", "step_name": "step_a"}]
        save_backlog(p, issues, "2026-06-10T12:00:00+00:00")
        loaded = load_backlog(p)
        assert len(loaded) == 1
        assert loaded[0]["key"] == "step_a:bar"

    def test_file_contains_header_comment(self, tmp_path):
        p = tmp_path / "backlog.yml"
        save_backlog(p, [], "2026-06-10T12:00:00+00:00")
        content = p.read_text()
        assert "auto-generated" in content


def _make_scored_item(key, step_name, affected=5, severity="warning", priority="medium", suggestion="fix it"):
    return {
        "key": key,
        "step_name": step_name,
        "issue": {
            "affected_count": affected,
            "severity": severity,
            "suggestion_detail": suggestion,
            "description": key.split(":", 1)[1].replace("_", " "),
        },
        "score": 10.0,
        "priority": priority,
    }


def _make_existing_entry(key, step_name, status="open", first_seen="2026-06-09T10:00:00+00:00"):
    return {
        "key": key,
        "step_name": step_name,
        "description": "some problem",
        "severity": "warning",
        "priority": "medium",
        "affected_count": 5,
        "suggestion_detail": "fix it",
        "status": status,
        "first_seen": first_seen,
        "last_seen": first_seen,
    }


RUN_AT = "2026-06-10T12:00:00+00:00"


class TestReconcile:
    def test_creates_new_issue_when_not_in_existing(self):
        scored = {"step_a:foo": _make_scored_item("step_a:foo", "step_a")}
        issues, stats = reconcile(scored, [], {"step_a"}, RUN_AT)
        assert stats["created"] == 1
        assert stats["updated"] == 0
        assert stats["resolved"] == 0
        assert len(issues) == 1
        assert issues[0]["key"] == "step_a:foo"

    def test_new_issue_has_first_seen_and_last_seen(self):
        scored = {"step_a:foo": _make_scored_item("step_a:foo", "step_a")}
        issues, _ = reconcile(scored, [], {"step_a"}, RUN_AT)
        assert issues[0]["first_seen"] == RUN_AT
        assert issues[0]["last_seen"] == RUN_AT

    def test_new_issue_has_open_status(self):
        scored = {"step_a:foo": _make_scored_item("step_a:foo", "step_a")}
        issues, _ = reconcile(scored, [], {"step_a"}, RUN_AT)
        assert issues[0]["status"] == "open"

    def test_unchanged_issue_updates_last_seen_only(self):
        key = "step_a:foo"
        existing = [_make_existing_entry(key, "step_a")]
        scored = {key: _make_scored_item(key, "step_a")}  # same affected/priority/severity
        issues, stats = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert stats["unchanged"] == 1
        assert stats["updated"] == 0
        assert issues[0]["last_seen"] == RUN_AT
        assert issues[0]["first_seen"] == "2026-06-09T10:00:00+00:00"  # preserved

    def test_changed_affected_count_counts_as_update(self):
        key = "step_a:foo"
        existing = [_make_existing_entry(key, "step_a")]  # affected_count=5
        scored = {key: _make_scored_item(key, "step_a", affected=999)}
        issues, stats = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert stats["updated"] == 1
        assert issues[0]["affected_count"] == 999

    def test_changed_priority_counts_as_update(self):
        key = "step_a:foo"
        existing = [_make_existing_entry(key, "step_a")]  # priority=medium
        scored = {key: _make_scored_item(key, "step_a", priority="high")}
        issues, stats = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert stats["updated"] == 1
        assert issues[0]["priority"] == "high"

    def test_resolves_issue_no_longer_in_eval(self):
        key = "step_a:gone"
        existing = [_make_existing_entry(key, "step_a")]
        scored = {}  # issue gone from eval
        issues, stats = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert stats["resolved"] == 1
        assert issues[0]["status"] == "resolved"
        assert issues[0]["resolved_at"] == RUN_AT

    def test_does_not_resolve_when_step_has_no_eval(self):
        key = "step_a:gone"
        existing = [_make_existing_entry(key, "step_a")]
        scored = {}
        # step_a not in steps_with_eval — eval hasn't run, don't resolve
        issues, stats = reconcile(scored, existing, set(), RUN_AT)
        assert stats["resolved"] == 0
        assert issues[0]["status"] == "open"

    def test_does_not_re_resolve_already_resolved_issue(self):
        key = "step_a:old"
        existing = [_make_existing_entry(key, "step_a", status="resolved")]
        scored = {}
        issues, stats = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert stats["resolved"] == 0
        assert issues[0]["status"] == "resolved"

    def test_reopens_resolved_issue_if_it_reappears(self):
        key = "step_a:regressed"
        existing = [_make_existing_entry(key, "step_a", status="resolved")]
        scored = {key: _make_scored_item(key, "step_a")}
        issues, stats = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert stats["updated"] == 1
        assert issues[0]["status"] == "open"

    def test_preserves_first_seen_on_update(self):
        key = "step_a:foo"
        original_first_seen = "2026-06-01T00:00:00+00:00"
        existing = [_make_existing_entry(key, "step_a", first_seen=original_first_seen)]
        scored = {key: _make_scored_item(key, "step_a", affected=999)}
        issues, _ = reconcile(scored, existing, {"step_a"}, RUN_AT)
        assert issues[0]["first_seen"] == original_first_seen

    def test_result_has_run_at_stats(self):
        _, stats = reconcile({}, [], set(), RUN_AT)
        assert "created" in stats
        assert "updated" in stats
        assert "resolved" in stats
        assert "unchanged" in stats

    def test_empty_run_with_empty_existing(self):
        issues, stats = reconcile({}, [], set(), RUN_AT)
        assert issues == []
        assert stats["created"] == 0

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


from steps.sync_backlog.run import build_body, parse_pipeline_key


class TestBuildBody:
    def test_contains_affected_count(self):
        issue = {"affected_count": 42, "suggestion_detail": "fix it"}
        body = build_body("step_a", issue, "2026-06-10T12:00:00Z")
        assert "42" in body

    def test_contains_step_name(self):
        issue = {"affected_count": 1, "suggestion_detail": "ok"}
        body = build_body("step_a", issue, "2026-06-10T12:00:00Z")
        assert "step_a" in body

    def test_contains_suggestion(self):
        issue = {"affected_count": 1, "suggestion_detail": "add to column_map"}
        body = build_body("step_a", issue, "2026-06-10T12:00:00Z")
        assert "add to column_map" in body

    def test_contains_run_at_timestamp(self):
        issue = {"affected_count": 1, "suggestion_detail": ""}
        body = build_body("step_a", issue, "2026-06-10T12:00:00Z")
        assert "2026-06-10T12:00:00Z" in body

    def test_contains_pipeline_key_comment(self):
        issue = {"description": "bad rows", "affected_count": 1, "suggestion_detail": ""}
        body = build_body("step_a", issue, "2026-06-10T12:00:00Z")
        assert "<!-- pipeline-key: step_a:bad_rows -->" in body

    def test_uses_error_type_for_key_when_present(self):
        issue = {"error_type": "NullField", "description": "ignored", "affected_count": 1, "suggestion_detail": ""}
        body = build_body("step_a", issue, "2026-06-10T12:00:00Z")
        assert "<!-- pipeline-key: step_a:nullfield -->" in body


class TestParsePipelineKey:
    def test_extracts_key(self):
        body = "some text\n<!-- pipeline-key: step_a:bad_rows -->\nmore text"
        assert parse_pipeline_key(body) == "step_a:bad_rows"

    def test_returns_none_when_absent(self):
        assert parse_pipeline_key("no key here") is None

    def test_returns_none_for_empty_body(self):
        assert parse_pipeline_key("") is None

    def test_returns_none_for_none(self):
        assert parse_pipeline_key(None) is None

    def test_key_with_colons_and_underscores(self):
        body = "<!-- pipeline-key: extract_disclosures_canonicalize:1183_records_have_unrecognize -->"
        result = parse_pipeline_key(body)
        assert result == "extract_disclosures_canonicalize:1183_records_have_unrecognize"


import requests
import unittest.mock as mock
from steps.sync_backlog.run import ensure_labels, REQUIRED_LABELS


class TestEnsureLabels:
    def _make_session(self, token="tok"):
        session = requests.Session()
        session.headers["Authorization"] = f"token {token}"
        return session

    def test_creates_missing_labels(self):
        repo_api_url = "https://codeberg.org/api/v1/repos/owner/repo"
        session = mock.MagicMock()
        # GET /labels returns empty list
        session.get.return_value.json.return_value = []
        session.get.return_value.raise_for_status = mock.MagicMock()
        # POST /labels returns created label
        created_ids = iter(range(1, 100))
        def post_side_effect(url, **kwargs):
            resp = mock.MagicMock()
            resp.json.return_value = {"id": next(created_ids), "name": kwargs["json"]["name"]}
            resp.raise_for_status = mock.MagicMock()
            return resp
        session.post.side_effect = post_side_effect

        result = ensure_labels(session, repo_api_url, set())
        assert "pipeline-issue" in result
        assert "severity:error" in result
        assert "priority:high" in result

    def test_skips_existing_labels(self):
        repo_api_url = "https://codeberg.org/api/v1/repos/owner/repo"
        session = mock.MagicMock()
        existing = [{"id": 10, "name": "pipeline-issue"}]
        session.get.return_value.json.return_value = existing
        session.get.return_value.raise_for_status = mock.MagicMock()
        created_ids = iter(range(100, 200))
        def post_side_effect(url, **kwargs):
            resp = mock.MagicMock()
            resp.json.return_value = {"id": next(created_ids), "name": kwargs["json"]["name"]}
            resp.raise_for_status = mock.MagicMock()
            return resp
        session.post.side_effect = post_side_effect

        result = ensure_labels(session, repo_api_url, set())
        assert result["pipeline-issue"] == 10

    def test_creates_step_labels_for_steps_with_eval(self):
        repo_api_url = "https://codeberg.org/api/v1/repos/owner/repo"
        session = mock.MagicMock()
        session.get.return_value.json.return_value = []
        session.get.return_value.raise_for_status = mock.MagicMock()
        created_ids = iter(range(1, 200))
        def post_side_effect(url, **kwargs):
            resp = mock.MagicMock()
            resp.json.return_value = {"id": next(created_ids), "name": kwargs["json"]["name"]}
            resp.raise_for_status = mock.MagicMock()
            return resp
        session.post.side_effect = post_side_effect

        result = ensure_labels(session, repo_api_url, {"find_public_bodies"})
        assert "step:find_public_bodies" in result

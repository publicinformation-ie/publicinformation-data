import json
from pathlib import Path

import evaluate as runner


def test_discover_steps_finds_eval_dirs(tmp_path):
    steps = tmp_path / "steps"
    (steps / "alpha" / "eval").mkdir(parents=True)
    (steps / "alpha" / "eval" / "evaluate.py").write_text("")
    (steps / "beta").mkdir(parents=True)  # no eval/ -> excluded
    order = ["beta", "alpha"]
    found = runner.discover_eval_steps(steps, order)
    assert found == ["alpha"]  # only steps with eval/evaluate.py, in pipeline order


def test_eval_dependencies_lists_present_files(tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "evaluate.py").write_text("")
    (eval_dir / "labels.csv").write_text("")
    deps = runner.eval_dependencies(eval_dir)
    names = {p.name for p in deps}
    assert "evaluate.py" in names
    assert "labels.csv" in names


def test_aggregate_issues_groups_by_upstream(tmp_path):
    step_a = tmp_path / "steps" / "a" / "eval"
    step_a.mkdir(parents=True)
    (step_a / "issues.json").write_text(json.dumps([
        {"severity": "warning", "description": "d1", "affected_count": 1,
         "affected_ids": ["x"], "suggested_upstream_step": "find_disclosure_files",
         "suggestion_detail": "filter", "confidence": 0.8},
        {"severity": "info", "description": "d2", "affected_count": 1,
         "affected_ids": ["y"], "suggested_upstream_step": None,
         "suggestion_detail": None, "confidence": 1.0},
    ]))
    grouped = runner.aggregate_issues(tmp_path / "steps", ["a"])
    assert "find_disclosure_files" in grouped
    assert len(grouped["find_disclosure_files"]) == 1


def test_load_primary_metric_reads_cached_results(tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "eval_results.json").write_text(json.dumps({
        "step": "a", "input_hash": "a" * 64, "judge_model": None,
        "metrics": [
            {"name": "recall", "value": 0.6, "counts": {}, "is_primary": False},
            {"name": "f1", "value": 0.57, "counts": {}, "is_primary": True},
        ],
    }))
    name, value = runner.load_primary_metric(eval_dir)
    assert name == "f1"
    assert value == 0.57

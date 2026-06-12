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


def test_main_steps_flag_only_runs_requested(tmp_path, monkeypatch):
    """--steps runs only the named steps, skipping all others even if stale."""
    # Set up fake pipeline structure
    steps_dir = tmp_path / "steps"
    for name in ["alpha", "beta"]:
        eval_dir = steps_dir / name / "eval"
        eval_dir.mkdir(parents=True)
        (eval_dir / "evaluate.py").write_text("")
        # Create eval_results.json so alpha and beta appear up-to-date unless forced
        (eval_dir / "eval_results.json").write_text(json.dumps({
            "step": name, "input_hash": "x" * 64, "judge_model": None,
            "metrics": [{"name": "score", "value": 0.5, "counts": {}, "is_primary": True}],
        }))
    pipeline_json = tmp_path / "pipeline.json"
    pipeline_json.write_text('{"steps": ["alpha", "beta"]}')

    ran = []

    def fake_run(sd, step, pd):
        ran.append(step)
        return 0

    # Mock the 'here' reference to point to tmp_path
    original_main = runner.main

    def mocked_main(argv=None):
        from pathlib import Path
        import argparse
        import json as json_lib

        parser = argparse.ArgumentParser(description="Run pipeline evaluations")
        parser.add_argument("--force", action="store_true", help="Recompute all evals")
        parser.add_argument("--steps", nargs="+", help="Force just these steps")
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--headline", action="store_true", help="Compute north-star metric")
        parser.add_argument("--check", action="store_true", help="Exit non-zero on regression")
        parser.add_argument("--update-baseline", action="store_true")
        args = parser.parse_args(argv)

        here = tmp_path
        steps_dir = here / "steps"
        pipeline_order = json_lib.loads((here / "pipeline.json").read_text())["steps"]
        eval_steps = runner.discover_eval_steps(steps_dir, pipeline_order)

        for step in eval_steps:
            eval_dir = steps_dir / step / "eval"
            results_path = eval_dir / "eval_results.json"
            if args.steps and step not in args.steps:
                continue
            forced = args.force or bool(args.steps)
            if not forced and not runner.eval_utils.is_eval_stale(results_path, runner.eval_dependencies(eval_dir)):
                continue
            fake_run(steps_dir, step, here)

        return 0

    monkeypatch.setattr(runner, "run_step_eval", fake_run)
    monkeypatch.setattr(runner, "main", mocked_main)
    mocked_main(["--steps", "alpha"])
    assert ran == ["alpha"]
    assert "beta" not in ran

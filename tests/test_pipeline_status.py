import json
import os
from pathlib import Path

import pytest

from scripts.pipeline_status import (
    Command,
    PipelineDataError,
    build_report,
    discover_pipelines,
    format_paid,
    entry_output,
    input_entry,
    load_config,
    read_steps,
)

T0 = 1_700_000_000


def make_pipeline(repo: Path, dir_name: str, config: dict) -> Path:
    d = repo / "pipelines" / dir_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "pipeline.json").write_text(json.dumps(config))
    return d


def write_output(repo: Path, entry_dir: Path, mtime: float, size_bytes: int = 2) -> None:
    entry_dir.mkdir(parents=True, exist_ok=True)
    out = entry_dir / "output.json"
    out.write_text("{}"[:size_bytes] if size_bytes else "")
    os.utime(out, (mtime, mtime))


def write_status(entry_dir: Path, record_count, completed_at: str = "2026-11-15T19:08:00+00:00") -> None:
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / "pipeline-status.json").write_text(
        json.dumps({"record_count": record_count, "completed_at": completed_at})
    )


def write_errors(entry_dir: Path, payload) -> None:
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / "errors.json").write_text(json.dumps(payload))


def step_dir(p: Path, name: str) -> Path:
    return p / "steps" / name


def states(repo: Path, p: Path):
    cfg = load_config(p)
    return read_steps(repo, p, cfg)


# ---------- Task 1: step model ----------

def test_states_never_stale_ok(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b", "c"]})
    write_output(tmp_path, step_dir(p, "a"), T0)
    write_output(tmp_path, step_dir(p, "b"), T0 + 10)
    assert [s.state for s in states(tmp_path, p)] == ["ok", "ok", "never"]


def test_stale_when_input_newer(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b"]})
    write_output(tmp_path, step_dir(p, "a"), T0 + 20)
    write_output(tmp_path, step_dir(p, "b"), T0 + 10)
    assert [s.state for s in states(tmp_path, p)] == ["ok", "stale"]


def test_input_steps_override(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b", "c"], "input_steps": {"c": "a"}})
    write_output(tmp_path, step_dir(p, "a"), T0)
    write_output(tmp_path, step_dir(p, "b"), T0 + 30)
    write_output(tmp_path, step_dir(p, "c"), T0 + 10)
    steps = states(tmp_path, p)
    assert steps[2].state == "ok"
    assert steps[2].input == "a"


def test_input_steps_absolute_path(tmp_path):  # Review Focus 3
    other = make_pipeline(tmp_path, "other_pipeline", {"steps": ["x"]})
    write_output(tmp_path, step_dir(other, "x"), T0 + 50)
    p = make_pipeline(
        tmp_path,
        "x_pipeline",
        {"steps": ["a", "b"], "input_steps": {"b": "/pipelines/other_pipeline/steps/x"}},
    )
    write_output(tmp_path, step_dir(p, "a"), T0)
    write_output(tmp_path, step_dir(p, "b"), T0 + 10)
    assert states(tmp_path, p)[1].state == "stale"


def test_upstream_entry_state(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["/pipelines/cso_pipeline/steps/r", "a"]})
    assert states(tmp_path, p)[0].state == "upstream"


def test_always_state_only_when_not_never_or_stale(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b"], "always_run": ["b"]})
    write_output(tmp_path, step_dir(p, "a"), T0)
    assert states(tmp_path, p)[1].state == "never"
    write_output(tmp_path, step_dir(p, "b"), T0 + 10)
    assert states(tmp_path, p)[1].state == "always"


def test_code_state_when_py_newer_than_output(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b"]})
    write_output(tmp_path, step_dir(p, "a"), T0)
    write_output(tmp_path, step_dir(p, "b"), T0 + 10)
    py = step_dir(p, "b") / "process.py"
    py.write_text("")
    os.utime(py, (T0 + 20, T0 + 20))
    assert states(tmp_path, p)[1].state == "code"
    os.utime(py, (T0, T0))
    assert states(tmp_path, p)[1].state == "ok"


def test_status_file_missing_malformed_or_null(tmp_path):  # Review Focus 1
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b", "c"]})
    for n in "abc":
        write_output(tmp_path, step_dir(p, n), T0)
    (step_dir(p, "b") / "pipeline-status.json").write_text("{not json")
    write_status(step_dir(p, "c"), None)
    a, b, c = states(tmp_path, p)
    assert (a.completed_at, a.record_count) == (None, None)
    assert (b.completed_at, b.record_count) == (None, None)
    assert c.record_count is None


def test_errors_count_list_dict_malformed_missing(tmp_path):  # Review Focus 2
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b", "c", "d"]})
    for n in "abcd":
        write_output(tmp_path, step_dir(p, n), T0)
    write_errors(step_dir(p, "a"), [1, 2, 3])
    write_errors(step_dir(p, "b"), {"a": 1})
    (step_dir(p, "c") / "errors.json").write_text("{bad")
    assert [s.errors for s in states(tmp_path, p)] == [3, 0, 0, 0]


def test_paid_kinds_attached(tmp_path):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a", "b"], "paid_steps": {"b": ["llm"]}})
    steps = states(tmp_path, p)
    assert steps[1].paid == ["llm"]
    assert steps[0].paid == []


@pytest.mark.parametrize("paid", [{"zzz": ["llm"]}, {"a": ["money"]}, {"a": []}])
def test_load_config_rejects_bad_paid_steps(tmp_path, paid):
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["a"], "paid_steps": paid})
    with pytest.raises(PipelineDataError):
        load_config(p)


def test_load_config_rejects_missing_or_bad_json(tmp_path):
    empty = tmp_path / "pipelines" / "e_pipeline"
    empty.mkdir(parents=True)
    with pytest.raises(PipelineDataError):
        load_config(empty)
    (empty / "pipeline.json").write_text("{bad")
    with pytest.raises(PipelineDataError):
        load_config(empty)
    (empty / "pipeline.json").write_text(json.dumps({"steps": "a"}))
    with pytest.raises(PipelineDataError):
        load_config(empty)


def test_entry_output_and_input_entry(tmp_path):
    p = tmp_path / "pipelines" / "x_pipeline"
    assert entry_output(tmp_path, p, "/pipelines/o/steps/s") == tmp_path / "pipelines/o/steps/s/output.json"
    assert entry_output(tmp_path, p, "a") == p / "steps/a/output.json"
    assert input_entry(["a", "b"], 1, {}) == "a"
    assert input_entry(["a", "b"], 0, {}) is None
    assert input_entry(["a", "b"], 1, {"b": "z"}) == "z"


# ---------- Task 2: report ----------

def build(tmp_path, steps, mtimes, counts=None, **cfg):
    """Create pipeline x_pipeline; mtimes maps step -> output mtime (absent = no output)."""
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": steps, **cfg})
    for name, t in mtimes.items():
        write_output(tmp_path, step_dir(p, name), t)
    for name, n in (counts or {}).items():
        write_status(step_dir(p, name), n)
    return p


BASE = "uv run python pipelines/x_pipeline/process.py pipelines/x_pipeline --stop-on-error"


def test_window_cascades_from_first_stale(tmp_path):
    p = build(tmp_path, list("abcd"), {"a": T0 + 20, "b": T0 + 10, "c": T0 + 30, "d": T0 + 40})
    r = build_report(tmp_path, p)
    assert r.window == ["b", "c", "d"]
    assert r.run_start == "b"
    assert r.status == "needs_run"


def test_window_branch_not_triggered_stays_out(tmp_path):
    p = build(
        tmp_path, list("abcd"),
        {"a": T0 + 20, "b": T0 + 10, "c": T0 + 30, "d": T0 + 40},
        input_steps={"c": "a", "d": "c"}, paid_steps={"c": ["llm"]},
    )
    r = build_report(tmp_path, p)
    assert r.window == ["b"]
    assert r.paid_in_window == {}


def test_always_run_before_stale_widens_window(tmp_path):  # Review Focus 5
    p = build(
        tmp_path, list("abcd"),
        {"a": T0, "b": T0 + 5, "c": T0 + 50, "d": T0 + 10},
        counts={"c": 77}, always_run=["b"],
    )
    r = build_report(tmp_path, p)
    assert r.window == ["b", "c", "d"]
    assert r.run_start == "d"
    assert r.volume == 77


def test_volume_from_run_start_input_and_unknown_cases(tmp_path):
    p = build(tmp_path, list("ab"), {"a": T0 + 20, "b": T0}, counts={"a": 278})
    assert build_report(tmp_path, p).volume == 278
    # run_start is first step -> None
    p2 = make_pipeline(tmp_path, "y_pipeline", {"steps": ["a", "b"]})
    assert build_report(tmp_path, p2).volume is None
    # input has no status -> None
    p3 = make_pipeline(tmp_path, "z_pipeline", {"steps": ["a", "b"]})
    write_output(tmp_path, step_dir(p3, "a"), T0)
    assert build_report(tmp_path, p3).volume is None


def test_volume_from_upstream_input(tmp_path):
    up = tmp_path / "pipelines/cso_pipeline/steps/r"
    write_output(tmp_path, up, T0)
    write_status(up, 50)
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["/pipelines/cso_pipeline/steps/r", "a"]})
    r = build_report(tmp_path, p)
    assert r.status == "needs_run"
    assert r.volume == 50


def test_blocked_when_upstream_missing_or_empty(tmp_path):  # Review Focus 4
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["/pipelines/cso_pipeline/steps/r", "a"]})
    r = build_report(tmp_path, p)
    assert (r.status, r.blocked_by, r.commands) == ("blocked", "cso_pipeline", [])
    write_output(tmp_path, tmp_path / "pipelines/cso_pipeline/steps/r", T0, size_bytes=0)
    assert build_report(tmp_path, p).status == "blocked"


def test_commands_bounded_then_paid(tmp_path):
    p = build(
        tmp_path, list("abcd"),
        {"a": T0 + 20, "b": T0 + 10, "c": T0 + 30, "d": T0 + 40},
        paid_steps={"c": ["llm"], "d": ["apify"]},
    )
    r = build_report(tmp_path, p)
    assert r.commands == [Command(BASE + " --to b", []), Command(BASE, ["c", "d"])]
    assert r.paid_in_window == {"llm": 1, "apify": 1}


def test_commands_only_paid_when_first_window_step_paid(tmp_path):
    p = build(tmp_path, ["a"], {}, paid_steps={"a": ["llm"]})
    assert build_report(tmp_path, p).commands == [Command(BASE, ["a"])]


def test_code_signal_command_uses_from(tmp_path):
    p = build(tmp_path, list("abc"), {"a": T0, "b": T0 + 10, "c": T0 + 20}, counts={"b": 9})
    py = step_dir(p, "c") / "process.py"
    py.write_text("")
    os.utime(py, (T0 + 30, T0 + 30))
    r = build_report(tmp_path, p)
    assert r.status == "up_to_date"
    assert r.code_changed_from == "c"
    assert r.commands[-1].command.endswith("--stop-on-error --from c")
    assert r.volume == 9


def test_code_signal_window_excludes_always_before_from(tmp_path):
    p = build(tmp_path, list("abc"), {"a": T0, "b": T0 + 10, "c": T0 + 20}, always_run=["a"])
    py = step_dir(p, "c") / "process.py"
    py.write_text("")
    os.utime(py, (T0 + 30, T0 + 30))
    assert build_report(tmp_path, p).window == ["c"]


def test_always_only_gives_up_to_date_with_note(tmp_path):
    p = build(
        tmp_path, list("abc"), {"a": T0, "b": T0 + 10, "c": T0 + 20},
        always_run=["b"], paid_steps={"c": ["llm"]},
    )
    r = build_report(tmp_path, p)
    assert r.status == "up_to_date"
    assert r.commands == []
    assert r.note == "any run re-checks sources from b → 2 steps, paid: llm"


def test_format_paid():
    assert format_paid({"llm": 2, "apify": 1}) == "llm×2, apify"
    assert format_paid({}) == "—"


def test_errors_total_and_top3(tmp_path):
    names = list("abcde")
    p = build(tmp_path, names, {n: T0 for n in names})
    for n, c in zip(names, [5, 0, 9, 5, 1]):
        write_errors(step_dir(p, n), list(range(c)))
    r = build_report(tmp_path, p)
    assert r.error_total == 20
    assert r.top_error_steps == [("c", 9), ("a", 5), ("d", 5)]


def test_last_run_excludes_upstream(tmp_path):
    up = tmp_path / "pipelines/cso_pipeline/steps/r"
    write_output(tmp_path, up, T0)
    write_status(up, 1, "2026-11-16T10:00:00+00:00")
    p = make_pipeline(tmp_path, "x_pipeline", {"steps": ["/pipelines/cso_pipeline/steps/r", "a"]})
    write_output(tmp_path, step_dir(p, "a"), T0 + 5)
    write_status(step_dir(p, "a"), 1, "2026-11-15T10:00:00+00:00")
    assert build_report(tmp_path, p).last_run == "2026-11-15T10:00:00+00:00"


def test_discover_pipelines_sorted(tmp_path):
    make_pipeline(tmp_path, "b_pipeline", {"steps": []})
    make_pipeline(tmp_path, "a_pipeline", {"steps": []})
    (tmp_path / "pipelines/c_pipeline").mkdir()
    assert [d.name for d in discover_pipelines(tmp_path)] == ["a_pipeline", "b_pipeline"]

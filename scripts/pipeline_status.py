"""Read-only status overview for every pipeline.

Usage: uv run python scripts/pipeline_status.py [--pipeline NAME] [--json]

Never imports or runs a step. Only stats output.json; reads pipeline.json,
pipeline-status.json and errors.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

COST_KINDS: tuple[str, ...] = ("llm", "apify")


# ---------------------------------------------------------------------------
# Step model
# ---------------------------------------------------------------------------

class PipelineDataError(Exception):
    pass


def load_config(pipeline_dir: Path) -> dict:
    name = pipeline_dir.name
    path = pipeline_dir / "pipeline.json"
    try:
        config = json.loads(path.read_text())
    except FileNotFoundError:
        raise PipelineDataError(f"{name}: pipeline.json not found")
    except (OSError, ValueError) as exc:
        raise PipelineDataError(f"{name}: pipeline.json unreadable: {exc}")
    if not isinstance(config, dict):
        raise PipelineDataError(f"{name}: pipeline.json must be an object")
    steps = config.get("steps")
    if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
        raise PipelineDataError(f"{name}: 'steps' must be a list of strings")
    paid = config.get("paid_steps", {})
    if not isinstance(paid, dict):
        raise PipelineDataError(f"{name}: 'paid_steps' must be an object")
    for key, kinds in paid.items():
        if key.startswith("/") or key not in steps:
            raise PipelineDataError(f"{name}: paid_steps key '{key}' is not a step of this pipeline")
        if not isinstance(kinds, list) or not kinds:
            raise PipelineDataError(f"{name}: paid_steps['{key}'] must be a non-empty list")
        for kind in kinds:
            if kind not in COST_KINDS:
                raise PipelineDataError(
                    f"{name}: paid_steps['{key}'] has unknown cost kind '{kind}' (allowed: {', '.join(COST_KINDS)})"
                )
    return config


def entry_output(repo_root: Path, pipeline_dir: Path, entry: str) -> Path:
    if entry.startswith("/"):
        return repo_root / entry.lstrip("/") / "output.json"
    return pipeline_dir / "steps" / entry / "output.json"


def input_entry(steps: list[str], index: int, input_steps: dict[str, str]) -> str | None:
    name = steps[index]
    if name in input_steps:
        return input_steps[name]
    return steps[index - 1] if index > 0 else None


@dataclass
class StepInfo:
    name: str
    state: str
    completed_at: str | None
    record_count: int | None
    errors: int
    paid: list[str]
    input: str | None
    output: Path


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _read_status(output: Path) -> tuple[str | None, int | None]:
    data = _read_json(output.parent / "pipeline-status.json")
    if not isinstance(data, dict):
        return None, None
    completed = data.get("completed_at")
    count = data.get("record_count")
    return (
        completed if isinstance(completed, str) else None,
        count if isinstance(count, int) and not isinstance(count, bool) else None,
    )


def _count_errors(output: Path) -> int:
    data = _read_json(output.parent / "errors.json")
    return len(data) if isinstance(data, list) else 0


def _code_newer(output: Path, mtime: float) -> bool:
    step_dir = output.parent
    return any(p.stat().st_mtime > mtime for p in step_dir.rglob("*.py"))


def read_steps(repo_root: Path, pipeline_dir: Path, config: dict) -> list[StepInfo]:
    steps: list[str] = config["steps"]
    input_steps: dict[str, str] = config.get("input_steps", {})
    always_run = set(config.get("always_run", []))
    paid = config.get("paid_steps", {})
    infos: list[StepInfo] = []
    for i, name in enumerate(steps):
        out = entry_output(repo_root, pipeline_dir, name)
        inp = input_entry(steps, i, input_steps)
        completed_at, record_count = _read_status(out)
        upstream = name.startswith("/")
        if upstream:
            state = "upstream"
        elif not out.exists():
            state = "never"
        else:
            own = out.stat().st_mtime
            inp_out = entry_output(repo_root, pipeline_dir, inp) if inp is not None else None
            if inp_out is not None and inp_out.exists() and inp_out.stat().st_mtime > own:
                state = "stale"
            elif name in always_run:
                state = "always"
            elif _code_newer(out, own):
                state = "code"
            else:
                state = "ok"
        infos.append(
            StepInfo(
                name=name,
                state=state,
                completed_at=completed_at,
                record_count=record_count,
                errors=0 if upstream else _count_errors(out),
                paid=[] if upstream else list(paid.get(name, [])),
                input=inp,
                output=out,
            )
        )
    return infos


# ---------------------------------------------------------------------------
# Report: simulate the runner's skip rule
# ---------------------------------------------------------------------------

def run_window(steps: list[StepInfo], from_step: str | None = None) -> list[str]:
    start = next((i for i, s in enumerate(steps) if s.name == from_step), 0) if from_step else 0
    will_run: set[str] = set()
    for i, s in enumerate(steps):
        if i < start or s.state == "upstream":
            continue
        if s.name == from_step or s.state in ("never", "stale", "always") or s.input in will_run:
            will_run.add(s.name)
    return [s.name for s in steps if s.name in will_run]


def paid_summary(steps: list[StepInfo], window: list[str]) -> dict[str, int]:
    in_window = set(window)
    counts = {k: 0 for k in COST_KINDS}
    for s in steps:
        if s.name in in_window:
            for kind in s.paid:
                counts[kind] += 1
    return {k: n for k, n in counts.items() if n}


def format_paid(summary: dict[str, int]) -> str:
    if not summary:
        return "—"
    return ", ".join(f"{k}×{n}" if n > 1 else k for k, n in summary.items())


@dataclass
class Command:
    command: str
    paid_steps: list[str]


def suggest_commands(
    dir_name: str, steps: list[StepInfo], window: list[str], from_step: str | None
) -> list[Command]:
    base = f"uv run python pipelines/{dir_name}/process.py pipelines/{dir_name} --stop-on-error"
    if from_step:
        base += f" --from {from_step}"
    in_window = set(window)
    paid_in = [s.name for s in steps if s.name in in_window and s.paid]
    if not paid_in:
        return [Command(base, [])]
    names = [s.name for s in steps]
    if paid_in[0] == window[0]:
        return [Command(base, paid_in)]
    before = names[names.index(paid_in[0]) - 1]
    return [Command(f"{base} --to {before}", []), Command(base, paid_in)]


@dataclass
class PipelineReport:
    dir_name: str
    name: str
    status: str  # "needs_run" | "blocked" | "up_to_date"
    last_run: str | None
    run_start: str | None
    code_changed_from: str | None
    window: list[str]
    volume: int | None
    paid_in_window: dict[str, int]
    error_total: int
    top_error_steps: list[tuple[str, int]]
    commands: list[Command]
    note: str | None
    blocked_by: str | None
    steps: list[StepInfo]
    has_status_script: bool = field(default=False)


def build_report(repo_root: Path, pipeline_dir: Path) -> PipelineReport:
    config = load_config(pipeline_dir)
    steps = read_steps(repo_root, pipeline_dir, config)
    dir_name = pipeline_dir.name

    def input_volume(step_name: str | None) -> int | None:
        if step_name is None:
            return None
        step = next(s for s in steps if s.name == step_name)
        if step.input is None:
            return None
        inp = next((s for s in steps if s.name == step.input), None)
        if inp is not None:
            return inp.record_count
        return _read_status(entry_output(repo_root, pipeline_dir, step.input))[1]

    status, blocked_by = "up_to_date", None
    window: list[str] = []
    commands: list[Command] = []
    volume = None
    note = None
    run_start = next((s.name for s in steps if s.state in ("never", "stale")), None)
    code_from = next((s.name for s in steps if s.state == "code"), None)

    blocker = next(
        (s for s in steps if s.state == "upstream" and (not s.output.exists() or s.output.stat().st_size == 0)),
        None,
    )
    if blocker is not None:
        status, blocked_by = "blocked", Path(blocker.name).parts[2]
    elif run_start is not None:
        status = "needs_run"
        window = run_window(steps)
        volume = input_volume(run_start)
        commands = suggest_commands(dir_name, steps, window, None)
    elif code_from is not None:
        window = run_window(steps, from_step=code_from)
        volume = input_volume(code_from)
        commands = suggest_commands(dir_name, steps, window, code_from)
    elif any(s.state == "always" for s in steps):
        w = run_window(steps)
        note = f"any run re-checks sources from {w[0]} → {len(w)} steps, paid: {format_paid(paid_summary(steps, w))}"

    errors = [(s.name, s.errors) for s in steps if s.errors > 0]
    top = sorted(errors, key=lambda e: -e[1])[:3]  # stable: ties keep pipeline order
    stamps = [
        (datetime.fromisoformat(s.completed_at), s.completed_at)
        for s in steps
        if s.state != "upstream" and s.completed_at
    ]
    last_run = max(stamps, key=lambda t: t[0])[1] if stamps else None

    return PipelineReport(
        dir_name=dir_name,
        name=dir_name.removesuffix("_pipeline"),
        status=status,
        last_run=last_run,
        run_start=run_start,
        code_changed_from=code_from,
        window=window,
        volume=volume,
        paid_in_window=paid_summary(steps, window),
        error_total=sum(n for _, n in errors),
        top_error_steps=top,
        commands=commands,
        note=note,
        blocked_by=blocked_by,
        steps=steps,
        has_status_script=(pipeline_dir / "status.py").exists(),
    )


def discover_pipelines(repo_root: Path) -> list[Path]:
    root = repo_root / "pipelines"
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir() if (d / "pipeline.json").is_file())

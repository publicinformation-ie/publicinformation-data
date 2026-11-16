"""Read-only status overview for every pipeline.

Usage: uv run python scripts/pipeline_status.py [--pipeline NAME] [--json]

Never imports or runs a step. Only stats output.json; reads pipeline.json,
pipeline-status.json and errors.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
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


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def sort_reports(reports: list[PipelineReport]) -> list[PipelineReport]:
    return sorted(
        reports,
        key=lambda r: (r.status not in ("needs_run", "blocked"), -r.error_total, r.name),
    )


def _local(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return "—"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    fmt = lambda cells: "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()
    return "\n".join([fmt(headers), *(fmt(r) for r in rows)])


def _volume_cell(r: PipelineReport) -> str:
    if not r.window:
        return "—"
    return f"up to {r.volume:,}" if r.volume is not None else "unknown"


def _needs_run_cell(r: PipelineReport) -> str:
    if r.status == "blocked":
        cell = f"blocked: run {r.blocked_by.removesuffix('_pipeline')} first"
    else:
        cell = (r.run_start if r.status == "needs_run" else None) or "—"
    if r.code_changed_from:
        cell += f" (code: {r.code_changed_from})"
    return cell


def _command_lines(r: PipelineReport, indent: str = "  ") -> list[str]:
    lines = []
    kinds = {s.name: s.paid for s in r.steps}
    for c in r.commands:
        line = indent + c.command
        if c.paid_steps:
            line += "  # PAID: " + ", ".join(f"{n} ({', '.join(kinds[n])})" for n in c.paid_steps)
        lines.append(line)
    return lines


def render_overview(reports: list[PipelineReport]) -> str:
    headers = ["PIPELINE", "LAST RUN", "NEEDS RUN FROM", "VOLUME", "PAID", "ERRORS", "TOP ERROR STEPS"]
    rows = [
        [
            r.name,
            _local(r.last_run),
            _needs_run_cell(r),
            _volume_cell(r),
            format_paid(r.paid_in_window),
            str(r.error_total),
            ", ".join(f"{n} {c}" for n, c in r.top_error_steps) or "—",
        ]
        for r in reports
    ]
    out = [_table(headers, rows)]
    for r in reports:
        if r.commands:
            out += ["", f"{r.name}:", *_command_lines(r)]
    notes = [f"{r.name}: {r.note}" for r in reports if r.note]
    if notes:
        out += ["", *notes]
    return "\n".join(out)


def render_drilldown(r: PipelineReport) -> str:
    rows = [
        [s.name, _local(s.completed_at), "—" if s.record_count is None else f"{s.record_count:,}",
         s.state, str(s.errors), ", ".join(s.paid) or "—"]
        for s in r.steps
    ]
    out = [f"{r.name} — {r.status}", "", _table(["STEP", "COMPLETED", "RECORDS", "STATE", "ERRORS", "PAID"], rows), ""]
    out.append(f"run start: {r.run_start or '—'}")
    out.append(f"window: {', '.join(r.window) or '—'}")
    out.append(f"volume: {_volume_cell(r)}")
    out.append(f"paid: {format_paid(r.paid_in_window)}")
    if r.commands:
        out += ["commands:", *_command_lines(r)]
    if r.note:
        out.append(f"note: {r.note}")
    if r.has_status_script:
        out.append(f"per-item view: uv run python pipelines/{r.dir_name}/status.py --help")
    return "\n".join(out)


def report_to_json(r: PipelineReport) -> dict:
    return {
        "name": r.name,
        "dir": r.dir_name,
        "status": r.status,
        "last_run": r.last_run,
        "run_start": r.run_start,
        "code_changed_from": r.code_changed_from,
        "blocked_by": r.blocked_by,
        "window": r.window,
        "volume": r.volume,
        "paid_in_window": r.paid_in_window,
        "error_total": r.error_total,
        "top_error_steps": [[n, c] for n, c in r.top_error_steps],
        "suggested_commands": [{"command": c.command, "paid_steps": c.paid_steps} for c in r.commands],
        "note": r.note,
        "steps": [
            {"name": s.name, "state": s.state, "completed_at": s.completed_at,
             "record_count": s.record_count, "errors": s.errors, "paid": s.paid}
            for s in r.steps
        ],
    }


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(description="Read-only status overview for every pipeline.")
    parser.add_argument("--pipeline", help="show one pipeline in detail (e.g. minutes)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    try:
        dirs = discover_pipelines(repo_root)
        if args.pipeline:
            wanted = args.pipeline.removesuffix("_pipeline") + "_pipeline"
            dirs = [d for d in dirs if d.name == wanted]
            if not dirs:
                print(f"error: unknown pipeline '{args.pipeline}'", file=sys.stderr)
                return 2
        reports = [build_report(repo_root, d) for d in dirs]
    except PipelineDataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not args.pipeline:
        reports = sort_reports(reports)
    if args.json:
        print(json.dumps([report_to_json(r) for r in reports], indent=2))
    elif args.pipeline:
        print(render_drilldown(reports[0]))
    else:
        print(render_overview(reports))
    return 0


if __name__ == "__main__":
    sys.exit(main())

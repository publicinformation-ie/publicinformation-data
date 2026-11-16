"""Read-only status overview for every pipeline.

Usage: uv run python scripts/pipeline_status.py [--pipeline NAME] [--json]

Never imports or runs a step. Only stats output.json; reads pipeline.json,
pipeline-status.json and errors.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
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

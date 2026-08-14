#!/usr/bin/env python3
"""Generate pipeline summaries embedded in repository agent documentation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BEGIN = "<!-- BEGIN GENERATED: pipeline-overviews -->"
END = "<!-- END GENERATED: pipeline-overviews -->"


def load_pipelines(repo_root: Path) -> list[tuple[str, dict]]:
    pipelines = []
    for config_path in sorted((repo_root / "pipelines").glob("*/pipeline.json")):
        pipelines.append((config_path.parent.name, json.loads(config_path.read_text())))
    return pipelines


def render(pipelines: list[tuple[str, dict]]) -> str:
    sections = []
    for name, config in pipelines:
        steps = config.get("steps", [])
        always_run = config.get("always_run", [])
        lines = [f"### `{name}` ({len(steps)} steps)", "", "| # | Step |", "|---:|---|"]
        lines.extend(f"| {index} | `{step}` |" for index, step in enumerate(steps, 1))
        if always_run:
            lines.extend(["", f"Always-run steps: {', '.join(f'`{step}`' for step in always_run)}."])
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def update_text(text: str, generated: str) -> str:
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END, start)
    return text[:start] + "\n\n" + generated.rstrip() + "\n\n" + text[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated documentation is stale")
    parser.add_argument("--file", default="AGENTS.md", help="Documentation file to update")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    documentation_path = repo_root / args.file
    current = documentation_path.read_text()
    expected = update_text(current, render(load_pipelines(repo_root)))

    if args.check:
        if current != expected:
            print(f"Generated pipeline documentation is stale: {documentation_path}")
            return 1
        return 0

    documentation_path.write_text(expected)
    print(f"Updated {documentation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

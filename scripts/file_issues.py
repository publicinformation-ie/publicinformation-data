#!/usr/bin/env python3
"""Triage view of all FOI disclosure files grouped by issue type."""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from src.lib.pipeline_steps import (
    STEP_NAMES,
    STEP_CONFIG,
    STEPS_DIR,
    get_step_path,
    load_json,
)


# ---------------------------------------------------------------------------
# Pure helpers (testable without filesystem)
# ---------------------------------------------------------------------------

def build_body_lookup(find_files_results: list) -> dict:
    """Map file_url -> public_body_name from find_disclosure_files results."""
    return {r["file_url"]: r["name"] for r in find_files_results if r.get("file_url")}


def extract_urls(output_data: dict | None) -> set:
    """Return the set of file_urls present in a step output dict."""
    if output_data is None:
        return set()
    return {r.get("file_url") for r in output_data.get("results", []) if r.get("file_url")}


def group_errors(errors: list, body_lookup: dict) -> dict:
    """
    Accumulate error counts by issue_type -> body_name -> file_url.

    Returns: {issue_type: {body_name: {file_url: count}}}
    errors: flat list of {error_type, context: {file_url, ...}}
    """
    result = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for err in errors:
        error_type = err.get("error_type")
        file_url = (err.get("context") or {}).get("file_url")
        if not error_type or not file_url:
            continue
        body = body_lookup.get(file_url, "(unknown)")
        result[error_type][body][file_url] += 1
    return result


def detect_dropped(prev_urls: set, next_urls: set) -> set:
    """Return URLs present in prev_urls but absent in next_urls."""
    return prev_urls - next_urls


def collect_all_issues(
    body_lookup: dict,
    step_names: list,
    step_config: dict,
    load_output_fn,
    load_errors_fn,
) -> dict:
    """
    Walk all pipeline steps and build the unified issue map.

    load_output_fn(step_name) -> dict | None
    load_errors_fn(step_name) -> list | None

    Returns: {issue_type: {body_name: {file_url: count}}}
    """
    issue_map = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    # Load all step outputs upfront for dropped-file detection
    outputs = {name: load_output_fn(name) for name in step_names}

    for step_name in step_names:
        _, has_errors, _ = step_config.get(step_name, ("results", False, False))

        # Accumulate errors
        if has_errors:
            errors = load_errors_fn(step_name)
            if errors:
                grouped = group_errors(errors, body_lookup)
                for issue_type, bodies in grouped.items():
                    for body, urls in bodies.items():
                        for url, count in urls.items():
                            issue_map[issue_type][body][url] += count

    # Detect dropped files between consecutive steps
    for i in range(len(step_names) - 1):
        step_n  = step_names[i]
        step_n1 = step_names[i + 1]
        out_n  = outputs[step_n]
        out_n1 = outputs[step_n1]
        if out_n is None or out_n1 is None:
            continue
        dropped = detect_dropped(extract_urls(out_n), extract_urls(out_n1))
        if dropped:
            issue_type = f"DroppedAt_{step_n1}"
            for url in dropped:
                body = body_lookup.get(url, "(unknown)")
                issue_map[issue_type][body][url] += 1

    return dict(issue_map)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _total_errors(bodies: dict) -> int:
    return sum(sum(urls.values()) for urls in bodies.values())


def _total_files(bodies: dict) -> int:
    return sum(len(urls) for urls in bodies.values())


def format_issues(
    issue_map: dict,
    filter_step: str | None = None,
    filter_issue: str | None = None,
    min_errors: int = 1,
) -> str:
    lines = []

    # Apply --issue filter
    if filter_issue:
        issue_map = {k: v for k, v in issue_map.items() if k == filter_issue}

    # Apply --step filter (step errors are named by step; DroppedAt_ issues include step name)
    if filter_step:
        # Keep only issues whose name contains the step name
        issue_map = {k: v for k, v in issue_map.items() if filter_step in k}

    # Sort issues by total file count descending
    sorted_issues = sorted(
        issue_map.items(),
        key=lambda kv: _total_files(kv[1]),
        reverse=True,
    )

    for issue_type, bodies in sorted_issues:
        total_err = _total_errors(bodies)
        total_files = _total_files(bodies)
        is_dropped = issue_type.startswith("DroppedAt_")

        if is_dropped:
            header = f"ISSUE: {issue_type}  ({total_files} files)"
        else:
            header = f"ISSUE: {issue_type}  ({total_err} errors across {total_files} files)"
        lines.append(header)

        for body in sorted(bodies.keys()):
            urls = bodies[body]
            # Sort by count descending, then url for stable output
            sorted_urls = sorted(urls.items(), key=lambda x: (-x[1], x[0]))
            # Apply --min-errors filter
            visible = [(url, cnt) for url, cnt in sorted_urls if cnt >= min_errors]
            if not visible:
                continue
            lines.append(f"  {body}")
            for url, count in visible:
                lines.append(f"    {count:5d}  {url}")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_issues(step_names, step_config, body_lookup) -> dict:
    def load_output(step_name):
        return load_json(get_step_path(step_name, "output"))

    def load_errors(step_name):
        return load_json(get_step_path(step_name, "errors"))

    return collect_all_issues(
        body_lookup=body_lookup,
        step_names=step_names,
        step_config=step_config,
        load_output_fn=load_output,
        load_errors_fn=load_errors,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Triage view of FOI disclosure files grouped by issue type"
    )
    parser.add_argument("--step",       metavar="STEP_NAME", help="Limit to one pipeline step")
    parser.add_argument("--issue",      metavar="ISSUE_TYPE", help="Limit to one issue type")
    parser.add_argument("--min-errors", metavar="N", type=int, default=1,
                        help="Hide file entries below this error count (default: 1)")
    return parser.parse_args()


def main():
    args = parse_args()

    find_files_output = STEPS_DIR / "find_disclosure_files" / "output.json"
    find_data = load_json(find_files_output)
    if find_data is None:
        print(
            f"Error: {find_files_output} is missing — cannot resolve public body names",
            file=sys.stderr,
        )
        sys.exit(1)

    body_lookup = build_body_lookup(find_data.get("results", []))
    issue_map = load_all_issues(STEP_NAMES, STEP_CONFIG, body_lookup)

    output = format_issues(
        issue_map,
        filter_step=args.step,
        filter_issue=args.issue,
        min_errors=args.min_errors,
    )
    print(output)


if __name__ == "__main__":
    main()

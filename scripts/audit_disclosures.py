#!/usr/bin/env python3
"""Diagnostic script: rank FOI disclosure source files by data-quality error count."""

import argparse
import sys
from dataclasses import dataclass

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))
from lib.db_client import DbClient


@dataclass
class Check:
    name: str
    description: str
    where_clause: str


CHECKS: list[Check] = [
    Check(
        name="blank_request_description",
        description="blank_request_description",
        where_clause="request_description IS NULL OR request_description = ''",
    ),
    Check(
        name="invalid_decision_date",
        description="invalid_decision_date",
        where_clause="decision_date IS NOT NULL AND date(decision_date) IS NULL",
    ),
    Check(
        name="invalid_date_received",
        description="invalid_date_received",
        where_clause="date_received IS NOT NULL AND date(date_received) IS NULL",
    ),
    Check(
        name="decision_status_is_date",
        description="decision_status_is_date",
        where_clause="decision_status IS NOT NULL AND date(decision_status) IS NOT NULL",
    ),
]


def get_check(name: str) -> "Check | None":
    for c in CHECKS:
        if c.name == name:
            return c
    return None


def run_checks(db: DbClient, checks: list[Check]) -> dict[str, dict[str, int]]:
    """Run each check query; return {file_url: {check_name: count}}."""
    results: dict[str, dict[str, int]] = {}
    for check in checks:
        sql = (
            f"SELECT file_url, COUNT(*) AS n "
            f"FROM foi_disclosures "
            f"WHERE {check.where_clause} "
            f"GROUP BY file_url"
        )
        rows = db.execute(sql)
        for row in rows:
            url = row["file_url"]
            if url not in results:
                results[url] = {}
            results[url][check.name] = row["n"]
    return results


def aggregate(
    raw: dict[str, dict[str, int]], min_errors: int = 1
) -> list[tuple[str, int, dict[str, int]]]:
    """Sum per-check counts; return list of (file_url, total, per_check) sorted desc."""
    rows = []
    for url, per_check in raw.items():
        total = sum(per_check.values())
        if total >= min_errors:
            rows.append((url, total, per_check))
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def format_report(
    checks: list[Check],
    raw: dict[str, dict[str, int]],
    ranked: list[tuple[str, int, dict[str, int]]],
    top: int,
    run_date: str,
) -> str:
    n = len(checks)
    separator = "=" * 54
    lines = [
        f"FOI Disclosures Quality Report — {n} checks, {run_date}",
        separator,
        "",
    ]

    if not ranked:
        lines.append("No issues found.")
        return "\n".join(lines)

    lines.append("CHECK SUMMARY")
    for check in checks:
        total_rows = sum(
            per_check.get(check.name, 0) for per_check in raw.values()
        )
        n_files = sum(1 for per_check in raw.values() if check.name in per_check)
        lines.append(f"  {check.name:<30} {total_rows:>4} rows in {n_files:>2} files")

    lines.append("")
    lines.append(f"TOP {top} FILES BY ERROR COUNT")
    for rank, (url, total, per_check) in enumerate(ranked[:top], start=1):
        lines.append(f"  {rank}. {url}  ({total} errors)")
        for check_name, count in sorted(per_check.items(), key=lambda x: -x[1]):
            lines.append(f"       {check_name}: {count}")
        lines.append("")

    return "\n".join(lines)

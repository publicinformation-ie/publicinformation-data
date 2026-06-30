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
    # dd/mm/yyyy dates in decision_status — not caught by date() which only parses ISO format.
    # 1,135 rows across 37 files identified 2026-06-24. Typically a column-shift artefact.
    Check(
        name="decision_status_is_slashdate",
        description="decision_status contains dd/mm/yyyy date (column-shift artefact)",
        where_clause="decision_status IS NOT NULL AND decision_status GLOB '[0-9][0-9]/[0-9][0-9]/[0-9][0-9]*'",
    ),
    # decision_status holds a value that isn't one of the ~8 canonical outcomes and isn't a date.
    # Catches wrong-column contamination (requester_type values), junk, OCR garbles.
    Check(
        name="decision_status_nonstandard",
        description="decision_status is not a recognised outcome value",
        where_clause="""decision_status IS NOT NULL
            AND decision_status != ''
            AND date(decision_status) IS NULL
            AND decision_status NOT GLOB '[0-9][0-9]/[0-9][0-9]/[0-9][0-9]*'
            AND TRIM(decision_status) NOT IN (
                'Part-Granted','Refused','Granted','Withdrawn',
                'Handled outside of FOI','Transferred','Unknown','Deemed Refused'
            )""",
    ),
    # requester_type has 783 distinct values (2026-06-24 audit); should be ~8-10 canonical ones.
    # Flags case variants, abbreviations, abbreviations, split PDF tokens, column-header leakage.
    # See docs/analysis/2026-06-24-foi-disclosures-enum-cleanup.md for the full canonical mapping.
    Check(
        name="requester_type_nonstandard",
        description="requester_type is not a recognised canonical value",
        where_clause="""requester_type IS NOT NULL
            AND requester_type != ''
            AND TRIM(LOWER(requester_type)) NOT IN (
                'journalist','journalists','media','press','reporter',
                'other','others',
                'client','clients',
                'member of the public','member of public','mop',
                'non personal','non-personal','non pers','non- personal',
                'business/interest group','business/interest groups',
                'business interest group','business interest',
                'oireachtas',
                'oireachtas/public representatives','oireachtas/public representative',
                'oireachtas / public representative','oireachtas / public reps',
                'oireachtas/ public reps','oireactas / public reps',
                'oireachtas member/ councillor','oireachtas member/councillor',
                'oireachtas/elected representative','oireachtas member',
                'member of oireachtas','member of the oireachtas',
                'member of the oireachtas/elected representative',
                'individual',
                'personal',
                'staff',
                'public',
                'public representative',
                'councillor',
                'solicitor','solicitors',
                'solicitor on behalf of member of the public',
                'association','organisation','company','industry',
                'general','commercial','customer',
                'student/lecturer','residents association',
                'non-personal (business/interest group)',
                'individual (non-personal)','individual (non- personal)',
                'individual (personal)',
                'member of business/interest group','member of business/interest groups',
                'business / interest group','business/ interest group',
                'business/interest','business / interest groups',
                'oireachtas/public reps','oireachtas / public representatives',
                'member of local authority','member of the oireachtas/elected representative',
                'public service','n/a'
            )""",
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


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit foi_disclosures for data-quality errors, ranked by source file."
    )
    parser.add_argument("--top", type=int, default=20, help="Limit file ranking to top N files")
    parser.add_argument("--check", default=None, help="Run only the named check")
    parser.add_argument("--min-errors", type=int, default=1, dest="min_errors",
                        help="Exclude files with fewer than N total errors")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    import datetime
    import os
    from pathlib import Path

    args = parse_args(argv)

    if args.check is not None:
        if get_check(args.check) is None:
            names = ", ".join(c.name for c in CHECKS)
            print(f"Error: unknown check '{args.check}'. Available: {names}", file=sys.stderr)
            return 1
        checks = [get_check(args.check)]
    else:
        checks = CHECKS

    db_url = os.getenv("DATABASE_URL", "local.db")
    if not db_url.startswith("http") and not db_url.startswith("libsql://"):
        path = db_url.removeprefix("file:") if db_url.startswith("file:") else db_url
        if not Path(path).exists():
            print(f"Error: database not found: {path}", file=sys.stderr)
            return 1

    db = DbClient()
    try:
        raw = run_checks(db, checks)
        ranked = aggregate(raw, min_errors=args.min_errors)
        run_date = datetime.date.today().isoformat()
        report = format_report(checks, raw, ranked, top=args.top, run_date=run_date)
        print(report)
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

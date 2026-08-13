"""Loader for input_plans.md — the hand-authored list of current/future
government plans and strategies, one markdown table per department.

Like documents.py, a malformed entry here is process-fatal: a bad parse
could silently drop or mis-slug plans downstream, so this fails the whole
run rather than continuing with partial data.
"""
import re
from pathlib import Path

PLANS_PATH = Path(__file__).parent / "input_plans.md"

_DEPT_NUMBER_RE = re.compile(r"^\d+\.\s+(.+)$")
_TABLE_ROW_RE = re.compile(r"^\|(.*)\|$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def _split_cells(row_text: str) -> list:
    return [c.strip() for c in row_text.split("|")]


def _is_separator_row(cells: list) -> bool:
    return all(_SEPARATOR_CELL_RE.match(c) for c in cells)


def _strip_markdown_bold(text: str) -> str:
    return text.replace("**", "").strip()


def load_plans(path=PLANS_PATH) -> list:
    """Parse and validate input_plans.md. Raises ValueError on malformed
    structure (missing/malformed heading, table row before any heading, a
    heading with no table, or a table row not matching the expected
    4-column shape)."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    records = []
    department = None
    header_seen = False
    saw_any_table_row = False

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        where = f"{path}:{lineno}"

        if line.startswith("## "):
            if department is not None and not saw_any_table_row:
                raise ValueError(
                    f"{where}: department {department!r} heading has no table before "
                    f"the next heading")
            heading_text = line[3:].strip()
            m = _DEPT_NUMBER_RE.match(heading_text)
            if not m:
                raise ValueError(
                    f"{where}: malformed department heading {line!r}; must match "
                    f"'## N. <Department Name>'")
            department = m.group(1).strip()
            header_seen = False
            saw_any_table_row = False
            continue

        if not line.startswith("|"):
            continue

        m = _TABLE_ROW_RE.match(line)
        if not m:
            raise ValueError(f"{where}: malformed table row {line!r}")
        cells = _split_cells(m.group(1))
        if len(cells) != 4:
            raise ValueError(
                f"{where}: table row has {len(cells)} cell(s), expected 4 cells: {line!r}")

        if department is None:
            raise ValueError(f"{where}: table row appears before any department heading")

        saw_any_table_row = True

        if not header_seen:
            header_seen = True
            continue  # column-header row: "Plan / Strategy Title | Time Horizon | ..."

        if _is_separator_row(cells):
            continue  # "| --- | --- | --- | --- |"

        title, time_horizon, focus, status = (_strip_markdown_bold(c) for c in cells)
        records.append({
            "department": department,
            "title": title,
            "time_horizon": time_horizon,
            "focus": focus,
            "status": status,
        })

    if department is not None and not saw_any_table_row:
        raise ValueError(
            f"{path}: department {department!r} heading has no table before end of file")

    return records

"""Generate the full activity × stage row register from the master.

The register is never stored: it is derived from ``activity_stages.csv``. A row
is ``assessed`` when at least one assignment exists for its activity × stage,
and ``not assessed`` otherwise. The two states never collapse: a row with no
assignment is not the same as an assessed line on which no council organ holds
a role.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import Master

ASSESSED = "assessed"
NOT_ASSESSED = "not assessed"


@dataclass(frozen=True)
class Row:
    row_id: str
    activity_id: str
    stage_id: str
    coverage: str
    assessed_lines: int


def generate_rows(master: Master) -> list[Row]:
    """Return every row in master order, with its coverage state."""
    retired = {
        activity.activity_id for activity in master.activities
        if activity.status != "active"
    }
    line_counts: dict[tuple[str, str], int] = {}
    for assignment in master.assignments:
        key = (assignment.activity_id, assignment.stage_id)
        line_counts[key] = line_counts.get(key, 0) + 1

    rows: list[Row] = []
    for link in master.activity_stages:
        if link.activity_id in retired:
            continue
        line_count = line_counts.get((link.activity_id, link.stage_id), 0)
        rows.append(Row(
            row_id=f"{link.activity_id}.{link.stage_id}",
            activity_id=link.activity_id,
            stage_id=link.stage_id,
            coverage=ASSESSED if line_count else NOT_ASSESSED,
            assessed_lines=line_count,
        ))
    return rows

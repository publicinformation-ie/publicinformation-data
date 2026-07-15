"""Canonical disclosure schema + row renderer for the llm-repair experiment.

The six fields mirror the canonicalization targets in
steps/extract_disclosures_canonicalize/column_mappings.json. entries_to_rows
renders arm B's named entries back into a header+grid so the SAME structural
eval predicates (has_newline_split_row / has_null_column / has_null_first_row)
that scored arm A can be applied to arm B unchanged.
"""
from pydantic import BaseModel

CANONICAL_FIELDS = [
    "foi_reference_id",
    "date_received",
    "request_description",
    "requester_type",
    "decision_status",
    "decision_date",
]


class DisclosureEntry(BaseModel):
    foi_reference_id: str | None = None
    date_received: str | None = None
    request_description: str | None = None
    requester_type: str | None = None
    decision_status: str | None = None
    decision_date: str | None = None


class DisclosureLog(BaseModel):
    entries: list[DisclosureEntry]


def entries_to_rows(entries: list[dict]) -> list[list]:
    """Render entry dicts into a header+value grid (None preserved)."""
    if not entries:
        return []
    rows: list[list] = [list(CANONICAL_FIELDS)]
    for entry in entries:
        rows.append([entry.get(field) for field in CANONICAL_FIELDS])
    return rows

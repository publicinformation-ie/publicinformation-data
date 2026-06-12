"""Shared table processing utilities for the FOI pipeline."""
from lib.text_utils import normalize_cell


def detect_header_row(rows, max_look_ahead=5):
    """Return index of the first row with 2+ non-null, non-empty cells.

    Normalizes cells (especially PDF cells with newlines) before counting.
    """
    for idx, row in enumerate(rows[:max_look_ahead]):
        normalized_row = [
            normalize_cell(v) if v else v
            for v in row
        ]
        non_empty = [v for v in normalized_row if v is not None and v != ""]
        if len(non_empty) >= 2:
            return idx
    return 0

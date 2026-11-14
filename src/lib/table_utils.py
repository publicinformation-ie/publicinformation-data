"""Shared table processing utilities for the FOI pipeline."""
from lib.text_utils import normalize_cell

_CONTINUATION_NULL_THRESHOLD = 0.5  # row is a continuation if > 50% of cells are None
_MAX_CONTINUATION_ROWS = 6
_MAX_PROSE_CELL_LEN = 50  # sparse rows with any non-null cell longer than this are preamble, not header fragments


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


def _count_canonical_columns(row) -> int:
    """Count how many distinct canonical columns a row maps to."""
    from lib.column_map import canonicalize_header
    seen = set()
    for cell in (row or []):
        if cell is not None:
            c = canonicalize_header(str(cell))
            if c:
                seen.add(c)
    return len(seen)


def normalize_header_row(rows, header_row_idx, max_continuation_rows=_MAX_CONTINUATION_ROWS):
    """Repair null cells in the detected header row.

    Three repairs are applied in order:
    1. Pre-header strip: rows before header_row_idx are dropped (document title rows
       with ≤1 non-null cell), and header_row_idx is reset to 0.
    2. Continuation-row merge: high-null rows immediately after the header are
       merged into it (column values joined with a space), then removed from rows.
    3. Forward-fill: remaining None cells in the header are replaced with the
       nearest preceding non-None value (repairing PDF merged-cell spans).

    Returns (new_rows, header_row_idx) — header_row_idx is 0 after repair.
    """
    if not rows or header_row_idx >= len(rows):
        return rows, header_row_idx

    header = list(rows[header_row_idx])
    ncols = len(header)

    # Step 1: detect and merge continuation rows
    continuation_end = header_row_idx + 1
    for i in range(header_row_idx + 1,
                   min(header_row_idx + 1 + max_continuation_rows, len(rows))):
        row = rows[i]
        if not row:  # empty list is falsy; not a continuation row, leave it in place
            break
        non_null = sum(1 for c in row if c is not None)
        null_fraction = 1 - (non_null / len(row))
        if null_fraction < _CONTINUATION_NULL_THRESHOLD:
            already_merging = continuation_end > header_row_idx + 1
            if not already_merging or _count_canonical_columns(row) < 1:
                break  # too many populated cells and not a header fragment — this is real data
            # else: dense row mid-sequence with ≥1 canonical hit — looks like a header fragment, keep merging
        # Drop sparse rows whose non-null content looks like prose (preamble text),
        # not a column header fragment. Header fragments are short phrases; prose sentences
        # are long. Dropping keeps the row out of both the header and the data output.
        if null_fraction >= _CONTINUATION_NULL_THRESHOLD:
            non_null_vals = [str(c) for c in row if c is not None]
            if any(len(v) > _MAX_PROSE_CELL_LEN for v in non_null_vals):
                continuation_end = i + 1  # consume the row (don't emit it as data)
                continue
        for col_idx, cell in enumerate(row):
            if cell is not None and col_idx < ncols:
                if header[col_idx] is not None:
                    header[col_idx] = header[col_idx] + " " + str(cell)
                else:
                    header[col_idx] = str(cell)
        continuation_end = i + 1

    # Step 2: forward-fill None cells left-to-right
    last_val = None
    for i, cell in enumerate(header):
        if cell is not None:
            last_val = cell
        elif last_val is not None:
            header[i] = last_val

    # Step 3: targeted fill — if Nones remain after forward-fill, check whether the
    # first non-merged row is actually a missed second header line. We detect this by
    # counting how many of its cells canonicalize as known header labels; ≥2 distinct
    # canonical hits strongly indicates a split header rather than a data row. When
    # triggered, only None positions in the header are filled (non-None positions are
    # never overwritten), and the candidate row is consumed (removed from data).
    none_positions = [i for i, c in enumerate(header) if c is None]
    if none_positions and continuation_end < len(rows):
        candidate = rows[continuation_end]
        if _count_canonical_columns(candidate) >= 2:
            for pos in none_positions:
                if pos < len(candidate) and candidate[pos] is not None:
                    header[pos] = str(candidate[pos])
            continuation_end += 1

    # Strip pre-header title rows; header is always rows[0] after this point.
    new_rows = [header] + list(rows[continuation_end:])

    # Scan-ahead rescue: if forward-fill produced a degenerate header (too few distinct
    # canonical columns), check if the immediately following row maps >= 3 canonical columns
    # and promote it instead.
    canonical_unique = _count_canonical_columns(new_rows[0])
    if canonical_unique < 2:
        if len(new_rows) > 1 and _count_canonical_columns(new_rows[1]) >= 3:
            return new_rows, 1

    return new_rows, 0

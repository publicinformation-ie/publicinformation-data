"""Continuation-row detection shared by filter_phantom_rows and the structure scorer."""

# Ratio of multi-value data rows below which a file is treated as having a
# "sparse layout" (its shape, not fragmentation) rather than leaked splits.
# See the guard in is_sparse_layout for the derivation. Shared with
# eval/evaluate.py (via filter_phantom_rows) so the eval's leak detection
# matches the step's own guard.
MULTI_ROW_TOLERANCE = 0.1


def _is_blank_cell(cell) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip())


def is_continuation_row(row: list) -> bool:
    """True if the row has >= 3 columns and exactly one non-blank cell.

    Blank means None *or* an empty/whitespace string: pdfplumber uses both
    sentinels interchangeably, often within one file.
    """
    return len(row) >= 3 and sum(1 for c in row if not _is_blank_cell(c)) == 1


def is_sparse_layout(data_rows: list[list]) -> bool:
    """Sparse-layout guard: True when single-value rows are the file's shape.

    If >50% of data rows are single-value rows AND multi-value rows are rare
    (not just "none"), this is the file's shape (not fragmentation). Merging
    would collapse distinct records. Files with continuation rows will have a
    substantial fraction of rows with 2+ non-None cells.
    """
    if not data_rows:
        return False
    single = sum(
        1 for r in data_rows
        if len(r) >= 3 and sum(1 for c in r if c is not None) == 1
    )
    multi = sum(
        1 for r in data_rows
        if len(r) >= 3 and sum(1 for c in r if c is not None) >= 2
    )
    # Ratio-based (not exact-zero) multi-row check: an exact `multi == 0` guard is
    # too brittle — a single incidental multi-value row in an otherwise sparse file
    # (e.g. 19 single-value rows + 1 multi-value row) would fully disable the guard
    # and chain-collapse the whole file. Constraining ratios from the test suite:
    #   test_merge_continuation_rows_consecutive:            multi/len = 1/3  = 0.333 (guard must NOT fire)
    #   test_merge_continuation_rows_does_not_corrupt_header: multi/len = 1/4  = 0.25  (guard must NOT fire)
    #   test_merge_skips_sparse_layout_files:                 multi/len = 0/4  = 0.0   (guard must fire)
    #   test_merge_skips_sparse_layout_with_one_incidental_multi_row: multi/len = 1/20 = 0.05 (guard must fire)
    # A threshold of 0.1 satisfies 0.05 < 0.1 <= 0.25, keeping all four cases correct.
    #
    # NOTE: this guard deliberately counts `is not None` while the merge loop below
    # is blank-aware. The 0.1 threshold was calibrated against None-only ratios;
    # switching the guard to _is_blank_cell shifts every ratio and re-fires the
    # guard on files that do need merging (measured: +9 files fully skipped,
    # orphan fragments 5,006 -> 7,088 across the PDF corpus). Retuning the
    # threshold is a separate, evidence-backed change — do not "tidy" this to
    # match the loop without re-deriving the constant.
    return single / len(data_rows) > 0.5 and multi / len(data_rows) < MULTI_ROW_TOLERANCE


def merge_continuation_rows(rows: list[list]) -> tuple[list[list], int]:
    """Merge continuation rows into the preceding row; rows[0] is the header.

    Single source of truth for which rows get folded: used by filter_phantom_rows
    and by the structure scorer. A continuation row is left in place when it
    directly follows the header, holds a non-string value, or its target cell in
    the previous row is a non-blank non-string. Returns (rows, n_merged).
    """
    if not rows or max(len(r) for r in rows) < 3:
        return rows, 0
    if is_sparse_layout(rows[1:]):
        return rows, 0  # sparse layout is this file's shape, not fragmentation

    merged = 0
    out = [list(rows[0])]
    for row in rows[1:]:
        # Blank-aware: pdfplumber emits a mix of None and '' for empty cells within
        # the same file, so a None-only count reads a continuation row as multi-value
        # and lets it survive as an orphan fragment.
        if is_continuation_row(row):
            col_idx, val = next((i, v) for i, v in enumerate(row) if not _is_blank_cell(v))
            prev = out[-1]
            if len(out) > 1 and col_idx < len(prev) and isinstance(val, str):
                if isinstance(prev[col_idx], str) and prev[col_idx].strip():
                    prev[col_idx] = prev[col_idx] + " " + val
                    merged += 1
                    continue
                if _is_blank_cell(prev[col_idx]):
                    prev[col_idx] = val
                    merged += 1
                    continue
        out.append(list(row))
    return out, merged

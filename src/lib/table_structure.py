"""Label-free structural quality scorer for extracted FOI tables.

Scores a ``rows`` grid (list of lists of cells) on structural signals that need
no ground-truth labels: row-width uniformity, fragment rows, column type
purity and words split across a column boundary. These are the *structural*
checks, and only they gate (``failed_checks``).

Two signals are recorded but never gate:

* ``run_together_rate``: run-together tokens inside a cell (``informaQon``,
  ``andThe``). That is a defect in cell text, not in the table; cell repair
  belongs in ``normalize_disclosure_cells``.
* ``repeated_header_share``: rows equal to the header (header repeated on each
  page). These rows are removed before scoring, as ``canonicalize`` does anyway.

Both still feed ``composite`` so candidate selection prefers cleaner text.
Threshold values in ``DEFAULT_THRESHOLDS`` were calibrated on a 10-file gold
set (small N); see experiments/2026-11-14-pdf-extractor-bakeoff/results/bakeoff.md.
"""
import re
from collections import Counter
from dataclasses import dataclass

from lib.continuation_rows import merge_continuation_rows
from lib.column_map import canonicalize_headers
from lib.date_parse import parse_date
from lib.table_utils import detect_header_row

_RUN_TOGETHER_RE = re.compile(r"[a-z]{2,}[A-Z][a-z]")
# CamelCase brand names (WhatsApp, EirGrid) are not run-together words.
_BRAND_RE = re.compile(r"^[A-Z][a-z]{2,}[A-Z][a-z]+$")
_REF_CHARS_RE = re.compile(r"[A-Za-z/\-]")
_MIN_TYPED_CELLS = 5


@dataclass(frozen=True)
class StructureScore:
    n_rows: int
    modal_width: int
    width_uniformity: float
    fragment_share: float
    column_type_purity: float
    cross_cell_split_rate: float  # structural: a word stub across a column boundary
    run_together_rate: float  # text: run-together tokens inside a cell (never gates)
    repeated_header_share: float  # recorded before removal (never gates)
    composite: float

    @property
    def split_word_rate(self) -> float:
        """Deprecated alias for ``cross_cell_split_rate`` (the gating signal)."""
        return self.cross_cell_split_rate

    @classmethod
    def from_dict(cls, d: dict) -> "StructureScore":
        """Rebuild from a stored score, including legacy ones that only have
        ``split_word_rate`` (a combined rate; read as the structural one)."""
        d = dict(d)
        legacy = d.pop("split_word_rate", None)
        if "cross_cell_split_rate" not in d and legacy is not None:
            d["cross_cell_split_rate"] = legacy
        d.setdefault("run_together_rate", 0.0)
        return cls(**d)


@dataclass(frozen=True)
class Thresholds:
    min_width_uniformity: float = 0.92
    max_fragment_share: float = 0.08
    min_column_type_purity: float = 0.85
    max_split_word_rate: float = 0.02
    # Kept so stored threshold reports still parse; no longer used by
    # failed_checks (repeated header rows are removed, not rejected).
    max_repeated_header_share: float = 0.07
    min_rows: int = 1


DEFAULT_THRESHOLDS = Thresholds()


_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _text(cell) -> str:
    return "" if cell is None else str(cell)


def _is_empty(cell) -> bool:
    return not _text(cell).strip()


def _trimmed(row: list) -> list:
    end = len(row)
    while end and _is_empty(row[end - 1]):
        end -= 1
    return list(row[:end])


def _norm(cell) -> str:
    return " ".join(_text(cell).lower().split())


def _cell_type(cell) -> str:
    text = " ".join(_text(cell).split())
    if not text:
        return "empty"
    if parse_date(text) is not None:
        return "date"
    if text.isdigit():
        return "number"
    if (len(text.split()) == 1 and any(c.isdigit() for c in text)
            and _REF_CHARS_RE.search(text)):
        return "reference"
    return "text"


def _non_empty(row: list) -> list[str]:
    return [" ".join(_text(c).split()) for c in row if not _is_empty(c)]


def _has_date_or_reference(row: list) -> bool:
    return any(_cell_type(c) in ("date", "reference") for c in row)


def _is_header_like(row: list) -> bool:
    cells = _non_empty(row)
    if not cells:
        return False
    mapped = canonicalize_headers(cells)
    if sum(1 for v in mapped.values() if v) * 2 > len(cells):
        return True
    plain = sum(1 for c in cells
                if _cell_type(c) == "text" and not any(ch.isdigit() for ch in c))
    return plain * 2 > len(cells)


def _is_year_divider(row: list) -> bool:
    """A row whose only non-empty cell is a bare year (a section divider)."""
    cells = _non_empty(row)
    return len(cells) == 1 and _YEAR_RE.fullmatch(cells[0]) is not None


def _data_rows(rows: list[list]) -> tuple[list, list[list], float]:
    """Return (header_row, data_rows, repeated_header_share).

    Blank rows, year dividers, extra header rows and rows repeating the header
    are dropped. The share is of the rows before the repeats were removed.
    """
    if not rows:
        return [], [], 0.0
    idx = detect_header_row(rows)
    header = rows[idx]
    body = [r for r in rows[idx + 1:]
            if any(not _is_empty(c) for c in r) and not _is_year_divider(r)]
    header_norm = [_norm(c) for c in _trimmed(header)]
    kept = [r for r in body if [_norm(c) for c in _trimmed(r)] != header_norm]
    repeated_share = (len(body) - len(kept)) / len(body) if body else 0.0
    body = kept
    start = 0
    while start < len(body):
        row = body[start]
        if _has_date_or_reference(row) or not _is_header_like(row):
            break
        start += 1
    return header, body[start:], repeated_share


def _is_run_together(tok: str) -> bool:
    if not _RUN_TOGETHER_RE.search(tok):
        return False
    core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", tok)
    core = re.sub(r"['\u2019]s$", "", core)
    return not _BRAND_RE.fullmatch(core)


# Words that may legitimately end or start a cell, so a 3-letter edge is not a stub.
_COMMON_SHORT = frozenset(
    "a an the of to for and or in on re by at is it as be no mr ms dr ltd na sec all any its".split()
)


def _is_stub_pair(left: str, right: str) -> bool:
    """A word broken by a column boundary: a stub on at least one side.

    Two adjacent complete values (``Journalist`` | ``all records``) are not.
    """
    if not (re.search(r"[A-Za-z]$", left) and re.match(r"[a-z]", right)):
        return False
    last_m = re.search(r"[A-Za-z]+$", left)
    first_m = re.match(r"[a-z]+", right)
    if last_m is None or first_m is None:
        return False
    last, first = last_m.group(0), first_m.group(0)
    return ((len(last) <= 3 and last.lower() not in _COMMON_SHORT)
            or (len(first) <= 3 and first not in _COMMON_SHORT))


def _count_run_together(rows: list[list]) -> tuple[int, int]:
    """Return (run-together tokens, non-empty cells). A text signal."""
    events = cells = 0
    for row in rows:
        for cell in row:
            t = _text(cell)
            if not t.strip():
                continue
            cells += 1
            events += sum(1 for tok in t.split() if _is_run_together(tok))
    return events, cells


def _count_cross_cell_splits(rows: list[list]) -> tuple[int, int]:
    """Return (stub pairs across adjacent cells, non-empty cells). Structural."""
    events = cells = 0
    for row in rows:
        texts = [_text(c) for c in row]
        for i, t in enumerate(texts):
            if not t.strip():
                continue
            cells += 1
            if i + 1 < len(texts) and texts[i + 1].strip() and _is_stub_pair(t, texts[i + 1]):
                events += 1
    return events, cells


def _column_type_purity(data: list[list]) -> float:
    columns: dict[int, list[str]] = {}
    for row in data:
        for i, cell in enumerate(row):
            t = _cell_type(cell)
            if t != "empty":
                columns.setdefault(i, []).append(t)
    shares = [
        Counter(types).most_common(1)[0][1] / len(types)
        for types in columns.values() if len(types) >= _MIN_TYPED_CELLS
    ]
    return sum(shares) / len(shares) if shares else 1.0


def _worst(n_rows: int, modal_width: int) -> StructureScore:
    return StructureScore(n_rows, modal_width, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0)


def score_table(rows: list[list]) -> StructureScore:
    # Score what survives filter_phantom_rows, in the same order: merge
    # continuation rows over the RAW rows first, only then drop blank rows,
    # year dividers and extra header rows. (Dropping blanks first would let a
    # continuation row fold into the real record across an all-blank separator
    # row that the filter would instead fill, hiding the surviving fragment.)
    # The filter treats rows[0] as the header; the scorer's header may sit lower
    # (title rows above it), so we merge from the detected header onward, which
    # is the same row sequence the filter sees once any title rows are absent.
    rows = rows[detect_header_row(rows):] if rows else rows
    header, data, repeated_header_share = _data_rows(
        merge_continuation_rows(rows)[0] if rows else rows)
    n_rows = len(data)
    if n_rows == 0:
        return _worst(0, 0)

    widths = [len(_trimmed(r)) for r in data]
    counts = Counter(widths)
    # The modal width is taken over rows with >= 3 non-empty cells so that a
    # run of continuation fragments cannot masquerade as the table's width.
    substantial = [w for w, r in zip(widths, data) if len(_non_empty(r)) >= 3]
    modal_counts = Counter(substantial) if substantial else counts
    modal_width = max(modal_counts, key=lambda w: (modal_counts[w], w))
    if modal_width < 2:
        return _worst(n_rows, modal_width)

    # Optional trailing columns: a row padded to full width whose trailing
    # cells are empty is still uniform if at most 2 are missing. Rows wider
    # than the table's usual padded width (stray extra columns) never are.
    raw_counts = Counter(len(r) for r in data)
    raw_mode = max(raw_counts, key=lambda w: (raw_counts[w], w))
    max_width = max(modal_width, raw_mode)
    uniform = sum(
        1 for w, r in zip(widths, data)
        if w == modal_width
        or (len(r) >= modal_width and modal_width - 2 <= w <= max_width
            and len(_non_empty(r)) >= 3)
    )
    width_uniformity = uniform / n_rows
    if modal_width >= 4:
        fragments = sum(1 for r in data if 1 <= len(_non_empty(r)) <= 2)
        fragment_share = fragments / n_rows
    else:
        fragment_share = 0.0

    splits, cells = _count_cross_cell_splits([header] + data)
    cross_cell_split_rate = splits / cells if cells else 1.0
    run_together, cells = _count_run_together([header] + data)
    run_together_rate = run_together / cells if cells else 1.0

    purity = _column_type_purity(data)
    composite = (width_uniformity * purity * (1 - fragment_share)
                 * (1 - min(1.0, 10 * (cross_cell_split_rate + run_together_rate)))
                 * (1 - repeated_header_share))
    return StructureScore(n_rows, modal_width, width_uniformity, fragment_share,
                          purity, cross_cell_split_rate, run_together_rate,
                          repeated_header_share, max(0.0, min(1.0, composite)))


def failed_checks(score: StructureScore,
                  thresholds: Thresholds = DEFAULT_THRESHOLDS) -> list[str]:
    failed = []
    if score.n_rows < max(1, thresholds.min_rows):
        failed.append("min_rows")
    if score.width_uniformity < thresholds.min_width_uniformity:
        failed.append("width_uniformity")
    if score.fragment_share > thresholds.max_fragment_share:
        failed.append("fragment_share")
    if score.column_type_purity < thresholds.min_column_type_purity:
        failed.append("column_type_purity")
    if score.cross_cell_split_rate > thresholds.max_split_word_rate:
        failed.append("split_word_rate")
    return failed


def passes(score: StructureScore,
           thresholds: Thresholds = DEFAULT_THRESHOLDS) -> bool:
    return not failed_checks(score, thresholds)

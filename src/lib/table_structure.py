"""Label-free structural quality scorer for extracted FOI tables.

Scores a ``rows`` grid (list of lists of cells) on structural signals that need
no ground-truth labels: row-width uniformity, fragment rows, column type
purity, split/run-together words and repeated header rows. Threshold values in
``DEFAULT_THRESHOLDS`` were calibrated on a 10-file gold set (small N);
see experiments/2026-11-14-pdf-extractor-bakeoff/results/bakeoff.md.
"""
import re
from collections import Counter
from dataclasses import dataclass

from lib.column_map import canonicalize_headers
from lib.date_parse import parse_date
from lib.table_utils import detect_header_row

_RUN_TOGETHER_RE = re.compile(r"[a-z]{2,}[A-Z][a-z]")
_REF_CHARS_RE = re.compile(r"[A-Za-z/\-]")
_MIN_TYPED_CELLS = 5


@dataclass(frozen=True)
class StructureScore:
    n_rows: int
    modal_width: int
    width_uniformity: float
    fragment_share: float
    column_type_purity: float
    split_word_rate: float
    repeated_header_share: float
    composite: float


@dataclass(frozen=True)
class Thresholds:
    min_width_uniformity: float = 0.85
    max_fragment_share: float = 0.10
    min_column_type_purity: float = 0.85
    max_split_word_rate: float = 0.02
    max_repeated_header_share: float = 0.07
    min_rows: int = 1


DEFAULT_THRESHOLDS = Thresholds()


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


def _data_rows(rows: list[list]) -> tuple[list, list[list]]:
    """Return (header_row, data_rows) with extra header rows and blanks dropped."""
    if not rows:
        return [], []
    idx = detect_header_row(rows)
    header = rows[idx]
    body = [r for r in rows[idx + 1:] if any(not _is_empty(c) for c in r)]
    start = 0
    while start < len(body):
        row = body[start]
        if _has_date_or_reference(row) or not _is_header_like(row):
            break
        start += 1
    return header, body[start:]


def _count_split_words(rows: list[list]) -> tuple[int, int]:
    """Return (split pairs + run-together tokens, non-empty cells)."""
    events = 0
    cells = 0
    for row in rows:
        texts = [_text(c) for c in row]
        for i, t in enumerate(texts):
            if not t.strip():
                continue
            cells += 1
            events += sum(1 for tok in t.split() if _RUN_TOGETHER_RE.search(tok))
            if i + 1 < len(texts):
                nxt = texts[i + 1]
                if (nxt.strip() and re.search(r"[A-Za-z]$", t)
                        and re.match(r"[a-z]", nxt)):
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
    return StructureScore(n_rows, modal_width, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0)


def score_table(rows: list[list]) -> StructureScore:
    header, data = _data_rows(rows)
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

    width_uniformity = counts[modal_width] / n_rows
    if modal_width >= 4:
        fragments = sum(1 for r in data if 1 <= len(_non_empty(r)) <= 2)
        fragment_share = fragments / n_rows
    else:
        fragment_share = 0.0

    header_norm = [_norm(c) for c in _trimmed(header)]
    repeated = sum(1 for r in data if [_norm(c) for c in _trimmed(r)] == header_norm)
    repeated_header_share = repeated / n_rows

    events, cells = _count_split_words([header] + data)
    split_word_rate = events / cells if cells else 1.0

    purity = _column_type_purity(data)
    composite = (width_uniformity * purity * (1 - fragment_share)
                 * (1 - min(1.0, 10 * split_word_rate))
                 * (1 - repeated_header_share))
    return StructureScore(n_rows, modal_width, width_uniformity, fragment_share,
                          purity, split_word_rate, repeated_header_share,
                          max(0.0, min(1.0, composite)))


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
    if score.split_word_rate > thresholds.max_split_word_rate:
        failed.append("split_word_rate")
    if score.repeated_header_share > thresholds.max_repeated_header_share:
        failed.append("repeated_header_share")
    return failed


def passes(score: StructureScore,
           thresholds: Thresholds = DEFAULT_THRESHOLDS) -> bool:
    return not failed_checks(score, thresholds)

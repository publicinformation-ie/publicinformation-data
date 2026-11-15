"""Value-kind classifier: what kind of value is a cell, regardless of column.

Used to check that a cell chosen for a role (reference, date, status, ...) is
not positively something else (e.g. a requester type in the reference column).
Unknown values are never foreign.
"""
import re
from typing import Literal, Optional

Kind = Literal["date", "reference", "status", "requester", "header"]

ROLE_KIND: dict[str, Kind] = {
    "foi_reference_id": "reference",
    "date_received": "date",
    "decision_date": "date",
    "decision_status": "status",
    "requester_type": "requester",
}

_FOREIGN_ORDER: tuple[Kind, ...] = ("date", "status", "requester", "reference", "header")
_REF_CHARS_RE = re.compile(r"[A-Za-z/\-]")
_PREFIXED_REF_RE = re.compile(r"^[A-Za-z]{2,6}[ /-]?\d+([ /-]+\d+)*$")
_NUMERIC_DATE_RE = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$")
# Mirrors _DATE_PATTERNS[1] in pipelines/foi_pipeline/steps/
# extract_disclosures_normalize_rows/process.py (src/lib cannot import from
# pipelines/). A parity test keeps the two in sync.
_D_MON_YY_RE = re.compile(
    r'^(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-\s]+(\d{2,4})$',
    re.IGNORECASE,
)
_DIGITS_RE = re.compile(r"^\d+\.?$")
_PUNCT = ".,;:"


def _text(cell) -> str:
    return "" if cell is None else str(cell)


def strip_value_punctuation(text: str) -> str:
    collapsed = " ".join(_text(text).split())
    return collapsed.strip(_PUNCT + " ").strip().casefold()


def _is_numeric_date(text: str) -> bool:
    # parse_date targets deadline phrases and does not read dd/mm/yyyy.
    m = _NUMERIC_DATE_RE.match(text)
    if not m:
        return False
    day, month = int(m.group(1)), int(m.group(2))
    return 1 <= day <= 31 and 1 <= month <= 12


def _is_date(text: str) -> bool:
    from lib.date_parse import parse_date

    def one(t: str) -> bool:
        return (_is_numeric_date(t) or bool(_D_MON_YY_RE.match(t))
                or parse_date(t) is not None)

    if one(text):
        return True
    tokens = text.split()
    return len(tokens) >= 2 and one(tokens[0])


def _is_reference(text: str) -> bool:
    if (len(text.split()) == 1 and any(c.isdigit() for c in text)
            and _REF_CHARS_RE.search(text)):
        return True
    return bool(_PREFIXED_REF_RE.match(text))


def _kinds(cell) -> tuple[frozenset[Kind], bool]:
    """Return (kinds, bare_digits)."""
    from lib.column_map import canonicalize_header
    from lib.requester_type_map import canonicalize_requester_type
    from lib.status_map import canonicalize_status

    text = " ".join(_text(cell).split())
    if not text:
        return frozenset(), False
    kinds: set[Kind] = set()
    if _is_date(text):
        kinds.add("date")
    if _is_reference(text):
        kinds.add("reference")
    if canonicalize_status(text) is not None:
        kinds.add("status")
    if canonicalize_requester_type(text) is not None:
        kinds.add("requester")
    if canonicalize_header(text) is not None:
        kinds.add("header")
    return frozenset(kinds), bool(_DIGITS_RE.match(text))


def cell_kinds(cell) -> frozenset[Kind]:
    """Every kind the cell positively is; empty when empty or unknown."""
    return _kinds(cell)[0]


def foreign_kind(cell, role: str) -> Optional[Kind]:
    """A kind the cell is that is not the role's own, else None."""
    kinds, bare_digits = _kinds(cell)
    own = ROLE_KIND[role]
    if own in kinds or (own == "reference" and bare_digits):
        return None
    for kind in _FOREIGN_ORDER:
        if kind in kinds:
            return kind
    return None

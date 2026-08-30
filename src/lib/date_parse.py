"""The single deadline parser shared across the action pipelines.

`extract_actions` (plan target dates), `extract_action_status` (a report's
`SMP Deadline` column) and `resolve_action_identity` (a plan's fused
TIMELINE & OUTPUT cell) all parse deadlines. They must agree exactly:
`public-body-actions` publishes an original deadline and a reported deadline
side by side and invites consumers to subtract them, so two parsers that
disagreed on what `Q4 2024` means would manufacture slippage that never
happened. One module, one set of semantics.

Raw-plus-structured and fail-closed: the caller always keeps the raw text,
and structured fields are filled only when a pattern matches confidently.
There is no "best effort" branch — an unmatched cell returns None and the
caller logs a `DateParseError`.
"""
import calendar
import re
from datetime import date

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

PRECISIONS = ("day", "month", "quarter", "year", "range")

_DASH = r"[–—\-]"
_QUARTER_RANGE_RE = re.compile(
    rf"^q([1-4])\s+(\d{{4}})\s*{_DASH}\s*q([1-4])\s+(\d{{4}})$", re.IGNORECASE)
_QUARTER_SINGLE_RE = re.compile(r"^q([1-4])\s+(\d{4})$", re.IGNORECASE)
_QUARTER_SINGLE_YEAR_FIRST_RE = re.compile(r"^(\d{4})\s+q([1-4])$", re.IGNORECASE)
_YEAR_RANGE_RE = re.compile(rf"^(\d{{4}})\s*{_DASH}\s*(\d{{4}})$")
_YEAR_RE = re.compile(r"^(\d{4})$")
_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DAY_MONTH_YEAR_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")
_MONTH_YEAR_RE = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")


def _structured(precision, year=None, quarter=None, month=None, day=None,
                start=None, end=None) -> dict:
    return {"year": year, "quarter": quarter, "month": month, "day": day,
            "precision": precision, "start": start, "end": end}


def _quarter_bounds(year, quarter) -> tuple:
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    end_day = calendar.monthrange(year, end_month)[1]
    return (f"{year:04d}-{start_month:02d}-01",
            f"{year:04d}-{end_month:02d}-{end_day:02d}")


def _month_bounds(year, month) -> tuple:
    end_day = calendar.monthrange(year, month)[1]
    return (f"{year:04d}-{month:02d}-01",
            f"{year:04d}-{month:02d}-{end_day:02d}")


def parse_date(raw):
    """Parse a normalized deadline cell into structured fields, or None.

    Returns the full `year`/`quarter`/`month`/`day`/`precision`/`start`/`end`
    dict when a pattern matches confidently, else None (the caller keeps the
    raw text and logs a `DateParseError` — nothing is silently dropped). For
    `range` precision a single `year`/`quarter` is undefined, so those stay
    null and `start`/`end` carry the span.
    """
    if not raw:
        return None
    text = " ".join(str(raw).split())

    match = _QUARTER_RANGE_RE.match(text)
    if match:
        q1, y1, q2, y2 = (int(match[i]) for i in range(1, 5))
        start, _ = _quarter_bounds(y1, q1)
        _, end = _quarter_bounds(y2, q2)
        return _structured("range", start=start, end=end)

    match = _QUARTER_SINGLE_RE.match(text)
    if match:
        quarter, year = int(match[1]), int(match[2])
        start, end = _quarter_bounds(year, quarter)
        return _structured("quarter", year=year, quarter=quarter,
                           start=start, end=end)

    match = _QUARTER_SINGLE_YEAR_FIRST_RE.match(text)
    if match:
        year, quarter = int(match[1]), int(match[2])
        start, end = _quarter_bounds(year, quarter)
        return _structured("quarter", year=year, quarter=quarter,
                           start=start, end=end)

    match = _ISO_RE.match(text)
    if match:
        year, month, day = (int(match[i]) for i in range(1, 4))
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        iso = parsed.isoformat()
        return _structured("day", year=year, month=month, day=day,
                           start=iso, end=iso)

    match = _DAY_MONTH_YEAR_RE.match(text)
    if match:
        day, name, year = int(match[1]), match[2].lower(), int(match[3])
        month = MONTHS.get(name)
        if month is None:
            return None
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        iso = parsed.isoformat()
        return _structured("day", year=year, month=month, day=day,
                           start=iso, end=iso)

    match = _MONTH_YEAR_RE.match(text)
    if match:
        name, year = match[1].lower(), int(match[2])
        month = MONTHS.get(name)
        if month is None:
            return None
        start, end = _month_bounds(year, month)
        return _structured("month", year=year, month=month, start=start, end=end)

    match = _YEAR_RANGE_RE.match(text)
    if match:
        start_year, end_year = int(match[1]), int(match[2])
        return _structured("range", start=f"{start_year:04d}-01-01",
                           end=f"{end_year:04d}-12-31")

    match = _YEAR_RE.match(text)
    if match:
        year = int(match[1])
        return _structured("year", year=year, start=f"{year:04d}-01-01",
                           end=f"{year:04d}-12-31")

    return None


EMPTY_STRUCTURED = _structured(None)


def structured_fields(parsed) -> dict:
    """`parsed`, or a fresh all-null dict. Fresh, not the shared constant —
    callers merge it into a record and would otherwise alias one dict across
    every undated row."""
    return parsed if parsed is not None else dict(EMPTY_STRUCTURED)

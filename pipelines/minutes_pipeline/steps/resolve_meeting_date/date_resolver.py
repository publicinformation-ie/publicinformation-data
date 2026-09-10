"""Pure meeting-date resolution for the resolve_meeting_date step.

Resolution order, fail-closed (never guess a year from the URL path):
  1. A deterministic ISO date already set by find_minutes_files.
  2. The LLM's stated_date, only if it parses to a full calendar day.
  3. A <day> <MonthName> from the document header, combined with either a
     year in that same header phrase or the year from the link text's
     "<MonthName> <YYYY>" — but only when the two month names agree.
  4. Otherwise unresolved: return an UnresolvedMeetingDate error when the
     document carried motions (real loss), or nothing when it did not.
"""
import re
from datetime import date

from lib.date_parse import parse_date

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
_MONTH_ALT = "|".join(_MONTHS)
_MONTH_INDEX = {name: i + 1 for i, name in enumerate(_MONTHS)}

_LINK_YEAR_RE = re.compile(rf"\b({_MONTH_ALT})\s+((?:19|20)\d{{2}})\b", re.IGNORECASE)
_BODY_DAYMONTH_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT})\b(?:\s+((?:19|20)\d{{2}}))?",
    re.IGNORECASE,
)
_HEADER_LINES = 15


def _canon_month(raw: str) -> str:
    return raw[:1].upper() + raw[1:].lower()


def link_text_year_month(link_text):
    if not link_text:
        return None, None
    m = _LINK_YEAR_RE.search(link_text)
    if not m:
        return None, None
    return _canon_month(m.group(1)), int(m.group(2))


def body_header_daymonth(text):
    if not text:
        return None
    header = "\n".join(text.splitlines()[:_HEADER_LINES])
    found = {}                                   # (day, month) -> year | None
    for m in _BODY_DAYMONTH_RE.finditer(header):
        day = int(m.group(1))
        if not 1 <= day <= 31:
            continue
        month = _canon_month(m.group(2))
        year = int(m.group(3)) if m.group(3) else None
        key = (day, month)
        if key not in found or (found[key] is None and year is not None):
            found[key] = year
    if len(found) != 1:
        return None
    (day, month), year = next(iter(found.items()))
    return day, month, year


def _safe_iso(year: int, month: str, day: int):
    try:
        return date(year, _MONTH_INDEX[month], day).isoformat()
    except (ValueError, KeyError):
        return None


def _is_full_day(raw):
    parsed = parse_date(raw) if raw else None
    if parsed and parsed.get("precision") == "day":
        return parsed["start"]
    return None


def resolve(record):
    """(iso_date | None, error_dict | None). See module docstring."""
    # 1. Deterministic upstream date.
    upstream = _is_full_day(record.get("meeting_date"))
    if upstream:
        return upstream, None

    # 2. LLM stated a full calendar date.
    stated = _is_full_day(record.get("stated_date"))
    if stated:
        return stated, None

    # 3. Merge header day+month with a corroborated year.
    header = body_header_daymonth(record.get("text"))
    link_month, link_year = link_text_year_month(record.get("link_text"))
    if header:
        day, body_month, body_year = header
        if body_year is not None:
            iso = _safe_iso(body_year, body_month, day)
            if iso:
                return iso, None
        if link_year is not None and link_month == body_month:
            iso = _safe_iso(link_year, body_month, day)
            if iso:
                return iso, None

    # 4. Unresolved.
    if record.get("motions"):
        return None, {
            "error_type": "UnresolvedMeetingDate",
            "error_message": (
                f"no full meeting date: header day/month {header!r}, "
                f"link-text {link_month} {link_year}, "
                f"llm stated_date {record.get('stated_date')!r}"
            ),
            "context": {
                "public_body_id": record.get("public_body_id"),
                "file_url": record.get("file_url"),
            },
        }
    return None, None

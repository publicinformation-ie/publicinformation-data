"""Header layout profiles: vocabulary as data, geometry as code.

A committee names a profile in ``committees.json``. A profile supplies the
label vocabulary and the date line of its council's minutes; the geometry that
reads the attendance block lives in ``header.py``. A label that a profile does
not map is an ``UnrecognisedHeaderLayout`` error, never a guess.

``meath-table`` is the original layout (labels in a left column, handled by
the code that predates profiles). ``kildare-table`` and ``westmeath-list`` both
print "Label  value" rows whose continuation lines align under the value; they
share one routine and differ only in the data below.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MONTHS_PATTERN = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_WEEKDAY = r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?"
_AMPM = r"(?:a\.?m\.?|p\.?m\.?)"
_TIME = r"\d{1,2}(?:[.:]\d{2})?\s*" + _AMPM


@dataclass(frozen=True)
class Label:
    """A printed attendance label and what it means.

    ``pattern`` is matched, case-insensitively, against the start of a line; the
    words it consumes are the label and the rest of the line is the first value
    row. ``marker`` is a mode marker the label itself prints (``remote`` for an
    "Online:" row), applied to every name in the block.
    """

    pattern: str
    category: str
    marker: str | None = None

    def match(self, text: str):
        return re.match(self.pattern + r"(?![A-Za-z])\s*:?\s*", text, re.IGNORECASE)


@dataclass(frozen=True)
class LayoutProfile:
    name: str
    routine: str                       # "meath-table" or "label-value"
    labels: tuple[Label, ...] = ()
    #: Regex over the header text (newlines folded to spaces); named groups
    #: ``day``, ``month`` and optional ``year``, ``venue``, ``time``.
    date_line: str = ""
    #: Item heading forms the renderer recognises: each captures (number, title).
    item_headings: tuple[str, ...] = ()
    #: Page furniture the renderer removes, as ``(kind, regex)``: a line matching
    #: it that also repeats at a page edge. Empty for the scanned layouts.
    furniture: tuple[tuple[str, str], ...] = ()
    #: Headings the renderer gives each attendance category (the printed labels).
    attendance_headings: tuple[tuple[str, str], ...] = ()
    #: How a block's value words split into people: ``titled-run`` (a person
    #: starts at each title: "Ms Celina Barrett, A/Director of Services; Mr ...")
    #: or ``one-per-line`` ("Jean Ryan, Director of Services" on its own line).
    entries: str = "titled-run"
    #: Title tokens ("Cllr.", "Mr", ...), compared without a trailing dot or comma.
    titles: frozenset[str] = field(default_factory=frozenset)
    #: Words that start a role rather than a name (``titled-run`` only).
    role_words: frozenset[str] = field(default_factory=frozenset)


_KILDARE_LABELS = (
    Label(r"Attendees", "councillors"),
    Label(r"Online", "councillors", marker="remote"),
    Label(r"Also(?:\s+Present)?", "officials"),
    Label(r"Guest", "guests"),
    Label(r"Apologies", "apologies"),
    Label(r"Not\s+Present", "absent"),
)

_WESTMEATH_LABELS = (
    Label(r"Members\s+Present", "councillors"),
    Label(r"Sectoral\s+Reps", "sectoral_representatives"),
    Label(r"Officials\s+Present", "officials"),
    Label(r"External\s+Presenters", "presenters"),
    Label(r"Apologies", "apologies"),
)

# "Minutes of Meeting held on Thursday, 11 December 2025 at 3.30p.m. in the
#  Committee Room, Aras Chill Dara, Naas."  (the time may follow a comma; the
#  venue follows "in the")
_KILDARE_DATE_LINE = (
    r"held\s+(?:on\s+)?(?:" + _WEEKDAY + r"\s+)?"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>" + MONTHS_PATTERN + r")\s+(?P<year>\d{4})"
    r"[\s,]*(?:at\s+)?(?P<time>" + _TIME + r")?"
    r"[\s.,]*(?:in\s+(?:the\s+)?)?(?P<venue>.*)"
)

# "Minutes of Planning, Regeneration & Transportation Strategic Policy Committee
#  Meeting, held in the Council Chambers, Aras an Chontae, Mullingar at 2.30pm on
#  Friday 23 May 2025 - Hybrid Meeting"
_WESTMEATH_DATE_LINE = (
    r"held\s+(?P<venue>.+?)\s+at\s+(?P<time>" + _TIME + r")\s+on\s+(?:" + _WEEKDAY + r"\s+)?"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>" + MONTHS_PATTERN + r")(?:\s+(?P<year>\d{4}))?"
)

# "Item 1 — Declarations", "Item 9- Any Other Business", "Item 2: Matters Arising".
# Scans read "Item" as "item" or "ltem" and the dash as "-—"; the separator is one
# or more dashes or a colon. Compared case-insensitively.
_ITEM_WORD = r"[Il]tem"
_KILDARE_ITEM = r"^" + _ITEM_WORD + r"\s+(\d+)\s*(?:[—–-]+|:)\s*(.*)$"
_WESTMEATH_ITEM = r"^" + _ITEM_WORD + r"\s+(\d+)\s*:\s*(.*)$"

PROFILES: dict[str, LayoutProfile] = {
    "meath-table": LayoutProfile(
        name="meath-table",
        routine="meath-table",
        furniture=(
            ("running_header", r"^Miontuairiscí/Meeting Minutes$"),
            ("page_number", r"^Page\s+\d+\s+of\s+\d+$"),
            ("footer", r"(meath\.ie|Meath County Council|Telephone:|Fax:|Email:|Buvinda House)"),
        ),
    ),
    "kildare-table": LayoutProfile(
        name="kildare-table",
        routine="label-value",
        labels=_KILDARE_LABELS,
        date_line=_KILDARE_DATE_LINE,
        item_headings=(_KILDARE_ITEM,),
        attendance_headings=(
            ("councillors", "Attendees"), ("officials", "Also present"),
            ("guests", "Guests"), ("apologies", "Apologies"), ("absent", "Not present"),
        ),
        entries="titled-run",
        titles=frozenset({"Councillor", "Cllr", "Mr", "Ms", "Mrs", "Dr", "Cathaoirleach"}),
        role_words=frozenset({
            "Director", "Senior", "Executive", "Assistant", "Staff", "Road", "Engineer",
            "Officer", "Administrative", "Parks", "Landscape", "Landscaping", "Estates",
            "Sustainable", "Planner", "Technician", "Manager", "Secretary", "Clerk",
        }),
    ),
    "westmeath-list": LayoutProfile(
        name="westmeath-list",
        routine="label-value",
        labels=_WESTMEATH_LABELS,
        date_line=_WESTMEATH_DATE_LINE,
        item_headings=(_WESTMEATH_ITEM,),
        attendance_headings=(
            ("councillors", "Members present"),
            ("sectoral_representatives", "Sectoral reps"),
            ("officials", "Officials present"), ("presenters", "External presenters"),
            ("apologies", "Apologies"),
        ),
        entries="one-per-line",
        titles=frozenset({"Councillor", "Cllr"}),
    ),
}


def profile_for(layout: str) -> LayoutProfile:
    try:
        return PROFILES[layout]
    except KeyError:
        raise KeyError(f"unknown header layout {layout!r}") from None

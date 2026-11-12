"""Split an action's interim-milestone prose into one record per milestone.

Pure functions, no I/O. The plans print milestones as flat text in three shapes
(`Q1 2029 – text. Q3 2030 – text`, `2024: text. 2025: text`, and date-only
lists on the climate action plan annexes). A piece is dated only when a marker
in the text states the date; nothing is inferred.

The split is lossless: pieces are slices of the whitespace-normalised input,
so re-joining them with single spaces reproduces it exactly. A violation
raises `MilestoneRoundTripFailed` rather than publishing a partial split.
"""
import re
from dataclasses import dataclass

from lib.date_parse import parse_date

_DASH = "-–—"
_YEAR = r"(?:19|20)\d{2}"
_QUARTER = r"Q\s?([1-4])\s+(" + _YEAR + r")"

# `Q1 2029 –` / `Q1 2029:`; a mid-sentence `by Q4 2030.` has no delimiter and
# is therefore prose.
_QUARTER_MARKER = re.compile(
    r"(?<![\w-])" + _QUARTER + r"(?!\d)(?=\s*[" + _DASH + r":])\s*[" + _DASH + r":]?")
# `2024:`
_YEAR_COLON = re.compile(r"(?<![\w-])(" + _YEAR + r")(?=:)\s*:?")
# `2027 interim target -`
_INTERIM = re.compile(
    r"(?<![\w-])(" + _YEAR + r")\s+interim\s+target(?=\s*[" + _DASH + r"])\s*[" + _DASH + r"]?")
# `2028 –` / `2028 onwards –`, only at the start or after a sentence end, and
# only with whitespace around the dash so `IMMAC 2025-2030` never matches.
_BARE_YEAR = re.compile(
    r"(?<![\w-])(" + _YEAR + r")(\s+onwards)?(?=\s+[" + _DASH + r"]\s)\s+[" + _DASH + r"]")

# A cell that is nothing but dates (`Q2 2023; Q4 2023`, `Q 4 2024`).
_DATE_ONLY = re.compile(r"^(?:" + _QUARTER + r"[\s;,]*)+$")
_DATE_ONLY_TOKEN = re.compile(_QUARTER + r"[\s;,]*")


class MilestoneRoundTripFailed(Exception):
    """The pieces did not re-join to the normalised input."""


@dataclass(frozen=True)
class Milestone:
    ordinal: int
    due_label: str
    due_start: str | None
    due_end: str | None
    due_precision: str | None
    text: str
    raw: str


def _normalise(text) -> str:
    # str.split() treats non-breaking spaces as whitespace.
    return " ".join(str(text or "").split())


def _dated(label: str, parse_as: str | None = None) -> tuple:
    parsed = parse_date(parse_as or label)
    if not parsed or parsed["precision"] not in ("quarter", "year"):
        return "", None, None, None
    return label, parsed["start"], parsed["end"], parsed["precision"]


def _markers(text: str) -> list:
    """`(start, end, label, parse_as)` for every marker, in document order."""
    if _DATE_ONLY.match(text):
        return [(m.start(), m.end(), f"Q{m.group(1)} {m.group(2)}", None)
                for m in _DATE_ONLY_TOKEN.finditer(text)]
    found = []
    for m in _QUARTER_MARKER.finditer(text):
        found.append((m.start(), m.end(), f"Q{m.group(1)} {m.group(2)}", None))
    for m in _YEAR_COLON.finditer(text):
        found.append((m.start(), m.end(), m.group(1), None))
    for m in _INTERIM.finditer(text):
        found.append((m.start(), m.end(), m.group(1), None))
    for m in _BARE_YEAR.finditer(text):
        at_sentence_start = m.start() == 0 or text[:m.start()].endswith(". ")
        if at_sentence_start:
            label = m.group(1) + (" onwards" if m.group(2) else "")
            found.append((m.start(), m.end(), label, m.group(1)))
    found.sort()
    # Drop markers overlapping an earlier one (e.g. `Q1 2029:` also matches
    # the bare `2029:` rule).
    kept, last_end = [], -1
    for marker in found:
        if marker[0] >= last_end:
            kept.append(marker)
            last_end = marker[1]
    return kept


def split_milestones(text) -> list:
    """One `Milestone` per marker, document order. Empty input gives `[]`."""
    normalised = _normalise(text)
    if not normalised:
        return []
    markers = _markers(normalised)

    pieces = []  # (label, parse_as, text_start, slice_start, slice_end)
    if not markers or markers[0][0] > 0:
        first_end = markers[0][0] if markers else len(normalised)
        pieces.append(("", None, 0, 0, first_end))
    for index, (start, end, label, parse_as) in enumerate(markers):
        slice_end = markers[index + 1][0] if index + 1 < len(markers) else len(normalised)
        pieces.append((label, parse_as, end, start, slice_end))

    milestones = []
    for ordinal, (label, parse_as, text_start, start, end) in enumerate(pieces, 1):
        raw = normalised[start:end].strip()
        body = normalised[text_start:end].strip()
        due = _dated(label, parse_as) if label else ("", None, None, None)
        milestones.append(Milestone(ordinal, due[0], due[1], due[2], due[3],
                                    body.lstrip(_DASH + ":;, ").strip()
                                    if label else body, raw))

    if " ".join(m.raw for m in milestones) != normalised:
        raise MilestoneRoundTripFailed(normalised)
    return milestones

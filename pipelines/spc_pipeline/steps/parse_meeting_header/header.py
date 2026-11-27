"""Meeting header, date and attendance-table parsing for SPC minutes.

pdfplumber's plain text interleaves the two-column attendance table, so the
table is read by word coordinates: label words occupy a left column, values a
right column. Only the Meath layout is supported; anything unrecognised fails
closed with ``UnrecognisedHeaderLayout``.

The parser never decides who a printed name *is* — that is
``resolve_attendees``' job against the committed register. It records the
printed name, title, initials, role text and mode markers exactly as seen.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from steps.parse_meeting_header.layouts import LayoutProfile, profile_for

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

_DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)
_START_RE = re.compile(r"\bat\s+(\d{1,2}[.:]\d{2}\s*(?:am|pm)?)", re.IGNORECASE)
_MONTH_ABBREVIATIONS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_LINK_MONTH_RE = re.compile(
    r"\b(" + "|".join(m.title() for m in MONTHS)
    + "|" + "|".join(a.title() for a in sorted(_MONTH_ABBREVIATIONS, key=len, reverse=True))
    + r")\.?\s+(\d{4})\b")
_END_RE = re.compile(
    r"Meeting ended\s*@?\s*([0-9]{1,2}[.:][0-9]{2}\s*(?:am|pm)?)", re.IGNORECASE
)

TITLE_TOKENS = {"Cllr", "Cllr.", "Mr.", "Ms.", "Mrs.", "Dr."}

# Words that mark the start of a role rather than a name. Used only to split a
# fragment into name and role; a wrong split becomes an unresolved attendee,
# never a new person.
ROLE_KEYWORDS = {
    "DOS", "PPN", "SE", "Acting", "Administrative", "Architect", "Assistant",
    "Chair", "Chief", "Clerk", "Climate", "Co-Ordinator", "Coordinator",
    "Council", "County", "Deputy", "Director", "Engineer", "Executive",
    "Finance", "Graduate", "Head", "Legal", "Lighting", "Manager", "Meetings",
    "Officer", "Operations", "Programme", "Public", "Regeneration", "Rep",
    "Road", "Safety", "Secretary", "Senior", "Services", "Staff", "Supervisor",
    "Team", "Technician", "Traffic",
}

_MARKER_PATTERNS = {
    "remote": (r"\bvia\s+teams\b", r"\bonline\b"),
    "in_person": (r"\bin\s+person\b",),
    "apologies": (r"\bapologies\b",),
}

_LABEL_STARTS = ("Attendees", "Absent", "Apologies:", "(Officials):",
                 "Presenters", "Presentations")
_LABEL_LINE_STARTS = ("Attendees", "Absent", "(Officials):", "Presenters", "Presentations")


class HeaderParseError(ValueError):
    error_type = "HeaderParseError"


class UnrecognisedHeaderLayout(HeaderParseError):
    error_type = "UnrecognisedHeaderLayout"


class MeetingDateUnparseable(HeaderParseError):
    error_type = "MeetingDateUnparseable"


class MeetingDateMismatch(HeaderParseError):
    error_type = "MeetingDateMismatch"


# ---------------------------------------------------------------------------
# Line and column helpers
# ---------------------------------------------------------------------------

def words_to_lines(words: list[dict], tolerance: float = 2.0) -> list[dict]:
    """Group words into physical lines; each line keeps x order.

    Text-layer words are grouped by ``top``. OCR words carry the ``line`` id
    Tesseract assigned, and are grouped by it: a scan is rarely level, so two
    words on one printed line can differ by several points in ``top``, which
    a ``top`` tolerance would split into separate lines.
    """
    if words and all("line" in word for word in words):
        return _ocr_lines(words)
    lines: list[dict] = []
    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if lines and abs(word["top"] - lines[-1]["top"]) <= tolerance:
            lines[-1]["words"].append(word)
        else:
            lines.append({"top": word["top"], "words": [word]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
        line["text"] = " ".join(w["text"] for w in line["words"])
    return lines


def _ocr_lines(words: list[dict]) -> list[dict]:
    by_id: dict[int, list[dict]] = {}
    for word in words:
        by_id.setdefault(word["line"], []).append(word)
    lines = []
    for members in by_id.values():
        members = sorted(members, key=lambda w: w["x0"])
        lines.append({
            "top": sum(w["top"] for w in members) / len(members),
            "words": members,
            "text": " ".join(w["text"] for w in members),
        })
    lines.sort(key=lambda line: (round(line["top"], 1), line["words"][0]["x0"]))
    return lines


def _split_label_from_values(line: dict) -> tuple[list[dict], list[dict]]:
    """Split a line into its label-column and value-column words.

    Labels sit on the left at a fixed left edge; the value column is separated
    by a wide horizontal gap. The "Presentations made by -" label has its
    value text flowing straight on, so it is split explicitly.
    """
    words = line["words"]
    if words and words[0]["text"] == "Presentations":
        dash = next((i for i, w in enumerate(words) if w["text"] == "-"), None)
        if dash is None:
            dash = len(words) - 1
        return words[:dash + 1], words[dash + 1:]
    for index in range(1, len(words)):
        if words[index]["x0"] - words[index - 1]["x1"] > 10:
            return words[:index], words[index:]
    return words, []


def _label_column(lines: list[dict]) -> tuple[float, list[dict], float]:
    """Return ``(value_left, label_blocks, header_end_top)``.

    A label block is one or more label lines (e.g. "Attendees –" followed by
    "(Councillors):"). The value column starts at the left edge of the words
    printed to the right of the labels.
    """
    label_lines = [
        line for line in lines
        if line["words"] and line["words"][0]["text"] in _LABEL_LINE_STARTS
    ]
    if not label_lines:
        raise UnrecognisedHeaderLayout("no attendance label column found on page 1")

    label_right = 0.0
    right_edges: list[float] = []
    for line in label_lines:
        left, right = _split_label_from_values(line)
        label_right = max(label_right, max(w["x1"] for w in left))
        right_edges.extend(w["x0"] for w in right)
    if right_edges:
        value_left = min(right_edges) - 1
    else:
        candidates = [
            w["x0"] for line in lines for w in line["words"]
            if w["x0"] > label_right + 20
        ]
        if not candidates:
            raise UnrecognisedHeaderLayout("no values in the attendance value column")
        value_left = min(candidates) - 1

    header_end = _header_end_top(lines, value_left)
    blocks: list[dict] = []
    started = False
    for line in lines:
        if line["top"] >= header_end:
            break
        if not line["words"]:
            continue
        if line["words"][0]["text"] == "Presentations":
            # The presentations label is printed in the value column, with its
            # value text flowing on after the dash.
            blocks.append({"top": line["top"], "label_lines": ["Presentations made by -"]})
            started = True
            continue
        if line["words"][0]["x0"] >= value_left:
            continue
        left, _right = _split_label_from_values(line)
        text = " ".join(w["text"] for w in left).strip()
        if not text:
            continue
        if text.startswith(_LABEL_LINE_STARTS):
            blocks.append({"top": line["top"], "label_lines": [text]})
            started = True
        elif started and blocks:
            blocks[-1]["label_lines"].append(text)
        elif started:
            raise UnrecognisedHeaderLayout(f"unexpected attendance label text: {text!r}")
    for block in blocks:
        block["label"] = _normalise_label(" ".join(block["label_lines"]))
    return value_left, blocks, header_end


def _header_end_top(lines: list[dict], value_left: float) -> float:
    """Top of the first "Item" line after the labels, else page infinity."""
    for line in lines:
        if line["words"][0]["text"] == "Item" and line["words"][0]["x0"] < value_left:
            return line["top"]
    return float("inf")


def _normalise_label(label: str) -> str:
    label = label.replace("–", "-").replace("—", "-")
    label = re.sub(r"\s+", " ", label).strip()
    label = re.sub(r"\s*-\s*", " - ", label)
    return label


_LABEL_CATEGORIES = (
    (re.compile(r"^Attendees\s*-\s*\(Councillors\):?$"), "councillors"),
    (re.compile(r"^Attendees\s*-\s*\(Sectoral Representatives\):?$"),
     "sectoral_representatives"),
    (re.compile(r"^Absent\s*Apologies:?$"), "apologies"),
    (re.compile(r"^Absent:?$"), "apologies"),
    (re.compile(r"^Apologies:?$"), "apologies"),
    (re.compile(r"^\(Officials\):?$"), "officials"),
    (re.compile(r"^Presenters:?$"), "presenters"),
    (re.compile(r"^Presentations made by\s*-\s*$"), "presenters"),
)


def label_category(label: str) -> str:
    for pattern, category in _LABEL_CATEGORIES:
        if pattern.match(label):
            return category
    raise UnrecognisedHeaderLayout(f"unrecognised attendance label: {label!r}")


# ---------------------------------------------------------------------------
# Entry splitting and name/role extraction
# ---------------------------------------------------------------------------

def _strip_markers(text: str) -> tuple[str, list[str]]:
    markers: list[str] = []
    for marker, patterns in _MARKER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                markers.append(marker)
                text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text, markers


_LEADING_MARKER_RE = re.compile(
    r"^(apologies|via\s+teams|online|in\s+person)\b[.,;:]?\s*", re.IGNORECASE
)


def _marker_kind(phrase: str) -> str:
    lowered = phrase.lower()
    if lowered.startswith("apologies"):
        return "apologies"
    if lowered.startswith("in person"):
        return "in_person"
    return "remote"


def _take_leading_markers(text: str) -> tuple[list[str], str]:
    """Markers printed before a name apply to the *previous* entry."""
    markers: list[str] = []
    while True:
        match = _LEADING_MARKER_RE.match(text)
        if not match:
            return markers, text
        markers.append(_marker_kind(match.group(1)))
        text = text[match.end():]


def _is_title(token: str) -> bool:
    return token.rstrip(",") in TITLE_TOKENS


def _role_at(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        if token.strip(".,") in ROLE_KEYWORDS:
            return index
    return None


def _looks_like_person(text: str) -> bool:
    """True when a fragment reads as a person rather than a role phrase."""
    text = text.strip(" ,;.")
    if not text or text in TITLE_TOKENS:
        return False
    tokens = text.split()
    if _is_title(tokens[0]):
        return True
    if _role_at(tokens) == 0:
        return False
    paren = re.match(r"^(?P<name>.+?)\s*\((?P<initials>[A-Za-z'’]{1,6})\)", text)
    if paren:
        name_tokens = paren.group("name").split()
        role = _role_at(name_tokens)
        if role is None and 1 <= len(name_tokens) <= 4:
            return True
        return role is not None and role > 0
    if _role_at(tokens) is not None:
        return True
    return 1 <= len(tokens) <= 4 and all(token[:1].isupper() for token in tokens if token)


def _split_fragments(words: list[dict]) -> list[str]:
    """Split a block's value words into printed fragments.

    Boundaries: comma/semicolon after a word, a bullet, a separating "&"
    before a person, a title token after a complete name, and a line break
    that starts a new person (a wrapped role line continues the entry).
    """
    fragments: list[str] = []
    current: list[str] = []
    tokens = [word["text"] for word in words]
    tops = [word["top"] for word in words]

    def flush() -> None:
        text = " ".join(current).strip()
        if text:
            fragments.append(text)
        current.clear()

    for index, token in enumerate(tokens):
        new_line = index > 0 and abs(tops[index] - tops[index - 1]) > 2
        if new_line and current and _line_starts_new_person(current, token):
            flush()
        if token == "•":
            flush()
            continue
        if token == "&" and _starts_person_after(tokens, index + 1):
            flush()
            continue
        if _is_title(token) and current and _complete_fragment(current):
            flush()
        current.append(token)
        if token.endswith(",") or token.endswith(";"):
            flush()
    flush()
    return fragments


def _line_starts_new_person(current: list[str], token: str) -> bool:
    """At a wrapped line, does ``token`` begin a new person rather than a role?"""
    if token in ("•", "&"):
        return False
    if not _complete_fragment(current):
        return False
    cleaned = token.strip(" ,;.")
    if cleaned in TITLE_TOKENS:
        return True
    if cleaned in ROLE_KEYWORDS:
        return False
    if cleaned.lower() in ("via", "online", "in", "person", "person.", "apologies"):
        return False
    return cleaned[:1].isupper()


def _complete_fragment(current: list[str]) -> bool:
    """True when the words so far already form a name (before another title)."""
    text = " ".join(current).strip(" ,;")
    if not text:
        return False
    if re.search(r"\([A-Za-z'’]{1,6}\)", text):
        return True
    tokens = [t.strip(" ,;") for t in current if t.strip(" ,;")]
    return len([t for t in tokens if not _is_title(t)]) >= 2


def _starts_person_after(tokens: list[str], start: int) -> bool:
    """True for "& Bernard Cooney - Senior ...", false for continuation "& Community ..."."""
    following = tokens[start:start + 4]
    if len(following) < 3:
        return False
    first = following[0].strip(" ,;.")
    second = following[1].strip(" ,;.")
    third = following[2].strip(" ,;.")
    if not (first[:1].isupper() and second[:1].isupper()):
        return False
    if first in TITLE_TOKENS or second in TITLE_TOKENS:
        return False
    if first in ROLE_KEYWORDS or second in ROLE_KEYWORDS:
        return False
    # A person after "&" is introduced by a dash or immediately by a role;
    # "& Community Centers Footpath Programme" is a continuation of a title.
    return third.startswith(("-", "–")) or third in ROLE_KEYWORDS


def _split_name_role(text: str) -> tuple[str, str, str | None]:
    """Return ``(name, role, initials)`` from one person fragment."""
    text = re.sub(r"\s+", " ", text).strip(" ,;.")
    paren = re.match(
        r"^(?P<name>.+?)\s*\((?P<initials>[A-Za-z'’]{1,6})\)\s*(?P<role>.*)$", text
    )
    if paren:
        name_tokens = paren.group("name").split()
        role_index = _role_at(name_tokens)
        if role_index is not None and role_index > 0:
            name = " ".join(name_tokens[:role_index])
            role = " ".join(name_tokens[role_index:]) + " " + paren.group("role")
            return name.strip(" ,;."), role.strip(" ,;."), None
        role = paren.group("role").strip(" ,;.")
        return paren.group("name").strip(" ,;."), role, paren.group("initials")
    # Dashes separate the name from the role: "Caroline Corrigan - Senior
    # Engineer", "John McGrath -Senior Engineer- Regeneration Team – Ongoing".
    for match in re.finditer(r"\s*[-–]\s*", text):
        name = text[:match.start()].strip(" ,;.")
        role = text[match.end():].strip(" ,;.")
        role_tokens = role.split()
        if not role or len(name.split()) < 2 or len(name.split()) > 4:
            continue
        if _role_at(role_tokens) is not None:
            return name, role, None
    name_tokens = text.split()
    role_index = _role_at(name_tokens)
    if role_index is not None and role_index > 0:
        return (" ".join(name_tokens[:role_index]).strip(" ,;."),
                " ".join(name_tokens[role_index:]).strip(" ,;."), None)
    return text.strip(" ,;."), "", None


def _strip_title(name: str) -> tuple[str, str | None]:
    tokens = name.split()
    if tokens and _is_title(tokens[0]):
        return " ".join(tokens[1:]).strip(), tokens[0].rstrip(".")
    return name.strip(), None


def _append_fragment(raw: str, text: str) -> str:
    """Append a printed fragment to the text kept for the verbatim minutes."""
    raw = raw.rstrip()
    separator = " " if raw.endswith((",", ";", "&", "-", "–", "/")) else ", "
    return f"{raw}{separator}{text}".strip()


def parse_entries(words: list[dict], category: str) -> tuple[list[dict], int]:
    """Parse one attendance block's value words into entries.

    Returns ``(entries, ignored_fragment_count)``.
    """
    entries: list[dict] = []
    ignored = 0
    pending_markers: list[str] = []
    pending_role = ""

    for fragment in _split_fragments(words):
        leading, remainder = _take_leading_markers(fragment)
        text, markers = _strip_markers(remainder)
        text = text.strip(" ,;.")
        if leading:
            if entries:
                entries[-1]["markers"].extend(leading)
            else:
                pending_markers.extend(leading)
        if not text:
            continue
        if text in TITLE_TOKENS:
            ignored += 1
            continue
        if not _looks_like_person(text):
            if entries:
                existing = entries[-1]["role"]
                separator = " " if existing.rstrip().endswith(("&", "-", "–", "/")) else ", "
                entries[-1]["role"] = (existing + (separator if existing else "") + text).strip(", ")
                entries[-1]["raw"] = _append_fragment(entries[-1]["raw"], text)
            else:
                pending_role = (pending_role + ", " + text).strip(", ")
            continue

        name, role, initials = _split_name_role(text)
        name, title = _strip_title(name)
        if not name:
            ignored += 1
            continue
        printed = fragment.strip()
        if pending_role:
            printed = f"{pending_role}, {printed}"
        entries.append({
            "category": category,
            "printed_name": name,
            "title": title,
            "initials": initials,
            "role": (pending_role + (", " if pending_role and role else "") + role).strip(", "),
            "markers": markers + pending_markers,
            "raw": printed,
        })
        pending_markers = []
        pending_role = ""
    return entries, ignored


# ---------------------------------------------------------------------------
# Header text: date, venue, times
# ---------------------------------------------------------------------------

def page_text(pages: list[dict]) -> str:
    """The page's text in reading order, page by page.

    Lines are rebuilt per page: sorting every word by ``top`` across pages
    would interleave the pages' words vertically.
    """
    page_texts = []
    for page in pages:
        lines = words_to_lines(page["words"])
        page_texts.append("\n".join(line["text"] for line in lines))
    return "\n".join(page_texts)


def parse_date_and_venue(header_text: str) -> tuple[str, date, str, str | None]:
    """Return ``(date_text, date, venue, start_time)`` from the header lines."""
    matches = list(_DATE_RE.finditer(header_text))
    if not matches:
        raise MeetingDateUnparseable("no '<day> <month> <year>' date in the header")
    first = matches[0]
    day, month_name, year = first.groups()
    try:
        meeting_date = date(int(year), MONTHS[month_name.lower()], int(day))
    except ValueError as exc:
        raise MeetingDateUnparseable(f"invalid header date {first.group(0)!r}: {exc}") from exc

    after = header_text[first.end():].lstrip(" ,")
    start_match = _START_RE.search(after)
    start_time = start_match.group(1).strip() if start_match else None
    venue_part = after[:start_match.start()] if start_match else after
    venue = re.sub(r"\s+", " ", venue_part.strip().strip(",").strip())
    return first.group(0), meeting_date, venue, start_time


def parse_end_time(all_text: str) -> str | None:
    match = _END_RE.search(all_text)
    return match.group(1).strip() if match else None


def link_month_year(link_text: str | None) -> tuple[int, int] | None:
    if not link_text:
        return None
    match = _LINK_MONTH_RE.search(link_text)
    if not match:
        return None
    name = match.group(1).lower()
    month = MONTHS.get(name) or _MONTH_ABBREVIATIONS[name]
    return month, int(match.group(2))


def make_meeting_id(committee_id: str, meeting_date: date) -> str:
    return f"{committee_id}/{meeting_date.isoformat()}"


# ---------------------------------------------------------------------------
# One meeting
# ---------------------------------------------------------------------------

def parse_record(source: dict) -> dict:
    """Parse one fetched record into a meeting record (or raise HeaderParseError).

    The committee's layout profile (``source["layout"]``, carried from
    ``committees.json``) selects the routine; a record with no layout is a
    Meath one, which is what the unit tests build.
    """
    profile = profile_for(source.get("layout") or "meath-table")
    if profile.routine == "meath-table":
        return _parse_meath_table(source)
    return _parse_label_value(source, profile)


def _parse_meath_table(source: dict) -> dict:
    pages = source["pages"]
    if not pages:
        raise UnrecognisedHeaderLayout("the PDF has no pages")
    first_page = pages[0]
    lines = words_to_lines(first_page["words"])

    # Header text is everything above the first attendance label.
    first_label_top = next(
        (line["top"] for line in lines
         if line["words"][0]["text"] in ("Attendees", "Absent", "(Officials):")),
        None,
    )
    if first_label_top is None:
        raise UnrecognisedHeaderLayout("no attendance labels on page 1")
    header_text = "\n".join(
        line["text"] for line in lines if line["top"] < first_label_top
    )
    date_text, meeting_date, venue, start_time = parse_date_and_venue(header_text)

    linked = link_month_year(source.get("link_text"))
    if linked is not None and (linked[0], linked[1]) != (meeting_date.month, meeting_date.year):
        raise MeetingDateMismatch(
            f"header says {date_text!r} but link text says {source.get('link_text')!r}"
        )

    end_time = parse_end_time(page_text(pages))

    value_left, blocks, header_end = _label_column(lines)
    entries: list[dict] = []
    ignored_total = 0
    for index, block in enumerate(blocks):
        category = label_category(block["label"])
        block_end = blocks[index + 1]["top"] if index + 1 < len(blocks) else header_end
        block_words = _value_words(lines, block["top"], block_end, value_left)
        parsed, ignored = parse_entries(block_words, category)
        entries.extend(parsed)
        ignored_total += ignored

    return _build_record(source, meeting_date, date_text, venue, start_time,
                         end_time, entries, ignored_total)


def _build_record(source: dict, meeting_date: date, date_text: str, venue: str,
                  start_time: str | None, end_time: str | None, entries: list[dict],
                  ignored_total: int, **extra) -> dict:
    pages = source["pages"]
    initials: dict[str, str] = {}
    initials_conflicts: list[dict] = []
    for entry in entries:
        if not entry["initials"]:
            continue
        if entry["initials"] in initials and initials[entry["initials"]] != entry["printed_name"]:
            initials_conflicts.append({
                "initials": entry["initials"],
                "names": [initials[entry["initials"]], entry["printed_name"]],
            })
        else:
            initials[entry["initials"]] = entry["printed_name"]

    return {
        "meeting_id": make_meeting_id(source["committee_id"], meeting_date),
        "committee_id": source["committee_id"],
        "committee_name": source["committee_name"],
        "public_body_id": source["public_body_id"],
        "page_url": source["page_url"],
        "meeting_date": meeting_date.isoformat(),
        "date_text": date_text,
        "venue": venue,
        "start_time": start_time,
        "end_time": end_time,
        "source_url": source["file_url"],
        "source_sha256": source["sha256"],
        "link_text": source.get("link_text"),
        "page_count": source["page_count"],
        "initials": initials,
        "initials_conflicts": initials_conflicts,
        "ignored_fragments": ignored_total,
        "attendance": entries,
        "layout": source.get("layout") or "meath-table",
        "text_source": source.get("text_source", "text_layer"),
        "ocr_engine": source.get("ocr_engine"),
        "ocr_skipped_pages": source.get("ocr_skipped_pages", 0),
        "pages": pages,
        **extra,
    }


# ---------------------------------------------------------------------------
# Label/value layouts (Kildare, Westmeath)
# ---------------------------------------------------------------------------

#: A continuation line sits under the value column, within this many points of
#: its left edge (scans are not perfectly aligned).
_VALUE_TOLERANCE = 12.0
#: A gap this wide between two words separates a label from its value.
_LABEL_GAP = 20.0
#: A continuation line is at most this many line pitches below the previous one.
_MAX_PITCH_RATIO = 1.5
#: Stray marks OCR reads from table borders and bullets; never a name.
_NOISE_TOKENS = {"|", "-", "–", "—"}


def _match_label(line: dict, profile: LayoutProfile):
    """``(label, consumed_words)`` when the line starts with a mapped label."""
    text = line["text"]
    for label in profile.labels:
        match = label.match(text)
        if match:
            consumed = len(text[:match.end()].split())
            return label, consumed
    return None


def _is_unmapped_label_line(line: dict, value_left: float) -> bool:
    """A line printed as ``Label   value``: a wide gap that lands in the value column."""
    words = line["words"]
    if words[0]["x0"] >= value_left - _VALUE_TOLERANCE:
        return False
    for index in range(1, len(words)):
        gap = words[index]["x0"] - words[index - 1]["x1"]
        if gap >= _LABEL_GAP and words[index]["x0"] >= value_left - _VALUE_TOLERANCE:
            return True
    return False


def _label_text(line: dict, value_left: float) -> str:
    """The words left of the value column, for an error message."""
    return " ".join(w["text"] for w in line["words"]
                    if w["x1"] < value_left - _VALUE_TOLERANCE)


def _level(line: dict) -> list[dict]:
    """The line's words with ``top`` set to the line's, for the entry splitter.

    A scan is rarely level, so words on one printed line differ in ``top``; the
    splitter reads a change in ``top`` as a new line. Only the geometry is
    levelled, never the text.
    """
    return [{**word, "top": line["top"]} for word in line["words"]]


def _parse_label_value(source: dict, profile: LayoutProfile) -> dict:
    pages = source["pages"]
    if not pages:
        raise UnrecognisedHeaderLayout("the PDF has no pages")
    lines = [line for line in words_to_lines(pages[0]["words"]) if line["words"]]

    first = next((i for i, line in enumerate(lines) if _match_label(line, profile)), None)
    if first is None:
        raise UnrecognisedHeaderLayout(
            f"no attendance label found on page 1 (layout {profile.name})")

    header_text = "\n".join(line["text"] for line in lines[:first])
    linked = link_month_year(source.get("link_text"))
    date_text, meeting_date, venue, start_time, year_source = parse_label_value_date(
        header_text, profile, linked)

    if linked is not None and (linked[0], linked[1]) != (meeting_date.month, meeting_date.year):
        raise MeetingDateMismatch(
            f"header says {date_text!r} but link text says {source.get('link_text')!r}"
        )

    # The value column starts where the first value word of each mapped label line sits.
    starts = []
    for line in lines[first:]:
        found = _match_label(line, profile)
        if found and found[1] < len(line["words"]):
            starts.append(line["words"][found[1]]["x0"])
    if not starts:
        raise UnrecognisedHeaderLayout("no values in the attendance value column")
    starts.sort()
    value_left = starts[len(starts) // 2]

    deltas = [b["top"] - a["top"] for a, b in zip(lines[first:], lines[first + 1:])]
    pitches = [d for d in deltas if d > 8]
    max_gap = _MAX_PITCH_RATIO * (min(pitches) if pitches else 20.0)

    blocks: list[dict] = []
    previous = lines[first]["top"]
    end_index = len(lines)
    for index in range(first, len(lines)):
        line = lines[index]
        found = _match_label(line, profile)
        if found:
            label, consumed = found
            blocks.append({"label": label, "words": _level(line)[consumed:]})
        elif _is_unmapped_label_line(line, value_left):
            raise UnrecognisedHeaderLayout(
                f"unrecognised attendance label {_label_text(line, value_left)!r} "
                f"(layout {profile.name})")
        elif (blocks and line["words"][0]["x0"] >= value_left - _VALUE_TOLERANCE
              and line["top"] - previous <= max_gap):
            blocks[-1]["words"].extend(_level(line))
        else:
            end_index = index
            break
        previous = line["top"]

    entries: list[dict] = []
    ignored_total = 0
    for block in blocks:
        label = block["label"]
        words = []
        for word in block["words"]:
            if word["text"] in _NOISE_TOKENS:
                ignored_total += 1
                continue
            words.append(word)
        parsed, ignored = parse_label_value_entries(words, label.category, profile)
        if label.marker:
            for entry in parsed:
                entry["markers"].append(label.marker)
        entries.extend(parsed)
        ignored_total += ignored

    # None: the attendance block runs to the end of page 1, so the body starts on page 2.
    body_top = lines[end_index]["top"] if end_index < len(lines) else None
    return _build_record(
        source, meeting_date, date_text, venue, start_time, None, entries,
        ignored_total, body_start={"page": 1, "top": body_top}, year_source=year_source)


def _strip_trailing_and(tokens: list[str]) -> list[str]:
    while tokens and tokens[-1].strip(",;.").lower() in ("and", "&"):
        tokens = tokens[:-1]
    return tokens


def _clean_brackets(text: str) -> str:
    """Remove the empty brackets a stripped marker leaves: ``Paul Ward ( )``."""
    return re.sub(r"\s*\(\s*\)", "", text).strip()


def _entry_from(tokens: list[str], category: str, profile: LayoutProfile,
                name_end: int | None = None) -> dict | None:
    """Build one entry from a person's tokens (``name_end``: index where the name stops)."""
    tokens = _strip_trailing_and(tokens)
    if not tokens:
        return None
    raw = " ".join(tokens)
    title = None
    if tokens[0].rstrip(".,") in profile.titles:
        title = tokens[0].rstrip(".,")
        tokens = tokens[1:]
        if name_end is not None:
            name_end -= 1
        # A printed double title ("Mr. Mr. Jonathan Hennessy") is one person.
        while tokens and tokens[0].rstrip(".,") in profile.titles:
            tokens = tokens[1:]
            if name_end is not None:
                name_end -= 1
    if name_end is None:
        name_end = len(tokens)
    name = " ".join(tokens[:name_end]).strip(" ,;.")
    role = " ".join(tokens[name_end:]).strip(" ,;.")
    # "(Chair)" and "(Cathaoirleach)" print a role, never initials, in these layouts.
    paren = name.find("(")
    if paren > 0:
        role = (name[paren:] + " " + role).strip()
        name = name[:paren].strip()
    role, markers = _strip_markers(role)
    name, name_markers = _strip_markers(name)
    markers = markers + name_markers
    role = _clean_brackets(role).strip(" ,;.")
    if re.fullmatch(r"\(([^)]*)\)", role):
        role = role[1:-1].strip()
    name = _clean_brackets(name).strip(" ,;.")
    if not name:
        return None
    return {
        "category": category,
        "printed_name": name,
        "title": title,
        "initials": None,
        "role": role,
        "markers": markers,
        "raw": raw,
    }


def _titled_runs(words: list[dict], profile: LayoutProfile) -> list[list[str]]:
    """Split value words into one token run per person: a title starts a person."""
    runs: list[list[str]] = []
    for word in words:
        token = word["text"]
        if token.rstrip(".,;") in profile.titles and runs and any(
                t.rstrip(".,;") not in profile.titles and t.strip(",;.").lower() not in ("and", "&")
                for t in runs[-1]):
            runs.append([token])
        elif runs:
            runs[-1].append(token)
        else:
            runs.append([token])
    return runs


def _titled_name_end(tokens: list[str], profile: LayoutProfile) -> int:
    """Index into ``tokens`` where the name stops and the role starts."""
    offset = 1 if tokens and tokens[0].rstrip(".,") in profile.titles else 0
    for index, token in enumerate(tokens[offset:]):
        bare = token.strip(",;.")
        if index > 0 and (token.startswith("(") or bare.startswith("A/")
                          or bare in profile.role_words):
            return index + offset
        if token.endswith((",", ";")):
            return index + offset + 1
        if token.endswith(".") and index >= 1 and len(bare) > 2:
            return index + offset + 1
    return len(tokens)


def _split_at_and(tokens: list[str], name_end: int, profile: LayoutProfile) -> list[list[str]]:
    """Split "Mr Cormac Browne and Eamonn Mahoney" into two people.

    Only when "and" sits inside the name span with at least two capitalised
    words on each side and no title follows: the second person is then printed
    without a title, and nothing else in the run can say where they start.
    """
    offset = 1 if tokens and tokens[0].rstrip(".,") in profile.titles else 0
    for index in range(offset + 2, name_end - 2):
        if tokens[index].lower() in ("and", "&"):
            before, after = tokens[offset:index], tokens[index + 1:name_end]
            if (len(before) >= 2 and len(after) >= 2
                    and all(t[:1].isupper() for t in before + after)):
                return [tokens[:index], tokens[index + 1:]]
    return [tokens]


def parse_label_value_entries(words: list[dict], category: str,
                              profile: LayoutProfile) -> tuple[list[dict], int]:
    """Entries for one block of a label/value layout; ``(entries, ignored_count)``."""
    entries: list[dict] = []
    if profile.entries == "titled-run":
        for run in _titled_runs(words, profile):
            for person in _split_at_and(run, _titled_name_end(run, profile), profile):
                entry = _entry_from(person, category, profile,
                                    name_end=_titled_name_end(person, profile))
                if entry:
                    entries.append(entry)
        return entries, 0

    # one-per-line: a new line starts a new person unless it continues the last
    # (starts lower case, or after a comma-ended line).
    lines: list[list[str]] = []
    last_top = None
    for word in words:
        token = word["text"]
        new_line = last_top is None or abs(word["top"] - last_top) > 2
        last_top = word["top"]
        if new_line and lines and token[:1].isupper() and not lines[-1][-1].endswith(","):
            lines.append([token])
        elif lines:
            lines[-1].append(token)
        else:
            lines.append([token])
    for tokens in lines:
        text = " ".join(_strip_trailing_and(tokens))
        comma = text.find(",")
        entry = _entry_from(
            text.split(), category, profile,
            name_end=len(text[:comma].split()) if comma > 0 else None)
        if entry:
            entries.append(entry)
    return entries, 0


def parse_label_value_date(header_text: str, profile: LayoutProfile,
                           linked: tuple[int, int] | None = None
                           ) -> tuple[str, date, str, str | None, str]:
    """``(date_text, date, venue, start_time, year_source)`` from a label/value header.

    The year is the header's. A header that prints day and month but no year
    takes the year from the link text, and only when the link text's month
    agrees with the header's month; otherwise it is ``MeetingDateUnparseable``.
    ``year_source`` is ``header`` or ``link_text``.
    """
    flat = re.sub(r"\s+", " ", header_text).strip()
    match = re.search(profile.date_line, flat, re.IGNORECASE)
    if not match:
        raise MeetingDateUnparseable(
            f"no date line ('held ... <day> <month> <year>') for layout {profile.name} in the header")
    groups = match.groupdict()
    year = groups.get("year")
    year_source = "header"
    if not year:
        month = MONTHS[groups["month"].lower()]
        if linked is None or linked[0] != month:
            raise MeetingDateUnparseable(
                f"the header prints no year and the link text cannot supply it: "
                f"{match.group(0)!r}")
        year, year_source = str(linked[1]), "link_text"
    try:
        meeting_date = date(int(year), MONTHS[groups["month"].lower()], int(groups["day"]))
    except ValueError as exc:
        raise MeetingDateUnparseable(f"invalid header date: {exc}") from exc
    date_text = f"{groups['day']} {groups['month']} {year}"
    venue = re.sub(r"\s+", " ", (groups.get("venue") or "")).strip(" .,;")
    venue = re.sub(r"^(?:in\s+the|in)\s+", "", venue, flags=re.IGNORECASE)
    time = groups.get("time")
    return (date_text, meeting_date, venue,
            (re.sub(r"\s+", " ", time).strip() if time else None), year_source)


def _value_words(lines: list[dict], block_top: float, block_end: float,
                 value_left: float) -> list[dict]:
    """The value-column words in a block's vertical range.

    On the presentations label line, the label itself is skipped so it never
    becomes a presenter name.
    """
    words: list[dict] = []
    for line in lines:
        if not (block_top - 2 <= line["top"] < block_end - 2):
            continue
        line_words = line["words"]
        if line_words and line_words[0]["text"] == "Presentations":
            dash = next((i for i, w in enumerate(line_words) if w["text"] == "-"),
                        len(line_words) - 1)
            line_words = line_words[dash + 1:]
        words.extend(w for w in line_words if w["x0"] >= value_left)
    return words


def run(input_data: dict) -> tuple[list[dict], list[dict]]:
    """Parse every fetched record; withhold both sides of a duplicate meeting."""
    records: list[dict] = []
    errors: list[dict] = []
    by_id: dict[str, list[str]] = {}
    for source in input_data.get("results", []):
        try:
            record = parse_record(source)
        except HeaderParseError as exc:
            errors.append(_error(exc.error_type, str(exc), source))
            continue
        by_id.setdefault(record["meeting_id"], []).append(record["source_url"])
        records.append(record)
        for conflict in record["initials_conflicts"]:
            errors.append(_error(
                "ContradictoryInitials",
                f"initials {conflict['initials']} map to "
                f"{' and '.join(conflict['names'])}",
                source,
            ))

    duplicates = {mid: urls for mid, urls in by_id.items() if len(urls) > 1}
    if duplicates:
        records = [r for r in records if r["meeting_id"] not in duplicates]
        for meeting_id, urls in duplicates.items():
            errors.append({
                "step": "parse_meeting_header",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "DuplicateMeeting",
                "error_message": f"two files resolve to {meeting_id}: {', '.join(urls)}",
                "context": {"meeting_id": meeting_id, "file_urls": urls},
            })
    return records, errors


def _error(error_type: str, message: str, source: dict) -> dict:
    return {
        "step": "parse_meeting_header",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": {
            "committee_id": source.get("committee_id"),
            "public_body_id": source.get("public_body_id"),
            "file_url": source.get("file_url"),
        },
    }

"""Quarantined parser for the Road Safety Strategy Phase 2 Action Plan's
"Primary Actions" section (PDF pages 12-17).

This is the ONE place in extract_actions that opens a PDF. The generic path
is pure JSON-in/JSON-out from clean_text; this format's tables are split
across page boundaries, carry lettered sub-rows, and bleed the Lead/Support
columns into the Action text so badly that clean_text's reflow destroys the
structure before extract_actions sees it. Rather than teach the generic
classifier a document-specific shape, this module re-reads the source PDF
and rebuilds the section from word x-coordinates. Activated only for
documents whose documents.yml entry sets `table_format: rss-primary-actions`.

Contract: `extract_primary_actions(pdf_path, doc_slug) -> (actions, errors)`
where each action dict is the generic extract_actions shape plus an explicit
string `action_number` (`"7A"` for a sub-action, `"8"` for a standalone),
and `columns` carries `No.`, optional `Sub`, `Lead`, `Support Partner(s)`,
and optional `Parent` (the heading text, which is NOT itself emitted as an
action).
"""
import re
from collections import namedtuple
from datetime import datetime, timezone

import pdfplumber

from lib.date_parse import structured_fields
from lib.text_utils import normalize_text

STEP_NAME = "extract_actions"

Word = namedtuple("Word", "text x0 x1 top bottom")

HEADER_CELLS = ("no.", "action", "lead", "support partner(s)")
_HEADER_PREFIX = ("no.", "action", "lead", "support")

_INT_RE = re.compile(r"^\d{1,3}$")
_LETTER_RE = re.compile(r"^([A-D])\.?$")
_CHILD_LEFT_PAD = 28.0          # a child letter sits within this many pt of the action band's left edge
_LINE_TOLERANCE = 3.0          # words within this vertical gap are the same line

# --- assembler geometry (empirical, from the real RSS Phase 2 PDF) ---------
_HEADER_STACK_TOL = 10.0       # "Support"/"Partner(s)" sit ~6.5pt above/below the No./Action/Lead line
_RIBBON_CLEARANCE = 75.0       # drop this many pt above the next header to shed its "Safe System" ribbon
_PAGE_BODY_HARD_BOTTOM = 795.0  # never ingest a word below this (page-number footer lives at ~803)
_MAX_ROW_GAP = 48.0           # a vertical gap wider than this ends the table body (footnotes, whitespace)
_PARENT_SLACK = 15.0          # a non-first parent's number aligns with its 2nd wrapped line; reach up this far
_CHILD_SLACK = 8.0           # a child's Support cell can start ~6.5pt above its letter marker

_DIGITS = "0123456789"


def _norm(text: str) -> str:
    return normalize_text(text, file_type="pdf", for_header=True)


def _header_key(text: str) -> str:
    """Normalised header-cell token, tolerant of a page-label digit glued to
    the left of "No." on odd physical pages ("12No." -> "no")."""
    return _norm(text).rstrip(".").lstrip(_DIGITS)


def _centre(word: Word) -> float:
    return (word.x0 + word.x1) / 2.0


def _error(error_type: str, message: str, context: dict) -> dict:
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type, "error_message": message,
            "context": context}


def _lines(words):
    """Group words into text lines by `top`, each line sorted left-to-right."""
    out = []
    for word in sorted(words, key=lambda w: (round(w.top, 1), w.x0)):
        if out and abs(word.top - out[-1][0]) <= _LINE_TOLERANCE:
            out[-1][1].append(word)
        else:
            out.append((word.top, [word]))
    return [sorted(line, key=lambda w: w.x0) for _, line in out]


def find_header_rows(page_words):
    """Header rows on one page. The real PDF staggers the header across THREE
    text lines: ``No./Action/Lead`` share a ``top`` while ``Support`` sits
    ~6.5pt above and ``Partner(s)`` ~6.5pt below. Detect the core line by the
    ``No.`` + ``Action`` + ``Lead`` triple, then fold in the nearby
    ``Support``/``Partner(s)`` words so :func:`column_bands` still sees four
    centres. Returns a list (top-to-bottom) of header-word lists."""
    rows = []
    for line in _lines(page_words):
        keys = [_header_key(w.text) for w in line]
        if "action" in keys and "lead" in keys and any(k in ("no", "no.") for k in keys):
            core = [w for w in line
                    if _header_key(w.text) in ("no", "no.", "action", "lead")]
            core_top = min(w.top for w in core)
            extra = [w for w in page_words
                     if _header_key(w.text) in ("support", "partner(s)")
                     and abs(w.top - core_top) <= _HEADER_STACK_TOL]
            rows.append(core + extra)
    return rows


def column_bands(header_words):
    """Half-open x ranges keyed no./action/lead/support spanning 0..inf.

    The ``No.`` and ``Action`` headings are centred over narrow-ish columns,
    so they split at the midpoint of their centres. ``Action`` is a very wide
    column whose wrapped text runs right up to the ``Lead`` code, while
    ``Lead`` and ``Support Partner(s)`` codes are left-aligned directly under
    their headings -- so the action/lead and lead/support splits sit at the
    *left edge* (x0) of the ``Lead`` and ``Support`` headings.
    """
    no_c = action_c = None
    lead_x0 = support_x0 = None
    for word in header_words:
        key = _header_key(word.text)
        if key in ("no", "no.") and no_c is None:
            no_c = _centre(word)
        elif key == "action" and action_c is None:
            action_c = _centre(word)
        elif key == "lead":
            lead_x0 = word.x0 if lead_x0 is None else min(lead_x0, word.x0)
        elif key in ("support", "partner(s)"):
            support_x0 = word.x0 if support_x0 is None else min(support_x0, word.x0)

    no_action = (no_c + action_c) / 2.0
    bands = {}
    bands["no."] = (0.0, no_action)
    bands["action"] = (no_action, lead_x0 if lead_x0 is not None else float("inf"))
    if lead_x0 is not None:
        bands["lead"] = (lead_x0, support_x0 if support_x0 is not None else float("inf"))
    if support_x0 is not None:
        bands["support"] = (support_x0, float("inf"))
    return bands


def _in_band(word, band):
    return band[0] <= _centre(word) < band[1]


def marker_kind(word, bands):
    text = word.text.strip()
    if _in_band(word, bands["no."]) and _INT_RE.match(text):
        return ("parent", text)
    if "action" in bands:
        left = bands["action"][0]
        m = _LETTER_RE.match(text)
        if m and word.x0 <= left + _CHILD_LEFT_PAD:
            return ("child", m.group(1))
    return None


def text_in_band(words, band, top, bottom):
    picked = [w for w in words
              if _in_band(w, band) and top <= w.top < bottom]
    picked.sort(key=lambda w: (round(w.top, 1), w.x0))
    joined = " ".join(w.text for w in picked)
    joined = " ".join(joined.split())
    joined = re.sub(r"([a-z])- ([a-z])", r"\1\2", joined)
    return joined


# --------------------------------------------------------------------------
# Assembler: rebuild the 29 tracked Primary Actions from the source PDF.
# --------------------------------------------------------------------------

def _page_words(page):
    return [Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"])
            for w in page.extract_words(use_text_flow=True,
                                        keep_blank_chars=False,
                                        extra_attrs=[])]


def _truncate_at_gap(words, top):
    """The `top` at which the table body ends: the start of the first
    vertical gap wider than ``_MAX_ROW_GAP`` (footnote / trailing whitespace),
    else the bottom-most word."""
    tops = sorted({round(w.top, 1) for w in words if w.top >= top})
    end = top
    for a, b in zip(tops, tops[1:]):
        end = a
        if b - a > _MAX_ROW_GAP:
            return a + 1.0
    return (tops[-1] + 1.0) if tops else top


def _subtables(pdf):
    """One entry per header block on the contiguous run of Primary-Actions
    pages: (page_number, bands, body_words, sorted markers)."""
    out = []
    started = False
    for page in pdf.pages:
        words = _page_words(page)
        headers = find_header_rows(words)
        if not headers:
            if started:
                break            # end of the contiguous Primary-Actions run
            continue
        started = True
        headers = sorted(headers, key=lambda hw: min(w.top for w in hw))
        header_tops = [min(w.top for w in hw) for hw in headers]
        for idx, hw in enumerate(headers):
            bands = column_bands(hw)
            header_top = min(w.top for w in hw)
            # A page-label digit glued to "No." on odd pages carries a garbage
            # bbox (bottom ~812); ignore any implausible glyph height.
            header_bottom = max(
                (w.bottom for w in hw if 0.0 < w.bottom - w.top < 40.0),
                default=header_top + 14.0)
            if idx + 1 < len(headers):
                limit = header_tops[idx + 1] - _RIBBON_CLEARANCE
            else:
                limit = _PAGE_BODY_HARD_BOTTOM
            candidate = [w for w in words
                         if header_bottom - _LINE_TOLERANCE <= w.top < limit]
            body_end = _truncate_at_gap(candidate, header_bottom)
            body = [w for w in candidate if w.top < body_end]
            markers = []
            for w in sorted(body, key=lambda w: (round(w.top, 1), w.x0)):
                kind = marker_kind(w, bands)
                if kind:
                    markers.append((kind[0], kind[1], w.top))
            out.append({"page": page.page_number, "bands": bands,
                        "header_bottom": header_bottom, "body": body,
                        "markers": markers})
    return out


def _row_spans(subtable):
    """Vertical [start, end) span for every marker in one sub-table.

    A parent's / standalone's number aligns with the *second* wrapped line of
    its Action text, so a group opened by a non-first parent must reach up
    ``_PARENT_SLACK`` to catch its first line; the first marker in a
    sub-table starts right below the header. A child's Support cell can sit a
    few points above its letter, hence ``_CHILD_SLACK``.
    """
    markers = subtable["markers"]
    starts = []
    for i, (kind, _value, top) in enumerate(markers):
        if i == 0:
            starts.append(subtable["header_bottom"] - _LINE_TOLERANCE)
        elif kind == "parent":
            starts.append(top - _PARENT_SLACK)
        else:
            starts.append(top - _CHILD_SLACK)
    body_bottom = max((w.bottom for w in subtable["body"]), default=0.0)
    ends = [starts[i + 1] if i + 1 < len(markers) else body_bottom
            for i in range(len(markers))]
    return list(zip(markers, starts, ends))


def _band_text(body, bands, key, start, end, strip_letter=None):
    text = text_in_band(body, bands[key], start, end)
    if strip_letter:
        m = re.match(rf"{strip_letter}\.?\s+", text)
        if m:
            text = text[m.end():]
        elif text[:1] == strip_letter:
            text = text[1:].lstrip(". ")
    return text.strip()


def _action_dict(doc_slug, page, row_counter, *, action_number, text, columns):
    row_counter[page] = row_counter.get(page, 0) + 1
    clean = {k: v for k, v in columns.items() if v not in (None, "")}
    return {
        "action_id": f"p{page:03d}-t01-r{row_counter[page]:02d}",
        "action_number": action_number,
        "action": text,
        "raw_date": "",
        **structured_fields(None),
        "source_page": page,
        "source_table": 1,
        "columns": clean,
    }


def extract_primary_actions(pdf_path, doc_slug):
    """Rebuild the RSS Phase 2 "Primary Actions" section (29 tracked
    sub/standalone actions) from word geometry. Returns ``(actions, errors)``;
    an id that cannot be reconstructed yields an informational error and is
    skipped, never guessed."""
    actions, errors = [], []

    with pdfplumber.open(pdf_path) as pdf:
        subtables = _subtables(pdf)

    if not subtables:
        errors.append(_error(
            "RssHeaderNotFound",
            "No 'No. | Action | Lead | Support Partner(s)' header found in the PDF.",
            {"doc_slug": doc_slug}))
        return actions, errors

    # Flatten to parent-led groups. Each sub-table carries one or more
    # parents; the child markers after a parent (until the next parent) are
    # its sub-actions.
    groups = []
    for st in subtables:
        current = None
        for (kind, value, top), start, end in _row_spans(st):
            if kind == "parent":
                current = {"number": value, "start": start, "end": end,
                           "subtable": st, "children": []}
                groups.append(current)
            elif current is not None:
                current["children"].append({"letter": value, "start": start,
                                            "end": end})
            else:
                errors.append(_error(
                    "RssOrphanChild",
                    "Child marker with no preceding parent; skipped.",
                    {"doc_slug": doc_slug, "letter": value}))

    row_counter = {}
    for g in groups:
        st = g["subtable"]
        body, bands = st["body"], st["bands"]
        number = g["number"]
        parent_text = _band_text(body, bands, "action", g["start"], g["end"])
        parent_lead = _band_text(body, bands, "lead", g["start"], g["end"])
        parent_support = _band_text(body, bands, "support", g["start"], g["end"])

        if g["children"]:
            if not parent_text:
                errors.append(_error(
                    "RssParentTextMissing",
                    "Numbered parent with children has no recoverable Action "
                    "text; children still emitted.",
                    {"doc_slug": doc_slug, "number": number}))
            for child in g["children"]:
                letter = child["letter"]
                text = _band_text(body, bands, "action", child["start"],
                                  child["end"], strip_letter=letter)
                if not text:
                    errors.append(_error(
                        "RssActionTextMissing",
                        "Sub-action Action band is empty; id skipped.",
                        {"doc_slug": doc_slug, "number": f"{number}{letter}"}))
                    continue
                actions.append(_action_dict(
                    doc_slug, st["page"], row_counter,
                    action_number=f"{number}{letter}",
                    text=text,
                    columns={"No.": number, "Sub": letter,
                             "Lead": _band_text(body, bands, "lead",
                                                child["start"], child["end"]),
                             "Support Partner(s)": _band_text(
                                 body, bands, "support",
                                 child["start"], child["end"]),
                             "Parent": parent_text}))
        else:
            if not parent_text:
                errors.append(_error(
                    "RssActionTextMissing",
                    "Standalone numbered action has an empty Action band; "
                    "id skipped.",
                    {"doc_slug": doc_slug, "number": number}))
                continue
            actions.append(_action_dict(
                doc_slug, st["page"], row_counter,
                action_number=number, text=parent_text,
                columns={"No.": number, "Lead": parent_lead,
                         "Support Partner(s)": parent_support}))

    if len(actions) != 29:
        errors.append(_error(
            "RssUnexpectedActionCount",
            "RSS Primary Actions parser produced an unexpected count.",
            {"doc_slug": doc_slug, "actual": len(actions), "expected": 29}))
    return actions, errors

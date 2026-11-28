"""Render each meeting's minutes as verbatim, phone-readable Markdown.

Page furniture (running header, page number, repeated footer) is removed and
counted. Lines broken by the PDF are rejoined; item headings, AOB sections,
bullets and labelled lines start new blocks. Markdown/HTML markup characters
are escaped so the file can be rendered without sanitisation.

The word check is an order-sensitive equality between two independent
readings: the body words read straight from the PDF pages (minus furniture
and bullet glyphs) and the words recovered from the rendered Markdown with
escapes undone. The attendance block is checked separately, so a parsed role
fragment that never reaches the printed text is a ``RenderMismatch`` rather
than a silent loss.

Each committee's layout profile (``layouts.py``) says how its minutes are laid
out. Meath's header table, running header and footer are removed as before. The
scanned layouts (Kildare, Westmeath) declare no furniture: the body is every
line below the attendance block, item headings follow the profile's forms, and
the source words are the OCR (or text-layer) words of each page in reading
order, so "verbatim" means verbatim to the text the ingestion step read.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from steps.parse_meeting_header.header import words_to_lines
from steps.parse_meeting_header.layouts import LayoutProfile, profile_for

STEP_NAME = "render_spc_minutes"

_ITEM_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")
_AOB_RE = re.compile(r"^[^\w]*AOB\s*$", re.IGNORECASE)
# Meath's declared furniture (layouts.py); the scanned layouts declare none.
_MEATH_FURNITURE = dict(profile_for("meath-table").furniture)
_PAGE_RE = re.compile(_MEATH_FURNITURE["page_number"], re.IGNORECASE)
_BULLET_GLYPHS = ("•", "\uf071")
_LABELLED_PREFIXES = ("Proposed by", "Seconded by", "Meeting ended")
_MINUTES_APPROVAL_RE = re.compile(r"^Minutes of (the )?previous meeting\b", re.IGNORECASE)
_MINUTES_ITEM_RE = re.compile(r"^Minutes\b", re.IGNORECASE)
_RUNNING_HEADER = _MEATH_FURNITURE["running_header"].strip("^$")
_ANCHOR_RE = re.compile(r"\s*\{#[^}]*\}\s*$")

#: A line repeated across pages is furniture only when it sits at the page
#: edge on every occurrence. A body line can repeat ("Noted.") without being
#: page furniture, so position, not frequency alone, decides.
_TOP_BAND = 0.02
_BOTTOM_BAND = 0.95
_FOOTER_RE = re.compile(_MEATH_FURNITURE["footer"], re.IGNORECASE)

_ESCAPE_CHARS = "\\`*_{}[]<>#|&"


class RenderError(ValueError):
    error_type = "RenderError"


class UnrecognisedBodyLayout(RenderError):
    error_type = "UnrecognisedBodyLayout"


class RenderMismatch(RenderError):
    error_type = "RenderMismatch"


class UnrecognisedFurniture(RenderError):
    error_type = "UnrecognisedFurniture"


# ---------------------------------------------------------------------------
# Furniture and source lines
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page_span(lines: list[dict]) -> tuple[float, float]:
    tops = [line["top"] for line in lines]
    if not tops:
        return 0.0, 1.0
    lowest, highest = min(tops), max(tops)
    return lowest, (highest - lowest) or 1.0


def detect_furniture(pages: list[dict]) -> tuple[set[str], Counter]:
    """Texts repeated at a page edge, on enough pages to be running furniture.

    The edge requirement keeps a genuine body line that repeats on several
    pages ("Noted.") in the body; only running headers, footers and page
    numbers sit at the top or bottom of every page they appear on. A two-page
    document needs both pages, not three, so its footer is still removed; a
    single-page document keeps everything, because frequency alone cannot
    distinguish a footer from the body.
    """
    threshold = 2 if len(pages) == 2 else 3
    pages_with = Counter()
    occurrences = Counter()
    positions: dict[str, list[float]] = defaultdict(list)
    for page in pages:
        seen = set()
        lowest, span = _page_span(page["lines"])
        for line in page["lines"]:
            text = _normalise(line["text"])
            if not text:
                continue
            occurrences[text] += 1
            positions[text].append((line["top"] - lowest) / span)
            if text not in seen:
                pages_with[text] += 1
                seen.add(text)
    furniture = {
        text for text, count in pages_with.items()
        if count >= threshold and all(
            fraction <= _TOP_BAND or fraction >= _BOTTOM_BAND
            for fraction in positions[text]
        )
    }
    return furniture, occurrences


def _furniture_kind(text: str) -> str:
    if text == _RUNNING_HEADER:
        return "running_header"
    if _FOOTER_RE.search(text):
        return "footer"
    return "unrecognised"


def _body_start(first_page_lines: list[dict]) -> int:
    """Index of the first agenda item on page 1, after the table header."""
    header_index = next(
        (i for i, line in enumerate(first_page_lines)
         if line["text"].strip().startswith("Item")),
        None,
    )
    if header_index is None:
        raise UnrecognisedBodyLayout("no 'Item' table header on page 1")
    # The table header ("Item" / "Item Discussion / Action") is not minutes
    # text; the body starts with the first agenda item.
    body_start = header_index + 1
    while (body_start < len(first_page_lines)
           and first_page_lines[body_start]["text"].strip().startswith("Item Discussion")):
        body_start += 1
    return body_start


def _profile(record: dict) -> LayoutProfile:
    return profile_for(record.get("layout") or "meath-table")


def _label_value_page_lines(record: dict) -> list[tuple[int, dict]]:
    """``(page, line)`` for every body line of a label/value layout.

    The body is everything below the attendance block on page 1 (the parse
    step records where that block ends) and every line of the later pages.
    Skipped pages have no words, so they contribute no lines.
    """
    body_start = record.get("body_start")
    if not body_start:
        raise UnrecognisedBodyLayout("the meeting record has no body_start from the header parse")
    lines: list[tuple[int, dict]] = []
    for page in record["pages"]:
        for line in _lines(page):
            if page["page"] == body_start["page"] and (
                    body_start["top"] is None or line["top"] < body_start["top"] - 0.01):
                continue
            if page["page"] < body_start["page"]:
                continue
            lines.append((page["page"], line))
    return lines


def body_source_lines(record: dict) -> tuple[list[dict], dict]:
    """The body lines after the attendance table, furniture removed and counted."""
    if _profile(record).routine == "label-value":
        # These layouts declare no page furniture, so nothing is removed.
        lines = [{"text": line["text"], "page": page}
                 for page, line in _label_value_page_lines(record)]
        return lines, {"total": 0, "page_numbers": 0, "by_text": []}
    pages = record["pages"]
    page_lines = [
        {"page": index + 1,
         "lines": [{"text": line["text"], "top": line["top"]} for line in _lines(page)]}
        for index, page in enumerate(pages)
    ]
    furniture, occurrences = detect_furniture(page_lines)

    first_page_lines = page_lines[0]["lines"] if page_lines else []
    body_start = _body_start(first_page_lines)

    removed = Counter()
    page_numbers = 0
    body: list[dict] = []
    for page_index, page in enumerate(page_lines):
        lines = page["lines"]
        for line_index, line in enumerate(lines):
            text = line["text"]
            normalised = _normalise(text)
            if page_index == 0 and line_index < body_start:
                # The page-1 header block above the attendance table is not
                # body text; its furniture is still counted as removed.
                if _PAGE_RE.match(normalised):
                    page_numbers += 1
                elif normalised in furniture:
                    removed[normalised] += 1
                continue
            if _PAGE_RE.match(normalised):
                page_numbers += 1
                continue
            if normalised in furniture:
                removed[normalised] += 1
                continue
            body.append({"text": text, "page": page["page"]})

    stats = {
        "total": sum(removed.values()) + page_numbers,
        "page_numbers": page_numbers,
        "by_text": [
            {"text": text, "count": count, "kind": _furniture_kind(text)}
            for text, count in sorted(removed.items())
        ],
    }
    unrecognised = [entry["text"] for entry in stats["by_text"]
                    if entry["kind"] == "unrecognised"]
    if unrecognised:
        raise UnrecognisedFurniture(
            "removed repeating page-edge line(s) that are neither the running "
            "header nor a recognisable footer: " + "; ".join(unrecognised)
        )
    return body, stats


def source_body_words(record: dict) -> list[str]:
    """The body words read directly from the PDF pages.

    Deliberately independent of ``body_source_lines`` and ``segment_blocks``:
    a lost or reordered block, an over-eager page-1 header cut or an escaping
    bug shows up as a mismatch instead of being compared with itself. The
    furniture set itself is position-limited by ``detect_furniture`` so a body
    line that merely repeats cannot be folded into it.
    """
    if _profile(record).routine == "label-value":
        words: list[str] = []
        body_start = record.get("body_start")
        for page in record["pages"]:
            if body_start and page["page"] < body_start["page"]:
                continue
            for line in _lines(page):
                if (body_start and page["page"] == body_start["page"]
                        and (body_start["top"] is None
                             or line["top"] < body_start["top"] - 0.01)):
                    continue
                words.extend(token for token in line["text"].split()
                             if token not in _BULLET_GLYPHS)
        return words
    page_lines = [
        {"page": index + 1, "lines": _lines(page)}
        for index, page in enumerate(record["pages"])
    ]
    furniture, _ = detect_furniture(page_lines)
    body_start = _body_start(page_lines[0]["lines"] if page_lines else [])

    words: list[str] = []
    for page_index, page in enumerate(page_lines):
        for line_index, line in enumerate(page["lines"]):
            text = line["text"]
            normalised = _normalise(text)
            if page_index == 0 and line_index < body_start:
                continue
            if _PAGE_RE.match(normalised) or normalised in furniture:
                continue
            words.extend(token for token in text.split()
                         if token not in _BULLET_GLYPHS)
    return words


def _lines(page: dict) -> list[dict]:
    """Physical lines of a page: text-layer words grouped by ``top``, OCR words
    by Tesseract's own line numbers (see ``words_to_lines``)."""
    return words_to_lines(page["words"])


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def _starts_with_bullet(text: str) -> bool:
    first = text.strip().split(" ", 1)[0]
    return first in _BULLET_GLYPHS


def _strip_bullet(text: str) -> str:
    stripped = text.strip()
    for glyph in _BULLET_GLYPHS:
        if stripped.startswith(glyph):
            return stripped[len(glyph):].strip()
    return stripped


def _item_heading(text: str, profile: LayoutProfile | None = None) -> tuple[str, str, str] | None:
    """``(number, title, printed_line)`` when the line is an item heading.

    Meath's headings are "4.0 Title"; a label/value profile lists its own forms
    ("Item 2 — Title", "Item 2: Title"), compared case-insensitively.
    """
    text = text.strip()
    if profile is not None and profile.routine == "label-value":
        for pattern in profile.item_headings:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1), match.group(2).strip(), _normalise(text)
        return None
    match = _ITEM_RE.match(text)
    if not match:
        return None
    number, title = match.group(1), match.group(2).strip()
    return number, title, f"{number} {title}"


def segment_blocks(body_lines: list[dict],
                   profile: LayoutProfile | None = None) -> tuple[list[dict], list[dict]]:
    """Group body lines into blocks and numbered items.

    Returns ``(blocks, items)``. Blocks carry a ``kind``
    (``heading``/``aob``/``bullet``/``labelled``/``paragraph``); items carry
    their printed number, title and plain text.
    """
    blocks: list[dict] = []
    items: list[dict] = []
    current_item: dict | None = None

    def add_block(kind: str, text: str) -> dict:
        block = {"kind": kind, "text": text}
        blocks.append(block)
        if current_item is not None:
            current_item["blocks"].append(block)
        return block

    for line in body_lines:
        text = line["text"].strip()
        if not text:
            continue
        if _starts_with_bullet(text):
            add_block("bullet", _strip_bullet(text))
            continue
        heading = _item_heading(text, profile)
        if heading:
            number, title, printed = heading
            item_key = "item-" + number.replace(".", "-")
            if any(item["item_key"] == item_key for item in items):
                suffix = 2
                while any(item["item_key"] == f"{item_key}-{suffix}" for item in items):
                    suffix += 1
                item_key = f"{item_key}-{suffix}"
            current_item = {
                "item_key": item_key,
                "number": number,
                "title": title,
                "blocks": [],
                "is_minutes_approval": bool(
                    (_MINUTES_ITEM_RE if profile is not None and profile.routine == "label-value"
                     else _MINUTES_APPROVAL_RE).match(title)),
            }
            items.append(current_item)
            block = {"kind": "heading", "number": number, "title": title,
                     "item_key": item_key, "text": printed, "printed": printed,
                     "printed_form": bool(profile is not None and profile.routine == "label-value")}
            blocks.append(block)
            current_item["blocks"].append(block)
            continue
        if _AOB_RE.match(text):
            add_block("aob", "AOB")
            continue
        if text.startswith(_LABELLED_PREFIXES):
            add_block("labelled", text)
            continue
        if blocks and blocks[-1]["kind"] in ("paragraph", "bullet", "labelled"):
            blocks[-1]["text"] = blocks[-1]["text"] + " " + text
        else:
            add_block("paragraph", text)

    for item in items:
        item["text"] = " ".join(block["text"] for block in item["blocks"])
    return blocks, items


def unescape_inline(text: str) -> str:
    """Undo ``escape_inline`` so rendered words can be compared with source."""
    return re.sub(r"\\(.)", r"\1", text)


def markdown_words(markdown: str, *, drop_headings: bool = False) -> list[str]:
    """Words of a rendered Markdown fragment, with markup and escapes undone.

    ``drop_headings`` is used for the attendance block, whose category
    headings are generated text rather than printed names.
    """
    words: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("## ", "### ")):
            if drop_headings:
                continue
            line = _ANCHOR_RE.sub("", line[3:])
        elif line.startswith("- "):
            line = line[2:]
        words.extend(unescape_inline(line).split())
    return words


def check_attendance(record: dict) -> None:
    """Prove the rendered attendance keeps every printed name and role word.

    The renderer writes each entry's ``raw`` text, so role words parsed out of
    a separate printed fragment must have been folded back into ``raw``;
    otherwise the verbatim minutes would silently drop them.
    """
    if not record.get("attendance_published", True):
        return
    expected: list[str] = []
    # The render lists entries by category, in the layout's heading order, so the
    # expected words follow that grouping (a layout may print Apologies before
    # Officials); within a category the printed order is kept.
    order = {category: index for index, (category, _) in enumerate(_attendance_labels(record))}
    entries = sorted(record.get("printed_attendance", []),
                     key=lambda e: order.get(e["category"], len(order)))
    for entry in entries:
        raw = (entry.get("raw") or entry["printed_name"]).strip().strip(",;.")
        role = (entry.get("role") or "").strip()
        # Compare as substrings: the printed text may glue the role to a
        # bracket or dash ("(MD’A)Climate", "-Senior Engineer-"), and a
        # trailing comma must not count as a different word.
        missing = [token for token in role.split() if token not in raw]
        if missing:
            raise RenderMismatch(
                f"attendance entry {entry['printed_name']!r}: role text "
                f"{' '.join(missing)!r} is not in the printed text {raw!r}"
            )
        expected.extend(raw.split())
    check_words(expected, markdown_words(render_attendance(record),
                                          drop_headings=True))


def check_words(source: list[str], rendered: list[str]) -> None:
    for index, (left, right) in enumerate(zip(source, rendered)):
        if left != right:
            raise RenderMismatch(
                f"first difference at word {index}: source {left!r}, rendered {right!r}"
            )
    if len(source) != len(rendered):
        index = min(len(source), len(rendered))
        raise RenderMismatch(
            f"word count differs at position {index}: source has {len(source)} words, "
            f"rendered has {len(rendered)}"
        )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def escape_inline(text: str) -> str:
    """Escape characters Markdown or HTML would read as markup."""
    escaped = "".join(f"\\{char}" if char in _ESCAPE_CHARS else char for char in text)
    return re.sub(r"^([-+])", r"\\\1", escaped)


def _yaml_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    import json

    return json.dumps(str(value), ensure_ascii=False)


def front_matter(record: dict) -> str:
    fields = [
        ("meeting_id", record["meeting_id"]),
        ("committee_id", record["committee_id"]),
        ("committee_name", record["committee_name"]),
        ("public_body_id", record["public_body_id"]),
        ("meeting_date", record["meeting_date"]),
        ("venue", record.get("venue")),
        ("start_time", record.get("start_time")),
        ("end_time", record.get("end_time")),
        ("source_url", record["source_url"]),
        ("source_sha256", record["source_sha256"]),
        ("text_source", record.get("text_source") or "text_layer"),
    ]
    if record.get("ocr_engine"):
        fields.append(("ocr_engine", record["ocr_engine"]))
    return "---\n" + "\n".join(f"{key}: {_yaml_value(value)}" for key, value in fields) + "\n---\n"


_ATTENDANCE_LABELS = [
    ("councillors", "Councillors"),
    ("sectoral_representatives", "Sectoral Representatives"),
    ("apologies", "Absent / Apologies"),
    ("officials", "Officials"),
    ("presenters", "Presenters"),
]


def _attendance_labels(record: dict) -> list[tuple[str, str]]:
    """The attendance headings: the layout's printed labels, else Meath's."""
    headings = _profile(record).attendance_headings
    return list(headings) if headings else _ATTENDANCE_LABELS


def render_attendance(record: dict) -> str:
    entries = record.get("printed_attendance", [])
    lines = ["## Attendance", ""]
    if not record.get("attendance_published", True):
        lines.append("_Attendance is withheld pending review of an unresolved name._")
        lines.append("")
    for category, label in _attendance_labels(record):
        group = [entry for entry in entries if entry["category"] == category]
        if not group:
            continue
        lines.extend([f"### {label}", ""])
        for entry in group:
            text = entry.get("raw") or entry["printed_name"]
            text = text.strip().strip(",;.")
            lines.append(f"- {escape_inline(text)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_body(blocks: list[dict]) -> str:
    parts: list[str] = []
    anchor = 0
    for block in blocks:
        kind = block["kind"]
        if kind == "heading":
            heading = (escape_inline(block["printed"]) if block.get("printed_form")
                       else f"{escape_inline(block['number'])} {escape_inline(block['title'])}")
            parts.append(f"## {heading} {{#{block['item_key']}}}")
        elif kind == "aob":
            anchor += 1
            suffix = "" if anchor == 1 else f"-{anchor}"
            parts.append(f"## AOB {{#aob{suffix}}}")
        elif kind == "bullet":
            parts.append(f"- {escape_inline(block['text'])}")
        else:
            parts.append(escape_inline(block["text"]))
    return "\n\n".join(parts) + "\n"


def render_meeting(record: dict) -> dict:
    body_lines, furniture = body_source_lines(record)
    blocks, items = segment_blocks(body_lines, _profile(record))
    body_markdown = render_body(blocks)
    # Both sides of the check are independent of the renderer's own line
    # selection: the source words come straight from the PDF, the rendered
    # words from the final Markdown with escapes undone.
    check_words(source_body_words(record), markdown_words(body_markdown))
    check_attendance(record)

    markdown = (
        front_matter(record)
        + "\n"
        + f"# {escape_inline(record['committee_name'])}\n\n"
        + f"**{escape_inline(record['date_text'])}**, {escape_inline(record.get('venue') or '')}"
        + (f". {escape_inline(record['start_time'].rstrip('.'))}"
           if record.get("start_time") else "")
        + (f" – {escape_inline(record['end_time'])}" if record.get("end_time") else "")
        + ".\n\n"
        + render_attendance(record)
        + "\n## Agenda items\n\n"
        + body_markdown
    )

    result = {key: value for key, value in record.items() if key != "pages"}
    result["markdown"] = markdown
    result["items"] = items
    result["furniture_removed"] = furniture
    result["word_check"] = "passed"
    return result


def run(input_data: dict) -> tuple[list[dict], list[dict]]:
    results: list[dict] = []
    errors: list[dict] = []
    for record in input_data.get("results", []):
        try:
            results.append(render_meeting(record))
        except RenderError as exc:
            errors.append({
                "step": STEP_NAME,
                "timestamp": _now(),
                "error_type": exc.error_type,
                "error_message": str(exc),
                "context": {
                    "meeting_id": record.get("meeting_id"),
                    "public_body_id": record.get("public_body_id"),
                    "file_url": record.get("source_url"),
                },
            })
    return results, errors


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()

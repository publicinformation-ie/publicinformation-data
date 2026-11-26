"""Render each meeting's minutes as verbatim, phone-readable Markdown.

Page furniture (running header, page number, repeated footer) is removed and
counted. Lines broken by the PDF are rejoined; item headings, AOB sections,
bullets and labelled lines start new blocks. Markdown/HTML markup characters
are escaped so the file can be rendered without sanitisation.

The word check is an order-sensitive equality: the source body words (minus
furniture and bullet glyphs) must equal the rendered body words (markup
stripped). A single lost, added or reordered word is a ``RenderMismatch``.
"""
from __future__ import annotations

import re
from collections import Counter

STEP_NAME = "render_spc_minutes"

_ITEM_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")
_AOB_RE = re.compile(r"^[^\w]*AOB\s*$", re.IGNORECASE)
_PAGE_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.IGNORECASE)
_BULLET_GLYPHS = ("•", "\uf071")
_LABELLED_PREFIXES = ("Proposed by", "Seconded by", "Meeting ended")
_MINUTES_APPROVAL_RE = re.compile(r"^Minutes of (the )?previous meeting\b", re.IGNORECASE)
_RUNNING_HEADER = "Miontuairiscí/Meeting Minutes"

_ESCAPE_CHARS = "\\`*_{}[]<>#|&"


class RenderError(ValueError):
    error_type = "RenderError"


class UnrecognisedBodyLayout(RenderError):
    error_type = "UnrecognisedBodyLayout"


class RenderMismatch(RenderError):
    error_type = "RenderMismatch"


# ---------------------------------------------------------------------------
# Furniture and source lines
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def detect_furniture(pages: list[dict]) -> tuple[set[str], Counter]:
    """Texts that repeat on at least three pages, plus page-number lines."""
    pages_with = Counter()
    occurrences = Counter()
    for page in pages:
        seen = set()
        for line in page["lines"]:
            text = _normalise(line["text"])
            occurrences[text] += 1
            if text not in seen:
                pages_with[text] += 1
                seen.add(text)
    furniture = {text for text, count in pages_with.items() if count >= 3}
    return furniture, occurrences


def body_source_lines(record: dict) -> tuple[list[dict], dict]:
    """The body lines after the attendance table, furniture removed and counted."""
    pages = record["pages"]
    page_lines = [
        {"page": index + 1,
         "lines": [{"text": line["text"], "top": line["top"]} for line in _lines(page)]}
        for index, page in enumerate(pages)
    ]
    furniture, occurrences = detect_furniture(page_lines)

    first_page_lines = page_lines[0]["lines"] if page_lines else []
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
            {"text": text, "count": count,
             "kind": "running_header" if text == _RUNNING_HEADER else "footer"}
            for text, count in sorted(removed.items())
        ],
    }
    return body, stats


def _lines(page: dict) -> list[dict]:
    """Physical lines of a page (words grouped by top)."""
    lines: list[dict] = []
    for word in sorted(page["words"], key=lambda w: (round(w["top"], 1), w["x0"])):
        if lines and abs(word["top"] - lines[-1]["top"]) <= 2.0:
            lines[-1]["words"].append(word)
        else:
            lines.append({"top": word["top"], "words": [word]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
        line["text"] = " ".join(w["text"] for w in line["words"])
    return lines


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


def _item_heading(text: str) -> tuple[str, str] | None:
    match = _ITEM_RE.match(text.strip())
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def segment_blocks(body_lines: list[dict]) -> tuple[list[dict], list[dict]]:
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
        heading = _item_heading(text)
        if heading:
            number, title = heading
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
                "is_minutes_approval": bool(_MINUTES_APPROVAL_RE.match(title)),
            }
            items.append(current_item)
            block = {"kind": "heading", "number": number, "title": title,
                     "item_key": item_key, "text": f"{number} {title}"}
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


def source_words(body_lines: list[dict]) -> list[str]:
    """Whitespace tokens of the body, without furniture or bullet glyphs."""
    words: list[str] = []
    for line in body_lines:
        for token in line["text"].split():
            if token in _BULLET_GLYPHS:
                continue
            words.append(token)
    return words


def rendered_words(blocks: list[dict]) -> list[str]:
    words: list[str] = []
    for block in blocks:
        words.extend(block["text"].split())
    return words


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
    ]
    return "---\n" + "\n".join(f"{key}: {_yaml_value(value)}" for key, value in fields) + "\n---\n"


_ATTENDANCE_LABELS = [
    ("councillors", "Councillors"),
    ("sectoral_representatives", "Sectoral Representatives"),
    ("apologies", "Absent / Apologies"),
    ("officials", "Officials"),
    ("presenters", "Presenters"),
]


def render_attendance(record: dict) -> str:
    entries = record.get("printed_attendance", [])
    lines = ["## Attendance", ""]
    if not record.get("attendance_published", True):
        lines.append("_Attendance is withheld pending review of an unresolved name._")
        lines.append("")
    for category, label in _ATTENDANCE_LABELS:
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
            parts.append(
                f"## {escape_inline(block['number'])} {escape_inline(block['title'])} "
                f"{{#{block['item_key']}}}"
            )
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
    blocks, items = segment_blocks(body_lines)
    check_words(source_words(body_lines), rendered_words(blocks))

    markdown = (
        front_matter(record)
        + "\n"
        + f"# {escape_inline(record['committee_name'])}\n\n"
        + f"**{escape_inline(record['date_text'])}**, {escape_inline(record.get('venue') or '')}"
        + (f". {escape_inline(record['start_time'])}" if record.get("start_time") else "")
        + (f" – {escape_inline(record['end_time'])}" if record.get("end_time") else "")
        + ".\n\n"
        + render_attendance(record)
        + "\n## Agenda items\n\n"
        + render_body(blocks)
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

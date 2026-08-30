#!/usr/bin/env python3
"""Step: extract_action_status — read each progress report's annex tables and
turn every row into one dated status observation of a plan action.

`extract_actions` records what a plan *committed to*. This step records what
the department later *reported* about each of those commitments: a status, a
re-stated deadline, and the progress narrative, stamped with the report's own
publication date. Together they are what makes slippage visible.

Like `extract_actions` this is pure JSON in / JSON out — no PDF is opened, no
OCR, no LLM — so every function here is testable against hand-written table
fixtures in milliseconds.

Two report layouts exist in the corpus and they are incompatible:

  * **Format A** (Year One, Year Two) — 7 columns, status in its own `Status`
    column, plus an `ASI` column (Avoid / Shift / Improve) that exists only in
    these two reports.
  * **Format B** (Year Three, Final) — 5 columns, no status column: the annex
    is segmented into `Complete` / `Modified` / `Delayed` sections and a row's
    status is the section it sits under.

Detection is explicit and fail-closed, and that matters more than it looks:
running the Format B reader over a Format A report would find no recognised
annex heading anywhere and emit `UnknownStatusSection` for every table — a
silent 100% data loss indistinguishable from "this document contains no
actions". Fail-closed stops us publishing wrong data; only the format detector
stops us publishing nothing and not noticing.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.date_parse import parse_date
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
from lib.text_utils import normalize_text

STEP_NAME = "extract_action_status"

# Header shapes, normalized (lowercased, trailing punctuation stripped). Exact
# tuples, not a keyword search: a header that has drifted is a document we do
# not yet know how to read, and must say so rather than be half-understood.
FORMAT_A_HEADER = ("no", "action", "proposed output", "smp deadline",
                   "status", "progress", "asi")
FORMAT_B_HEADER = ("no", "action", "proposed output", "smp deadline", "progress")

# Column positions per format.
_COLUMNS = {
    "A": {"number": 0, "action": 1, "output": 2, "deadline": 3,
          "status": 4, "progress": 5, "asi": 6},
    "B": {"number": 0, "action": 1, "output": 2, "deadline": 3,
          "status": None, "progress": 4, "asi": None},
}

# Raw status text (normalized, lowercased) -> vocabulary notation. Exactly the
# five terms in public/vocabularies/action-status.csv and no synonyms: an
# unmappable value is a reviewable error, never a nearest match.
STATUS_VOCABULARY = {
    "complete": "Complete",
    "on schedule": "OnSchedule",
    "delayed": "Delayed",
    "ongoing": "Ongoing",
    "modified": "Modified",
}

# Words that identify a Format B annex status section, keyed by the notation
# they imply.
_SECTION_KEYWORDS = {"complete": "Complete", "modified": "Modified",
                     "delayed": "Delayed"}


def _normalize_cell(value):
    return normalize_text(value, file_type="pdf")


def _normalize_header(value):
    return normalize_text(value, file_type="pdf", for_header=True)


def _cell_at(cells, index):
    if index is None or index >= len(cells):
        return ""
    return cells[index]


def _error_dict(error_type: str, message: str, context: dict) -> dict:
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": message,
            "context": context}


# --------------------------------------------------------------------------
# Format detection
# --------------------------------------------------------------------------


def detect_format(header_cells):
    """`"A"`, `"B"`, or None for a header matching neither layout."""
    key = tuple(c for c in (_normalize_header(v) for v in header_cells) if c)
    if key == FORMAT_A_HEADER:
        return "A"
    if key == FORMAT_B_HEADER:
        return "B"
    return None


def _header_index(rows):
    for index, row in enumerate(rows):
        if any(_normalize_cell(c) for c in row):
            return index
    return None


# --------------------------------------------------------------------------
# Format B: page -> status
# --------------------------------------------------------------------------


def status_sections(clean_record) -> dict:
    """Map page number -> status notation, read from standalone
    Complete/Modified/Delayed paragraphs in clean_text.

    detect_structure's node tree is not a reliable source for this: across
    the real corpus, the annex's own PDF outline bookmark is sometimes one
    entry for the whole thing (Year Three) and sometimes several oddly-scoped
    ones that don't reach the sections they should (the Final report bookmarks
    "Complete"/"Modified"/"Delayed" but only for their first page each, while
    the annex tables they govern run for another thirty pages). The label
    itself is more reliable: it is always its own one-word paragraph block
    immediately before the table(s) it governs, and the status it implies
    carries forward page to page until the next such label — a document-wide
    scan, not restricted to any detected section, because a table this step
    already recognises as one of the two known annex layouts (Format A or B)
    is never confused with an unrelated same-shaped table elsewhere; any
    earlier, unrelated appearance of the same one-word label is harmless
    because there is nothing recognised to attach it to yet. A page with two
    labels (rare — a status changes mid-page) keeps only the last, which is
    the correct forward-carried state by the time the page ends.
    """
    mapping = {}
    current = None
    pages = sorted(clean_record.get("pages") or [], key=lambda p: int(p.get("number", 0)))
    for page in pages:
        page_number = int(page.get("number", 0))
        for block in page.get("blocks") or []:
            if block.get("type") != "paragraph":
                continue
            text = _normalize_header(block.get("text") or "")
            if text in _SECTION_KEYWORDS:
                current = _SECTION_KEYWORDS[text]
        if current is not None:
            mapping[page_number] = current
    return mapping


# --------------------------------------------------------------------------
# Status normalisation
# --------------------------------------------------------------------------


def normalize_status(raw):
    """Vocabulary notation for a raw status cell, or None if unmappable.

    Values are inconsistent across the series — casing varies and line breaks
    appear mid-value (`"On\\nschedule"`) — so normalize through the shared
    text normalizer before the lookup.
    """
    text = _normalize_cell(raw or "")
    return STATUS_VOCABULARY.get(" ".join(text.lower().split()))


# --------------------------------------------------------------------------
# Row extraction
# --------------------------------------------------------------------------


def _blank_observation(page_number, table_index, row_number):
    return {"action_number": None, "action_text": "", "proposed_output": "",
            "reported_deadline_raw": "", "reported_deadline_start": None,
            "reported_deadline_end": None, "reported_deadline_precision": None,
            "progress_text": "", "status": None, "asi": None,
            "source_page": page_number,
            "source_ref": f"p{page_number:03d}-t{table_index + 1:02d}-r{row_number:02d}"}


_APPENDABLE = {"action": "action_text", "output": "proposed_output",
               "progress": "progress_text"}


def extract_table(rows, page_number, table_index, fmt, section_status,
                  doc_slug, errors) -> list:
    """Every observation in one annex table.

    Annex tables split across page boundaries and the header repeats as page
    furniture, so a page yields a fragment: a row with an empty `No.` cell
    continues the previous row and its text is appended. A continuation with no
    preceding row is `ContinuationRowOrphaned` — skipped, never attached to a
    row from a different table.
    """
    columns = _COLUMNS[fmt]
    header_index = _header_index(rows)
    if header_index is None:
        return []

    observations = []
    row_number = 0

    for row in rows[header_index + 1:]:
        cells = [_normalize_cell(c) for c in row]
        if not any(cells):
            continue
        if detect_format(row) is not None:
            continue                      # repeated header as page furniture

        number_cell = _cell_at(cells, columns["number"])
        if not number_cell:
            if not observations:
                errors.append(_error_dict(
                    "ContinuationRowOrphaned",
                    "Row has an empty No. cell but no preceding row in this "
                    "table to continue; skipped.",
                    {"doc_slug": doc_slug, "page": page_number,
                     "table": table_index}))
                continue
            previous = observations[-1]
            for key, field in _APPENDABLE.items():
                text = _cell_at(cells, columns[key])
                if text:
                    previous[field] = f"{previous[field]} {text}".strip()
            continue

        row_number += 1
        observation = _blank_observation(page_number, table_index, row_number)

        digits = "".join(ch for ch in number_cell if ch.isdigit())
        if not digits:
            errors.append(_error_dict(
                "UnresolvedActionNumber",
                f"No. cell {number_cell!r} contains no digits; observation "
                f"skipped rather than attached to a neighbouring action.",
                {"doc_slug": doc_slug, "page": page_number,
                 "table": table_index, "row": row_number}))
            continue
        observation["action_number"] = int(digits)

        raw_status = (section_status if fmt == "B"
                      else _cell_at(cells, columns["status"]))
        status = section_status if fmt == "B" else normalize_status(raw_status)
        if status is None:
            errors.append(_error_dict(
                "UnknownStatusValue",
                f"Status {raw_status!r} is not in the action-status "
                f"vocabulary; observation skipped, never coerced.",
                {"doc_slug": doc_slug, "page": page_number,
                 "table": table_index, "row": row_number,
                 "action_number": observation["action_number"],
                 "raw_status": raw_status}))
            continue
        observation["status"] = status

        observation["action_text"] = _cell_at(cells, columns["action"])
        observation["proposed_output"] = _cell_at(cells, columns["output"])
        observation["progress_text"] = _cell_at(cells, columns["progress"])
        if columns["asi"] is not None:
            observation["asi"] = _cell_at(cells, columns["asi"]) or None

        raw_deadline = _cell_at(cells, columns["deadline"])
        observation["reported_deadline_raw"] = raw_deadline
        parsed = parse_date(raw_deadline) if raw_deadline else None
        if raw_deadline and parsed is None:
            errors.append(_error_dict(
                "DateParseError",
                "Reported deadline is non-empty but matched no supported date "
                "pattern; kept raw with structured fields null.",
                {"doc_slug": doc_slug, "page": page_number,
                 "table": table_index, "row": row_number,
                 "raw_deadline": raw_deadline}))
        if parsed is not None:
            observation["reported_deadline_start"] = parsed["start"]
            observation["reported_deadline_end"] = parsed["end"]
            observation["reported_deadline_precision"] = parsed["precision"]

        observations.append(observation)

    return observations


# --------------------------------------------------------------------------
# Per-document extraction
# --------------------------------------------------------------------------


def _tables(clean_record):
    for page in clean_record.get("pages") or []:
        page_number = int(page.get("number", 0))
        for block in page.get("blocks") or []:
            if block.get("type") != "table":
                continue
            yield page_number, int(block.get("index", 0)), block.get("text") or []


def extract_document(clean_record, document, errors):
    """One report's record, or None when the layout is unrecognised.

    The format is decided once, from the first table whose header matches
    either layout, and then applied to every table in the document — a report
    does not change layout halfway through, and deciding per-table would let a
    misread header quietly switch readers mid-annex.
    """
    doc_slug = clean_record["doc_slug"]
    tables = list(_tables(clean_record))

    fmt = None
    for _, _, rows in tables:
        header_index = _header_index(rows)
        if header_index is None:
            continue
        fmt = detect_format(rows[header_index])
        if fmt is not None:
            break

    if fmt is None:
        errors.append(_error_dict(
            "UnknownReportFormat",
            "No table header matched Format A (7-col) or Format B (5-col); "
            "document skipped and not marked processed so a later run retries it.",
            {"doc_slug": doc_slug}))
        return None

    sections = status_sections(clean_record) if fmt == "B" else {}
    observations = []

    for page_number, table_index, rows in tables:
        header_index = _header_index(rows)
        if header_index is None or detect_format(rows[header_index]) != fmt:
            first_cell = ""
            if rows:
                first_cell = next((_normalize_cell(c) for row in rows
                                   for c in row if _normalize_cell(c)), "")
            errors.append(_error_dict(
                "UnrecognisedAnnexTable",
                "Table's header does not match this document's detected "
                f"format ({fmt}); table skipped and its rows are not "
                "represented in the published observations.",
                {"doc_slug": doc_slug, "page": page_number,
                 "table": table_index, "first_cell": first_cell}))
            continue

        section_status = None
        if fmt == "B":
            section_status = sections.get(page_number)
            if section_status is None:
                errors.append(_error_dict(
                    "UnknownStatusSection",
                    "Format B table sits under no recognised Complete/Modified/"
                    "Delayed heading; skipped, never defaulted.",
                    {"doc_slug": doc_slug, "page": page_number,
                     "table": table_index}))
                continue

        observations.extend(extract_table(rows, page_number, table_index, fmt,
                                          section_status, doc_slug, errors))

    status_counts = {}
    for observation in observations:
        status_counts[observation["status"]] = status_counts.get(observation["status"], 0) + 1

    return {
        "doc_slug": doc_slug,
        "doc_title": document.get("doc_title") or doc_slug,
        "source_url": document.get("source_url") or "",
        "published_date": document.get("published_date"),
        "public_body_id": document.get("public_body_id"),
        "reports_on": document.get("reports_on"),
        "report_format": fmt,
        # Never inferred from document content: a report's own publication date
        # is what dates its claims.
        "as_of": document.get("published_date"),
        "observation_count": len(observations),
        "status_counts": status_counts,
        "observations": observations,
    }


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------


def _index_by_doc(path: Path) -> dict:
    if not Path(path).exists():
        return {}
    return {record["doc_slug"]: record
            for record in read_json(path).get("results", [])
            if "doc_slug" in record}


def process(clean_records, meta, step_dir, writer, doc_slug=None,
            verbose=False):
    """Extract observations from every `role: report` document. Plans are
    skipped without error — they declare actions, they do not observe them."""
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])

    documents = clean_records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for record in documents:
        slug = record["doc_slug"]
        document = meta.get(slug) or {}
        if document.get("role", "plan") != "report":
            continue
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {slug} ...", end=" ", flush=True)

        errors = []
        try:
            result = extract_document(record, document, errors)
        except Exception as e:
            # A corrupt upstream record must not abort the batch — the same
            # isolation clean_text and assemble_sections apply.
            errors.append(_error_dict("ExtractActionStatusFailed", str(e),
                                      {"doc_slug": slug}))
            result = None

        for error in errors:
            append_error(step_dir, error)

        if result is None:
            # Not marked processed: a later run retries without --force.
            if verbose:
                print("[skipped]", flush=True)
            continue

        writer.append([result])
        if verbose:
            print(f"format {result['report_format']}, "
                  f"{result['observation_count']} observation(s)", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract one dated status observation per action row from "
                    "each progress report's annex tables")
    parser.add_argument("--input", required=True, help="Path to clean_text/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-extract every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    clean_records = read_json(input_path).get("results", [])

    # Fan-in: blocks from --input (clean_text); the document's role/provenance
    # from fetch_pdfs, the same pattern assemble_sections uses.
    steps_dir = input_path.resolve().parents[1]
    fetched = _index_by_doc(steps_dir / "fetch_pdfs" / "output.json")
    meta = {slug: {"doc_title": record.get("title") or slug,
                   "source_url": record.get("url") or "",
                   "published_date": record.get("published_date"),
                   "public_body_id": record.get("public_body_id"),
                   "role": record.get("role") or "plan",
                   "reports_on": record.get("reports_on")}
            for slug, record in fetched.items()}

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(clean_records, meta, step_dir, writer, doc_slug=args.doc,
            verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} report status record(s) to {output_path}")


if __name__ == "__main__":
    main()

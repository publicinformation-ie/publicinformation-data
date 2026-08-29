#!/usr/bin/env python3
"""Step: extract_actions — find the commitments inside a document's tables
and turn each action row into clean, reviewable metadata.

`document_pipeline` already turns a public-interest PDF into per-section
Markdown, but the *commitments* inside it — the action-plan tables that are
the actual point of a Sustainable Mobility Policy Action Plan or a Road
Safety Strategy Phase 2 Action Plan — are only reachable by reading the
rendered prose. This step walks `clean_text`'s table blocks and, per
document, (1) classifies it into one of three buckets by whether it contains
action tables and whether those tables carry a target date, (2) extracts each
action row and its target date, and (3) emits the categorisation record (a
human reviews it) plus a library-wide `public/documents/actions.json` — the
input a future calendar/ICS exporter would consume. Exporting a calendar is
out of scope: this stops at metadata.

All of this is deterministic and pure JSON in / JSON out — no PDF is opened,
no LLM or vision model is consulted (the document-bundle contract excludes
them for this pipeline), no OCR, and no dates beyond the deadline column.
That is what lets every function here be tested against hand-written table
fixtures in milliseconds, exactly the way `clean_text` and `assemble_sections`
are.

Detection is header-based and fail-closed, per the repository's core
data-handling principle:

  * a table qualifies as an **action table** only if its header row (first
    non-empty row, cells normalized via `lib.text_utils.normalize_text`)
    contains an action column AND every data row's action cell is non-empty;
  * a table with no action column is **confidently excluded** — progress
    trackers, abbreviation tables, TOC/furniture tables and plain data tables
    are excluded by the *absence* of an action column, never by a positive
    "this is X" heuristic;
  * a table with an action column whose column mapping (action vs date) is
    ambiguous is `ActionHeaderAmbiguous`; a table with an action column that
    fails the every-row-non-empty test is `UnclassifiedTable` — both
    informational, so a human can eyeball them in the report.

Date parsing is raw-plus-structured: `raw_date` is always emitted, structured
fields (`year`/`quarter`/`month`/`day`/`precision`/`start`/`end`) are filled
only when a pattern matches confidently; otherwise they are null and a
`DateParseError` (informational) is logged. Nothing is silently dropped or
rewritten to "fit".
"""
import argparse
import calendar
import re
from datetime import date, datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
from lib.text_utils import normalize_text

STEP_NAME = "extract_actions"

# --------------------------------------------------------------------------
# Keyword vocabularies (exact, case-insensitive after normalization)
# --------------------------------------------------------------------------

ACTION_KEYWORDS = frozenset({
    "action", "actions", "action(s)", "action description", "measure",
    "measures", "key action", "strategic action", "action item",
})

DATE_KEYWORDS = frozenset({
    "deadline", "timeframe", "timeline", "target date", "completion date",
    "date", "due date", "time period", "delivery date", "year", "quarter",
})

# --------------------------------------------------------------------------
# Cell / header normalization
# --------------------------------------------------------------------------


def _normalize_cell(value):
    return normalize_text(value, file_type="pdf")


def _normalize_header(value):
    return normalize_text(value, file_type="pdf", for_header=True)


def _has_content(row) -> bool:
    return any(_normalize_cell(c) for c in row)


def _cell_at(cells, index):
    if index is None or index >= len(cells):
        return ""
    return cells[index]


def _header_index(rows):
    """Index of the first non-empty row, or None if every row is empty."""
    for index, row in enumerate(rows):
        if _has_content(row):
            return index
    return None


# --------------------------------------------------------------------------
# Table → action-table classification
# --------------------------------------------------------------------------


class TableVerdict:
    """The result of classifying one table block.

    `is_action_table` is True only for a fully-qualified action table; a
    verdict that fails carries `error_type` instead (informational, the table
    is simply skipped for extraction). `dated` is True when a date column was
    found alongside the action column.
    """

    __slots__ = ("is_action_table", "dated", "action_col", "date_col",
                 "header_index", "error_type")

    def __init__(self, is_action_table, dated, action_col=None, date_col=None,
                 header_index=None, error_type=None):
        self.is_action_table = is_action_table
        self.dated = dated
        self.action_col = action_col
        self.date_col = date_col
        self.header_index = header_index
        self.error_type = error_type


def classify_table(rows) -> TableVerdict:
    """Classify one table's rows against the action-table rules above."""
    header_index = _header_index(rows)
    if header_index is None:
        # A table with no content at all has no action column: excluded.
        return TableVerdict(False, False)

    header = [_normalize_header(c) for c in rows[header_index]]
    action_cols = [i for i, c in enumerate(header) if c in ACTION_KEYWORDS]
    date_cols = [i for i, c in enumerate(header) if c in DATE_KEYWORDS]

    if not action_cols:
        # Confidently excluded by the absence of an action column.
        return TableVerdict(False, False, header_index=header_index)

    if (len(action_cols) > 1 or len(date_cols) > 1
            or (date_cols and action_cols[0] == date_cols[0])):
        return TableVerdict(False, False, header_index=header_index,
                            error_type="ActionHeaderAmbiguous")

    action_col = action_cols[0]
    date_col = date_cols[0] if date_cols else None

    for row in rows[header_index + 1:]:
        if not _has_content(row):
            continue
        if not _normalize_cell(_cell_at(row, action_col)):
            # A header that matches an action column, but a data row with an
            # empty action cell: matched but not confidently an action table.
            return TableVerdict(False, False, action_col=action_col,
                                date_col=date_col, header_index=header_index,
                                error_type="UnclassifiedTable")

    return TableVerdict(True, date_col is not None, action_col=action_col,
                        date_col=date_col, header_index=header_index)


# --------------------------------------------------------------------------
# Date parsing (raw + structured, fail-closed)
# --------------------------------------------------------------------------

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DASH = r"[–—\-]"
_QUARTER_RANGE_RE = re.compile(
    rf"^q([1-4])\s+(\d{{4}})\s*{_DASH}\s*q([1-4])\s+(\d{{4}})$", re.IGNORECASE)
_QUARTER_SINGLE_RE = re.compile(r"^q([1-4])\s+(\d{4})$", re.IGNORECASE)
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
        month = _MONTHS.get(name)
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
        month = _MONTHS.get(name)
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


_EMPTY_STRUCTURED = _structured(None)


def _structured_fields(parsed) -> dict:
    return parsed if parsed is not None else dict(_EMPTY_STRUCTURED)


# --------------------------------------------------------------------------
# Row extraction (one row = one action)
# --------------------------------------------------------------------------


def _error_dict(error_type: str, message: str, context: dict) -> dict:
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": message,
            "context": context}


def extract_table(rows, page_number, table_index, verdict, doc_slug, errors) -> list:
    """Extract every action row from one qualified action table.

    One data row is one action; there is no row-level classification (a
    continuation row is out of scope per the design). Returns a list of action
    dicts and appends a `DateParseError` to `errors` for any non-empty date
    cell that no pattern matched — the action is still emitted with its raw
    date.
    """
    header = [_normalize_cell(c) for c in rows[verdict.header_index]]
    actions = []
    row_number = 0

    for row in rows[verdict.header_index + 1:]:
        if not _has_content(row):
            continue
        cells = [_normalize_cell(c) for c in row]
        action = _cell_at(cells, verdict.action_col)
        if not action:
            # A qualified table guarantees this is non-empty; guard anyway so
            # a ragged row can never produce an empty action.
            continue
        row_number += 1

        raw_date = _cell_at(cells, verdict.date_col) if verdict.dated else ""
        parsed = parse_date(raw_date) if raw_date else None
        if raw_date and parsed is None:
            errors.append(_error_dict(
                "DateParseError",
                "Deadline cell is non-empty but matched no supported date "
                "pattern; kept as raw_date with structured fields null.",
                {"doc_slug": doc_slug, "page": page_number, "table": table_index,
                 "row": row_number, "raw_date": raw_date}))

        columns = {}
        for index in range(len(header)):
            if index == verdict.action_col or index == verdict.date_col:
                continue
            key = header[index]
            value = _cell_at(cells, index)
            if key and value:
                columns[key] = value

        actions.append({
            "action_id": f"p{page_number:03d}-t{table_index + 1:02d}-r{row_number:02d}",
            "action": action,
            "raw_date": raw_date,
            **_structured_fields(parsed),
            "source_page": page_number,
            "source_table": table_index,
            "columns": columns,
        })
    return actions


# --------------------------------------------------------------------------
# Per-document classification + extraction
# --------------------------------------------------------------------------


def extract_document(clean_record, doc_slug):
    """Classify one document and extract its actions.

    Returns `(category, dated_table_count, undated_table_count, actions, errors)`.
    Precedence is `dated-actions` > `undated-actions` > `no-action-tables`;
    the per-kind counts keep a mixed document visible in the report.
    """
    dated_count = 0
    undated_count = 0
    actions = []
    errors = []

    for page in clean_record.get("pages") or []:
        page_number = int(page.get("number", 0))
        for block in page.get("blocks") or []:
            if block.get("type") != "table":
                continue
            rows = block.get("text") or []
            table_index = int(block.get("index", 0))
            verdict = classify_table(rows)

            if verdict.error_type == "ActionHeaderAmbiguous":
                errors.append(_error_dict(
                    "ActionHeaderAmbiguous",
                    "Header matched an action column but the column mapping "
                    "(action vs date) is ambiguous.",
                    {"doc_slug": doc_slug, "page": page_number,
                     "table": table_index}))
                continue
            if verdict.error_type == "UnclassifiedTable":
                errors.append(_error_dict(
                    "UnclassifiedTable",
                    "Header contains an action column but at least one data "
                    "row's action cell is empty; not confidently an action "
                    "table.",
                    {"doc_slug": doc_slug, "page": page_number,
                     "table": table_index}))
                continue
            if not verdict.is_action_table:
                continue

            if verdict.dated:
                dated_count += 1
            else:
                undated_count += 1
            actions.extend(extract_table(rows, page_number, table_index, verdict,
                                         doc_slug, errors))

    if dated_count:
        category = "dated-actions"
    elif undated_count:
        category = "undated-actions"
    else:
        category = "no-action-tables"

    return category, dated_count, undated_count, actions, errors


# --------------------------------------------------------------------------
# Published side artifact: public/documents/actions.json
# --------------------------------------------------------------------------


def flatten_actions(records) -> list:
    """The library-wide flat list: one entry per action, with its document
    provenance, ready to feed a future calendar/ICS exporter."""
    flat = []
    for record in records:
        for action in record.get("actions") or []:
            flat.append({
                "doc_slug": record["doc_slug"],
                "doc_title": record.get("doc_title"),
                "source_url": record.get("source_url"),
                "action_id": action["action_id"],
                "action": action["action"],
                "raw_date": action.get("raw_date"),
                "year": action.get("year"),
                "quarter": action.get("quarter"),
                "month": action.get("month"),
                "day": action.get("day"),
                "precision": action.get("precision"),
                "start": action.get("start"),
                "end": action.get("end"),
                "source_page": action.get("source_page"),
                "source_table": action.get("source_table"),
            })
    return flat


def write_public_actions(records, public_root) -> Path:
    """Write `actions.json` into `public_root`, returning its path. Mirrors
    generate_topics's `write_public_topics` — a side artifact alongside
    `public/documents/`, not a bundle-contract change."""
    public_root = Path(public_root)
    public_root.mkdir(parents=True, exist_ok=True)
    public_path = public_root / "actions.json"
    write_json(public_path, flatten_actions(records))
    return public_path


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------

def _index_by_doc(path: Path) -> dict:
    if not Path(path).exists():
        return {}
    return {record["doc_slug"]: record
            for record in read_json(path).get("results", [])
            if "doc_slug" in record}


def process(clean_records, meta, step_dir, writer, doc_slug=None, verbose=False):
    """Classify every document and extract its actions. `meta` is the
    fetch_pdfs provenance keyed by doc_slug (resolved by sibling path in
    main(), the same way assemble_sections does)."""
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])

    documents = clean_records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for record in documents:
        slug = record["doc_slug"]
        # Progress reports' annex tables carry an `Action` column and so
        # *qualify* under the header test below — extracting them would
        # duplicate every plan action once per report with nothing to signal
        # it had gone wrong. Actions are declared by plans; reports observe
        # them (extract_action_status). Not marked processed: the skip is
        # re-decided every run, so flipping a document's role in
        # documents.yml takes effect without --force.
        if (meta.get(slug) or {}).get("role", "plan") != "plan":
            if verbose:
                print(f"  {slug} ... [skipped: not a plan]", flush=True)
            continue
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {slug} ...", end=" ", flush=True)

        try:
            document = meta.get(slug) or {}
            category, dated, undated, actions, errors = extract_document(record, slug)
        except Exception as e:
            # A corrupt upstream record must not abort the batch — the same
            # isolation clean_text and assemble_sections apply. Not marked
            # processed, so a later run retries it.
            append_error(step_dir, _error_dict(
                "ExtractActionsFailed", str(e), {"doc_slug": slug}))
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        for error in errors:
            append_error(step_dir, error)

        writer.append([{
            "doc_slug": slug,
            "doc_title": document.get("doc_title") or slug,
            "source_url": document.get("source_url") or "",
            "publisher": document.get("publisher"),
            "published_date": document.get("published_date"),
            "public_body_id": document.get("public_body_id"),
            "category": category,
            "dated_table_count": dated,
            "undated_table_count": undated,
            "action_count": len(actions),
            "actions": actions,
        }])
        if verbose:
            print(f"{category} ({len(actions)} action(s))", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Classify each document's action tables and extract every "
                    "action row plus its target date into reviewable metadata")
    parser.add_argument("--input", required=True,
                        help="Path to clean_text/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-extract every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--public-root", type=Path, default=None,
                        help="Override public/documents/ (defaults to the repo root's)")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    clean_records = read_json(input_path).get("results", [])

    # Fan-in: the blocks come from --input (clean_text, its immediate
    # predecessor); the document's provenance comes from fetch_pdfs by sibling
    # path, the same pattern assemble_sections uses.
    steps_dir = input_path.resolve().parents[1]
    fetched = _index_by_doc(steps_dir / "fetch_pdfs" / "output.json")
    meta = {slug: {"doc_title": record.get("title") or slug,
                   "source_url": record.get("url") or "",
                   "publisher": record.get("publisher"),
                   "published_date": record.get("published_date"),
                   "public_body_id": record.get("public_body_id"),
                   "role": record.get("role") or "plan"}
            for slug, record in fetched.items()}

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(clean_records, meta, step_dir, writer, doc_slug=args.doc,
            verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)

    public_root = args.public_root or (step_dir.parents[3] / "public" / "documents")
    public_path = write_public_actions(read_json(output_path).get("results", []),
                                       public_root)

    print(f"Wrote {count} of {len(clean_records)} document action record(s) "
          f"to {output_path}")
    print(f"Wrote public data to {public_path}")


if __name__ == "__main__":
    main()

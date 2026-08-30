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
human reviews it) plus the action rows themselves. The categorisation record
lets a human review table classifications; the action rows are consumed by
`actions_pipeline`'s `resolve_action_identity` step and published as the
`public-body-actions` dataset (with public_body_id, stable identities, and
status history).

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

Date parsing is raw-plus-structured via `lib.date_parse` (shared with
`extract_action_status` and `resolve_action_identity`): `raw_date` is always
emitted, structured fields (`year`/`quarter`/`month`/`day`/`precision`/
`start`/`end`) are filled only when a pattern matches confidently; otherwise
they are null and a `DateParseError` (informational) is logged. Nothing is
silently dropped or rewritten to "fit".
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.date_parse import parse_date, structured_fields
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


def _is_title_only_row(row) -> bool:
    """True for a row that is a section title merged above the real header:
    a row with more than one cell overall but exactly one non-empty cell,
    where that cell doesn't look like a header keyword (e.g. "CORE ACTIONS"
    spanning what pdfplumber read as one cell of an otherwise-empty row).

    A row with only one cell to begin with (a genuinely single-column
    table) can't be distinguished this way — every row of such a table
    trivially has "exactly one non-empty cell" — so those are never
    considered title-only here.
    """
    if len(row) <= 1:
        return False
    cells = [_normalize_cell(c) for c in row]
    non_empty = [c for c in cells if c]
    if len(non_empty) != 1:
        return False
    header_cell = _normalize_header(non_empty[0])
    return header_cell not in ACTION_KEYWORDS and header_cell not in DATE_KEYWORDS


def _header_index(rows):
    """Index of the header row, or None if every row is empty.

    Normally this is the first non-empty row. But a table can carry a
    section-title row (e.g. "CORE ACTIONS") merged in above its real
    `ACTION/OWNER/...` header row — skip any leading title-only rows and
    land on the first row that either has more than one populated cell or
    whose lone cell matches a known header keyword. If every non-empty row
    looks title-shaped, fall back to the first non-empty row rather than
    giving up (a table that is genuinely just a lone label still needs a
    header index, not None).
    """
    first_non_empty = None
    for index, row in enumerate(rows):
        if not _has_content(row):
            continue
        if first_non_empty is None:
            first_non_empty = index
        if not _is_title_only_row(row):
            return index
    return first_non_empty


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
        if _is_title_only_row(row):
            # A mid-table section title (e.g. "COMPLEMENTARY ACTION IN
            # HOUSING FOR ALL") that clean_text didn't split into its own
            # table block: not a data row.
            continue
        cells = [_normalize_cell(c) for c in row]
        action = _cell_at(cells, verdict.action_col)
        if not action:
            # A qualified table guarantees this is non-empty; guard anyway so
            # a ragged row can never produce an empty action.
            continue
        if cells == header:
            # A repeated header row (e.g. a second "ACTION" row following a
            # mid-table title) mid-way through the same table block: not a
            # data row either. Matched whole-row, not just the action cell,
            # so a genuine action whose text happens to equal a keyword
            # (e.g. "Measures") is never mistaken for a repeated header.
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
            **structured_fields(parsed),
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

    print(f"Wrote {count} of {len(clean_records)} document action record(s) "
          f"to {output_path}")


if __name__ == "__main__":
    main()

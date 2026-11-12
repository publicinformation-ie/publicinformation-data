#!/usr/bin/env python3
"""Step: extract_annex_status — read each report's status annex workbook and
turn every row into one dated status observation of a plan action.

The department publishes the status of each Climate Action Plan action in a
quarterly XLSX annex. This is the annex counterpart of `extract_action_status`
and emits the same record shape, plus internal provenance (sheet, row, raw
cells), so the actions pipeline joins both through one path.

Nothing here guesses (AGENTS.md: if a record cannot be reconstructed
deterministically, log an error for human review):

  * **Headers are fail-closed.** Row 1 of a sheet, normalised, must equal the
    full ordered header of a reviewed layout exactly. No approximate match, no
    header search in later rows, no reducing to the columns that matched.
  * **Status is text only.** Fill colour is never read. Anything outside the
    reviewed mapping (`Discontinued`, blank, ...) is excluded and logged with
    its raw value, never coerced to the nearest member.
  * **Dates come from the report.** `as_of` is the curated `published_date`; an
    undated report contributes no observations and one `MissingReportDate`.
  * **Duplicate references exclude both rows.**

Attribution of an observation to a plan edition is not done here; that is
`resolve_action_identity`, which knows the plans.
"""
import argparse
import importlib.util
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.date_parse import parse_date
from lib.file_utils import IncrementalWriter, append_errors, read_json, write_json, write_status

STEP_NAME = "extract_annex_status"


def _load_action_references():
    """`action_references` lives in actions_pipeline; load it by path so that
    pipeline's own `steps` package never shadows this one on sys.path."""
    root = Path(__file__).resolve()
    while not (root / ".git").exists():
        root = root.parent
    path = root / "pipelines" / "actions_pipeline" / "action_references.py"
    spec = importlib.util.spec_from_file_location("action_references", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_refs = _load_action_references()
InvalidReference = _refs.InvalidReference
parse_reference = _refs.parse_reference

# --------------------------------------------------------------------------
# Reviewed layout table
# --------------------------------------------------------------------------
# Every distinct row-1 header observed across the nine CAP workbooks
# (2023 Q1-Q4, 2024 Q1&Q2 and Q3&Q4, CAP25 Q1, Q2&Q3, Q4, 2026 Q1&Q2), after
# whitespace/NBSP collapse and casefolding, with trailing empty cells ignored.
# Each is an exact, complete, ordered header. A header that is not in this
# table is a workbook we have not reviewed; adding one is a reviewed change.
_LAYOUT_SIGNATURES = (
    # Climate_Action_Plan_2024_-_Q3_and_Q4_Annex_of / Q3 & Q4 Actions (+2 more)
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'action',
        'step',
        'output',
        'timeline',
        'lead',
        'responsible department',
        'stakeholders',
        'status: complete / delayed',
        'final text update',
    ),
    # Climate_Action_Plan_2025_Q2_and_Q3_Annex.xlsx / Q3
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'actions',
        'steps necessary for delivery',
        'output',
        'timeline',
        'lead',
        'reporting lead',
        'stakeholders',
        'status: complete/delayed',
        'text update',
    ),
    # Climate_Action_Plan_2025_Q2_and_Q3_Annex.xlsx / Q2 (+2 more)
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'actions',
        'steps necessary for delivery',
        'output',
        'timeline',
        'lead',
        'reporting lead',
        'stakeholders',
        'status (complete/ delayed)',
        'q3 update text',
    ),
    # Climate_Action_Plan_2025_Q4_Annex.xlsx / Q4 (+1 more)
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'actions',
        'steps necessary for delivery',
        'output',
        'timeline',
        'lead',
        'reporting lead',
        'stakeholders',
        'status: complete/delayed',
        'q4 text update',
    ),
    # Climate_Action_Plan_2025_Q4_Annex.xlsx / Q2 (+2 more)
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'actions',
        'steps necessary for delivery',
        'output',
        'timeline',
        'lead',
        'reporting lead',
        'stakeholders',
        'status (complete/ delayed)',
        'q4 update text',
    ),
    # Climate_Action_Plan_Q1__Q2_2026_Annex.xlsx / Sheet1
    (
        'action number',
        'actions',
        'steps necessary for delivery',
        'output',
        'timeline',
        'lead',
        'reporting lead',
        'stakeholders',
        'status: complete/delayed',
        'q1 / q2 2026 text update',
    ),
    # Q1_CAP25_Progress_Report_Annex_of_Actions_-_F / Q1 (+1 more)
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'actions',
        'steps necessary for delivery',
        'output',
        'timeline',
        'lead',
        'reporting lead',
        'stakeholders',
        'status (complete/ delayed)',
        'final text update',
    ),
    # climate-action-plan-2023-q1-actions.xlsx / Q1 Final text update
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'action',
        'step',
        'output',
        'timeline',
        'lead',
        'responsible department',
        'stakeholders',
        'status (complete / delayed)',
        'text',
    ),
    # climate-action-plan-2023-q2-actions.xlsx / Q2 Final Updates
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'action',
        'step',
        'output',
        'timeline',
        'lead',
        'responsible department',
        'stakeholders',
        'status: complete/delayed',
        'q2 2023 text update',
    ),
    # climate-action-plan-2023-q3-actions.xlsx / Q3 final returns
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'action',
        'step',
        'output',
        'timeline',
        'lead',
        'responsible department',
        'stakeholders',
        'status: complete or delayed',
        'final text update',
    ),
    # climate-action-plan-2023-q4-actions.xlsx / 2023 Q4 Final Updates
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'action',
        'step',
        'output',
        'timeline',
        'lead',
        'responsible department',
        'stakeholders',
        'status: complete/ delayed',
        'q4 text update',
    ),
    # climate-action-plan-2024-q1-q2-and-legacy-202 / Q1 & Q2 Actions (+1 more)
    (
        'chapter',
        'theme',
        'measure',
        'action number',
        'action',
        'step',
        'output',
        'timeline',
        'lead',
        'responsible department',
        'stakeholders',
        'status: complete / delayed',
        'text update',
    ),
)

_STATUS_MAP = {"complete": "Complete", "delayed": "Delayed", "on schedule": "OnSchedule"}
_QUARTER_RE = re.compile(r"^Q([1-4]) (\d{4})$")


def normalise_cell(value) -> str:
    """Whitespace collapse and trim (NBSP included). The only text transform."""
    return " ".join(str(value).split()) if value is not None else ""


def header_signature(row) -> tuple:
    cells = [normalise_cell(c).casefold() for c in row]
    while cells and not cells[-1]:
        cells.pop()
    return tuple(cells)


def _column(header: tuple, names) -> int:
    matches = [i for i, c in enumerate(header) if c in names]
    if len(matches) != 1:
        raise ValueError(f"layout {header!r} has no unique column among {names}")
    return matches[0]


def layout_columns(header: tuple) -> dict:
    """Column indexes for a header already proven equal to a reviewed layout."""
    status = [i for i, c in enumerate(header) if c.startswith("status")]
    if len(status) != 1:
        raise ValueError(f"layout {header!r} has no unique status column")
    return {
        "reference": _column(header, ("action number",)),
        "action_text": _column(header, ("action", "actions")),
        "output": _column(header, ("output",)),
        "timeline": _column(header, ("timeline",)),
        "status": status[0],
        # The last column is the quarter's progress narrative in every layout.
        "status_text": len(header) - 1,
    }


LAYOUTS = {sig: layout_columns(sig) for sig in _LAYOUT_SIGNATURES}


def _error(error_type, message, context):
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type, "error_message": message, "context": context}


def map_status(raw):
    """Vocabulary notation for a status cell, or None if outside the mapping."""
    return _STATUS_MAP.get(normalise_cell(raw).casefold())


def parse_timeline(raw: str):
    """Structured deadline for a strict `Q[1-4] YYYY`, else None (raw kept)."""
    if not _QUARTER_RE.match(raw):
        return None
    return parse_date(raw)


def _cell(row, index):
    return row[index] if index < len(row) else None


def read_sheet(ws, doc_slug, errors):
    """`(candidates, rows_seen)` for one worksheet; ([], 0) when the header is
    unrecognised (error logged). Rows here still need the cross-sheet
    duplicate check and the status/date gates in `extract_document`."""
    rows = ws.iter_rows(values_only=True)
    header_row = next(rows, None)
    signature = header_signature(header_row or ())
    columns = LAYOUTS.get(signature)
    if columns is None:
        errors.append(_error(
            "UnrecognisedAnnexLayout",
            "Row 1 matches no reviewed layout; worksheet skipped with zero rows "
            "emitted. Never matched approximately, sought in another row, or "
            "reduced to the columns that matched.",
            {"doc_slug": doc_slug, "sheet": ws.title,
             "header_found": [normalise_cell(c) for c in (header_row or ())]}))
        return [], 0

    candidates = []
    seen = 0
    for row_number, row in enumerate(rows, start=2):
        if not any(normalise_cell(c) for c in row):
            continue
        seen += 1
        where = {"doc_slug": doc_slug, "sheet": ws.title, "row": row_number}
        raw_reference = _cell(row, columns["reference"])
        try:
            parsed = parse_reference(normalise_cell(raw_reference))
        except InvalidReference as e:
            errors.append(_error(e.error_type, str(e),
                                 {**where, "raw_reference": raw_reference}))
            continue
        candidates.append({"where": where, "parsed": parsed, "row": row,
                           "columns": columns, "raw_reference": raw_reference})
    return candidates, seen


def build_observation(candidate, as_of, errors):
    """The observation for one row, or None when its status excludes it."""
    where, row, columns = candidate["where"], candidate["row"], candidate["columns"]
    parsed = candidate["parsed"]
    raw_status = _cell(row, columns["status"])
    status_text = normalise_cell(raw_status)
    if not status_text:
        errors.append(_error(
            "MissingStatus",
            "Status cell is empty; no status is inferred (fill colour is never "
            "read), observation excluded.",
            {**where, "action_number": parsed.number}))
        return None
    status = map_status(raw_status)
    if status is None:
        errors.append(_error(
            "UnmappableStatus",
            f"Status {raw_status!r} is outside the reviewed mapping "
            f"({sorted(_STATUS_MAP)}); excluded, never coerced.",
            {**where, "action_number": parsed.number, "raw_status": raw_status}))
        return None

    raw_timeline = normalise_cell(_cell(row, columns["timeline"]))
    structured = parse_timeline(raw_timeline)
    if raw_timeline and structured is None:
        errors.append(_error(
            "UnparsedTimeline",
            "Timeline is not a strict 'Q<n> <year>'; raw text kept, structured "
            "deadline fields null.",
            {**where, "action_number": parsed.number, "raw_timeline": raw_timeline}))

    return {
        "action_number": parsed.number,
        "action_reference_printed": parsed.printed,
        "action_flags": parsed.flags,
        "reference_year": parsed.year,
        "action_text": normalise_cell(_cell(row, columns["action_text"])),
        "proposed_output": normalise_cell(_cell(row, columns["output"])),
        "reported_deadline_raw": raw_timeline,
        "reported_deadline_start": structured["start"] if structured else None,
        "reported_deadline_end": structured["end"] if structured else None,
        "reported_deadline_precision": structured["precision"] if structured else None,
        "progress_text": normalise_cell(_cell(row, columns["status_text"])),
        "status": status,
        "asi": None,
        "source_page": None,
        "source_ref": f"{where['sheet']}!r{where['row']}",
        "sheet": where["sheet"],
        "row": where["row"],
        "raw_reference": candidate["raw_reference"],
        "raw_status": raw_status,
        "as_of": as_of,
    }


def extract_document(annex_path, document, errors):
    """One report's record from its workbook."""
    import openpyxl
    slug = document["doc_slug"]
    as_of = document.get("published_date")

    wb = openpyxl.load_workbook(annex_path, read_only=True, data_only=True)
    try:
        candidates, sheets = [], []
        for ws in wb.worksheets:
            sheet_candidates, seen = read_sheet(ws, slug, errors)
            candidates.extend(sheet_candidates)
            sheets.append({"sheet": ws.title, "rows_read": seen})
    finally:
        wb.close()

    # An undated report contributes nothing: dating from content, the workbook
    # or its sheet names would be a guess.
    if not as_of:
        errors.append(_error(
            "MissingReportDate",
            "The report has no curated published_date, so none of its annex "
            "rows can be dated; no observations emitted.",
            {"doc_slug": slug, "rows_read": len(candidates)}))
        candidates = []

    by_number = defaultdict(list)
    for candidate in candidates:
        by_number[candidate["parsed"].number].append(candidate)
    excluded = set()
    for number, group in by_number.items():
        if len(group) > 1:
            excluded.update(id(c) for c in group)
            errors.append(_error(
                "DuplicateAnnexReference",
                f"Reference {number!r} appears on {len(group)} rows of this "
                f"annex; all are excluded.",
                {"doc_slug": slug, "action_number": number,
                 "locations": [{"sheet": c["where"]["sheet"], "row": c["where"]["row"]}
                               for c in group]}))

    observations = []
    for candidate in candidates:
        if id(candidate) in excluded:
            continue
        observation = build_observation(candidate, as_of, errors)
        if observation is not None:
            observations.append(observation)

    status_counts = {}
    for observation in observations:
        status_counts[observation["status"]] = status_counts.get(observation["status"], 0) + 1

    return {
        "doc_slug": slug,
        "doc_title": document.get("title") or slug,
        "source_url": document.get("url") or "",
        "published_date": as_of,
        "public_body_id": document.get("public_body_id"),
        "reports_on": document.get("reports_on"),
        "report_format": "annex-xlsx",
        "as_of": as_of,
        "annex_sha256": None,
        "sheets": sheets,
        "observation_count": len(observations),
        "status_counts": status_counts,
        "observations": observations,
    }


def process(annex_records, meta, annex_root, step_dir, writer, doc_slug=None,
            verbose=False):
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])
    errors = []

    fetched = {r["doc_slug"] for r in annex_records}
    for slug, document in meta.items():
        if (document.get("status_annex") and slug not in fetched
                and (doc_slug is None or doc_slug == slug)):
            errors.append(_error(
                "AnnexNotFetched",
                "The report declares a status annex but fetch_status_annexes "
                "produced no record for it (see that step's errors); no "
                "observations.",
                {"doc_slug": slug}))

    for record in annex_records:
        slug = record["doc_slug"]
        if doc_slug is not None and slug != doc_slug:
            continue
        if writer.is_processed(slug):
            continue
        document = meta.get(slug)
        if document is None:
            errors.append(_error("AnnexNotFetched",
                                 "Annex record has no document in documents.yml.",
                                 {"doc_slug": slug}))
            continue
        try:
            result = extract_document(Path(annex_root) / record["annex_path"],
                                      {**document, "doc_slug": slug}, errors)
        except Exception as e:  # one bad workbook must not abort the batch
            errors.append(_error("ExtractAnnexStatusFailed", f"{type(e).__name__}: {e}",
                                 {"doc_slug": slug}))
            continue
        result["annex_sha256"] = record.get("source_sha256")
        writer.append([result])
        if verbose:
            print(f"  {slug}: {result['observation_count']} observation(s)", flush=True)

    append_errors(step_dir, errors)


def main():
    parser = argparse.ArgumentParser(
        description="Extract dated status observations from each report's annex workbook")
    parser.add_argument("--input", required=True,
                        help="Path to fetch_status_annexes/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Accepted for the runner")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    input_path = Path(args.input).resolve()
    annex_records = read_json(input_path).get("results", [])

    # Curated report facts come from fetch_pdfs (documents.yml as fetched),
    # the same fan-in extract_action_status uses.
    steps_dir = input_path.parents[1]
    fetched_pdfs = read_json(steps_dir / "fetch_pdfs" / "output.json").get("results", [])
    meta = {r["doc_slug"]: r for r in fetched_pdfs if "doc_slug" in r}

    # Whole-corpus recomputation: the curated published_date can change without
    # the workbook changing, so nothing is resumed — except a --doc scope keeps
    # the other documents' records.
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=True if args.doc is None else args.force,
                               target_key=args.doc)
    process(annex_records, meta, input_path.parent, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} annex status record(s) to {output_path}")


if __name__ == "__main__":
    main()

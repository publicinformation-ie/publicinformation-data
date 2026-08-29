#!/usr/bin/env python3
"""Step: resolve_action_identity — give every published commitment a stable
name, and hang each report's observations off it.

Upstream, an action is identified by where its text sat on a page
(`p009-t01-r01`). That is a fine provenance record and a terrible identity: it
changes if the PDF is re-typeset, and it says nothing about which action the
document itself calls "action 48". This step derives identity from what the
document *states*:

    action_id = {plan_slug}#{action_number}

The plan edition is deliberately part of the key. An action renumbered in a
later plan is genuinely a different published row — a citation of "SMP action
48" means the 2022-2025 one — so continuity across editions is expressed as a
relationship (extract_relationships), never by collapsing two rows into one.
Action numbers are unique only within a plan, which is exactly why the key is
namespaced.

Two further jobs:

  * **The original deadline comes from the plan that declares the action**,
    never from a progress report. A deadline in a report is a *reported*
    deadline. Sourcing the baseline from the earliest report was considered and
    rejected: it agrees with the plan on ~91% of the SMP corpus, which is what
    makes it dangerous rather than merely imprecise — it would look right
    almost everywhere while being wrong on exactly the actions that slipped
    earliest, the highest-value rows in a dataset about slippage.
  * **Observations join to actions via the report's explicit `reports_on`**,
    never inferred from content or filename. An observation whose number has no
    matching plan action is `UnresolvedActionNumber`: skipped and logged, never
    guessed onto a neighbouring action.
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.date_parse import parse_date
from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "resolve_action_identity"

# Column aliases. extract_actions keys `columns` with normalize_text (not
# normalize_header), so the keys keep their source casing — always compare
# lowercased.
LEAD_ALIASES = ("owner", "lead", "lead organisation", "lead body",
                "responsible body", "responsible")
SUPPORT_ALIASES = ("support", "supporting bodies", "support organisation",
                   "supporting")
OUTPUT_ALIASES = ("output", "outputs", "proposed output")
TIMELINE_ALIASES = ("timeline & output", "timeline and output", "timeline",
                    "timeline & outputs", "timeframe", "deadline", "target date")

_BEL = "\x07"
_ORDINAL_RE = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*")
_YEAR_RE = re.compile(r"\d{4}")
_QUARTER_PREFIX_RE = re.compile(r"q([1-4])\s*$", re.IGNORECASE)
_DASHES = "-–—"


def _error_dict(error_type: str, message: str, context: dict) -> dict:
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": message,
            "context": context}


def mint_action_id(plan_slug: str, action_number: int) -> str:
    return f"{plan_slug}#{action_number}"


def strip_leading_ordinal(text):
    """`(action_number, clean_text)` for a plan action cell.

    Plan action cells carry their number as a leading ordinal and are peppered
    with `\\x07` (BEL) bullet artifacts, e.g. `"1. \\x07Develop and publish…"`.
    Stripping both is mechanical, but it is a named, tested transform rather
    than an incidental regex because the number it recovers *is* the published
    identity of the row.
    """
    cleaned = (text or "").replace(_BEL, " ")
    cleaned = " ".join(cleaned.split())
    match = _ORDINAL_RE.match(cleaned)
    if not match:
        return None, cleaned
    return int(match.group(1)), cleaned[match.end():].strip()


def column_value(columns: dict, aliases) -> str:
    lowered = {str(key).lower(): value for key, value in (columns or {}).items()}
    for alias in aliases:
        if lowered.get(alias):
            return lowered[alias]
    return ""


def _date_candidates(text):
    """`(year, quarter, labelled)` for every year token that could be a date.

    Rejects a year adjacent to a dash — `IMMAC 2025-2030` is the title of a
    contract, not a deadline, and naive "latest year wins" reads 2030 out of
    it. `labelled` marks a year introduced the way this corpus introduces
    milestones: `Q<n> <year>` or `<year>:`.
    """
    candidates = []
    for match in _YEAR_RE.finditer(text):
        before, after = text[:match.start()], text[match.end():]
        # `before[-1:] in _DASHES`/`after[:1] in _DASHES` would wrongly reject
        # every match at the very start (or end) of `text`: an empty slice is
        # a substring of any string in Python, so `"" in _DASHES` is True.
        # `.endswith`/`.startswith` on the dash tuple don't have that trap.
        if before.endswith(tuple(_DASHES)) or after.startswith(tuple(_DASHES)):
            continue
        quarter_match = _QUARTER_PREFIX_RE.search(before)
        if quarter_match:
            candidates.append((int(match.group()), int(quarter_match.group(1)), True))
        else:
            candidates.append((int(match.group()), None,
                               after.lstrip(" ").startswith(":")))
    return candidates


def _parse_candidate(candidate):
    year, quarter, _ = candidate
    return parse_date(f"Q{quarter} {year}" if quarter else str(year))


def resolve_original_deadline(raw_date, timeline_cell):
    """`(structured_date | None, confidence | None)` for one plan action.

    `confidence` is published so a consumer can tell what the document *stated*
    from what we *concluded* — 63 of the 2022-2025 plan's 91 baselines are
    transcribed, 23 are derived by the latest-milestone rule — without having
    to re-derive that judgement from the raw text.
    """
    raw_date = " ".join(str(raw_date or "").split())
    if raw_date:
        parsed = parse_date(raw_date)
        if parsed is not None:
            return parsed, "stated"

    text = " ".join(str(timeline_cell or "").replace(_BEL, " ").split())
    if not text:
        return None, None

    parsed = parse_date(text)
    if parsed is not None:
        return parsed, "stated"

    candidates = _date_candidates(text)
    if not candidates:
        return None, None

    distinct = {(year, quarter) for year, quarter, _ in candidates}
    if len(distinct) == 1:
        return _parse_candidate(candidates[0]), "stated"

    milestones = [c for c in candidates if c[2]]
    if not milestones:
        # Several candidate years, none introduced as a milestone: there is no
        # rule that picks one, so refuse rather than take the latest.
        return None, None
    return _parse_candidate(max(milestones, key=lambda c: (c[0], c[1] or 4))), "interpreted"


def build_actions(plan_records, plan_meta):
    """`(actions, errors)` — the canonical action set across every plan."""
    actions = []
    errors = []

    for record in plan_records:
        plan_slug = record["doc_slug"]
        meta = plan_meta.get(plan_slug) or {}
        for raw in record.get("actions") or []:
            source_ref = raw.get("action_id")
            number, action_text = strip_leading_ordinal(raw.get("action"))
            if number is None:
                errors.append(_error_dict(
                    "UnresolvedActionNumber",
                    "Plan action cell carries no leading ordinal, so the row "
                    "has no stated number to be identified by; skipped.",
                    {"plan_slug": plan_slug, "source_ref": source_ref}))
                continue

            columns = raw.get("columns") or {}
            timeline_raw = (column_value(columns, TIMELINE_ALIASES)
                            or raw.get("raw_date") or "")
            parsed, confidence = resolve_original_deadline(
                raw.get("raw_date"), timeline_raw)
            if timeline_raw and parsed is None:
                errors.append(_error_dict(
                    "DateParseError",
                    "Timeline cell is non-empty but yielded no confident "
                    "deadline; raw text kept, structured fields null.",
                    {"plan_slug": plan_slug, "action_number": number,
                     "original_timeline_raw": timeline_raw}))

            actions.append({
                "action_id": mint_action_id(plan_slug, number),
                "public_body_id": meta.get("public_body_id") or record.get("public_body_id"),
                "plan_slug": plan_slug,
                "plan_title": meta.get("doc_title") or record.get("doc_title") or plan_slug,
                "source_url": meta.get("source_url") or record.get("source_url") or "",
                "action_number": number,
                "action_text": action_text,
                "original_deadline_raw": timeline_raw,
                "original_deadline_start": parsed["start"] if parsed else None,
                "original_deadline_end": parsed["end"] if parsed else None,
                "original_deadline_precision": parsed["precision"] if parsed else None,
                "original_deadline_confidence": confidence,
                "original_timeline_raw": timeline_raw,
                "lead": column_value(columns, LEAD_ALIASES),
                "support": column_value(columns, SUPPORT_ALIASES),
                "output": column_value(columns, OUTPUT_ALIASES),
                "source_page": raw.get("source_page"),
                "source_ref": source_ref,
            })

    return actions, errors


def build_observations(report_records, actions):
    """`(observations, errors)` — every report observation joined to an action.

    Also emits the informational `DeadlineDivergedAtFirstReport` marker, and
    only for the *earliest* report that mentions an action: a plan baseline
    that already differs from the first thing anyone reported about it is
    evidence of slippage before the first report was written — the dataset's
    headline signal, not a fault.
    """
    by_id = {action["action_id"]: action for action in actions}
    observations = []
    errors = []

    earliest_by_action = {}
    for record in sorted(report_records, key=lambda r: r.get("as_of") or ""):
        plan_slug = record.get("reports_on")
        for raw in record.get("observations") or []:
            number = raw.get("action_number")
            action_id = mint_action_id(plan_slug, number) if plan_slug else None
            action = by_id.get(action_id)
            if action is None:
                errors.append(_error_dict(
                    "UnresolvedActionNumber",
                    f"Observation of action {number!r} in report "
                    f"{record['doc_slug']!r} matches no action in plan "
                    f"{plan_slug!r}; skipped, never guessed onto a neighbour.",
                    {"report_slug": record["doc_slug"], "reports_on": plan_slug,
                     "action_number": number, "source_ref": raw.get("source_ref")}))
                continue

            observations.append({
                "action_id": action_id,
                "report_slug": record["doc_slug"],
                "report_title": record.get("doc_title") or record["doc_slug"],
                "as_of": record.get("as_of"),
                "status": raw.get("status"),
                "reported_deadline_raw": raw.get("reported_deadline_raw") or "",
                "reported_deadline_start": raw.get("reported_deadline_start"),
                "reported_deadline_end": raw.get("reported_deadline_end"),
                "reported_deadline_precision": raw.get("reported_deadline_precision"),
                "progress_text": raw.get("progress_text") or "",
                "asi": raw.get("asi"),
                "source_page": raw.get("source_page"),
                "source_ref": raw.get("source_ref"),
            })

            if action_id in earliest_by_action:
                continue
            earliest_by_action[action_id] = record["doc_slug"]
            baseline = action["original_deadline_start"]
            reported = raw.get("reported_deadline_start")
            if baseline and reported and baseline != reported:
                errors.append(_error_dict(
                    "DeadlineDivergedAtFirstReport",
                    "The plan's original deadline differs from the earliest "
                    "reported deadline: slippage that predates the first "
                    "progress report. Informational — a finding, not a fault.",
                    {"action_id": action_id, "report_slug": record["doc_slug"],
                     "original_deadline_start": baseline,
                     "reported_deadline_start": reported}))

    return observations, errors


def _repo_root() -> Path:
    root = Path(__file__).resolve()
    while not (root / ".git").exists():
        if root == root.parent:
            raise RuntimeError("Could not find the repository root")
        root = root.parent
    return root


def _plan_meta(documents) -> dict:
    return {doc["doc_slug"]: {"doc_title": doc.get("title"),
                              "source_url": doc.get("url"),
                              "public_body_id": doc.get("public_body_id")}
            for doc in documents}


def main():
    parser = argparse.ArgumentParser(
        description="Mint stable action ids, resolve each action's original "
                    "deadline, and join every report observation to an action")
    parser.add_argument("--input", required=True,
                        help="Path to document_pipeline extract_actions/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true",
                        help="Accepted for runner compatibility; this step is "
                             "a whole-corpus recomputation and always rebuilds")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    write_json(step_dir / "errors.json", [])

    input_path = Path(args.input).resolve()
    plan_records = read_json(input_path).get("results", [])

    # extract_action_status is a sibling *of the input path* — the input is a
    # document_pipeline step output, so its parents[1] is that pipeline's
    # steps/ directory (see the pipeline's README on cross-pipeline wiring).
    document_steps = input_path.parents[1]
    status_path = document_steps / "extract_action_status" / "output.json"
    if not status_path.exists():
        sys.exit(f"Missing {status_path} — run document_pipeline first")
    report_records = read_json(status_path).get("results", [])

    sys.path.insert(0, str(_repo_root() / "pipelines" / "document_pipeline"))
    from documents import load_documents
    documents = load_documents()

    actions, action_errors = build_actions(plan_records, _plan_meta(documents))
    observations, observation_errors = build_observations(report_records, actions)

    append_errors(step_dir, action_errors + observation_errors)
    write_json(output_path, {
        "metadata": {"step": STEP_NAME,
                     "generated_at": datetime.now(timezone.utc).isoformat(),
                     "action_count": len(actions),
                     "observation_count": len(observations)},
        "actions": actions,
        "observations": observations,
    })
    write_status(step_dir, len(actions))
    print(f"Resolved {len(actions)} action(s) and {len(observations)} "
          f"observation(s) to {output_path}")


if __name__ == "__main__":
    main()

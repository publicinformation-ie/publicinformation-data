#!/usr/bin/env python3
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.llm_extract import extract_json

from steps.extract_motions.chunking import split_text
from steps.extract_motions.guards import (
    detect_ce_schedule,
    detect_procedural_dump,
)

STEP_NAME = "extract_motions"

_SYSTEM_PROMPT = (
    "Return ONLY valid JSON. No markdown, no extra text, no code fences.\n"
    "Schema: {\"meeting_date\": \"YYYY-MM-DD\" or null, "
    "\"motions\": [{\"motion_text\": \"string\", \"proposer\": \"string or null\", "
    "\"seconder\": \"string or null\", \"status_label\": "
    "\"carried|carried_as_amended|not_carried|withdrawn|deferred|not_recorded\"}]}"
    "\nExtract motions from Irish local-authority council meeting minutes. "
    "A motion is a formal proposal put to a vote (often starting "
    "'That the council…' or 'Proposed by…'). "
    "'meeting_date' is the ISO date (YYYY-MM-DD) when stated in the document "
    "(full calendar date only), otherwise null."
)


def build_user_prompt(record, part=None, total=None, text=None) -> str:
    if part is None:
        header = ("Extract the motions from these minutes "
                  f"(municipal district {record.get('municipal_district')}, "
                  f"meeting date {record.get('meeting_date')}).")
    else:
        header = ("Extract the motions from part "
                  f"{part} of {total} of these minutes "
                  f"(municipal district {record.get('municipal_district')}, "
                  f"meeting date {record.get('meeting_date')}). "
                  "Only extract complete motions fully contained in this part; "
                  "ignore any motion that is cut off at the start or end.")
    body = record["text"] if text is None else text
    return f"{header}\n\n{body}"


def _normalise_motion_text(motion) -> str:
    return " ".join((motion.get("motion_text") or "").split()).lower()


def extract_one(record, api_fn=None, model=None, effort=None):
    """Extract motions, chunking documents over MAX_CHUNK_CHARS. One failed
    chunk fails the whole document (no partial motions). Two deterministic
    guards quarantine extreme CE schedules and procedural acceptance dumps."""
    schedule = detect_ce_schedule(record.get("text"))
    if schedule is not None:
        return {**record, "stated_date": None, "motions": None,
                "skip_reason": "ce_recommendation_schedule",
                "guard_evidence": schedule}

    chunks = split_text(record.get("text") or "")
    total = len(chunks)
    motions = []
    seen_texts = set()
    stated_date = None
    failed_chunks = []

    for index, chunk in enumerate(chunks, start=1):
        prompt = (build_user_prompt(record, index, total, text=chunk)
                  if total > 1 else build_user_prompt(record))
        result = extract_json(_SYSTEM_PROMPT, prompt, api_fn=api_fn,
                              model=model, effort=effort)
        payload_motions = result.get("motions") if isinstance(result, dict) else None
        if not isinstance(payload_motions, list) or not all(
                isinstance(motion, dict) for motion in payload_motions):
            failed_chunks.append(index)
            break
        if stated_date is None and isinstance(result.get("meeting_date"), str):
            stated_date = result["meeting_date"]
        chunk_motions = [
            motion for motion in payload_motions
            if _normalise_motion_text(motion) not in seen_texts
        ]
        motions.extend(chunk_motions)
        seen_texts.update(_normalise_motion_text(m) for m in chunk_motions)

    if failed_chunks:
        return {**record, "stated_date": stated_date, "motions": None,
                "failed_chunks": failed_chunks, "chunk_count": total}
    dump = detect_procedural_dump(motions)
    if dump is not None:
        return {**record, "stated_date": stated_date, "motions": None,
                "skip_reason": "procedural_acceptance_dump",
                "chunk_count": total, "guard_evidence": dump}
    return {**record, "stated_date": stated_date, "motions": motions}


def _process_one(item, api_fn=None):
    file_url = item["file_url"]
    try:
        record = extract_one(item, api_fn=api_fn)
        failed = record["motions"] is None
        return file_url, record, None, failed
    except Exception as e:
        return file_url, None, e, False


def process(input_data, step_dir, writer, verbose=False, max_workers=2, api_fn=None):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["file_url"])]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, item, api_fn): item for item in pending}
        for future in as_completed(futures):
            file_url, record, exc, failed = future.result()
            if exc is not None or failed:
                skip_reason = (record or {}).get("skip_reason")
                context = {"file_url": file_url,
                           "public_body_id": record["public_body_id"] if record else None}
                if record is not None:
                    if record.get("failed_chunks"):
                        context["failed_chunks"] = record["failed_chunks"]
                    if record.get("chunk_count"):
                        context["chunk_count"] = record["chunk_count"]
                    if skip_reason:
                        context["skip_reason"] = skip_reason
                    if record.get("guard_evidence"):
                        context["guard_evidence"] = record["guard_evidence"]
                if skip_reason:
                    error_type = "MotionExtractionSkipped"
                    error_message = f"Skipped by guard: {skip_reason}"
                elif exc is not None:
                    error_type = type(exc).__name__
                    error_message = str(exc)
                else:
                    error_type = "MotionExtractionError"
                    error_message = "LLM returned unparseable/empty motions JSON"
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": error_type,
                    "error_message": error_message,
                    "context": context,
                })
                if record is not None:
                    writer.append([record])
                else:
                    writer.append([])
            else:
                writer.append([record])
            if verbose:
                print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract motions from minutes documents via LLM"
    )
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (input_data.get("results")):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="file_url", force=args.force,
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
                               target_public_body=args.public_body)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()

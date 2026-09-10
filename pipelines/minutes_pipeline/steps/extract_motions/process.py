#!/usr/bin/env python3
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.llm_extract import extract_json

STEP_NAME = "extract_motions"

_SYSTEM_PROMPT = (
    "You extract the motions from Irish local-authority council meeting "
    "minutes. A motion is a formal proposal put to a vote (often starting "
    "'That the council…' or 'Proposed by…'). Return a JSON object with two "
    "keys: 'meeting_date' and 'motions'. 'meeting_date' is the ISO date "
    "(YYYY-MM-DD) of the meeting when it is stated in the document (a full "
    "calendar date, e.g. '8 July 2024' or '2024-07-08'), otherwise null. "
    "'motions' is a list of objects, each with string fields: motion_text "
    "(verbatim motion text), proposer (councillor or null), seconder "
    "(councillor or null), status_label (one of: carried, "
    "carried_as_amended, not_carried, withdrawn, deferred, not_recorded). "
    "Return no text outside the JSON object."
)


def build_user_prompt(record) -> str:
    return (
        f"Extract the motions from these minutes "
        f"(municipal district {record.get('municipal_district')}, "
        f"meeting date {record.get('meeting_date')}).\n\n"
        f"{record['text']}"
    )


def extract_one(record, api_fn=None):
    """Return the record with a 'motions' list (or None on failure) and a
    raw 'stated_date' passthrough of whatever date the LLM reported. Date
    *resolution* is the resolve_meeting_date step's job, not this one."""
    result = extract_json(_SYSTEM_PROMPT, build_user_prompt(record), api_fn=api_fn)
    if not isinstance(result, dict):
        return {**record, "stated_date": None, "motions": None}
    stated_date = result.get("meeting_date")
    motions = result.get("motions")
    if not isinstance(motions, list):
        return {**record, "stated_date": stated_date, "motions": None}
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
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": (type(exc).__name__ if exc else "MotionExtractionError"),
                    "error_message": (str(exc) if exc else
                                      "LLM returned unparseable/empty motions JSON"),
                    "context": {"file_url": file_url, "public_body_id": record["public_body_id"]
                                if record else None},
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

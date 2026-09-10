#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body, merge_replacing_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "canonicalize_motions"

CANONICAL_STATUSES = {
    "carried", "carried_as_amended", "not_carried", "withdrawn",
    "deferred", "not_recorded",
}

_STATUS_ALIASES = {
    "carried": "carried",
    "carried as amended": "carried_as_amended",
    "carried-as-amended": "carried_as_amended",
    "amended": "carried_as_amended",
    "not carried": "not_carried",
    "defeated": "not_carried",
    "lost": "not_carried",
    "withdrawn": "withdrawn",
    "deferred": "deferred",
}


def map_status(label) -> str:
    """Map a raw status_label to the closed set; unknown -> not_recorded.
    The caller logs the error — this function never raises."""
    if not isinstance(label, str):
        return "not_recorded"
    key = " ".join(label.strip().lower().split())
    if key in CANONICAL_STATUSES:
        return key
    if key in _STATUS_ALIASES:
        return _STATUS_ALIASES[key]
    return "not_recorded"


def _authority_map(authorities_data):
    """Map public_body_id -> {slug, name}."""
    out = {}
    for r in authorities_data.get("results", []):
        out[str(r["public_body_id"])] = {
            "slug": r["slug"], "name": r["name"],
        }
    return out


def canonicalize_records(input_records, authorities, body_id=None, errors_out=None):
    """Return (canonical_motions, errors). input_records are extract_motions
    records (each with a 'motions' list or None)."""
    canonical = []
    errors = errors_out if errors_out is not None else []
    meeting_state = {}

    for record in input_records:
        bid = record["public_body_id"]
        if body_id is not None and str(bid) != str(body_id):
            continue
        auth = authorities.get(str(bid))
        if auth is None:
            errors.append({
                "error_type": "UnknownAuthority",
                "error_message": f"no authority for public_body_id {bid}",
                "context": {"public_body_id": bid},
            })
            continue
        motions = record.get("motions")
        if not motions:            # None (failed LLM) or [] (empty document)
            errors.append({
                "error_type": "NoMotionsExtracted",
                "error_message": "document produced no motions",
                "context": {"public_body_id": bid, "file_url": record.get("file_url")},
            })
            continue
        meeting_date = record.get("meeting_date")
        if not meeting_date:
            errors.append({
                "error_type": "MissingMeetingDate",
                "error_message": "meeting_date unresolved; motion cannot get a stable id",
                "context": {"public_body_id": bid, "file_url": record.get("file_url")},
            })
            continue
        district = record.get("municipal_district")
        meeting_type = "council" if district is None else "municipal_district"
        meeting_key = (bid, district, meeting_date)
        state = meeting_state.setdefault(meeting_key, {"seq": 0, "seen_texts": set()})
        for motion in motions:
            raw = motion.get("motion_text") or ""
            norm = " ".join(raw.lower().split())
            if not norm or norm in state["seen_texts"]:
                continue  # duplicate within the meeting, or empty
            state["seen_texts"].add(norm)
            state["seq"] += 1
            status_label = map_status(motion.get("status_label"))
            if status_label == "not_recorded" and motion.get("status_label") not in (None, "not_recorded"):
                errors.append({
                    "error_type": "UnknownStatusLabel",
                    "error_message": f"unmapped status_label {motion.get('status_label')!r}",
                    "context": {"public_body_id": bid, "file_url": record.get("file_url")},
                })
            canonical.append({
                "motion_id": f"{auth['slug']}/{meeting_date}/m{state['seq']:03d}",
                "public_body_id": bid,
                "public_body_slug": auth["slug"],
                "public_body_name": auth["name"],
                "municipal_district": district,
                "meeting_date": meeting_date,
                "meeting_type": meeting_type,
                "source_file_url": record.get("file_url"),
                "motion_text": raw,
                "proposer": motion.get("proposer"),
                "seconder": motion.get("seconder"),
                "status": status_label,
            })

    return canonical, errors


def main():
    parser = argparse.ArgumentParser(
        description="Canonicalize extracted motions: status, date, id, dedupe"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)

    # Join slug/name from find_local_authorities (sibling step).
    la_path = step_dir.parent / "find_local_authorities" / "output.json"
    authorities = _authority_map(read_json(la_path))

    errors = []
    canonical, errors = canonicalize_records(
        input_data.get("results", []), authorities,
        body_id=args.public_body, errors_out=errors)

    # Shape-b merge-back for --public-body scoping.
    if args.public_body is not None and not args.force and output_path.exists():
        existing = read_json(output_path).get("results", [])
        canonical = merge_replacing_body(existing, canonical, args.public_body)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "total_records_output": len(canonical),
        },
        "results": canonical,
    })
    write_json(step_dir / "errors.json", errors)
    write_status(step_dir, len(canonical))
    print(f"Wrote {len(canonical)} canonical motions to {output_path}")


if __name__ == "__main__":
    main()

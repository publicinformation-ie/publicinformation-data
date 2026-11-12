#!/usr/bin/env python3
"""Step: extract_milestones — one record per interim milestone.

Reads `resolve_action_identity/output.json` and splits each action's
`original_deadline_milestones` prose with `milestones.split_milestones`. Pure
and deterministic: no model call, and the upstream file is never rewritten.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import append_errors, read_json, write_json, write_status

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from milestones import MilestoneRoundTripFailed, split_milestones  # noqa: E402

STEP_NAME = "extract_milestones"


def _record(action_id: str, ordinal: int, label, start, end, precision, text) -> dict:
    return {"milestone_id": f"{action_id}/m{ordinal}",
            "action_id": action_id,
            "ordinal": ordinal,
            "due_label": label or "",
            "due_start": start or "",
            "due_end": end or "",
            "due_precision": precision or "",
            "milestone_text": text}


def build_milestones(actions: list) -> tuple:
    """`(records, errors)` for every action, in input order."""
    records, errors = [], []
    for action in actions:
        action_id = action["action_id"]
        prose = action.get("original_deadline_milestones")
        try:
            pieces = split_milestones(prose)
        except MilestoneRoundTripFailed:
            errors.append({
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "MilestoneRoundTripFailed",
                "error_message": "Milestone pieces did not re-join to the "
                                 "input; kept as one undated milestone.",
                "context": {"action_id": action_id,
                            "original_deadline_milestones": prose}})
            text = " ".join(str(prose or "").split())
            records.append(_record(action_id, 1, "", None, None, None, text))
            continue
        for piece in pieces:
            records.append(_record(action_id, piece.ordinal, piece.due_label,
                                   piece.due_start, piece.due_end,
                                   piece.due_precision, piece.text))
    return records, errors


def main():
    parser = argparse.ArgumentParser(
        description="Split interim-milestone prose into one record per milestone")
    parser.add_argument("--input", required=True,
                        help="Path to resolve_action_identity/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true",
                        help="Accepted for runner compatibility; this step "
                             "always rebuilds the whole table")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    write_json(step_dir / "errors.json", [])

    actions = read_json(Path(args.input)).get("actions", [])
    records, errors = build_milestones(actions)

    append_errors(step_dir, errors)
    write_json(output_path, {
        "metadata": {"step": STEP_NAME,
                     "generated_at": datetime.now(timezone.utc).isoformat(),
                     "milestone_count": len(records)},
        "milestones": records,
    })
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} milestone(s) to {output_path}")


if __name__ == "__main__":
    main()

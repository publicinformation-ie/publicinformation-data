#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import read_json, write_json, write_status, append_errors

STEP_NAME = "normalize_cso_fields"

LEGAL_STATUS_MAP = {
    "Commercial Financial Corporation under the aegis of Department": {
        "is_commercial": True, "is_financial": True,
        "aegis": "Department", "legal_entity_type": "Corporation",
    },
    "Commercial Non-Financial Corporation under the aegis of Department": {
        "is_commercial": True, "is_financial": False,
        "aegis": "Department", "legal_entity_type": "Corporation",
    },
    "Commercial Non-Financial Corporation under the aegis of Local Government": {
        "is_commercial": True, "is_financial": False,
        "aegis": "Local Government", "legal_entity_type": "Corporation",
    },
    "Non-Commercial Agency under the aegis of Central Government": {
        "is_commercial": False, "is_financial": None,
        "aegis": "Central Government", "legal_entity_type": "Agency",
    },
    "Non-Commercial Agency under the aegis of Department": {
        "is_commercial": False, "is_financial": None,
        "aegis": "Department", "legal_entity_type": "Agency",
    },
    "Non-Commercial Agency under the aegis of Local Government": {
        "is_commercial": False, "is_financial": None,
        "aegis": "Local Government", "legal_entity_type": "Agency",
    },
    "Extra-Budgetary Fund": {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Extra-Budgetary Fund",
    },
    "Social Security Fund": {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Social Security Fund",
    },
    "Vote": {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Vote",
    },
    "Vote 46": {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Vote",
    },
}

_NULL_LEGAL = {"is_commercial": None, "is_financial": None, "aegis": None, "legal_entity_type": None}
_NULL_NACE = {
    "nace_section": None, "nace_division": None, "nace_group": None,
    "nace_class": None, "nace_section_name": None, "nace_class_name": None,
}


def parse_legal_status(legal_status):
    """Return (fields_dict, is_unrecognised). is_unrecognised=True only for non-null unknown values."""
    if legal_status is None:
        return dict(_NULL_LEGAL), False
    mapped = LEGAL_STATUS_MAP.get(legal_status)
    if mapped is None:
        return dict(_NULL_LEGAL), True
    return dict(mapped), False


def parse_nace_code(nace_code, lookup):
    """Return (fields_dict, is_malformed). is_malformed=True only for non-null malformed codes."""
    if nace_code is None:
        return dict(_NULL_NACE), False
    if len(nace_code) != 5 or not nace_code[0].isalpha() or not nace_code[1:].isdigit():
        return dict(_NULL_NACE), True
    section = nace_code[0]
    class_code = nace_code[1:]
    return {
        "nace_section": section,
        "nace_division": class_code[:2],
        "nace_group": class_code[:3],
        "nace_class": class_code,
        "nace_section_name": lookup.get("sections", {}).get(section),
        "nace_class_name": lookup.get("classes", {}).get(class_code),
    }, False


def normalize_bodies(bodies, lookup):
    """Add 10 normalized fields to each body. Returns (enriched_bodies, errors_list)."""
    enriched = []
    errors = []
    for body in bodies:
        ls_fields, ls_unrecognised = parse_legal_status(body.get("legal_status"))
        nace_fields, nace_malformed = parse_nace_code(body.get("nace_code"), lookup)
        if ls_unrecognised:
            errors.append({
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "UnrecognisedLegalStatus",
                "error_message": f"Unknown legal_status: {body.get('legal_status')!r}",
                "context": {"public_body_id": body.get("public_body_id")},
            })
        if nace_malformed:
            errors.append({
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "MalformedNaceCode",
                "error_message": f"Malformed nace_code: {body.get('nace_code')!r}",
                "context": {"public_body_id": body.get("public_body_id")},
            })
        enriched.append({**body, **ls_fields, **nace_fields})
    return enriched, errors


def main(step_dir=None):
    parser = argparse.ArgumentParser(description="Normalize legal_status and nace_code fields")
    parser.add_argument("--input", required=True, help="Path to parse_cso_bodies/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body")
    args = parser.parse_args()

    if step_dir is None:
        step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    lookup_path = step_dir / "nace_lookup.json"

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    input_data = read_json(args.input)
    bodies = input_data.get("public_bodies", [])
    lookup = read_json(lookup_path)

    enriched, errors = normalize_bodies(bodies, lookup)

    errors_path = step_dir / "errors.json"
    write_json(errors_path, [])
    if errors:
        append_errors(step_dir, errors)

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": enriched,
    }
    write_json(output_path, output)
    write_status(step_dir, len(enriched))
    print(f"Wrote {len(enriched)} public bodies to {output_path} ({len(errors)} errors)")


if __name__ == "__main__":
    main()

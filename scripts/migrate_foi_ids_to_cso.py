#!/usr/bin/env python3
"""One-time, idempotent migration of FOI/disclosure data onto canonical CSO body IDs.

Background
----------
The FOI pipeline originally numbered public bodies by gov.ie scrape order. Later
the CSO pipeline became the canonical body register (``find_public_bodies`` now
ingests CSO bodies, numbered alphabetically). Both ID ranges are 1000-1882, so
the old FOI ``public_body_id`` values silently collide with *different* canonical
CSO bodies. The disclosure subsystem was never remapped.

This script rewrites every disclosure step output (and the hand-maintained
override files) so that each record's ``public_body_id`` and ``name`` match the
canonical CSO body, resolved by *folded name*. It is idempotent: a record that is
already canonical maps to itself, and a second full run reports zero remaps and
zero dedup removals.

Usage
-----
    PYTHONPATH=src python scripts/migrate_foi_ids_to_cso.py [--dry-run]

``--dry-run`` reports the per-file plan without writing any file.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from lib.file_utils import read_json, write_json

# Repo root = parent of the scripts/ directory this file lives in.
REPO_ROOT = Path(__file__).resolve().parent.parent
STEPS_DIR = REPO_ROOT / "pipelines" / "foi_pipeline" / "steps"
CANONICAL_BODIES_PATH = STEPS_DIR / "find_public_bodies" / "output.json"

# Disclosure step outputs carrying public_body_id + name to remap.
TARGET_STEPS = [
    "find_foi_pages",
    "check_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
    "find_disclosure_files",
    "verify_disclosure_files",
    "transform_disclosure_files",
    "normalize_disclosure_cells",
    "extract_disclosures_detect_header_row",
    "extract_disclosures_normalize_header",
    "extract_disclosures_normalize_rows",
    "extract_disclosures_canonicalize",
    "extract_disclosures_canonicalize_rows",
]

# Hand-maintained override files (flat list of records).
OVERRIDE_STEPS = [
    "find_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
    "extract_disclosures_normalize_header",
]

# Stale folded name -> canonical folded name. The canonical folded name is then
# resolved to an id through the crosswalk built from the canonical body table, so
# the ids are never hardcoded here. The comments record the expected canonical id
# (verified at build time against the live crosswalk; a mismatch aborts the run).
ALIASES = {
    "greyhound racing ireland gri": "rasaiocht con eireann",                       # -> 1679
    "bord bia irish food board": "bord bia",                                        # -> 1052
    "fiosru the office of the police ombudsman": "fiosru oifig an ombudsman poilineachta",  # -> 1298
    "competition and consumer protection commission ccpc": "competition and consumer protection commission",  # -> 1156
    "data protection commission": "the data protection commission dpc",             # -> 1782
}

# Expected canonical ids for the alias targets, asserted at crosswalk-build time
# so an unexpected re-fold of a canonical name fails loudly instead of silently
# attaching records to the wrong body.
EXPECTED_ALIAS_IDS = {
    "rasaiocht con eireann": 1679,
    "bord bia": 1052,
    "fiosru oifig an ombudsman poilineachta": 1298,
    "competition and consumer protection commission": 1156,
    "the data protection commission dpc": 1782,
}


class MigrationError(Exception):
    """Raised when a record name cannot be resolved to a canonical CSO id."""


# --------------------------------------------------------------------------- #
# Pure, importable, file-I/O-free core logic
# --------------------------------------------------------------------------- #

def fold(name: str) -> str:
    """Normalise a body name for matching.

    Lowercase, NFKD-strip accents (combining marks removed), replace each run of
    non-alphanumerics with a single space, collapse whitespace, strip.
    """
    if name is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(name))
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = no_accents.lower()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    return spaced.strip()


def build_crosswalk(canonical_bodies: list) -> tuple[dict, dict]:
    """Build ``folded name -> canonical id`` and ``canonical id -> name`` maps.

    ``canonical_bodies`` is a list of dicts each with ``name`` and
    ``public_body_id`` (the records under ``public_bodies`` in
    find_public_bodies/output.json).

    Verifies that every ALIAS target folds to its expected canonical id; raises
    MigrationError if a target is missing or resolves to an unexpected id.
    """
    name_to_id: dict[str, int] = {}
    id_to_name: dict[int, str] = {}
    for body in canonical_bodies:
        name = body.get("name")
        pid = body.get("public_body_id")
        if name is None or pid is None:
            continue
        name_to_id[fold(name)] = pid
        id_to_name[pid] = name

    # Loudly verify alias targets resolve as the plan predicts.
    for target_folded, expected_id in EXPECTED_ALIAS_IDS.items():
        got = name_to_id.get(target_folded)
        if got is None:
            raise MigrationError(
                f"ALIAS target {target_folded!r} did not fold to any canonical "
                f"body name in the crosswalk (expected id {expected_id})."
            )
        if got != expected_id:
            raise MigrationError(
                f"ALIAS target {target_folded!r} resolved to id {got}, "
                f"expected {expected_id}."
            )

    return name_to_id, id_to_name


def resolve_name(name: str, name_to_id: dict) -> int:
    """Resolve a record name to a canonical CSO id.

    Tries a direct folded-name match first, then the ALIAS table. Raises
    MigrationError if the name cannot be resolved.
    """
    folded = fold(name)
    if folded in name_to_id:
        return name_to_id[folded]
    if folded in ALIASES:
        target = ALIASES[folded]
        if target in name_to_id:
            return name_to_id[target]
        raise MigrationError(
            f"ALIAS for {name!r} (folded {folded!r}) points at {target!r}, "
            f"which is not in the canonical crosswalk."
        )
    raise MigrationError(
        f"Could not resolve name {name!r} (folded {folded!r}) to a canonical "
        f"CSO id; no direct match and no alias."
    )


def remap_record(record: dict, name_to_id: dict, id_to_name: dict) -> bool:
    """Rewrite ``public_body_id`` and ``name`` of one record in place.

    Returns True if the record changed, False if it was already canonical.
    Records without both ``public_body_id`` and ``name`` are left untouched.
    """
    if not isinstance(record, dict):
        return False
    if "public_body_id" not in record or "name" not in record:
        return False

    canonical_id = resolve_name(record["name"], name_to_id)
    canonical_name = id_to_name[canonical_id]

    changed = (
        record["public_body_id"] != canonical_id
        or record["name"] != canonical_name
    )
    record["public_body_id"] = canonical_id
    record["name"] = canonical_name
    return changed


def remap_records(records: list, name_to_id: dict, id_to_name: dict) -> int:
    """Remap every record in a list in place; return count changed."""
    changed = 0
    for record in records:
        if remap_record(record, name_to_id, id_to_name):
            changed += 1
    return changed


def dedup_disclosure_pages(records: list) -> list:
    """One record per public_body_id; prefer ``overridden``, else max confidence."""
    best: dict = {}
    order: list = []
    for rec in records:
        pid = rec.get("public_body_id")
        if pid not in best:
            best[pid] = rec
            order.append(pid)
            continue
        current = best[pid]
        if _page_rank(rec) > _page_rank(current):
            best[pid] = rec
    return [best[pid] for pid in order]


# Categorical confidence ordering used by find_disclosure_pages records.
_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0}


def _page_rank(rec: dict) -> tuple:
    """Sort key: overridden wins, then higher confidence.

    ``confidence`` may be a categorical string (high/medium/low/none), a number,
    or absent; all are normalised to a comparable numeric rank.
    """
    overridden = 1 if rec.get("overridden") else 0
    confidence = rec.get("confidence")
    if isinstance(confidence, str):
        conf_rank = _CONFIDENCE_RANK.get(confidence.lower(), 0)
    elif isinstance(confidence, (int, float)):
        conf_rank = confidence
    else:
        conf_rank = 0
    return (overridden, conf_rank)


def dedup_disclosure_files(records: list) -> list:
    """Unique by (public_body_id, file_url, disclosure_page_url); first wins."""
    seen = set()
    out = []
    for rec in records:
        key = (
            rec.get("public_body_id"),
            rec.get("file_url"),
            rec.get("disclosure_page_url"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# File-level orchestration
# --------------------------------------------------------------------------- #

def _process_results_file(path: Path, name_to_id, id_to_name) -> tuple[dict, int, int]:
    """Remap records under the top-level ``results`` list of an output.json.

    Returns (data, remapped, total). Caller decides whether to write.
    """
    data = read_json(path)
    records = data.get("results", []) if isinstance(data, dict) else []
    remapped = remap_records(records, name_to_id, id_to_name)
    return data, remapped, len(records)


def _process_override_file(path: Path, name_to_id, id_to_name) -> tuple[list, int, int]:
    """Remap a flat-list override.json. Returns (data, remapped, total)."""
    data = read_json(path)
    records = data if isinstance(data, list) else []
    remapped = remap_records(records, name_to_id, id_to_name)
    return data, remapped, len(records)


def run(dry_run: bool = False) -> int:
    """Execute the migration. Returns process exit code (0 = success)."""
    canonical = read_json(CANONICAL_BODIES_PATH)
    bodies = canonical.get("public_bodies", []) if isinstance(canonical, dict) else []
    if not bodies:
        print(f"ERROR: no canonical bodies found in {CANONICAL_BODIES_PATH}", file=sys.stderr)
        return 1

    name_to_id, id_to_name = build_crosswalk(bodies)
    print(f"Crosswalk: {len(name_to_id)} canonical body names "
          f"({len(id_to_name)} ids). {len(ALIASES)} aliases active.")
    print(f"Mode: {'DRY-RUN (no writes)' if dry_run else 'WRITE'}\n")

    print("Target step outputs:")
    for step in TARGET_STEPS:
        path = STEPS_DIR / step / "output.json"
        if not path.exists():
            print(f"  - {step}: MISSING (skipped)")
            continue
        data, remapped, total = _process_results_file(path, name_to_id, id_to_name)

        dedup_note = ""
        if step == "find_disclosure_pages":
            before = len(data["results"])
            data["results"] = dedup_disclosure_pages(data["results"])
            dedup_note = f"  [dedup pages: {before} -> {len(data['results'])}]"
        elif step == "find_disclosure_files":
            before = len(data["results"])
            data["results"] = dedup_disclosure_files(data["results"])
            dedup_note = f"  [dedup files: {before} -> {len(data['results'])}]"

        if not dry_run:
            write_json(path, data)
        print(f"  - {step}: remapped {remapped}/{total}{dedup_note}")

    print("\nOverride files:")
    for step in OVERRIDE_STEPS:
        path = STEPS_DIR / step / "override.json"
        if not path.exists():
            print(f"  - {step}/override.json: MISSING (skipped)")
            continue
        data, remapped, total = _process_override_file(path, name_to_id, id_to_name)
        if not dry_run:
            write_json(path, data)
        print(f"  - {step}/override.json: remapped {remapped}/{total}")

    print("\nDone." + (" (dry-run, nothing written)" if dry_run else ""))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="One-time, idempotent FOI->CSO public_body_id remap.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the per-file plan without writing any file.",
    )
    args = parser.parse_args(argv)
    try:
        return run(dry_run=args.dry_run)
    except MigrationError as exc:
        print(f"MIGRATION ABORTED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import read_json, write_json, write_status, IncrementalWriter
from lib.body_matching import normalise, best_match, load_candidates

STEP_NAME = "match_public_bodies"
CANDIDATES_PATH = "pipelines/cso_pipeline/steps/resolve_website_urls/output.json"


def entity_type_flag(entity_type, canonical_name: str):
    """Soft cross-check of statespend's coarse entity_type against the
    matched canonical body's name (§5.4 of the design doc). Returns a
    human-readable reason string on mismatch, None when consistent or when
    no rule exists for the type. Never fatal — the flag lands in
    match_log.json for review instead of failing the run."""
    if entity_type is None:
        return None
    name = canonical_name.lower()
    if entity_type == "local_authority" and "council" not in name:
        return (f"statespend entity_type=local_authority but canonical name "
                f"has no 'Council': {canonical_name!r}")
    if entity_type == "department" and not name.startswith("department of"):
        return (f"statespend entity_type=department but canonical name is not "
                f"a 'Department of …': {canonical_name!r}")
    if entity_type == "etb" and "education and training board" not in name:
        return (f"statespend entity_type=etb but canonical name is not an "
                f"'Education and Training Board': {canonical_name!r}")
    return None


def process(input_data, candidates, attrs_by_id, writer, verbose=False):
    """attrs_by_id: {public_body_id: canonical name} — used only to enrich
    match_log.json so near-misses are auditable without a re-crawl."""
    match_log = []
    for record in input_data.get("results", []):
        sid = record["statespend_id"]
        if writer.is_processed(sid):
            continue
        norm = normalise(record["statespend_name"])
        matched_id, score = best_match(norm, candidates)
        entry = {
            "statespend_id": sid,
            "statespend_name": record["statespend_name"],
            "normalised": norm,
            "matched_public_body_id": matched_id,
            "match_score": round(score, 4),
        }
        if matched_id is not None:
            canonical_name = attrs_by_id.get(matched_id)
            entry["matched_canonical_name"] = canonical_name
            flag = entity_type_flag(record.get("statespend_entity_type"), canonical_name)
            if flag:
                entry["entity_type_flag"] = flag
        match_log.append(entry)
        writer.append([{**record, "public_body_id": matched_id}])
        if verbose:
            print(".", end="", flush=True)
    return match_log


def load_attrs(candidates_path: Path) -> dict:
    """{public_body_id: name} for enriching the match log."""
    data = read_json(candidates_path)
    bodies = data.get("results") or data.get("public_bodies", [])
    return {b["public_body_id"]: b["name"] for b in bodies}


def main():
    parser = argparse.ArgumentParser(
        description="Fuzzy-match statespend.ie bodies against public bodies by name"
    )
    add_common_args(parser)
    parser.add_argument("--candidates", default=None,
                        help="Path to resolve_website_urls output.json "
                             f"(defaults to <repo_root>/{CANDIDATES_PATH})")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    pipeline_dir = step_dir.parent.parent  # pipelines/statespend_pipeline/
    repo_root = pipeline_dir.parent.parent
    output_path = Path(args.output)
    candidates_path = Path(args.candidates) if args.candidates else repo_root / CANDIDATES_PATH

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    if not candidates_path.exists():
        print(f"Fatal: candidates file not found at {candidates_path}\n"
              f"Run cso_pipeline through resolve_website_urls first.", file=sys.stderr)
        sys.exit(1)
    candidates = load_candidates(candidates_path)
    attrs_by_id = load_attrs(candidates_path)

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="statespend_id", force=args.force)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    match_log = process(input_data, candidates, attrs_by_id, writer, verbose=args.verbose)
    write_json(step_dir / "match_log.json", match_log)

    flagged = sum(1 for e in match_log if e.get("entity_type_flag"))
    if flagged:
        print(f"Note: {flagged} match(es) flagged by the entity_type cross-check "
              f"— see match_log.json")

    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()

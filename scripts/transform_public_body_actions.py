#!/usr/bin/env python3
"""Publish the Public Body Actions dataset from actions_pipeline output.

Three tables: what each plan committed to, what each progress report later
said about it, and how actions relate to one another.

This script is also where the dataset's validation invariants live, because it
is the first place the three tables are assembled together — and it is the main
defence against a silent mis-parse of a 50-page annex. A failed invariant
aborts publication outright; it never writes a partial dataset. The
expectations it checks against are *declared data*, read from documents.yml,
not constants: hard-coding "91 actions" or "58/28/5" here would make the check
unmaintainable the moment a second body is added, and would silently stop
applying if the corpus changed.

Deliberately not derived: no lineage_id (consumers traverse the link table),
and no slippage column. `actions` carries the original deadline, each
observation carries the reported one, both normalised through the same parser,
so slippage is one subtraction away without the dataset baking in a judgement
about what counts as a slip.

Usage: uv run python scripts/transform_public_body_actions.py
"""
import csv
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pipelines" / "document_pipeline"))

from src.lib.body_refs import BASE_URI, slugify
from src.lib.dataset_publish import render_csv, render_jsonld, stamp_if_changed
from src.lib.date_parse import PRECISIONS

RESOLVED_PATH = "pipelines/actions_pipeline/steps/resolve_action_identity/output.json"
RELATIONSHIPS_PATH = "pipelines/actions_pipeline/steps/extract_relationships/output.json"
FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
STATUS_VOCABULARY_PATH = "public/vocabularies/action-status.csv"
RELATIONSHIP_VOCABULARY_PATH = "public/vocabularies/action-relationship.csv"

OUTPUT_DIR = "public/v1.0.0/public-body-actions"
LATEST_DIR = "public/latest/public-body-actions"
TTL_PATH = "public/catalog/dataset-public-body-actions.ttl"

ACTIONS_CSV = "actions.csv"
OBSERVATIONS_CSV = "action-status-observations.csv"
RELATIONSHIPS_CSV = "action-relationships.csv"
JSONLD = "public-body-actions.jsonld"

ACTION_FIELDS = [
    "action_id", "public_body_id", "plan_slug", "plan_title", "source_url",
    "action_number", "action_text", "original_deadline_raw",
    "original_deadline_start", "original_deadline_end",
    "original_deadline_precision", "original_deadline_confidence",
    "original_timeline_raw", "lead", "support", "output", "source_page",
    "source_ref",
]
OBSERVATION_FIELDS = [
    "action_id", "report_slug", "report_title", "as_of", "status",
    "reported_deadline_raw", "reported_deadline_start", "reported_deadline_end",
    "reported_deadline_precision", "progress_text", "asi", "source_page",
    "source_ref",
]
RELATIONSHIP_FIELDS = [
    "from_action_id", "to_action_id", "to_plan_hint", "to_action_number",
    "relationship", "family", "method", "asserted_in", "evidence",
]

CONFIDENCES = ("stated", "interpreted")


class InvariantViolation(Exception):
    """One or more §12 invariants failed. Nothing is written."""


# --------------------------------------------------------------------------
# Row building
# --------------------------------------------------------------------------


def _cell(value):
    """None renders as an empty CSV cell, never the string "None"."""
    return "" if value is None else value


def _rows(records, fields):
    return [{field: _cell(record.get(field)) for field in fields}
            for record in records]


def build_action_rows(actions):
    return _rows(actions, ACTION_FIELDS)


def build_observation_rows(observations):
    return _rows(observations, OBSERVATION_FIELDS)


def build_relationship_rows(relationships):
    return _rows(relationships, RELATIONSHIP_FIELDS)


# --------------------------------------------------------------------------
# Invariants (spec §12)
# --------------------------------------------------------------------------


def check_invariants(actions, observations, relationships, expectations,
                     status_terms, relationship_terms) -> list:
    """Every violation, as a human-readable string. Empty means publishable.

    Returns all violations rather than raising on the first: a release that
    fails two checks should show both, so one run of the pipeline tells a human
    everything that is wrong.
    """
    violations = []
    action_ids = {action["action_id"] for action in actions}

    # 1. Action count, where the plan declares one.
    counts = {}
    for action in actions:
        counts[action["plan_slug"]] = counts.get(action["plan_slug"], 0) + 1
    for slug, expectation in expectations.items():
        expected = expectation.get("expected_action_count")
        if expected is None:
            continue
        actual = counts.get(slug, 0)
        if actual != expected:
            violations.append(
                f"{slug}: expected_action_count is {expected} but {actual} "
                f"action(s) were extracted")

    # 2. Published split, where the report declares one.
    tallies = {}
    for observation in observations:
        report = tallies.setdefault(observation["report_slug"], {})
        report[observation["status"]] = report.get(observation["status"], 0) + 1
    for slug, expectation in expectations.items():
        expected = expectation.get("expected_status_counts")
        if expected is None:
            continue
        actual = tallies.get(slug, {})
        if actual != expected:
            violations.append(
                f"StatusCountMismatch {slug}: the report publishes {expected} "
                f"but {actual} was extracted")

    # 3. Referential integrity.
    for observation in observations:
        if observation["action_id"] not in action_ids:
            violations.append(
                f"observation {observation['action_id']}/"
                f"{observation['report_slug']}: action_id resolves to no action")
    for edge in relationships:
        if edge["from_action_id"] not in action_ids:
            violations.append(
                f"relationship from_action_id {edge['from_action_id']} "
                f"resolves to no action")
        if edge["to_action_id"] is not None and edge["to_action_id"] not in action_ids:
            violations.append(
                f"relationship to_action_id {edge['to_action_id']} is non-null "
                f"but resolves to no action")

    # 4. Vocabulary closure.
    for observation in observations:
        if observation["status"] not in status_terms:
            violations.append(
                f"status {observation['status']!r} is not in the action-status "
                f"vocabulary")
    for edge in relationships:
        if edge["relationship"] not in relationship_terms:
            violations.append(
                f"relationship {edge['relationship']!r} is not in the "
                f"action-relationship vocabulary")

    # 5. Observation uniqueness.
    seen = set()
    for observation in observations:
        key = (observation["action_id"], observation["report_slug"])
        if key in seen:
            violations.append(
                f"observation {key} is not unique on (action_id, report_slug)")
        seen.add(key)

    # 6. Deadline comparability — both sides drawn from the same enumeration.
    for action in actions:
        precision = action["original_deadline_precision"]
        if precision is not None and precision not in PRECISIONS:
            violations.append(
                f"{action['action_id']}: original_deadline_precision "
                f"{precision!r} is outside {PRECISIONS}")
    for observation in observations:
        precision = observation["reported_deadline_precision"]
        if precision is not None and precision not in PRECISIONS:
            violations.append(
                f"observation {observation['action_id']}/"
                f"{observation['report_slug']}: reported_deadline_precision "
                f"{precision!r} is outside {PRECISIONS}")

    # 7. Confidence closure — null if and only if there is no parsed deadline.
    for action in actions:
        confidence = action["original_deadline_confidence"]
        if confidence is not None and confidence not in CONFIDENCES:
            violations.append(
                f"{action['action_id']}: original_deadline_confidence "
                f"{confidence!r} is outside {CONFIDENCES}")
        has_deadline = action["original_deadline_start"] is not None
        if has_deadline != (confidence is not None):
            violations.append(
                f"{action['action_id']}: original_deadline_confidence must be "
                f"null if and only if original_deadline_start is null "
                f"(confidence={confidence!r}, start="
                f"{action['original_deadline_start']!r})")

    return violations


# --------------------------------------------------------------------------
# JSON-LD
# --------------------------------------------------------------------------


def action_uri(action) -> str:
    """A path-safe URI. `action_id` contains a `#`, which is a fragment
    delimiter in a URI, so the identifier is re-expressed as a path here and
    the raw key is published alongside it as `action_id`."""
    return f"{BASE_URI}/action/{action['plan_slug']}/{action['action_number']}"


def transform_to_jsonld(actions, observations, relationships,
                        body_slug_lookup=None) -> dict:
    body_slug_lookup = body_slug_lookup or {}
    uris = {action["action_id"]: action_uri(action) for action in actions}
    graph = []

    for action in actions:
        node = {"@id": uris[action["action_id"]], "@type": "act:Action"}
        slug = body_slug_lookup.get(action["public_body_id"])
        node["public_body"] = f"{BASE_URI}/body/{slug}" if slug else None
        node.update({field: action.get(field) for field in ACTION_FIELDS})
        graph.append(node)

    for observation in observations:
        action_id = observation["action_id"]
        node = {"@id": f"{uris[action_id]}/observation/{observation['report_slug']}",
                "@type": "act:ActionStatusObservation",
                "action": uris[action_id]}
        node.update({field: observation.get(field) for field in OBSERVATION_FIELDS})
        graph.append(node)

    for index, edge in enumerate(relationships):
        node = {"@id": f"{BASE_URI}/action-relationship/{index + 1}",
                "@type": "act:ActionRelationship",
                "from_action": uris[edge["from_action_id"]]}
        node.update({field: edge.get(field) for field in RELATIONSHIP_FIELDS})
        graph.append(node)

    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "act": f"{BASE_URI}/ns/action#",
            "dct": "http://purl.org/dc/terms/",
            "public_body": {"@id": "act:publicBody", "@type": "@id"},
            "action": {"@id": "act:action", "@type": "@id"},
            "from_action": {"@id": "act:fromAction", "@type": "@id"},
        },
        "@graph": graph,
    }


# --------------------------------------------------------------------------
# Publication
# --------------------------------------------------------------------------


def copy_to_latest():
    """Copy the versioned directory to latest/ as a build-time snapshot.

    Not a symlink: Codeberg Pages and various git checkout paths don't
    reliably serve or preserve them. This also sweeps the committed
    csv-metadata.json and README.md into latest/ alongside the payloads.
    """
    shutil.copytree(OUTPUT_DIR, LATEST_DIR, dirs_exist_ok=True)


def publish_all(actions, observations, relationships, expectations,
                status_terms, relationship_terms, body_slug_lookup=None,
                output_dir=Path(OUTPUT_DIR), ttl_path=Path(TTL_PATH)) -> bool:
    """Assert every invariant, then write. Returns True if content changed."""
    violations = check_invariants(actions, observations, relationships,
                                  expectations, status_terms, relationship_terms)
    if violations:
        raise InvariantViolation(
            f"{len(violations)} validation invariant(s) failed; nothing "
            f"written:\n  - " + "\n  - ".join(violations))

    output_dir = Path(output_dir)
    paths = {
        output_dir / ACTIONS_CSV: render_csv(ACTION_FIELDS,
                                             build_action_rows(actions)),
        output_dir / OBSERVATIONS_CSV: render_csv(OBSERVATION_FIELDS,
                                                  build_observation_rows(observations)),
        output_dir / RELATIONSHIPS_CSV: render_csv(RELATIONSHIP_FIELDS,
                                                   build_relationship_rows(relationships)),
        output_dir / JSONLD: render_jsonld(
            transform_to_jsonld(actions, observations, relationships,
                                body_slug_lookup)),
    }
    # One call covering every payload: stamp_if_changed takes a list, so the
    # three CSVs and the JSON-LD share a single change-detection decision and
    # a single dct:modified stamp.
    return stamp_if_changed(Path(ttl_path), list(paths), paths)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def load_expectations() -> dict:
    """doc_slug -> the count expectations that document declares."""
    from documents import load_documents
    return {doc["doc_slug"]: {
        "expected_action_count": doc.get("expected_action_count"),
        "expected_status_counts": doc.get("expected_status_counts"),
    } for doc in load_documents()}


def load_vocabulary(path) -> set:
    with open(path, newline="", encoding="utf-8") as f:
        return {row["notation"] for row in csv.DictReader(f)}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(RESOLVED_PATH) as f:
        resolved = json.load(f)
    with open(RELATIONSHIPS_PATH) as f:
        relationships = json.load(f)["relationships"]
    with open(FIND_PUBLIC_BODIES_PATH) as f:
        public_bodies = json.load(f)["public_bodies"]

    actions = resolved["actions"]
    observations = resolved["observations"]
    body_slug_lookup = {b["public_body_id"]: slugify(b["name"])
                        for b in public_bodies}

    changed = publish_all(
        actions, observations, relationships,
        load_expectations(),
        load_vocabulary(STATUS_VOCABULARY_PATH),
        load_vocabulary(RELATIONSHIP_VOCABULARY_PATH),
        body_slug_lookup=body_slug_lookup)

    summary = (f"{len(actions)} action(s), {len(observations)} observation(s), "
               f"{len(relationships)} relationship(s)")
    if changed:
        copy_to_latest()
        print(f"Published {summary} (content changed, dct:modified updated)")
    else:
        print(f"Published {summary} (no content change, dct:modified untouched)")


if __name__ == "__main__":
    main()

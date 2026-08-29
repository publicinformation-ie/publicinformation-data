"""Loader for action_relationships.yml — the hand-curated link table.

Validated strictly and loudly, the way documents.yml is, and for the same
reason: it is a hand-authored input that asserts published facts about how two
commitments relate. A malformed entry here would publish a claim the source
documents never made.

Renumbering can only ever arrive this way, because no document in the corpus
states it machine-readably. The schema and validation exist from day one so
that recording a renumbering later is a data addition, not a migration.
"""
from pathlib import Path

import yaml

RELATIONSHIPS_PATH = Path(__file__).parent / "action_relationships.yml"

# notation -> family. Only lineage edges are valid for reconstructing an
# action's history across plan editions; `complements` does not imply
# continuity, and publishing the family as data is what stops each consumer
# deciding that for themselves and silently splicing two unrelated commitments
# into one timeline.
VOCABULARY = {
    "renumbered_as": "lineage",
    "supersedes": "lineage",
    "split_into": "lineage",
    "merged_into": "lineage",
    "carried_forward_to": "lineage",
    "complements": "reference",
    "references": "reference",
}


class InvalidRelationshipFile(ValueError):
    """A malformed curated relationship file. Process-fatal."""


def _split_action_id(action_id: str):
    plan_slug, _, number = str(action_id).partition("#")
    return plan_slug, (number or None)


def load_relationships(path, known_action_ids) -> list:
    """Parse and validate the curated file into published edge records.

    `path` may be None or a missing file — an absent curated file is valid and
    means no curated edges.
    """
    if path is None:
        return []
    path = Path(path)
    if not path.exists():
        return []

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise InvalidRelationshipFile(f"{path} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise InvalidRelationshipFile(f"{path} must be a mapping")

    entries = raw.get("relationships")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise InvalidRelationshipFile(f"{path} 'relationships' must be a list")

    edges = []
    seen = set()
    for index, entry in enumerate(entries):
        where = f"{path} entry {index}"
        if not isinstance(entry, dict):
            raise InvalidRelationshipFile(f"{where} is not a mapping")

        source = entry.get("from")
        if not source:
            raise InvalidRelationshipFile(f"{where} is missing 'from'")
        if source not in known_action_ids:
            raise InvalidRelationshipFile(
                f"{where} has from {source!r}, which resolves to no action")

        term = entry.get("relationship")
        if term not in VOCABULARY:
            raise InvalidRelationshipFile(
                f"{where} has relationship {term!r}; must be one of "
                f"{sorted(VOCABULARY)}")

        external = bool(entry.get("external"))
        target = entry.get("to")
        if external:
            if target:
                raise InvalidRelationshipFile(
                    f"{where} is marked external but also sets 'to' {target!r}")
            hint = entry.get("to_plan_hint")
            if not hint:
                raise InvalidRelationshipFile(
                    f"{where} is external and must set 'to_plan_hint'")
            number = entry.get("to_action_number")
            number = None if number is None else str(number)
            target_id = None
        else:
            if not target:
                raise InvalidRelationshipFile(
                    f"{where} must set 'to', or set external: true")
            if target == source:
                raise InvalidRelationshipFile(f"{where} is a self edge on {source!r}")
            if target not in known_action_ids:
                raise InvalidRelationshipFile(
                    f"{where} has to {target!r}, which resolves to no action; "
                    f"mark it external: true if the target plan is outside the corpus")
            target_id = target
            hint, number = _split_action_id(target)

        triple = (source, target_id, entry.get("to_plan_hint"),
                  None if target_id else str(entry.get("to_action_number")), term)
        if triple in seen:
            raise InvalidRelationshipFile(
                f"{where} is a duplicate (from, to, relationship) triple")
        seen.add(triple)

        evidence = entry.get("evidence")
        if not evidence:
            raise InvalidRelationshipFile(
                f"{where} is missing 'evidence'; a curated claim must say what "
                f"it is based on")

        edges.append({
            "from_action_id": source,
            "to_action_id": target_id,
            "to_plan_hint": hint,
            "to_action_number": number,
            "relationship": term,
            "family": VOCABULARY[term],
            "method": "curated",
            "asserted_in": entry.get("asserted_in") or path.name,
            "evidence": str(evidence),
        })

    return edges

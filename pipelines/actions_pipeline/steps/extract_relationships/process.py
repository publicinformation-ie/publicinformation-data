#!/usr/bin/env python3
"""Step: extract_relationships — publish how actions relate to one another.

Actions get modified, renumbered and carried between plan editions, and they
cross-reference other national plans. The link table is built here rather than
retrofitted later: the corpus already contains 57 explicit parenthetical
cross-references plus section-level groupings, and one referenced plan is
already ingested.

Three methods, deliberately unequal in trust:

  * **extracted** — parenthetical references and section-level groupings.
    Automated and published directly, but only ever as `complements` or
    `references`. Never lineage: "complements" does not mean "is the same
    commitment as", and an automated lineage guess would splice two unrelated
    commitments into one history.
  * **declared** — narrative continuity phrases in report prose. Detected and
    logged as `RelationshipCandidate` for a human to promote. Never
    auto-published.
  * **curated** — action_relationships.yml, validated strictly (relationships.py).

A `to_action_id` of null is a first-class state, not an error. "SMP action 19
complements Climate Action Plan action 233" is publishable and useful before
CAP is ingested, and becomes a resolved edge for free if CAP is added later —
no schema change, no migration. `UnresolvedRelationshipTarget` is deliberately
not an error type.
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "extract_relationships"

_PAREN_RE = re.compile(r"\(([^()]*)\)")
_TARGET_RE = re.compile(
    r"\b(?P<plan>[A-Z][A-Za-z]{1,9})\s+"
    r"(?:[Aa]ctions?|[Pp]olicy\s+[Oo]bjectives?)\s+"
    r"(?P<numbers>\d+(?:\.\d+)?(?:\s*(?:,|and)\s*\d+(?:\.\d+)?)*)")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_COMPLEMENTS_RE = re.compile(r"^\s*complements\b", re.IGNORECASE)

# Section headings in the 2022-2025 plan that group actions under another plan.
_SECTION_RE = re.compile(r"^complementary\s+actions?\s+in\s+(?P<plan>.+)$",
                         re.IGNORECASE)

# Narrative phrases that *suggest* continuity without stating it
# machine-readably. Logged for human promotion, never published.
_CONTINUITY_RE = re.compile(
    r"\b(which incorporat\w+|carried forward|superseded by|supersedes|"
    r"replaced by|merged (?:in)?to|split into|renumbered)\b", re.IGNORECASE)

# Plan hint -> corpus doc_slug, for resolving to_action_id.
#
# Deliberately empty at v1.0.0. The obvious candidate, RSS, is *not* safe to
# resolve: the corpus's Road Safety Strategy document is the Phase 2 Action
# Plan 2025-2027, whose action numbering is not the RSS 2021-2030 numbering the
# SMP cites, so resolving it would attach every edge to the wrong row. Adding
# a hint here once a correctly-numbered plan is ingested is a one-line data
# change — the resolution path below is fully implemented and tested.
PLAN_HINT_SLUGS = {}


def _error_dict(error_type: str, message: str, context: dict) -> dict:
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": message,
            "context": context}


def extract_references(text) -> list:
    """Every parenthetical cross-reference in one action or progress cell.

    A parenthetical opening with "Complements" asserts `complements`; any other
    recognised reference is the weaker `references`. Both are in the
    `reference` family — an extracted edge never claims lineage.
    """
    references = []
    for match in _PAREN_RE.finditer(text or ""):
        inner = match.group(1)
        relationship = "complements" if _COMPLEMENTS_RE.match(inner) else "references"
        for target in _TARGET_RE.finditer(inner):
            for number in _NUMBER_RE.findall(target.group("numbers")):
                references.append({
                    "relationship": relationship,
                    "to_plan_hint": target.group("plan"),
                    "to_action_number": number,
                    "evidence": match.group(0),
                })
    return references


def section_edges(actions, nodes, plan_slug) -> list:
    """`complements` edges for every action under a `COMPLEMENTARY ACTIONS IN
    <plan>` heading.

    These are *plan-level*: the heading names a plan, not a numbered action, so
    `to_action_number` is null. That null is the signal — it distinguishes a
    plan-level assertion from a resolvable action-level one, which is more
    honest than inventing a number and more useful than dropping the edge.
    """
    ranges = []
    for node in nodes or []:
        match = _SECTION_RE.match(" ".join(str(node.get("title") or "").split()))
        if not match:
            continue
        ranges.append((int(node.get("start_page") or 0),
                       int(node.get("end_page") or 0),
                       match.group("plan").strip(),
                       node.get("title")))

    edges = []
    for action in actions:
        if action.get("plan_slug") != plan_slug:
            continue
        page = action.get("source_page") or 0
        for start, end, hint, title in ranges:
            if start <= page <= end:
                edges.append({
                    "from_action_id": action["action_id"],
                    "to_action_id": None,
                    "to_plan_hint": hint,
                    "to_action_number": None,
                    "relationship": "complements",
                    "family": "reference",
                    "method": "extracted",
                    "asserted_in": plan_slug,
                    "evidence": title,
                })
                break
    return edges


def is_continuity_phrase(text) -> bool:
    return bool(_CONTINUITY_RE.search(text or ""))


def build_edges(action_texts, actions, observations, nodes, section_plan_slug,
                hint_slugs, curated) -> tuple:
    """`(edges, errors)` — the full link table plus the candidates log.

    `action_texts` are the records whose `action_text` is scanned for
    parentheticals; `actions` is the canonical action set used to resolve
    targets.
    """
    by_id = {action["action_id"] for action in actions}
    edges = []
    errors = []

    def _reference_edges(from_action_id, asserted_in, text):
        """Parenthetical references in one cell, as published edges."""
        built = []
        for reference in extract_references(text):
            hint = reference["to_plan_hint"]
            target_slug = hint_slugs.get(hint)
            target_id = None
            if target_slug:
                candidate = f"{target_slug}#{reference['to_action_number']}"
                if candidate in by_id:
                    target_id = candidate
            built.append({
                "from_action_id": from_action_id,
                "to_action_id": target_id,
                "to_plan_hint": hint,
                "to_action_number": reference["to_action_number"],
                "relationship": reference["relationship"],
                "family": "reference",
                "method": "extracted",
                "asserted_in": asserted_in,
                "evidence": reference["evidence"],
            })
        return built

    for record in action_texts:
        edges.extend(_reference_edges(record["action_id"],
                                      record.get("plan_slug"),
                                      record.get("action_text")))

    edges.extend(section_edges(actions, nodes, section_plan_slug))

    for observation in observations:
        # Progress prose carries cross-references too — the same parenthetical
        # forms, asserted by the report rather than the plan, which is why
        # `asserted_in` is the report slug here.
        edges.extend(_reference_edges(observation["action_id"],
                                      observation.get("report_slug"),
                                      observation.get("progress_text")))
        if is_continuity_phrase(observation.get("progress_text")):
            errors.append(_error_dict(
                "RelationshipCandidate",
                "Progress text contains a narrative continuity phrase. Logged "
                "for a human to promote into action_relationships.yml; never "
                "auto-published, because prose does not state a lineage edge "
                "precisely enough to publish one.",
                {"action_id": observation.get("action_id"),
                 "report_slug": observation.get("report_slug"),
                 "progress_text": observation.get("progress_text")}))

    edges.extend(curated)
    return edges, errors


def _repo_root() -> Path:
    root = Path(__file__).resolve()
    while not (root / ".git").exists():
        if root == root.parent:
            raise RuntimeError("Could not find the repository root")
        root = root.parent
    return root


def _structure_nodes(repo_root: Path, plan_slug: str) -> list:
    path = (repo_root / "pipelines" / "document_pipeline" / "steps"
            / "detect_structure" / "output.json")
    if not path.exists():
        return []
    for record in read_json(path).get("results", []):
        if record.get("doc_slug") == plan_slug:
            return record.get("nodes") or []
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Build the action relationship link table from "
                    "parenthetical references, section groupings and the "
                    "curated file")
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

    resolved = read_json(Path(args.input))
    actions = resolved.get("actions", [])
    observations = resolved.get("observations", [])

    repo_root = _repo_root()
    pipeline_dir = step_dir.parents[1]
    sys.path.insert(0, str(pipeline_dir))
    from relationships import RELATIONSHIPS_PATH, load_relationships

    # InvalidRelationshipFile is intentionally uncaught: a malformed
    # hand-authored input is process-fatal, matching documents.yml.
    curated = load_relationships(RELATIONSHIPS_PATH,
                                 {action["action_id"] for action in actions})

    # Section-level groupings exist only in the 2022-2025 plan; scan every plan
    # in the corpus so a future plan with the same convention is picked up.
    edges = []
    errors = []
    for plan_slug in sorted({action["plan_slug"] for action in actions}):
        plan_actions = [a for a in actions if a["plan_slug"] == plan_slug]
        nodes = _structure_nodes(repo_root, plan_slug)
        plan_edges, plan_errors = build_edges(
            plan_actions, actions, [], nodes, plan_slug,
            hint_slugs=PLAN_HINT_SLUGS, curated=[])
        edges.extend(plan_edges)
        errors.extend(plan_errors)

    observation_edges, observation_errors = build_edges(
        [], actions, observations, [], "", hint_slugs=PLAN_HINT_SLUGS,
        curated=curated)
    edges.extend(observation_edges)
    errors.extend(observation_errors)

    by_method = {}
    for edge in edges:
        by_method[edge["method"]] = by_method.get(edge["method"], 0) + 1

    append_errors(step_dir, errors)
    write_json(output_path, {
        "metadata": {"step": STEP_NAME,
                     "generated_at": datetime.now(timezone.utc).isoformat(),
                     "relationship_count": len(edges),
                     "by_method": by_method},
        "relationships": edges,
    })
    write_status(step_dir, len(edges))
    print(f"Wrote {len(edges)} relationship(s) to {output_path} ({by_method})")


if __name__ == "__main__":
    main()

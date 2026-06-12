"""Shared types and helpers for the pipeline evaluation framework.

Mirrors the staleness contract of process.py: an eval is recomputed only when
a dependency (fixture, labels/judgments, or evaluate.py) is newer than the
cached eval_results.json. input_hash() provides content-addressed comparison
so a baseline score is only trusted when scored against identical input.
"""
import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import jsonschema

_SCHEMA = json.loads((Path(__file__).parent / "eval_schema.json").read_text())

# Maps the spec's aspirational north-star field names to the actual canonical
# output keys emitted by extract_disclosures_canonicalize. Change here if the
# canonical schema is renamed.
HEADLINE_FIELDS = {
    "decision_date": "decision_date",
    "disclosure_request_summary": "request_description",
    "decision": "decision_status",
    "foi_reference_id": "foi_reference_id",
}


@dataclass
class Metric:
    name: str
    value: float
    counts: dict
    is_primary: bool = False


@dataclass
class EvalResults:
    step: str
    metrics: list  # list[Metric]; >= 1 required
    input_hash: str
    judge_model: str | None = None


@dataclass
class Issue:
    severity: str
    description: str
    affected_count: int
    affected_ids: list
    suggested_upstream_step: str | None = None
    suggestion_detail: str | None = None
    confidence: float = 1.0


def input_hash(path: Path) -> str:
    """sha256 of a file's bytes — survives touch/copy/branch-switch."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_eval_stale(results_path: Path, dependencies: list[Path]) -> bool:
    """True iff results_path is missing or any dependency is newer than it.

    Mirrors process.py:is_stale — mtime decides whether to recompute.
    Missing dependencies are ignored (a step may have no judgments.json).
    """
    results_path = Path(results_path)
    if not results_path.exists():
        return True
    results_mtime = results_path.stat().st_mtime
    for dep in dependencies:
        dep = Path(dep)
        if dep.exists() and dep.stat().st_mtime > results_mtime:
            return True
    return False


def _validate(instance, defn):
    jsonschema.validate(instance, {**_SCHEMA, "$ref": f"#/$defs/{defn}"})


def write_eval_outputs(eval_dir: Path, results: EvalResults, issues: list) -> None:
    """Validate and write eval_results.json + issues.json into eval_dir."""
    eval_dir = Path(eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)

    results_dict = dataclasses.asdict(results)
    _validate(results_dict, "eval_results")

    issues_list = [dataclasses.asdict(i) for i in issues]
    _validate(issues_list, "issues_file")

    (eval_dir / "eval_results.json").write_text(json.dumps(results_dict, indent=2))
    (eval_dir / "issues.json").write_text(json.dumps(issues_list, indent=2))

"""Audit PDF text-extraction artefacts in the public-body-actions data.

Scans the resolved actions/observations for artefacts in `lib.text_repairs`'s
repair map (`find_repairs`) and for artefact-shaped text missing from it
(`find_suspicious`).

Clean fields must contain no mapped artefact, and must exist: a hit or a
missing field is a failure. Raw-only fields report mapped artefacts as
`flagged` and never fail the check.

Usage:
    python scripts/audit_text_artefacts.py [--path FILE] [--json] [--check]

`--check` exits 1 when a clean field is dirty or missing.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from lib.text_repairs import find_repairs, find_suspicious  # noqa: E402

DEFAULT_PATH = (REPO_ROOT / "pipelines/actions_pipeline/steps/"
                "resolve_action_identity/output.json")

ACTION_FIELDS = ("action_text", "action_text_clean", "original_deadline_raw",
                 "original_deadline_milestones", "original_timeline_raw",
                 "lead", "support", "output")
OBSERVATION_FIELDS = ("reported_deadline_raw", "progress_text",
                      "progress_text_clean")
# Raw fields that ship with a repaired `_clean` twin: a hit is already
# repaired in the published clean text. Other raw-only fields are flagged.
HAS_CLEAN_TWIN = {"action_text", "progress_text"}
CLEAN_FIELDS = {"action_text_clean", "original_deadline_milestones",
                "progress_text_clean"}


def _scan(records, fields, id_of, kind, out, failures):
    for rec in records:
        rid = id_of(rec)
        for field in fields:
            clean = field in CLEAN_FIELDS
            if field not in rec:
                if clean:
                    failures.append(f"{kind} {rid}: clean field {field} missing")
                continue
            value = rec[field]
            if not isinstance(value, str) or not value:
                continue
            for hit in find_repairs(value):
                out["records"].append({
                    "field": field, "record_id": rid,
                    "before": hit["before"], "after": hit["after"],
                    "status": ("repaired" if field in HAS_CLEAN_TWIN
                               else "flagged")})
                if clean:
                    failures.append(
                        f"{kind} {rid}: mapped artefact {hit['before']!r} "
                        f"remains in clean field {field}")
            for hit in find_suspicious(value):
                out["suspicious"].append({
                    "field": field, "record_id": rid, "text": hit["text"]})


def audit(actions, observations):
    out = {"records": [], "suspicious": [], "failures": []}
    failures = out["failures"]
    _scan(actions, ACTION_FIELDS, lambda r: r.get("action_id"), "action",
          out, failures)
    _scan(observations, OBSERVATION_FIELDS,
          lambda r: f"{r.get('action_id')}@{r.get('report_slug')}",
          "observation", out, failures)
    return out


def check_failures(report):
    return list(report["failures"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    report = audit(data["actions"], data["observations"])
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"{len(report['records'])} mapped artefact occurrence(s), "
              f"{len(report['suspicious'])} suspicious span(s), "
              f"{len(report['failures'])} failure(s)")
        for f in report["failures"]:
            print(f"  FAIL {f}")
    if args.check and check_failures(report):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

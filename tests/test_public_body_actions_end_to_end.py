import csv
import json
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
RESOLVED = REPO_ROOT / "pipelines/actions_pipeline/steps/resolve_action_identity/output.json"
PLAN = "sustainable-mobility-policy-action-plan-2022-2025"
FINAL = "sustainable-mobility-policy-action-plan-2022-2025-final-progress-report"

pytestmark = pytest.mark.skipif(
    not RESOLVED.exists(),
    reason="actions_pipeline has not been run in this checkout (output.json is gitignored)")


@pytest.fixture(scope="module")
def resolved():
    return json.loads(RESOLVED.read_text())


def test_the_2022_2025_plan_publishes_all_91_actions(resolved):
    actions = [a for a in resolved["actions"] if a["plan_slug"] == PLAN]
    assert len(actions) == 91
    assert {a["action_number"] for a in actions} == set(range(1, 92))


def test_the_2026_2030_plan_publishes_95_actions_and_no_observations(resolved):
    """Correct representation of a plan whose first progress report does not
    yet exist — not a gap to be filled."""
    slug = "sustainable-mobility-policy-action-plan-2026-2030"
    assert len([a for a in resolved["actions"] if a["plan_slug"] == slug]) == 95
    assert not [o for o in resolved["observations"]
                if o["action_id"].startswith(f"{slug}#")]


def test_all_four_reports_contribute_observations(resolved):
    """The extract_pages table-header-reconciliation fix (2026-08-30) recovered
    Year Two, Year Three, and the Final report from UnknownReportFormat —
    all four reports on the 2022-2025 plan now contribute."""
    slugs = {o["report_slug"] for o in resolved["observations"]}
    assert slugs == {
        "sustainable-mobility-policy-year-one-progress-report",
        "sustainable-mobility-policy-year-two-progress-report",
        "sustainable-mobility-policy-year-three-progress-report",
        "sustainable-mobility-policy-action-plan-2022-2025-final-progress-report",
    }


def test_the_final_report_reproduces_its_own_published_split(resolved):
    """Free validation invariant: the Final report publishes its own
    Complete/Delayed/Modified split on page 7 — 63.7%/30.8%/5.5% = 58/28/5 of
    91 actions."""
    observations = [o for o in resolved["observations"] if o["report_slug"] == FINAL]
    assert len(observations) == 91
    counts = Counter(o["status"] for o in observations)
    assert counts == {"Complete": 58, "Delayed": 28, "Modified": 5}


def test_the_published_csvs_are_consistent_with_the_pipeline(resolved):
    published = REPO_ROOT / "public/v1.0.0/public-body-actions/actions.csv"
    if not published.exists():
        pytest.skip("dataset not yet published")
    with published.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(resolved["actions"])

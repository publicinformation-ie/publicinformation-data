> **NOTE**: This document refers to the old `publicinfo-prototype` subdirectory structure.
> The website has been moved to the separate `publicinformation-web` repository at
> /Users/gingertechie/dev/publicinformation/publicinformation-web/
> 
> References to `publicinfo-prototype` in this document should be read as `../publicinformation-web`.

# export_status Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stub `import_disclosures` step with a new final `export_status` step that fan-in merges all preceding step outputs into the consolidated `pipeline-status.json` the Astro data-status page expects.

**Architecture:** `export_status/process.py` honours the orchestrator's `--input/--output/--force` contract but ignores `--input`; it derives the `steps/` directory from `__file__`, reads `pipeline.json` for step order, loads each preceding step's `output.json` in sequence, and merges field updates into a deep copy of `find_public_bodies/output.json`. Steps whose `output.json` is absent are silently skipped (fields remain `"not_attempted"`); bodies absent from a present step's results are marked `"failed"` for that step's status fields.

**Tech Stack:** Python 3.12+, stdlib only (`json`, `copy`, `collections`, `pathlib`, `argparse`, `datetime`); pytest + requests-mock for tests.

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Rename (git mv) | `foi_pipeline/steps/import_disclosures/` → `foi_pipeline/steps/export_status/` | Step directory |
| Rewrite | `foi_pipeline/steps/export_status/process.py` | Fan-in merge logic + CLI entry point |
| Keep empty | `foi_pipeline/steps/export_status/__init__.py` | Package marker |
| Update | `foi_pipeline/pipeline.json` | Rename last entry |
| Create | `foi_pipeline/tests/test_export_status.py` | All tests for this step |
| Update | `publicinfo-prototype/package.json` | Point prebuild `cp` at new step output |

---

### Task 1: Rename the step directory and update pipeline.json

**Files:**
- Rename: `foi_pipeline/steps/import_disclosures/` → `foi_pipeline/steps/export_status/`
- Modify: `foi_pipeline/pipeline.json`

- [ ] **Step 1: Rename the directory with git**

```bash
cd foi_pipeline
git mv steps/import_disclosures steps/export_status
```

Expected: no output (silent success).

- [ ] **Step 2: Update the STEP_NAME in the moved process.py**

In `foi_pipeline/steps/export_status/process.py`, change line 10:

```python
STEP_NAME = "export_status"
```

- [ ] **Step 3: Update pipeline.json**

Replace the content of `foi_pipeline/pipeline.json` with:

```json
{
  "steps": [
    "find_public_bodies",
    "validate_websites",
    "find_foi_pages",
    "check_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
    "find_disclosure_files",
    "transform_disclosure_files",
    "extract_disclosures",
    "export_status"
  ]
}
```

- [ ] **Step 4: Run existing tests to confirm the rename doesn't break anything**

```bash
cd foi_pipeline && python -m pytest tests/ -v --tb=short -q
```

Expected: all previously passing tests still pass (no test currently references `import_disclosures`).

- [ ] **Step 5: Commit**

```bash
cd foi_pipeline
git add steps/export_status/ pipeline.json
git commit -m "refactor: rename import_disclosures step to export_status"
```

---

### Task 2: Write the failing tests

**Files:**
- Create: `foi_pipeline/tests/test_export_status.py`

- [ ] **Step 1: Create the test file**

Write `foi_pipeline/tests/test_export_status.py` with this complete content:

```python
import copy
import json
import pytest
from steps.export_status.process import (
    STEP_NAME,
    merge,
    merge_validate_websites,
    merge_find_foi_pages,
    merge_check_foi_pages,
    merge_get_foi_emails,
    merge_find_disclosure_pages,
    merge_find_disclosure_files,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PIPELINE_STEPS = [
    "find_public_bodies",
    "validate_websites",
    "find_foi_pages",
    "check_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
    "find_disclosure_files",
    "transform_disclosure_files",
    "extract_disclosures",
    "export_status",
]

BASE_OUTPUT = {
    "metadata": {"step": "find_public_bodies", "completed_at": "2026-05-04T00:00:00+00:00"},
    "public_bodies": [
        {
            "public_body_id": 1001,
            "name": "Dept A",
            "official_website_url": "https://dept-a.ie/",
            "status": {
                "website_url": {"url": "https://dept-a.ie/", "status": "not_attempted"},
                "foi_page": {"url": None, "status": "not_attempted"},
                "foi_email": {"email": None, "status": "not_attempted"},
                "disclosures_page": {"url": None, "status": "not_attempted"},
                "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "not_attempted"},
                "foi_requests": {"valid": 0, "errors": 0, "status": "not_attempted"},
            },
        },
        {
            "public_body_id": 1002,
            "name": "Dept B",
            "official_website_url": "https://dept-b.ie/",
            "status": {
                "website_url": {"url": "https://dept-b.ie/", "status": "not_attempted"},
                "foi_page": {"url": None, "status": "not_attempted"},
                "foi_email": {"email": None, "status": "not_attempted"},
                "disclosures_page": {"url": None, "status": "not_attempted"},
                "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "not_attempted"},
                "foi_requests": {"valid": 0, "errors": 0, "status": "not_attempted"},
            },
        },
    ],
}


def make_body(bid):
    return {
        "public_body_id": bid,
        "name": f"Body {bid}",
        "official_website_url": f"https://body-{bid}.ie/",
        "status": {
            "website_url": {"url": f"https://body-{bid}.ie/", "status": "not_attempted"},
            "foi_page": {"url": None, "status": "not_attempted"},
            "foi_email": {"email": None, "status": "not_attempted"},
            "disclosures_page": {"url": None, "status": "not_attempted"},
            "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "not_attempted"},
            "foi_requests": {"valid": 0, "errors": 0, "status": "not_attempted"},
        },
    }


def make_body_map(*bids):
    return {bid: make_body(bid) for bid in bids}


def setup_steps_dir(tmp_path, outputs: dict):
    steps_dir = tmp_path / "steps"
    for step_name, data in outputs.items():
        step_dir = steps_dir / step_name
        step_dir.mkdir(parents=True)
        (step_dir / "output.json").write_text(json.dumps(data))
    return steps_dir


# ---------------------------------------------------------------------------
# STEP_NAME
# ---------------------------------------------------------------------------

def test_step_name():
    assert STEP_NAME == "export_status"


# ---------------------------------------------------------------------------
# merge_validate_websites
# ---------------------------------------------------------------------------

def test_validate_websites_reachable_sets_success():
    body_map = make_body_map(1001)
    merge_validate_websites(body_map, {"results": [{"public_body_id": 1001, "is_reachable": True}]})
    assert body_map[1001]["status"]["website_url"]["status"] == "success"


def test_validate_websites_unreachable_sets_failed():
    body_map = make_body_map(1001)
    merge_validate_websites(body_map, {"results": [{"public_body_id": 1001, "is_reachable": False}]})
    assert body_map[1001]["status"]["website_url"]["status"] == "failed"


def test_validate_websites_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_validate_websites(body_map, {"results": [{"public_body_id": 1001, "is_reachable": True}]})
    assert body_map[1002]["status"]["website_url"]["status"] == "failed"


def test_validate_websites_does_not_touch_other_fields():
    body_map = make_body_map(1001)
    merge_validate_websites(body_map, {"results": [{"public_body_id": 1001, "is_reachable": True}]})
    assert body_map[1001]["status"]["foi_page"]["status"] == "not_attempted"


# ---------------------------------------------------------------------------
# merge_find_foi_pages
# ---------------------------------------------------------------------------

def test_find_foi_pages_sets_url_and_success():
    body_map = make_body_map(1001)
    merge_find_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "foi_page_url": "https://dept-a.ie/foi/"}]
    })
    assert body_map[1001]["status"]["foi_page"]["url"] == "https://dept-a.ie/foi/"
    assert body_map[1001]["status"]["foi_page"]["status"] == "success"


def test_find_foi_pages_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_find_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "foi_page_url": "https://dept-a.ie/foi/"}]
    })
    assert body_map[1002]["status"]["foi_page"]["status"] == "failed"


# ---------------------------------------------------------------------------
# merge_check_foi_pages
# ---------------------------------------------------------------------------

def test_check_foi_pages_reachable_sets_success():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["foi_page"]["status"] = "success"
    merge_check_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "is_reachable": True}]
    })
    assert body_map[1001]["status"]["foi_page"]["status"] == "success"


def test_check_foi_pages_unreachable_sets_failed():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["foi_page"]["status"] = "success"
    merge_check_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "is_reachable": False}]
    })
    assert body_map[1001]["status"]["foi_page"]["status"] == "failed"


def test_check_foi_pages_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_check_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "is_reachable": True}]
    })
    assert body_map[1002]["status"]["foi_page"]["status"] == "failed"


def test_check_foi_pages_does_not_touch_url():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["foi_page"]["url"] = "https://dept-a.ie/foi/"
    merge_check_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "is_reachable": False}]
    })
    assert body_map[1001]["status"]["foi_page"]["url"] == "https://dept-a.ie/foi/"


# ---------------------------------------------------------------------------
# merge_get_foi_emails
# ---------------------------------------------------------------------------

def test_get_foi_emails_found_sets_email_and_success():
    body_map = make_body_map(1001)
    merge_get_foi_emails(body_map, {
        "results": [{"public_body_id": 1001, "foi_email": "foi@dept-a.ie", "email_status": "found"}]
    })
    assert body_map[1001]["status"]["foi_email"]["email"] == "foi@dept-a.ie"
    assert body_map[1001]["status"]["foi_email"]["status"] == "success"


def test_get_foi_emails_not_found_sets_failed():
    body_map = make_body_map(1001)
    merge_get_foi_emails(body_map, {
        "results": [{"public_body_id": 1001, "foi_email": None, "email_status": "not_found"}]
    })
    assert body_map[1001]["status"]["foi_email"]["status"] == "failed"


def test_get_foi_emails_multiple_found_sets_failed():
    body_map = make_body_map(1001)
    merge_get_foi_emails(body_map, {
        "results": [{"public_body_id": 1001, "foi_email": None, "email_status": "multiple_found"}]
    })
    assert body_map[1001]["status"]["foi_email"]["status"] == "failed"


def test_get_foi_emails_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_get_foi_emails(body_map, {
        "results": [{"public_body_id": 1001, "foi_email": "foi@dept-a.ie", "email_status": "found"}]
    })
    assert body_map[1002]["status"]["foi_email"]["status"] == "failed"


# ---------------------------------------------------------------------------
# merge_find_disclosure_pages
# ---------------------------------------------------------------------------

def test_find_disclosure_pages_sets_url_and_success():
    body_map = make_body_map(1001)
    merge_find_disclosure_pages(body_map, {
        "results": [{"public_body_id": 1001, "disclosure_page_url": "https://dept-a.ie/disclosure/"}]
    })
    assert body_map[1001]["status"]["disclosures_page"]["url"] == "https://dept-a.ie/disclosure/"
    assert body_map[1001]["status"]["disclosures_page"]["status"] == "success"


def test_find_disclosure_pages_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_find_disclosure_pages(body_map, {
        "results": [{"public_body_id": 1001, "disclosure_page_url": "https://dept-a.ie/disclosure/"}]
    })
    assert body_map[1002]["status"]["disclosures_page"]["status"] == "failed"


# ---------------------------------------------------------------------------
# merge_find_disclosure_files
# ---------------------------------------------------------------------------

def test_find_disclosure_files_counts_files_per_body():
    body_map = make_body_map(1001)
    merge_find_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.pdf", "file_type": "pdf"},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.pdf", "file_type": "pdf"},
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["total"] == 2
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == 2
    assert body_map[1001]["status"]["disclosure_files"]["failed"] == 0
    assert body_map[1001]["status"]["disclosure_files"]["status"] == "success"


def test_find_disclosure_files_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_find_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.pdf", "file_type": "pdf"},
        ]
    })
    assert body_map[1002]["status"]["disclosure_files"]["status"] == "failed"


def test_find_disclosure_files_counts_are_per_body():
    body_map = make_body_map(1001, 1002)
    merge_find_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.pdf", "file_type": "pdf"},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.pdf", "file_type": "pdf"},
            {"public_body_id": 1002, "file_url": "https://dept-b.ie/q1.pdf", "file_type": "pdf"},
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["total"] == 2
    assert body_map[1002]["status"]["disclosure_files"]["total"] == 1


# ---------------------------------------------------------------------------
# merge() orchestration
# ---------------------------------------------------------------------------

def test_merge_returns_all_base_bodies(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    assert {b["public_body_id"] for b in result} == {1001, 1002}


def test_merge_all_not_attempted_when_only_base_exists(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    for body in result:
        assert body["status"]["website_url"]["status"] == "not_attempted"
        assert body["status"]["foi_page"]["status"] == "not_attempted"
        assert body["status"]["foi_email"]["status"] == "not_attempted"
        assert body["status"]["disclosures_page"]["status"] == "not_attempted"
        assert body["status"]["disclosure_files"]["status"] == "not_attempted"


def test_merge_applies_validate_websites(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies": BASE_OUTPUT,
        "validate_websites": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "is_reachable": True},
                {"public_body_id": 1002, "is_reachable": False},
            ],
        },
    })
    result = merge(steps_dir, PIPELINE_STEPS)
    by_id = {b["public_body_id"]: b for b in result}
    assert by_id[1001]["status"]["website_url"]["status"] == "success"
    assert by_id[1002]["status"]["website_url"]["status"] == "failed"


def test_merge_check_foi_pages_refines_find_foi_pages(tmp_path):
    """check_foi_pages should overwrite foi_page.status set by find_foi_pages."""
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies": BASE_OUTPUT,
        "find_foi_pages": {
            "metadata": {},
            "results": [{"public_body_id": 1001, "foi_page_url": "https://dept-a.ie/foi/"}],
        },
        "check_foi_pages": {
            "metadata": {},
            "results": [{"public_body_id": 1001, "is_reachable": False}],
        },
    })
    result = merge(steps_dir, PIPELINE_STEPS)
    by_id = {b["public_body_id"]: b for b in result}
    assert by_id[1001]["status"]["foi_page"]["url"] == "https://dept-a.ie/foi/"
    assert by_id[1001]["status"]["foi_page"]["status"] == "failed"


def test_merge_skips_step_with_no_output_file(tmp_path):
    """A missing step output.json leaves that step's fields as not_attempted."""
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    assert result[0]["status"]["website_url"]["status"] == "not_attempted"


def test_merge_skips_steps_with_no_merger(tmp_path):
    """Steps not in STEP_MERGERS (transform_disclosure_files, extract_disclosures, export_status)
    are silently skipped without error."""
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies": BASE_OUTPUT,
        "transform_disclosure_files": {"metadata": {}, "results": []},
    })
    result = merge(steps_dir, PIPELINE_STEPS)
    assert len(result) == 2


def test_merge_does_not_mutate_base_output(tmp_path):
    original = copy.deepcopy(BASE_OUTPUT)
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies": BASE_OUTPUT,
        "validate_websites": {
            "metadata": {},
            "results": [{"public_body_id": 1001, "is_reachable": True}],
        },
    })
    merge(steps_dir, PIPELINE_STEPS)
    assert BASE_OUTPUT == original


def test_merge_full_pipeline(tmp_path):
    """Integration: apply all implemented steps and verify consolidated output."""
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies": BASE_OUTPUT,
        "validate_websites": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "is_reachable": True},
                {"public_body_id": 1002, "is_reachable": True},
            ],
        },
        "find_foi_pages": {
            "metadata": {},
            "results": [{"public_body_id": 1001, "foi_page_url": "https://dept-a.ie/foi/"}],
        },
        "check_foi_pages": {
            "metadata": {},
            "results": [{"public_body_id": 1001, "is_reachable": True}],
        },
        "get_foi_emails": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "foi_email": "foi@dept-a.ie", "email_status": "found"}
            ],
        },
        "find_disclosure_pages": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "disclosure_page_url": "https://dept-a.ie/disclosure/"}
            ],
        },
        "find_disclosure_files": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.pdf", "file_type": "pdf"},
            ],
        },
    })
    result = merge(steps_dir, PIPELINE_STEPS)
    by_id = {b["public_body_id"]: b for b in result}

    a = by_id[1001]
    assert a["status"]["website_url"]["status"] == "success"
    assert a["status"]["foi_page"]["url"] == "https://dept-a.ie/foi/"
    assert a["status"]["foi_page"]["status"] == "success"
    assert a["status"]["foi_email"]["email"] == "foi@dept-a.ie"
    assert a["status"]["foi_email"]["status"] == "success"
    assert a["status"]["disclosures_page"]["url"] == "https://dept-a.ie/disclosure/"
    assert a["status"]["disclosures_page"]["status"] == "success"
    assert a["status"]["disclosure_files"]["total"] == 1
    assert a["status"]["disclosure_files"]["status"] == "success"
    assert a["status"]["foi_requests"]["status"] == "not_attempted"

    b = by_id[1002]
    assert b["status"]["website_url"]["status"] == "success"
    assert b["status"]["foi_page"]["status"] == "failed"
    assert b["status"]["foi_email"]["status"] == "failed"
    assert b["status"]["disclosures_page"]["status"] == "failed"
    assert b["status"]["disclosure_files"]["status"] == "failed"
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd foi_pipeline && python -m pytest tests/test_export_status.py -v --tb=short 2>&1 | head -30
```

Expected: `ImportError` — the new names (`merge`, `merge_validate_websites`, etc.) don't exist in the current stub `process.py`.

- [ ] **Step 3: Commit the failing tests**

```bash
cd foi_pipeline
git add tests/test_export_status.py
git commit -m "test: add failing tests for export_status step"
```

---

### Task 3: Implement the merger functions and STEP_MERGERS

**Files:**
- Rewrite: `foi_pipeline/steps/export_status/process.py`

- [ ] **Step 1: Write the full process.py**

Replace the contents of `foi_pipeline/steps/export_status/process.py` with:

```python
#!/usr/bin/env python3
import argparse
import copy
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status

STEP_NAME = "export_status"


def merge_validate_websites(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["website_url"]["status"] = (
                "success" if r["is_reachable"] else "failed"
            )
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["website_url"]["status"] = "failed"


def merge_find_foi_pages(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_page"]["url"] = r["foi_page_url"]
            body_map[bid]["status"]["foi_page"]["status"] = "success"
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["foi_page"]["status"] = "failed"


def merge_check_foi_pages(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_page"]["status"] = (
                "success" if r["is_reachable"] else "failed"
            )
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["foi_page"]["status"] = "failed"


def merge_get_foi_emails(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_email"]["email"] = r.get("foi_email")
            body_map[bid]["status"]["foi_email"]["status"] = (
                "success" if r.get("email_status") == "found" else "failed"
            )
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["foi_email"]["status"] = "failed"


def merge_find_disclosure_pages(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["disclosures_page"]["url"] = r["disclosure_page_url"]
            body_map[bid]["status"]["disclosures_page"]["status"] = "success"
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["disclosures_page"]["status"] = "failed"


def merge_find_disclosure_files(body_map, step_data):
    counts = defaultdict(int)
    for r in step_data["results"]:
        counts[r["public_body_id"]] += 1
    for bid, body in body_map.items():
        if bid in counts:
            total = counts[bid]
            body["status"]["disclosure_files"]["total"] = total
            body["status"]["disclosure_files"]["valid"] = total
            body["status"]["disclosure_files"]["failed"] = 0
            body["status"]["disclosure_files"]["status"] = "success" if total > 0 else "failed"
        else:
            body["status"]["disclosure_files"]["status"] = "failed"


STEP_MERGERS = {
    "validate_websites": merge_validate_websites,
    "find_foi_pages": merge_find_foi_pages,
    "check_foi_pages": merge_check_foi_pages,
    "get_foi_emails": merge_get_foi_emails,
    "find_disclosure_pages": merge_find_disclosure_pages,
    "find_disclosure_files": merge_find_disclosure_files,
}


def merge(steps_dir, pipeline_steps):
    base_data = read_json(steps_dir / "find_public_bodies" / "output.json")
    bodies = copy.deepcopy(base_data["public_bodies"])
    body_map = {b["public_body_id"]: b for b in bodies}

    for step_name in pipeline_steps:
        if step_name in ("find_public_bodies", STEP_NAME):
            continue
        merger = STEP_MERGERS.get(step_name)
        if merger is None:
            continue
        output_path = steps_dir / step_name / "output.json"
        if not output_path.exists():
            continue
        step_data = read_json(output_path)
        merger(body_map, step_data)

    return list(body_map.values())


def main():
    parser = argparse.ArgumentParser(description="Export merged pipeline status for all public bodies")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    steps_dir = step_dir.parent
    pipeline_dir = steps_dir.parent
    pipeline_config = read_json(pipeline_dir / "pipeline.json")

    bodies = merge(steps_dir, pipeline_config["steps"])
    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": bodies,
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full test suite**

```bash
cd foi_pipeline && python -m pytest tests/test_export_status.py -v 2>&1 | tail -20
```

Expected: all tests in `test_export_status.py` **PASS**.

- [ ] **Step 3: Confirm no regressions in existing tests**

```bash
cd foi_pipeline && python -m pytest tests/ -v --tb=short -q 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd foi_pipeline
git add steps/export_status/process.py
git commit -m "feat: implement export_status step with fan-in status merge"
```

---

### Task 4: Update the Astro prebuild hook

**Files:**
- Modify: `publicinfo-prototype/package.json`

- [ ] **Step 1: Update the prebuild script**

In `publicinfo-prototype/package.json`, change the `prebuild` script from:

```json
"prebuild": "mkdir -p src/data && (cp ../foi_pipeline/steps/find_public_bodies/output.json src/data/pipeline-status.json 2>/dev/null || echo '{\"metadata\": {}, \"public_bodies\": []}' > src/data/pipeline-status.json)"
```

to:

```json
"prebuild": "mkdir -p src/data && (cp ../foi_pipeline/steps/export_status/output.json src/data/pipeline-status.json 2>/dev/null || echo '{\"metadata\": {}, \"public_bodies\": []}' > src/data/pipeline-status.json)"
```

- [ ] **Step 2: Verify the fallback still works when no output.json exists**

```bash
cd publicinfo-prototype && npm run prebuild 2>&1
```

Expected: either copies `export_status/output.json` (if it exists from a prior pipeline run), or falls back to writing the empty JSON stub — no error exit code in either case.

- [ ] **Step 3: Commit**

```bash
git add publicinfo-prototype/package.json
git commit -m "fix: prebuild now copies export_status output instead of find_public_bodies"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run the full test suite one last time**

```bash
cd foi_pipeline && python -m pytest tests/ -v 2>&1 | tail -15
```

Expected: all tests pass, no failures or errors.

- [ ] **Step 2: Smoke-test main() directly**

From the `foi_pipeline/` directory (with PYTHONPATH set):

```bash
cd foi_pipeline && PYTHONPATH=. python steps/export_status/process.py \
  --input steps/extract_disclosures/output.json \
  --output /tmp/export_status_test.json \
  --force 2>&1
```

Expected (if `find_public_bodies/output.json` exists): `Wrote N public bodies to /tmp/export_status_test.json`

Expected (if `find_public_bodies/output.json` does not exist): `FileNotFoundError` — this is correct; the step has a hard dependency on the base step having run first.

- [ ] **Step 3: Verify output structure matches spec**

```bash
python -c "
import json
data = json.load(open('/tmp/export_status_test.json'))
print('step:', data['metadata']['step'])
print('bodies:', len(data['public_bodies']))
body = data['public_bodies'][0]
print('status keys:', list(body['status'].keys()))
print('first body status:', json.dumps(body['status'], indent=2))
"
```

Expected: `step: export_status`, correct body count, status keys matching `website_url`, `foi_page`, `foi_email`, `disclosures_page`, `disclosure_files`, `foi_requests`.

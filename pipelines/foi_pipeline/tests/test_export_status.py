import copy
import json
import pytest
from steps.export_status.process import (
    STEP_NAME,
    DISCLOSURE_STEPS,
    collect_disclosure_ids,
    merge,
    merge_validate_websites,
    merge_find_foi_pages,
    merge_check_foi_pages,
    merge_get_foi_emails,
    merge_find_disclosure_pages,
    merge_find_disclosure_files,
    merge_transform_disclosure_files,
    merge_extract_disclosures_canonicalize,
    write_public_output,
    write_disclosure_files_output,
    write_foi_disclosures_output,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PIPELINE_STEPS = [
    "find_public_bodies",
    "find_public_bodies_subject_to_foi",
    "resolve_website_urls",
    "validate_websites",
    "find_foi_pages",
    "check_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
    "find_disclosure_files",
    "transform_disclosure_files",
    "extract_disclosures_detect_header_row",
    "extract_disclosures_canonicalize",
    "export_status",
]

BASE_OUTPUT = {
    "metadata": {"step": "find_public_bodies", "completed_at": "2026-05-04T00:00:00+00:00"},
    "public_bodies": [
        {
            "public_body_id": 1001,
            "name": "Dept A",
            "official_website_url": "https://dept-a.ie/",
            "category": "government department",
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
            "category": "public service body",
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
        "category": "government department",
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
# merge_transform_disclosure_files
# ---------------------------------------------------------------------------

def test_transform_disclosure_files_counts_xlsx_with_rows():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["disclosure_files"]["total"] = 2
    merge_transform_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a", "b"]]},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.xlsx", "file_type": "xlsx", "rows": [["c", "d"]]},
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == 2


def test_transform_disclosure_files_pdf_rows_none_not_counted():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["disclosure_files"]["total"] = 3
    merge_transform_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a"]]},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.pdf", "file_type": "pdf", "rows": None},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q3.pdf", "file_type": "pdf", "rows": None},
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == 1


def test_transform_disclosure_files_failed_transform_rows_none_not_counted():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["disclosure_files"]["total"] = 2
    merge_transform_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a"]]},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.xlsx", "file_type": "xlsx", "rows": None},
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == 1


def test_transform_disclosure_files_counts_are_per_body():
    body_map = make_body_map(1001, 1002)
    body_map[1001]["status"]["disclosure_files"]["total"] = 2
    body_map[1002]["status"]["disclosure_files"]["total"] = 1
    merge_transform_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a"]]},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.pdf", "file_type": "pdf", "rows": None},
            {"public_body_id": 1002, "file_url": "https://dept-b.ie/q1.xlsx", "file_type": "xlsx", "rows": [["b"]]},
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == 1
    assert body_map[1002]["status"]["disclosure_files"]["valid"] == 1


def test_transform_disclosure_files_body_with_no_transform_records_gets_zero():
    body_map = make_body_map(1001, 1002)
    body_map[1001]["status"]["disclosure_files"]["total"] = 2
    body_map[1002]["status"]["disclosure_files"]["total"] = 1
    merge_transform_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a"]]},
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.xlsx", "file_type": "xlsx", "rows": [["b"]]},
            # 1002 is absent from transform output
        ]
    })
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == 2
    assert body_map[1002]["status"]["disclosure_files"]["valid"] == 0


def test_transform_disclosure_files_skips_bodies_with_no_found_files():
    """Bodies with total=0 are not touched — no transform data means nothing to report."""
    body_map = make_body_map(1001)
    body_map[1001]["status"]["disclosure_files"]["total"] = 0
    original_valid = body_map[1001]["status"]["disclosure_files"]["valid"]
    merge_transform_disclosure_files(body_map, {"results": []})
    assert body_map[1001]["status"]["disclosure_files"]["valid"] == original_valid


def test_transform_disclosure_files_does_not_touch_other_fields():
    body_map = make_body_map(1001)
    body_map[1001]["status"]["disclosure_files"]["total"] = 1
    merge_transform_disclosure_files(body_map, {
        "results": [
            {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a"]]},
        ]
    })
    assert body_map[1001]["status"]["foi_page"]["status"] == "not_attempted"
    assert body_map[1001]["status"]["disclosure_files"]["total"] == 1
    assert body_map[1001]["status"]["disclosure_files"]["failed"] == 0


# ---------------------------------------------------------------------------
# merge_extract_disclosures_canonicalize
# ---------------------------------------------------------------------------

def test_extract_disclosures_canonicalize_counts_records_sets_success():
    body_map = make_body_map(1001)
    merge_extract_disclosures_canonicalize(body_map, {
        "results": [
            {"public_body_id": 1001, "foi_reference_id": "16/001"},
            {"public_body_id": 1001, "foi_reference_id": "16/002"},
        ]
    })
    assert body_map[1001]["status"]["foi_requests"]["valid"] == 2
    assert body_map[1001]["status"]["foi_requests"]["errors"] == 0
    assert body_map[1001]["status"]["foi_requests"]["status"] == "success"


def test_extract_disclosures_canonicalize_absent_body_sets_failed():
    body_map = make_body_map(1001, 1002)
    merge_extract_disclosures_canonicalize(body_map, {
        "results": [{"public_body_id": 1001, "foi_reference_id": "16/001"}]
    })
    assert body_map[1002]["status"]["foi_requests"]["status"] == "failed"


def test_extract_disclosures_canonicalize_counts_are_per_body():
    body_map = make_body_map(1001, 1002)
    merge_extract_disclosures_canonicalize(body_map, {
        "results": [
            {"public_body_id": 1001, "foi_reference_id": "16/001"},
            {"public_body_id": 1001, "foi_reference_id": "16/002"},
            {"public_body_id": 1002, "foi_reference_id": "16/003"},
        ]
    })
    assert body_map[1001]["status"]["foi_requests"]["valid"] == 2
    assert body_map[1002]["status"]["foi_requests"]["valid"] == 1


def test_extract_disclosures_canonicalize_empty_results_sets_failed():
    body_map = make_body_map(1001)
    merge_extract_disclosures_canonicalize(body_map, {"results": []})
    assert body_map[1001]["status"]["foi_requests"]["status"] == "failed"


def test_extract_disclosures_canonicalize_does_not_touch_other_status_fields():
    body_map = make_body_map(1001)
    merge_extract_disclosures_canonicalize(body_map, {
        "results": [{"public_body_id": 1001, "foi_reference_id": "16/001"}]
    })
    assert body_map[1001]["status"]["disclosure_files"]["status"] == "not_attempted"
    assert body_map[1001]["status"]["foi_page"]["status"] == "not_attempted"


# ---------------------------------------------------------------------------
# merge() orchestration
# ---------------------------------------------------------------------------

def test_merge_returns_all_base_bodies(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    assert {b["public_body_id"] for b in result} == {1001, 1002}


def test_merge_all_not_attempted_when_only_base_exists(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    for body in result:
        assert body["status"]["website_url"]["status"] == "not_attempted"
        assert body["status"]["foi_page"]["status"] == "not_attempted"
        assert body["status"]["foi_email"]["status"] == "not_attempted"
        assert body["status"]["disclosures_page"]["status"] == "not_attempted"
        assert body["status"]["disclosure_files"]["status"] == "not_attempted"


def test_merge_applies_validate_websites(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
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
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
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
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    assert result[0]["status"]["website_url"]["status"] == "not_attempted"


def test_merge_skips_steps_with_no_merger(tmp_path):
    """Steps not in STEP_MERGERS (e.g. extract_disclosures_detect_header_row)
    are silently skipped without error."""
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
        "transform_disclosure_files": {"metadata": {}, "results": []},
    })
    result = merge(steps_dir, PIPELINE_STEPS)
    assert len(result) == 2


def test_merge_does_not_mutate_base_output(tmp_path):
    original = copy.deepcopy(BASE_OUTPUT)
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
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
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
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
                {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx"},
                {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.pdf", "file_type": "pdf"},
            ],
        },
        "transform_disclosure_files": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "file_url": "https://dept-a.ie/q1.xlsx", "file_type": "xlsx", "rows": [["a"]]},
                {"public_body_id": 1001, "file_url": "https://dept-a.ie/q2.pdf", "file_type": "pdf", "rows": None},
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
    assert a["status"]["disclosure_files"]["total"] == 2
    assert a["status"]["disclosure_files"]["valid"] == 1  # only the xlsx
    assert a["status"]["disclosure_files"]["status"] == "success"
    assert a["status"]["foi_requests"]["status"] == "not_attempted"

    b = by_id[1002]
    assert b["status"]["website_url"]["status"] == "success"
    assert b["status"]["foi_page"]["status"] == "failed"
    assert b["status"]["foi_email"]["status"] == "failed"
    assert b["status"]["disclosures_page"]["status"] == "failed"
    assert b["status"]["disclosure_files"]["status"] == "failed"


def test_merge_renames_name_to_public_body_name(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    assert result[0]["public_body_name"] == "Dept A"
    assert "name" not in result[0]


def test_merge_renames_official_website_url_to_public_body_url(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    assert result[0]["public_body_url"] == "https://dept-a.ie/"
    assert "official_website_url" not in result[0]


def test_merge_renames_category_to_public_body_category(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS)
    by_id = {b["public_body_id"]: b for b in result}
    assert by_id[1001]["public_body_category"] == "government department"
    assert by_id[1002]["public_body_category"] == "public service body"
    assert "category" not in by_id[1001]


# ---------------------------------------------------------------------------
# write_public_output
# ---------------------------------------------------------------------------

def test_write_public_output_returns_correct_path(tmp_path):
    output = {"metadata": {"step": "export_status"}, "public_bodies": []}
    path = write_public_output(output, tmp_path)
    assert path == tmp_path / "public" / "pipeline-data.json"


def test_write_public_output_creates_file(tmp_path):
    output = {"metadata": {"step": "export_status"}, "public_bodies": []}
    write_public_output(output, tmp_path)
    assert (tmp_path / "public" / "pipeline-data.json").exists()


def test_write_public_output_content_matches(tmp_path):
    output = {
        "metadata": {"step": "export_status", "completed_at": "2026-05-06T00:00:00+00:00"},
        "public_bodies": [{"public_body_id": 1001, "name": "Dept A"}],
    }
    write_public_output(output, tmp_path)
    data = json.loads((tmp_path / "public" / "pipeline-data.json").read_text())
    assert data == output


def test_write_public_output_creates_public_dir(tmp_path):
    output = {"metadata": {}, "public_bodies": []}
    write_public_output(output, tmp_path)
    assert (tmp_path / "public").is_dir()


def test_write_public_output_overwrites_existing_file(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "pipeline-data.json").write_text('{"old": true}')
    output = {"metadata": {}, "public_bodies": [{"public_body_id": 99}]}
    write_public_output(output, tmp_path)
    data = json.loads((tmp_path / "public" / "pipeline-data.json").read_text())
    assert data["public_bodies"][0]["public_body_id"] == 99


# ---------------------------------------------------------------------------
# write_disclosure_files_output
# ---------------------------------------------------------------------------


def _make_disclosure_steps_dir(tmp_path, results):
    """Helper: write find_disclosure_files/output.json into a steps dir."""
    steps_dir = tmp_path / "steps"
    disc_dir = steps_dir / "find_disclosure_files"
    disc_dir.mkdir(parents=True)
    (disc_dir / "output.json").write_text(json.dumps({
        "metadata": {"step": "find_disclosure_files"},
        "results": results,
    }))
    return steps_dir


def test_write_disclosure_files_output_maps_fields(tmp_path):
    steps_dir = _make_disclosure_steps_dir(tmp_path, [
        {
            "public_body_id": 1001,
            "name": "Dept A",
            "disclosure_page_url": "https://dept-a.ie/disclosure/",
            "file_url": "https://assets.gov.ie/q1.pdf",
            "file_type": "pdf",
        }
    ])
    write_disclosure_files_output(steps_dir, tmp_path)
    data = json.loads((tmp_path / "public" / "disclosure-files.json").read_text())
    assert len(data) == 1
    assert data[0]["document_url"] == "https://assets.gov.ie/q1.pdf"
    assert data[0]["source_page_url"] == "https://dept-a.ie/disclosure/"
    assert data[0]["file_type"] == "pdf"
    assert data[0]["date_added"] is None
    assert data[0]["public_body_id"] == 1001
    assert "file_url" not in data[0]
    assert "name" not in data[0]
    assert "disclosure_page_url" not in data[0]


def test_write_disclosure_files_output_returns_path(tmp_path):
    steps_dir = _make_disclosure_steps_dir(tmp_path, [])
    path = write_disclosure_files_output(steps_dir, tmp_path)
    assert path == tmp_path / "public" / "disclosure-files.json"


def test_write_disclosure_files_output_returns_none_when_no_input(tmp_path):
    steps_dir = tmp_path / "steps"
    steps_dir.mkdir()
    path = write_disclosure_files_output(steps_dir, tmp_path)
    assert path is None


def test_write_disclosure_files_output_creates_public_dir(tmp_path):
    steps_dir = _make_disclosure_steps_dir(tmp_path, [])
    write_disclosure_files_output(steps_dir, tmp_path)
    assert (tmp_path / "public").is_dir()


def test_write_disclosure_files_output_multiple_bodies(tmp_path):
    steps_dir = _make_disclosure_steps_dir(tmp_path, [
        {
            "public_body_id": 1001,
            "name": "Dept A",
            "disclosure_page_url": "https://dept-a.ie/disclosure/",
            "file_url": "https://assets.gov.ie/q1.pdf",
            "file_type": "pdf",
        },
        {
            "public_body_id": 1002,
            "name": "Dept B",
            "disclosure_page_url": "https://dept-b.ie/disclosure/",
            "file_url": "https://assets.gov.ie/q2.xlsx",
            "file_type": "xlsx",
        },
    ])
    write_disclosure_files_output(steps_dir, tmp_path)
    data = json.loads((tmp_path / "public" / "disclosure-files.json").read_text())
    assert len(data) == 2
    ids = {r["public_body_id"] for r in data}
    assert ids == {1001, 1002}


# ---------------------------------------------------------------------------
# write_foi_disclosures_output
# ---------------------------------------------------------------------------


def _make_deduplicate_steps_dir(tmp_path, results):
    """Helper: write extract_disclosures_deduplicate/output.json into a steps dir."""
    steps_dir = tmp_path / "steps"
    dedup_dir = steps_dir / "extract_disclosures_deduplicate"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "output.json").write_text(json.dumps({
        "metadata": {"step": "extract_disclosures_deduplicate"},
        "results": results,
    }))
    return steps_dir


def test_write_foi_disclosures_output_returns_correct_path(tmp_path):
    steps_dir = _make_deduplicate_steps_dir(tmp_path, [])
    path = write_foi_disclosures_output(steps_dir, tmp_path)
    assert path == tmp_path / "public" / "foi-disclosures.json"


def test_write_foi_disclosures_output_creates_file(tmp_path):
    steps_dir = _make_deduplicate_steps_dir(tmp_path, [])
    write_foi_disclosures_output(steps_dir, tmp_path)
    assert (tmp_path / "public" / "foi-disclosures.json").exists()


def test_write_foi_disclosures_output_content(tmp_path):
    record = {
        "public_body_id": 1001,
        "name": "Dept A",
        "file_url": "https://x.ie/q1.xlsx",
        "file_type": "xlsx",
        "foi_reference_id": "16/001",
        "decision_date": None,
        "requester_type": None,
        "decision_status": None,
        "review_status": None,
        "related_request": None,
        "request_description": "Test request",
    }
    steps_dir = _make_deduplicate_steps_dir(tmp_path, [record])
    write_foi_disclosures_output(steps_dir, tmp_path)
    data = json.loads((tmp_path / "public" / "foi-disclosures.json").read_text())
    assert len(data) == 1
    assert data[0] == record


def test_write_foi_disclosures_output_returns_none_when_no_input(tmp_path):
    steps_dir = tmp_path / "steps"
    steps_dir.mkdir()
    path = write_foi_disclosures_output(steps_dir, tmp_path)
    assert path is None


def test_write_foi_disclosures_output_creates_public_dir(tmp_path):
    steps_dir = _make_deduplicate_steps_dir(tmp_path, [])
    write_foi_disclosures_output(steps_dir, tmp_path)
    assert (tmp_path / "public").is_dir()


def test_write_foi_disclosures_output_multiple_bodies(tmp_path):
    records = [
        {
            "public_body_id": 1001, "name": "Dept A",
            "file_url": "https://x.ie/q1.xlsx", "file_type": "xlsx",
            "foi_reference_id": "16/001", "decision_date": None,
            "requester_type": None, "decision_status": None, "review_status": None,
            "related_request": None, "request_description": "First",
        },
        {
            "public_body_id": 1002, "name": "Dept B",
            "file_url": "https://y.ie/q1.xlsx", "file_type": "xlsx",
            "foi_reference_id": "17/001", "decision_date": None,
            "requester_type": None, "decision_status": None, "review_status": None,
            "related_request": None, "request_description": "Second",
        },
    ]
    steps_dir = _make_deduplicate_steps_dir(tmp_path, records)
    write_foi_disclosures_output(steps_dir, tmp_path)
    data = json.loads((tmp_path / "public" / "foi-disclosures.json").read_text())
    assert len(data) == 2
    ids = {r["public_body_id"] for r in data}
    assert ids == {1001, 1002}


# ---------------------------------------------------------------------------
# verified flag — overridden records propagate verified: True
# ---------------------------------------------------------------------------

def test_validate_websites_overridden_sets_verified():
    body_map = make_body_map(1001)
    merge_validate_websites(body_map, {
        "results": [{"public_body_id": 1001, "is_reachable": True, "overridden": True}]
    })
    assert body_map[1001]["status"]["website_url"].get("verified") is True


def test_validate_websites_not_overridden_omits_verified():
    body_map = make_body_map(1001)
    merge_validate_websites(body_map, {
        "results": [{"public_body_id": 1001, "is_reachable": True}]
    })
    assert "verified" not in body_map[1001]["status"]["website_url"]


def test_find_foi_pages_overridden_sets_verified():
    body_map = make_body_map(1001)
    merge_find_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "foi_page_url": "https://dept-a.ie/foi/", "overridden": True}]
    })
    assert body_map[1001]["status"]["foi_page"].get("verified") is True


def test_find_foi_pages_not_overridden_omits_verified():
    body_map = make_body_map(1001)
    merge_find_foi_pages(body_map, {
        "results": [{"public_body_id": 1001, "foi_page_url": "https://dept-a.ie/foi/"}]
    })
    assert "verified" not in body_map[1001]["status"]["foi_page"]


def test_get_foi_emails_overridden_sets_verified():
    body_map = make_body_map(1001)
    merge_get_foi_emails(body_map, {
        "results": [{"public_body_id": 1001, "foi_email": "foi@dept-a.ie", "email_status": "found", "overridden": True}]
    })
    assert body_map[1001]["status"]["foi_email"].get("verified") is True


def test_get_foi_emails_not_overridden_omits_verified():
    body_map = make_body_map(1001)
    merge_get_foi_emails(body_map, {
        "results": [{"public_body_id": 1001, "foi_email": "foi@dept-a.ie", "email_status": "found"}]
    })
    assert "verified" not in body_map[1001]["status"]["foi_email"]


def test_find_disclosure_pages_overridden_sets_verified():
    body_map = make_body_map(1001)
    merge_find_disclosure_pages(body_map, {
        "results": [{"public_body_id": 1001, "disclosure_page_url": "https://dept-a.ie/disclosure/", "overridden": True}]
    })
    assert body_map[1001]["status"]["disclosures_page"].get("verified") is True


def test_find_disclosure_pages_not_overridden_omits_verified():
    body_map = make_body_map(1001)
    merge_find_disclosure_pages(body_map, {
        "results": [{"public_body_id": 1001, "disclosure_page_url": "https://dept-a.ie/disclosure/"}]
    })
    assert "verified" not in body_map[1001]["status"]["disclosures_page"]


def test_scoped_export_only_targets_body(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {"find_public_bodies_subject_to_foi": BASE_OUTPUT})
    result = merge(steps_dir, PIPELINE_STEPS, target_public_body=1002)
    body_ids = [b["public_body_id"] for b in result]
    assert body_ids == [1002]
    assert 1001 not in body_ids


# ---------------------------------------------------------------------------
# Orphan guard: disclosure ids must exist in the canonical body map
# ---------------------------------------------------------------------------

def test_collect_disclosure_ids_extracts_ids_from_results():
    step_data = {"results": [{"public_body_id": 1001}, {"public_body_id": 1002}]}
    assert collect_disclosure_ids(step_data) == {1001, 1002}


def test_collect_disclosure_ids_empty_results():
    assert collect_disclosure_ids({"results": []}) == set()


def test_merge_raises_on_orphan_disclosure_id(tmp_path):
    """A disclosure record referencing a public_body_id absent from the
    canonical body map must raise loudly, naming the offending id and step."""
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
        "extract_disclosures_canonicalize": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001},
                {"public_body_id": 9999},  # orphan: not in BASE_OUTPUT (1001, 1002)
            ],
        },
    })
    with pytest.raises(ValueError) as exc:
        merge(steps_dir, PIPELINE_STEPS)
    msg = str(exc.value)
    assert "9999" in msg
    assert "extract_disclosures_canonicalize" in msg
    assert "1001" not in msg  # valid ids must not be reported


def test_merge_raises_on_orphan_in_find_disclosure_files(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
        "find_disclosure_files": {
            "metadata": {},
            "results": [
                {"public_body_id": 8888, "file_url": "x", "file_type": "xlsx"},
            ],
        },
    })
    with pytest.raises(ValueError) as exc:
        merge(steps_dir, PIPELINE_STEPS)
    assert "8888" in str(exc.value)
    assert "find_disclosure_files" in str(exc.value)


def test_merge_does_not_raise_when_all_disclosure_ids_valid(tmp_path):
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
        "find_disclosure_files": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001, "file_url": "x", "file_type": "xlsx"},
                {"public_body_id": 1002, "file_url": "y", "file_type": "pdf"},
            ],
        },
        "extract_disclosures_canonicalize": {
            "metadata": {},
            "results": [{"public_body_id": 1001}, {"public_body_id": 1002}],
        },
    })
    result = merge(steps_dir, PIPELINE_STEPS)  # must not raise
    assert {b["public_body_id"] for b in result} == {1001, 1002}


def test_scoped_export_does_not_false_positive_on_other_bodies_ids(tmp_path):
    """A single-body run must only see the targeted body's disclosure records,
    so another body's id present in the raw output must not trip the guard."""
    steps_dir = setup_steps_dir(tmp_path, {
        "find_public_bodies_subject_to_foi": BASE_OUTPUT,
        "extract_disclosures_canonicalize": {
            "metadata": {},
            "results": [
                {"public_body_id": 1001},
                {"public_body_id": 9999},  # filtered out when scoping to 1002
            ],
        },
    })
    # Scope to 1002: the 9999 record is filtered out before the guard sees it.
    result = merge(steps_dir, PIPELINE_STEPS, target_public_body=1002)
    assert [b["public_body_id"] for b in result] == [1002]


def test_disclosure_steps_are_registered_mergers():
    """Every guarded disclosure step must also have a real merger."""
    from steps.export_status.process import STEP_MERGERS
    for step in DISCLOSURE_STEPS:
        assert step in STEP_MERGERS

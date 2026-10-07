import json
from pathlib import Path
from unittest import mock

import pytest

from steps.extract_motions.process import (
    STEP_NAME,
    build_user_prompt,
    extract_one,
    process,
)
from lib.file_utils import read_json


def _doc(motions=None, text="…minutes text…"):
    d = {
        "public_body_id": 1511, "municipal_district": "Navan",
        "file_url": "https://x.ie/m.pdf", "meeting_date": "2024-07-08",
        "text": text,
    }
    if motions is not None:
        d["motions"] = motions
    return d


def test_extract_one_parses_motions():
    payload = {"motions": [
        {"motion_text": "That the council…", "proposer": "Cllr A",
         "seconder": "Cllr B", "status_label": "carried"}
    ]}
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(_doc())
    assert record["motions"] == payload["motions"]


def test_extract_one_none_on_bad_json():
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=None):
        record = extract_one(_doc())
    assert record["motions"] is None


def test_process_logs_error_with_full_file_url(tmp_path, make_writer):
    # Deep path + query string so a regression (collapse to the bare domain)
    # is unambiguous.
    full_url = ("https://www.meath.ie/system/files/media/file-uploads/2026-05/"
                "05-2026%20Minutes%20Navan%20MD.pdf?ver=2")
    item = _doc()
    item["file_url"] = full_url
    with mock.patch("steps.extract_motions.process.extract_json", return_value=None):
        writer = make_writer(STEP_NAME, key_field="file_url")
        process({"results": [item]}, tmp_path, writer)
        writer.finalize()
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "MotionExtractionError"
    ctx = errors[0]["context"]
    assert ctx["file_url"] == full_url    # full URL preserved, not collapsed to a domain
    assert "url" not in ctx


def test_extract_one_passes_llm_date_through_as_stated_date():
    payload = {"meeting_date": "10th October", "motions": [
        {"motion_text": "That the council…", "proposer": "Cllr A",
         "seconder": "Cllr B", "status_label": "carried"}
    ]}
    doc = _doc()
    doc["meeting_date"] = None            # nothing deterministic upstream
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(doc)
    assert record["stated_date"] == "10th October"   # raw, unvalidated
    assert record["meeting_date"] is None             # untouched, not resolved
    assert record["motions"] == payload["motions"]


def test_extract_one_stated_date_none_when_llm_omits_it():
    payload = {"motions": []}
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(_doc())
    assert record["stated_date"] is None
    assert record["motions"] == []


def test_extract_one_bad_json_still_sets_stated_date_key():
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=None):
        record = extract_one(_doc())
    assert record["motions"] is None
    assert record["stated_date"] is None


def test_extract_one_defaults_preserve_current_call():
    with mock.patch("steps.extract_motions.process.extract_json", return_value={"motions": []}) as m:
        extract_one(_doc())
        assert m.call_args.kwargs.get("model") is None


def test_extract_one_preserves_nonnull_upstream_meeting_date():
    payload = {"meeting_date": "2024-09-09", "motions": [
        {"motion_text": "That the council…", "proposer": "Cllr A",
         "seconder": "Cllr B", "status_label": "carried"}
    ]}
    doc = _doc()
    doc["meeting_date"] = "2024-01-02"    # non-null deterministic upstream date
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(doc)
    assert record["meeting_date"] == "2024-01-02"     # upstream preserved, untouched
    assert record["stated_date"] == "2024-09-09"      # LLM value carried through raw
    assert record["motions"] == payload["motions"]

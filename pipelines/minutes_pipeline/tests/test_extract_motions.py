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
from steps.extract_motions.chunking import MAX_CHUNK_CHARS, split_text
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
        assert m.call_args.kwargs.get("effort") is None


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


def _payload(text, *, date=None):
    return {"meeting_date": date, "motions": [
        {"motion_text": text, "proposer": "Cllr A", "seconder": "Cllr B",
         "status_label": "carried"}
    ]}


def test_short_doc_makes_exactly_one_call_with_the_current_prompt():
    doc = _doc(text="a" * (MAX_CHUNK_CHARS - 1))
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value={"motions": []}) as m:
        extract_one(doc)
    assert m.call_count == 1
    prompt = m.call_args.args[1]
    assert prompt.startswith(
        "Extract the motions from these minutes "
        "(municipal district Navan, meeting date 2024-07-08).\n\n"
    )
    assert prompt.split("\n\n", 1)[1] == doc["text"]


def test_exactly_max_chars_makes_exactly_one_call():
    doc = _doc(text="a" * MAX_CHUNK_CHARS)
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value={"motions": []}) as m:
        extract_one(doc)
    assert m.call_count == 1


def test_large_doc_calls_once_per_chunk_and_merges_in_order():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    payloads = [_payload("m1"), _payload("m2"), _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads) as m:
        record = extract_one(doc)
    assert m.call_count == len(split_text(text)) == 3
    bodies = [call.args[1].split("\n\n", 1)[1] for call in m.call_args_list]
    assert bodies == split_text(text)
    assert all(len(body) <= MAX_CHUNK_CHARS for body in bodies)
    assert [x["motion_text"] for x in record["motions"]] == ["m1", "m2", "m3"]


def test_chunked_extraction_dedupes_an_overlap_duplicate():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    payloads = [_payload("same motion"), _payload("same motion"), _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads):
        record = extract_one(doc)
    assert [x["motion_text"] for x in record["motions"]] == ["same motion", "m3"]


def test_within_chunk_duplicates_are_preserved():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    same = _payload("same motion")["motions"][0]
    payloads = [{"motions": [same, same]}, _payload("m2"), _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads):
        record = extract_one(doc)
    assert [x["motion_text"] for x in record["motions"]] == [
        "same motion", "same motion", "m2", "m3"
    ]


def test_chunked_extraction_uses_first_non_null_stated_date():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    payloads = [{"meeting_date": None, "motions": []},
                _payload("m2", date="2024-09-09"),
                _payload("m3", date="2024-10-10")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads):
        record = extract_one(doc)
    assert record["stated_date"] == "2024-09-09"


def test_one_failed_chunk_fails_the_whole_document_and_stops_early():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    payloads = [_payload("m1", date="2024-09-09"), None, _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads) as m:
        record = extract_one(doc)
    assert m.call_count == 2
    assert record["motions"] is None
    assert record["stated_date"] == "2024-09-09"
    assert record["failed_chunks"] == [2]
    assert record["chunk_count"] == 3


def test_a_non_object_motion_item_fails_the_chunk():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    payloads = [{"motions": ["not an object"]}, _payload("m2"), _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads):
        record = extract_one(doc)
    assert record["motions"] is None
    assert record["failed_chunks"] == [1]
    assert record["chunk_count"] == 3


def test_chunked_prompt_asks_for_complete_motions_only():
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    doc = _doc(text=text)
    payloads = [_payload("m1"), _payload("m2"), _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads) as m:
        extract_one(doc)
    second_prompt = m.call_args_list[1].args[1]
    assert "part 2 of 3" in second_prompt
    assert "fully contained" in second_prompt.lower()


def test_process_logs_failed_chunk_context(tmp_path, make_writer):
    text = "".join(chr(0x10000 + i) for i in range(200_000))
    item = _doc(text=text)
    payloads = [_payload("m1"), None, _payload("m3")]
    with mock.patch("steps.extract_motions.process.extract_json",
                    side_effect=payloads):
        writer = make_writer(STEP_NAME, key_field="file_url")
        process({"results": [item]}, tmp_path, writer)
        writer.finalize()
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "MotionExtractionError"
    assert errors[0]["context"]["failed_chunks"] == [2]
    assert errors[0]["context"]["chunk_count"] == 3
    assert errors[0]["context"]["file_url"] == item["file_url"]

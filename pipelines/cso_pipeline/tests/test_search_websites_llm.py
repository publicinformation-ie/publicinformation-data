import json
from pathlib import Path

import pytest

from steps.search_websites_llm.process import (
    build_user_prompt,
    parse_llm_response,
    process,
    STEP_NAME,
)
from lib.file_utils import IncrementalWriter, read_json


def _make_body(id, name, parent_name=None, gov_dept=None, legal_status="State Body", cro=None):
    return {
        "public_body_id": id,
        "name": name,
        "legal_status": legal_status,
        "parent_name": parent_name,
        "government_department": gov_dept,
        "cro": cro,
        "official_website_url": None,
    }


def _input_data(*bodies):
    return {"public_bodies": list(bodies)}


# ── build_user_prompt ─────────────────────────────────────────────────────────

def test_build_prompt_includes_name():
    prompt = build_user_prompt(_make_body(1, "Abbey Theatre"))
    assert "Abbey Theatre" in prompt


def test_build_prompt_includes_parent_and_department():
    body = _make_body(1, "Some Agency", parent_name="Dept of Health", gov_dept="Department of Health")
    prompt = build_user_prompt(body)
    assert "Dept of Health" in prompt
    assert "Department of Health" in prompt


def test_build_prompt_shows_none_when_no_parent():
    prompt = build_user_prompt(_make_body(1, "Some Agency"))
    assert "none" in prompt.lower()


# ── parse_llm_response ────────────────────────────────────────────────────────

def test_parse_llm_response_valid_json():
    raw = '{"url": "https://example.ie", "url_type": "direct", "confidence": "high", "notes": "Found it"}'
    result = parse_llm_response(raw)
    assert result["url"] == "https://example.ie"
    assert result["confidence"] == "high"


def test_parse_llm_response_markdown_fenced():
    raw = '```json\n{"url": null, "url_type": null, "confidence": "not_found", "notes": "Nothing"}\n```'
    result = parse_llm_response(raw)
    assert result["confidence"] == "not_found"
    assert result["url"] is None


def test_parse_llm_response_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_llm_response("Sorry, I cannot find that body.")


# ── process() ─────────────────────────────────────────────────────────────────

_HIGH = {"url": "https://abbeytheatre.ie", "url_type": "direct", "confidence": "high", "notes": "Direct site"}
_LOW = {"url": "https://artscouncil.ie", "url_type": "parent", "confidence": "low", "notes": "Parent only"}


def test_process_enriches_body_with_llm_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.search_websites_llm.process.call_mistral",
        lambda prompt, api_key: _HIGH,
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "Abbey Theatre")), tmp_path, writer, api_key="test", delay=0)
    writer.finalize()

    record = read_json(output_path)["results"][0]
    assert record["llm_website_url"] == "https://abbeytheatre.ie"
    assert record["llm_url_type"] == "direct"
    assert record["llm_confidence"] == "high"
    assert record["llm_notes"] == "Direct site"


def test_process_logs_parse_error_and_writes_null_confidence(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.search_websites_llm.process.call_mistral",
        lambda prompt, api_key: (_ for _ in ()).throw(ValueError("bad json")),
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "Some Body")), tmp_path, writer, api_key="test", delay=0)
    writer.finalize()

    record = read_json(output_path)["results"][0]
    assert record["llm_confidence"] is None
    assert record["llm_website_url"] is None

    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "LLMParseError"


def test_process_passes_through_high_and_low_confidence(tmp_path, monkeypatch):
    responses = [_HIGH, _LOW]
    call_count = [0]

    def _rotating(prompt, api_key):
        r = responses[call_count[0] % 2]
        call_count[0] += 1
        return r

    monkeypatch.setattr("steps.search_websites_llm.process.call_mistral", _rotating)
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "Abbey Theatre"), _make_body(2, "Arts Council")), tmp_path, writer, api_key="test", delay=0)
    writer.finalize()

    results = read_json(output_path)["results"]
    assert results[0]["llm_confidence"] == "high"
    assert results[1]["llm_confidence"] == "low"

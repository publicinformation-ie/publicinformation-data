import json
from unittest.mock import patch

import pytest

from steps.resolve_website_urls.process import process
from lib.file_utils import IncrementalWriter


def _make_body(id, name, url=None):
    return {"public_body_id": id, "name": name, "official_website_url": url, "sector": "S13"}


def test_null_url_passes_through_without_fetch(tmp_path):
    """Bodies with null official_website_url must be written through; no HTTP call, no error."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch") as mock_fetch:
        process({"public_bodies": [_make_body(1, "Some Body CLG")]}, tmp_path, writer)

    mock_fetch.assert_not_called()

    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []

    writer.finalize()
    output = json.loads(output_path.read_text())
    results = output.get("results", output.get("public_bodies", []))
    assert len(results) == 1
    assert results[0]["official_website_url"] is None


def test_no_failed_ids_file_created(tmp_path):
    """process() must not create failed_ids.json; failures are tracked via errors.json."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch"):
        process({"public_bodies": [_make_body(42, "Ghost Body")]}, tmp_path, writer)

    assert not (tmp_path / "failed_ids.json").exists()


def test_fetch_failure_id_appears_in_errors(tmp_path):
    """When a fetch fails, the body's ID must appear in errors.json context."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch", side_effect=Exception("timeout")):
        process({"public_bodies": [_make_body(99, "Failing Body", url="http://example.com")]}, tmp_path, writer)

    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["context"]["public_body_id"] == 99


def test_results_key_accepted_as_input(tmp_path):
    """process() must work when input uses 'results' key (IncrementalWriter output format)."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch"):
        process({"results": [_make_body(7, "Body A")]}, tmp_path, writer)

    writer.finalize()
    output = json.loads(output_path.read_text())
    results = output.get("results", [])
    assert len(results) == 1

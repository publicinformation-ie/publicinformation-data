from steps.transform_disclosure_files.mistral_ocr import markdown_to_rows


def test_markdown_to_rows_simple_table():
    markdown = "| Ref | Date |\n|---|---|\n| 16/002 | 2016-01-05 |"
    rows = markdown_to_rows(markdown)
    assert rows == [["Ref", "Date"], ["16/002", "2016-01-05"]]


def test_markdown_to_rows_multi_line_cell_joined_with_space():
    markdown = (
        "| Ref | Description |\n"
        "|---|---|\n"
        "| 16/002 | Request for\ninformation about roads |"
    )
    rows = markdown_to_rows(markdown)
    assert rows == [["Ref", "Description"], ["16/002", "Request for information about roads"]]


def test_markdown_to_rows_strips_formatting():
    markdown = (
        "| Ref | Status |\n"
        "|---|---|\n"
        "| **16/002** | *Granted* `partial` ~~pending~~ [link](http://x.com) |"
    )
    rows = markdown_to_rows(markdown)
    assert rows == [["Ref", "Status"], ["16/002", "Granted partial pending link"]]


def test_markdown_to_rows_multiple_tables_separated_by_page_break():
    markdown = (
        "| Ref | Date |\n|---|---|\n| A | 1 |"
        "\n---\n"
        "| Ref | Date |\n|---|---|\n| B | 2 |"
    )
    rows = markdown_to_rows(markdown)
    assert rows == [["Ref", "Date"], ["A", "1"], ["Ref", "Date"], ["B", "2"]]


def test_markdown_to_rows_empty_input_returns_empty_list():
    assert markdown_to_rows("") == []
    assert markdown_to_rows(None) == []
    assert markdown_to_rows("   ") == []


from steps.transform_disclosure_files.mistral_ocr import _strip_duplicate_headers


def test_strip_duplicate_headers_exact_repeat_removed():
    rows = [
        ["Ref", "Date"],
        ["A", "1"],
        ["Ref", "Date"],
        ["B", "2"],
    ]
    deduped, count = _strip_duplicate_headers(rows)
    assert deduped == [["Ref", "Date"], ["A", "1"], ["B", "2"]]
    assert count == 1


def test_strip_duplicate_headers_normalizes_whitespace_and_case():
    rows = [
        ["Ref", "Date"],
        ["A", "1"],
        ["  ref  ", "DATE"],
        ["B", "2"],
    ]
    deduped, count = _strip_duplicate_headers(rows)
    assert deduped == [["Ref", "Date"], ["A", "1"], ["B", "2"]]
    assert count == 1


def test_strip_duplicate_headers_near_match_not_removed():
    rows = [
        ["Ref", "Date"],
        ["A", "1"],
        ["Ref", "Date Received"],
        ["B", "2"],
    ]
    deduped, count = _strip_duplicate_headers(rows)
    assert deduped == rows
    assert count == 0


def test_strip_duplicate_headers_single_page_is_noop():
    rows = [["Ref", "Date"], ["A", "1"], ["B", "2"]]
    deduped, count = _strip_duplicate_headers(rows)
    assert deduped == rows
    assert count == 0


def test_strip_duplicate_headers_empty_input():
    deduped, count = _strip_duplicate_headers([])
    assert deduped == []
    assert count == 0


import hashlib
import json
import time
import unittest.mock

from steps.transform_disclosure_files.mistral_ocr import call_mistral_ocr


def _mock_ocr_response(markdown_parts):
    """Build a mock object shaped like the mistralai OCR response:
    response.pages[i].tables[j].markdown"""
    table = unittest.mock.MagicMock()
    table.markdown = markdown_parts[0] if markdown_parts else None
    table.content = None
    page = unittest.mock.MagicMock()
    page.tables = [table] if markdown_parts else []
    response = unittest.mock.MagicMock()
    response.pages = [page]
    response.tables = []
    return response


def test_call_mistral_ocr_cache_hit_returns_without_api_call(tmp_path):
    cache_dir = tmp_path / "ocr_cache"
    cache_dir.mkdir()
    file_url = "https://example.com/a.pdf"
    sha256 = hashlib.sha256(file_url.encode("utf-8")).hexdigest()
    (cache_dir / f"{sha256}.json").write_text(json.dumps({
        "file_url": file_url,
        "markdown": "| Ref |\n|---|\n| A |",
        "cached_at": "2026-01-01T00:00:00+00:00",
    }))
    with unittest.mock.patch("steps.transform_disclosure_files.mistral_ocr.Mistral") as mock_client_cls:
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key")
    mock_client_cls.assert_not_called()
    assert result == "| Ref |\n|---|\n| A |"


def test_call_mistral_ocr_success_writes_cache(tmp_path):
    cache_dir = tmp_path / "ocr_cache"
    file_url = "https://example.com/a.pdf"
    sha256 = hashlib.sha256(file_url.encode("utf-8")).hexdigest()
    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.return_value = _mock_ocr_response(["| Ref |\n|---|\n| A |"])
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ) as mock_client_cls:
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key")
    assert result == "| Ref |\n|---|\n| A |"
    mock_client_cls.assert_called_once_with(api_key="fake-key")
    call_kwargs = mock_client.ocr.process.call_args.kwargs
    assert call_kwargs["document"]["document_url"] == f"https://base.example.com/{sha256}.bytes"
    assert call_kwargs["table_format"] == "markdown"
    assert call_kwargs["extract_header"] is True
    cached = json.loads((cache_dir / f"{sha256}.json").read_text())
    assert cached["file_url"] == file_url
    assert cached["markdown"] == "| Ref |\n|---|\n| A |"
    assert "cached_at" in cached


def test_call_mistral_ocr_empty_result_returns_empty_string_and_caches_it(tmp_path):
    cache_dir = tmp_path / "ocr_cache"
    file_url = "https://example.com/a.pdf"
    sha256 = hashlib.sha256(file_url.encode("utf-8")).hexdigest()
    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.return_value = _mock_ocr_response([])
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ):
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key")
    assert result == ""
    cached = json.loads((cache_dir / f"{sha256}.json").read_text())
    assert cached["markdown"] == ""


def test_call_mistral_ocr_retries_then_fails_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    cache_dir = tmp_path / "ocr_cache"
    file_url = "https://example.com/a.pdf"
    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.side_effect = Exception("api error")
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ):
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key", max_retries=3)
    assert result is None
    assert mock_client.ocr.process.call_count == 3
    sha256 = hashlib.sha256(file_url.encode("utf-8")).hexdigest()
    assert not (cache_dir / f"{sha256}.json").exists()


def test_call_mistral_ocr_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    cache_dir = tmp_path / "ocr_cache"
    file_url = "https://example.com/a.pdf"
    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.side_effect = [
        Exception("api error"),
        _mock_ocr_response(["| Ref |\n|---|\n| A |"]),
    ]
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ):
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key", max_retries=3)
    assert result == "| Ref |\n|---|\n| A |"
    assert mock_client.ocr.process.call_count == 2


def test_call_mistral_ocr_uses_content_attribute_when_markdown_absent(tmp_path):
    cache_dir = tmp_path / "ocr_cache"
    file_url = "https://example.com/a.pdf"
    table = unittest.mock.MagicMock()
    table.markdown = None
    table.content = "| Ref |\n|---|\n| A |"
    page = unittest.mock.MagicMock()
    page.tables = [table]
    response = unittest.mock.MagicMock()
    response.pages = [page]
    response.tables = []
    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.return_value = response
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ):
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key")
    assert result == "| Ref |\n|---|\n| A |"


def test_call_mistral_ocr_semaphore_bounds_concurrent_calls(tmp_path, monkeypatch):
    """Two calls sharing a Semaphore(1) must not run their API call
    concurrently — the second blocks until the first releases."""
    import threading

    cache_dir = tmp_path / "ocr_cache"
    semaphore = threading.Semaphore(1)
    concurrent_count = {"current": 0, "max": 0}
    lock = threading.Lock()

    def slow_process(**kwargs):
        with lock:
            concurrent_count["current"] += 1
            concurrent_count["max"] = max(concurrent_count["max"], concurrent_count["current"])
        time.sleep(0.05)
        with lock:
            concurrent_count["current"] -= 1
        return _mock_ocr_response(["| Ref |\n|---|\n| A |"])

    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.side_effect = slow_process
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ):
        threads = [
            threading.Thread(target=call_mistral_ocr, args=(
                f"https://example.com/{i}.pdf", cache_dir, "https://base.example.com", "fake-key", semaphore
            ))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert concurrent_count["max"] == 1

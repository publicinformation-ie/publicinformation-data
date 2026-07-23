from steps.transform_disclosure_files.mistral_ocr import markdown_to_pages, _PAGE_BREAK_MARKER


def test_markdown_to_pages_single_page():
    markdown = "| Ref | Date |\n|---|---|\n| 16/002 | 2016-01-05 |"
    pages = markdown_to_pages(markdown)
    assert pages == [[["Ref", "Date"], ["16/002", "2016-01-05"]]]


def test_markdown_to_pages_multiple_pages_split_on_marker():
    markdown = (
        "| Ref | Date |\n|---|---|\n| A | 1 |"
        + _PAGE_BREAK_MARKER
        + "| Ref | Date |\n|---|---|\n| B | 2 |"
    )
    pages = markdown_to_pages(markdown)
    assert pages == [
        [["Ref", "Date"], ["A", "1"]],
        [["Ref", "Date"], ["B", "2"]],
    ]


def test_markdown_to_pages_title_rows_before_header_on_first_page_only():
    """Mirrors the National Transport Authority PDFs: page 1 opens with a
    document title and a subtitle row before the real column header; page 2
    starts directly with the header. This is the exact shape that made the
    old rows[0]-based _strip_duplicate_headers silently strip nothing."""
    page1_markdown = (
        "| National Transport Authority - FOI Disclosure Log (Non-Personal Requests) |\n"
        "| Quarter 2 2024 (1 April 2024 - 30 June 2024) |\n"
        "| FOI Reference | Date Received | Decision | Date Decision letter issued |\n"
        "|---|---|---|---|\n"
        "| 2024-0028 | 08/04/2024 | Part-Granted | 19/04/2024 |"
    )
    page2_markdown = (
        "| FOI Reference | Date Received | Decision | Date Decision letter issued |\n"
        "|---|---|---|---|\n"
        "| 2024-0042 | 09/04/2024 | Part-Granted | 14/05/2024 |"
    )
    markdown = page1_markdown + _PAGE_BREAK_MARKER + page2_markdown
    pages = markdown_to_pages(markdown)
    assert pages == [
        [
            ["National Transport Authority - FOI Disclosure Log (Non-Personal Requests)"],
            ["Quarter 2 2024 (1 April 2024 - 30 June 2024)"],
            ["FOI Reference", "Date Received", "Decision", "Date Decision letter issued"],
            ["2024-0028", "08/04/2024", "Part-Granted", "19/04/2024"],
        ],
        [
            ["FOI Reference", "Date Received", "Decision", "Date Decision letter issued"],
            ["2024-0042", "09/04/2024", "Part-Granted", "14/05/2024"],
        ],
    ]


def test_markdown_to_pages_strips_formatting_and_joins_multiline_cells():
    markdown = (
        "| Ref | Description |\n"
        "|---|---|\n"
        "| **16/002** | Request for\ninformation `about` roads |"
    )
    pages = markdown_to_pages(markdown)
    assert pages == [[["Ref", "Description"], ["16/002", "Request for information about roads"]]]


def test_markdown_to_pages_empty_input_returns_empty_list():
    assert markdown_to_pages("") == []
    assert markdown_to_pages(None) == []
    assert markdown_to_pages("   ") == []


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


def test_call_mistral_ocr_joins_multiple_pages_with_page_break_marker(tmp_path):
    from steps.transform_disclosure_files.mistral_ocr import _PAGE_BREAK_MARKER

    cache_dir = tmp_path / "ocr_cache"
    file_url = "https://example.com/two-pages.pdf"

    table1 = unittest.mock.MagicMock()
    table1.markdown = "| Ref | Date |\n|---|---|\n| A | 1 |"
    table1.content = None
    page1 = unittest.mock.MagicMock()
    page1.tables = [table1]

    table2 = unittest.mock.MagicMock()
    table2.markdown = "| Ref | Date |\n|---|---|\n| B | 2 |"
    table2.content = None
    page2 = unittest.mock.MagicMock()
    page2.tables = [table2]

    response = unittest.mock.MagicMock()
    response.pages = [page1, page2]
    response.tables = []

    mock_client = unittest.mock.MagicMock()
    mock_client.ocr.process.return_value = response
    with unittest.mock.patch(
        "steps.transform_disclosure_files.mistral_ocr.Mistral", return_value=mock_client
    ):
        result = call_mistral_ocr(file_url, cache_dir, "https://base.example.com", "fake-key")

    assert result == (
        "| Ref | Date |\n|---|---|\n| A | 1 |"
        + _PAGE_BREAK_MARKER
        + "| Ref | Date |\n|---|---|\n| B | 2 |"
    )


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

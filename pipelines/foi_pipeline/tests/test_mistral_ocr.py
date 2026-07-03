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

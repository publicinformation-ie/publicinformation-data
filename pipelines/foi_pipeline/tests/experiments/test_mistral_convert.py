"""Tests for Mistral markdown to rows conversion."""
import importlib.util
from pathlib import Path

# Import the convert module using importlib since the directory has hyphens
_CONVERT_PATH = Path(__file__).parents[2] / "experiments/2025-01-03-mistral-ocr-comparison/convert.py"
spec = importlib.util.spec_from_file_location("mistral_convert", _CONVERT_PATH)
assert spec is not None and spec.loader is not None
_convert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_convert)

markdown_to_rows = _convert.markdown_to_rows


def test_simple_table():
    """Test conversion of a simple markdown table."""
    markdown = """| Reference | Date Received | Description |
|-----------|---------------|-------------|
| FOI-2024-001 | 2024-01-15 | Request for documents |
| FOI-2024-002 | 2024-01-16 | Another request |
"""
    expected = [
        ["Reference", "Date Received", "Description"],
        ["FOI-2024-001", "2024-01-15", "Request for documents"],
        ["FOI-2024-002", "2024-01-16", "Another request"]
    ]
    result = markdown_to_rows(markdown)
    assert result == expected


def test_table_with_page_breaks():
    """Test conversion with page break separators."""
    markdown = """| Ref | Date |
|-----|------|
| A-1 | 2024-01-01 |

---

| Ref | Date |
|-----|------|
| B-1 | 2024-01-02 |
"""
    expected = [
        ["Ref", "Date"],
        ["A-1", "2024-01-01"],
        ["Ref", "Date"],
        ["B-1", "2024-01-02"]
    ]
    result = markdown_to_rows(markdown)
    assert result == expected


def test_multiline_cells():
    """Test conversion with multi-line cells."""
    markdown = """| Description |
|-------------|
| Line 1
Line 2 |
| Single |
"""
    expected = [
        ["Description"],
        ["Line 1 Line 2"],
        ["Single"]
    ]
    result = markdown_to_rows(markdown)
    assert result == expected


def test_empty_markdown():
    """Test conversion with no tables."""
    markdown = "No tables found"
    result = markdown_to_rows(markdown)
    assert result == []


def test_stripped_formatting():
    """Test that markdown formatting is stripped from cells."""
    markdown = """| **Bold** | *Italic* | `Code` |
|----------|----------|---------|
| **A** | *B* | `C` |
"""
    expected = [
        ["Bold", "Italic", "Code"],
        ["A", "B", "C"]
    ]
    result = markdown_to_rows(markdown)
    assert result == expected

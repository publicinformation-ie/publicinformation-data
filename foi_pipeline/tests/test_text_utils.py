import pytest
from scripts.text_utils import normalize_text, normalize_cell, normalize_header

class TestNormalizeText:
    def test_non_string_passthrough(self):
        assert normalize_text(None) is None
        assert normalize_text(123) == 123
        assert normalize_text([1, 2, 3]) == [1, 2, 3]

    def test_pdf_newlines(self):
        assert normalize_text("Requestor\nType", file_type="pdf") == "Requestor Type"
        assert normalize_text("FOI\nOutcome", file_type="pdf") == "FOI Outcome"
        assert normalize_text("Request\nAssignment\nID", file_type="pdf") == "Request Assignment ID"

    def test_pdf_cid_artefacts(self):
        assert normalize_text("hello(cid:123)world", file_type="pdf") == "helloworld"

    def test_pdf_multi_spaces(self):
        assert normalize_text("hello   world", file_type="pdf") == "hello world"

    def test_whitespace_stripping(self):
        assert normalize_text("  hello  ") == "hello"
        assert normalize_text("\nhello\n") == "hello"

    def test_header_normalization(self):
        assert normalize_text("Requestor Type", for_header=True) == "requestor type"
        assert normalize_text("FOI Decision.", for_header=True) == "foi decision"

    def test_non_pdf_passthrough(self):
        # XLSX/XLS just get whitespace stripping
        assert normalize_text("  hello  ", file_type="xlsx") == "hello"
        assert normalize_text("hello\nworld", file_type="xlsx") == "hello\nworld"

class TestNormalizeCell:
    def test_pdf_cell_with_newlines(self):
        assert normalize_cell("Requestor\nType", file_type="pdf") == "Requestor Type"

class TestNormalizeHeader:
    def test_newlines_in_header(self):
        assert normalize_header("Requestor\nType") == "requestor type"

    def test_underscores(self):
        assert normalize_header("Requestor_Type") == "requestor type"

    def test_trailing_punctuation(self):
        assert normalize_header("Decision:") == "decision"
        assert normalize_header("Decision .") == "decision"

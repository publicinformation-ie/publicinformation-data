"""Tests for extract_disclosures_split_combined_columns step."""
import pytest
from steps.extract_disclosures_split_combined_columns.process import (
    split_cell,
    split_file,
)


class TestSplitCell:
    def test_none_returns_none_none(self):
        assert split_cell(None) == (None, None)

    def test_empty_returns_empty_none(self):
        assert split_cell("") == ("", None)

    def test_pure_iso_date_no_description(self):
        assert split_cell("2022-12-29") == ("2022-12-29", None)

    def test_pure_dd_month_yyyy_date_no_description(self):
        assert split_cell("29 December 2022") == ("29 December 2022", None)

    def test_combined_iso_date_and_description(self):
        date, desc = split_cell("2022-12-29 Records relating to SEM capacity")
        assert date == "2022-12-29"
        assert desc == "Records relating to SEM capacity"

    def test_combined_long_date_and_description(self):
        date, desc = split_cell(
            "29 December 2022 The most recently updated Department Brief"
        )
        assert date == "29 December 2022"
        assert desc == "The most recently updated Department Brief"

    def test_description_spans_multiple_sentences(self):
        date, desc = split_cell(
            "29 December 2022 Records relating to SEM. Including all attachments."
        )
        assert date == "29 December 2022"
        assert desc == "Records relating to SEM. Including all attachments."

    def test_dd_mm_yyyy_slash_format(self):
        date, desc = split_cell("29/12/2022 Records relating to SEM")
        assert date == "29/12/2022"
        assert desc == "Records relating to SEM"

    def test_ordinal_date_format(self):
        date, desc = split_cell("1st January 2023 All departmental emails")
        assert date == "1st January 2023"
        assert desc == "All departmental emails"

    def test_non_string_passthrough(self):
        assert split_cell(42) == (42, None)


class TestSplitFile:
    def _make_item(self, headers, data_rows, header_row_idx=0, **kwargs):
        return {
            "public_body_id": 1,
            "name": "Test Body",
            "file_url": "https://example.com/test.pdf",
            "file_type": "pdf",
            "header_row_idx": header_row_idx,
            "rows": [headers] + data_rows,
            **kwargs,
        }

    def test_no_combined_column_unchanged(self):
        item = self._make_item(
            ["Ref", "Date Received", "Request Details"],
            [["001", "2022-01-01", "Some request"]],
        )
        result, errors = split_file(item)
        assert result["rows"] == item["rows"]
        assert errors == []

    def test_splits_combined_column(self):
        item = self._make_item(
            ["FOI No.", "Requester", "Date and Details of Request Received", "Decision"],
            [
                ["FOI001", "Journalist", "29 December 2022 Records about emissions", "Granted"],
                ["FOI002", "Individual", "2022-12-28 All ministerial briefings", "Refused"],
            ],
        )
        result, errors = split_file(item)
        assert errors == []
        new_headers = result["rows"][0]
        assert new_headers == ["FOI No.", "Requester", "Date Received", "Request Details", "Decision"]
        row1 = result["rows"][1]
        assert row1 == ["FOI001", "Journalist", "29 December 2022", "Records about emissions", "Granted"]
        row2 = result["rows"][2]
        assert row2 == ["FOI002", "Individual", "2022-12-28", "All ministerial briefings", "Refused"]

    def test_pure_date_only_cell_gets_none_description(self):
        item = self._make_item(
            ["FOI No.", "Date and Details of Request Received", "Decision"],
            [["FOI001", "2022-12-29", "Granted"]],
        )
        result, errors = split_file(item)
        assert errors == []
        row = result["rows"][1]
        assert row[1] == "2022-12-29"
        assert row[2] is None  # no description
        assert row[3] == "Granted"

    def test_none_cell_in_combined_column(self):
        item = self._make_item(
            ["FOI No.", "Date and Details of Request Received", "Decision"],
            [["FOI001", None, "Granted"]],
        )
        result, errors = split_file(item)
        assert errors == []
        row = result["rows"][1]
        assert row[1] is None
        assert row[2] is None

    def test_no_rows_returns_unchanged(self):
        item = {"file_url": "x", "rows": None, "header_row_idx": None}
        result, errors = split_file(item)
        assert result is item
        assert errors == []

    def test_no_header_row_idx_returns_unchanged(self):
        item = {"file_url": "x", "rows": [["a", "b"]], "header_row_idx": None}
        result, errors = split_file(item)
        assert result is item
        assert errors == []

    def test_case_insensitive_header_match(self):
        item = self._make_item(
            ["Ref", "Date And Details Of Request Received", "Decision"],
            [["001", "29 December 2022 Some request", "Granted"]],
        )
        result, errors = split_file(item)
        assert errors == []
        assert result["rows"][0][1] == "Date Received"
        assert result["rows"][0][2] == "Request Details"

    def test_header_row_idx_nonzero(self):
        item = self._make_item(
            ["Date and Details of Request Received", "Decision"],
            [["29 December 2022 Some request", "Granted"]],
            header_row_idx=1,
        )
        # header_row_idx=1 means rows[0] is a title row, rows[1] is the header
        item["rows"].insert(0, ["Title Row", None])
        result, errors = split_file(item)
        assert errors == []
        assert result["rows"][1][0] == "Date Received"
        assert result["rows"][2][0] == "29 December 2022"
        assert result["rows"][2][1] == "Some request"

"""Tests for extract_disclosures_split_combined_columns step."""
import pytest
from steps.extract_disclosures_split_combined_columns.process import (
    split_cell,
    split_file,
    split_refid_date_cell,
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


class TestSplitRefidDateCell:
    """Tests for the new refID+date combined cell splitter."""

    def test_none_returns_none_none(self):
        assert split_refid_date_cell(None) == (None, None)

    def test_non_string_returns_none_none(self):
        assert split_refid_date_cell(42) == (None, None)

    def test_pure_date_returns_none_date(self):
        # A clean date — no refID present
        assert split_refid_date_cell("18/01/2017") == (None, "18/01/2017")

    def test_pure_refid_returns_refid_none(self):
        # Just a 5-digit FOI reference number
        assert split_refid_date_cell("7191") == ("7191", None)

    def test_pure_refid_4digit(self):
        assert split_refid_date_cell("9557") == ("9557", None)

    def test_refid_then_date(self):
        # 2017 file pattern: refID space date
        assert split_refid_date_cell("7190 19/01/2017") == ("7190", "19/01/2017")

    def test_refid_then_date_hyphen_format(self):
        assert split_refid_date_cell("7190 19-01-2017") == ("7190", "19-01-2017")

    def test_date_then_refid(self):
        # 2022-q3 / 2022-q2 pattern: date space refID
        assert split_refid_date_cell("06/07/2022 19447") == ("19447", "06/07/2022")

    def test_date_then_refid_dot_format(self):
        assert split_refid_date_cell("06.07.2022 19447") == ("19447", "06.07.2022")

    def test_asterisk_prefix_stripped(self):
        # 2018 file pattern: asterisk then date then refID
        assert split_refid_date_cell("*02/01/2018 9559") == ("9559", "02/01/2018")

    def test_asterisk_pure_refid(self):
        assert split_refid_date_cell("*9557") == ("9557", None)

    def test_pure_date_no_refid_dd_mm_yyyy(self):
        assert split_refid_date_cell("02/10/2023") == (None, "02/10/2023")

    def test_empty_string_returns_none_none(self):
        assert split_refid_date_cell("") == (None, None)


class TestSplitFileRefidDate:
    """Tests for split_file detecting and splitting refID+date columns."""

    def _make_item(self, headers, data_rows, header_row_idx=0, **kwargs):
        return {
            "public_body_id": 1211,
            "name": "Department of Social Protection",
            "file_url": "https://assets.gov.ie/static/documents/foi-disclosure-log-2017.pdf",
            "file_type": "pdf",
            "header_row_idx": header_row_idx,
            "rows": [headers] + data_rows,
            **kwargs,
        }

    def test_pure_refid_in_date_column_splits(self):
        # 2017 / 2023-q4 style: col 1 has "Date of Request" but cells contain pure refIDs
        item = self._make_item(
            [None, "Date of Request", "Category", "Summary", "Decision", "Date of Reply"],
            [
                [None, "18/01/2017", "Journalist", "Some request summary", None, None],
                ["12", "7191", "Journalist", "Other request", "Granted", "15/02/2017"],
                ["13", "7190 19/01/2017", "public", "Third request", "Refused", "25/01/2017"],
            ],
        )
        result, errors = split_file(item)
        assert errors == []
        # A new "FOI Reference Number" column is inserted at position 2
        new_headers = result["rows"][0]
        assert new_headers[1] == "Date of Request"
        assert new_headers[2] == "FOI Reference Number"
        # Row with pure date: date stays, refID is None
        row0 = result["rows"][1]
        assert row0[1] == "18/01/2017"
        assert row0[2] is None
        # Row with pure refID: date is None, refID extracted
        row1 = result["rows"][2]
        assert row1[1] is None
        assert row1[2] == "7191"
        # Row with combined refID+date: date extracted, refID extracted
        row2 = result["rows"][3]
        assert row2[1] == "19/01/2017"
        assert row2[2] == "7190"

    def test_date_then_refid_pattern(self):
        # 2022-q3 style: date comes first in combined cells
        item = self._make_item(
            ["Date Received", "Category of", "Request", "Decision", "Decision Date"],
            [
                ["05/07/2022", "Others", "Some request", "Granted", "18/07/2022"],
                ["19443", None, "Other request continuation", None, None],
                ["06/07/2022 19447", "Others", "Third request", "Granted", "25/07/2022"],
            ],
        )
        result, errors = split_file(item)
        assert errors == []
        new_headers = result["rows"][0]
        assert new_headers[0] == "Date Received"
        assert new_headers[1] == "FOI Reference Number"
        # Pure date row
        assert result["rows"][1][0] == "05/07/2022"
        assert result["rows"][1][1] is None
        # Pure refID row
        assert result["rows"][2][0] is None
        assert result["rows"][2][1] == "19443"
        # Combined date+refID row
        assert result["rows"][3][0] == "06/07/2022"
        assert result["rows"][3][1] == "19447"

    def test_date_column_without_refids_unchanged(self):
        # Normal date column — no integers — must NOT be split
        item = self._make_item(
            ["Ref", "Date Received", "Decision"],
            [
                ["001", "05/07/2022", "Granted"],
                ["002", "06/07/2022", "Refused"],
                ["003", None, "Pending"],
            ],
        )
        result, errors = split_file(item)
        assert result["rows"] == item["rows"]
        assert errors == []

    def test_decision_date_column_with_refids_also_splits(self):
        # 2022-q2 has 'Date' header (-> decision_date canonical) but same pattern
        item = self._make_item(
            ["Date", "Category of", "Request", "Decision", "Date of"],
            [
                ["05/04/2022 18894", "Journalist", "Some request", "Part Granted", "03/05/2022"],
                ["08/04/2022", "Member of the", "Other request", "Granted", "11/04/2022"],
                ["18908", "Public", None, None, None],
            ],
        )
        result, errors = split_file(item)
        assert errors == []
        assert result["rows"][0][0] == "Date"
        assert result["rows"][0][1] == "FOI Reference Number"
        # Combined date+refID row
        assert result["rows"][1][0] == "05/04/2022"
        assert result["rows"][1][1] == "18894"
        # Pure date row
        assert result["rows"][2][0] == "08/04/2022"
        assert result["rows"][2][1] is None
        # Pure refID row
        assert result["rows"][3][0] is None
        assert result["rows"][3][1] == "18908"

    def test_existing_combined_date_description_still_works(self):
        # The original COMBINED_DATE_HEADERS logic must still work after this change
        item = self._make_item(
            ["FOI No.", "Date and Details of Request Received", "Decision"],
            [["FOI001", "29 December 2022 Records about emissions", "Granted"]],
        )
        result, errors = split_file(item)
        assert errors == []
        assert result["rows"][0][1] == "Date Received"
        assert result["rows"][0][2] == "Request Details"
        assert result["rows"][1][1] == "29 December 2022"
        assert result["rows"][1][2] == "Records about emissions"

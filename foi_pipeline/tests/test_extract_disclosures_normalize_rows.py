"""Tests for extract_disclosures_normalize_rows step."""
import pytest
from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile

from steps.extract_disclosures_normalize_rows.process import (
    normalize_date_value,
    is_date_column,
    process_file,
    process,
    STEP_NAME,
    _two_digit_year,
    _is_valid_date,
)


class TestNormalizeDateValue:
    """Tests for normalize_date_value() function."""

    def test_none_returns_none(self):
        assert normalize_date_value(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_date_value("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_date_value("   ") is None

    def test_na_returns_none(self):
        assert normalize_date_value("N/A") is None

    def test_na_variants_return_none(self):
        assert normalize_date_value("NA") is None
        assert normalize_date_value("na") is None
        assert normalize_date_value("n/a") is None
        assert normalize_date_value("null") is None
        assert normalize_date_value("-") is None
        assert normalize_date_value("---") is None

    def test_non_date_text_returns_none(self):
        assert normalize_date_value("Decision Date") is None
        assert normalize_date_value("Part Granted") is None
        assert normalize_date_value("granted") is None

    # DD/MM/YYYY format tests
    def test_dd_mm_yyyy_slash(self):
        assert normalize_date_value("01/02/2023") == "2023-02-01"

    def test_d_m_yyyy_slash(self):
        assert normalize_date_value("1/2/2023") == "2023-02-01"

    def test_dd_m_yyyy_slash(self):
        assert normalize_date_value("01/2/2023") == "2023-02-01"

    def test_d_mm_yyyy_slash(self):
        assert normalize_date_value("1/02/2023") == "2023-02-01"

    # DD-MM-YYYY format tests
    def test_dd_mm_yyyy_dash(self):
        assert normalize_date_value("01-02-2023") == "2023-02-01"

    def test_d_m_yyyy_dash(self):
        assert normalize_date_value("1-2-2023") == "2023-02-01"

    # DD.MM.YYYY format tests
    def test_dd_mm_yyyy_dot(self):
        assert normalize_date_value("01.02.2023") == "2023-02-01"

    def test_d_m_yyyy_dot(self):
        assert normalize_date_value("1.02.2023") == "2023-02-01"

    # DD Month YYYY format tests
    def test_dd_month_yyyy(self):
        assert normalize_date_value("01 February 2023") == "2023-02-01"

    def test_d_month_yyyy(self):
        assert normalize_date_value("1 February 2023") == "2023-02-01"

    def test_dd_month_abbrev_yyyy(self):
        assert normalize_date_value("01 Feb 2023") == "2023-02-01"

    def test_d_month_abbrev_yyyy(self):
        assert normalize_date_value("1 Feb 2023") == "2023-02-01"

    # Month DD, YYYY format tests
    def test_month_dd_comma_yyyy(self):
        assert normalize_date_value("February 01, 2023") == "2023-02-01"

    def test_month_d_comma_yyyy(self):
        assert normalize_date_value("February 1, 2023") == "2023-02-01"

    # Ordinal format tests
    def test_ordinal_day_month_yyyy(self):
        assert normalize_date_value("14th July 2016") == "2016-07-14"

    def test_ordinal_1st_month_yyyy(self):
        assert normalize_date_value("1st January 2020") == "2020-01-01"

    def test_ordinal_2nd_month_yyyy(self):
        assert normalize_date_value("2nd February 2021") == "2021-02-02"

    def test_ordinal_3rd_month_yyyy(self):
        assert normalize_date_value("3rd March 2022") == "2022-03-03"

    # Short year format tests
    def test_short_year_dd_mmm_yy(self):
        assert normalize_date_value("30-Jul-25") == "2025-07-30"

    def test_short_year_dd_mmm_yy_20th_century(self):
        assert normalize_date_value("01-Jan-99") == "1999-01-01"

    def test_short_year_dd_mmm_yy_21st_century(self):
        assert normalize_date_value("01-Jan-05") == "2005-01-01"

    # ISO 8601 format (pass-through)
    def test_iso_8601_passthrough(self):
        assert normalize_date_value("2023-02-01") == "2023-02-01"

    # Two-digit year tests
    def test_two_digit_year_slash(self):
        assert normalize_date_value("01/02/23") == "2023-02-01"

    def test_two_digit_year_20th_century(self):
        assert normalize_date_value("01/02/99") == "1999-02-01"


class TestIsDateColumn:
    """Tests for is_date_column() function."""

    def test_date_received_true(self):
        assert is_date_column("Date Received") is True

    def test_date_received_lowercase_true(self):
        assert is_date_column("date received") is True

    def test_date_received_variant_true(self):
        assert is_date_column("Date Rec'd") is True

    def test_decision_date_true(self):
        assert is_date_column("Decision Date") is True

    def test_decision_date_lowercase_true(self):
        assert is_date_column("decision date") is True

    def test_date_issued_true(self):
        assert is_date_column("Date Issued") is True

    def test_date_of_request_true(self):
        assert is_date_column("Date of Request") is True

    def test_description_false(self):
        assert is_date_column("Description") is False

    def test_request_details_false(self):
        assert is_date_column("Request Details") is False

    def test_none_false(self):
        assert is_date_column(None) is False

    def test_empty_string_false(self):
        assert is_date_column("") is False


class TestProcessFile:
    """Tests for process_file() function."""

    BASE_META = {
        "public_body_id": 1001,
        "name": "Dept A",
        "file_url": "https://assets.gov.ie/log.xlsx",
        "file_type": "xlsx",
    }

    def test_process_file_no_rows(self):
        item = {**self.BASE_META, "rows": None, "header_row_idx": None}
        result, errors = process_file(item, Path("/tmp"))
        assert result == item
        assert errors == []

    def test_process_file_no_header_row_idx(self):
        item = {**self.BASE_META, "rows": [["A", "B"], ["1", "2"]], "header_row_idx": None}
        result, errors = process_file(item, Path("/tmp"))
        assert result == item
        assert errors == []

    def test_process_file_header_row_out_of_bounds(self):
        item = {**self.BASE_META, "rows": [["A", "B"]], "header_row_idx": 5}
        result, errors = process_file(item, Path("/tmp"))
        assert result == item
        assert errors == []

    def test_process_file_no_date_columns(self):
        item = {
            **self.BASE_META,
            "rows": [
                ["Our Reference", "Request Details"],
                ["16/001", "some request"],
            ],
            "header_row_idx": 0,
        }
        result, errors = process_file(item, Path("/tmp"))
        assert result["rows"] == item["rows"]
        assert errors == []

    def test_process_file_with_date_column(self):
        item = {
            **self.BASE_META,
            "rows": [
                ["Our Reference", "Date Received", "Request Details"],
                ["16/001", "01/02/2023", "some request"],
                ["16/002", "15-03-2023", "another request"],
            ],
            "header_row_idx": 0,
        }
        result, errors = process_file(item, Path("/tmp"))
        assert result["rows"][1][1] == "2023-02-01"
        assert result["rows"][2][1] == "2023-03-15"
        assert result["rows"][1][0] == "16/001"  # non-date column unchanged
        assert result["rows"][1][2] == "some request"  # non-date column unchanged
        assert errors == []

    def test_process_file_unparseable_date(self):
        item = {
            **self.BASE_META,
            "rows": [
                ["Our Reference", "Date Received"],
                ["16/001", "Not a date"],
            ],
            "header_row_idx": 0,
        }
        result, errors = process_file(item, Path("/tmp"))
        assert result["rows"][1][1] is None
        assert len(errors) == 1
        assert errors[0]["error_type"] == "UnparseableDate"
        assert errors[0]["context"]["original_value"] == "Not a date"
        assert errors[0]["context"]["canonical_column"] == "date_received"

    def test_process_file_multiple_date_columns(self):
        item = {
            **self.BASE_META,
            "rows": [
                ["Date Received", "Decision Date", "Description"],
                ["01/02/2023", "15/03/2023", "request 1"],
            ],
            "header_row_idx": 0,
        }
        result, errors = process_file(item, Path("/tmp"))
        assert result["rows"][1][0] == "2023-02-01"
        assert result["rows"][1][1] == "2023-03-15"
        assert result["rows"][1][2] == "request 1"

    def test_process_file_decision_date_column(self):
        item = {
            **self.BASE_META,
            "rows": [
                ["Ref", "Decision Date"],
                ["1", "01 February 2023"],
            ],
            "header_row_idx": 0,
        }
        result, errors = process_file(item, Path("/tmp"))
        assert result["rows"][1][1] == "2023-02-01"

    def test_process_file_preserves_metadata(self):
        item = {
            **self.BASE_META,
            "sheet_name": "Sheet1",
            "rows": [["Date Received"], ["01/02/2023"]],
            "header_row_idx": 0,
        }
        result, errors = process_file(item, Path("/tmp"))
        assert result["public_body_id"] == 1001
        assert result["name"] == "Dept A"
        assert result["file_url"] == "https://assets.gov.ie/log.xlsx"
        assert result["file_type"] == "xlsx"
        assert result["sheet_name"] == "Sheet1"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_two_digit_year_00_to_29(self):
        assert _two_digit_year("00") == 2000
        assert _two_digit_year("29") == 2029

    def test_two_digit_year_30_to_99(self):
        assert _two_digit_year("30") == 1930
        assert _two_digit_year("99") == 1999

    def test_is_valid_date_valid(self):
        assert _is_valid_date(2023, 2, 1) is True
        assert _is_valid_date(2020, 12, 31) is True
        assert _is_valid_date(2020, 2, 29) is True  # Leap year

    def test_is_valid_date_invalid_year(self):
        assert _is_valid_date(1899, 1, 1) is False
        assert _is_valid_date(2101, 1, 1) is False

    def test_is_valid_date_invalid_month(self):
        assert _is_valid_date(2023, 0, 1) is False
        assert _is_valid_date(2023, 13, 1) is False

    def test_is_valid_date_invalid_day(self):
        assert _is_valid_date(2023, 2, 0) is False
        assert _is_valid_date(2023, 2, 30) is False  # February doesn't have 30 days
        assert _is_valid_date(2023, 4, 31) is False  # April doesn't have 31 days

    def test_is_valid_date_non_leap_year(self):
        assert _is_valid_date(2023, 2, 29) is False  # 2023 is not a leap year


class TestProcessFunction:
    """Tests for the main process() function."""

    def test_process_empty_results(self):
        input_data = {"results": []}
        results_out = []
        errors_out = []
        
        from lib.file_utils import IncrementalWriter
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = IncrementalWriter(
                Path(tmpdir) / "output.json",
                STEP_NAME,
                key_field="file_url",
                force=True
            )
            process(input_data, Path(tmpdir), writer)
            assert writer.results == []

    def test_process_with_valid_file(self):
        input_data = {
            "results": [
                {
                    "public_body_id": 1001,
                    "name": "Dept A",
                    "file_url": "https://assets.gov.ie/log.xlsx",
                    "file_type": "xlsx",
                    "rows": [
                        ["Date Received", "Description"],
                        ["01/02/2023", "request 1"],
                    ],
                    "header_row_idx": 0,
                }
            ]
        }
        
        import tempfile
        from lib.file_utils import IncrementalWriter
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = IncrementalWriter(
                Path(tmpdir) / "output.json",
                STEP_NAME,
                key_field="file_url",
                force=True
            )
            process(input_data, Path(tmpdir), writer)
            assert len(writer.results) == 1
            assert writer.results[0]["rows"][1][0] == "2023-02-01"


class TestMainFunction:
    """Integration tests for the main() function."""

    def test_main_with_sample_input(self, tmp_path, monkeypatch):
        import sys
        import os
        import shutil
        import steps.extract_disclosures_normalize_rows.process as proc_module
        
        # Copy process.py to temp location so step_dir resolution works
        process_src = Path(proc_module.__file__)
        process_dst = tmp_path / "process.py"
        shutil.copy2(str(process_src), str(process_dst))
        
        # Create sample input
        input_file = tmp_path / "input.json"
        input_data = {
            "metadata": {"step": "extract_disclosures_normalize_header"},
            "results": [
                {
                    "public_body_id": 1001,
                    "name": "Test Body",
                    "file_url": "https://example.com/test.xlsx",
                    "file_type": "xlsx",
                    "rows": [
                        ["Date Received", "Description"],
                        ["01/02/2023", "Test request"],
                    ],
                    "header_row_idx": 0,
                }
            ]
        }
        input_file.write_text(json.dumps(input_data))
        
        output_file = tmp_path / "output.json"
        
        # Create step dir structure
        step_dir = tmp_path / "steps" / "extract_disclosures_normalize_rows"
        step_dir.mkdir(parents=True)
        (step_dir / "override.json").write_text("[]")
        (step_dir / "__init__.py").write_text("")
        
        # Set argv
        test_argv = [
            str(process_dst),
            "--input", str(input_file),
            "--output", str(output_file),
            "--force",
        ]
        monkeypatch.setattr(sys, "argv", test_argv)
        
        # Change to tmp_path
        original_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        
        try:
            # Run main
            proc_module.main()
            
            # Check output
            output_data = json.loads(output_file.read_text())
            assert "results" in output_data
            assert len(output_data["results"]) == 1
            assert output_data["results"][0]["rows"][1][0] == "2023-02-01"
        finally:
            os.chdir(original_cwd)

    def test_main_skips_already_processed(self, tmp_path, monkeypatch):
        import sys
        import steps.extract_disclosures_normalize_rows.process as proc_module
        
        # Create existing output with same file_url
        output_file = tmp_path / "output.json"
        existing_output = {
            "metadata": {"step": STEP_NAME, "completed_at": "2025-01-01T00:00:00Z"},
            "results": [
                {
                    "public_body_id": 1001,
                    "name": "Test Body",
                    "file_url": "https://example.com/test.xlsx",
                    "file_type": "xlsx",
                    "rows": [["Date Received"], ["2023-02-01"]],
                    "header_row_idx": 0,
                }
            ]
        }
        output_file.write_text(json.dumps(existing_output))
        
        # Create input with same file_url
        input_file = tmp_path / "input.json"
        input_data = {
            "metadata": {"step": "extract_disclosures_normalize_header"},
            "results": [
                {
                    "public_body_id": 1001,
                    "name": "Test Body",
                    "file_url": "https://example.com/test.xlsx",
                    "file_type": "xlsx",
                    "rows": [["Date Received"], ["01/02/2023"]],
                    "header_row_idx": 0,
                }
            ]
        }
        input_file.write_text(json.dumps(input_data))
        
        # Mock __file__
        monkeypatch.setattr(proc_module, "__file__", str(tmp_path / "process.py"))
        
        # Create step dir structure
        step_dir = tmp_path / "steps" / "extract_disclosures_normalize_rows"
        step_dir.mkdir(parents=True)
        (step_dir / "override.json").write_text("[]")
        (step_dir / "__init__.py").write_text("")
        
        # Set argv - no --force flag
        test_argv = [
            "process.py",
            "--input", str(input_file),
            "--output", str(output_file),
        ]
        monkeypatch.setattr(sys, "argv", test_argv)
        
        # Run main
        proc_module.main()
        
        # Check output unchanged
        output_data = json.loads(output_file.read_text())
        # Should have the same results as before (not reprocessed)
        assert len(output_data["results"]) == 1

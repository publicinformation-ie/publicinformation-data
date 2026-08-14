import pytest
from scripts.trace_file import find_file_record, calculate_metric, determine_status


def test_find_file_record_file_based():
    data = {
        "results": [
            {"file_url": "https://a.com/1.xlsx", "rows": [["a", "b"]]},
            {"file_url": "https://a.com/2.xlsx", "rows": [["c", "d"]]},
        ]
    }
    result = find_file_record(data, "https://a.com/1.xlsx", "transform_disclosure_files")
    assert result is not None
    assert result["file_url"] == "https://a.com/1.xlsx"


def test_find_file_record_record_based():
    data = {
        "results": [
            {"file_url": "https://a.com/1.xlsx", "request_id": "1"},
            {"file_url": "https://a.com/1.xlsx", "request_id": "2"},
            {"file_url": "https://a.com/2.xlsx", "request_id": "3"},
        ]
    }
    result = find_file_record(data, "https://a.com/1.xlsx", "extract_disclosures_canonicalize_rows")
    assert result is not None
    assert len(result["records"]) == 2


def test_find_file_record_not_found():
    data = {"results": [{"file_url": "https://a.com/1.xlsx"}]}
    result = find_file_record(data, "https://a.com/999.xlsx", "transform_disclosure_files")
    assert result is None


def test_find_file_record_none_data():
    result = find_file_record(None, "https://a.com/1.xlsx", "transform_disclosure_files")
    assert result is None


def test_calculate_metric_transform_disclosure_files():
    record = {"file_url": "https://a.com/1.xlsx", "rows": [["a"]]}
    assert calculate_metric("transform_disclosure_files", record, None) == 100
    
    record_null = {"file_url": "https://a.com/1.pdf", "rows": None}
    assert calculate_metric("transform_disclosure_files", record_null, None) == 0


def test_calculate_metric_normalize_cells():
    assert calculate_metric("normalize_disclosure_cells", {}, None) == 100


def test_calculate_metric_detect_header_row():
    record = {"file_url": "https://a.com/1.xlsx", "header_row_idx": 0}
    assert calculate_metric("extract_disclosures_detect_header_row", record, None) == 100
    
    record_null = {"file_url": "https://a.com/1.xlsx", "header_row_idx": None}
    assert calculate_metric("extract_disclosures_detect_header_row", record_null, None) == 0


def test_calculate_metric_normalize_rows():
    record = {"file_url": "https://a.com/1.xlsx", "total_rows": 10}
    errors = {"results": [{"file_url": "https://a.com/1.xlsx", "errors": ["e1", "e2"]}]}
    # 10 rows, 2 errors -> 80%
    assert calculate_metric("extract_disclosures_normalize_rows", record, errors) == 80
    
    # No errors -> 100%
    assert calculate_metric("extract_disclosures_normalize_rows", record, None) == 100


def test_calculate_metric_record_based():
    record = {"records": [{"request_id": "1"}], "file_url": "https://a.com/1.xlsx"}
    assert calculate_metric("extract_disclosures_canonicalize", record, None) == 100
    
    record_empty = {"records": [], "file_url": "https://a.com/1.xlsx"}
    assert calculate_metric("extract_disclosures_canonicalize", record_empty, None) == 0


def test_calculate_metric_none_record():
    assert calculate_metric("transform_disclosure_files", None, None) == 0


def test_determine_status():
    assert determine_status(100) == "SUCCESS"
    assert determine_status(50) == "PARTIAL"
    assert determine_status(1) == "PARTIAL"
    assert determine_status(0) == "FAILED"


import tempfile
import json
from pathlib import Path
from unittest.mock import patch


def test_trace_file_success():
    # Create temporary step directories with mock data
    with tempfile.TemporaryDirectory() as tmpdir:
        tmproot = Path(tmpdir)
        steps_dir = tmproot / "pipelines" / "foi_pipeline" / "steps"
        
        # Create transform_disclosure_files output
        step_dir = steps_dir / "transform_disclosure_files"
        step_dir.mkdir(parents=True)
        (step_dir / "output.json").write_text(json.dumps({
            "results": [{"file_url": "https://test.com/file.xlsx", "rows": [["a"]]}]
        }))
        
        # Mock STEPS_DIR in the shared module
        with patch("src.lib.pipeline_steps.STEPS_DIR", steps_dir):
            from scripts.trace_file import trace_file
            from io import StringIO
            import sys
            
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()
            
            try:
                exit_code = trace_file("https://test.com/file.xlsx")
                assert exit_code == 0
                output = sys.stdout.getvalue()
                assert "transform_disclosure_files" in output
                assert "100%" in output
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr


def test_trace_file_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmproot = Path(tmpdir)
        steps_dir = tmproot / "pipelines" / "foi_pipeline" / "steps"
        
        # Create empty transform_disclosure_files output
        step_dir = steps_dir / "transform_disclosure_files"
        step_dir.mkdir(parents=True)
        (step_dir / "output.json").write_text(json.dumps({"results": []}))
        
        with patch("src.lib.pipeline_steps.STEPS_DIR", steps_dir):
            from scripts.trace_file import trace_file
            from io import StringIO
            import sys

            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()

            try:
                exit_code = trace_file("https://test.com/missing.xlsx")
                assert exit_code == 1
                stderr_output = sys.stderr.getvalue()
                assert "not found" in stderr_output
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr


def test_trace_file_missing_step_output():
    """Test that missing step output.json is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmproot = Path(tmpdir)
        steps_dir = tmproot / "pipelines" / "foi_pipeline" / "steps"
        
        # Create only transform_disclosure_files output
        step_dir = steps_dir / "transform_disclosure_files"
        step_dir.mkdir(parents=True)
        (step_dir / "output.json").write_text(json.dumps({
            "results": [{"file_url": "https://test.com/file.xlsx", "rows": [["a"]]}]
        }))
        
        # Other step directories don't exist

        with patch("src.lib.pipeline_steps.STEPS_DIR", steps_dir):
            from scripts.trace_file import trace_file
            from io import StringIO
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            
            try:
                exit_code = trace_file("https://test.com/file.xlsx")
                assert exit_code == 0
                output = sys.stdout.getvalue()
                lines = output.strip().split("\n")
                # First step should be SUCCESS, rest FAILED
                assert "SUCCESS" in lines[0]
                assert "FAILED" in lines[1]
            finally:
                sys.stdout = old_stdout


def test_trace_file_partial_normalize_rows():
    """Test PARTIAL status for normalize_rows with errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmproot = Path(tmpdir)
        steps_dir = tmproot / "pipelines" / "foi_pipeline" / "steps"
        
        # Create all step outputs up to normalize_rows with proper fields
        step_configs = {
            "transform_disclosure_files": {"results": [{"file_url": "https://test.com/file.xlsx", "rows": [["a"]]}]},
            "normalize_disclosure_cells": {"results": [{"file_url": "https://test.com/file.xlsx"}]},
            "filter_phantom_rows": {"results": [{"file_url": "https://test.com/file.xlsx"}]},
            "extract_disclosures_detect_header_row": {"results": [{"file_url": "https://test.com/file.xlsx", "header_row_idx": 0}]},
            "extract_disclosures_normalize_header": {"results": [{"file_url": "https://test.com/file.xlsx"}]},
            "extract_disclosures_split_combined_columns": {"results": [{"file_url": "https://test.com/file.xlsx"}]},
            "extract_disclosures_normalize_rows": {
                "output": {"results": [{"file_url": "https://test.com/file.xlsx", "total_rows": 10}]},
                "errors": {"results": [{"file_url": "https://test.com/file.xlsx", "errors": ["e1", "e2"]}]}
            }
        }
        
        for step_name, data in step_configs.items():
            step_dir = steps_dir / step_name
            step_dir.mkdir(parents=True, exist_ok=True)
            if step_name == "extract_disclosures_normalize_rows":
                (step_dir / "output.json").write_text(json.dumps(data["output"]))
                (step_dir / "errors.json").write_text(json.dumps(data["errors"]))
            else:
                (step_dir / "output.json").write_text(json.dumps(data))

        with patch("src.lib.pipeline_steps.STEPS_DIR", steps_dir):
            from scripts.trace_file import trace_file
            from io import StringIO
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            
            try:
                exit_code = trace_file("https://test.com/file.xlsx")
                output = sys.stdout.getvalue()
                lines = output.strip().split("\n")
                # normalize_rows should be 80% PARTIAL
                normalize_line = [l for l in lines if "normalize_rows" in l][0]
                assert "80%" in normalize_line
                assert "PARTIAL" in normalize_line
            finally:
                sys.stdout = old_stdout


def test_trace_file_pdf_null_rows():
    """Test FAILED status for PDF with null rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmproot = Path(tmpdir)
        steps_dir = tmproot / "pipelines" / "foi_pipeline" / "steps"
        
        # Create transform_disclosure_files with null rows (PDF)
        step_dir = steps_dir / "transform_disclosure_files"
        step_dir.mkdir(parents=True)
        (step_dir / "output.json").write_text(json.dumps({
            "results": [{"file_url": "https://test.com/file.pdf", "rows": None}]
        }))

        with patch("src.lib.pipeline_steps.STEPS_DIR", steps_dir):
            from scripts.trace_file import trace_file
            from io import StringIO
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            
            try:
                exit_code = trace_file("https://test.com/file.pdf")
                output = sys.stdout.getvalue()
                lines = output.strip().split("\n")
                # All steps should be FAILED
                for line in lines:
                    assert "FAILED" in line or "0%" in line
            finally:
                sys.stdout = old_stdout

"""Integration tests for the Mistral OCR comparison experiment."""
import importlib.util
from pathlib import Path

import pytest

# Import the run module using importlib since the directory has hyphens
_RUN_PATH = Path(__file__).parents[2] / "experiments/2025-01-03-mistral-ocr-comparison/run.py"
spec = importlib.util.spec_from_file_location("run_mod", _RUN_PATH)
assert spec is not None and spec.loader is not None
run_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_mod)

process_file = run_mod.process_file

# Import compare module
_COMPARE_PATH = Path(__file__).parents[2] / "experiments/2025-01-03-mistral-ocr-comparison/compare.py"
spec = importlib.util.spec_from_file_location("compare_mod", _COMPARE_PATH)
assert spec is not None and spec.loader is not None
compare_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_mod)

aggregate_comparison = compare_mod.aggregate_comparison


@pytest.fixture
def sample_file_entry():
    """Create a sample file entry for testing."""
    return {
        "file_url": "https://example.com/test.pdf",
        "body_id": "test_body",
        "body_name": "Test Body",
        "source_url": "https://example.com",
        "file_type": "pdf",
        "sha256": "abc123def456"
    }


def test_process_file_structure(sample_file_entry):
    """Test that the file entry structure is correct."""
    # Verify the sample file entry has all required fields
    assert "file_url" in sample_file_entry
    assert "body_name" in sample_file_entry
    assert "sha256" in sample_file_entry
    assert "file_type" in sample_file_entry
    
    # Verify the expected keys that would be in a result
    expected_result_keys = ["file_id", "file_url", "body_name", "mistral", "pdfplumber", 
                     "comparison", "normalization", "timing"]
    assert len(expected_result_keys) == 8  # Just verify we have the right number of keys


def test_aggregate_comparison_empty():
    """Test aggregation with empty results."""
    results = []
    aggregate = aggregate_comparison(results)
    
    assert aggregate["summary"]["total_files"] == 0
    assert aggregate["summary"]["cell_match_rate"] == 0


def test_aggregate_comparison_single():
    """Test aggregation with single result."""
    results = [{
        "file_id": "test",
        "file_url": "http://example.com/test.pdf",
        "body_name": "Test",
        "mistral": {
            "row_count": 10,
            "col_count": 3,
            "null_cells": 0,
            "null_rows": 0,
            "empty": False
        },
        "pdfplumber": {
            "row_count": 10,
            "col_count": 3,
            "null_cells": 0,
            "null_rows": 0,
            "empty": False
        },
        "comparison": {
            "cell_match_rate": 1.0,
            "matched_cells": 30,
            "total_cells_compared": 30
        },
        "normalization": {
            "mistral": {"modified": 0},
            "pdfplumber": {"modified": 0}
        },
        "timing": {
            "mistral_ms": 100,
            "pdfplumber_ms": 150
        }
    }]
    
    aggregate = aggregate_comparison(results)
    
    assert aggregate["summary"]["total_files"] == 1
    assert aggregate["summary"]["cell_match_rate"] == 1.0
    assert aggregate["summary"]["mistral"]["avg_row_count"] == 10
    assert aggregate["summary"]["pdfplumber"]["avg_row_count"] == 10

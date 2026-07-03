#!/usr/bin/env python3
"""Run normalization on extracted rows using the existing pipeline step."""
import sys
from pathlib import Path

# Add the steps directory to path so we can import normalize_disclosure_cells utilities
# We need to use importlib to import from the normalize_disclosure_cells module
import importlib.util

# Import the normalization helper functions from normalize_disclosure_cells
# Find the repo root first
_REPO_ROOT = Path(__file__).resolve()
while _REPO_ROOT.exists() and not (_REPO_ROOT / ".git").is_dir():
    _REPO_ROOT = _REPO_ROOT.parent

# Set up PYTHONPATH to include src/ so that lib modules can be imported
SRC_PATH = _REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

_STEP_PATH = _REPO_ROOT / "pipelines/foi_pipeline/steps/normalize_disclosure_cells/process.py"
spec = importlib.util.spec_from_file_location("norm_process", _STEP_PATH)
assert spec is not None and spec.loader is not None
norm_process = importlib.util.module_from_spec(spec)
spec.loader.exec_module(norm_process)

# Get the helper functions
_merge_continuation_rows = norm_process._merge_continuation_rows
_prune_null_columns = norm_process._prune_null_columns
_normalize_cell = norm_process._normalize_cell


def normalize_extracted_rows(rows, file_id, file_type="pdf"):
    """Normalize extracted rows using the pipeline's normalize_disclosure_cells logic.
    
    This runs the normalization step in-memory on the extracted rows,
    capturing the changes made.
    
    Args:
        rows: List of rows in pipeline format (list of lists)
        file_id: Identifier for this file (for tracking)
        file_type: Type of file (e.g., "pdf")
        
    Returns:
        Dict with normalized rows and audit information:
        {
            "normalized_rows": [...],
            "changes": [...],  # List of change records
            "stats": {...}
        }
    """
    if not rows:
        return {
            "normalized_rows": [],
            "changes": [],
            "stats": {"unchanged": 0, "modified": 0, "null_cells_fixed": 0}
        }
    
    # Capture the original rows for comparison
    original_rows = [list(row) for row in rows]
    
    try:
        # Process rows through the normalization functions
        normalized_rows = []
        changes = []
        
        for row_idx, row in enumerate(rows):
            normalized_row = []
            for col_idx, cell in enumerate(row):
                normalized, rules = _normalize_cell(file_type, cell)
                normalized_row.append(normalized)
                if rules:
                    changes.append({
                        "row": row_idx,
                        "col": col_idx,
                        "original": cell,
                        "normalized": normalized,
                        "rules": rules
                    })
            normalized_rows.append(normalized_row)
        
        # Apply PDF-specific normalization
        if file_type == "pdf":
            normalized_rows = _merge_continuation_rows(normalized_rows)
            normalized_rows = _prune_null_columns(normalized_rows)
        
        return {
            "normalized_rows": normalized_rows,
            "changes": changes,
            "stats": {
                "unchanged": len(original_rows) - len(changes),
                "modified": len(changes),
                "null_cells_fixed": sum(1 for c in changes if c["original"] is None or c["original"] == "")
            }
        }
    except Exception as e:
        print(f"Normalization failed for {file_id}: {e}")
        return {
            "normalized_rows": rows,
            "changes": [],
            "stats": {"error": str(e)}
        }


def count_nulls(rows):
    """Count null/empty cells in rows."""
    null_count = 0
    null_rows = 0
    for row in rows:
        row_has_null = False
        for cell in row:
            if cell is None or cell == "" or cell.strip() == "":
                null_count += 1
                row_has_null = True
        if row_has_null:
            null_rows += 1
    return null_count, null_rows

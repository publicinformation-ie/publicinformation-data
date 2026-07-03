#!/usr/bin/env python3
"""Compare extraction results between Mistral OCR and pdfplumber."""
import json
from pathlib import Path

# Import count_nulls from normalize module
import importlib.util

# Import count_nulls function
_REPO_ROOT = Path(__file__).resolve()
while _REPO_ROOT.exists() and not (_REPO_ROOT / ".git").is_dir():
    _REPO_ROOT = _REPO_ROOT.parent

# Set up PYTHONPATH to include src/ so that lib modules can be imported
import sys
SRC_PATH = _REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Import normalize module
_NORMALIZE_PATH = Path(__file__).parent / "normalize.py"
spec = importlib.util.spec_from_file_location("normalize_mod", _NORMALIZE_PATH)
assert spec is not None and spec.loader is not None
normalize_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(normalize_mod)
count_nulls = normalize_mod.count_nulls


def compute_file_metrics(rows, label):
    """Compute metrics for a single extraction result.
    
    Args:
        rows: List of rows (list of lists)
        label: Either 'mistral' or 'pdfplumber'
        
    Returns:
        Dict with computed metrics
    """
    if not rows:
        return {
            "row_count": 0,
            "col_count": 0,
            "null_cells": 0,
            "null_rows": 0,
            "empty": True
        }
    
    row_count = len(rows)
    col_count = max(len(row) for row in rows) if rows else 0
    null_cells, null_rows = count_nulls(rows)
    
    return {
        "row_count": row_count,
        "col_count": col_count,
        "null_cells": null_cells,
        "null_rows": null_rows,
        "empty": False
    }


def compare_rows(mistral_rows, pdfplumber_rows, sample_size=5):
    """Compare cell values between two extraction methods.
    
    Args:
        mistral_rows: Rows from Mistral OCR
        pdfplumber_rows: Rows from pdfplumber
        sample_size: Number of rows to compare (from the start)
        
    Returns:
        Dict with comparison results
    """
    # Determine the number of rows to compare
    min_rows = min(len(mistral_rows), len(pdfplumber_rows), sample_size)
    if min_rows == 0:
        return {
            "cell_match_rate": 0,
            "matched_cells": 0,
            "total_cells_compared": 0,
            "row_differences": []
        }
    
    matched_cells = 0
    total_cells = 0
    row_differences = []
    
    for i in range(min_rows):
        mistral_row = mistral_rows[i]
        pdfplumber_row = pdfplumber_rows[i]
        
        # Compare cells in this row
        min_cols = min(len(mistral_row), len(pdfplumber_row))
        row_matches = 0
        row_total = min_cols
        
        for j in range(min_cols):
            m_cell = mistral_row[j] if j < len(mistral_row) else None
            p_cell = pdfplumber_row[j] if j < len(pdfplumber_row) else None
            
            # Normalize for comparison (strip whitespace, handle None)
            m_val = (m_cell or "").strip()
            p_val = (p_cell or "").strip()
            
            if m_val == p_val:
                matched_cells += 1
                row_matches += 1
            
            total_cells += 1
        
        if row_total > 0:
            row_differences.append({
                "row_index": i,
                "match_rate": row_matches / row_total,
                "matched_cells": row_matches,
                "total_cells": row_total
            })
    
    cell_match_rate = matched_cells / total_cells if total_cells > 0 else 0
    
    return {
        "cell_match_rate": cell_match_rate,
        "matched_cells": matched_cells,
        "total_cells_compared": total_cells,
        "row_differences": row_differences
    }


def aggregate_comparison(results):
    """Aggregate comparison results across all files.
    
    Args:
        results: List of per-file comparison results
        
    Returns:
        Dict with aggregate summary
    """
    total_files = len(results)
    
    mistral_metrics = {
        "row_count": [],
        "col_count": [],
        "null_cells": [],
        "null_rows": []
    }
    pdfplumber_metrics = {
        "row_count": [],
        "col_count": [],
        "null_cells": [],
        "null_rows": []
    }
    
    cell_match_rates = []
    normalization_changes = {"mistral": [], "pdfplumber": []}
    processing_times = {"mistral": [], "pdfplumber": []}
    
    per_file_results = []
    
    for result in results:
        # Mistral metrics
        if result.get("mistral"):
            m = result["mistral"]
            if not m.get("empty"):
                mistral_metrics["row_count"].append(m["row_count"])
                mistral_metrics["col_count"].append(m["col_count"])
                mistral_metrics["null_cells"].append(m["null_cells"])
                mistral_metrics["null_rows"].append(m["null_rows"])
        
        # pdfplumber metrics
        if result.get("pdfplumber"):
            p = result["pdfplumber"]
            if not p.get("empty"):
                pdfplumber_metrics["row_count"].append(p["row_count"])
                pdfplumber_metrics["col_count"].append(p["col_count"])
                pdfplumber_metrics["null_cells"].append(p["null_cells"])
                pdfplumber_metrics["null_rows"].append(p["null_rows"])
        
        # Cell match rate
        if "comparison" in result:
            cell_match_rates.append(result["comparison"].get("cell_match_rate", 0))
        
        # Normalization changes
        if "normalization" in result:
            norm = result["normalization"]
            if "mistral" in norm:
                normalization_changes["mistral"].append(norm["mistral"].get("stats", {}).get("modified", 0))
            if "pdfplumber" in norm:
                normalization_changes["pdfplumber"].append(norm["pdfplumber"].get("stats", {}).get("modified", 0))
        
        # Processing time
        if "timing" in result:
            processing_times["mistral"].append(result["timing"].get("mistral_ms", 0))
            processing_times["pdfplumber"].append(result["timing"].get("pdfplumber_ms", 0))
        
        per_file_results.append({
            "file_id": result.get("file_id", "unknown"),
            "file_url": result.get("file_url", ""),
            "body_name": result.get("body_name", ""),
            "mistral": m if result.get("mistral") else None,
            "pdfplumber": p if result.get("pdfplumber") else None,
            "comparison": result.get("comparison", {}),
            "timing": result.get("timing", {})
        })
    
    def avg(values):
        return sum(values) / len(values) if values else 0
    
    summary = {
        "total_files": total_files,
        "mistral": {
            "avg_row_count": avg(mistral_metrics["row_count"]),
            "avg_col_count": avg(mistral_metrics["col_count"]),
            "avg_null_cells": avg(mistral_metrics["null_cells"]),
            "avg_null_rows": avg(mistral_metrics["null_rows"]),
            "files_processed": len(mistral_metrics["row_count"])
        },
        "pdfplumber": {
            "avg_row_count": avg(pdfplumber_metrics["row_count"]),
            "avg_col_count": avg(pdfplumber_metrics["col_count"]),
            "avg_null_cells": avg(pdfplumber_metrics["null_cells"]),
            "avg_null_rows": avg(pdfplumber_metrics["null_rows"]),
            "files_processed": len(pdfplumber_metrics["row_count"])
        },
        "cell_match_rate": avg(cell_match_rates),
        "avg_normalization_changes": {
            "mistral": avg(normalization_changes["mistral"]),
            "pdfplumber": avg(normalization_changes["pdfplumber"])
        },
        "avg_processing_time_ms": {
            "mistral": avg(processing_times["mistral"]),
            "pdfplumber": avg(processing_times["pdfplumber"])
        }
    }
    
    return {
        "summary": summary,
        "per_file": per_file_results
    }


def save_comparison(comparison_data, output_path):
    """Save comparison results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(comparison_data, f, indent=2)
    print(f"Comparison saved to {output_path}")

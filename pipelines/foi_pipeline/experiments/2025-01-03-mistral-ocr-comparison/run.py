#!/usr/bin/env python3
"""Main script for Mistral OCR vs pdfplumber comparison experiment."""
import json
import sys
import time
from pathlib import Path

# Set up PYTHONPATH to include src/ so that lib modules can be imported
_REPO_ROOT = Path(__file__).resolve()
while _REPO_ROOT.exists() and not (_REPO_ROOT / ".git").is_dir():
    _REPO_ROOT = _REPO_ROOT.parent
SRC_PATH = _REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Import local modules
import importlib.util

# Import extract module
_EXTRACT_PATH = Path(__file__).parent / "extract.py"
spec = importlib.util.spec_from_file_location("extract_mod", _EXTRACT_PATH)
assert spec is not None and spec.loader is not None
extract_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract_mod)

# Import convert module
_CONVERT_PATH = Path(__file__).parent / "convert.py"
spec = importlib.util.spec_from_file_location("convert_mod", _CONVERT_PATH)
assert spec is not None and spec.loader is not None
convert_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(convert_mod)

# Import normalize module
_NORMALIZE_PATH = Path(__file__).parent / "normalize.py"
spec = importlib.util.spec_from_file_location("normalize_mod", _NORMALIZE_PATH)
assert spec is not None and spec.loader is not None
normalize_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(normalize_mod)

# Import compare module
_COMPARE_PATH = Path(__file__).parent / "compare.py"
spec = importlib.util.spec_from_file_location("compare_mod", _COMPARE_PATH)
assert spec is not None and spec.loader is not None
compare_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_mod)

# Use the imported functions
extract_file = extract_mod.extract_file
load_sample = extract_mod.load_sample
normalize_extracted_rows = normalize_mod.normalize_extracted_rows
compute_file_metrics = compare_mod.compute_file_metrics
compare_rows = compare_mod.compare_rows
aggregate_comparison = compare_mod.aggregate_comparison
save_comparison = compare_mod.save_comparison

# Import file_utils for JSON operations
from lib.file_utils import write_json

RESULTS_DIR = Path(__file__).resolve().parent / "results"
SAMPLE_PATH = Path(__file__).resolve().parent / "sample.json"


def process_file(file_entry):
    """Process a single file through both extraction methods.
    
    Args:
        file_entry: Dict with file metadata
        
    Returns:
        Dict with extraction and comparison results for this file
    """
    file_id = file_entry["sha256"]
    print(f"\nProcessing {file_id[:8]}... ({file_entry.get('body_name', 'unknown')})")
    
    start_time = time.time()
    
    # Extract with both methods
    extraction = extract_file(file_entry, RESULTS_DIR)
    
    # Save raw outputs
    if extraction.get("mistral_raw"):
        raw_path = RESULTS_DIR / f"mistral_raw_{file_id}.json"
        write_json(raw_path, {"file_id": file_id, "markdown": extraction["mistral_raw"]})
    
    if extraction.get("pdfplumber_raw"):
        raw_path = RESULTS_DIR / f"pdfplumber_raw_{file_id}.json"
        write_json(raw_path, {"file_id": file_id, "rows": extraction["pdfplumber_raw"]})
    
    mistral_rows = extraction.get("mistral_rows", [])
    pdfplumber_rows = extraction.get("pdfplumber_raw", [])
    
    mistral_extract_time = time.time() - start_time
    
    # Normalize both
    start_time = time.time()
    mistral_norm = normalize_extracted_rows(mistral_rows, file_id, file_type="pdf")
    pdfplumber_norm = normalize_extracted_rows(pdfplumber_rows, file_id, file_type="pdf")
    pdfplumber_norm_time = time.time() - start_time
    
    # Save normalized outputs
    norm_path = RESULTS_DIR / f"mistral_normalized_{file_id}.json"
    write_json(norm_path, {
        "file_id": file_id,
        "rows": mistral_norm["normalized_rows"],
        "changes": mistral_norm["changes"],
        "stats": mistral_norm["stats"]
    })
    
    norm_path = RESULTS_DIR / f"pdfplumber_normalized_{file_id}.json"
    write_json(norm_path, {
        "file_id": file_id,
        "rows": pdfplumber_norm["normalized_rows"],
        "changes": pdfplumber_norm["changes"],
        "stats": pdfplumber_norm["stats"]
    })
    
    # Compute metrics
    mistral_metrics = compute_file_metrics(mistral_rows, "mistral")
    pdfplumber_metrics = compute_file_metrics(pdfplumber_rows, "pdfplumber")
    
    # Compare
    comparison = compare_rows(mistral_rows, pdfplumber_rows)
    
    result = {
        "file_id": file_id,
        "file_url": file_entry["file_url"],
        "body_name": file_entry.get("body_name", ""),
        "mistral": mistral_metrics,
        "pdfplumber": pdfplumber_metrics,
        "comparison": comparison,
        "normalization": {
            "mistral": mistral_norm["stats"],
            "pdfplumber": pdfplumber_norm["stats"]
        },
        "timing": {
            "extraction_ms": (mistral_extract_time + pdfplumber_norm_time) * 1000
        },
        "error": extraction.get("error")
    }
    
    print(f"  Mistral: {mistral_metrics['row_count']} rows, {mistral_metrics['col_count']} cols, {mistral_metrics['null_cells']} nulls")
    print(f"  pdfplumber: {pdfplumber_metrics['row_count']} rows, {pdfplumber_metrics['col_count']} cols, {pdfplumber_metrics['null_cells']} nulls")
    print(f"  Cell match rate: {comparison['cell_match_rate']:.2%}")
    
    return result


def main():
    """Run the full comparison experiment."""
    print("=" * 60)
    print("Mistral OCR vs pdfplumber Comparison Experiment")
    print("=" * 60)
    
    # Load sample
    sample = load_sample()
    print(f"\nLoaded sample with {sample['sample_size']} files")
    
    # Process each file
    results = []
    for i, file_entry in enumerate(sample["files"]):
        print(f"\n[{i+1}/{len(sample['files'])}]")
        try:
            result = process_file(file_entry)
            results.append(result)
        except Exception as e:
            print(f"Error processing {file_entry.get('file_url', 'unknown')}: {e}")
            results.append({
                "file_id": file_entry.get("sha256", "unknown"),
                "file_url": file_entry.get("file_url", ""),
                "body_name": file_entry.get("body_name", ""),
                "error": str(e)
            })
    
    # Aggregate results
    aggregate = aggregate_comparison(results)
    
    # Save comparison
    comparison_path = RESULTS_DIR / "comparison.json"
    save_comparison(aggregate, comparison_path)
    
    # Save per-file results
    per_file_path = RESULTS_DIR / "per_file_results.json"
    write_json(per_file_path, results)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    s = aggregate["summary"]
    print(f"\nFiles processed: {s['total_files']}")
    print(f"\nMistral OCR:")
    print(f"  Avg rows: {s['mistral']['avg_row_count']:.1f}")
    print(f"  Avg null cells: {s['mistral']['avg_null_cells']:.1f}")
    print(f"  Files processed: {s['mistral']['files_processed']}")
    print(f"\npdfplumber:")
    print(f"  Avg rows: {s['pdfplumber']['avg_row_count']:.1f}")
    print(f"  Avg null cells: {s['pdfplumber']['avg_null_cells']:.1f}")
    print(f"  Files processed: {s['pdfplumber']['files_processed']}")
    print(f"\nCell match rate: {s['cell_match_rate']:.1%}")
    print(f"Avg normalization changes - Mistral: {s['avg_normalization_changes']['mistral']:.1f}, pdfplumber: {s['avg_normalization_changes']['pdfplumber']:.1f}")
    print(f"Avg processing time - Mistral: {s['avg_processing_time_ms']['mistral']:.1f}ms, pdfplumber: {s['avg_processing_time_ms']['pdfplumber']:.1f}ms")
    
    print(f"\nFull comparison saved to: {comparison_path}")
    print(f"Per-file results saved to: {per_file_path}")


if __name__ == "__main__":
    main()

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
STEPS_DIR = REPO_ROOT / "pipelines" / "foi_pipeline" / "steps"

STEP_NAMES = [
    "transform_disclosure_files",
    "normalize_disclosure_cells",
    "filter_phantom_rows",
    "extract_disclosures_detect_header_row",
    "extract_disclosures_normalize_header",
    "extract_disclosures_split_combined_columns",
    "extract_disclosures_normalize_rows",
    "extract_disclosures_canonicalize",
    "extract_disclosures_canonicalize_rows",
    "extract_disclosures_deduplicate",
]

# (output_key, has_errors_json, is_record_based)
# is_record_based: True for steps 6-8 where output is a flat record list
STEP_CONFIG = {
    "transform_disclosure_files":               ("results", True,  False),
    "normalize_disclosure_cells":               ("results", False, False),
    "filter_phantom_rows":                        ("results", True,  False),
    "extract_disclosures_detect_header_row":    ("results", True,  False),
    "extract_disclosures_normalize_header":     ("results", True,  False),
    "extract_disclosures_split_combined_columns": ("results", False, False),
    "extract_disclosures_normalize_rows":       ("results", True,  False),
    "extract_disclosures_canonicalize":         ("results", True,  True),
    "extract_disclosures_canonicalize_rows":    ("results", True,  True),
    "extract_disclosures_deduplicate":          ("results", False, True),
}


def get_step_path(step_name: str, file_type: str = "output") -> Path:
    step_dir = STEPS_DIR / step_name
    if file_type == "output":
        return step_dir / "output.json"
    elif file_type == "errors":
        return step_dir / "errors.json"
    elif file_type == "changes":
        return step_dir / "changes.json"
    else:
        raise ValueError(f"Unknown file type: {file_type}")


def load_json(path: Path) -> dict | list | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

import json
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_error(step_dir, error_dict):
    errors_path = Path(step_dir) / "errors.json"
    try:
        errors = read_json(errors_path)
    except FileNotFoundError:
        errors = []
    errors.append(error_dict)
    write_json(errors_path, errors)


def write_status(step_dir, record_count):
    write_json(
        Path(step_dir) / "pipeline-status.json",
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "record_count": record_count,
        },
    )

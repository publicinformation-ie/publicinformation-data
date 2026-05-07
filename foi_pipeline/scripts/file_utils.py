import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


class IncrementalWriter:
    def __init__(self, output_path, step_name, key_field="public_body_id", force=False):
        self.output_path = Path(output_path)
        self.step_name = step_name
        self.key_field = key_field
        self.results = []
        self.processed_keys = set()

        if not force and self.output_path.exists():
            try:
                existing = read_json(self.output_path)
                self.results = existing.get("results", [])
                self.processed_keys = {r[key_field] for r in self.results if key_field in r}
            except (json.JSONDecodeError, KeyError):
                self.results = []
                self.processed_keys = set()

    def is_processed(self, key) -> bool:
        return key in self.processed_keys

    def append(self, items: list):
        self.results.extend(items)
        for item in items:
            if self.key_field in item:
                self.processed_keys.add(item[self.key_field])
        write_json(
            self.output_path,
            {"metadata": {"step": self.step_name}, "results": self.results},
        )
        print(".", end="", flush=True)

    def finalize(self) -> int:
        write_json(
            self.output_path,
            {
                "metadata": {
                    "step": self.step_name,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
                "results": self.results,
            },
        )
        print()
        return len(self.results)


def sanitize_url_for_logging(url):
    """
    Sanitize URL for safe logging.

    Removes potentially sensitive information while preserving
    enough context for debugging.

    Args:
        url: The URL to sanitize

    Returns:
        str: Sanitized URL string
    """
    if not url or not isinstance(url, str):
        return "[invalid-url]"

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return "[invalid-url]"

        # Return domain only (no path, query, or fragment)
        # This prevents leaking sensitive paths or parameters
        domain = parsed.netloc.lower()

        # Truncate long domains
        if len(domain) > 50:
            domain = domain[:47] + "..."

        return domain
    except Exception:
        return "[invalid-url]"


def sanitize_error_context(context):
    """
    Sanitize error context dictionary for safe logging.

    Args:
        context: Dictionary containing error context

    Returns:
        dict: Sanitized context dictionary
    """
    if not isinstance(context, dict):
        return {}

    sanitized = {}
    for key, value in context.items():
        if key.lower() in ('url', 'foi_page_url', 'official_website_url', 'disclosure_page_url'):
            sanitized[key] = sanitize_url_for_logging(value)
        elif key.lower() in ('api_key', 'token', 'password', 'secret'):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:197] + "..."
        else:
            sanitized[key] = value
    return sanitized


def append_error(step_dir, error_dict):
    errors_path = Path(step_dir) / "errors.json"
    try:
        errors = read_json(errors_path)
    except (FileNotFoundError, json.JSONDecodeError):
        errors = []
    
    # Sanitize error dict before appending
    sanitized_error = {
        'step': error_dict.get('step', 'unknown'),
        'timestamp': error_dict.get('timestamp', datetime.now(timezone.utc).isoformat()),
        'error_type': error_dict.get('error_type', 'UnknownError'),
        'error_message': error_dict.get('error_message', 'No message'),
        'context': sanitize_error_context(error_dict.get('context', {}))
    }
    
    errors.append(sanitized_error)
    write_json(errors_path, errors)


def write_status(step_dir, record_count):
    write_json(
        Path(step_dir) / "pipeline-status.json",
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "record_count": record_count,
        },
    )

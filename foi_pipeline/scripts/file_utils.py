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

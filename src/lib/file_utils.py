import json
import jsonschema
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_append_error_locks: dict[str, threading.Lock] = {}
_append_error_locks_meta = threading.Lock()


def _get_append_error_lock(path: str) -> threading.Lock:
    with _append_error_locks_meta:
        if path not in _append_error_locks:
            _append_error_locks[path] = threading.Lock()
        return _append_error_locks[path]


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class IncrementalWriter:
    def __init__(self, output_path, step_name, key_field="public_body_id",
                 force=False, override_path=None, upstream_dirty_path=None,
                 target_public_body=None):
        self.output_path = Path(output_path)
        self.step_name = step_name
        self.key_field = key_field
        self.results = []
        self.processed_keys = set()
        self.dirty_body_ids = set()

        if (not force or target_public_body is not None) and self.output_path.exists():
            try:
                existing = read_json(self.output_path)
                self.results = existing.get("results", [])
                self.processed_keys = {r[key_field] for r in self.results if key_field in r}
            except (json.JSONDecodeError, KeyError):
                self.results = []
                self.processed_keys = set()

        if upstream_dirty_path and Path(upstream_dirty_path).exists():
            self._evict_upstream_dirty(Path(upstream_dirty_path))

        if target_public_body is not None:
            self._evict_keys({target_public_body})

        if override_path and Path(override_path).exists():
            self._load_overrides(Path(override_path))

    def _evict_upstream_dirty(self, dirty_path):
        self._evict_keys(set(read_json(dirty_path)))

    def _evict_keys(self, body_ids: set):
        """Remove all records whose public_body_id is in body_ids from
        self.results, drop their keys from processed_keys, and mark them
        dirty so finalize() cascades them downstream. Shared by upstream
        dirty propagation and the --public-body target eviction."""
        if not body_ids:
            return
        to_evict = [r for r in self.results if r.get("public_body_id") in body_ids]
        if not to_evict:
            return
        evicted_body_ids = {r["public_body_id"] for r in to_evict if "public_body_id" in r}
        evicted_keys = {r[self.key_field] for r in to_evict if self.key_field in r}
        self.results = [r for r in self.results if r.get("public_body_id") not in body_ids]
        self.processed_keys -= evicted_keys
        self.dirty_body_ids.update(evicted_body_ids)
        print(
            f"Dirty: evicted {len(to_evict)} record(s) for "
            f"{len(evicted_body_ids)} body ID(s): "
            f"{', '.join(str(k) for k in sorted(evicted_body_ids))}"
        )

    def _load_overrides(self, override_path):
        overrides = read_json(override_path)

        item_schema = None
        schema_path = override_path.parent / "output_schema.json"
        if schema_path.exists():
            schema = read_json(schema_path)
            props = schema.get("properties", {})
            for collection_key in ("results", "public_bodies"):
                if collection_key in props and "items" in props[collection_key]:
                    item_schema = props[collection_key]["items"]
                    break

        pre_override_keys = set(self.processed_keys)
        loaded_ids = []
        for record in overrides:
            key = record.get(self.key_field)
            if key is None:
                continue
            if key in self.processed_keys and key not in pre_override_keys:
                continue  # duplicate in override file — first entry wins
            if item_schema is not None:
                try:
                    jsonschema.validate(record, item_schema)
                except jsonschema.ValidationError as e:
                    raise ValueError(
                        f"Override record {self.key_field}={key} failed schema validation: {e.message}"
                    ) from e
            if key in pre_override_keys:
                existing = next((r for r in self.results if r.get(self.key_field) == key), None)
                self.results = [r for r in self.results if r.get(self.key_field) != key]
                if existing != record:
                    body_id = record.get("public_body_id")
                    if body_id is not None:
                        self.dirty_body_ids.add(body_id)
            self.results.append(record)
            self.processed_keys.add(key)
            loaded_ids.append(key)

        if loaded_ids:
            print(
                f"Override: {len(loaded_ids)} record(s) loaded from override.json "
                f"[{self.key_field}s: {', '.join(str(k) for k in loaded_ids)}]"
            )

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
        write_json(self.output_path.parent / "dirty_ids.json", sorted(self.dirty_body_ids))
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


def _sanitize_error(error_dict):
    return {
        'step': error_dict.get('step', 'unknown'),
        'timestamp': error_dict.get('timestamp', datetime.now(timezone.utc).isoformat()),
        'error_type': error_dict.get('error_type', 'UnknownError'),
        'error_message': error_dict.get('error_message', 'No message'),
        'context': sanitize_error_context(error_dict.get('context', {}))
    }


def append_error(step_dir, error_dict):
    errors_path = Path(step_dir) / "errors.json"
    lock = _get_append_error_lock(str(errors_path))
    with lock:
        try:
            errors = read_json(errors_path)
        except (FileNotFoundError, json.JSONDecodeError):
            errors = []
        errors.append(_sanitize_error(error_dict))
        write_json(errors_path, errors)


def append_errors(step_dir, error_list):
    """Batch-append multiple errors in a single read/write cycle."""
    if not error_list:
        return
    errors_path = Path(step_dir) / "errors.json"
    lock = _get_append_error_lock(str(errors_path))
    with lock:
        try:
            errors = read_json(errors_path)
        except (FileNotFoundError, json.JSONDecodeError):
            errors = []
        errors.extend(_sanitize_error(e) for e in error_list)
        write_json(errors_path, errors)


def write_status(step_dir, record_count):
    write_json(
        Path(step_dir) / "pipeline-status.json",
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "record_count": record_count,
        },
    )

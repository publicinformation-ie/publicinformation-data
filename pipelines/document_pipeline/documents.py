"""Loader for documents.yml — the curated list of source PDFs.

This is the pipeline's only hand-authored input. It is validated strictly and
loudly: a malformed entry here is the one condition in this pipeline that is
process-fatal, because every downstream step is keyed on doc_slug and a bad
slug would corrupt published URLs.
"""
import re
from pathlib import Path

import yaml

DOCUMENTS_PATH = Path(__file__).parent / "documents.yml"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_REQUIRED = ("doc_slug", "title", "url")
_OPTIONAL = ("publisher", "public_body_id", "published_date")


def load_documents(path=DOCUMENTS_PATH) -> list:
    """Parse and validate documents.yml. Raises ValueError on any violation."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"{path} is not valid YAML: {e}") from e

    entries = raw.get("documents")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path} must contain a non-empty 'documents' list")

    records = []
    seen = set()
    for index, entry in enumerate(entries):
        where = f"{path} entry {index}"
        if not isinstance(entry, dict):
            raise ValueError(f"{where} is not a mapping")

        for field in _REQUIRED:
            if not entry.get(field):
                raise ValueError(f"{where} is missing required field '{field}'")

        slug = entry["doc_slug"]
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            raise ValueError(
                f"{where} has doc_slug {slug!r}; must match {SLUG_RE.pattern}")
        if slug in seen:
            raise ValueError(f"{where} has duplicate doc_slug {slug!r}")
        seen.add(slug)

        url = entry["url"]
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"{where} has url {url!r}; must be http(s)")

        published = entry.get("published_date")
        if published is not None and not DATE_RE.match(str(published)):
            raise ValueError(
                f"{where} has published_date {published!r}; must be YYYY-MM-DD")

        body_id = entry.get("public_body_id")
        if body_id is not None and not isinstance(body_id, int):
            raise ValueError(f"{where} has non-integer public_body_id {body_id!r}")

        record = {field: entry[field] for field in _REQUIRED}
        record.update({field: entry.get(field) for field in _OPTIONAL})
        record["published_date"] = None if published is None else str(published)
        records.append(record)

    return records

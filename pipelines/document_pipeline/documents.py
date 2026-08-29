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
_OPTIONAL = ("publisher", "public_body_id", "published_date", "role",
             "reports_on", "expected_action_count", "expected_status_counts")

VALID_ROLES = ("plan", "report")


class InvalidDocumentRole(ValueError):
    """A `role`/`reports_on` combination that cannot be resolved.

    Process-fatal, like every other documents.yml violation: `reports_on` is
    what joins a progress report's observations to the plan that declares the
    actions, so a bad link would silently mis-attribute every observation in
    the document rather than losing one field.
    """


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

        role = entry.get("role") or "plan"
        if role not in VALID_ROLES:
            raise InvalidDocumentRole(
                f"{where} has role {role!r}; must be one of {VALID_ROLES}")

        reports_on = entry.get("reports_on")
        if role == "report" and not reports_on:
            raise InvalidDocumentRole(
                f"{where} has role 'report' but no 'reports_on'; a report must "
                f"name the plan whose actions it reports on")
        if role != "report" and reports_on:
            raise InvalidDocumentRole(
                f"{where} sets 'reports_on' but its role is {role!r}; "
                f"reports_on is only meaningful on a report")

        expected_actions = entry.get("expected_action_count")
        if expected_actions is not None and (isinstance(expected_actions, bool)
                                             or not isinstance(expected_actions, int)
                                             or expected_actions < 0):
            raise ValueError(
                f"{where} has expected_action_count {expected_actions!r}; "
                f"must be a non-negative integer")

        expected_statuses = entry.get("expected_status_counts")
        if expected_statuses is not None:
            if not isinstance(expected_statuses, dict) or not expected_statuses:
                raise ValueError(
                    f"{where} has expected_status_counts {expected_statuses!r}; "
                    f"must be a non-empty mapping of status -> count")
            for status, count in expected_statuses.items():
                if (not isinstance(status, str) or isinstance(count, bool)
                        or not isinstance(count, int) or count < 0):
                    raise ValueError(
                        f"{where} has expected_status_counts entry "
                        f"{status!r}: {count!r}; must be str -> non-negative int")

        record = {field: entry[field] for field in _REQUIRED}
        record.update({field: entry.get(field) for field in _OPTIONAL})
        record["published_date"] = None if published is None else str(published)
        record["role"] = role
        records.append(record)

    slugs = {record["doc_slug"] for record in records}
    for record in records:
        target = record["reports_on"]
        if target is not None and target not in slugs:
            raise InvalidDocumentRole(
                f"{path} entry {record['doc_slug']!r} has reports_on {target!r}, "
                f"which is not a doc_slug in this file")

    return records

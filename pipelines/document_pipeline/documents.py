"""Loader for documents.yml — the curated list of source PDFs.

This is the pipeline's only hand-authored input. It is validated strictly and
loudly: a malformed entry here is the one condition in this pipeline that is
process-fatal, because every downstream step is keyed on doc_slug and a bad
slug would corrupt published URLs.
"""
import re
from pathlib import Path

import yaml

from policies import load_policies

DOCUMENTS_PATH = Path(__file__).parent / "documents.yml"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_REQUIRED = ("doc_slug", "title", "url", "policy_id", "policy_role")
_OPTIONAL = ("publisher", "public_body_id", "published_date", "role",
             "reports_on", "expected_action_count", "expected_status_counts",
             "status_source", "hold", "ocr_pages", "action_table_layout",
             "reference_corrections", "status_annex")

VALID_ROLES = ("plan", "report")
# Where a report's machine-readable status detail lives, when not in its PDF.
# "annex": a companion spreadsheet; extract_action_status skips the report.
VALID_STATUS_SOURCES = ("annex",)
# Formats a report's companion status workbook may be declared in.
VALID_STATUS_ANNEX_FORMATS = ("xlsx",)
# Opt-in table-reading behaviours for annexes whose layout differs from the
# default (see extract_actions). Never auto-detected: undeclared documents are
# read exactly as before.
VALID_ACTION_TABLE_LAYOUTS = ("action_number_header", "carry_header")
VALID_POLICY_ROLES = ("primary", "action-plan", "progress-report")


class InvalidDocumentRole(ValueError):
    """A `role`/`reports_on` combination that cannot be resolved.

    Process-fatal, like every other documents.yml violation: `reports_on` is
    what joins a progress report's observations to the plan that declares the
    actions, so a bad link would silently mis-attribute every observation in
    the document rather than losing one field.
    """


def reports_on_slugs(reports_on) -> list:
    """The plan slugs a report observes, as a list.

    `reports_on` is a single slug (the historical form, kept meaning exactly
    what it did) or a non-empty list of slugs. Absent -> [].
    """
    if reports_on is None:
        return []
    if isinstance(reports_on, str):
        return [reports_on]
    return list(reports_on)


def load_documents(path=DOCUMENTS_PATH, policy_ids=None) -> list:
    """Parse and validate documents.yml. Raises ValueError on any violation."""
    path = Path(path)
    if policy_ids is None:
        policy_ids = {p["policy_id"] for p in load_policies()}
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

        policy_id = entry["policy_id"]
        if policy_id not in policy_ids:
            raise ValueError(
                f"{where} has policy_id {policy_id!r}, which is not in the policy inventory")
        policy_role = entry["policy_role"]
        if policy_role not in VALID_POLICY_ROLES:
            raise ValueError(
                f"{where} has policy_role {policy_role!r}; must be one of {VALID_POLICY_ROLES}")
        if (role == "report") != (policy_role == "progress-report"):
            raise InvalidDocumentRole(
                f"{where} has role {role!r} but policy_role {policy_role!r}; "
                f"a report must be a progress-report and vice versa")

        reports_on = entry.get("reports_on")
        if isinstance(reports_on, list):
            if (not reports_on
                    or any(not isinstance(s, str) or not s for s in reports_on)
                    or len(set(reports_on)) != len(reports_on)):
                raise InvalidDocumentRole(
                    f"{where} has reports_on {reports_on!r}; a list must be "
                    f"non-empty with unique plan slugs")
        elif reports_on is not None and not isinstance(reports_on, str):
            raise InvalidDocumentRole(
                f"{where} has reports_on {reports_on!r}; must be a plan slug "
                f"or a list of plan slugs")
        if role == "report" and not reports_on:
            raise InvalidDocumentRole(
                f"{where} has role 'report' but no 'reports_on'; a report must "
                f"name the plan whose actions it reports on")
        if role != "report" and reports_on:
            raise InvalidDocumentRole(
                f"{where} sets 'reports_on' but its role is {role!r}; "
                f"reports_on is only meaningful on a report")

        status_source = entry.get("status_source")
        if status_source is not None:
            if role != "report":
                raise InvalidDocumentRole(
                    f"{where} sets 'status_source' but its role is {role!r}; "
                    f"status_source is only meaningful on a report")
            if status_source not in VALID_STATUS_SOURCES:
                raise ValueError(
                    f"{where} has status_source {status_source!r}; "
                    f"must be one of {VALID_STATUS_SOURCES}")

        if "status_annex" in entry:
            annex = entry["status_annex"]
            name = f"{where} ({entry.get('doc_slug')}) has status_annex"
            if status_source != "annex":
                raise ValueError(
                    f"{name} but no status_source: annex; a status_annex is "
                    f"only permitted on a report that declares status_source: annex")
            if (not isinstance(annex, dict) or set(annex) != {"url", "format"}
                    or not isinstance(annex["url"], str)
                    or not annex["url"].startswith(("http://", "https://"))):
                raise ValueError(
                    f"{name} {annex!r}; must be {{url (http/https), format}}")
            if annex["format"] not in VALID_STATUS_ANNEX_FORMATS:
                raise ValueError(
                    f"{name} format {annex['format']!r}; must be one of "
                    f"{VALID_STATUS_ANNEX_FORMATS}")

        if "hold" in entry:
            hold = entry["hold"]
            if not isinstance(hold, str) or not hold.strip():
                raise ValueError(
                    f"{where} has hold {hold!r}; must be a non-empty string "
                    f"giving the reason the document is withheld")

        if "ocr_pages" in entry:
            pages = entry["ocr_pages"]
            if (not isinstance(pages, list) or not pages
                    or any(isinstance(p, bool) or not isinstance(p, int) or p < 1
                           for p in pages)
                    or len(set(pages)) != len(pages)):
                raise ValueError(
                    f"{where} has ocr_pages {pages!r}; must be a non-empty list of "
                    f"unique 1-based page numbers (positive integers)")
            entry["ocr_pages"] = sorted(pages)

        if "action_table_layout" in entry:
            layout = entry["action_table_layout"]
            if (not isinstance(layout, list) or not layout
                    or any(flag not in VALID_ACTION_TABLE_LAYOUTS for flag in layout)
                    or len(set(layout)) != len(layout)):
                raise ValueError(
                    f"{where} ({entry.get('doc_slug')}) has action_table_layout {layout!r}; must be a "
                    f"non-empty list of unique values from "
                    f"{VALID_ACTION_TABLE_LAYOUTS}")
            if policy_role != "action-plan":
                raise ValueError(
                    f"{where} ({entry.get('doc_slug')}) sets action_table_layout but its policy_role is "
                    f"{policy_role!r}; it is only permitted on an action-plan "
                    f"entry")

        if "reference_corrections" in entry:
            corrections = entry["reference_corrections"]
            name = f"{where} ({entry.get('doc_slug')}) has reference_corrections"
            if not isinstance(corrections, list) or not corrections:
                raise ValueError(f"{name} {corrections!r}; must be a non-empty list")
            for item in corrections:
                if (not isinstance(item, dict)
                        or set(item) != {"page", "printed", "corrected", "text_starts", "evidence"}
                        or isinstance(item["page"], bool)
                        or not isinstance(item["page"], int) or item["page"] < 1
                        or any(not isinstance(item[k], str) or not item[k].strip()
                               for k in ("printed", "corrected", "text_starts", "evidence"))
                        or item["printed"] == item["corrected"]):
                    raise ValueError(
                        f"{name} entry {item!r}; each must be "
                        f"{{page (>= 1), printed, corrected, text_starts, evidence}} with "
                        f"printed different from corrected")
            if policy_role != "action-plan":
                raise ValueError(
                    f"{where} ({entry.get('doc_slug')}) sets reference_corrections but "
                    f"its policy_role is {policy_role!r}; it is only permitted on an "
                    f"action-plan entry")

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

    by_slug = {record["doc_slug"]: record for record in records}
    slugs = set(by_slug)
    for record in records:
        for target in reports_on_slugs(record["reports_on"]):
            if target not in slugs:
                raise InvalidDocumentRole(
                    f"{path} entry {record['doc_slug']!r} has reports_on {target!r}, "
                    f"which is not a doc_slug in this file")
            if by_slug[target]["policy_id"] != record["policy_id"]:
                raise InvalidDocumentRole(
                    f"{path} entry {record['doc_slug']!r} reports on {target!r}, "
                    f"which belongs to a different policy; a report and its plan must "
                    f"share the same policy_id")
            if by_slug[target]["role"] != "plan":
                raise InvalidDocumentRole(
                    f"{path} entry {record['doc_slug']!r} reports on {target!r}, "
                    f"which is not a role: plan entry")

    return records

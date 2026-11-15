"""Shared vocabulary and helpers for the Active Travel allocations pipeline.

Everything the steps agree on lives here: the closed row-kind and
funding-stream vocabularies, the committed configuration loaders, amount
normalisation, row classification, and the anchor-bounded segmentation that
decides which project rows belong to which section and block.

The module is imported by every step (`from allocations import ...`, since the
runner puts the pipeline directory on PYTHONPATH) and by the tests.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from lib.body_refs import slugify as _body_slugify
from lib.text_utils import normalize_cell

PIPELINE_DIR = Path(__file__).resolve().parent
STEPS_DIR = PIPELINE_DIR / "steps"
CACHE_DIR = PIPELINE_DIR / "cache"

# --- closed vocabularies ---------------------------------------------------

DOC_KINDS = ("project_table", "recipient_summary", "programme_summary")
FUNDING_STREAMS = ("active_travel", "other_nta_streams")
ROW_KINDS = (
    "document_title",
    "column_header",
    "recipient_heading",
    "stream_divider",
    "project",
    "anchor",
    "footnote",
    "blank",
)

TOTAL_LABELS = frozenset({"total", "totals"})
SUBTOTAL_LABELS = frozenset({"subtotal"})
ANCHOR_LABELS = TOTAL_LABELS | SUBTOTAL_LABELS

STREAM_DIVIDER_TEXT = "allocations through other nta funding streams"
PROJECT_TABLE_HEADER = "projectcode"
SUMMARY_TABLE_HEADER = "agency"

RECIPIENT_KINDS = ("local_authority", "other")

# --- small helpers ---------------------------------------------------------


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_error(step: str, error_type: str, message: str, **context) -> dict:
    return {
        "step": step,
        "error_type": error_type,
        "error_message": message,
        "context": context,
    }


def scope(records: list[dict], document_id: str | None) -> list[dict]:
    """Restrict records to one document when `--doc` was passed."""
    if document_id is None:
        return records
    return [r for r in records if r.get("document_id") == document_id]


CARRY_KEYS = ("documents", "pages", "summary_rows")


def carried(input_data: dict) -> dict:
    """The document/page/summary context every step must pass through unchanged."""
    return {key: input_data.get(key, []) for key in CARRY_KEYS}


def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def normalise(value) -> str:
    """The single cell normalisation used on every extracted table cell.

    PDF extraction artefacts (`(cid:N)` tokens, embedded newlines, runs of
    spaces) are normalised away by the shared helper; nothing else is changed,
    so a printed value is never silently rewritten.
    """
    if value is None:
        return ""
    return normalize_cell(str(value), file_type="pdf").strip()


def alnum(text: str) -> str:
    """Lowercase letters and digits only — the matching key for header labels."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def alias_key(text: str) -> str:
    """Matching key for a recipient heading or table title.

    Case, whitespace, a leading ``Table A:`` and surrounding quotes are
    presentation, not identity.
    """
    key = " ".join(text.split()).lower()
    key = re.sub(r"^table\s+a\s*:\s*", "", key)
    key = key.replace('"', "").replace("\u201c", "").replace("\u201d", "")
    return key.strip(" .:")


def slugify(text: str) -> str:
    return _body_slugify(text)


# --- committed configuration ----------------------------------------------


def load_publications() -> list[dict]:
    """Read and validate `steps/fetch_grant_documents/publications.json`.

    A malformed entry is process-fatal: the committed list is the only
    ingestion source, so an entry that cannot be read must stop the run rather
    than be skipped.
    """
    path = STEPS_DIR / "fetch_grant_documents" / "publications.json"
    data = read_json(path)
    publications = data.get("publications")
    if not isinstance(publications, list) or not publications:
        raise ValueError(f"{path}: 'publications' must be a non-empty list")

    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    years: set[int] = set()
    for entry in publications:
        year = entry.get("year")
        if not isinstance(year, int):
            raise ValueError(f"{path}: every publication needs an integer 'year'")
        if year in years:
            raise ValueError(f"{path}: year {year} is declared twice")
        years.add(year)
        if not entry.get("publication_page"):
            raise ValueError(f"{path}: year {year} has no publication_page")
        documents = entry.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ValueError(f"{path}: year {year} has no documents")
        for document in documents:
            document_id = document.get("document_id")
            url = document.get("url")
            kinds = document.get("kinds")
            if not document_id:
                raise ValueError(f"{path}: year {year} has a document without an id")
            if document_id in seen_ids:
                raise ValueError(f"{path}: document_id {document_id!r} is declared twice")
            seen_ids.add(document_id)
            if not url:
                raise ValueError(f"{path}: {document_id} has no url")
            if url in seen_urls:
                raise ValueError(f"{path}: {document_id} reuses url {url}")
            seen_urls.add(url)
            if not isinstance(kinds, list) or not kinds:
                raise ValueError(f"{path}: {document_id} has no kinds")
            unknown = [k for k in kinds if k not in DOC_KINDS]
            if unknown:
                raise ValueError(f"{path}: {document_id} has unknown kinds {unknown}")
        if not any("project_table" in d["kinds"] for d in documents):
            raise ValueError(f"{path}: year {year} has no project_table document")
    return publications


def flatten_documents(publications: list[dict]) -> list[dict]:
    """One entry per document, carrying its publication's year and page."""
    documents = []
    for publication in publications:
        for document in publication["documents"]:
            documents.append({
                "document_id": document["document_id"],
                "year": publication["year"],
                "kinds": list(document["kinds"]),
                "publication_page": publication["publication_page"],
                "url": document["url"],
                "title": document.get("title", ""),
            })
    return documents


def load_recipient_aliases() -> dict:
    """Map alias key -> recipient record (canonical name, kind, body name)."""
    path = STEPS_DIR / "resolve_recipients" / "recipient_aliases.json"
    data = read_json(path)
    recipients = data.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise ValueError(f"{path}: 'recipients' must be a non-empty list")

    by_alias: dict[str, dict] = {}
    for recipient in recipients:
        canonical = recipient.get("canonical")
        kind = recipient.get("kind")
        if not canonical or kind not in RECIPIENT_KINDS:
            raise ValueError(f"{path}: recipient entry {recipient!r} is incomplete")
        aliases = recipient.get("aliases") or []
        if canonical not in aliases:
            aliases = [canonical, *aliases]
        if kind == "local_authority" and not recipient.get("public_body_name"):
            raise ValueError(f"{path}: {canonical} is a local authority with no public_body_name")
        record = {
            "canonical": canonical,
            "kind": kind,
            "public_body_name": recipient.get("public_body_name"),
            "slug": recipient.get("slug") or slugify(canonical),
        }
        for alias in aliases:
            key = alias_key(alias)
            existing = by_alias.get(key)
            if existing is not None and existing["canonical"] != canonical:
                raise ValueError(
                    f"{path}: alias {alias!r} maps to both "
                    f"{existing['canonical']!r} and {canonical!r}"
                )
            by_alias[key] = record
    return by_alias


def load_code_prefixes() -> dict:
    """Map project-code prefix -> record of candidate recipients.

    A prefix may list more than one candidate only where the publisher really
    reuses it (e.g. ``LCC`` is Limerick's prefix and also appears on Louth's
    provisional 2022 codes). A prefix-only attribution needs exactly one
    candidate; a heading-corroborated attribution accepts any candidate that
    matches the heading.
    """
    path = STEPS_DIR / "resolve_recipients" / "code_prefixes.json"
    data = read_json(path)
    prefixes = data.get("prefixes")
    if not isinstance(prefixes, dict) or not prefixes:
        raise ValueError(f"{path}: 'prefixes' must be a non-empty object")
    out: dict[str, dict] = {}
    for prefix, entry in prefixes.items():
        recipients = entry.get("recipients")
        if not isinstance(recipients, list) or not recipients:
            raise ValueError(f"{path}: prefix {prefix!r} has no recipients")
        out[prefix.upper()] = {
            "recipients": list(recipients),
            "note": entry.get("note", ""),
        }
    return out


def load_row_repairs() -> list[dict]:
    """Read the committed manual repair list (absent file means no repairs)."""
    path = STEPS_DIR / "reconcile_sections" / "row_repairs.json"
    if not path.exists():
        return []
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of repairs")
    for entry in data:
        if entry.get("source_method") != "manual" or entry.get("overridden") is not True:
            raise ValueError(f"{path}: every repair needs source_method 'manual' and overridden true")
        if entry.get("action") not in ("set_amount", "drop_row"):
            raise ValueError(f"{path}: repair {entry!r} has an unknown action")
        for field in ("document_id", "page", "row_index", "reason"):
            if field not in entry:
                raise ValueError(f"{path}: repair {entry!r} is missing {field}")
    return data


# --- amounts ---------------------------------------------------------------

_LETTER_RE = re.compile(r"[A-Za-z]")


def parse_amount(cell) -> dict:
    """Read one printed amount as whole euro.

    The currency symbol, thousands separators and incidental whitespace inside
    the number are formatting. Anything that is not a consistently grouped
    decimal integer is rejected — a value is never harvested out of a cell that
    also holds other text. Every change needed to obtain the value is returned
    as `repair` so normalisation stays visible.

    Returns {'value', 'raw', 'error', 'repair', 'detail'}.
    """
    raw = normalise(cell)
    result = {"value": None, "raw": raw, "error": None, "repair": None, "detail": ""}

    if raw == "":
        result["error"] = "empty"
        result["detail"] = "amount cell is empty"
        return result
    if _LETTER_RE.search(raw):
        result["error"] = "letters"
        result["detail"] = "amount cell contains letters"
        return result

    after_currency = raw.split("\u20ac")[-1]
    compact = re.sub(r"\s+", "", after_currency)
    if compact in ("", "-"):
        result["error"] = "no_digits"
        result["detail"] = "amount cell holds no digits"
        return result

    # A printed cents part is accepted only when it is zero: `.00` carries no
    # sub-euro information, any other cents value is not a whole-euro figure.
    whole_text, dot, cents = compact.partition(".")
    if dot:
        if not cents.isdigit() or len(cents) != 2:
            result["error"] = "not_numeric"
            result["detail"] = "cents are not two digits"
            return result
        if int(cents) != 0:
            result["error"] = "sub_euro_amount"
            result["detail"] = "amount is not a whole number of euro"
            return result

    if whole_text.startswith(","):
        result["error"] = "ambiguous_grouping"
        result["detail"] = "amount starts with a thousands separator"
        return result

    parts = whole_text.split(",")
    if any(not part.isdigit() for part in parts):
        result["error"] = "not_numeric"
        result["detail"] = "amount is not a decimal integer"
        return result
    if len(parts) > 1:
        if len(parts[0]) > 3 or any(len(part) != 3 for part in parts[1:]):
            result["error"] = "ambiguous_grouping"
            result["detail"] = "thousands separators are not groups of three"
            return result

    value = int("".join(parts))
    result["value"] = value

    if re.search(r"\s", re.sub(r"^\s*", "", after_currency).strip()):
        result["repair"] = {
            "field": "amount_eur",
            "raw": raw,
            "value_used": value,
            "rule": "whitespace_inside_number",
        }
    return result


# --- row classification ----------------------------------------------------

_TITLE_PREFIXES = ("active travel investment grants",)


def classify_row(cells: list[str]) -> tuple[str, dict]:
    """Classify one normalised table row into exactly one kind.

    Returns (kind, detail). `detail` carries the matched text (heading, title,
    anchor label) and the anchor's amount cell so later steps never re-guess
    which cell holds the money.
    """
    c0, c1, c2 = (cells + ["", "", ""])[:3]
    non_empty = [i for i, cell in enumerate(cells) if cell]

    if not non_empty:
        return "blank", {}

    if c0.startswith("*"):
        return "footnote", {"text": c0}

    if " ".join(c0.split()).lower() == STREAM_DIVIDER_TEXT:
        return "stream_divider", {}

    if alnum(c0) in (PROJECT_TABLE_HEADER, SUMMARY_TABLE_HEADER):
        return "column_header", {"label": c0}

    for index, cell in enumerate(cells):
        label = cell.split(":")[0].strip().lower()
        if label in ANCHOR_LABELS:
            amount = ""
            amount_column = None
            for later_index in range(index + 1, len(cells)):
                if cells[later_index]:
                    amount = cells[later_index]
                    amount_column = later_index
            return "anchor", {
                "label": label,
                "label_column": index,
                "amount_cell": amount,
                "amount_column": amount_column,
            }

    if len(non_empty) == 1:
        text = c0 if c0 else cells[non_empty[0]]
        if text.lower().startswith("table a:"):
            return "document_title", {"text": text, "is_section_title": True}
        if text.lower().startswith(_TITLE_PREFIXES):
            return "document_title", {"text": text, "is_section_title": False}
        return "recipient_heading", {"text": text}

    if c0 and c1:
        return "project", {"code": c0, "name": c1, "amount_cell": c2}

    return "unknown", {"cells": list(cells)}



# --- segmentation ----------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"x{2,}", re.IGNORECASE)


def code_prefix(code: str) -> str:
    """The recipient-carrying part of a printed project code."""
    return code.split("/")[0].strip()


def is_provisional_code(code: str) -> bool:
    """True when the printed code is a placeholder rather than an assigned code."""
    if not code:
        return True
    if _PLACEHOLDER_RE.search(code):
        return True
    prefix = code_prefix(code).upper()
    return prefix in ("XX", "XXX", "XXXX") or code.upper().startswith("XX/")


def _new_section(heading: str | None, first_row: dict, title: str | None = None) -> dict:
    return {
        "heading": heading,
        "title": title,
        "first_page": first_row["page"],
        "first_row_index": first_row["row_index"],
        "rows": [],
        "blocks": [],
        "open_rows": [],
        "section_total": None,
        "closed": False,
    }


def build_sections(doc_rows: list[dict]) -> list[dict]:
    """Group one document's classified rows into anchor-bounded sections.

    Section boundaries come from recipient headings; a heading equal to the
    current section's is a repeated page header, not a new section. A project
    row that arrives when no section is open (or when the open one has already
    closed on its total) opens a heading-less section, which the recipient
    resolver can still attribute from the project-code prefix — no row is ever
    attributed by position alone.

    Within a section, anchors close blocks. The anchor that ends the section is
    the section total: the first `Total`/`Totals` row that directly follows
    another anchor, or, when the section is closed by the next heading, the
    last anchor seen.
    """
    sections: list[dict] = []
    current: dict | None = None
    previous_kind: str | None = None
    pending_title: str | None = None

    def close_open_block(declared):
        if current is None:
            return
        current["blocks"].append({"rows": current["open_rows"], "declared": declared})
        current["open_rows"] = []

    for row in doc_rows:
        kind = row["kind"]

        if kind == "document_title" and row["detail"].get("is_section_title"):
            pending_title = row["detail"]["text"]
            previous_kind = kind
            continue

        if kind == "recipient_heading":
            heading = row["detail"]["text"]
            if current is not None and not current["closed"] and current["heading"] is not None:
                if alias_key(current["heading"]) == alias_key(heading):
                    previous_kind = kind
                    continue
            current = _new_section(heading, row, pending_title)
            pending_title = None
            sections.append(current)
            previous_kind = kind
            continue

        if kind == "project":
            if current is None or current["closed"]:
                current = _new_section(None, row, pending_title)
                pending_title = None
                sections.append(current)
            current["open_rows"].append(row)
            previous_kind = kind
            continue

        if kind == "stream_divider":
            if current is not None and not current["closed"] and current["open_rows"]:
                close_open_block(None)
            previous_kind = kind
            continue

        if kind == "anchor":
            if current is None or current["closed"]:
                previous_kind = kind
                continue
            label = row["detail"]["label"]
            if (not current["open_rows"]
                    and label in TOTAL_LABELS
                    and previous_kind == "anchor"):
                current["section_total"] = row
                current["closed"] = True
            else:
                close_open_block(row)
            previous_kind = kind
            continue

        if kind in ("blank", "footnote"):
            continue

        previous_kind = kind

    for section in sections:
        if section["open_rows"]:
            section["blocks"].append({"rows": section["open_rows"], "declared": None})
            section["open_rows"] = []
        if section["section_total"] is None and section["blocks"]:
            last = section["blocks"][-1]
            section["section_total"] = last["declared"]
            last["declared"] = None
    return sections

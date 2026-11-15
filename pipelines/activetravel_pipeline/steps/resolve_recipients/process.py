#!/usr/bin/env python3
"""Attribute every project row to a recipient from two independent signals.

The section heading (via the committed alias list) and the project-code prefix
(via the committed prefix map) must agree. A heading-less section, which the
publisher produces when a table's heading page is missing, is attributed from a
prefix only when that prefix names exactly one recipient. A conflict, an
undeclared prefix, or an ambiguous one withholds the row and names both signals.

A local authority must resolve to a body in the Public Bodies register: if one
does not, publication stops instead of emitting a record without its body link.
The non-local-authority block keeps its printed name and gets no body link, and
because that block *is* the document's active-travel "Others" table, every one
of its blocks belongs to the active-travel stream.
"""
import argparse
import sys
from pathlib import Path

from allocations import (
    PIPELINE_DIR, alias_key, carried, code_prefix, make_error, now_iso, scope,
)
from lib.body_refs import body_uri
from lib.body_utils import resolve_slug
from lib.cli_utils import add_common_args, add_doc_arg
from lib.file_utils import append_errors, read_json as read_json_file, write_json, write_status

STEP_NAME = "resolve_recipients"
STEP_DIR = Path(__file__).parent

REPO_ROOT = PIPELINE_DIR.parent.parent
PUBLIC_BODIES_PATH = REPO_ROOT / "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SLUG_SEED_PATH = REPO_ROOT / "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"


def _name_key(name: str) -> str:
    return " ".join(name.split()).lower()


def load_public_body_register(path: Path | None = None) -> dict[str, int]:
    """Map normalised public-body name -> public_body_id."""
    path = PUBLIC_BODIES_PATH if path is None else path
    if not path.exists():
        raise ValueError(
            f"{path} is missing: run the FOI pipeline's find_public_bodies step first "
            "(it owns public-body identity for every dataset)"
        )
    bodies = read_json_file(path).get("public_bodies", [])
    return {_name_key(b["name"]): b["public_body_id"] for b in bodies}


def load_slug_seed(path: Path | None = None) -> dict[int, str]:
    path = SLUG_SEED_PATH if path is None else path
    raw = read_json_file(path)
    return {int(key): value for key, value in raw.items()}


def resolve(heading: str | None, code: str, aliases: dict, prefixes: dict
            ) -> tuple[dict | None, str | None, str]:
    """Return (recipient, error_type, detail) for one project row."""
    prefix = code_prefix(code)
    prefix_entry = prefixes.get(prefix.upper())
    candidates = prefix_entry["recipients"] if prefix_entry else None
    heading_recipient = aliases.get(alias_key(heading)) if heading else None

    if heading_recipient is not None:
        if candidates is None:
            return None, "RecipientUnresolved", f"project-code prefix {prefix!r} is not declared"
        if heading_recipient["canonical"] in candidates:
            return heading_recipient, None, "heading+prefix"
        return None, "RecipientConflict", (
            f"heading names {heading_recipient['canonical']!r} but prefix {prefix!r} "
            f"belongs to {', '.join(candidates)}"
        )

    if candidates is None:
        return None, "RecipientUnresolved", (
            f"no section heading and project-code prefix {prefix!r} is not declared"
        )
    if len(candidates) != 1:
        return None, "RecipientUnresolved", (
            f"no section heading and prefix {prefix!r} names {len(candidates)} recipients"
        )
    recipient = aliases.get(alias_key(candidates[0]))
    if recipient is None:
        return None, "RecipientUnresolved", (
            f"prefix {prefix!r} names undeclared recipient {candidates[0]!r}"
        )
    return recipient, None, "prefix_only"


def run(input_data: dict, document: str | None = None, aliases: dict | None = None,
        prefixes: dict | None = None, register: dict[str, int] | None = None,
        slug_seed: dict[int, str] | None = None) -> tuple[dict, list[dict]]:
    from allocations import load_code_prefixes, load_recipient_aliases

    aliases = load_recipient_aliases() if aliases is None else aliases
    prefixes = load_code_prefixes() if prefixes is None else prefixes
    register = load_public_body_register() if register is None else register
    slug_seed = load_slug_seed() if slug_seed is None else slug_seed

    rows = input_data.get("rows", [])
    scoped = scope(rows, document)
    sections = [s for s in input_data.get("sections", [])
                if document is None or s["document_id"] == document]
    withheld: list[dict] = list(input_data.get("withheld_rows", []))
    errors: list[dict] = []

    resolved: dict[str, dict] = {}
    for section in sections:
        section_rows = [r for r in scoped if r.get("section_id") == section["section_id"]]
        if not section_rows:
            continue
        recipient, error_type, detail = resolve(
            section["heading"], section_rows[0]["detail"]["code"], aliases, prefixes)
        if recipient is None:
            section["recipient_error"] = error_type
            continue
        section["recipient_name"] = recipient["canonical"]
        section["recipient_kind"] = recipient["kind"]
        section["recipient_slug"] = recipient["slug"]
        section["resolution"] = detail
        if recipient["kind"] == "local_authority":
            public_body_id = register.get(_name_key(recipient["public_body_name"]))
            if public_body_id is None:
                raise ValueError(
                    f"local authority {recipient['public_body_name']!r} has no record in the "
                    f"Public Bodies register ({PUBLIC_BODIES_PATH}); publication stopped"
                )
            slug = resolve_slug(public_body_id, recipient["public_body_name"], slug_seed)
            section["public_body_id"] = public_body_id
            section["public_body"] = body_uri(slug)
        else:
            section["public_body_id"] = None
            section["public_body"] = None
            # The non-local-authority block is the document's own active-travel
            # table: every one of its blocks is active travel, not another stream.
            for block in section["blocks"]:
                block["funding_stream"] = "active_travel"
            section["stream_rule"] = "non_local_authority_section"
        resolved[section["section_id"]] = section

    for row in scoped:
        if row.get("kind") != "project":
            continue
        section = resolved.get(row.get("section_id"))
        if section is None:
            error_type = "RecipientUnresolved"
            for candidate in sections:
                if candidate["section_id"] == row.get("section_id"):
                    error_type = candidate.get("recipient_error", error_type)
                    break
            row["withheld_reason"] = error_type
            withheld.append(row)
            errors.append(make_error(
                STEP_NAME, error_type,
                f"{row['document_id']} page {row['page']}: recipient could not be resolved",
                document_id=row["document_id"], year=row["year"], page=row["page"],
                row_index=row["row_index"], cells=row["cells"],
                section_heading=row.get("section_heading"),
                code=row["detail"]["code"],
            ))
            continue
        row["recipient_name"] = section["recipient_name"]
        row["recipient_kind"] = section["recipient_kind"]
        row["recipient_slug"] = section["recipient_slug"]
        row["public_body_id"] = section["public_body_id"]
        row["public_body"] = section["public_body"]
        if section["recipient_kind"] == "other":
            row["funding_stream"] = "active_travel"

    withheld_ids = {id(row) for row in withheld}
    kept = [row for row in rows if id(row) not in withheld_ids]

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": now_iso(),
            "rows": len(kept),
            "withheld_rows": len(withheld),
            "sections": len(resolved),
            "prefix_only_sections": sum(1 for s in resolved.values()
                                        if s.get("resolution") == "prefix_only"),
        },
        **carried(input_data),
        "rows": kept,
        "withheld_rows": withheld,
        "sections": sections,
    }
    return output, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve allocation recipients")
    add_common_args(parser)
    add_doc_arg(parser)
    args = parser.parse_args()

    try:
        input_data = read_json_file(args.input)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Fatal: could not read input: {exc}")

    try:
        output, errors = run(input_data, document=args.doc)
    except ValueError as exc:
        sys.exit(f"Fatal: {exc}")

    errors_path = STEP_DIR / "errors.json"
    if errors_path.exists():
        errors_path.unlink()
    if errors:
        append_errors(STEP_DIR, errors)

    write_json(args.output, output)
    write_status(STEP_DIR, len(output["rows"]))
    print(f"Resolved {output['metadata']['sections']} sections, {len(output['rows'])} rows")


if __name__ == "__main__":
    main()

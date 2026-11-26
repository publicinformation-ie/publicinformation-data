"""Resolve every printed attendee to a person in the committed register.

Matching is exact after normalisation — no fuzzy or similarity matching. A
printed name that matches no person, matches more than one, or a person who is
recorded as both present and under apologies withholds the *whole meeting's*
attendance, so per-person counts are never quietly incomplete. The reason is
recorded in ``errors.json``.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

STEP_NAME = "resolve_attendees"

VALID_KINDS = ("councillor", "sectoral_representative", "official", "guest")


def normalise_name(value: str) -> str:
    """Normalise a printed name or alias for exact comparison."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = re.sub(r"'\s+", "'", text)          # O' Reilly -> O'Reilly
    text = re.sub(r"\bMc\s+", "Mc", text)      # Mc Caul -> McCaul
    tokens = text.split()
    while tokens and tokens[0].rstrip(".") in ("Cllr", "Mr", "Ms", "Mrs", "Dr"):
        tokens.pop(0)
    text = " ".join(tokens)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,;.").casefold()


def load_register(path: Path, councillor_reference: Path | None = None) -> list[dict]:
    """Load and validate the committed people register.

    Shape, kinds and councillor ids are checked here rather than in a test, so
    a bad register stops the step. When the motions councillor reference is
    available, every councillor id must exist in it.
    """
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: the people register must be a JSON list")
    for person in data:
        _validate_person(person, path)

    reference = councillor_reference or _default_councillor_reference(path)
    known = _read_councillor_ids(reference)
    if known is not None:
        unknown = sorted(
            person["councillor_id"] for person in data
            if person["kind"] == "councillor" and person["councillor_id"] not in known
        )
        if unknown:
            raise ValueError(
                f"{path}: unknown councillor id(s) not in {reference}: "
                f"{', '.join(unknown)}"
            )
    return data


def _validate_person(person: object, path: Path) -> None:
    if not isinstance(person, dict):
        raise ValueError(f"{path}: every register entry must be a JSON object")
    person_id = person.get("person_id")
    for key in ("person_id", "canonical_name", "kind", "public_body_id"):
        if not person.get(key):
            raise ValueError(f"{path}: register entry {person_id!r} has no {key}")
    kind = person["kind"]
    if kind not in VALID_KINDS:
        raise ValueError(
            f"{path}: {person_id!r} has unknown kind {kind!r}; "
            f"expected one of {', '.join(VALID_KINDS)}"
        )
    if not isinstance(person["public_body_id"], int):
        raise ValueError(f"{path}: {person_id!r} public_body_id must be an integer")
    for field in ("aliases", "initials"):
        values = person.get(field, [])
        if not isinstance(values, list) or not all(
                isinstance(value, str) and value for value in values):
            raise ValueError(
                f"{path}: {person_id!r} {field} must be a list of non-empty strings"
            )
    councillor_id = person.get("councillor_id")
    if kind == "councillor":
        if not councillor_id:
            raise ValueError(f"{path}: councillor {person_id!r} has no councillor_id")
        if councillor_id != person_id:
            raise ValueError(
                f"{path}: councillor {person_id!r} has councillor_id "
                f"{councillor_id!r}, which differs from its person_id"
            )
    elif councillor_id is not None:
        raise ValueError(
            f"{path}: non-councillor {person_id!r} must not have a councillor_id"
        )


def _default_councillor_reference(path: Path) -> Path | None:
    for parent in Path(path).resolve().parents:
        candidate = parent / "minutes_pipeline" / "reference" / "councillors.csv"
        if candidate.exists():
            return candidate
    return None


def _read_councillor_ids(path: Path | None) -> set[str] | None:
    import csv

    if path is None or not Path(path).exists():
        return None
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return {
            row["councillor_id"] for row in csv.DictReader(handle)
            if row.get("councillor_id")
        }


def build_alias_index(register: list[dict]) -> dict[str, str]:
    """Map normalised alias/name -> person_id; raise on an ambiguous alias."""
    index: dict[str, str] = {}
    for person in register:
        names = [person["canonical_name"], *person.get("aliases", [])]
        for name in names:
            key = normalise_name(name)
            if not key:
                continue
            if key in index and index[key] != person["person_id"]:
                raise ValueError(
                    f"alias {name!r} is listed by both {index[key]} and {person['person_id']}"
                )
            index[key] = person["person_id"]
    return index


def build_initials_index(register: list[dict]) -> dict[str, list[str]]:
    """Inititals -> person IDs. Ambiguity is reported only when used."""
    index: dict[str, list[str]] = {}
    for person in register:
        for initials in person.get("initials", []):
            index.setdefault(initials, [])
            if person["person_id"] not in index[initials]:
                index[initials].append(person["person_id"])
    return index


def resolve_initials(initials: str, meeting_initials: dict[str, str],
                     alias_index: dict[str, str],
                     initials_index: dict[str, list[str]]) -> tuple[str | None, str | None]:
    """Return ``(person_id, error_message)`` for printed initials.

    The meeting's printed ``(XX)`` map wins; the register is the fallback. An
    unresolved or ambiguous initialism returns an error, never a guess.
    """
    printed = meeting_initials.get(initials)
    if printed:
        person_id = alias_index.get(normalise_name(printed))
        if person_id:
            return person_id, None
        return None, (
            f"the meeting prints {printed!r} for initials {initials!r}, "
            f"which matches no registered person"
        )
    candidates = initials_index.get(initials, [])
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, f"initials {initials!r} resolve to no registered person"
    names = ", ".join(candidates)
    return None, f"initials {initials!r} are ambiguous between {names}"


def _status(entry: dict) -> str:
    if entry["category"] == "apologies" or "apologies" in entry.get("markers", []):
        return "apologies"
    return "present"


def _mode(entry: dict) -> tuple[str, bool]:
    markers = entry.get("markers", [])
    remote = "remote" in markers
    in_person = "in_person" in markers
    if remote and in_person:
        return "not_stated", True
    if remote:
        return "remote", False
    if in_person:
        return "in_person", False
    return "not_stated", False


#: Table order, used to pick the row a person is recorded under when their
#: name is printed in more than one attendance block (an official who also
#: presented, for example).
CATEGORY_ORDER = {
    "councillors": 0,
    "sectoral_representatives": 1,
    "officials": 2,
    "presenters": 3,
    "apologies": 4,
}


def _merge_printed_rows(rows: list[dict], record: dict,
                        errors: list[dict]) -> dict:
    """One attendance row per person, however many blocks printed their name."""
    rows = sorted(rows, key=lambda row: CATEGORY_ORDER[row["category"]])
    primary = dict(rows[0])
    roles: list[str] = []
    for row in rows:
        if row["role"] and row["role"] not in roles:
            roles.append(row["role"])
    stated_modes = {row["mode"] for row in rows if row["mode"] != "not_stated"}
    if len(stated_modes) > 1:
        errors.append(_error(
            "ContradictoryMode",
            f"{primary['printed_name']!r} is recorded with conflicting modes: "
            f"{', '.join(sorted(stated_modes))}",
            record, printed_name=primary["printed_name"],
        ))
    primary["role"] = "; ".join(roles) if roles else None
    primary["mode"] = next(iter(stated_modes), "not_stated")
    primary["presented"] = any(row["category"] == "presenters" for row in rows)
    return primary


def resolve_meeting(record: dict, alias_index: dict[str, str]) -> tuple[dict, list[dict]]:
    """Resolve one meeting's attendance; return ``(result, errors)``."""
    errors: list[dict] = []
    seen: dict[str, str] = {}
    by_person: dict[str, list[dict]] = {}

    for entry in record.get("attendance", []):
        person_id = alias_index.get(normalise_name(entry["printed_name"]))
        if person_id is None:
            errors.append(_error(
                "UnresolvedAttendee",
                f"{entry['printed_name']!r} matches no registered person",
                record, printed_name=entry["printed_name"],
            ))
            continue
        status = _status(entry)
        mode, contradictory_mode = _mode(entry)
        if contradictory_mode:
            errors.append(_error(
                "ContradictoryMode",
                f"{entry['printed_name']!r} is marked both online and in person",
                record, printed_name=entry["printed_name"],
            ))
        if person_id in seen and seen[person_id] != status:
            errors.append(_error(
                "ContradictoryAttendance",
                f"{entry['printed_name']!r} is recorded as both "
                f"{seen[person_id]} and {status}",
                record, printed_name=entry["printed_name"],
            ))
        seen.setdefault(person_id, status)
        printed = entry["printed_name"]
        if entry.get("title"):
            printed = f"{entry['title']} {printed}"
        by_person.setdefault(person_id, []).append({
            "meeting_id": record["meeting_id"],
            "person_id": person_id,
            "printed_name": printed,
            "category": entry["category"],
            "role": entry.get("role") or None,
            "status": status,
            "mode": mode,
        })

    attendance = [_merge_printed_rows(rows, record, errors)
                  for rows in by_person.values()]
    attendance.sort(key=lambda row: row["person_id"])

    withheld = bool(errors)
    result = dict(record)
    result["printed_attendance"] = result.pop("attendance", [])
    result["attendance"] = [] if withheld else attendance
    result["attendance_published"] = not withheld
    result["withheld_reasons"] = [
        f"{e['error_type']}: {e['error_message']}" for e in errors
    ]
    return result, errors


def run(input_data: dict, register: list[dict]) -> tuple[list[dict], list[dict]]:
    alias_index = build_alias_index(register)
    results: list[dict] = []
    errors: list[dict] = []
    for record in input_data.get("results", []):
        result, meeting_errors = resolve_meeting(record, alias_index)
        results.append(result)
        errors.extend(meeting_errors)
    return results, errors


def _error(error_type: str, message: str, record: dict, **extra) -> dict:
    from datetime import datetime, timezone

    context = {
        "meeting_id": record.get("meeting_id"),
        "public_body_id": record.get("public_body_id"),
        "file_url": record.get("source_url"),
    }
    context.update(extra)
    return {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": context,
    }

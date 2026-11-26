"""Extract official decisions and COFOG/subdomain topics from each meeting.

One model call per meeting, over the numbered items only (minutes-approval
items are classified deterministically and never sent). The response is
validated in a fixed order:

1. JSON schema — a failure fails the whole meeting closed.
2. Closed lists (COFOG codes, transport subdomains, decision types).
3. The ``04.5``/subdomain rule.
4. Verbatim quote check against the item's text.
5. Minutes-approval discard.
6. Proposer and seconder resolution through the people register.

A per-item violation withholds that item's topics or that decision; the rest
of the meeting is unaffected. Results are cached by source sha256, model and
prompt version so an unchanged re-run makes no model call.
"""
from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from lib import llm_extract
from steps.resolve_attendees.resolving import (
    build_alias_index,
    build_initials_index,
    load_register,
    normalise_name,
    resolve_initials,
)

STEP_NAME = "extract_spc_items"
PROMPT_VERSION = "spc-items-v1"
DECISION_TYPES = (
    "agreed", "adopted", "recommended_to_council", "referred", "deferred", "appointment",
)
_MINUTES_APPROVAL_CODE = "01.1.1"

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        # Models sometimes echo the meeting context they were given, either as
        # flat keys or as a `meeting` object. Echoed values are accepted only
        # when they agree with the meeting being extracted (see
        # _validate_echoed_context); content fields stay strict.
        "meeting_id": {"type": "string"},
        "date": {"type": "string"},
        "committee": {"type": "string"},
        "meeting": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "meeting_id": {"type": "string"},
                "date": {"type": "string"},
                "committee": {"type": "string"},
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item_key", "topics", "decisions"],
                "properties": {
                    "item_key": {"type": "string"},
                    "topics": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["cofog", "subdomains", "procedural"],
                        "properties": {
                            "cofog": {
                                "type": "array", "minItems": 1, "maxItems": 3,
                                "items": {"type": "string"},
                            },
                            "subdomains": {"type": "array", "items": {"type": "string"}},
                            "procedural": {"type": "boolean"},
                        },
                    },
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["decision_text", "decision_type",
                                         "proposer", "seconder"],
                            "properties": {
                                "decision_text": {"type": "string", "minLength": 1},
                                "decision_type": {"type": "string"},
                                "proposer": {"type": ["string", "null"]},
                                "seconder": {"type": ["string", "null"]},
                            },
                        },
                    },
                },
            },
        },
    },
}


class ExtractionFailed(ValueError):
    error_type = "ExtractionFailed"


#: Production model chosen by the 2026-11-26 sweep (see
#: `experiments/2026-11-26-spc-model-sweep/REPORT.md`). `SPC_LLM_MODEL`
#: overrides it for one run.
DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"


def spc_model() -> str:
    return os.environ.get("SPC_LLM_MODEL") or DEFAULT_MODEL


@contextmanager
def spc_llm_env():
    """Expose SPC_LLM_* to llm_extract, falling back to MOTIONS_LLM_* when unset."""
    mapping = {
        "SPC_LLM_PROVIDER": "MOTIONS_LLM_PROVIDER",
        "SPC_LLM_MODEL": "MOTIONS_LLM_MODEL",
        "SPC_LLM_BASE_URL": "MOTIONS_LLM_BASE_URL",
        "SPC_LLM_API_KEY": "MOTIONS_LLM_API_KEY",
        "SPC_LLM_SESSION_ID": "MOTIONS_LLM_SESSION_ID",
    }
    previous = {}
    try:
        for spc_name, motions_name in mapping.items():
            if spc_name in os.environ:
                previous[motions_name] = os.environ.get(motions_name)
                os.environ[motions_name] = os.environ[spc_name]
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def load_taxonomy(pipeline_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    cofog_data = json.loads((pipeline_dir / "reference" / "cofog_1999.json").read_text())
    subdomain_data = json.loads(
        (pipeline_dir / "reference" / "transport_subdomains.json").read_text()
    )
    cofog = {entry["code"]: entry["description"] for entry in cofog_data["codes"]}
    subdomains = {entry["id"]: entry["plain_label"] for entry in subdomain_data["subdomains"]}
    return cofog, subdomains


def build_prompt(meeting: dict, cofog: dict[str, str],
                 subdomains: dict[str, str]) -> tuple[str, str]:
    """Return ``(system, user)`` for one meeting; no model call."""
    items = [
        {"item_key": item["item_key"], "number": item["number"],
         "title": item["title"], "text": item["text"]}
        for item in meeting.get("items", [])
        if not item.get("is_minutes_approval")
    ]
    system = (
        "You extract official decisions and topic codes from local-authority "
        "Strategic Policy Committee minutes. Return one JSON object only, with "
        "no commentary and no code fence. Follow the response schema exactly.\n\n"
        "For every item supplied:\n"
        "- topics.cofog: one to three codes from the COFOG 1999 closed list, the "
        "first being the primary. Use a class code; use a group code only when "
        "the item spans several classes of that group.\n"
        "- topics.subdomains: one or more IDs from the transport subdomain list "
        "when (and only when) a chosen COFOG code is under 04.5. Otherwise an "
        "empty array.\n"
        "- topics.procedural: true only for purely procedural items with no "
        "substantive content.\n"
        "- decisions: only official decisions (agreed, adopted, recommended to "
        "council, referred, deferred, appointment). decision_text must be a "
        "contiguous verbatim quote from the item's text; never paraphrase. "
        "decision_type must be exactly one of: " + ", ".join(DECISION_TYPES) + ". "
        "proposer and seconder: the person as printed (name or initials), or "
        "null when the minutes do not name them.\n"
        "Do not invent decisions. A presentation or discussion with no decision "
        "has an empty decisions array."
    )
    user = json.dumps({
        "meeting": {
            "meeting_id": meeting["meeting_id"],
            "date": meeting["meeting_date"],
            "committee": meeting["committee_name"],
        },
        "items": items,
        "initials": meeting.get("initials", {}),
        "closed_lists": {
            "cofog_1999": cofog,
            "transport_subdomains": subdomains,
            "decision_types": list(DECISION_TYPES),
        },
    }, ensure_ascii=False, indent=2)
    return system, user


def cache_path(cache_dir: Path, source_sha256: str, model: str) -> Path:
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", model)
    return Path(cache_dir) / "llm" / f"{source_sha256}-{safe_model}-{PROMPT_VERSION}.json"


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _resolve_person(value, meeting_initials, alias_index, initials_index):
    if value is None:
        return None, None
    text = str(value).strip().strip(" ,;.")
    if not text:
        return None, None
    initials_match = re.search(r"\(([A-Za-z'’]{1,6})\)\s*$", text)
    if initials_match:
        text = initials_match.group(1)
    if text in meeting_initials or len(text) <= 6 and text.isupper():
        person, error = resolve_initials(text, meeting_initials, alias_index, initials_index)
        if person:
            return person, None
        if "(" in str(value) or text.isupper():
            return None, error
    person = alias_index.get(normalise_name(text))
    if person:
        return person, None
    return None, f"{value!r} resolves to no registered person"


def _is_minutes_approval_decision(text: str) -> bool:
    """True when the quote only approves/confirms earlier minutes."""
    pattern = (
        r"(?i)\b(approv\w*|adopt\w*|confirm\w*)\b[^.]{0,80}\bminutes\b"
        r"|\bminutes\b[^.]{0,80}\b(approv\w*|adopt\w*|confirm\w*)\b"
    )
    return re.search(pattern, text) is not None


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _validate_echoed_context(response: dict, meeting: dict) -> None:
    """Accept echoed meeting context only when it agrees with the meeting.

    Some models repeat the id, date or committee they were given, flat or
    under a ``meeting`` object. That is harmless, but a wrong echo means the
    response may belong to another meeting, so a disagreement fails closed.
    """
    nested = response.get("meeting") or {}
    flat = {key: response[key] for key in ("meeting_id", "date", "committee")
            if response.get(key) is not None}
    for key, value in flat.items():
        if key in nested and str(nested[key]) != str(value):
            raise ExtractionFailed(f"response echoes conflicting {key} values")
    echoed = {**nested, **flat}
    expected = {
        "meeting_id": meeting["meeting_id"],
        "date": meeting["meeting_date"],
    }
    for key, want in expected.items():
        if echoed.get(key) and str(echoed[key]) != want:
            raise ExtractionFailed(
                f"response echoes {key} {echoed[key]!r}, not {want!r}"
            )
    if echoed.get("committee") and (_squash(str(echoed["committee"]))
                                    != _squash(meeting["committee_name"])):
        raise ExtractionFailed(
            f"response echoes committee {echoed['committee']!r}, "
            f"not {meeting['committee_name']!r}"
        )


def validate_response(meeting: dict, response: dict, cofog: dict[str, str],
                      subdomains: dict[str, str], register: list[dict],
                      model: str | None = None) -> tuple[dict, list[dict]]:
    """Validate a parsed model response; return ``(result, errors)``."""
    try:
        jsonschema.validate(response, RESPONSE_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ExtractionFailed(f"response failed the schema: {exc.message}") from exc

    _validate_echoed_context(response, meeting)

    alias_index = build_alias_index(register)
    initials_index = build_initials_index(register)
    meeting_initials = meeting.get("initials", {})

    response_by_key: dict[str, dict] = {}
    errors: list[dict] = []
    for entry in response["items"]:
        key = str(entry["item_key"])
        if key in response_by_key:
            errors.append(_error("UnexpectedItem", f"item {key} returned twice", meeting))
            continue
        response_by_key[key] = entry

    known_items = {item["item_key"]: item for item in meeting.get("items", [])}
    for key in response_by_key:
        if key not in known_items:
            errors.append(_error(
                "UnexpectedItem", f"response names item {key}, which is not in the meeting",
                meeting,
            ))

    decisions: list[dict] = []
    item_topics: list[dict] = []
    minutes_approval_discarded = 0

    for item in meeting.get("items", []):
        number = item["number"]
        item_key = item["item_key"]
        if item.get("is_minutes_approval"):
            item_topics.append({
                "item_key": item_key,
                "number": number,
                "cofog": [_MINUTES_APPROVAL_CODE],
                "subdomains": [],
                "procedural": True,
            })
            continue
        entry = response_by_key.get(item_key)
        if entry is None:
            errors.append(_error(
                "MissingItem", f"response has no entry for item {item_key}", meeting,
                item_number=number, item_key=item_key,
            ))
            item_topics.append({"item_key": item_key, "number": number, "cofog": None,
                                "subdomains": None, "procedural": None, "withheld": True})
            continue

        topics = entry["topics"]
        codes = topics["cofog"]
        item_errors = []
        unknown_codes = [code for code in codes if code not in cofog]
        if unknown_codes:
            item_errors.append(_error(
                "UnknownCofogCode",
                f"item {number} returned unknown COFOG code(s): {', '.join(unknown_codes)}",
                meeting, item_number=number,
            ))
        if len(set(codes)) != len(codes):
            item_errors.append(_error(
                "DuplicateCofogCode", f"item {number} repeats a COFOG code",
                meeting, item_number=number,
            ))
        unknown_subdomains = [s for s in topics["subdomains"] if s not in subdomains]
        if unknown_subdomains:
            item_errors.append(_error(
                "UnknownSubdomain",
                f"item {number} returned unknown subdomain(s): "
                f"{', '.join(unknown_subdomains)}",
                meeting, item_number=number,
            ))
        has_transport = any(code == "04.5" or code.startswith("04.5.") for code in codes)
        if topics["subdomains"] and not has_transport:
            item_errors.append(_error(
                "SubdomainWithoutTransport",
                f"item {number} carries a subdomain but no 04.5 COFOG code",
                meeting, item_number=number,
            ))
        topics_valid = not item_errors
        item_topics.append({
            "item_key": item_key,
            "number": number,
            "cofog": codes if topics_valid else None,
            "subdomains": topics["subdomains"] if topics_valid else None,
            "procedural": topics["procedural"] if topics_valid else None,
            "withheld": not topics_valid,
        })
        errors.extend(item_errors)

        for decision in entry["decisions"]:
            text = decision["decision_text"]
            if decision["decision_type"] not in DECISION_TYPES:
                errors.append(_error(
                    "UnknownDecisionType",
                    f"item {number} returned unknown decision type "
                    f"{decision['decision_type']!r}",
                    meeting, item_number=number,
                ))
                continue
            if _normalise_text(text) not in _normalise_text(item["text"]):
                errors.append(_error(
                    "DecisionNotInSource",
                    f"item {number} decision is not a verbatim quote: {text!r}",
                    meeting, item_number=number,
                ))
                continue
            if _is_minutes_approval_decision(text):
                minutes_approval_discarded += 1
                continue
            proposer, proposer_error = _resolve_person(
                decision["proposer"], meeting_initials, alias_index, initials_index)
            seconder, seconder_error = _resolve_person(
                decision["seconder"], meeting_initials, alias_index, initials_index)
            if proposer_error:
                errors.append(_error(
                    "UnresolvedDecisionPerson",
                    f"item {number} proposer: {proposer_error}",
                    meeting, item_number=number, field="proposer",
                ))
            if seconder_error:
                errors.append(_error(
                    "UnresolvedDecisionPerson",
                    f"item {number} seconder: {seconder_error}",
                    meeting, item_number=number, field="seconder",
                ))
            decisions.append({
                "item_key": item_key,
                "item_number": number,
                "decision_text": text,
                "decision_type": decision["decision_type"],
                "proposer": proposer,
                "seconder": seconder,
            })

    for index, decision in enumerate(decisions, start=1):
        decision["decision_id"] = f"{meeting['meeting_id']}/d{index:02d}"

    # Carry the whole meeting through: export_spc_meetings reads this step's
    # output, so dropping the rendered minutes, items or attendance here would
    # silently publish nothing.
    result = dict(meeting)
    result.update({
        "decisions": decisions,
        "item_topics": item_topics,
        "minutes_approval_discarded": minutes_approval_discarded,
        "model": model or spc_model(),
        "prompt_version": PROMPT_VERSION,
        "extraction_failed": False,
    })
    return result, errors


def extract_meeting(meeting: dict, cache_dir: Path, register: list[dict],
                    cofog: dict[str, str], subdomains: dict[str, str],
                    api_fn=None, model: str | None = None) -> tuple[dict, list[dict]]:
    """Extract one meeting, using the cache when inputs are unchanged.

    ``model`` overrides the configured model for this call (used by the model
    sweep); it also varies the cache key, so each model's responses are kept
    separately.
    """
    if meeting.get("items") is None:
        raise ExtractionFailed("the meeting has no rendered items")

    chosen_model = model or spc_model()
    system, user = build_prompt(meeting, cofog, subdomains)
    path = cache_path(cache_dir, meeting["source_sha256"], chosen_model)
    if path.exists():
        try:
            response = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            response = None
    else:
        response = None

    if response is None:
        if api_fn is not None:
            response = llm_extract.extract_json(system, user, api_fn=api_fn)
        else:
            with spc_llm_env():
                response = llm_extract.extract_json(system, user, model=chosen_model)
        if response is None:
            raise ExtractionFailed("the model returned no parseable JSON")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")

    return validate_response(meeting, response, cofog, subdomains, register,
                             model=chosen_model)


def run(input_data: dict, cache_dir: Path, register: list[dict],
        cofog: dict[str, str], subdomains: dict[str, str],
        api_fn=None) -> tuple[list[dict], list[dict]]:
    results: list[dict] = []
    errors: list[dict] = []
    for meeting in input_data.get("results", []):
        try:
            result, meeting_errors = extract_meeting(
                meeting, cache_dir, register, cofog, subdomains, api_fn=api_fn)
        except ExtractionFailed as exc:
            failed = dict(meeting)
            failed.update({
                "decisions": [],
                "item_topics": [],
                "minutes_approval_discarded": 0,
                "model": spc_model(),
                "prompt_version": PROMPT_VERSION,
                "extraction_failed": True,
            })
            results.append(failed)
            errors.append(_error(exc.error_type, str(exc), meeting))
            continue
        results.append(result)
        errors.extend(meeting_errors)
    return results, errors


def _error(error_type: str, message: str, meeting: dict, **extra) -> dict:
    context = {
        "meeting_id": meeting.get("meeting_id"),
        "public_body_id": meeting.get("public_body_id"),
        "file_url": meeting.get("source_url"),
    }
    context.update(extra)
    return {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": context,
    }

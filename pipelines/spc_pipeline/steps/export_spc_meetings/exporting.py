"""Assemble the published SPC meetings dataset from a completed pipeline run.

Meetings whose render failed never reach this step. Attendance, topics or
decisions withheld upstream stay withheld here and are counted in the report
by error type, so a consumer never mistakes missing data for absence.
"""
from __future__ import annotations

from collections import Counter

STEP_NAME = "export_spc_meetings"


def _minutes_path(meeting: dict) -> str:
    return f"minutes/{meeting['committee_id']}/{meeting['meeting_date']}.md"


def _meeting_record(record: dict) -> dict:
    return {
        "meeting_id": record["meeting_id"],
        "committee_id": record["committee_id"],
        "committee_name": record["committee_name"],
        "public_body_id": record["public_body_id"],
        "meeting_date": record["meeting_date"],
        "venue": record.get("venue"),
        "start_time": record.get("start_time"),
        "end_time": record.get("end_time"),
        "source_url": record["source_url"],
        "source_sha256": record["source_sha256"],
        "minutes_path": _minutes_path(record),
        "attendance_published": record["attendance_published"],
        "text_source": record["text_source"],
        "ocr_engine": record["ocr_engine"],
    }


def _topics_by_key(record: dict) -> dict[str, dict]:
    return {entry["item_key"]: entry for entry in record.get("item_topics", [])}


def _item_records(record: dict) -> list[dict]:
    topics = _topics_by_key(record)
    items: list[dict] = []
    for item in record.get("items", []):
        entry = topics.get(item["item_key"], {})
        published = entry.get("cofog") is not None
        items.append({
            "item_id": f"{record['meeting_id']}/{item['item_key']}",
            "meeting_id": record["meeting_id"],
            "item_number": item["number"],
            "item_key": item["item_key"],
            "title": item["title"],
            "text": item["text"],
            "is_minutes_approval": bool(item.get("is_minutes_approval")),
            "topics_published": published,
            "cofog": entry.get("cofog") if published else None,
            "subdomains": entry.get("subdomains") if published else None,
            "procedural": entry.get("procedural") if published else None,
        })
    return items


def _decision_records(record: dict) -> list[dict]:
    return [{
        **decision,
        "meeting_id": record["meeting_id"],
        "meeting_date": record["meeting_date"],
    } for decision in record.get("decisions", [])]


def _person_records(referenced: set[str], register_by_id: dict[str, dict]) -> list[dict]:
    people = []
    for person_id in sorted(referenced):
        person = register_by_id.get(person_id)
        if person is None:
            continue
        people.append({
            "person_id": person["person_id"],
            "canonical_name": person["canonical_name"],
            "kind": person["kind"],
            "councillor_id": person.get("councillor_id"),
            "public_body_id": person["public_body_id"],
        })
    return people


def export(input_data: dict, register: list[dict]) -> tuple[dict, dict]:
    """Return ``(dataset, report)``."""
    register_by_id = {person["person_id"]: person for person in register}

    meetings: list[dict] = []
    minutes: list[dict] = []
    attendance: list[dict] = []
    items: list[dict] = []
    decisions: list[dict] = []
    referenced_people: set[str] = set()
    reported_errors: Counter = Counter()
    render_failures = 0

    for record in input_data.get("results", []):
        if record.get("word_check") != "passed" or not record.get("markdown"):
            render_failures += 1
            continue

        published = record.get("attendance_published")
        if not isinstance(published, bool):
            raise ValueError(
                f"{record.get('meeting_id')}: attendance_published must be a boolean"
            )
        rows = record.get("attendance", [])
        if not published and rows:
            raise ValueError(
                f"{record.get('meeting_id')}: attendance_published is false but "
                f"{len(rows)} attendance row(s) are present"
            )

        meetings.append(_meeting_record(record))
        minutes.append({
            "meeting_id": record["meeting_id"],
            "path": _minutes_path(record),
            "markdown": record["markdown"],
        })
        for row in record.get("attendance", []):
            attendance.append({
                "meeting_id": row["meeting_id"],
                "meeting_date": record["meeting_date"],
                "person_id": row["person_id"],
                "category": row["category"],
                "role": row.get("role"),
                "status": row["status"],
                "mode": row["mode"],
                "presented": bool(row.get("presented", False)),
            })
            referenced_people.add(row["person_id"])
        for reason in record.get("withheld_reasons", []):
            reported_errors[reason.split(":", 1)[0]] += 1

        meeting_items = _item_records(record)
        items.extend(meeting_items)
        withheld_topics = sum(1 for item in meeting_items if not item["topics_published"])
        if withheld_topics:
            reported_errors["WithheldTopics"] += withheld_topics

        meeting_decisions = _decision_records(record)
        decisions.extend(meeting_decisions)
        for decision in meeting_decisions:
            for field in ("proposer", "seconder"):
                if decision.get(field):
                    referenced_people.add(decision[field])
        if record.get("extraction_failed"):
            reported_errors["ExtractionFailed"] += 1

    people = _person_records(referenced_people, register_by_id)
    missing_people = referenced_people - {person["person_id"] for person in people}
    if missing_people:
        raise ValueError(
            "attendance or a decision references person id(s) with no register "
            f"entry: {', '.join(sorted(missing_people))}"
        )

    dataset = {
        "meetings": meetings,
        "people": people,
        "attendance": attendance,
        "items": items,
        "decisions": decisions,
        "minutes": minutes,
    }
    report = {
        "meetings": len(meetings),
        "attendance": len(attendance),
        "items": len(items),
        "decisions": len(decisions),
        "people": len(people),
        "render_failures": render_failures,
        "attendance_withheld": sum(1 for meeting in meetings
                                   if not meeting["attendance_published"]),
        "topics_withheld": sum(1 for item in items if not item["topics_published"]),
        "by_error_type": dict(sorted(reported_errors.items())),
    }
    return dataset, report

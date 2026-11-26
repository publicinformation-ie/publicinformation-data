from pathlib import Path

from steps.export_spc_meetings.exporting import export
from steps.resolve_attendees.resolving import load_register

PIPELINE = Path(__file__).resolve().parents[1]
REGISTER = load_register(PIPELINE / "reference" / "people.json")


def _record(**overrides):
    record = {
        "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
        "committee_id": "meath/transportation-urban-regeneration",
        "committee_name": "Transportation & Urban Regeneration Strategic Policy Committee",
        "public_body_id": 1511,
        "meeting_date": "2026-02-19",
        "venue": "Swift Room",
        "start_time": "2.30 pm",
        "end_time": "16.10 pm",
        "source_url": "https://www.meath.ie/x.pdf",
        "source_sha256": "a" * 64,
        "markdown": "# Minutes\n",
        "word_check": "passed",
        "attendance_published": True,
        "withheld_reasons": [],
        "attendance": [{
            "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
            "person_id": "meath/michael-bray",
            "printed_name": "Cllr Mike Bray",
            "category": "councillors",
            "role": "Chair",
            "status": "present",
            "mode": "not_stated",
            "presented": False,
        }],
        "items": [{
            "item_key": "item-2-0",
            "number": "2.0",
            "title": "Matters Arising from Minutes",
            "text": "It was agreed to circulate the policy.",
            "is_minutes_approval": False,
        }],
        "item_topics": [{
            "item_key": "item-2-0",
            "number": "2.0",
            "cofog": ["04.5.1"],
            "subdomains": ["infra/regional-local-roads"],
            "procedural": False,
        }],
        "decisions": [{
            "decision_id": "meath/transportation-urban-regeneration/2026-02-19/d01",
            "item_number": "2.0",
            "decision_text": "It was agreed to circulate the policy.",
            "decision_type": "agreed",
            "proposer": "meath/amanda-smith",
            "seconder": None,
        }],
        "extraction_failed": False,
    }
    record.update(overrides)
    return record


def test_clean_meeting_is_assembled_with_a_minutes_path():
    dataset, report = export({"results": [_record()]}, REGISTER)
    assert report["meetings"] == 1
    assert report["render_failures"] == 0
    meeting = dataset["meetings"][0]
    assert meeting["minutes_path"] == (
        "minutes/meath/transportation-urban-regeneration/2026-02-19.md"
    )
    assert meeting["attendance_published"] is True
    assert dataset["attendance"][0]["person_id"] == "meath/michael-bray"
    assert dataset["items"][0]["cofog"] == ["04.5.1"]
    assert dataset["decisions"][0]["decision_id"].endswith("/d01")
    people_ids = {person["person_id"] for person in dataset["people"]}
    assert people_ids == {"meath/michael-bray", "meath/amanda-smith"}


def test_withheld_attendance_is_visible_and_has_no_rows():
    record = _record(attendance=[], attendance_published=False,
                     withheld_reasons=["UnresolvedAttendee: 'Niamh Nobody' matches no person"])
    dataset, report = export({"results": [record]}, REGISTER)
    assert dataset["meetings"][0]["attendance_published"] is False
    assert dataset["attendance"] == []
    assert report["attendance_withheld"] == 1
    assert report["by_error_type"]["UnresolvedAttendee"] == 1


def test_withheld_topics_are_marked_and_counted():
    record = _record(item_topics=[{
        "item_key": "item-2-0", "number": "2.0", "cofog": None,
        "subdomains": None, "procedural": None, "withheld": True,
    }])
    dataset, report = export({"results": [record]}, REGISTER)
    item = dataset["items"][0]
    assert item["topics_published"] is False
    assert item["cofog"] is None
    assert report["topics_withheld"] == 1


def test_extraction_failure_withholds_decisions_and_topics():
    record = _record(decisions=[], item_topics=[], extraction_failed=True)
    dataset, report = export({"results": [record]}, REGISTER)
    assert dataset["decisions"] == []
    assert dataset["items"][0]["topics_published"] is False
    assert report["by_error_type"]["ExtractionFailed"] == 1


def test_render_failure_publishes_nothing():
    record = _record(word_check="failed", markdown=None)
    dataset, report = export({"results": [record]}, REGISTER)
    assert dataset == {"meetings": [], "people": [], "attendance": [],
                       "items": [], "decisions": [], "minutes": []}
    assert report["render_failures"] == 1

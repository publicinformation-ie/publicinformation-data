import json
from pathlib import Path

import pytest

def _sweep_module():
    import sweep

    return sweep

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments/2026-11-26-spc-model-sweep"
GOLD = EXPERIMENT / "gold.json"


def _gold():
    return json.loads(GOLD.read_text())


def test_gold_covers_every_rendered_item_and_quotes_are_verbatim(rendered_meetings):
    import re

    gold = _gold()
    rendered = rendered_meetings
    cofog = json.loads((Path(__file__).resolve().parents[1] / "reference/cofog_1999.json").read_text())
    codes = {entry["code"] for entry in cofog["codes"]}
    subdomains = json.loads(
        (Path(__file__).resolve().parents[1] / "reference/transport_subdomains.json").read_text())
    sub_ids = {entry["id"] for entry in subdomains["subdomains"]}

    for meeting in rendered:
        entry = gold["meetings"][meeting["meeting_id"]]
        assert set(entry["items"]) == {item["item_key"] for item in meeting["items"]}
        items = {item["item_key"]: item for item in meeting["items"]}
        for item_key, gold_item in entry["items"].items():
            assert 1 <= len(gold_item["cofog"]) <= 3
            assert set(gold_item["cofog"]) <= codes
            assert set(gold_item["subdomains"]) <= sub_ids
            has_transport = any(code.startswith("04.5") for code in gold_item["cofog"])
            assert bool(gold_item["subdomains"]) == has_transport
        for decision in entry["decisions"]:
            assert decision["decision_type"] in {
                "agreed", "adopted", "recommended_to_council", "referred",
                "deferred", "appointment"}
            quote = re.sub(r"\s+", " ", decision["decision_text"]).strip()
            source = re.sub(r"\s+", " ", items[decision["item_key"]]["text"]).strip()
            assert quote in source


def _canned_for(gold_meeting: dict, meeting_id: str, *, extra_decision=False):
    result = {
        "meeting_id": meeting_id,
        "decisions": [{
            "item_key": decision["item_key"],
            "decision_text": decision["decision_text"],
            "decision_type": decision["decision_type"],
            "proposer": None,
            "seconder": None,
        } for decision in gold_meeting["decisions"]],
        "item_topics": [{
            "item_key": key,
            "number": value["number"],
            "cofog": value["cofog"],
            "subdomains": value["subdomains"],
            "procedural": value["procedural"],
        } for key, value in gold_meeting["items"].items()],
    }
    if extra_decision:
        result["decisions"].append({
            "item_key": "item-1-0", "decision_text": "A hallucinated decision.",
            "decision_type": "agreed", "proposer": None, "seconder": None})
    return result


def test_sweep_scores_canned_responses_end_to_end(tmp_path):
    gold = _gold()
    model = "canned-model"
    canned = tmp_path / "canned" / model
    canned.mkdir(parents=True)
    for meeting_id, entry in gold["meetings"].items():
        slug = meeting_id.rsplit("/", 1)[-1]
        (canned / f"{slug}.json").write_text(json.dumps({
            "result": _canned_for(entry, meeting_id),
            "errors": [],
        }))

    sweep = _sweep_module()
    meetings = [{"meeting_id": meeting_id} for meeting_id in gold["meetings"]]
    report = sweep.run_sweep([model], meetings, gold,
                             sweep.canned_runner(tmp_path / "canned"))
    aggregate = report["models"][0]["aggregate"]
    assert aggregate["decision_precision"] == 1.0
    assert aggregate["decision_recall"] == 1.0
    assert aggregate["topic_primary_accuracy"] == 1.0
    assert aggregate["verbatim_failure_rate"] == 0.0
    text = sweep.render_report(report)
    assert "SPC model sweep" in text and "canned-model" in text
    assert "Cost per meeting" in text


def test_an_extra_decision_lowers_precision():
    sweep = _sweep_module()
    gold = _gold()
    meeting_id = next(iter(gold["meetings"]))
    entry = gold["meetings"][meeting_id]
    result = _canned_for(entry, meeting_id, extra_decision=True)
    score = sweep.score_meeting(result, entry, [])
    assert score["decision_precision"] < 1.0
    assert score["decision_recall"] == 1.0


def test_a_failed_extraction_scores_zero_and_is_flagged():
    sweep = _sweep_module()
    gold = _gold()
    meeting_id = next(iter(gold["meetings"]))
    failed = {"meeting_id": meeting_id, "decisions": [], "item_topics": [],
              "extraction_failed": True}
    score = sweep.score_meeting(failed, gold["meetings"][meeting_id],
                               [{"error_type": "ExtractionFailed"}])
    assert score["extraction_failed"] is True
    assert score["decision_precision"] == 0.0
    assert score["decision_recall"] == 0.0
    assert score["verbatim_failure_rate"] is None


def test_run_sweep_keeps_going_past_a_failing_meeting():
    sweep = _sweep_module()
    gold = _gold()
    meeting_ids = list(gold["meetings"])

    def runner(model, meeting):
        if meeting["meeting_id"] == meeting_ids[0]:
            return {"meeting_id": meeting["meeting_id"], "decisions": [],
                    "item_topics": [], "extraction_failed": True}, [], None
        return _canned_for(gold["meetings"][meeting["meeting_id"]],
                           meeting["meeting_id"]), [], None

    report = sweep.run_sweep(["m"], [{"meeting_id": m} for m in meeting_ids],
                             gold, runner)
    model = report["models"][0]
    assert model["aggregate"]["extraction_failure_rate"] == round(1 / len(meeting_ids), 3)
    assert len(model["meetings"]) == len(meeting_ids)
    assert "failed" in sweep.render_report(report)


def test_same_decision_tolerates_a_boundary_difference():
    sweep = _sweep_module()
    gold = ("It was agreed that 2026 meetings would be as follows:")
    model = ("It was agreed that 2026 meetings would be as follows: "
             "Thursday 19th February @ 2.30pm Thursday 21st May @ 2.30pm")
    assert sweep.same_decision(gold, model)
    assert sweep.same_decision(model, gold)


def test_same_decision_matches_a_prefix_followed_by_punctuation():
    sweep = _sweep_module()
    gold = "Members agreed that glyphosate is a harmful product and should be avoided"
    model = ("Members agreed that glyphosate is a harmful product and should be "
             "avoided. Further discussion followed on the matter.")
    assert sweep.same_decision(gold, model)
    assert not sweep.same_decision("agreed that the glyphosate is a harm",
                                   "Members agreed that the glyphosate is a harmful product")


def test_same_decision_rejects_a_bare_fragment_or_a_different_quote():
    sweep = _sweep_module()
    assert not sweep.same_decision("It was agreed", "It was agreed that the policy be adopted")
    assert not sweep.same_decision("It was agreed to circulate the policy.",
                                   "It was agreed to review the programme.")


def test_a_shorter_quote_inside_a_longer_one_matches_only_on_the_same_item():
    sweep = _sweep_module()
    gold = [{"item_key": "item-2-0", "decision_type": "agreed",
             "decision_text": "It was agreed that the policy be adopted by the members."}]
    extracted = [{"item_key": "item-3-0", "decision_type": "agreed",
                  "decision_text": "It was agreed that the policy be adopted by the members."}]
    metrics = sweep.decision_metrics(extracted, gold)
    assert metrics["precision"] == 0.0 and metrics["recall"] == 0.0


def test_topic_agreement_tolerates_group_class_and_ordering():
    sweep = _sweep_module()
    topics = [
        {"item_key": "item-1-0", "cofog": ["04.5.1"]},
        {"item_key": "item-2-0", "cofog": ["06.2.0", "04.5.1"]},
        {"item_key": "item-3-0", "cofog": ["05.3.0"]},
    ]
    gold = {
        "item-1-0": {"cofog": ["04.5"]},
        "item-2-0": {"cofog": ["04.5.1"]},
        "item-3-0": {"cofog": ["06.4.0"]},
    }
    metrics = sweep.topic_metrics(topics, gold)
    assert metrics["primary_accuracy"] == 0.0
    assert metrics["agreement"] == pytest.approx(2 / 3)

import pytest

from steps.extract_motions.guards import (
    detect_ce_schedule,
    detect_procedural_dump,
)


def _schedule_text(pma=500, accept=200, on_proposal=200):
    return "\n".join(
        ["Proposed Material Alteration No. 1"] * pma
        + ["We accept the Chief Executive's recommendation."] * accept
        + ["On the proposal by Cllr. A."] * on_proposal
    )


def _motion(i, *, accept=True, pma=True, proposer="Cllr. Doyle",
            seconder="Cllr. Sammon"):
    parts = ["That the council act."]
    if accept:
        parts.append("Accept the Chief Executive's recommendation.")
    if pma:
        parts.append("Proposed Material Alteration No. 1.")
    return {
        "motion_text": f"{' '.join(parts)} Item {i}.",
        "proposer": proposer,
        "seconder": seconder,
        "status_label": "carried",
    }


def _dump(n=100, accept_n=80, pma_n=80, proposer_n=80, seconder_n=80):
    return [
        _motion(
            i,
            accept=i < accept_n,
            pma=i < pma_n,
            proposer="Cllr. Doyle" if i < proposer_n else f"Cllr. Other {i}",
            seconder="Cllr. Sammon" if i < seconder_n else f"Cllr. Other {i}",
        )
        for i in range(n)
    ]


def test_pre_filter_detects_extreme_ce_schedule():
    evidence = detect_ce_schedule(_schedule_text())
    assert evidence is not None
    assert evidence["proposed_material_alteration_count"] == 500
    assert evidence["accept_chief_executive_count"] == 200
    assert evidence["on_the_proposal_count"] == 200


@pytest.mark.parametrize("pma,accept,on_proposal", [
    (499, 200, 200),
    (500, 199, 200),
    (500, 200, 199),
])
def test_pre_filter_requires_all_thresholds(pma, accept, on_proposal):
    assert detect_ce_schedule(_schedule_text(pma, accept, on_proposal)) is None


def test_pre_filter_ignores_legitimate_ce_report_without_pma_schedule():
    # The Kildare 24 Feb 2022 document has hundreds of "accept the Chief
    # Executive" phrases but few numbered material alterations and contains
    # genuine member motions.
    assert detect_ce_schedule(
        _schedule_text(pma=0, accept=360, on_proposal=416)
    ) is None


def test_post_filter_detects_procedural_dump():
    evidence = detect_procedural_dump(_dump())
    assert evidence is not None
    assert evidence["motion_count"] == 100
    assert evidence["accept_chief_executive_ratio"] == 0.8
    assert evidence["pma_or_alteration_ratio"] == 0.8
    assert evidence["top_proposer_ratio"] == 0.8
    assert evidence["top_seconder_ratio"] == 0.8


def test_post_filter_ignores_fewer_than_minimum_motions():
    assert detect_procedural_dump(_dump(n=99)) is None


@pytest.mark.parametrize("kwargs", [
    {"accept_n": 79},
    {"pma_n": 79},
    {"proposer_n": 79},
    {"seconder_n": 79},
])
def test_post_filter_requires_all_thresholds(kwargs):
    assert detect_procedural_dump(_dump(**kwargs)) is None


def test_post_filter_ignores_legitimate_plan_meeting():
    # Many substantive "That the Council..." motions, no procedural accepts.
    motions = [
        _motion(i, accept=False, pma=False, proposer=f"Cllr. {i}")
        for i in range(115)
    ]
    assert detect_procedural_dump(motions) is None


def test_post_filter_ignores_single_seconder_without_accept_ce():
    motions = [
        _motion(i, accept=False, pma=True, proposer=f"Cllr. {i}",
                seconder="Cllr. Sammon")
        for i in range(113)
    ]
    assert detect_procedural_dump(motions) is None


def test_post_filter_ignores_missing_actors():
    motions = [
        _motion(i, accept=True, pma=True, proposer=None, seconder=None)
        for i in range(100)
    ]
    assert detect_procedural_dump(motions) is None


def test_post_filter_ignores_empty_list():
    assert detect_procedural_dump([]) is None

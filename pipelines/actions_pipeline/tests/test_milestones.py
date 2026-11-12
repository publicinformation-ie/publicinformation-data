import pytest

from milestones import Milestone, MilestoneRoundTripFailed, split_milestones


def tuples(text):
    return [(m.due_label, m.due_start, m.due_end, m.due_precision, m.text)
            for m in split_milestones(text)]


def test_action_4():
    text = ("Q1 2029 – Convene working group to review contract. Q3 2030 – "
            "Secure Ministerial sign-off on new contract in advance of the new "
            "contract period in 2031.")
    assert tuples(text) == [
        ("Q1 2029", "2029-01-01", "2029-03-31", "quarter",
         "Convene working group to review contract."),
        ("Q3 2030", "2030-07-01", "2030-09-30", "quarter",
         "Secure Ministerial sign-off on new contract in advance of the new "
         "contract period in 2031."),
    ]


def test_year_colon_format():
    got = tuples("2022: Report developed. 2023: First report published and "
                 "annual reports published thereafter.")
    assert [g[0] for g in got] == ["2022", "2023"]
    assert {g[3] for g in got} == {"year"}
    assert got[0][4] == "Report developed."


def test_immac_range_is_not_a_marker():
    got = tuples("2024: Existing IMMAC reviewed. 2025: IMMAC 2025-2030 agreed.")
    assert len(got) == 2
    assert got[1][4] == "IMMAC 2025-2030 agreed."


def test_marker_without_preceding_full_stop():
    got = tuples("Q1 2026 – Tender issued. Q4 2026 – New service roll-out "
                 "commenced Q2 2027 – Contract renewal reviewed.")
    assert [g[0] for g in got] == ["Q1 2026", "Q4 2026", "Q2 2027"]


def test_prose_date_is_not_a_marker():
    got = tuples("Deliver the report by Q4 2030.")
    assert got == [("", None, None, None, "Deliver the report by Q4 2030.")]


def test_lead_in_text_before_first_marker():
    got = tuples("Kick-off. Q2 2026 – Procurement.")
    assert got[0] == ("", None, None, None, "Kick-off.")
    assert got[1][0] == "Q2 2026"


def test_bare_year_dash_marker():
    assert tuples("2028 – Public Consultation held.") == [
        ("2028", "2028-01-01", "2028-12-31", "year", "Public Consultation held.")]
    got = tuples("Q1 2027 – Review. 2028 onwards – Monitor compliance.")
    assert got[0][0] == "Q1 2027"
    assert got[1] == ("2028 onwards", "2028-01-01", "2028-12-31", "year",
                      "Monitor compliance.")


def test_marker_labels_are_canonicalised():
    got = tuples("Q 4 2024")
    assert got == [("Q4 2024", "2024-10-01", "2024-12-31", "quarter", "")]


def test_undated_single():
    (m,) = split_milestones("Ongoing review of the programme.")
    assert m.due_label == "" and m.due_precision is None


def test_interim_target_marker():
    got = tuples("2027 interim target - 150km of new/ upgraded walking and "
                 "cycling infrastructure in the five cities.")
    assert len(got) == 1 and got[0][0] == "2027" and got[0][3] == "year"


def test_date_only_lists():
    assert [g[0] for g in tuples("Q2 2023; Q4 2023")] == ["Q2 2023", "Q4 2023"]
    assert [g[0] for g in tuples("Q1 2023 Q4 2023")] == ["Q1 2023", "Q4 2023"]
    assert [g[0] for g in tuples("Q1 2023,")] == ["Q1 2023"]
    assert {g[4] for g in tuples("Q2 2023; Q4 2023")} == {""}


@pytest.mark.parametrize("text", ["", None, "   ", " ", " "])
def test_empty_inputs_yield_nothing(text):
    assert split_milestones(text) == []


def test_ordinals_are_one_based_and_contiguous():
    got = split_milestones("2022: a. 2023: b. 2024: c.")
    assert [m.ordinal for m in got] == [1, 2, 3]


def test_pieces_partition_the_text():
    text = "Lead. Q1 2027 – Review. 2028 onwards – Monitor. Done."
    normalised = " ".join(text.split())
    assert " ".join(m.raw for m in split_milestones(text)) == normalised


def test_split_is_deterministic():
    text = "2022: a. 2023: b."
    assert split_milestones(text) == split_milestones(text)


def test_round_trip_failure_is_raised(monkeypatch):
    import milestones
    monkeypatch.setattr(milestones, "_markers", lambda t: [(5, 3, "", None)])
    with pytest.raises(MilestoneRoundTripFailed):
        split_milestones("abcdefghij")

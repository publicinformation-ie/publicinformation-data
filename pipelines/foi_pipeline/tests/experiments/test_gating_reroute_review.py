import pytest

from experiments.gating import reroute_review as rr


def test_parse_picks_overrides_and_validates():
    assert rr.parse_picks(None) == rr.PICKS
    assert rr.parse_picks(["1210=force:pdfplumber"])[1210] == "force:pdfplumber"
    with pytest.raises(ValueError):
        rr.parse_picks(["1210=bogus"])
    with pytest.raises(ValueError):
        rr.parse_picks(["x=docling"])


def test_picks_cover_the_five_rejected_bodies():
    assert set(rr.PICKS) == {1210, 1508, 1235, 1655, 1244}
    assert all(v in rr.CANDIDATES for v in rr.PICKS.values())


def test_fill_shares():
    recs = [{"foi_reference_id": "a", "date_received": None}, {"foi_reference_id": "", "date_received": "x"}]
    f = rr.fill_shares(recs)
    assert f["foi_reference_id"] == 0.5 and f["date_received"] == 0.5 and f["decision_status"] == 0.0
    assert rr.fill_shares([])["foi_reference_id"] == 0.0


def test_merge_record_joins_continuation_rows():
    rows = [["H1", "H2"], ["a", "b"], ["", "more"], ["", "again"], ["c", "d"]]
    j, merged = rr.merge_record(rows, 1)
    assert j == 4 and merged == ["a", "b more again"]
    assert rr.merge_record(rows, 4) == (5, ["c", "d"])

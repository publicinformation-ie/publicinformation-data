import json

from steps.match_public_bodies.process import process


# (public_body_id, name, normalised_name) — the shape load_candidates returns.
CANDIDATES = [
    (1608, "Office of the Revenue Commissioners", "office of the revenue commissioners"),
    (1014, "An Garda Síochána", "an garda síochána"),
    (1104, "Adoption Authority of Ireland", "adoption authority of ireland"),
]


def _input(*records):
    return {"metadata": {}, "results": list(records)}


def test_process_matches_a_name_differing_only_in_capitalisation(tmp_path, make_writer):
    writer = make_writer("match_public_bodies")
    data = _input({
        "foigovie_slug": "adoption-authority-of-ireland",
        "foigovie_name": "Adoption Authority Of Ireland",
    })
    match_log = process(data, CANDIDATES, writer)
    writer.finalize()
    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert results[0]["public_body_id"] == 1104
    assert match_log[0]["match_score"] >= 0.90


def test_process_leaves_public_body_id_null_below_threshold(tmp_path, make_writer):
    """foi.gov.ie writes names without fadas. normalise() does not strip
    diacritics, so "An Garda Siochana" scores ~0.88 against "An Garda Síochána"
    and is correctly left for override.json to resolve."""
    writer = make_writer("match_public_bodies")
    data = _input({"foigovie_slug": "an-garda-siochana", "foigovie_name": "An Garda Siochana"})
    match_log = process(data, CANDIDATES, writer)
    writer.finalize()
    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert results[0]["public_body_id"] is None
    assert match_log[0]["match_score"] < 0.90


def test_process_preserves_every_upstream_field(tmp_path, make_writer):
    writer = make_writer("match_public_bodies")
    data = _input({
        "foigovie_slug": "adoption-authority-of-ireland",
        "foigovie_name": "Adoption Authority of Ireland",
        "foigovie_email": "corporate@aai.gov.ie",
        "foigovie_phone": None,
    })
    process(data, CANDIDATES, writer)
    writer.finalize()
    record = json.loads((tmp_path / "output.json").read_text())["results"][0]
    assert record["foigovie_email"] == "corporate@aai.gov.ie"
    assert record["foigovie_phone"] is None


def test_match_log_records_unmatched_entries_too(tmp_path, make_writer):
    writer = make_writer("match_public_bodies")
    data = _input({"foigovie_slug": "totally-unknown-body", "foigovie_name": "Totally Unknown Body"})
    match_log = process(data, CANDIDATES, writer)
    assert len(match_log) == 1
    assert match_log[0]["matched_public_body_id"] is None
    assert match_log[0]["foigovie_slug"] == "totally-unknown-body"


def test_process_skips_already_processed_slugs(tmp_path, make_writer):
    writer = make_writer("match_public_bodies")
    writer.append([{"foigovie_slug": "adoption-authority-of-ireland", "public_body_id": 1104}])
    data = _input({
        "foigovie_slug": "adoption-authority-of-ireland",
        "foigovie_name": "Adoption Authority of Ireland",
    })
    match_log = process(data, CANDIDATES, writer)
    assert match_log == []

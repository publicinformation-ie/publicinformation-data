from steps.match_public_bodies.process import (
    build_index, local_authority_name, match_key, process, resolve,
)

CANDS = [
    {"public_body_id": 1, "name": "Leitrim County Council"},
    {"public_body_id": 2, "name": "Limerick City and County Council"},
    {"public_body_id": 3, "name": "Cork City Council"},
    {"public_body_id": 4, "name": "Bord Bia"},
    {"public_body_id": 5, "name": "Crawford Art Gallery"},
    {"public_body_id": 6, "name": "Twin Body"},
    {"public_body_id": 7, "name": "The Twin Body (Ireland)"},
    {"public_body_id": 8, "name": "Coimisiún na Meán"},
]
INDEX = build_index(CANDS)


def test_match_key_folds_case_accents_ampersand_and_the():
    assert match_key("The Coimisiún Na Meán") == match_key("coimisiun na mean")
    assert match_key("Rural & Community") == match_key("rural and community")
    assert match_key("Foo (Bar) Ltd.") == "foo ltd"


def test_local_authority_inversion():
    assert local_authority_name("County Council - Leitrim") == "Leitrim County Council"
    assert local_authority_name("City Council - Cork") == "Cork City Council"
    assert local_authority_name("City & County Council - Limerick") == "Limerick City and County Council"
    assert local_authority_name("Bord Bia") is None


def test_exact_and_rule_matches():
    assert resolve("Bord Bia", INDEX) == (4, "exact", "exact_name")
    assert resolve("County Council - Leitrim", INDEX) == (1, "rule", "local_authority_rule")
    assert resolve("City & County Council - Limerick", INDEX)[0] == 2


def test_near_miss_is_never_auto_matched():
    # 'Crawford Gallery' is close to 'Crawford Art Gallery' but must be a human decision
    assert resolve("Crawford Gallery", INDEX) == (None, "unmatched", None)


def test_ambiguous_key_does_not_pick_one():
    assert resolve("Twin Body", INDEX)[:2] == (None, "ambiguous")


def test_unknown_local_authority_stays_unmatched():
    assert resolve("County Council - Dun Laoire", INDEX)[0] is None


def test_process_logs_suggestions_for_unmatched_only():
    recs = [{"source_key": "k1", "source_name": "Bord Bia"},
            {"source_key": "k2", "source_name": "Crawford Gallery"}]
    out, log = process(recs, CANDS)
    assert [r["public_body_id"] for r in out] == [4, None]
    assert [e["source_key"] for e in log] == ["k2"]
    assert log[0]["suggestions"][0]["public_body_id"] == 5

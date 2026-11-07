from lib.text_repairs import REPAIRS, find_repairs, repair_text


def test_a_split_word_is_joined():
    assert repair_text("annual reports published thereafet r") == (
        "annual reports published thereafter")


def test_a_transposition_is_repaired():
    assert repair_text("Kent Statoi n Through Platof rm") == (
        "Kent Station Through Platform")


def test_the_longest_pattern_wins():
    assert repair_text("ofef ring a bike") == "offering a bike"


def test_capitalisation_is_preserved():
    assert repair_text("The SPSV Advisory Commitet e met") == (
        "The SPSV Advisory Committee met")


def test_a_legitimate_phrase_is_untouched():
    assert repair_text("signed of later and will be reviewed") == (
        "signed of later and will be reviewed")


def test_a_url_is_untouched():
    assert repair_text("see https://example.ie/staf.f") == (
        "see https://example.ie/staf.f")


def test_find_repairs_reports_offsets():
    found = find_repairs("A betet r plan")
    assert found[0]["before"] == "betet r"
    assert found[0]["after"] == "better"


def test_the_mapping_has_no_duplicate_sources():
    sources = [before.lower() for before, _ in REPAIRS]
    assert len(sources) == len(set(sources))

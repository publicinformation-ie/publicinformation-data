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


def test_url_fragment_with_percent_encoding_untouched():
    frag = "text=The%20guiding,a betet r%2C cleaner"
    assert repair_text(frag) == frag
    assert repair_text("a betet r plan") == "a better plan"


def test_replacement_casing_follows_match():
    assert repair_text("the statoi n") == "the station"
    assert repair_text("Statoi n") == "Station"
    assert repair_text("STATOI N") == "STATION"
    assert repair_text("COMMITET E") == "COMMITTEE"
    assert repair_text("a commitet e met") == "a committee met"


def test_construction_and_evaluation_repaired():
    assert repair_text("Q4 2027 – Constructoi n commenced") == (
        "Q4 2027 – Construction commenced")
    assert repair_text("Q1 2027 – Evaluatoi n of pilot") == (
        "Q1 2027 – Evaluation of pilot")

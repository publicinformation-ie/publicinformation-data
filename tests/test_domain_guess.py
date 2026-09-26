from lib.domain_guess import guess_domains


def test_acronym_first():
    guesses = guess_domains("Health and Safety Authority")
    assert guesses[0] == "https://hsa.ie/"
    assert "https://healthandsafetyauthority.ie/" in guesses


def test_legal_suffix_stripped():
    guesses = guess_domains("Meath Arts Centre DAC")
    assert "https://meathartscentre.ie/" in guesses
    assert not any("dac" in g for g in guesses)


def test_fadas_are_folded_to_ascii():
    guesses = guess_domains("Bord na Móna PLC")
    assert "https://bordnamona.ie/" in guesses


def test_ampersand_and_parentheses():
    guesses = guess_domains("Arts & Culture (Kerry) CLG")
    assert "https://artsandculture.ie/" in guesses
    assert not any("kerry" in g for g in guesses)


def test_cap_and_no_duplicates():
    guesses = guess_domains("Irish Aviation Authority")
    assert len(guesses) <= 6
    assert len(guesses) == len(set(guesses))


def test_empty_and_short_names():
    assert guess_domains("") == []
    # single-word names: no acronym (it would equal the slug), slug min length 3
    assert guess_domains("ESB") == ["https://esb.ie/", "https://esb.com/", "https://esb.org/"]

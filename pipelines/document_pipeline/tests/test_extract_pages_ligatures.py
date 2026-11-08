import pytest

from steps.extract_pages.ligatures import repair_ligature_widths


def _char(text, x0, x1, top=390.58, font="Lato-Regular", upright=True):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "fontname": font,
            "upright": upright, "width": x1 - x0, "adv": x1 - x0}


def _read(chars):
    return "".join(c["text"] for c in sorted(chars, key=lambda c: c["x0"]))


def test_kerned_tt_ligature_reads_in_order():          # real values from SMP p11
    chars = [_char("b",364.204,369.804), _char("a",369.804,374.774),
             _char("t",374.709,381.539), _char("e",381.514,386.794),
             _char("t",381.539,381.539), _char("r",386.794,390.434),
             _char("y",390.434,395.584)]
    assert _read(chars) == "batetry"
    assert repair_ligature_widths(chars) == 1
    assert _read(chars) == "battery"
    assert chars[2]["x1"] == pytest.approx(378.124) and chars[4]["x0"] == pytest.approx(378.124)
    assert chars[4]["width"] == chars[4]["adv"] == pytest.approx(3.415)


def test_three_component_ligature_splits_in_thirds():
    chars = [_char("f",10,19), _char("f",19,19), _char("i",19,19), _char("x",19,24)]
    assert repair_ligature_widths(chars) == 1
    assert [round(c["x0"],2) for c in chars[:3]] == [10, 13, 16]
    assert _read(chars) == "ffix"


def test_punctuation_kerned_into_ligature_sorts_after_it():   # "staf.f"
    chars = [_char("a",0,5), _char("f",5,12), _char(".",11.9,14), _char("f",12,12)]
    repair_ligature_widths(chars)
    assert _read(chars) == "aff."


def test_zero_width_combining_mark_stays_after_base():
    chars = [_char("e",0,5), _char("́",5,5), _char("x",5,9)]
    repair_ligature_widths(chars)
    assert _read(chars) == "éx"


def test_zero_width_char_without_matching_base_is_untouched():
    chars = [_char("a",0,5), _char("b",7,7)]                       # gap, no base
    other = [_char("a",0,5,font="Other"), _char("b",5,5)]          # font differs
    line = [_char("a",0,5,top=1), _char("b",5,5,top=2)]            # line differs
    for cs in (chars, other, line):
        before = [dict(c) for c in cs]
        assert repair_ligature_widths(cs) == 0 and cs == before


def test_non_upright_chars_are_untouched():
    chars = [_char("t",0,6,upright=False), _char("t",6,6,upright=False)]
    before = [dict(c) for c in chars]
    assert repair_ligature_widths(chars) == 0 and chars == before


def test_whitespace_zero_width_chars_are_not_components():
    chars = [_char("a",0,5), _char(" ",5,5)]
    assert repair_ligature_widths(chars) == 0

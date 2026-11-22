"""Tests for gold chapter lists: loading, validation and consistency checks."""
import json

import pytest

from steps.detect_structure.eval import gold


def _page(number, *lines):
    return {"number": number, "width": 595.0, "height": 842.0,
            "spans": [{"text": line, "font": "Helvetica", "size": 12.0,
                       "bbox": [72.0, 100.0 + i * 20, 500.0, 112.0 + i * 20],
                       "block": i, "line": 0, "span": 0}
                      for i, line in enumerate(lines)]}


def _gold(**overrides):
    data = {
        "doc_slug": "fixture-doc",
        "pdf_sha256": "a" * 64,
        "toc_pdf_pages": [3],
        "annotator": "test",
        "annotated_on": "2026-11-22",
        "reviewed": True,
        "notes": "",
        "chapters": [
            {"title": "Introduction", "printed_page": "1", "pdf_page": 7},
            {"title": "Conclusions", "printed_page": "2", "pdf_page": 8},
        ],
    }
    data.update(overrides)
    return data


def _write_gold(dirpath, data, name=None):
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / f"{name or data.get('doc_slug', 'fixture-doc')}.json"
    path.write_text(json.dumps(data), encoding="utf-8")


def _doc(data, pages=None):
    return gold.GoldDocument(
        doc_slug=data["doc_slug"], pdf_sha256=data["pdf_sha256"],
        toc_pdf_pages=data["toc_pdf_pages"], reviewed=True,
        chapters=[dict(c) for c in data["chapters"]],
        annotator=data["annotator"], annotated_on=data["annotated_on"],
        notes=data["notes"])


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def test_valid_gold_has_no_errors():
    assert gold.validate_gold(_gold(), expected_slug="fixture-doc") == []


def test_missing_pdf_sha256_is_malformed(tmp_path):
    data = _gold()
    del data["pdf_sha256"]
    _write_gold(tmp_path, data)
    loaded = gold.load_gold(tmp_path)

    assert loaded.documents == {}
    assert loaded.excluded == [{"doc_slug": "fixture-doc", "reason": "malformed gold file",
                                "detail": "missing required field 'pdf_sha256'"}]


def test_chapter_without_pdf_page_is_malformed():
    data = _gold()
    del data["chapters"][1]["pdf_page"]
    errors = gold.validate_gold(data)

    assert any("chapter 2" in error and "pdf_page" in error for error in errors)


def test_decreasing_pdf_page_is_malformed():
    data = _gold(chapters=[
        {"title": "Introduction", "printed_page": "1", "pdf_page": 9},
        {"title": "Conclusions", "printed_page": "2", "pdf_page": 8},
    ])
    errors = gold.validate_gold(data)

    assert any("before the previous chapter" in error for error in errors)


def test_unreviewed_draft_is_excluded(tmp_path):
    _write_gold(tmp_path, _gold(reviewed=False))
    loaded = gold.load_gold(tmp_path)

    assert loaded.documents == {}
    assert loaded.excluded[0]["reason"] == "unreviewed"


def test_no_toc_register_lists_document_as_unscorable(tmp_path):
    (tmp_path / "no_toc.json").write_text(json.dumps(
        {"letter-doc": "No contents page; a single two-page letter."}), encoding="utf-8")
    loaded = gold.load_gold(tmp_path)

    assert loaded.documents == {}
    assert loaded.excluded == [{"doc_slug": "letter-doc", "reason": "no printed TOC",
                                "detail": "No contents page; a single two-page letter."}]


def test_document_cannot_be_both_scored_and_no_toc(tmp_path):
    _write_gold(tmp_path, _gold())
    (tmp_path / "no_toc.json").write_text(json.dumps({"fixture-doc": "contradiction"}),
                                          encoding="utf-8")
    with pytest.raises(ValueError, match="both"):
        gold.load_gold(tmp_path)


def test_filename_must_match_doc_slug(tmp_path):
    _write_gold(tmp_path, _gold(), name="other-doc")
    loaded = gold.load_gold(tmp_path)

    assert loaded.documents == {}
    assert "does not match filename" in loaded.excluded[0]["detail"]


# --------------------------------------------------------------------------
# Consistency warnings
# --------------------------------------------------------------------------

def test_page_offset_jump_warns_and_still_scores(tmp_path):
    data = _gold(chapters=[
        {"title": "One", "printed_page": "1", "pdf_page": 7},
        {"title": "Two", "printed_page": "2", "pdf_page": 8},
        {"title": "Three", "printed_page": "3", "pdf_page": 9},
        {"title": "Four", "printed_page": "4", "pdf_page": 12},
    ])
    pages = [_page(number, title) for number, title in
             [(7, "One"), (8, "Two"), (9, "Three"), (12, "Four")]]
    warnings = gold.consistency_warnings(_doc(data), pages)

    assert len(warnings) == 1
    assert "offset changes from 6 to 8" in warnings[0]
    assert "'Four'" in warnings[0]


def test_offset_note_clears_the_warning():
    data = _gold(notes="A fold-out map before chapter 4 changes the offset.",
                 chapters=[
                     {"title": "One", "printed_page": "1", "pdf_page": 7},
                     {"title": "Two", "printed_page": "2", "pdf_page": 8},
                     {"title": "Four", "printed_page": "4", "pdf_page": 12},
                 ])
    pages = [_page(number, title) for number, title in
             [(7, "One"), (8, "Two"), (12, "Four")]]

    assert gold.consistency_warnings(_doc(data), pages) == []


def test_title_not_on_its_start_page_warns():
    data = _gold()
    pages = [_page(7, "Something else entirely"), _page(8, "Conclusions")]

    warnings = gold.consistency_warnings(_doc(data), pages)

    assert len(warnings) == 1
    assert "'Introduction'" in warnings[0]
    assert "PDF page 7" in warnings[0]


def test_title_is_found_through_a_leading_number_and_line_breaks():
    data = _gold(chapters=[{"title": "Long Term Strategic Issues for National Roads",
                            "printed_page": "3", "pdf_page": 9}])
    pages = [_page(9, "3 Long Term Strategic Issues", "for National Roads")]

    assert gold.consistency_warnings(_doc(data), pages) == []


def test_shared_start_page_warns_unless_noted():
    data = _gold(chapters=[
        {"title": "Introduction", "printed_page": "1", "pdf_page": 7},
        {"title": "Background", "printed_page": "1", "pdf_page": 7},
        {"title": "Conclusions", "printed_page": "2", "pdf_page": 8},
    ])
    pages = [_page(7, "Introduction Background"), _page(8, "Conclusions")]

    warnings = gold.consistency_warnings(_doc(data), pages)
    assert any("share PDF page 7" in warning for warning in warnings)

    data["notes"] = "Both openers are printed side by side on the same page."
    assert gold.consistency_warnings(_doc(data), pages) == []


def test_normalise_title_strips_numbers_but_not_words():
    assert gold.normalise_title("3 Long Term Strategic Issues") == \
        "long term strategic issues"
    assert gold.normalise_title("Appendix A National Policy Actions") == \
        "national policy actions"
    assert gold.normalise_title("Chapter 4: Implementation.") == "implementation"
    assert gold.normalise_title("Civil Rights and Equality") == "civil rights and equality"


def test_normalise_title_strips_decorative_toc_labels():
    # A bar between a chapter label and its title is design, not text.
    assert gold.normalise_title("Chapter 1 | Purpose") == "purpose"
    assert gold.normalise_title("Appendix C | Mitigation and Monitoring Measures") == \
        "mitigation and monitoring measures"
    # A short all-caps sector code is the chapter's number.
    assert gold.normalise_title("RE | Research and Innovation") == \
        "research and innovation"
    assert gold.normalise_title("| The Railway Today") == "the railway today"

import json
from pathlib import Path

from steps.extract_pages.process import process

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "fixture.pdf"


def _upstream(tmp_path):
    return [{"doc_slug": "fixture-doc", "title": "Fixture Transport Strategy",
             "url": "https://example.org/fixture.pdf", "page_count": 4,
             "pdf_path": str(FIXTURE_PDF)}]


def test_process_writes_one_page_file_per_page(tmp_path, make_writer):
    writer = make_writer("extract_pages")
    process(_upstream(tmp_path), tmp_path, tmp_path, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert len(record["pages"]) == 4
    for page in record["pages"]:
        assert (tmp_path / page["file"]).exists()


def test_page_files_carry_spans_with_font_and_size(tmp_path, make_writer):
    writer = make_writer("extract_pages")
    process(_upstream(tmp_path), tmp_path, tmp_path, writer)

    page = json.loads((tmp_path / "pages" / "fixture-doc" / "002.json").read_text())
    assert page["spans"], "expected text spans on page 2"
    span = page["spans"][0]
    assert set(span) >= {"text", "font", "size", "bbox", "block", "line", "span"}
    assert len(span["bbox"]) == 4


def test_coordinates_are_rounded_to_two_places(tmp_path, make_writer):
    writer = make_writer("extract_pages")
    process(_upstream(tmp_path), tmp_path, tmp_path, writer)

    page = json.loads((tmp_path / "pages" / "fixture-doc" / "002.json").read_text())
    for value in page["spans"][0]["bbox"]:
        assert round(value, 2) == value


def test_the_outline_is_recorded_when_present(tmp_path, make_writer):
    writer = make_writer("extract_pages")
    process(_upstream(tmp_path), tmp_path, tmp_path, writer)

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert "outline" in record


def test_a_document_with_no_text_layer_is_skipped_with_an_error(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr("steps.extract_pages.process.extract_page",
                        lambda page, number: {"number": number, "width": 1.0,
                                              "height": 1.0, "rotation": 0,
                                              "spans": [], "drawings": [],
                                              "images": [], "tables": []})
    writer = make_writer("extract_pages")
    process(_upstream(tmp_path), tmp_path, tmp_path, writer)
    writer.finalize()

    assert json.loads((tmp_path / "output.json").read_text())["results"] == []
    (error,) = json.loads((tmp_path / "errors.json").read_text())
    assert error["error_type"] == "NoTextLayer"
    assert "scanned" in error["error_message"]

import json
from pathlib import Path

from lib.file_utils import IncrementalWriter
from steps.detect_structure.process import Line
from steps.extract_figures import process as extract_figures_process
from steps.extract_figures.process import (
    CAPTION_RE,
    CLUSTER_GAP,
    MIN_AREA_FRACTION,
    area,
    cluster_boxes,
    filter_clusters,
    find_caption,
    is_page_furniture,
    is_prose,
    onpage_fraction,
    process,
)
from steps.extract_pages.process import process as extract_pages_process

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "fixture.pdf"

PAGE_W, PAGE_H = 595.0, 842.0
PAGE_AREA = PAGE_W * PAGE_H


def line(text, x0=72.0, y0=100.0, size=10.0, font="Helvetica", page=3):
    return Line(text=text, size=size, font=font,
                bbox=(x0, y0, x0 + 6.0 * len(text), y0 + size),
                block=0, index=0, page=page)


def write_upstream(tmp_path, pages, doc_slug="fixture-doc"):
    """Lay out an extract_pages step directory the way that step writes it."""
    upstream = tmp_path / "extract_pages"
    (upstream / "pages" / doc_slug).mkdir(parents=True, exist_ok=True)
    index = []
    for record in pages:
        relative = f"pages/{doc_slug}/{record['number']:03d}.json"
        (upstream / relative).write_text(json.dumps(record), encoding="utf-8")
        index.append({"number": record["number"], "file": relative,
                      "width": record["width"], "height": record["height"],
                      "rotation": record["rotation"], "span_count": len(record["spans"])})
    return upstream, [{"doc_slug": doc_slug, "doc_title": "Fixture", "page_count": len(pages),
                       "outline": [], "pages": index}]


def page(number=3, spans=None, drawings=None, images=None, tables=None):
    return {"number": number, "width": PAGE_W, "height": PAGE_H, "rotation": 0,
            "spans": spans or [], "drawings": drawings or [],
            "images": images or [], "tables": tables or []}


def writer_for(path):
    return IncrementalWriter(path, "extract_figures", key_field="doc_slug", force=True)


# --- clustering ------------------------------------------------------------

def test_boxes_within_the_gap_merge_and_boxes_beyond_it_stay_separate():
    near_box = (77.0, 100.0, 120.0, 200.0)      # 5pt to the right of the anchor
    far_box = (92.0, 100.0, 135.0, 200.0)       # 20pt to the right of the anchor
    anchor = (20.0, 100.0, 72.0, 200.0)

    assert cluster_boxes([anchor, near_box], gap=CLUSTER_GAP) == [(20.0, 100.0, 120.0, 200.0)]
    assert sorted(cluster_boxes([anchor, far_box], gap=CLUSTER_GAP)) == [anchor, far_box]


def test_clustering_reaches_a_fixpoint_through_a_chain_of_overlaps():
    """A overlaps B and B overlaps C, but A and C do not touch: repeated passes
    must still fold all three into one cluster."""
    a = (0.0, 0.0, 100.0, 20.0)
    b = (90.0, 0.0, 190.0, 20.0)
    c = (180.0, 0.0, 280.0, 20.0)
    far = (400.0, 400.0, 440.0, 440.0)

    clusters = cluster_boxes([a, c, b, far], gap=CLUSTER_GAP)

    assert sorted(clusters) == [(0.0, 0.0, 280.0, 20.0), far]


# --- furniture and size filtering ------------------------------------------

def test_a_full_page_background_rectangle_is_furniture():
    assert is_page_furniture((0.0, 0.0, PAGE_W, PAGE_H), PAGE_W, PAGE_H, [])


def test_a_two_point_high_rule_is_furniture():
    assert is_page_furniture((72.0, 100.0, 523.0, 102.0), PAGE_W, PAGE_H, [])


def test_a_drawing_inside_a_detected_table_is_furniture():
    table = (72.0, 160.0, 400.0, 280.0)
    assert is_page_furniture((80.0, 170.0, 390.0, 200.0), PAGE_W, PAGE_H, [table])
    assert not is_page_furniture((80.0, 400.0, 390.0, 600.0), PAGE_W, PAGE_H, [table])


def test_a_box_mostly_off_the_page_edge_is_furniture():
    """Bleed art or a facing-page artifact positioned past the canvas: only a
    sliver of it overlaps this page, so it must not become a figure with a
    bogus (page, y) that corrupts section ownership downstream."""
    assert is_page_furniture((PAGE_W, -8.0, PAGE_W + 600.0, 260.0), PAGE_W, PAGE_H, [])


def test_a_box_entirely_off_the_page_is_furniture():
    assert is_page_furniture((-500.0, -500.0, -100.0, -100.0), PAGE_W, PAGE_H, [])


def test_a_box_straddling_the_page_edge_with_minority_onpage_is_furniture():
    """36% of the box sits on the visible canvas — under the 50% threshold —
    so it is treated as bleed even though it is not wholly off the page."""
    box = (PAGE_W - 18.0, 100.0, PAGE_W + 32.0, 200.0)
    assert onpage_fraction(box, PAGE_W, PAGE_H) < 0.5
    assert is_page_furniture(box, PAGE_W, PAGE_H, [])


def test_a_box_straddling_the_page_edge_with_majority_onpage_is_kept():
    """60% of the box sits on the visible canvas — over the 50% threshold —
    so a real figure that merely bleeds past the edge is not dropped."""
    box = (PAGE_W - 30.0, 100.0, PAGE_W + 20.0, 200.0)
    assert onpage_fraction(box, PAGE_W, PAGE_H) > 0.5
    assert not is_page_furniture(box, PAGE_W, PAGE_H, [])


def test_a_cluster_below_the_area_floor_is_dropped():
    icon = (72.0, 100.0, 160.0, 180.0)
    real = (72.0, 200.0, 400.0, 500.0)
    assert area(icon) / PAGE_AREA < MIN_AREA_FRACTION
    assert area(real) / PAGE_AREA > MIN_AREA_FRACTION

    assert filter_clusters([icon, real], PAGE_W, PAGE_H) == [real]


# --- prose rejection -------------------------------------------------------

def test_body_text_in_reading_flow_is_rejected_as_prose():
    box = (72.0, 100.0, 523.0, 220.0)
    body = [line("Walking is the most universally available mode of transport.",
                 y0=100.0 + i * 14.0) for i in range(6)]

    assert is_prose(box, body, body_size=10.0)


def test_small_labels_over_a_drawing_are_not_prose():
    """Map labels are text *inside* a figure. Rejecting them would delete every
    map in the document, so size alone must not be the discriminator."""
    box = (72.0, 100.0, 523.0, 400.0)
    labels = [line("Dublin", y0=120.0, size=7.0), line("Bray", y0=200.0, size=7.0),
              line("Swords", y0=300.0, size=7.0), line("Tallaght", y0=350.0, size=7.0),
              line("Howth", y0=380.0, size=7.0)]

    assert not is_prose(box, labels, body_size=10.0)


# --- captions --------------------------------------------------------------

def test_a_caption_below_the_cluster_is_matched():
    box = (72.0, 130.0, 320.0, 300.0)
    candidates = [line("Figure 1.1 A vector diagram", y0=305.0, size=9.0),
                  line("Body text that follows.", y0=360.0)]

    assert find_caption(box, candidates) == "Figure 1.1 A vector diagram"


def test_a_caption_above_the_cluster_is_matched_when_none_is_below():
    box = (72.0, 200.0, 320.0, 400.0)
    candidates = [line("Table 2.1 Mode share", y0=175.0, size=9.0)]

    assert find_caption(box, candidates) == "Table 2.1 Mode share"


def test_the_caption_regex_rejects_a_sentence_that_merely_starts_with_figure():
    assert CAPTION_RE.match("Figure 1.1 A vector diagram")
    assert not CAPTION_RE.match("Figures are shown below.")


def test_no_caption_yields_a_fallback_title_and_a_missing_caption_error(tmp_path):
    upstream, records = write_upstream(
        tmp_path, [page(number=3, drawings=[{"bbox": [72.0, 130.0, 320.0, 300.0]}])])
    step_dir = tmp_path / "extract_figures"
    step_dir.mkdir()
    writer = writer_for(step_dir / "output.json")

    process(records, upstream, {"fixture-doc": FIXTURE_PDF}, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((step_dir / "output.json").read_text())["results"]
    (figure,) = record["figures"]
    assert figure["caption"] == "Figure from page 3"
    assert figure["alt"] == "Figure from page 3"

    errors = json.loads((step_dir / "errors.json").read_text())
    assert [e["error_type"] for e in errors] == ["MissingCaption"]
    assert errors[0]["context"]["figure_id"] == figure["id"]


# --- failures are isolated, per figure and per document --------------------

def test_one_unrenderable_figure_does_not_prevent_the_others(tmp_path, monkeypatch):
    """A cluster that will not rasterise costs its own record and nothing else."""
    upstream, records = write_upstream(tmp_path, [page(
        number=3,
        spans=[{"text": "Figure 1.1 A vector diagram", "font": "Helvetica", "size": 9.0,
                "bbox": [72.0, 305.0, 183.0, 317.0], "block": 0, "line": 0, "span": 0}],
        drawings=[{"bbox": [72.0, 130.0, 320.0, 300.0]},
                  {"bbox": [72.0, 350.0, 300.0, 480.0]}])])
    step_dir = tmp_path / "extract_figures"
    step_dir.mkdir()
    writer = writer_for(step_dir / "output.json")

    real_render = extract_figures_process.render

    def selective(pdf_page, box, target):
        if target.name == "p003-f02.webp":
            raise RuntimeError("cannot rasterise")
        return real_render(pdf_page, box, target)

    monkeypatch.setattr(extract_figures_process, "render", selective)
    process(records, upstream, {"fixture-doc": FIXTURE_PDF}, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((step_dir / "output.json").read_text())["results"]
    assert [f["id"] for f in record["figures"]] == ["p003-f01"]
    assert (step_dir / "assets" / "fixture-doc" / "p003-f01.webp").exists()

    errors = json.loads((step_dir / "errors.json").read_text())
    assert [e["error_type"] for e in errors] == ["FigureRenderFailed"]
    assert errors[0]["context"]["figure_id"] == "p003-f02"


def test_one_failing_document_does_not_prevent_the_others(tmp_path):
    """An unopenable PDF is one document's problem, not the whole run's."""
    upstream, records = write_upstream(
        tmp_path, [page(number=3, drawings=[{"bbox": [72.0, 130.0, 320.0, 300.0]}])])
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf at all")
    records = [{**records[0], "doc_slug": "broken-doc"}, records[0]]

    step_dir = tmp_path / "extract_figures"
    step_dir.mkdir()
    writer = writer_for(step_dir / "output.json")

    process(records, upstream, {"broken-doc": broken, "fixture-doc": FIXTURE_PDF},
            step_dir, writer)
    writer.finalize()

    results = json.loads((step_dir / "output.json").read_text())["results"]
    assert [r["doc_slug"] for r in results] == ["fixture-doc"]

    errors = json.loads((step_dir / "errors.json").read_text())
    failures = [e for e in errors if e["error_type"] == "DocumentFigureExtractionFailed"]
    assert [e["context"]["doc_slug"] for e in failures] == ["broken-doc"]
    # Not marked processed, so a later run retries it.
    assert "broken-doc" not in writer.processed_keys


def test_a_page_missing_from_the_pdf_is_a_document_error_not_a_crash(tmp_path):
    """extract_pages recorded more pages than the PDF has — the recurring
    cross-step staleness failure. It must not abort the run."""
    upstream, records = write_upstream(
        tmp_path, [page(number=99, drawings=[{"bbox": [72.0, 130.0, 320.0, 300.0]}])])
    step_dir = tmp_path / "extract_figures"
    step_dir.mkdir()
    writer = writer_for(step_dir / "output.json")

    process(records, upstream, {"fixture-doc": FIXTURE_PDF}, step_dir, writer)
    writer.finalize()

    assert json.loads((step_dir / "output.json").read_text())["results"] == []
    errors = json.loads((step_dir / "errors.json").read_text())
    assert [e["error_type"] for e in errors] == ["DocumentFigureExtractionFailed"]


# --- integration against the real fixture PDF ------------------------------

def test_the_fixture_vector_figure_renders_to_a_non_empty_webp(tmp_path):
    pages_dir = tmp_path / "extract_pages"
    pages_dir.mkdir()
    pages_writer = IncrementalWriter(pages_dir / "output.json", "extract_pages",
                                     key_field="doc_slug", force=True)
    extract_pages_process(
        [{"doc_slug": "fixture-doc", "title": "Fixture Transport Strategy",
          "url": "https://example.org/fixture.pdf", "page_count": 4,
          "pdf_path": str(FIXTURE_PDF)}],
        tmp_path, pages_dir, pages_writer)
    pages_writer.finalize()
    records = json.loads((pages_dir / "output.json").read_text())["results"]

    step_dir = tmp_path / "extract_figures"
    step_dir.mkdir()
    writer = writer_for(step_dir / "output.json")
    process(records, pages_dir, {"fixture-doc": FIXTURE_PDF}, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((step_dir / "output.json").read_text())["results"]
    figures = [f for f in record["figures"] if f["kind"] == "figure"]

    assert [f["id"] for f in figures] == ["p003-f01", "p003-f02"]
    assert [f["caption"] for f in figures] == ["Figure 1.1 A vector diagram",
                                               "Figure 1.2 A raster image"]

    tables = [f for f in record["figures"] if f["kind"] == "table"]
    assert [(t["id"], t["page"]) for t in tables] == [("p004-t01", 4)]

    vector = figures[0]
    asset = step_dir / vector["asset"]
    assert vector["asset"] == "assets/fixture-doc/p003-f01.webp"
    assert asset.exists() and asset.stat().st_size > 200
    assert asset.read_bytes()[:4] == b"RIFF"
    assert vector["width"] > 0 and vector["height"] > 0

    sheet = (step_dir / "contact-sheets" / "fixture-doc.html").read_text(encoding="utf-8")
    assert "p003-f01.webp" in sheet
    assert "page 3" in sheet

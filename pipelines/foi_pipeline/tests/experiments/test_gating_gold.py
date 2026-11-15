import json

import pymupdf
import pytest

from experiments.gating import gold_tools as gt

DPI = 110
S = DPI / 72  # points -> pixels
COLX = [50, 150, 300]  # points
ROWH = 30
TOP = 50


def make_pdf(rows, extra=()):
    doc = pymupdf.open()
    page = doc.new_page()
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            page.insert_text((COLX[c] + 5, TOP + r * ROWH + 18), text, fontsize=9)
    for text, x, y in extra:
        page.insert_text((x, y), text, fontsize=9)
    return doc.tobytes()


def bounds_for(nrows, skip=(0,)):
    return {"dpi": DPI, "columns": ["Ref", "Date"],
            "pages": [{"page": 1, "x": [round(x * S) for x in COLX],
                       "y": [round((TOP + i * ROWH) * S) for i in range(nrows + 1)],
                       "skip_rows": list(skip)}]}


def test_gold_from_bounds_reads_text_layer_by_cell():
    data = make_pdf([["Ref", "Date"], ["FOI-001", "12/01/2023"], ["FOI-002", "15/01/2023"]])
    gold = gt.gold_from_bounds(data, bounds_for(3))
    assert gold["columns"] == ["Ref", "Date"]
    assert gold["rows"] == [["FOI-001", "12/01/2023"], ["FOI-002", "15/01/2023"]]
    assert {c["row"] for c in gold["cells"]} == {0, 1} and gold["cells"][0]["page"] == 1


def test_word_outside_all_cells_is_not_included():
    data = make_pdf([["Ref", "Date"], ["FOI-001", "12/01/2023"]], extra=[("STRAY", 400, 100)])
    gold = gt.gold_from_bounds(data, bounds_for(2))
    assert "STRAY" not in json.dumps(gold["rows"])


def test_skip_rows_excluded_and_first15_last5_kept():
    rows = [["Ref", "Date"]] + [[f"FOI-{i:03d}", "01/01/2023"] for i in range(30)]
    # 31 rows of 30pt would overflow the page; use two pages-worth via small row height
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=1200)
    for r, row in enumerate(rows):
        for c, t in enumerate(row):
            page.insert_text((COLX[c] + 5, TOP + r * 30 + 18), t, fontsize=9)
    gold = gt.gold_from_bounds(doc.tobytes(), bounds_for(31))
    refs = [r[0] for r in gold["rows"]]
    assert refs == [f"FOI-{i:03d}" for i in list(range(15)) + list(range(25, 30))]
    assert len(gold["cells"]) == 40


def test_cells_to_check_marks_disputed_and_adds_random():
    gold = {"columns": ["Ref", "Date"],
            "rows": [[f"FOI-{i:03d}", f"{i + 1:02d}/01/2023"] for i in range(10)]}
    good = [["Ref", "Date"]] + [list(r) for r in gold["rows"]]
    bad = [list(r) for r in good]
    bad[3][1] = "99/99/2023"
    out = gt.cells_to_check(gold, {"a": good, "b": bad}, seed="abc")
    disputed = [c for c in out if c["reason"] == "disputed"]
    assert [(c["row"], c["col"]) for c in disputed] == [(2, 1)]
    assert disputed[0]["values"]["b"] == "99/99/2023"
    assert len([c for c in out if c["reason"] == "random"]) == 10
    keys = [(c["row"], c["col"]) for c in out]
    assert len(keys) == len(set(keys))
    assert out == gt.cells_to_check(gold, {"a": good, "b": bad}, seed="abc")


def test_cells_to_check_caps_random_at_available_cells():
    gold = {"columns": ["Ref", "Date"], "rows": [["FOI-001", "01/01/2023"]]}
    out = gt.cells_to_check(gold, {"a": None}, seed="x")
    assert len(out) == 2 and {c["reason"] for c in out} == {"random"}


def test_save_gold_marks_provisional(tmp_path):
    status = tmp_path / "status.json"
    p = gt.save_gold("sha1", {"columns": ["A"], "rows": [["x"]], "cells": [1]},
                     gold_dir=tmp_path, status_path=status, cells_dir=tmp_path / "cells")
    assert json.loads(p.read_text()) == {"columns": ["A"], "rows": [["x"]]}
    assert json.loads(status.read_text()) == {"sha1": "provisional"}
    gt.mark_gold_checked("sha1", status_path=status)
    assert json.loads(status.read_text()) == {"sha1": "checked"}


def test_render_and_crop(tmp_path):
    data = make_pdf([["Ref", "Date"], ["FOI-001", "12/01/2023"]])
    pages = gt.render_pages(data, tmp_path / "p")
    assert [p.name for p in pages] == ["page-1.png"] and pages[0].stat().st_size > 0
    gold = gt.gold_from_bounds(data, bounds_for(2))
    out = gt.crop_cell(data, gold["cells"][0], tmp_path / "c.png")
    assert out.is_file()


def test_save_gold_refuses_existing_unless_forced(tmp_path):
    status = tmp_path / "status.json"
    cells = tmp_path / "cells"
    gold = {"columns": ["A"], "rows": [["x"]], "cells": [{"row": 0, "col": 0, "page": 1, "rect": [0, 0, 1, 1]}]}
    p = gt.save_gold("sha1", gold, gold_dir=tmp_path, status_path=status, cells_dir=cells)
    assert json.loads((cells / "sha1.json").read_text()) == gold["cells"]
    gt.mark_gold_checked("sha1", status_path=status)
    with pytest.raises(FileExistsError):
        gt.save_gold("sha1", {"columns": ["A"], "rows": [["y"]], "cells": []},
                     gold_dir=tmp_path, status_path=status, cells_dir=cells)
    assert json.loads(p.read_text())["rows"] == [["x"]]
    assert json.loads(status.read_text()) == {"sha1": "checked"}
    gt.save_gold("sha1", {"columns": ["A"], "rows": [["y"]], "cells": []},
                 gold_dir=tmp_path, status_path=status, cells_dir=cells, force=True)
    assert json.loads(p.read_text())["rows"] == [["y"]]
    assert json.loads(status.read_text()) == {"sha1": "provisional"}

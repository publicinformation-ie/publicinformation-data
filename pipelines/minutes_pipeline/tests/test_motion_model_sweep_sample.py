"""Tests for the motion-model-sweep sample freeze (Task 2).

Loads draw_sample from experiments/2026-10-07-motion-model-sweep/sample.py
via importlib: the experiment directory name contains dashes so it is not
importable with a plain `from ... import` (same loader pattern as the
2026-09-15 run_experiment.py `_load_approach` helper).
"""
import importlib.util
from pathlib import Path

_SAMPLE_PY = (Path(__file__).parent.parent / "experiments"
              / "2026-10-07-motion-model-sweep" / "sample.py")


def _load_sample_module():
    spec = importlib.util.spec_from_file_location("motion_sweep_sample", _SAMPLE_PY)
    assert spec is not None and spec.loader is not None, f"Cannot load {_SAMPLE_PY}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


draw_sample = _load_sample_module().draw_sample


def _text(chars):
    return "Motion discussion text. " * (chars // 24 + 1)


def _motion(i, j):
    return {"motion_text": f"Motion {i}-{j} that the council approves the works.",
            "proposer": f"Proposer {i}", "seconder": None,
            "status_label": "carried"}


def _record(i, **overrides):
    band = ["short", "medium", "long"][i % 3]
    chars = {"short": 2400, "medium": 14400, "long": 36000}[band]
    count = [0, 1, 3, 5][i % 4]
    rec = {"public_body_id": 1000 + i,
           "minutes_page_url": "https://example.ie/minutes",
           "file_url": f"https://example.ie/minutes/file{i:02d}.pdf",
           "text": _text(chars),
           "extractor": "tesseract" if i % 5 == 4 else "pdfplumber"}
    rec.update(overrides)
    return rec, count


_FIXTURE_RECORDS = []
_FIXTURE_COUNTS = {}
for _i in range(26):
    _rec, _n = _record(_i)
    _FIXTURE_RECORDS.append(_rec)
    _FIXTURE_COUNTS[_rec["file_url"]] = {
        "count": _n,
        "motions": [_motion(_i, _j) for _j in range(_n)],
    }

_SHORT_URL = "https://example.ie/minutes/short.pdf"
_FIXTURE_RECORDS.append(_record(100, file_url=_SHORT_URL)[0] | {"text": "too short"})
_FIXTURE_COUNTS[_SHORT_URL] = {"count": 0, "motions": []}
_FIXTURE_RECORDS.append({"file_url": "unknown", "text": _text(3000),
                         "extractor": "pdfplumber"})
_QUAR_URL = "https://example.ie/minutes/quarantined.pdf"
_FIXTURE_RECORDS.append(_record(101, file_url=_QUAR_URL)[0] | {"quarantined": True})
_FIXTURE_COUNTS[_QUAR_URL] = {"count": 2, "motions": [_motion(101, 0), _motion(101, 1)]}


def test_draw_is_seeded_and_stratified():
    out_a = draw_sample(_FIXTURE_RECORDS, _FIXTURE_COUNTS, seed=20261007)
    out_b = draw_sample(_FIXTURE_RECORDS, _FIXTURE_COUNTS, seed=20261007)
    assert [f["file_url"] for f in out_a] == [f["file_url"] for f in out_b]
    assert len(out_a) == 20
    assert sum(1 for f in out_a if f["old_motion_count"] == 0) >= 2
    assert {f["extractor"] for f in out_a} >= {"pdfplumber", "tesseract"}
    assert all(len((f["text"] or "").strip()) >= 200 for f in out_a)


def test_old_motions_frozen_and_unusable_skipped():
    out = draw_sample(_FIXTURE_RECORDS, _FIXTURE_COUNTS, seed=20261007)
    for f in out:
        frozen = _FIXTURE_COUNTS[f["file_url"]]
        assert f["old_motions"] == frozen["motions"]
        assert f["old_motion_count"] == frozen["count"]
    urls = {f["file_url"] for f in out}
    assert _SHORT_URL not in urls
    assert _QUAR_URL not in urls
    assert "unknown" not in urls

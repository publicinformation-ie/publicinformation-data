"""Unit tests for src/lib/ocr.py with pytesseract faked (no binary needed)."""
import sys
import types

import pytest

from lib import ocr


def _fake_pytesseract(monkeypatch, data, version="5.5.2"):
    module = types.ModuleType("pytesseract")
    module.Output = types.SimpleNamespace(DICT="dict")
    calls = []

    def image_to_data(image, lang=None, config=None, output_type=None):
        calls.append({"lang": lang, "config": config})
        return data

    module.image_to_data = image_to_data
    module.get_tesseract_version = lambda: f"{version}\n leptonica-1.87.0"
    monkeypatch.setitem(sys.modules, "pytesseract", module)
    return calls


DATA = {
    "text": ["", "Hello", " ", "world"],
    "conf": ["-1", "96", "-1", "80"],
    "left": [0, 300, 0, 600],
    "top": [0, 150, 0, 150],
    "width": [0, 150, 0, 300],
    "height": [0, 30, 0, 30],
    "block_num": [1, 1, 1, 1],
    "par_num": [1, 1, 1, 1],
    "line_num": [1, 1, 1, 1],
    "word_num": [0, 1, 0, 2],
}


def test_engine_string_names_version_language_psm_and_dpi(monkeypatch):
    _fake_pytesseract(monkeypatch, DATA)
    assert ocr.engine_string(psm=4) == "tesseract 5.5.2 lang=eng psm=4 dpi=300"


def test_words_in_points_scales_by_72_over_dpi():
    words = [{"text": "Hello", "conf": 96.0, "left": 300, "top": 150,
              "width": 150, "height": 30}]
    assert ocr.words_in_points(words) == [{
        "text": "Hello", "x0": 72.0, "x1": 108.0, "top": 36.0, "bottom": 43.2,
        "conf": 96.0, "line": 0,
    }]


def test_words_on_one_tesseract_line_share_a_line_id_even_when_the_scan_is_skewed():
    words = [
        {"text": "a", "conf": 90.0, "left": 0, "top": 100, "width": 10, "height": 20,
         "block": 1, "par": 1, "line": 1},
        {"text": "b", "conf": 90.0, "left": 100, "top": 140, "width": 10, "height": 20,
         "block": 1, "par": 1, "line": 1},          # 40 px lower: skewed scan
        {"text": "c", "conf": 90.0, "left": 0, "top": 200, "width": 10, "height": 20,
         "block": 1, "par": 1, "line": 2},
        {"text": "d", "conf": 90.0, "left": 0, "top": 300, "width": 10, "height": 20,
         "block": 2, "par": 1, "line": 1},
    ]
    assert [w["line"] for w in ocr.words_in_points(words)] == [0, 0, 1, 2]


def test_ocr_page_words_renders_recognises_and_scales(monkeypatch):
    calls = _fake_pytesseract(monkeypatch, DATA)

    class Pix:
        width, height, samples = 2, 2, bytes(12)

    class Page:
        dpi = None

        def get_pixmap(self, dpi):
            self.dpi = dpi
            return Pix()

    page = Page()
    words = ocr.ocr_page_words(page, psm=4)
    assert page.dpi == 300
    assert calls == [{"lang": "eng", "config": "--psm 4"}]
    assert [w["text"] for w in words] == ["Hello", "world"]
    assert words[1]["x0"] == 144.0 and words[1]["x1"] == 216.0


def test_mean_confidence_of_recognised_words(monkeypatch):
    _fake_pytesseract(monkeypatch, DATA)
    words = ocr.ocr_words(object())
    assert ocr.mean_confidence(words) == pytest.approx(88.0)
    assert ocr.mean_confidence([]) is None

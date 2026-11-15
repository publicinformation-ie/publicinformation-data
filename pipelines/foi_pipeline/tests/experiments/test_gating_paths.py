import hashlib
import json

from experiments.gating import paths


def test_pdf_bytes_reads_by_url_hash_and_never_downloads(tmp_path):
    url = "https://example.org/a.pdf"
    (tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.bytes").write_bytes(b"%PDF-x")
    assert paths.pdf_bytes(url, tmp_path) == b"%PDF-x"
    assert paths.pdf_bytes("https://example.org/other.pdf", tmp_path) is None


def test_content_sha():
    assert paths.content_sha(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_load_results_shapes(tmp_path):
    a, b, c, d = (tmp_path / n for n in "abcd")
    a.write_text(json.dumps({"results": [{"x": 1}]}))
    b.write_text(json.dumps([{"y": 2}]))
    c.write_text("")
    assert paths.load_results(a) == [{"x": 1}]
    assert paths.load_results(b) == [{"y": 2}]
    assert paths.load_results(c) == []
    assert paths.load_results(d) == []


def test_settings_and_constants():
    s = paths.settings()
    assert s["agreement_min"] == 0.90 and s["gold_min"] == 0.95
    assert paths.CACHE == paths.GATING / "cache"
    assert paths.STEPS == paths.FOI / "steps"

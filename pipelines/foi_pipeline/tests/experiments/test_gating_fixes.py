import json

import pytest

import experiments.gating.fixes as fixes_mod
from experiments.gating.extract_cache import get_rows
from experiments.gating.fixes import FAMILY, Fix, NotExtracted, get, family_of, register, REGISTRY
from experiments.gating.paths import content_sha
from steps.transform_disclosure_files.candidates import CANDIDATE_NAMES

URL = "https://x.test/a.pdf"
R = [["Ref", "Date"], ["1", "01/01/2020"]]


@pytest.fixture(autouse=True)
def _clean_registry():
    before = dict(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.update(before)


def test_register_rejects_duplicate_and_unknown_kind():
    register(Fix(name="t:one", kind="config", extract=lambda b, u: R))
    with pytest.raises(ValueError):
        register(Fix(name="t:one", kind="config", extract=lambda b, u: R))
    with pytest.raises(ValueError):
        register(Fix(name="t:two", kind="nonsense"))
    with pytest.raises(ValueError):
        register(Fix(name="t:three", kind="config", scope="weird"))
    with pytest.raises(KeyError) as e:
        get("missing")
    assert "current" in str(e.value)


def test_every_candidate_has_family_and_force_fix():
    for n in CANDIDATE_NAMES:
        assert n in FAMILY
        assert get(f"force:{n}").family == FAMILY[n]
        assert get(f"force:{n}").kind == "config"


def test_current_fix_returns_stored_rows_and_family(tmp_path):
    ex = get_rows(get("current"), URL, b"%PDF", {"rows": R, "pdf_extractor": "camelot_stream"}, tmp_path)
    assert ex.status == "ok" and ex.rows == R
    assert family_of(get("current"), {"pdf_extractor": "camelot_stream"}) == "camelot"
    assert list(tmp_path.iterdir()) == []


def test_extraction_is_cached_by_content_sha_and_version(tmp_path):
    calls = []

    def ex(b, u):
        calls.append(1)
        return R
    f = Fix(name="gate:x+y", kind="candidate", extract=ex)
    assert get_rows(f, URL, b"abc", {}, tmp_path).rows == R
    assert get_rows(f, URL, b"abc", {}, tmp_path).rows == R
    assert len(calls) == 1
    assert (tmp_path / "gate_x_y@1" / f"{content_sha(b'abc')}.json").is_file()
    get_rows(Fix(name="gate:x+y", kind="candidate", extract=ex, version="2"), URL, b"abc", {}, tmp_path)
    assert len(calls) == 2


def test_no_table_and_error_are_recorded_not_raised(tmp_path):
    def boom(b, u):
        raise RuntimeError("boom")
    n = get_rows(Fix(name="n", kind="config", extract=lambda b, u: None), URL, b"a", {}, tmp_path)
    assert n.status == "no_table" and n.rows is None
    e = get_rows(Fix(name="e", kind="config", extract=boom), URL, b"a", {}, tmp_path)
    assert e.status == "error" and e.error == "boom"
    again = get_rows(Fix(name="e", kind="config", extract=lambda b, u: R), URL, b"a", {}, tmp_path)
    assert again.status == "error"  # cached


def test_docling_fix_without_pages_file_is_not_extracted_and_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(fixes_mod, "DOCLING_PAGES", tmp_path / "pages")
    ex = get_rows(get("docling"), URL, b"abc", {}, tmp_path / "c")
    assert ex.status == "not_extracted" and ex.rows is None
    assert not (tmp_path / "c").exists() or not list((tmp_path / "c").rglob("*.json"))


def test_docling_fix_reads_pages_file(tmp_path, monkeypatch):
    pages = tmp_path / "pages"
    pages.mkdir()
    monkeypatch.setattr(fixes_mod, "DOCLING_PAGES", pages)
    (pages / f"{content_sha(b'abc')}.json").write_text(json.dumps({"pages": [R]}))
    ex = get_rows(get("docling"), URL, b"abc", {}, tmp_path / "c")
    assert ex.status == "ok" and ["1", "01/01/2020"] in ex.rows
    (pages / f"{content_sha(b'def')}.json").write_text(json.dumps({"pages": [[]]}))
    assert get_rows(get("docling"), URL, b"def", {}, tmp_path / "c").status == "no_table"
    with pytest.raises(NotExtracted):
        get("docling").extract(b"zzz", URL)


def test_rows_from_uses_other_fix_rows(tmp_path):
    f = register(Fix(name="gate:z", kind="gate", rows_from="current", scope="global"))
    ex = get_rows(f, URL, b"a", {"rows": R, "pdf_extractor": "pdfplumber"}, tmp_path)
    assert ex.status == "ok" and ex.rows == R
    assert family_of(f, {"pdf_extractor": "pdfplumber"}) == "pdfplumber"


def test_run_docling_module_imports_without_docling():
    import experiments.gating.run_docling  # noqa: F401


def test_gate_fix_must_be_global_scope():
    with pytest.raises(ValueError):
        register(Fix(name="t:gate", kind="gate", scope="routed"))
    register(Fix(name="t:gate", kind="gate", scope="global"))


def test_mistral_cache_miss_is_not_extracted_and_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(fixes_mod, "OCR_CACHE", tmp_path / "ocr")
    fx = get("force:mistral_cache")
    with pytest.raises(NotExtracted):
        fx.extract(b"%PDF-x", URL)
    assert not (tmp_path / "ocr").exists()  # nothing written, no network path

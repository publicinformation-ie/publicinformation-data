"""Tests for the motion-model-sweep extraction matrix (Task 4).

Loads extract.py via importlib: the experiment directory name contains
dashes so it is not importable with a plain `from ... import` (same loader
pattern as test_motion_model_sweep_sample.py).

Binary effort semantics (Ruling G): the only implementable levels are
default (`effort=None`, thinking enabled) and `"none"` (thinking disabled).
Gradient levels raise ValueError in Task 3's backend plumbing — run_combo
must convert that into a fail-closed error entry, never propagate.
"""
import importlib.util
from pathlib import Path

_EXTRACT_PY = (Path(__file__).parent.parent / "experiments"
               / "2026-10-07-motion-model-sweep" / "extract.py")


def _load_extract_module():
    spec = importlib.util.spec_from_file_location("motion_sweep_extract", _EXTRACT_PY)
    assert spec is not None and spec.loader is not None, f"Cannot load {_EXTRACT_PY}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_extract_module()
cache_key = _mod.cache_key
run_combo = _mod.run_combo

_SAMPLE_FILE = {
    "file_url": "https://example.ie/minutes/file01.pdf",
    "text": "Minutes of the meeting held on 1 January 2024. "
            "That the council approves the works. Proposed by Cllr A.",
    "extractor": "pdfplumber",
    "old_motion_count": 1,
    "old_motions": [],
}

# Real spec-table model: cost arithmetic needs a priced model id (the cost
# table carries no "m" rate and inventing one would violate fail-closed).
_MODEL = "opencode-go/deepseek-v4.1-flash"


def _STUB_OK(system, user, session_id):
    return '{"meeting_date": null, "motions": []}'


def test_cache_key_pins_effort():
    assert cache_key("u", "m", None) != cache_key("u", "m", "none")
    assert cache_key("u", "m", "none") == cache_key("u", "m", "none")


def test_failed_extraction_is_error_only_with_cost():
    # run_combo returns the arms.json combo shape {file_url: record}, so the
    # single-file result is indexed by URL; the error entry still carries
    # cost (prompt side), never zero-filled.
    arm = run_combo([_SAMPLE_FILE], model=_MODEL, effort="none",
                    api_fn=lambda s, u, sid: (_ for _ in ()).throw(RuntimeError("x"))
                    )[_SAMPLE_FILE["file_url"]]
    assert arm["motions"] is None and arm["error"] is not None
    assert arm["cost_usd"] is not None and arm["tokens"] is not None


def test_invalid_effort_level_is_fail_closed_error():
    arm = run_combo([_SAMPLE_FILE], model=_MODEL, effort="low", api_fn=_STUB_OK
                    )[_SAMPLE_FILE["file_url"]]
    assert arm["motions"] is None and "low" in (arm["error"] or "")

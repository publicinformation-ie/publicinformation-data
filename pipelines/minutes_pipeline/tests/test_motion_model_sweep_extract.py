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


def test_run_live_checkpoints_after_gold_and_each_combo(monkeypatch):
    """on_arm is handed a partial snapshot after gold and every combo, so a
    live run can be checkpointed per arm (interruption loses at most one)."""
    monkeypatch.setattr(_mod, "GOLD_ARM", (_MODEL, None))
    monkeypatch.setattr(_mod, "GRID", [(_MODEL, None)])
    snaps = []
    _mod.run_live({"files": [_SAMPLE_FILE]}, cache={}, api_fn=_STUB_OK,
                  on_arm=lambda snap: snaps.append(
                      (sorted(snap["gold"]), sorted(snap["combos"]))))
    assert len(snaps) == 2
    assert snaps[0][1] == []
    assert snaps[1][1] == [_mod.combo_key(_MODEL, None)]


def test_run_combo_calls_on_file_per_fresh_response():
    """on_file fires once per freshly-computed file, carrying its record -
    the hook the live run uses to flush durable state per response."""
    seen = []
    run_combo([_SAMPLE_FILE], model=_MODEL, effort=None, api_fn=_STUB_OK,
              on_file=lambda url, rec: seen.append((url, rec)))
    assert [u for u, _ in seen] == [_SAMPLE_FILE["file_url"]]
    assert seen[0][1]["error"] is None


def test_run_live_seeds_working_dicts_from_prior_snapshot(monkeypatch):
    """A resumed run's per-response checkpoints start from the prior
    arms.json content, so early flushes never clobber completed arms."""
    monkeypatch.setattr(_mod, "GOLD_ARM", (_MODEL, None))
    monkeypatch.setattr(_mod, "GRID", [])
    prior = {"gold": {"https://example.ie/old.pdf": {"motions": []}},
             "combos": {}}
    snaps = []
    gold, _, _ = _mod.run_live({"files": [_SAMPLE_FILE]}, cache={},
                               api_fn=_STUB_OK, prior=prior,
                               on_file=snaps.append)
    assert "https://example.ie/old.pdf" in gold
    assert snaps and all("https://example.ie/old.pdf" in s["gold"]
                         for s in snaps)

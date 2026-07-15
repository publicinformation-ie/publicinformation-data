"""Determinism tests for the llm-repair sample draw."""
import importlib.util
from pathlib import Path

_SAMPLE_PATH = (
    Path(__file__).parents[2]
    / "experiments/2026-07-15-llm-structuring-repair/sample.py"
)
_spec = importlib.util.spec_from_file_location("llm_repair_sample", _SAMPLE_PATH)
assert _spec is not None and _spec.loader is not None
_sample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sample)

build_sample = _sample.build_sample


def test_same_seed_same_sample():
    a = build_sample()
    b = build_sample()
    assert a["files"] == b["files"]


def test_stratum_targets_respected_and_deduped():
    result = build_sample()
    files = result["files"]
    # No file appears twice.
    urls = [f["file_url"] for f in files]
    assert len(urls) == len(set(urls))
    # Every file carries a known stratum.
    assert all(
        f["stratum"] in {"newline_split_row", "null_column", "null_first_row"}
        for f in files
    )
    # null_first_row has exactly 2 available -> both drawn.
    n_first = sum(1 for f in files if f["stratum"] == "null_first_row")
    assert n_first == 2


def test_sha256_matches_file_url():
    import hashlib
    for f in build_sample()["files"]:
        expected = hashlib.sha256(f["file_url"].encode("utf-8")).hexdigest()
        assert f["sha256"] == expected

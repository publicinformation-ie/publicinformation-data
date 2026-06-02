import eval_utils
from steps.find_disclosure_files.eval import evaluate as fdf


# ── duplicate URL tests ──────────────────────────────────────────────────────

def _judgments_for(*urls):
    """Return a pre-verified judgments dict for each URL so precision scoring
    doesn't fail on cache misses — duplicates tests care about duplicate
    metrics, not precision."""
    return {url: {"label": "yes", "verified": "yes"} for url in urls}


def test_no_duplicates_produces_zero_metrics():
    items = [
        {"file_url": "a", "public_body_id": 1},
        {"file_url": "b", "public_body_id": 2},
    ]
    results, issues = fdf.run_eval(
        items, _judgments_for("a", "b"), input_hash="a" * 64, api_fn=None
    )
    names = {m.name: m.value for m in results.metrics}
    assert names["duplicate_file_url_count"] == 0
    assert names["duplicate_file_url_extra_records"] == 0
    assert names["duplicate_file_url_rate"] == 0.0
    assert not any("duplicate" in i.description for i in issues)


def test_single_duplicate_url():
    items = [
        {"file_url": "x", "public_body_id": 1},
        {"file_url": "x", "public_body_id": 2},
        {"file_url": "y", "public_body_id": 3},
    ]
    results, issues = fdf.run_eval(
        items, _judgments_for("x", "y"), input_hash="a" * 64, api_fn=None
    )
    names = {m.name: m.value for m in results.metrics}
    assert names["duplicate_file_url_count"] == 1   # one distinct URL duplicated
    assert names["duplicate_file_url_extra_records"] == 1  # one extra record
    assert abs(names["duplicate_file_url_rate"] - 1 / 3) < 1e-9
    assert any("duplicate" in i.description for i in issues)
    dup_issue = next(i for i in issues if "duplicate" in i.description)
    assert "x" in dup_issue.affected_ids


def test_multiple_duplicate_urls():
    items = [
        {"file_url": "a", "public_body_id": 1},
        {"file_url": "a", "public_body_id": 2},
        {"file_url": "a", "public_body_id": 3},
        {"file_url": "b", "public_body_id": 4},
        {"file_url": "b", "public_body_id": 5},
        {"file_url": "c", "public_body_id": 6},
    ]
    results, issues = fdf.run_eval(
        items, _judgments_for("a", "b", "c"), input_hash="a" * 64, api_fn=None
    )
    names = {m.name: m.value for m in results.metrics}
    assert names["duplicate_file_url_count"] == 2   # "a" and "b" are duplicated
    assert names["duplicate_file_url_extra_records"] == 3  # 2 extra "a" + 1 extra "b"
    assert abs(names["duplicate_file_url_rate"] - 3 / 6) < 1e-9


def test_empty_input_produces_zero_metrics():
    results, issues = fdf.run_eval([], {}, input_hash="a" * 64, api_fn=None)
    names = {m.name: m.value for m in results.metrics}
    assert names["duplicate_file_url_count"] == 0
    assert names["duplicate_file_url_extra_records"] == 0
    assert names["duplicate_file_url_rate"] == 0.0


# ── original tests ───────────────────────────────────────────────────────────

def test_precision_over_verified_judgments_only():
    items = [
        {"file_url": "a", "public_body_id": 1},
        {"file_url": "b", "public_body_id": 1},
        {"file_url": "c", "public_body_id": 2},
    ]
    judgments = {
        "a": {"label": "yes", "verified": "yes"},
        "b": {"label": "no", "verified": "yes"},
        "c": {"label": "yes", "verified": "auto"},  # unverified -> excluded
    }
    results, issues = fdf.run_eval(items, judgments, input_hash="a" * 64, api_fn=None)
    primary = [m for m in results.metrics if m.is_primary][0]
    assert primary.name == "precision"
    assert primary.value == 0.5  # 1 of 2 verified files are FOI
    assert primary.counts == {"foi": 1, "judged": 2}
    # the non-FOI file becomes an issue
    assert any("b" in i.affected_ids for i in issues)


def test_unverified_coverage_reported_as_secondary_metric():
    items = [{"file_url": "c", "public_body_id": 2}]
    judgments = {"c": {"label": "yes", "verified": "auto"}}
    results, _ = fdf.run_eval(items, judgments, input_hash="a" * 64, api_fn=None)
    names = {m.name for m in results.metrics}
    assert "unverified_coverage" in names


def test_cache_miss_with_no_api_raises():
    import pytest
    items = [{"file_url": "z", "public_body_id": 9}]
    with pytest.raises(Exception):
        fdf.run_eval(items, {}, input_hash="a" * 64, api_fn=None)


def test_cache_miss_with_api_fills_and_scores():
    items = [{"file_url": "z", "public_body_id": 9}]
    judgments = {}
    results, _ = fdf.run_eval(
        items, judgments, input_hash="a" * 64,
        api_fn=lambda prompt: "yes | genuine FOI disclosure log",
    )
    assert judgments["z"]["label"] == "yes"
    assert judgments["z"]["verified"] == "auto"  # auto -> excluded from precision
    assert results.metrics[0].counts["judged"] == 0

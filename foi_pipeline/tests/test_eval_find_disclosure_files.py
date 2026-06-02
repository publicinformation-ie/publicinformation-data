import eval_utils
from steps.find_disclosure_files.eval import evaluate as fdf


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

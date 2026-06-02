import evaluate_baseline as bl


def test_regression_fires_when_metric_drops_and_hash_matches():
    baseline = {"steps": {"a": {"f1": {"value": 0.80, "input_hash": "h1"}}}}
    current = {"a": {"name": "f1", "value": 0.70, "input_hash": "h1"}}
    regressions = bl.find_regressions(baseline, current, tolerance=0.02)
    assert regressions == [("a", "f1", 0.80, 0.70)]


def test_no_regression_when_input_hash_differs():
    baseline = {"steps": {"a": {"f1": {"value": 0.80, "input_hash": "h1"}}}}
    current = {"a": {"name": "f1", "value": 0.10, "input_hash": "DIFFERENT"}}
    assert bl.find_regressions(baseline, current, tolerance=0.02) == []


def test_within_tolerance_is_not_a_regression():
    baseline = {"steps": {"a": {"f1": {"value": 0.80, "input_hash": "h1"}}}}
    current = {"a": {"name": "f1", "value": 0.79, "input_hash": "h1"}}
    assert bl.find_regressions(baseline, current, tolerance=0.02) == []


def test_headline_regression_detected():
    baseline = {"headline": {"valid_records": 1251}}
    assert bl.headline_regressed(baseline, {"valid_records": 1200}) is True
    assert bl.headline_regressed(baseline, {"valid_records": 1251}) is False
    assert bl.headline_regressed(baseline, {"valid_records": 1300}) is False

from steps.find_disclosure_pages.eval.evaluate import classify, score, _norm


def test_norm_strips_trailing_slash_and_lowercases():
    assert _norm("https://X.ie/Log/") == "https://x.ie/log"
    assert _norm(None) == ""


def test_classify_true_positive():
    record = {"disclosure_page_url": "https://x.ie/log", "foi_page_url": "https://x.ie/foi"}
    label = {"label": "distinct_log", "expected_url": "https://x.ie/log"}
    assert classify(record, label) == "TP"


def test_classify_false_positive_wrong_url():
    record = {"disclosure_page_url": "https://x.ie/wrong", "foi_page_url": "https://x.ie/foi"}
    label = {"label": "distinct_log", "expected_url": "https://x.ie/log"}
    assert classify(record, label) == "FP"


def test_classify_false_negative_fell_back_when_log_exists():
    record = {"disclosure_page_url": "https://x.ie/foi", "foi_page_url": "https://x.ie/foi"}
    label = {"label": "distinct_log", "expected_url": "https://x.ie/log"}
    assert classify(record, label) == "FN"


def test_classify_false_positive_when_should_use_foi_page():
    record = {"disclosure_page_url": "https://x.ie/blah", "foi_page_url": "https://x.ie/foi"}
    label = {"label": "use_foi_page", "expected_url": ""}
    assert classify(record, label) == "FP"


def test_classify_true_negative_correctly_fell_back():
    record = {"disclosure_page_url": "https://x.ie/foi", "foi_page_url": "https://x.ie/foi"}
    label = {"label": "use_foi_page", "expected_url": ""}
    assert classify(record, label) == "TN"


def test_classify_true_negative_no_log_exists():
    record = {"disclosure_page_url": "https://x.ie/foi", "foi_page_url": "https://x.ie/foi"}
    label = {"label": "no_log_exists", "expected_url": ""}
    assert classify(record, label) == "TN"


def test_score_aggregates_and_computes_precision_recall():
    records = {
        "1": {"disclosure_page_url": "https://x.ie/log", "foi_page_url": "https://x.ie/foi"},
        "2": {"disclosure_page_url": "https://x.ie/wrong", "foi_page_url": "https://x.ie/foi"},
        "3": {"disclosure_page_url": "https://x.ie/foi", "foi_page_url": "https://x.ie/foi"},
        "4": {"disclosure_page_url": "https://x.ie/foi", "foi_page_url": "https://x.ie/foi"},
        "5": {"disclosure_page_url": "https://x.ie/blah", "foi_page_url": "https://x.ie/foi"},
    }
    labels = [
        {"public_body_id": "1", "label": "distinct_log", "expected_url": "https://x.ie/log"},
        {"public_body_id": "2", "label": "distinct_log", "expected_url": "https://x.ie/log"},
        {"public_body_id": "3", "label": "distinct_log", "expected_url": "https://x.ie/log"},
        {"public_body_id": "4", "label": "use_foi_page", "expected_url": ""},
        {"public_body_id": "5", "label": "use_foi_page", "expected_url": ""},
    ]
    counts, precision, recall, f1, details, skipped = score(records, labels)
    assert counts == {"TP": 1, "FP": 2, "FN": 1, "TN": 1}
    assert precision == 1 / 3
    assert recall == 0.5
    assert abs(f1 - 0.4) < 1e-9
    assert ("2", "https://x.ie/wrong") in details["FP"]
    assert ("3", "https://x.ie/log") in details["FN"]


from pathlib import Path

import eval_utils
from steps.find_disclosure_pages.eval import evaluate as fdp_eval

EVAL_DIR = Path(fdp_eval.__file__).parent


def test_run_eval_builds_primary_f1_metric_and_promotes_skipped(tmp_path):
    labels = [
        {"public_body_id": "1", "label": "distinct_log", "expected_url": "https://x.ie/log"},
        {"public_body_id": "9", "label": "distinct_log", "expected_url": "https://x.ie/log"},
    ]
    records = {
        "1": {"disclosure_page_url": "https://x.ie/log", "foi_page_url": "https://x.ie/foi"},
        # id 9 has no record -> skipped -> warning Issue
    }
    fixture = tmp_path / "matcher_output.json"
    fixture.write_text('{"results": []}')

    results, issues = fdp_eval.run_eval(records, labels, fixture)

    primary = [m for m in results.metrics if m.is_primary]
    assert len(primary) == 1
    assert primary[0].name == "f1"
    assert results.input_hash == eval_utils.input_hash(fixture)
    assert any(i.severity == "warning" and "no output record" in i.description for i in issues)


def test_default_fixture_is_committed_matcher_output():
    assert (EVAL_DIR / "matcher_output.json").exists()

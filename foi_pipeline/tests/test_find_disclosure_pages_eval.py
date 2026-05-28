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

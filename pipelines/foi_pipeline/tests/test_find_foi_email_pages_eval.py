from steps.find_foi_email_pages.eval.evaluate import classify, score


def test_classify_true_positive_found_correct_email():
    record = {"foi_email": "foi@dept-a.ie", "confidence": "high"}
    label = {"label": "found", "expected_url": "foi@dept-a.ie"}
    assert classify(record, label) == "TP"


def test_classify_false_positive_found_wrong_email():
    record = {"foi_email": "wrong@dept-a.ie", "confidence": "medium"}
    label = {"label": "found", "expected_url": "foi@dept-a.ie"}
    assert classify(record, label) == "FP"


def test_classify_false_negative_should_have_found_no_hit():
    record = {"foi_email": None, "confidence": None}
    label = {"label": "should_have_found", "expected_url": "foi@dept-a.ie"}
    assert classify(record, label) == "FN"


def test_classify_true_negative_no_email_exists_no_hit():
    record = {"foi_email": None, "confidence": None}
    label = {"label": "no_email_exists", "expected_url": ""}
    assert classify(record, label) == "TN"


def test_classify_false_positive_wrong_match_hit():
    record = {"foi_email": "heritage@corkcity.ie", "confidence": "none"}
    label = {"label": "wrong_match", "expected_url": ""}
    assert classify(record, label) == "FP"


def test_classify_true_negative_wrong_match_correctly_rejected():
    record = {"foi_email": None, "confidence": None}
    label = {"label": "wrong_match", "expected_url": ""}
    assert classify(record, label) == "TN"


def test_score_aggregates_and_computes_precision_recall():
    records = {
        "1": {"foi_email": "foi@a.ie", "confidence": "high"},
        "2": {"foi_email": "wrong@b.ie", "confidence": "medium"},
        "3": {"foi_email": None, "confidence": None},
        "4": {"foi_email": None, "confidence": None},
        "5": {"foi_email": "x@c.ie", "confidence": "none"},
    }
    labels = [
        {"public_body_id": "1", "label": "found", "expected_url": "foi@a.ie"},
        {"public_body_id": "2", "label": "found", "expected_url": "foi@b.ie"},
        {"public_body_id": "3", "label": "should_have_found", "expected_url": "foi@d.ie"},
        {"public_body_id": "4", "label": "no_email_exists", "expected_url": ""},
        {"public_body_id": "5", "label": "wrong_match", "expected_url": ""},
    ]
    counts, precision, recall, f1, details, skipped = score(records, labels)
    assert counts == {"TP": 1, "FP": 2, "FN": 1, "TN": 1}
    assert precision == 1 / 3
    assert recall == 0.5
    assert abs(f1 - 0.4) < 1e-9
    assert skipped == 0

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


from steps.find_foi_email_pages.eval.run_matcher import _matcher_result_for_fixture

FOI_PAGE_HTML = '<html><body><a href="/foi-officer">FOI Officer</a></body></html>'
CANDIDATE_HTML_WITH_EMAIL = '<html><body><a href="mailto:foi@dept-a.ie">FOI</a></body></html>'
CANDIDATE_HTML_NO_EMAIL = '<html><body><p>No contact info</p></body></html>'


def test_matcher_result_upgrades_when_candidate_has_email():
    result = _matcher_result_for_fixture(FOI_PAGE_HTML, "https://dept-a.ie/foi/", CANDIDATE_HTML_WITH_EMAIL)
    assert result["email_status"] == "found"
    assert result["foi_email"] == "foi@dept-a.ie"
    assert result["confidence"] == "high"
    assert result["source_page_url"] == "https://dept-a.ie/foi-officer"


def test_matcher_result_leaves_not_found_when_candidate_has_no_email():
    result = _matcher_result_for_fixture(FOI_PAGE_HTML, "https://dept-a.ie/foi/", CANDIDATE_HTML_NO_EMAIL)
    assert result["email_status"] == "not_found"
    assert result["foi_email"] is None
    assert "confidence" not in result


def test_matcher_result_leaves_not_found_when_no_candidate_fixture():
    result = _matcher_result_for_fixture(FOI_PAGE_HTML, "https://dept-a.ie/foi/", None)
    assert result["email_status"] == "not_found"
    assert result["foi_email"] is None


def test_matcher_result_leaves_not_found_when_no_links_on_page():
    result = _matcher_result_for_fixture('<html><body><p>nothing</p></body></html>', "https://dept-a.ie/foi/", None)
    assert result["email_status"] == "not_found"

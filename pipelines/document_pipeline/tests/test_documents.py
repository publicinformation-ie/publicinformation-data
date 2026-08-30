import pytest

from documents import InvalidDocumentRole, load_documents

VALID = """
documents:
  - doc_slug: gda-transport-strategy-2022-2042
    title: "GDA Transport Strategy"
    url: "https://example.org/strategy.pdf"
    publisher: "National Transport Authority"
    public_body_id: 1486
    published_date: "2023-01-19"
"""


def _write(tmp_path, text):
    path = tmp_path / "documents.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_documents_returns_one_normalised_record(tmp_path):
    records = load_documents(_write(tmp_path, VALID))
    assert records == [{
        "doc_slug": "gda-transport-strategy-2022-2042",
        "title": "GDA Transport Strategy",
        "url": "https://example.org/strategy.pdf",
        "publisher": "National Transport Authority",
        "public_body_id": 1486,
        "published_date": "2023-01-19",
        "role": "plan",
        "reports_on": None,
        "expected_action_count": None,
        "expected_status_counts": None,
    }]


def test_load_documents_defaults_optional_fields_to_none(tmp_path):
    text = (
        "documents:\n"
        "  - doc_slug: a-doc\n"
        '    title: "A Doc"\n'
        '    url: "https://example.org/a.pdf"\n'
    )
    (record,) = load_documents(_write(tmp_path, text))
    assert record["publisher"] is None
    assert record["public_body_id"] is None
    assert record["published_date"] is None
    assert record["reports_on"] is None
    assert record["expected_action_count"] is None
    assert record["expected_status_counts"] is None


@pytest.mark.parametrize("slug", ["Not_A_Slug", "trailing-", "-leading", "has space", ""])
def test_load_documents_rejects_a_malformed_slug(tmp_path, slug):
    text = f'documents:\n  - doc_slug: "{slug}"\n    title: "T"\n    url: "https://e.org/a.pdf"\n'
    with pytest.raises(ValueError, match="doc_slug"):
        load_documents(_write(tmp_path, text))


def test_load_documents_rejects_a_duplicate_slug(tmp_path):
    text = (
        "documents:\n"
        '  - doc_slug: a-doc\n    title: "One"\n    url: "https://e.org/1.pdf"\n'
        '  - doc_slug: a-doc\n    title: "Two"\n    url: "https://e.org/2.pdf"\n'
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_documents(_write(tmp_path, text))


def test_load_documents_rejects_a_non_http_url(tmp_path):
    text = 'documents:\n  - doc_slug: a-doc\n    title: "T"\n    url: "ftp://e.org/a.pdf"\n'
    with pytest.raises(ValueError, match="url"):
        load_documents(_write(tmp_path, text))


def test_load_documents_rejects_a_missing_required_field(tmp_path):
    text = 'documents:\n  - doc_slug: a-doc\n    url: "https://e.org/a.pdf"\n'
    with pytest.raises(ValueError, match="title"):
        load_documents(_write(tmp_path, text))


def write_yaml(tmp_path, body):
    path = tmp_path / "documents.yml"
    path.write_text(body, encoding="utf-8")
    return path


PLAN = """documents:
  - doc_slug: a-plan
    title: "A Plan"
    url: "https://example.ie/a.pdf"
"""


def test_role_defaults_to_plan_when_absent(tmp_path):
    records = load_documents(write_yaml(tmp_path, PLAN))
    assert records[0]["role"] == "plan"
    assert records[0]["reports_on"] is None
    assert records[0]["expected_action_count"] is None
    assert records[0]["expected_status_counts"] is None


def test_report_resolves_reports_on_to_another_slug(tmp_path):
    path = write_yaml(tmp_path, PLAN + """  - doc_slug: a-report
    title: "A Report"
    url: "https://example.ie/b.pdf"
    role: report
    reports_on: a-plan
""")
    records = load_documents(path)
    assert records[1]["role"] == "report"
    assert records[1]["reports_on"] == "a-plan"


def test_report_without_reports_on_is_fatal(tmp_path):
    path = write_yaml(tmp_path, PLAN + """  - doc_slug: a-report
    title: "A Report"
    url: "https://example.ie/b.pdf"
    role: report
""")
    with pytest.raises(InvalidDocumentRole, match="reports_on"):
        load_documents(path)


def test_report_with_unresolvable_reports_on_is_fatal(tmp_path):
    path = write_yaml(tmp_path, PLAN + """  - doc_slug: a-report
    title: "A Report"
    url: "https://example.ie/b.pdf"
    role: report
    reports_on: no-such-plan
""")
    with pytest.raises(InvalidDocumentRole, match="no-such-plan"):
        load_documents(path)


def test_unknown_role_is_fatal(tmp_path):
    path = write_yaml(tmp_path, """documents:
  - doc_slug: a-plan
    title: "A Plan"
    url: "https://example.ie/a.pdf"
    role: annex
""")
    with pytest.raises(InvalidDocumentRole, match="annex"):
        load_documents(path)


def test_reports_on_is_rejected_on_a_plan(tmp_path):
    path = write_yaml(tmp_path, """documents:
  - doc_slug: a-plan
    title: "A Plan"
    url: "https://example.ie/a.pdf"
    reports_on: a-plan
""")
    with pytest.raises(InvalidDocumentRole, match="reports_on"):
        load_documents(path)


def test_expected_counts_are_parsed(tmp_path):
    path = write_yaml(tmp_path, """documents:
  - doc_slug: a-plan
    title: "A Plan"
    url: "https://example.ie/a.pdf"
    expected_action_count: 91
  - doc_slug: a-report
    title: "A Report"
    url: "https://example.ie/b.pdf"
    role: report
    reports_on: a-plan
    expected_status_counts:
      Complete: 58
      Delayed: 28
""")
    records = load_documents(path)
    assert records[0]["expected_action_count"] == 91
    assert records[1]["expected_status_counts"] == {"Complete": 58, "Delayed": 28}


def test_non_integer_expected_action_count_is_rejected(tmp_path):
    path = write_yaml(tmp_path, """documents:
  - doc_slug: a-plan
    title: "A Plan"
    url: "https://example.ie/a.pdf"
    expected_action_count: "ninety-one"
""")
    with pytest.raises(ValueError, match="expected_action_count"):
        load_documents(path)


def test_non_integer_expected_status_count_value_is_rejected(tmp_path):
    path = write_yaml(tmp_path, """documents:
  - doc_slug: a-report
    title: "A Report"
    url: "https://example.ie/b.pdf"
    role: report
    reports_on: a-report
    expected_status_counts:
      Complete: many
""")
    with pytest.raises(ValueError):
        load_documents(path)


def test_the_real_documents_yml_declares_the_smp_corpus():
    """The corpus is the dataset's whole input; a slug typo here is a silent
    empty dataset rather than a failure, so assert the shape directly."""
    records = {r["doc_slug"]: r for r in load_documents()}
    plan = records["sustainable-mobility-policy-action-plan-2022-2025"]
    assert plan["role"] == "plan"
    assert plan["expected_action_count"] == 91
    reports = [r for r in records.values() if r["role"] == "report"]
    assert len(reports) == 4
    assert all(r["reports_on"] == plan["doc_slug"] for r in reports)
    assert all(r["public_body_id"] == 1213 for r in reports)
    final = records["sustainable-mobility-policy-action-plan-2022-2025-final-progress-report"]
    # No expected_status_counts: this report's status observations are not
    # yet extractable (UnknownReportFormat — see
    # extract_action_status/README.md's "Known limitations" section), so it
    # is intentionally unchecked for v1.0.0 pending a follow-up fix to
    # extract_pages's table-header detection.
    assert final["expected_status_counts"] is None

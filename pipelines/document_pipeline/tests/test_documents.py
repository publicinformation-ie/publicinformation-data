import pytest

from documents import load_documents

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

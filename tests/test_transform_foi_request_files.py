from scripts.transform_foi_request_files import hash_document_id


def test_hash_document_id_deterministic():
    url = "https://www.centralbank.ie/docs/default-source/foi-disclosure-log-q1-2026.pdf"
    assert hash_document_id(url) == hash_document_id(url)


def test_hash_document_id_is_12_hex_chars():
    result = hash_document_id("https://example.ie/foi.pdf")
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_document_id_differs_for_different_urls():
    a = hash_document_id("https://example.ie/foi-2024.pdf")
    b = hash_document_id("https://example.ie/foi-2025.pdf")
    assert a != b

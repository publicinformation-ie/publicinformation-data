from lib.disclosure_link_utils import find_file_links, _score_link


def test_find_file_links_returns_link_text():
    html = '<html><body><a href="/disclosures/foi-log-2024.pdf">FOI Disclosure Log 2024</a></body></html>'
    files = find_file_links(html, "https://dept.ie/foi/")
    assert len(files) == 1
    assert files[0]["link_text"] == "FOI Disclosure Log 2024"
    assert files[0]["file_url"] == "https://dept.ie/disclosures/foi-log-2024.pdf"
    assert files[0]["file_type"] == "pdf"


def test_find_file_links_negative_link_text_rejected():
    html = '<html><body><a href="/disclosures/q1.pdf">Election Results 2024</a></body></html>'
    files = find_file_links(html, "https://dept.ie/foi/")
    assert len(files) == 0


def test_find_file_links_positive_link_text_accepts_opaque_url():
    html = '<html><body><a href="/media/e482e8d6-44ae-4359-hash.pdf">Disclosure Log</a></body></html>'
    files = find_file_links(html, "https://assets.cpsa.ie/")
    assert len(files) == 1
    assert files[0]["link_text"] == "Disclosure Log"


def test_score_link_hard_rejects_protected_disclosure():
    assert _score_link("https://dept.ie/protected-disclosure/foi-log.pdf", "") < 0


def test_score_link_accepts_foi_keyword_url():
    assert _score_link("https://dept.ie/foi-decisions/log-2024.pdf", "") > 0


def test_find_file_links_deduplicates_same_url():
    html = '<html><body><a href="/q1.pdf">Q1</a><a href="/q1.pdf">Q1 again</a></body></html>'
    files = find_file_links(html, "https://dept.ie/")
    assert len(files) == 1

from pdf_candidates import extract_pdf_links, render_review_list

HTML = """
<a href="/uploads/Plan-2022.pdf">The Plan (PDF)</a>
<a href="https://other.example/x/Report.PDF?download=1">Report</a>
<a href="/uploads/Plan-2022.pdf">duplicate</a>
<a href="mailto:a@b.ie">mail</a><a>no href</a><a href="#top">anchor</a>
<a href="/page.html">not a pdf</a>
"""


def test_extract_pdf_links_resolves_dedupes_and_filters():
    links = extract_pdf_links(HTML, "https://site.example/section/index.html")
    assert [l["url"] for l in links] == [
        "https://site.example/uploads/Plan-2022.pdf",
        "https://other.example/x/Report.PDF?download=1",
    ]
    assert links[0]["text"] == "The Plan (PDF)"


def test_extract_pdf_links_on_empty_or_garbage_html():
    assert extract_pdf_links("", "https://s.example/") == []
    assert extract_pdf_links("<a href=", "https://s.example/") == []


def test_review_list_shows_candidates_failures_and_empty_pages():
    policies = [
        {"policy_id": "alpha", "number": 1, "title": "Alpha", "source_urls": ["https://s.example/a"]},
        {"policy_id": "beta", "number": 2, "title": "Beta", "source_urls": ["https://s.example/b"]},
        {"policy_id": "gamma", "number": 3, "title": "Gamma", "source_urls": ["https://www.localgov.ie/"]},
    ]
    results = {
        "alpha": {"pages": [{"url": "https://s.example/a", "error": None,
                             "pdfs": [{"url": "https://s.example/a.pdf", "text": "Alpha PDF"}]}]},
        "beta": {"pages": [{"url": "https://s.example/b", "error": "BotChallengeError: blocked", "pdfs": []}]},
        "gamma": {"pages": [{"url": "https://www.localgov.ie/", "error": None, "pdfs": []}]},
    }
    md = render_review_list(policies, results)
    assert "### 1. Alpha" in md and "https://s.example/a.pdf" in md
    assert "BotChallengeError" in md                      # failures are visible, not dropped
    assert "no PDF links found" in md                     # empty page is stated, never invented
    assert "Approve / reject" in md

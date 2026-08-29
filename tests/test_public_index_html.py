"""Guard the hand-authored homepage nav: the `/documents` index must stay
reachable from the site root, below the schema/provenance/pipeline section."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "public" / "index.html"


def test_homepage_links_to_documents_index_after_reference_section():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'href="documents/"' in html
    assert "Strategies and Plans" in html

    reference_pos = html.index('id="reference"')
    link_pos = html.index('href="documents/"')
    assert link_pos > reference_pos

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
HUB = PUBLIC / "README.md"
INDEX = PUBLIC / "index.html"
REDIRECT = "https://github.com/publicinformation-ie/publicinformation-data/blob/main/public/README.md"


def _slugs():
    return sorted(p.name for p in (PUBLIC / "latest").iterdir() if p.is_dir())


def test_index_is_a_redirect_to_the_hub():
    html = INDEX.read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in html
    assert REDIRECT in html


def test_hub_links_every_dataset_readme():
    hub = HUB.read_text(encoding="utf-8")
    for slug in _slugs():
        assert f"latest/{slug}/README.md" in hub, slug


def test_hub_has_no_documents_bundle_link():
    assert "documents/" not in HUB.read_text(encoding="utf-8")


def test_hub_links_the_three_guides():
    hub = HUB.read_text(encoding="utf-8")
    for guide in ("GET_THE_DATA.md", "QUICKSTART.md", "DATA_QUALITY.md"):
        assert guide in hub, guide

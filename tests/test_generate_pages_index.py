"""Unit tests for scripts/generate_pages_index.py."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import generate_pages_index as gpi  # noqa: E402


def _make_fixture_tree(tmp_path: Path) -> Path:
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "dataset-a.ttl").write_text("a" * 100)
    (tmp_path / "latest").mkdir()
    (tmp_path / "latest" / "who-does-what").mkdir()
    (tmp_path / "latest" / "who-does-what" / "who-does-what.csv").write_text("b" * 2048)
    (tmp_path / "topics.json").write_text("{}")
    return tmp_path


class TestGenerateIndex:
    def test_writes_index_html(self, tmp_path):
        root = _make_fixture_tree(tmp_path)
        gpi.generate_index(root)
        assert (root / "index.html").exists()

    def test_includes_top_level_file_link(self, tmp_path):
        root = _make_fixture_tree(tmp_path)
        gpi.generate_index(root)
        content = (root / "index.html").read_text()
        assert 'href="topics.json"' in content

    def test_includes_nested_file_links(self, tmp_path):
        root = _make_fixture_tree(tmp_path)
        gpi.generate_index(root)
        content = (root / "index.html").read_text()
        assert 'href="catalog/dataset-a.ttl"' in content
        assert 'href="latest/who-does-what/who-does-what.csv"' in content

    def test_includes_directory_links(self, tmp_path):
        root = _make_fixture_tree(tmp_path)
        gpi.generate_index(root)
        content = (root / "index.html").read_text()
        assert 'href="catalog/"' in content
        assert 'href="latest/"' in content
        assert 'href="latest/who-does-what/"' in content

    def test_excludes_index_html_itself_from_top_level_listing(self, tmp_path):
        root = _make_fixture_tree(tmp_path)
        gpi.generate_index(root)
        gpi.generate_index(root)  # re-run: must not list its own output
        content = (root / "index.html").read_text()
        assert 'href="index.html"' not in content

    def test_no_external_assets_or_js(self, tmp_path):
        root = _make_fixture_tree(tmp_path)
        gpi.generate_index(root)
        content = (root / "index.html").read_text()
        assert "<script" not in content
        assert "http://" not in content
        assert "https://" not in content

"""Guard the open-data entry pages: every dataset that publishes a ``latest/``
distribution must be linked from ``get-the-data.html`` (each CSV table) and
from the ``#reference`` list on ``index.html`` (its README).

Datasets published outside ``latest/`` (notably ``documents``, served from
``public/documents/``) are naturally excluded because only ``latest/*/``
subdirectories are enumerated.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = REPO_ROOT / "public"
LATEST_DIR = PUBLIC_DIR / "latest"
GET_THE_DATA = PUBLIC_DIR / "get-the-data.html"
INDEX_HTML = PUBLIC_DIR / "index.html"


def _dataset_slugs() -> list[str]:
    return sorted(p.name for p in LATEST_DIR.iterdir() if p.is_dir())


def _csv_basenames(slug: str) -> list[str]:
    return sorted(p.name for p in (LATEST_DIR / slug).glob("*.csv"))


def _reference_section(html: str) -> str:
    start = html.index('id="reference"')
    end = html.index("</ul>", start)
    return html[start:end]


def test_every_latest_dataset_csv_is_linked_from_get_the_data():
    get_the_data = GET_THE_DATA.read_text(encoding="utf-8")
    for slug in _dataset_slugs():
        basenames = _csv_basenames(slug)
        assert basenames, f"dataset {slug} has no CSV files"
        for basename in basenames:
            assert (
                f"latest/{slug}/{basename}" in get_the_data
            ), f"get-the-data.html is missing a link to latest/{slug}/{basename}"


def test_every_latest_dataset_readme_is_in_index_reference_list():
    index_html = INDEX_HTML.read_text(encoding="utf-8")
    reference = _reference_section(index_html)
    for slug in _dataset_slugs():
        assert (
            f"latest/{slug}/README.md" in reference
        ), f"index.html #reference is missing latest/{slug}/README.md"

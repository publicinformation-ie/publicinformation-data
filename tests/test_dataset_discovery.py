"""Guard the open-data entry pages: every dataset that publishes a ``latest/``
distribution must be linked from ``GET_THE_DATA.md`` (each CSV table) and
from the data hub ``README.md`` (its dataset README).

Datasets published outside ``latest/`` are naturally excluded because only
``latest/*/`` subdirectories are enumerated.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = REPO_ROOT / "public"
LATEST_DIR = PUBLIC_DIR / "latest"
GET_THE_DATA = PUBLIC_DIR / "GET_THE_DATA.md"
HUB = PUBLIC_DIR / "README.md"


def _dataset_slugs() -> list[str]:
    return sorted(p.name for p in LATEST_DIR.iterdir() if p.is_dir())


def _csv_basenames(slug: str) -> list[str]:
    return sorted(p.name for p in (LATEST_DIR / slug).glob("*.csv"))


def test_every_latest_dataset_csv_is_linked_from_get_the_data():
    get_the_data = GET_THE_DATA.read_text(encoding="utf-8")
    for slug in _dataset_slugs():
        basenames = _csv_basenames(slug)
        assert basenames, f"dataset {slug} has no CSV files"
        for basename in basenames:
            assert (
                f"latest/{slug}/{basename}" in get_the_data
            ), f"GET_THE_DATA.md is missing a link to latest/{slug}/{basename}"


def test_every_latest_dataset_readme_is_in_the_hub():
    hub = HUB.read_text(encoding="utf-8")
    for slug in _dataset_slugs():
        assert (
            f"latest/{slug}/README.md" in hub
        ), f"public/README.md is missing latest/{slug}/README.md"

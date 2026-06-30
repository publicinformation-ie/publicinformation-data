# foi_pipeline/tests/test_column_mappings_config.py
import json
from pathlib import Path

MAPPINGS_PATH = (
    Path(__file__).parent.parent
    / "steps"
    / "extract_disclosures_canonicalize"
    / "column_mappings.json"
)


def _load():
    return json.loads(MAPPINGS_PATH.read_text())


def test_column_mappings_is_flat_dict_of_overrides():
    """Every top-level value must be an override dict with only the three
    expected keys — catches entries accidentally nested inside another
    entry's column_mapping instead of being a top-level sibling."""
    data = _load()
    assert isinstance(data, dict)
    for url, entry in data.items():
        assert url.startswith("http"), f"key {url!r} is not a URL"
        assert isinstance(entry, dict)
        assert set(entry.keys()) <= {"source_method", "overridden", "column_mapping"}, (
            f"entry for {url!r} has unexpected keys: {sorted(entry.keys())} "
            "— likely another entry nested inside this one"
        )
        assert "column_mapping" in entry


def test_column_mappings_urls_are_percent_encoded():
    """Keys must match the percent-encoded file_url format used everywhere
    else in the pipeline (e.g. %20 not a literal space), or the exact-match
    lookup in canonicalize_file() silently never fires."""
    data = _load()
    for url in data:
        assert " " not in url, (
            f"key {url!r} contains a literal space — should be percent-encoded (%20)"
        )


def test_no_duplicate_top_level_urls():
    """json.load silently keeps only the last of duplicate keys — guard
    against that by checking key count against a manual scan of the raw
    text for duplicate top-level URL strings."""
    data = _load()
    raw = MAPPINGS_PATH.read_text()
    for url in data:
        # each top-level key should appear exactly once as a JSON key (": {" follows it)
        needle = json.dumps(url)
        assert raw.count(needle) == 1, f"key {url!r} appears more than once in the file"

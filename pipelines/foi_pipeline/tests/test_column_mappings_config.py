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
        assert set(entry.keys()) <= {"source_method", "overridden", "column_mapping", "skip_camelot_fallback"}, (
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


import pytest

MEATH_URLS = [
    "https://www.meath.ie/system/files/media/file-uploads/2019-05/FOI%20Disclosure%20Log%202018%20%28Jul%20to%20Dec%29.pdf",
    "https://www.meath.ie/system/files/media/file-uploads/2019-05/FOI%20Disclosure%20Log%202018%20%28Jan%20to%20Jun%29.pdf",
    "https://www.meath.ie/system/files/media/file-uploads/2020-03/Disclosure%20Log%202019%20-%20July%20to%20December%20-%20for%20website_0.pdf",
    "https://www.meath.ie/system/files/media/file-uploads/2019-09/Disclosure%20Log%202019%20-%20January%20-%20June%20-%20for%20website%20-%20Updated%20Sept.pdf",
]

MEATH_COLUMN_MAPPING = {
    "0": "foi_reference_id",
    "1": "date_received",
    "2": "requester_type",
    "3": "request_description",
    "4": "decision_date",
    "5": "decision_status",
}


@pytest.mark.parametrize("url", MEATH_URLS)
def test_meath_entries_present_with_expected_mapping(url):
    data = _load()
    assert url in data, f"missing column_mappings entry for {url!r}"
    assert data[url]["column_mapping"] == MEATH_COLUMN_MAPPING
    assert data[url]["source_method"] == "manual"
    assert data[url]["overridden"] is True
    assert data[url]["skip_camelot_fallback"] is True


def test_non_meath_entries_do_not_have_skip_camelot_fallback():
    """Only the 4 Meath entries should opt into skip_camelot_fallback — the
    other 9 overrides rely on camelot's extraction and must not be affected."""
    data = _load()
    for url, entry in data.items():
        if "meath.ie" not in url:
            assert "skip_camelot_fallback" not in entry, (
                f"non-Meath entry {url!r} unexpectedly has skip_camelot_fallback"
            )

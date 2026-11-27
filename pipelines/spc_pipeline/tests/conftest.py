import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
_prev = None
while not (_REPO_ROOT / ".git").exists():
    if _prev == _REPO_ROOT:
        raise RuntimeError(f"Could not find .git root starting from {_HERE}")
    _prev = _REPO_ROOT
    _REPO_ROOT = _REPO_ROOT.parent

sys.path.insert(0, str(_HERE.parent))          # pipelines/spc_pipeline/, for steps.* imports
sys.path.insert(0, str(_HERE.parent / "experiments" / "2026-11-26-spc-model-sweep"))
sys.path.insert(0, str(_REPO_ROOT))            # repo root, for src.lib imports
sys.path.insert(0, str(_REPO_ROOT / "src"))    # src/lib/ takes precedence over pipeline lib/

FIXTURES = _HERE / "fixtures"
CACHE = _HERE.parent / "cache"
PDF_FIXTURES = FIXTURES / "pdf"
MEETINGS_MANIFEST = FIXTURES / "meetings.json"


OCR_FIXTURES = FIXTURES / "ocr"
OCR_OVERRIDES = _HERE.parent / "steps" / "fetch_spc_minutes" / "ocr_overrides.json"


def fixture_meetings(committee_prefix: str | None = None) -> list[dict]:
    """The committed fixture manifest: fetch records without page words.

    ``committee_prefix`` (for example ``"meath/"``) selects one council's files.
    """
    meetings = json.loads(MEETINGS_MANIFEST.read_text())["meetings"]
    if committee_prefix:
        meetings = [m for m in meetings if m["committee_id"].startswith(committee_prefix)]
    return meetings


def fetch_fixture(entry: dict) -> dict:
    """Rebuild one fetch record from its sha-pinned PDF, reading scanned pages
    through the committed OCR fixtures (never a live tesseract run)."""
    from steps.fetch_spc_minutes import fetching

    data = (PDF_FIXTURES / entry["pdf"]).read_bytes()
    read = fetching.read_pages(
        data, fetching.sha256_hex(data), fetching.FixtureOcr(OCR_FIXTURES),
        fetching.load_overrides(OCR_OVERRIDES))
    record = {key: value for key, value in entry.items() if key != "pdf"}
    record.update({
        "pages": read["pages"],
        "text_source": read["text_source"],
        "ocr_engine": read["ocr_engine"],
        "ocr_skipped_pages": read["skipped_pages"],
    })
    return record


@pytest.fixture(scope="session")
def fetch_by_pdf():
    """``name -> fetch record`` for any committed fixture PDF, e.g. ``"westmeath-2025-09-19.pdf"``."""
    entries = {entry["pdf"]: entry for entry in fixture_meetings()}
    return lambda pdf: fetch_fixture(entries[pdf])


@pytest.fixture(scope="session")
def fetched_meetings() -> list[dict]:
    """Meath's six fetch records rebuilt from the committed, sha-pinned PDFs.

    CI has no git-ignored step output, so the fixture PDFs are the source of
    truth. Extraction happens once for the whole session.
    """
    return [fetch_fixture(entry) for entry in fixture_meetings("meath/")]


def fetch_new_meetings() -> tuple[list[dict], dict[str, str]]:
    """``(records, failures)`` for the Kildare and Westmeath fixtures.

    A fixture whose fetch fails closed (an OCR gate error) is left out of
    ``records`` and named in ``failures`` with its error type.
    """
    from steps.fetch_spc_minutes import fetching

    records: list[dict] = []
    failures: dict[str, str] = {}
    for entry in fixture_meetings():
        if entry["committee_id"].startswith("meath/"):
            continue
        try:
            records.append(fetch_fixture(entry))
        except (fetching.NoTextRecovered, fetching.OcrLowConfidence,
                fetching.EmptyOcrPage) as exc:
            failures[entry["pdf"]] = type(exc).__name__
    return records, failures


@pytest.fixture(scope="session")
def fetched_new_meetings() -> list[dict]:
    """The Kildare and Westmeath fetch records (scanned pages via OCR fixtures)."""
    return fetch_new_meetings()[0]


@pytest.fixture(scope="session")
def parsed_meetings(fetched_meetings) -> list[dict]:
    from steps.parse_meeting_header.header import run

    records, errors = run({"results": fetched_meetings})
    assert errors == []
    return records


@pytest.fixture(scope="session")
def resolved_meetings(parsed_meetings) -> list[dict]:
    from steps.resolve_attendees.resolving import load_register, run

    register = load_register(_HERE.parent / "reference" / "people.json")
    records, errors = run({"results": parsed_meetings}, register)
    assert errors == []
    return records


@pytest.fixture(scope="session")
def rendered_meetings(resolved_meetings) -> list[dict]:
    from steps.render_spc_minutes.rendering import run

    records, errors = run({"results": resolved_meetings})
    assert errors == []
    return records


@pytest.fixture(scope="session")
def rendered_new_meetings(fetched_new_meetings) -> list[dict]:
    """Kildare and Westmeath meetings parsed, resolved and rendered (OCR fixtures)."""
    from steps.parse_meeting_header.header import run as parse
    from steps.render_spc_minutes.rendering import run as render
    from steps.resolve_attendees.resolving import load_register, run as resolve

    parsed, _ = parse({"results": fetched_new_meetings})
    resolved, _ = resolve({"results": parsed},
                          load_register(_HERE.parent / "reference" / "people.json"))
    rendered, errors = render({"results": resolved})
    assert errors == []
    return rendered

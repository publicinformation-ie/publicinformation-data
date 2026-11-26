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


def fixture_meetings() -> list[dict]:
    """The committed fixture manifest: six fetch records without page words."""
    return json.loads(MEETINGS_MANIFEST.read_text())["meetings"]


@pytest.fixture(scope="session")
def fetched_meetings() -> list[dict]:
    """Real fetch records rebuilt from the committed, sha-pinned PDFs.

    CI has no git-ignored step output, so the fixture PDFs are the source of
    truth. Extraction happens once for the whole session.
    """
    from steps.fetch_spc_minutes.fetching import extract_pages

    records = []
    for entry in fixture_meetings():
        record = {key: value for key, value in entry.items() if key != "pdf"}
        record["pages"] = extract_pages((PDF_FIXTURES / entry["pdf"]).read_bytes())
        records.append(record)
    return records


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

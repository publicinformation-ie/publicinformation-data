from lib.body_matching import normalise, best_match, load_candidates, MATCH_THRESHOLD
from lib.file_utils import write_json


def _candidates(*pairs):
    """Build a candidates list from (public_body_id, name) pairs."""
    return [(pid, name, normalise(name)) for pid, name in pairs]


# ── normalise ────────────────────────────────────────────────────────────

def test_normalise_strips_clg_suffix():
    assert normalise("Adare Heritage Trust CLG") == "adare heritage trust"


def test_normalise_strips_parenthetical():
    assert normalise("Adoption Authority of Ireland (AAI)") == "adoption authority of ireland"


def test_normalise_collapses_whitespace_and_lowercases():
    assert normalise("  Central   Statistics Office  ") == "central statistics office"


# ── best_match ───────────────────────────────────────────────────────────

def test_best_match_exact_name_clears_threshold():
    candidates = _candidates((1106, "Central Statistics Office"))
    body_id, score = best_match(normalise("Central Statistics Office"), candidates)
    assert body_id == 1106
    assert score >= MATCH_THRESHOLD


def test_best_match_below_threshold_returns_none():
    candidates = _candidates(
        (1594, "Office of Public Works"),
        (1651, "Public Appointments Service"),
    )
    body_id, score = best_match(normalise("publicjobs"), candidates)
    assert body_id is None
    assert score < MATCH_THRESHOLD


def test_best_match_empty_candidates_returns_none():
    body_id, score = best_match(normalise("Anything"), [])
    assert body_id is None
    assert score == 0.0


# ── load_candidates ──────────────────────────────────────────────────────

def test_load_candidates_reads_results_key(tmp_path):
    path = tmp_path / "candidates.json"
    write_json(path, {"results": [{"public_body_id": 1106, "name": "Central Statistics Office"}]})
    candidates = load_candidates(path)
    assert candidates == [(1106, "Central Statistics Office", "central statistics office")]


def test_load_candidates_reads_public_bodies_key(tmp_path):
    path = tmp_path / "candidates.json"
    write_json(path, {"public_bodies": [{"public_body_id": 1002, "name": "Ability West"}]})
    candidates = load_candidates(path)
    assert candidates == [(1002, "Ability West", "ability west")]

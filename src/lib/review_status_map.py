from typing import Optional

from lib.text_utils import normalize_header

CANONICAL_REVIEW_STATUSES: list[str] = [
    'Upheld',
    'Partially Upheld',
    'Varied',
    'Annulled',
]

_REVIEW_SYNONYMS: dict[str, list[str]] = {
    'Upheld': ['Upheld', 'Affirmed', 'Confirmed'],
    'Partially Upheld': ['Partially Upheld', 'Partially Overturned', 'Partially Varied'],
    'Varied': ['Varied'],
    'Annulled': ['Annulled'],
}

_REVIEW_LOOKUP: dict[str, str] = {}
for _canonical, _synonyms in _REVIEW_SYNONYMS.items():
    for _synonym in _synonyms:
        _norm = normalize_header(_synonym)
        _REVIEW_LOOKUP.setdefault(_norm, _canonical)


def canonicalize_review_status(status: str | None) -> Optional[str]:
    """Return canonical review status for a value, or None if unrecognised."""
    if not status or not isinstance(status, str) or not status.strip():
        return None
    return _REVIEW_LOOKUP.get(normalize_header(status))

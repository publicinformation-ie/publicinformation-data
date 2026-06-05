"""Status normalization mapping for FOI decision status values."""
import re
from typing import Optional

from lib.text_utils import normalize_header

# The seven canonical status values
CANONICAL_STATUSES: list[str] = [
    'Granted',
    'Refused',
    'Part-Granted',
    'Withdrawn',
    'Handled outside of FOI',
    'Transferred',
    'Deemed Refused',
]

# Minimal initial mapping - will be expanded based on error review
# Maps canonical status to list of known synonyms
_STATUS_SYNONYMS: dict[str, list[str]] = {
    'Granted': [
        'Granted',
        'Grant',
        'GRANTED',
        'Grant - FOI Non Personal',
        'Access: Granted',
        'Access Granted',
    ],
    'Refused': [
        'Refused',
        'Refuse',
        'REFUSED',
        'Refusal - FOI Non Personal',
        'Access Refused',
    ],
    'Part-Granted': [
        'Part-Granted',
        'Part Granted',
        'Part Grant',
        'Part- Granted',
        'Partially Granted',
        'Partial Grant',
    ],
    'Withdrawn': [
        'Withdrawn',
        'Withdraw',
        'Request Withdrawn',
        'Withdrew',
    ],
    'Handled outside of FOI': [
        'Handled outside of FOI',
        'Handled Outside FOI',
        'Handled Outside',
        'Handled outside FOI',
    ],
    'Transferred': [
        'Transferred',
        'Transfer',
        'Transferred to another body',
    ],
    'Deemed Refused': [
        'Deemed Refused',
        'Deemed refused',
        'Deemed-Refused',
        'Time limit expired',
    ],
}

# Build inverted lookup dict at module load time for O(1) lookups
# Key: normalized status string -> Value: canonical status
_STATUS_LOOKUP: dict[str, str] = {}
for canonical, synonyms in _STATUS_SYNONYMS.items():
    for synonym in synonyms:
        norm = normalize_header(synonym)
        # First synonym wins; later ones are ignored to avoid conflicts
        if norm not in _STATUS_LOOKUP:
            _STATUS_LOOKUP[norm] = canonical


def canonicalize_status(status: str | None) -> Optional[str]:
    """Return the canonical status for a decision status string, or None.
    
    Uses normalize_header() which:
    - Converts to lowercase
    - Replaces all whitespace sequences (including newlines, underscores) with single spaces
    - Strips leading/trailing whitespace
    - Removes trailing punctuation
    
    This ensures case-insensitive, whitespace-tolerant matching.
    
    Args:
        status: The raw decision status string to normalize
        
    Returns:
        The canonical status string, or None if status is empty or unrecognized
    """
    if not status or not isinstance(status, str) or not status.strip():
        return None
    
    norm = normalize_header(status)
    return _STATUS_LOOKUP.get(norm)


def get_canonical_statuses() -> list[str]:
    """Return the list of canonical status values."""
    return CANONICAL_STATUSES.copy()


def get_status_synonyms() -> dict[str, list[str]]:
    """Return the synonym mapping dictionary."""
    return _STATUS_SYNONYMS.copy()

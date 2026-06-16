"""Status normalization mapping for FOI decision status values."""
import re
from typing import Optional

from lib.text_utils import normalize_header

# The canonical status values
CANONICAL_STATUSES: list[str] = [
    'Granted',
    'Refused',
    'Part-Granted',
    'Withdrawn',
    'Handled outside of FOI',
    'Transferred',
    'Deemed Refused',
    'Personal',
    'Unknown',
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
        'Granted in Full',
        '2017-09-01 Decision - Granted in full',
        'Affirm (Internal Review)',
        'Admin Access',
        'Final',
        'Released',
        'Fully Released',
    ],
    'Refused': [
        'Refused',
        'Refuse',
        'REFUSED',
        'Refusal - FOI Non Personal',
        'Access Refused',
        'No',
        'Refusal',
        'Refused (not answered within time period)',
        'Refuse (record does not exist)',
        'Refused under',
        'R e f u s e d',
        'Refused under the provisions of Schedule 1, Part 1(d)',
        'INVALID',
        'Not Valid',
        'Request not Valid',
        'Invalid Request',
    ],
    'Part-Granted': [
        'Part-Granted',
        'Part Granted',
        'Part Grant',
        'Part-Grant',
        'Part-grant',
        'Part- Granted',
        'Partially Granted',
        'Partial Grant',
        'Part -Grant',
        'Partly Granted',
        'Part grant - non personal',
        'Part Grant - FOI Non Personal',
        'Part Released',
        'Part Release',
        'Partial Release',
        'PART-GRAN',
        'Part',
    ],
    'Withdrawn': [
        'Withdrawn',
        'Withdraw',
        'Request Withdrawn',
        'Withdrew',
        'Withdrawn and dealt with outside of FOI',
        'Withdraw and handle outside FOI',
        'Withdrawn and Handled Outside of FOI',
        'Withdrawn/ ha',
        'Case Closed',
        'WITHDRA WN/OUT',
    ],
    'Handled outside of FOI': [
        'Handled outside of FOI',
        'Handled Outside FOI',
        'Handled Outside',
        'Handled outside FOI',
        'O/s FOI',
        'Handled O/S FOI',
        'Non FOI',
        'Outside FOI',
        'Dealt with outside FOI',
        'outside of FOI',
        'outside of FOI Act',
        'Outside of FOI',
    ],
    'Transferred': [
        'Transferred',
        'Transfer',
        'Transferred to another body',
        'Transferred to DoD',
    ],
    'Deemed Refused': [
        'Deemed Refused',
        'Deemed refused',
        'Deemed-Refused',
        'Time limit expired',
        'Deemed Refused No records found',
        'Deemed to be refused as reply not sent within timeframes',
        'lapsed - S & R fee not received',
    ],
    'Personal': [
        'PERSONAL',
        'Personal',
    ],
    'Unknown': [
        'N/A',
        'n/a',
        'NA',
        'Unknown',
        'Queried',
    ],
}


def _normalize_status(status: str) -> str:
    """Normalize a status string for matching."""
    return normalize_header(status.replace('-', ' '))


# Build inverted lookup dict at module load time for O(1) lookups
# Key: normalized status string -> Value: canonical status
_STATUS_LOOKUP: dict[str, str] = {}
for canonical, synonyms in _STATUS_SYNONYMS.items():
    for synonym in synonyms:
        norm = _normalize_status(synonym)
        if norm not in _STATUS_LOOKUP:
            _STATUS_LOOKUP[norm] = canonical


def canonicalize_status(status: str | None) -> Optional[str]:
    """Return the canonical status for a decision status string, or None."""
    if not status or not isinstance(status, str) or not status.strip():
        return None

    norm = _normalize_status(status)

    result = _STATUS_LOOKUP.get(norm)
    if result:
        return result

    all_synonyms = []
    for canonical, synonyms in _STATUS_SYNONYMS.items():
        for synonym in synonyms:
            norm_syn = _normalize_status(synonym)
            all_synonyms.append((len(norm_syn), canonical, norm_syn))

    all_synonyms.sort(key=lambda x: (-x[0], x[1]))

    for _, canonical, norm_syn in all_synonyms:
        pattern = r'\b' + re.escape(norm_syn) + r'\b'
        if re.search(pattern, norm):
            return canonical

    return None


def get_canonical_statuses() -> list[str]:
    """Return the list of canonical status values."""
    return CANONICAL_STATUSES.copy()


def get_status_synonyms() -> dict[str, list[str]]:
    """Return the synonym mapping dictionary."""
    return _STATUS_SYNONYMS.copy()

"""Requester type normalisation mapping for FOI disclosure records."""
from typing import Optional

CANONICAL_REQUESTER_TYPES: list[str] = [
    'Journalist',
    'Other',
    'Member of the Public',
    'Non-Personal',
    'Client',
    'Business/Interest Group',
    'Oireachtas',
    'Media',
    'Individual',
    'Personal',
    'Staff',
    'Public',
    'Solicitor',
]

# Maps value.strip().lower() → canonical string, or None for confirmed junk.
_LOOKUP: dict[str, Optional[str]] = {
    # Journalist
    'journalist': 'Journalist',
    'journalists': 'Journalist',
    # Other
    'other': 'Other',
    'others': 'Other',
    # Member of the Public
    'member of the public': 'Member of the Public',
    'member of public': 'Member of the Public',
    'a member of the public': 'Member of the Public',
    'mop': 'Member of the Public',
    # Non-Personal
    'non-personal': 'Non-Personal',
    'non personal': 'Non-Personal',
    'non pers': 'Non-Personal',
    'non- personal': 'Non-Personal',
    # Client
    'client': 'Client',
    'clients': 'Client',
    # Business/Interest Group
    'business/interest group': 'Business/Interest Group',
    'business / interest group': 'Business/Interest Group',
    'business/ interest group': 'Business/Interest Group',
    'business/interest groups': 'Business/Interest Group',
    'business / interest groups': 'Business/Interest Group',
    'business interest group': 'Business/Interest Group',
    'business interest groups': 'Business/Interest Group',
    'business interest': 'Business/Interest Group',
    'business/interest': 'Business/Interest Group',
    'business/inte rest group': 'Business/Interest Group',  # OCR word-wrap artefact
    # Oireachtas — all compound forms collapse to Oireachtas
    'oireachtas': 'Oireachtas',
    'oireachtas/public representatives': 'Oireachtas',
    'oireachtas/public representative': 'Oireachtas',
    'oireachtas / public representative': 'Oireachtas',
    'oireachtas / public representatives': 'Oireachtas',
    'oireachtas / public reps': 'Oireachtas',
    'oireachtas/ public reps': 'Oireachtas',
    'oireachtas/public reps': 'Oireachtas',
    'oireachtas member/ councillor': 'Oireachtas',
    'oireachtas member/councillor': 'Oireachtas',
    'oireachtas/elected representative': 'Oireachtas',
    'oireachtas/elected representatives': 'Oireachtas',
    'oireachtas member': 'Oireachtas',
    'member of oireachtas': 'Oireachtas',
    'member of the oireachtas': 'Oireachtas',
    'member of the oireachtas/elected representative': 'Oireachtas',
    'oireactas / public reps': 'Oireachtas',  # typo (missing 'h')
    # Media
    'media': 'Media',
    'press': 'Media',
    'reporter': 'Media',
    # Individual
    'individual': 'Individual',
    # Personal
    'personal': 'Personal',
    # Staff
    'staff': 'Staff',
    # Public
    'public': 'Public',
    # Solicitor
    'solicitor': 'Solicitor',
    'solicitors': 'Solicitor',
    # Confirmed junk — explicit None so we know we've seen them
    'category': None,    # column header leaking in
    'type': None,        # column header leaking in
    'su': None,          # unknown abbreviation
    'member of': None,   # truncated — not enough context to classify
    'the public': None,  # second half of OCR-split "Member of the Public"
    'erest group': None, # second half of OCR-split "Business/Interest Group"
    'business/int': None,# first half of OCR-split
}


def canonicalize_requester_type(value: str | None) -> Optional[str]:
    """Return canonical requester type for a value, or None if unrecognised or junk."""
    if not value or not isinstance(value, str) or not value.strip():
        return None
    key = value.strip().lower()
    if key in _LOOKUP:
        return _LOOKUP[key]
    return None

"""Requester type normalisation mapping for FOI disclosure records."""
from typing import Optional

CANONICAL_REQUESTER_TYPES: list[str] = [
    'Journalist',
    'Other',
    'Member of the Public',
    'Non-Personal',
    'Client',
    'Business/Interest Group',
    'Elected-Oireachtas',
    'Elected-Councillor',
    'Elected-Unknown',
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
    'applicant': 'Other',
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
    'non -personal': 'Non-Personal',
    'individual (non-personal)': 'Non-Personal',
    'individual (non- personal)': 'Non-Personal',
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
    'interest groups': 'Business/Interest Group',
    'commercial': 'Business/Interest Group',
    'organisation': 'Business/Interest Group',
    'business group': 'Business/Interest Group',
    'business': 'Business/Interest Group',
    'association': 'Business/Interest Group',
    'residents association': 'Business/Interest Group',
    'housing association': 'Business/Interest Group',
    'campaign organisation': 'Business/Interest Group',
    'campaign organization': 'Business/Interest Group',
    'app.housing body': 'Business/Interest Group',
    'member of business/interest group': 'Business/Interest Group',
    'industry': 'Business/Interest Group',
    'business / industry': 'Business/Interest Group',
    'group': 'Business/Interest Group',
    'groups': 'Business/Interest Group',
    'interested group': 'Business/Interest Group',
    'interest group': 'Business/Interest Group',
    'business/ interest groups': 'Business/Interest Group',
    'business/ interest': 'Business/Interest Group',
    'group business/interest': 'Business/Interest Group',
    'company': 'Business/Interest Group',
    'ngo': 'Business/Interest Group',
    'charitable organisation': 'Business/Interest Group',
    'business/in terest group': 'Business/Interest Group',  # OCR word-wrap artefact
    # Elected-Oireachtas — national parliament elected members
    'oireachtas': 'Elected-Oireachtas',
    'oireachtas/public representatives': 'Elected-Oireachtas',
    'oireachtas/public representative': 'Elected-Oireachtas',
    'oireachtas / public representative': 'Elected-Oireachtas',
    'oireachtas / public representatives': 'Elected-Oireachtas',
    'oireachtas / public reps': 'Elected-Oireachtas',
    'oireachtas/ public reps': 'Elected-Oireachtas',
    'oireachtas/public reps': 'Elected-Oireachtas',
    'oireachtas member/ councillor': 'Elected-Oireachtas',
    'oireachtas member/councillor': 'Elected-Oireachtas',
    'oireachtas/elected representative': 'Elected-Oireachtas',
    'oireachtas/elected representatives': 'Elected-Oireachtas',
    'oireachtas member': 'Elected-Oireachtas',
    'member of oireachtas': 'Elected-Oireachtas',
    'member of the oireachtas': 'Elected-Oireachtas',
    'member of the oireachtas/elected representative': 'Elected-Oireachtas',
    'oireactas / public reps': 'Elected-Oireachtas',  # typo (missing 'h')
    'oireachtas members': 'Elected-Oireachtas',
    'oireactas': 'Elected-Oireachtas',          # standalone typo (missing 'h')
    'oireachtas/public': 'Elected-Oireachtas',
    'td / senator': 'Elected-Oireachtas',
    'public rep': 'Elected-Oireachtas',
    # Elected-Councillor — local authority elected members
    'councillor': 'Elected-Councillor',
    'member of local authority': 'Elected-Councillor',
    # Elected-Unknown — elected representative, level unclear
    'public representative': 'Elected-Unknown',
    'politician': 'Elected-Unknown',
    'elected member': 'Elected-Unknown',
    # Media
    'media': 'Media',
    'press': 'Media',
    'reporter': 'Media',
    # Individual
    'individual': 'Individual',
    'private individual': 'Individual',
    # Personal
    'personal': 'Personal',
    'individual (personal)': 'Personal',
    # Staff
    'staff': 'Staff',
    # Public
    'public': 'Public',
    # Solicitor
    'solicitor': 'Solicitor',
    'solicitors': 'Solicitor',
    'legal firm': 'Solicitor',
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

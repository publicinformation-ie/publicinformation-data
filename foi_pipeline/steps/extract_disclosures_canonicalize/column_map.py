import re
from typing import Optional

CANONICAL_COLUMNS: list[str] = [
    'foi_reference_id',
    'decision_date',
    'requester_type',
    'decision_status',
    'review_status',
    'related_request',
    'request_description',
]

REQUIRED_COLUMNS: frozenset[str] = frozenset({'foi_reference_id', 'request_description'})

_SYNONYMS: dict[str, list[str]] = {
    'foi_reference_id': [
        'our ref', 'our ref.', 'foi reference number', 'request assignment id',
        'request number', 'ref no', 'ref no.', 'ref. no.', 'reference number',
        'case id', 'query number', 'ref number', 'foi reference', 'request id',
        'reference no', 'reference no.', 'query number/uimhir',
        'query number/uimhir cháis', 'case number', 'reference no.',
        'reference number', 'foi no.', 'foi ref', 'ref. no. foi–',
        'reference', 'ref', 'date received reference no', 'request reference',
        'no', 'id', 'aie no.', 'request no.', 'index',
        'our reference',
    ],
    'decision_date': [
        'decision date', 'date received', "date rec'd", "date rcv'd",
        'due date', 'date issued', 'date released', 'date of request',
        'request date', 'date of reply', 'date received/dáta a fuarthas',
        'date issued/dáta a eisíodh an cinneadh', 'decisiondate',
        'completion date', 'date and details of request received',
        'date of decision', 'date completed', 'date of release', 'reply date',
        'date and details of request', 'date', 'request date',
        'foi request date received',
    ],
    'requester_type': [
        'requester type', 'category', 'category of requester', 'requester',
        'request category', 'requestor category', 'request type',
        'requester category', 'requester/cineál', 'category of request',
        'category of requestor', 'requestor', 'requestor type',
        'type of requester', 'name of requester', 'type request',
    ],
    'decision_status': [
        'decision made', 'decision', 'status', 'decision/cinneadh',
        'dm decision', 'reason',
        'foi request status', 'foi decision',
    ],
    'review_status': [
        'ir', 'ir/al', 'al',
    ],
    'related_request': [
        'related file', 'related file/uimhir cháis',
    ],
    'request_description': [
        'description', 'request details', 'request', 'summary',
        'summary of request', 'request summary', 'request description',
        'query', 'summary scope', 'query/ceist', 'description of request',
        'subject', 'statement of request',
        'foi request summary', 'foi description',
    ],
}

_LOOKUP: dict[str, str] = {}
for _canonical, _synonyms in _SYNONYMS.items():
    for _synonym in _synonyms:
        _norm = re.sub(r'[\s_]+', ' ', _synonym.strip().lower())
        _LOOKUP.setdefault(_norm, _canonical)


def _normalise(header: str) -> str:
    return re.sub(r'[\s_]+', ' ', header.strip().lower())


def canonicalize_header(header: str | None) -> Optional[str]:
    """Return the canonical key for a header string, or None if unrecognised."""
    if not header or not str(header).strip():
        return None
    norm = _normalise(str(header))
    if norm in _LOOKUP:
        return _LOOKUP[norm]
    stripped = re.sub(r'\s+\d{4}\.?$', '', norm).strip()
    if stripped != norm:
        return _LOOKUP.get(stripped)
    return None


def canonicalize_headers(headers: list[str]) -> dict[str, Optional[str]]:
    """Map a list of header strings to canonical keys."""
    return {h: canonicalize_header(h) for h in headers}

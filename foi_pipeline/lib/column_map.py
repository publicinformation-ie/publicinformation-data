import re
from typing import Optional
from lib.text_utils import normalize_header

CANONICAL_COLUMNS: list[str] = [
    'foi_reference_id',
    'date_received',
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
        # additional synonyms derived from columns.csv profiling
        'foi req no', 'aie req no', 'foi no',
        'tag / reference', 'tag / ref', 'tag/reference',
        'rec. no',
        'case file',
        'freedom of information (foi) ref',
        # pdfplumber mid-word line-wrap artefacts (Pleanála PDFs)
        'query number/ui mhir',   # Query\nNumber/Ui\nmhir
        'query number/ uimhir',   # Query\nNumber/\nUimhir
        'tag/ref',
        'document no',
        'reco rd no',             # OCR artefact for 'Record No'
        # Group E — PDF variants from disclosure logs
        'file ref.', 'file ref',
    ],
    'date_received': [
        'date received', "date rec'd", "date rcv'd",
        'date of request', 'request date',
        'date received/dáta a fuarthas',
        'date and details of request received',
        'date and details of request',
        'foi request date received',
        # additional synonyms derived from columns.csv profiling
        'date request received',
        'dáta faighte / date received',  # Irish-first bilingual header
        'dáta faighte/ date received',   # no-space variant
    ],
    'decision_date': [
        'decision date', 'due date', 'date issued', 'date released',
        'date issued/dáta a eisíodh an cinneadh', 'decisiondate',
        'completion date', 'date of decision', 'date completed',
        'date of release', 'reply date', 'date of reply', 'date',
        # additional synonyms derived from columns.csv profiling
        'date decision letter issued',
        'date of decision letter',
        'response date',
        'date of of release',            # typo in source data
        'cinneadh eisithe / decision issued',
        'cinneadh eisithe / date decision issued',
        'cinneadh eisithe/ decision issued',
        'decision due',
    ],
    'requester_type': [
        'requester type', 'category', 'category of requester', 'requester',
        'request category', 'requestor category', 'request type',
        'requester category', 'requester/cineál', 'category of request',
        'category of requestor', 'requestor', 'requestor type',
        'type of requester', 'name of requester', 'type request',
        # additional synonyms derived from columns.csv profiling
        'cineál iarratasóra / type of requestor',  # Irish bilingual (Galway)
        'cineál iarratasóra/ type of requestor',   # no-space variant
        'type of request',
        # Group E — additional body variants
        'category of applicant',
        'personal (p)/non- persona (np)',
        # OCR spacing artefact — each character separated by space
        'c a t e g o r y o f requester',
    ],
    'decision_status': [
        'decision made', 'decision', 'status', 'decision/cinneadh',
        'dm decision', 'reason',
        'foi decision',
        # additional synonyms derived from columns.csv profiling
        'foi result', 'foi outcome',
        'catagóir cinnidh / decision category',    # Irish bilingual (Galway)
        'decision grant part grant refuse',
        'decision granted/part granted/refused',
        'decision grant, grant part or refuse',
        'decision grant, part grant or refuse',
        'grant, part grant, refusal',
        'decisions',
        # pdfplumber mid-word line-wrap artefact
        'decision/cinne adh',   # Decision/Cinne\nadh
        # Group E — additional PDF variants
        'decisions made',
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
        # additional synonyms derived from columns.csv profiling
        'information requested',
        'nature of request',
        'brief description of request',
        'brief description of record',
        'brief description',
        'sonraí / details',  # Irish/bilingual (Galway)
        'details',
        'description of the request (categories of records sought)',
        # Group C/E — older and PDF variant headers
        'foi request',
        'brief description of the request',
        'summary of the information/records requested',
        'records requested',
        'query re',
        'disclosure log for 2023 description of the request (categories of records sought)',
    ],
}

def _normalise(header: str) -> str:
    """Normalize header string for canonical matching."""
    return normalize_header(header)


_LOOKUP: dict[str, str] = {}
for _canonical, _synonyms in _SYNONYMS.items():
    for _synonym in _synonyms:
        _LOOKUP.setdefault(_normalise(_synonym), _canonical)


_ISO_DATETIME_SUFFIX = re.compile(r'\s+\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}$')
_YEAR_SUFFIX = re.compile(r'\s+\d{4}\.?$')


def canonicalize_header(header: str | None) -> Optional[str]:
    """Return the canonical key for a header string, or None if unrecognised."""
    if not header or not str(header).strip():
        return None
    norm = _normalise(str(header))
    if norm in _LOOKUP:
        return _LOOKUP[norm]
    # Strip trailing ISO datetime suffix (e.g. 'Date of Decision 2024-01-31T00:00:00')
    iso_stripped = _ISO_DATETIME_SUFFIX.sub('', norm)
    if iso_stripped != norm:
        return _LOOKUP.get(iso_stripped)
    # Strip trailing year suffix (e.g. 'Our Ref. 2019') — re-normalise in case stripping
    # exposes punctuation that normalize_header would remove (e.g. trailing period)
    year_stripped = _normalise(_YEAR_SUFFIX.sub('', norm))
    if year_stripped != norm:
        return _LOOKUP.get(year_stripped)
    return None


def canonicalize_headers(headers: list[str]) -> dict[str, Optional[str]]:
    """Map a list of header strings to canonical keys."""
    return {h: canonicalize_header(h) for h in headers}

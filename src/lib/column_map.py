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

# Normalised headers of columns that contain both a date AND request description in the same cell.
# These are split by extract_disclosures_split_combined_columns before date normalisation.
COMBINED_DATE_HEADERS: frozenset[str] = frozenset({
    'date and details of request received',
    'date and details of request',
})


_SYNONYMS: dict[str, list[str]] = {
    'foi_reference_id': [
        'our ref', 'our ref.', 'foi reference number', 'request assignment id',
        'request number', 'ref no', 'ref no.', 'ref. no.', 'reference number',
        'case id', 'query number', 'ref number', 'foi reference', 'request id',
        'reference no', 'reference no.', 'query number/uimhir',
        'query number/uimhir cháis', 'case number', 'reference no.',
        'reference number', 'foi no.', 'foi ref', 'ref. no. foi–',
        'reference', 'ref', 'date received reference no', 'request reference',
        'no', 'number', 'id', 'aie no.', 'request no.', 'index',
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
        'foi file no',
        # Irish-language synonyms (Fingal, DLR PDFs)
        'uimhir thagartha', 'uimhir',
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
        # Meath PDFs
        'date of receipt',
        'date when',
        # Charities Regulator — reversed word order
        'received date',
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
        'response sent date',
        'date of of release',            # typo in source data
        'cinneadh eisithe / decision issued',
        'cinneadh eisithe / date decision issued',
        'cinneadh eisithe/ decision issued',
        'cinneadh eisithe/decision made',      # Donegal compiled PDF (no spaces around /)
        'decision due',
        # Leitrim and Fingal/DLR variants
        'date outcome',
        'dáta eisiúna',
        # Task 2: header-leakage values (multi-row PDF headers bleeding into data)
        'dáta',               # Irish for "Date" (standalone column header)
        # Galway City Council OCR artefacts: "Cinneadh Eisithe" = "Decision Issued" (a date column,
        # not the decision type). OCR adds spaces within the Irish word, breaking the exact-match
        # on the clean synonym above and letting the bilingual fallback pick up "decision made"
        # → decision_status instead. These explicit entries win before the fallback fires.
        'C i nneadh Eisithe/\nDecision Made',    # 2022–2024 PDFs
        'C i n n e adh Eisithe/\nDecision Made', # 2025 PDF variant
        # Fingal County Council: "Decision/Response Sent" is the date the decision was sent,
        # not the decision type. Without these entries the bilingual fallback splits on "/" and
        # picks up "decision" → decision_status, overriding the correct Cineál Cinneadh column.
        'Decision/Response\nSent',               # 2021–2022 PDFs
        'Decision/Respons\ne Sent',              # pdfplumber line-wrap artefact
        'Decision/\nResponse\nSent',             # another line-wrap variant
        'Decision/Response \nBreith ar',         # 2023–2024 PDFs ("breith ar" = IR review)
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
        'cineál iarratasóra/type of requestor',    # Donegal compiled PDF (no spaces around /)
        'type of request',
        # Group E — additional body variants
        'category of applicant',
        'personal (p)/non- persona (np)',
        # OCR spacing artefact — each character separated by space
        'c a t e g o r y o f requester',
        # Irish-language synonyms (Fingal, DLR PDFs)
        'catagóir',
        'iarrthóra',
        # Task 2: header-leakage values (multi-row PDF headers bleeding into data)
        'type',               # standalone "Type" column header (requester type)
        'cineál',             # Irish for "Type" — standalone (not compound form)
        'non pers',           # "Non-Personal" requester category abbreviation
        'member of the',      # fragment of "Member of the Oireachtas/Public Representatives"
        'category of',        # fragment of "Category of Requester"
        'catagóir on',        # Irish fragment "Category of"
    ],
    'decision_status': [
        'decision made', 'decision', 'status', 'decision/cinneadh',
        'dm decision', 'reason',
        'foi decision',
        # additional synonyms derived from columns.csv profiling
        'foi result', 'foi outcome',
        'catagóir cinnidh / decision category',    # Irish bilingual (Galway) — space-padded /
        'Catagóir Cinnidh/\nDecision Category',    # Galway PDFs: \n collapses to space, drops the padding
        'C atagóir Cinnidh/ Decision\nCategory',   # Galway 2025 PDF — OCR splits "Catagóir"
        'catagóir cinnidh/decision category',      # Donegal compiled PDF (no spaces around /)
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
        'request outcome',
        # Irish-language and reversed variants (Fingal, DLR, Tipperary PDFs)
        'cinneadh',
        'date decision',    # Tipperary PDFs: "Date Decision" is their decision outcome column, not a date
        'decision type',
        'Cineál\nCinneadh/Decisio\nn Type',  # Fingal 2022 PDF: pdfplumber splits "Decision" across lines
        # Task 2: header-leakage values (multi-row PDF headers bleeding into data)
        'made',               # 2nd line of split "Decision / Made" header (body 1211)
    ],
    'review_status': [
        'ir', 'ir/al', 'al',
        # Irish-language synonym (Fingal, DLR PDFs)
        'athbhreithniú',
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
        # Irish-language and variant headers (Fingal, DLR, Leitrim, Tipperary PDFs)
        'tuairisc ar',
        'tuairisc ar iarrataís / description of',
        'title (summary description)',
        'request detail',
        # Cork CoCo variants
        'subject matter',
        'subject matter of request',
        'subject matter of request (non-personal only)',
        'subject matter of request (non- personal only)',
        # Department of Justice
        'personal records',
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
    # Bilingual fallback: 'Irish/English Name' — try each part after splitting on '/'.
    # This handles Fingal/DLR PDFs where pdfplumber preserves 'Uimhir/Reference Number'.
    # Only applied after all other lookups fail to avoid false positives.
    if '/' in norm:
        for part in norm.split('/'):
            part = part.strip()
            if part and part in _LOOKUP:
                return _LOOKUP[part]
    return None


def canonicalize_headers(headers: list[str]) -> dict[str, Optional[str]]:
    """Map a list of header strings to canonical keys."""
    return {h: canonicalize_header(h) for h in headers}

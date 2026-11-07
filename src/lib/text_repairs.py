r"""Deterministic repairs for confirmed PDF text-extraction artefacts.

Action text extracted from PDFs carries a small set of recurring, confirmed
artefacts: transposed letter pairs that split a word in two ("thereafet r"
for "thereafter", "statoi n" for "Station") and a dot where a space belongs
("staf.f" for "staff"). `REPAIRS` is the committed, human-reviewed mapping of
exactly those artefacts; `repair_text` applies it so consumers can publish
clean display text while the raw extraction stays untouched.

Semantics:

- Matching is case-insensitive and longest-pattern-first, so "ofef ring"
  wins over the "ofef r" contained inside it. All-caps and leading-capital
  forms of a match are preserved ("Commitet e" -> "Committee",
  "STAF F" -> "STAFF").
- A match inside a URL, e-mail address or domain-like token is never
  repaired. The guard looks at the whitespace-delimited token around the
  match with the matched text itself stripped out: only if what remains
  contains "://", "@" or a domain-like `\w+\.\w+` stretch is the match
  skipped. That keeps "https://example.ie/staf.f" intact while plain prose
  "staf.f" is still repaired.

`find_suspicious` is a review aid, not an auto-fixer: it flags text shaped
like the known artefacts but missing from `REPAIRS`, so a human can decide
whether to extend the map. It must never be applied to data automatically.
"""
import re

REPAIRS: tuple[tuple[str, str], ...] = (
    ("staf frespect", "staff respect"),
    ("staf fcan", "staff can"),
    ("of flater", "off later"),
    ("difef rences", "differences"),
    ("informatoi n", "information"),
    ("efef ct", "effect"),
    ("efof rt", "effort"),
    ("ofef ring", "offering"),
    ("ofef r", "offer"),
    ("afof rdable", "affordable"),
    ("difef rent", "different"),
    ("locatoi ns", "locations"),
    ("multpi le", "multiple"),
    ("patet rns", "patterns"),
    ("setnti g", "setting"),
    ("atti udes", "attitudes"),
    ("connectni g", "Connecting"),
    ("statoi n", "Station"),
    ("platof rm", "platform"),
    ("submitet d", "submitted"),
    ("permitet d", "permitted"),
    ("commitet e", "Committee"),
    ("atet nd", "attend"),
    ("betet r", "better"),
    ("thereafet r", "thereafter"),
    ("batet ry", "battery"),
    ("letet rkenny", "Letterkenny"),
    ("etiquetet", "etiquette"),
    ("trafcfi", "traffic"),
    ("staf.f", "staff"),
    ("staf f", "staff"),
)

# Each source pattern compiled with re.escape, sorted longest first at
# import time so longer patterns claim their span before shorter ones.
_COMPILED = tuple(
    (re.compile(re.escape(before), re.IGNORECASE), after)
    for before, after in sorted(REPAIRS, key=lambda pair: -len(pair[0]))
)

_URL_MARKERS = ("://", "@")
_DOMAIN_LIKE_RE = re.compile(r"\w+\.\w+")
_SUSPICIOUS_RE = re.compile(r"\b[A-Za-z]{3,}(?:et|of|ef|oi|ni|pi)\s[a-z]{1,3}\b")


def _match_case(matched: str, replacement: str) -> str:
    """Return `replacement` carrying the case form of `matched`."""
    if matched.isupper():
        return replacement.upper()
    if matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _is_protected(text: str, start: int, end: int) -> bool:
    r"""True when the match sits inside a URL, e-mail or domain-like token.

    The matched substring is stripped from its surrounding whitespace-delimited
    token before testing: the artefact itself (e.g. "staf.f") matches
    `\w+\.\w+`, so testing the unstripped token would protect every match.
    Only "://", "@" or a domain-like `\w+\.\w+` in the remaining text
    protects the match.
    """
    token_start = start
    while token_start > 0 and not text[token_start - 1].isspace():
        token_start -= 1
    token_end = end
    while token_end < len(text) and not text[token_end].isspace():
        token_end += 1
    remainder = text[token_start:start] + text[end:token_end]
    if any(marker in remainder for marker in _URL_MARKERS):
        return True
    return _DOMAIN_LIKE_RE.search(remainder) is not None


def _find_matches(text: str) -> list[tuple[int, int, str, str]]:
    """Return (start, end, matched, replacement) for every repair in `text`.

    Longest pattern first: a match overlapping an already-accepted span is
    skipped, so "staf frespect" suppresses the "staf f" inside it. Guarded
    matches are skipped without claiming their span. Results are ordered by
    position.
    """
    claimed: list[tuple[int, int]] = []
    found: list[tuple[int, int, str, str]] = []
    for pattern, replacement in _COMPILED:
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            if any(start < c_end and c_start < end
                   for c_start, c_end in claimed):
                continue
            if _is_protected(text, start, end):
                continue
            claimed.append((start, end))
            found.append((start, end, match.group(0), replacement))
    found.sort()
    return found


def repair_text(text: str) -> str:
    """Return `text` with every mapped artefact repaired, case preserved."""
    result = text
    for start, end, matched, replacement in reversed(_find_matches(text)):
        result = result[:start] + _match_case(matched, replacement) + result[end:]
    return result


def find_repairs(text: str) -> list[dict]:
    """Return every non-overlapping repair `repair_text` would apply.

    Each item is `{"before", "after", "start", "end"}` with the match offsets
    in the original text and the case-matched replacement.
    """
    return [
        {"before": matched, "after": _match_case(matched, replacement),
         "start": start, "end": end}
        for start, end, matched, replacement in _find_matches(text)
    ]


def find_suspicious(text: str) -> list[dict]:
    """Return artefact-shaped spans in `text` not covered by `REPAIRS`.

    Each item is `{"text", "start", "end"}`. This is a review aid for a
    human, not an auto-fixer: flagged spans are never rewritten, only read.
    """
    covered = {before.lower() for before, _ in REPAIRS}
    results = []
    for match in _SUSPICIOUS_RE.finditer(text):
        if match.group(0).lower() in covered:
            continue
        results.append(
            {"text": match.group(0), "start": match.start(), "end": match.end()})
    return results

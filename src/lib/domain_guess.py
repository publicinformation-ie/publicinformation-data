"""Deterministic website-domain guesses from a public body's name.

Guesses are cheap: most die at the DNS stage of website_probe, and survivors
still have to pass the judge.
"""
import re
import unicodedata

MAX_GUESSES = 6
_PAREN_RE = re.compile(r"\(.*?\)")
_SUFFIX_RE = re.compile(
    r"\b(designated activity company|company limited by guarantee|clg|ltd|limited|dac|plc|"
    r"teo|teoranta|cpt|uc)\b\.?",
    re.IGNORECASE,
)
_ACRONYM_SKIP = {"and", "of", "the", "for", "in", "on", "to", "na", "an"}


def _words(name: str) -> list[str]:
    name = _PAREN_RE.sub(" ", name)
    name = _SUFFIX_RE.sub(" ", name)
    name = name.replace("&", " and ")
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", folded.lower())


def guess_domains(name: str) -> list[str]:
    words = _words(name or "")
    if not words:
        return []
    acronym = "".join(w[0] for w in words if w not in _ACRONYM_SKIP)
    slug = "".join(words)
    domains = []
    if 3 <= len(acronym) <= 6 and len(words) > 1:
        domains.append(f"{acronym}.ie")
    if 3 <= len(slug) <= 40:
        domains += [f"{slug}.ie", f"{slug}.com", f"{slug}.org"]
    seen, out = set(), []
    for d in domains:
        if d not in seen:
            seen.add(d)
            out.append(f"https://{d}/")
    return out[:MAX_GUESSES]

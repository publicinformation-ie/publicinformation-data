"""Fuzzy name-matching helpers for resolving an external list of body names
(e.g. gov.ie's Who Does What campaign, data.gov.ie's organisation list)
against the canonical public-bodies list. Shared by wdw_pipeline and
datagovie_pipeline so there is one implementation instead of two copies
that can drift apart.
"""
import re
from difflib import SequenceMatcher
from pathlib import Path

from lib.file_utils import read_json

MATCH_THRESHOLD = 0.90

_SUFFIX_RE = re.compile(
    r"\s*\b(clg|ltd|limited|dac|plc|teo|teoranta|cpt|uc)\b\.?\s*$",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\s*\(.*?\)\s*")
_WS_RE = re.compile(r"\s+")


def normalise(name: str) -> str:
    name = _PAREN_RE.sub(" ", name)
    name = _SUFFIX_RE.sub("", name)
    return _WS_RE.sub(" ", name).strip().lower()


def best_match(query_norm: str, candidates: list) -> tuple:
    """Return (public_body_id, score) for the best match at or above
    MATCH_THRESHOLD, else (None, best_score).

    candidates: list of (public_body_id, name, normalised_name)
    """
    best_score = 0.0
    best_id = None
    for public_body_id, _, norm in candidates:
        score = SequenceMatcher(None, query_norm, norm).ratio()
        if score > best_score:
            best_score = score
            best_id = public_body_id
    if best_score >= MATCH_THRESHOLD:
        return best_id, best_score
    return None, best_score


def load_candidates(candidates_path: Path) -> list:
    data = read_json(candidates_path)
    bodies = data.get("results") or data.get("public_bodies", [])
    return [(b["public_body_id"], b["name"], normalise(b["name"])) for b in bodies]

"""Deterministic guards for pathological minutes documents.

Stage 1 runs before any LLM call and skips extreme Chief Executive
recommendation schedules (for example a 400-page development-plan adoption
schedule where every material alteration is phrased as a resolution).

Stage 2 runs after extraction and quarantines a document whose motion list is
a procedural acceptance dump, even when the pre-filter did not catch it.

Both guards fail closed: the caller emits ``motions: null`` plus a reviewable
reason, never a partial motion list.
"""
from __future__ import annotations

import re
from collections import Counter

# Stage 1: only documents far outside the normal range.  The known Kildare
# CDP adoption schedule has 890 PMA mentions, 541 "accept the Chief Executive"
# mentions and 639 "on the proposal by" mentions; the next-highest document in
# the corpus has 122 PMA mentions.
PRE_FILTER_MIN_PMA = 500
PRE_FILTER_MIN_ACCEPT_CE = 200
PRE_FILTER_MIN_ON_PROPOSAL = 200

# Stage 2: a normal meeting can have 100+ motions, but not with this much
# procedural acceptance language and this little proposer/seconder variety.
POST_FILTER_MIN_MOTIONS = 100
POST_FILTER_MIN_ACCEPT_CE_RATIO = 0.80
POST_FILTER_MIN_PMA_RATIO = 0.80
POST_FILTER_MIN_ACTOR_RATIO = 0.80

_PMA_RE = re.compile(r"proposed\s+material\s+alteration\s+no\.?", re.I)
_ACCEPT_CE_RE = re.compile(r"accept\s+the\s+chief\s+executive", re.I)
_ON_PROPOSAL_RE = re.compile(r"on\s+the\s+proposal\s+by", re.I)
_PMA_MOTION_RE = re.compile(
    r"\bPMA\b|material\s+alteration|consequential\s+amendment", re.I
)


def _count(pattern: re.Pattern, text: str) -> int:
    return len(pattern.findall(text or ""))


def detect_ce_schedule(text: str | None) -> dict | None:
    """Return evidence when text is an extreme CE recommendation schedule.

    The thresholds are intentionally extreme so ordinary plan meetings with a
    few material alterations are not caught.
    """
    text = text or ""
    pma = _count(_PMA_RE, text)
    accept_ce = _count(_ACCEPT_CE_RE, text)
    on_proposal = _count(_ON_PROPOSAL_RE, text)
    if (
        pma >= PRE_FILTER_MIN_PMA
        and accept_ce >= PRE_FILTER_MIN_ACCEPT_CE
        and on_proposal >= PRE_FILTER_MIN_ON_PROPOSAL
    ):
        return {
            "proposed_material_alteration_count": pma,
            "accept_chief_executive_count": accept_ce,
            "on_the_proposal_count": on_proposal,
            "chars": len(text),
        }
    return None


def _top_actor(motions: list[dict], field: str) -> tuple[str, int]:
    values = Counter(
        (motion.get(field) or "").strip()
        for motion in motions
        if (motion.get(field) or "").strip()
    )
    return values.most_common(1)[0] if values else ("", 0)


def detect_procedural_dump(motions: list[dict] | None) -> dict | None:
    """Return evidence when extracted motions are a procedural acceptance dump."""
    motions = motions or []
    total = len(motions)
    if total < POST_FILTER_MIN_MOTIONS:
        return None

    texts = [(motion.get("motion_text") or "") for motion in motions]
    accept_ce = sum(1 for text in texts if _ACCEPT_CE_RE.search(text))
    pma = sum(1 for text in texts if _PMA_MOTION_RE.search(text))
    top_proposer, top_proposer_count = _top_actor(motions, "proposer")
    top_seconder, top_seconder_count = _top_actor(motions, "seconder")

    accept_ratio = accept_ce / total
    pma_ratio = pma / total
    proposer_ratio = top_proposer_count / total
    seconder_ratio = top_seconder_count / total

    if not (
        accept_ratio >= POST_FILTER_MIN_ACCEPT_CE_RATIO
        and pma_ratio >= POST_FILTER_MIN_PMA_RATIO
        and proposer_ratio >= POST_FILTER_MIN_ACTOR_RATIO
        and seconder_ratio >= POST_FILTER_MIN_ACTOR_RATIO
    ):
        return None

    return {
        "motion_count": total,
        "accept_chief_executive_count": accept_ce,
        "accept_chief_executive_ratio": round(accept_ratio, 4),
        "pma_or_alteration_count": pma,
        "pma_or_alteration_ratio": round(pma_ratio, 4),
        "top_proposer": top_proposer,
        "top_proposer_count": top_proposer_count,
        "top_proposer_ratio": round(proposer_ratio, 4),
        "top_seconder": top_seconder,
        "top_seconder_count": top_seconder_count,
        "top_seconder_ratio": round(seconder_ratio, 4),
    }

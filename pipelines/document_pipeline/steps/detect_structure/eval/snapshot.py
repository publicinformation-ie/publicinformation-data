"""Snapshot fingerprinting, shared by `make_input.py` and `score.py`.

The detection snapshot (`input.json`) records, per document, a hash of exactly
what `detect_structure` reads: each page's spans plus the PDF outline. `score.py`
recomputes the same hash over live `extract_pages` output to warn when the
snapshot has drifted. Keeping the hash definition here means the writer and the
checker cannot disagree about what "the same input" means.

Run nothing from this module directly; import it.
"""
import hashlib
import json


def canonical_json(value) -> str:
    """Stable JSON for hashing: sorted keys, no insignificant whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _page_sort_key(page: dict) -> int:
    return int(page.get("number") or 0)


def spans_sha256(pages: list, outline=None) -> str:
    """sha256 over a document's spans and outline in canonical form.

    Page width/height are deliberately excluded: they are not read by
    `detect_structure`'s strategies, so a re-extraction that changes only the
    mediabox should not look like drift. Page number and spans are included
    because a moved or re-ordered span does change detection.
    """
    payload = {
        "outline": outline or [],
        "pages": [
            {"number": page.get("number"), "spans": page.get("spans") or []}
            for page in sorted(pages, key=_page_sort_key)
        ],
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

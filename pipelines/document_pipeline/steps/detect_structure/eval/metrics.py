"""Accuracy metrics for the document chapter split.

Pure functions over two chapter lists: the gold list (from `gold.py`) and the
predicted list (from a detected tree). No file I/O, no detection — that keeps
the scoring rules testable in isolation and identical wherever they are used
(detector scoring, baseline diff, gold re-annotation).

Definitions follow the `document-structure-evaluation` spec:

* a predicted chapter is a node with no resolvable parent — the definition the
  published bundles use;
* boundaries are matched one-to-one in document order by page, exactly or
  within ±1, by a longest-common-subsequence alignment;
* a page is correctly attributed when its predicted chapter is *exactly*
  matched to the gold chapter that contains it, with front matter treated as a
  chapter on both sides;
* titles are compared after normalisation, with the gold TOC wording as the
  reference.
"""
try:  # imported as a module from the test suite
    from .gold import normalise_title
except ImportError:  # run as a script from score.py
    from gold import normalise_title

EXACT = "exact"
TOLERANT = "tolerant"


def _field(node, name, default=None):
    if isinstance(node, dict):
        return node.get(name, default)
    return getattr(node, name, default)


def predicted_chapters(nodes) -> list:
    """The published chapter list: nodes with no resolvable parent.

    A node is a chapter when it has no parent, or when its `parent` slug is not
    in the tree (an orphaned section — the bundles publish those as chapters
    too). Returned in document order, as `{title, slug, page}`.
    """
    nodes = list(nodes or [])
    slugs = {_field(node, "slug") for node in nodes}
    chapters = [
        {"title": _field(node, "title") or "",
         "slug": _field(node, "slug"),
         "page": int(_field(node, "start_page") or 1)}
        for node in nodes
        if _field(node, "parent") is None or _field(node, "parent") not in slugs
    ]
    return sorted(chapters, key=lambda c: c["page"])


def align(gold: list, predicted: list, tolerance: int = 0) -> list:
    """One-to-one monotonic pairs `(gold_index, predicted_index)` by page.

    Longest-common-subsequence alignment over the two page sequences, where a
    pair counts only when the pages are within `tolerance`. Order is preserved
    and ties prefer the earlier pairing, so the result is deterministic.
    """
    n, m = len(gold), len(predicted)
    match = [[abs(int(g["pdf_page"]) - int(p["page"])) <= tolerance
              for p in predicted] for g in gold]

    # f[i][j] is the best number of pairs from gold[i:] and predicted[j:].
    f = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best = max(f[i + 1][j], f[i][j + 1])
            if match[i][j]:
                best = max(best, 1 + f[i + 1][j + 1])
            f[i][j] = best

    pairs = []
    i = j = 0
    while i < n and j < m:
        if match[i][j] and 1 + f[i + 1][j + 1] == f[i][j]:
            pairs.append((i, j))
            i += 1
            j += 1
        elif f[i + 1][j] == f[i][j]:
            i += 1
        else:
            j += 1
    return pairs


def _prf(matched: int, gold_n: int, predicted_n: int) -> dict:
    precision = matched / predicted_n if predicted_n else 0.0
    recall = matched / gold_n if gold_n else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"matched": matched, "precision": precision, "recall": recall, "f1": f1}


def _page_owners(chapters: list, page_count: int, page_key: str) -> list:
    """`owner[page]` (1-indexed list, index 0 unused) -> chapter index or None.

    A page belongs to the last chapter that starts at or before it. Pages
    before the first chapter are front matter (None).
    """
    owner = [None] * (page_count + 1)
    for index, chapter in enumerate(chapters):
        start = int(chapter[page_key])
        for page in range(max(start, 1), page_count + 1):
            owner[page] = index
    return owner


def score(gold: list, predicted: list, page_count: int) -> dict:
    """Score one document's predicted chapters against its gold chapters."""
    page_count = int(page_count or 0)
    exact_pairs = align(gold, predicted, tolerance=0)
    tolerant_pairs = align(gold, predicted, tolerance=1)
    exact_set = set(exact_pairs)

    gold_owner = _page_owners(gold, page_count, "pdf_page")
    pred_owner = _page_owners(predicted, page_count, "page")
    pages_correct = 0
    for page in range(1, page_count + 1):
        gold_index, pred_index = gold_owner[page], pred_owner[page]
        if gold_index is None and pred_index is None:
            pages_correct += 1
        elif gold_index is not None and pred_index is not None:
            if (gold_index, pred_index) in exact_set:
                pages_correct += 1

    titles_correct = sum(
        1 for gold_index, pred_index in exact_pairs
        if normalise_title(predicted[pred_index]["title"])
        == normalise_title(gold[gold_index]["title"]))

    title_accuracy = (titles_correct / len(exact_pairs)) if exact_pairs else None
    fully_correct = (bool(gold) and len(exact_pairs) == len(gold)
                     and len(predicted) == len(gold)
                     and titles_correct == len(exact_pairs))

    return {
        "gold_chapters": len(gold),
        "predicted_chapters": len(predicted),
        "exact": _prf(len(exact_pairs), len(gold), len(predicted)),
        "tolerant": _prf(len(tolerant_pairs), len(gold), len(predicted)),
        "page_count": page_count,
        "pages_correct": pages_correct,
        "page_accuracy": (pages_correct / page_count) if page_count else 0.0,
        "matched_pairs": len(exact_pairs),
        "titles_correct": titles_correct,
        "title_accuracy": title_accuracy,
        "fully_correct": fully_correct,
    }


def disagreements(gold: list, predicted: list) -> list:
    """Human-readable list of chapters the two lists disagree about.

    Used by gold-versus-gold comparison (re-annotation), where the interest is
    not only the score but *which* decisions differed.
    """
    exact_pairs = align(gold, predicted, tolerance=0)
    paired_gold = {i for i, _ in exact_pairs}
    paired_pred = {j for _, j in exact_pairs}
    tolerant_pairs = align(gold, predicted, tolerance=1)
    tolerant_near = {(i, j) for i, j in tolerant_pairs if abs(
        int(gold[i]["pdf_page"]) - int(predicted[j]["page"])) == 1}

    items = []
    for gold_index, gold_chapter in enumerate(gold):
        if gold_index in paired_gold:
            continue
        near = [(i, j) for i, j in tolerant_near if i == gold_index]
        if near:
            _, pred_index = near[0]
            items.append(
                f"off by one: gold {gold_chapter['title']!r} on page "
                f"{gold_chapter['pdf_page']}, other on page {predicted[pred_index]['page']}")
        else:
            items.append(
                f"only in gold: {gold_chapter['title']!r} on page {gold_chapter['pdf_page']}")
    for pred_index, pred_chapter in enumerate(predicted):
        if pred_index in paired_pred:
            continue
        if any(j == pred_index for _, j in tolerant_near):
            continue  # already reported as an off-by-one against its gold chapter
        items.append(
            f"only in the other list: {pred_chapter['title']!r} on page {pred_chapter['page']}")
    for gold_index, pred_index in exact_pairs:
        gold_title = normalise_title(gold[gold_index]["title"])
        other_title = normalise_title(predicted[pred_index]["title"])
        if gold_title != other_title:
            items.append(
                f"title differs on page {gold[gold_index]['pdf_page']}: "
                f"{gold[gold_index]['title']!r} vs {predicted[pred_index]['title']!r}")
    return items


def gold_as_predicted(gold: list) -> list:
    """Gold chapters in predicted-chapter shape, for gold-versus-gold scoring."""
    return [{"title": chapter["title"], "slug": None, "page": int(chapter["pdf_page"])}
            for chapter in gold]


def _mean(values: list):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def summarise(scores: list) -> dict:
    """Corpus summary: macro (per-document mean) and micro (pooled) averages."""
    scores = list(scores or [])
    gold_n = sum(s["gold_chapters"] for s in scores)
    pred_n = sum(s["predicted_chapters"] for s in scores)
    matched_exact = sum(s["exact"]["matched"] for s in scores)
    matched_tolerant = sum(s["tolerant"]["matched"] for s in scores)
    pages = sum(s["page_count"] for s in scores)
    pages_correct = sum(s["pages_correct"] for s in scores)
    pairs = sum(s["matched_pairs"] for s in scores)
    titles = sum(s["titles_correct"] for s in scores)

    def macro(path):
        return _mean([_get(s, path) for s in scores])

    macro_values = {
        "boundary_precision_exact": macro("exact.precision"),
        "boundary_recall_exact": macro("exact.recall"),
        "boundary_f1_exact": macro("exact.f1"),
        "boundary_precision_tolerant": macro("tolerant.precision"),
        "boundary_recall_tolerant": macro("tolerant.recall"),
        "boundary_f1_tolerant": macro("tolerant.f1"),
        "page_accuracy": macro("page_accuracy"),
        "title_accuracy": macro("title_accuracy"),
    }

    micro_values = {
        "boundary_precision_exact": (matched_exact / pred_n) if pred_n else 0.0,
        "boundary_recall_exact": (matched_exact / gold_n) if gold_n else 0.0,
        "boundary_f1_exact": _prf(matched_exact, gold_n, pred_n)["f1"],
        "boundary_precision_tolerant": (matched_tolerant / pred_n) if pred_n else 0.0,
        "boundary_recall_tolerant": (matched_tolerant / gold_n) if gold_n else 0.0,
        "boundary_f1_tolerant": _prf(matched_tolerant, gold_n, pred_n)["f1"],
        "page_accuracy": (pages_correct / pages) if pages else 0.0,
        "title_accuracy": (titles / pairs) if pairs else None,
    }

    return {
        "documents": len(scores),
        "fully_correct": sum(1 for s in scores if s["fully_correct"]),
        "macro": macro_values,
        "micro": micro_values,
    }


def _get(mapping: dict, path: str):
    value = mapping
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
        if value is None:
            return None
    return value


METRIC_KEYS = (
    "boundary_precision_exact",
    "boundary_recall_exact",
    "boundary_f1_exact",
    "boundary_precision_tolerant",
    "boundary_recall_tolerant",
    "boundary_f1_tolerant",
    "page_accuracy",
    "title_accuracy",
)

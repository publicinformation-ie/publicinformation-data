"""End-to-end tests for the accuracy report (`eval/score.py`)."""
import json
import os

import pytest

from steps.detect_structure.eval import gold, score
from steps.detect_structure.eval.snapshot import spans_sha256


def _page(number, *lines):
    return {"number": number, "width": 595.0, "height": 842.0,
            "spans": [{"text": line, "font": "Helvetica", "size": 12.0,
                       "bbox": [72.0, 100.0 + i * 20, 500.0, 112.0 + i * 20],
                       "block": i, "line": 0, "span": 0}
                      for i, line in enumerate(lines)]}


def _document(slug, chapters, page_count=6, source_sha="a" * 64, sha=None):
    """A snapshot document whose outline places `chapters` (title, page)."""
    pages = [_page(1, "Cover")]
    for title, page in chapters:
        pages.append(_page(page, title))
    for number in range(len(pages) + 1, page_count + 1):
        pages.append(_page(number, f"Body text on page {number}."))
    pages = sorted({p["number"]: p for p in pages}.values(), key=lambda p: p["number"])
    # Pad any page numbers the chapter pages skipped so the document is dense.
    present = {p["number"] for p in pages}
    for number in range(1, page_count + 1):
        if number not in present:
            pages.append(_page(number, f"Body text on page {number}."))
    pages.sort(key=lambda p: p["number"])
    outline = [{"level": 1, "title": title, "page": page, "y": 10.0}
               for title, page in chapters]
    if sha is None:
        sha = spans_sha256(pages, outline)
    return {"doc_slug": slug, "page_count": page_count, "outline": outline,
            "spans_sha256": sha, "source_sha256": source_sha, "pages": pages}


def _gold(slug, chapters, reviewed=True, source_sha="a" * 64, notes=""):
    return {
        "doc_slug": slug, "pdf_sha256": source_sha, "toc_pdf_pages": [1],
        "annotator": "test", "annotated_on": "2026-11-22", "reviewed": reviewed,
        "notes": notes,
        "chapters": [{"title": title, "printed_page": str(page), "pdf_page": page}
                     for title, page in chapters],
    }


def _write_snapshot(path, documents):
    path.write_text(json.dumps({
        "metadata": {"step": "extract_pages", "doc_count": len(documents)},
        "documents": documents,
    }), encoding="utf-8")


def _write_gold(dirpath, data):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f"{data['doc_slug']}.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    snapshot_docs = [
        _document("plain-doc", [("Chapter One", 2), ("Chapter Two", 3)]),
        _document("overridden-doc", [("Chapter One", 2), ("Chapter Two", 3)]),
    ]
    snapshot_path = tmp_path / "input.json"
    _write_snapshot(snapshot_path, snapshot_docs)
    gold_dir = tmp_path / "gold"
    _write_gold(gold_dir, _gold("plain-doc", [("Chapter One", 2), ("Chapter Two", 3)]))
    _write_gold(gold_dir, _gold("overridden-doc",
                                [("Introduction", 2), ("Conclusions", 3)]))
    monkeypatch.setattr(score, "INPUT_PATH", snapshot_path)
    monkeypatch.setattr(score, "BASELINE_PATH", tmp_path / "baseline.json")
    return {"tmp": tmp_path, "snapshot": snapshot_path, "gold_dir": gold_dir,
            "baseline": tmp_path / "baseline.json", "snapshot_docs": snapshot_docs}


def _report(workspace, overrides=None):
    source = score.load_snapshot(workspace["snapshot"])
    gold_load = gold.load_gold(workspace["gold_dir"])
    if overrides is None:
        overrides = {"overridden-doc": [
            {"slug": "chapter-one", "title": "Introduction"},
            {"slug": "chapter-two", "title": "Conclusions"},
        ]}
    return score.build_report(source, gold_load, overrides)


# --------------------------------------------------------------------------
# 4.1 Report: raw and post-override scoring
# --------------------------------------------------------------------------

def test_report_scores_raw_and_post_override_for_an_overridden_document(workspace):
    report = _report(workspace)

    by_slug = {doc["doc_slug"]: doc for doc in report["documents"]}
    plain = by_slug["plain-doc"]
    assert plain["raw"]["fully_correct"] is True
    assert plain["post_override"] is None        # no override entries
    assert plain["method"] == "outline"

    overridden = by_slug["overridden-doc"]
    assert overridden["has_overrides"] is True
    assert overridden["raw"]["title_accuracy"] == 0.0     # detector titles differ from gold
    assert overridden["raw"]["fully_correct"] is False
    assert overridden["post_override"]["title_accuracy"] == 1.0
    assert overridden["post_override"]["fully_correct"] is True

    assert report["summary"]["raw"]["documents"] == 2
    assert report["summary"]["raw"]["fully_correct"] == 1
    assert report["summary"]["post_override"]["fully_correct"] == 2


def test_report_prints_both_rows_for_an_overridden_document(workspace, capsys, monkeypatch):
    monkeypatch.setattr(score, "load_overrides", lambda step_dir: {"overridden-doc": [
        {"slug": "chapter-one", "title": "Introduction"},
        {"slug": "chapter-two", "title": "Conclusions"},
    ]})
    code = score.main(["--gold", str(workspace["gold_dir"]),
                       "--baseline", str(workspace["baseline"])])

    assert code == 0
    out = capsys.readouterr().out
    rows = [line for line in out.splitlines() if line.startswith("overridden-doc")]
    assert len(rows) == 2, out
    assert any(" raw " in row for row in rows)
    assert any("post=publish" in row for row in rows)
    assert rows[0].rstrip().endswith("no")
    assert rows[1].rstrip().endswith("yes")


# --------------------------------------------------------------------------
# 4.2 Live mode, drift and gold/PDF mismatch
# --------------------------------------------------------------------------

def _write_live_output(tmp_path, documents):
    pages_dir = tmp_path
    results = []
    for document in documents:
        entries = []
        for page in document["pages"]:
            name = f"pages/{document['doc_slug']}/{page['number']:03d}.json"
            path = pages_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(page), encoding="utf-8")
            entries.append({"number": page["number"], "file": name})
        results.append({"doc_slug": document["doc_slug"],
                        "page_count": document["page_count"],
                        "outline": document["outline"], "pages": entries})
    output = tmp_path / "extract_pages_output.json"
    output.write_text(json.dumps({"metadata": {}, "results": results}), encoding="utf-8")
    return output


def test_live_mode_warns_when_live_output_drifted_from_the_snapshot(workspace, monkeypatch):
    tmp = workspace["tmp"]
    output = _write_live_output(tmp, workspace["snapshot_docs"])
    fetch = tmp / "fetch.json"
    fetch.write_text(json.dumps({"results": [{"doc_slug": "plain-doc", "source_sha256": "a" * 64},
                                             {"doc_slug": "overridden-doc",
                                              "source_sha256": "a" * 64}]}), encoding="utf-8")
    monkeypatch.setattr(score, "EXTRACT_PAGES_OUTPUT", output)
    monkeypatch.setattr(score, "FETCH_PDFS_OUTPUT", fetch)

    snapshot = score.load_snapshot(workspace["snapshot"])
    snapshot["documents"]["plain-doc"]["spans_sha256"] = "0" * 64
    source = score.load_live(snapshot)

    assert source["kind"] == "live"
    assert [entry["doc_slug"] for entry in source["drifted"]] == ["plain-doc"]
    printed = score.format_drift({"source": source})
    assert "drifted from the snapshot" in printed
    assert "plain-doc" in printed
    # The report still scores the source it was asked to score.
    report = score.build_report(source, gold.load_gold(workspace["gold_dir"]), {})
    assert len(report["documents"]) == 2


def test_gold_pdf_mismatch_excludes_the_document(workspace, monkeypatch):
    gold_dir = workspace["tmp"] / "mismatch-gold"
    _write_gold(gold_dir, _gold("plain-doc", [("Chapter One", 2), ("Chapter Two", 3)],
                                source_sha="b" * 64))

    report = score.build_report(score.load_snapshot(workspace["snapshot"]),
                                gold.load_gold(gold_dir), {})

    assert report["documents"] == []
    assert report["excluded"][0]["reason"] == "gold/PDF mismatch"
    assert "page numbers may be stale" in report["excluded"][0]["detail"]


def test_check_gold_reports_drafts_and_their_warnings(workspace, capsys):
    # A draft with a page-offset jump: the check must show it even though the
    # report itself would exclude the unreviewed file.
    draft = _gold("plain-doc", [("Chapter One", 2), ("Chapter Two", 3)],
                  reviewed=False)
    _write_gold(workspace["gold_dir"], draft)

    code = score.main(["--gold", str(workspace["gold_dir"]), "--check-gold"])

    out = capsys.readouterr().out
    assert code == 0
    assert "plain-doc: valid, DRAFT (reviewed is not true)" in out
    assert "overridden-doc: valid, reviewed" in out


def test_check_gold_fails_on_a_malformed_file(workspace, capsys):
    broken = _gold("broken-doc", [("Chapter One", 2)])
    del broken["pdf_sha256"]
    _write_gold(workspace["gold_dir"], broken)

    code = score.main(["--gold", str(workspace["gold_dir"]), "--check-gold"])

    out = capsys.readouterr().out
    assert code == 1
    assert "broken-doc: MALFORMED" in out


# --------------------------------------------------------------------------
# 4.3 Baseline diff
# --------------------------------------------------------------------------

def _score(page_accuracy, exact_f1):
    return {"gold_chapters": 2, "predicted_chapters": 2,
            "exact": {"matched": 2, "precision": exact_f1, "recall": exact_f1, "f1": exact_f1},
            "tolerant": {"matched": 2, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "page_count": 100, "pages_correct": int(page_accuracy * 100),
            "page_accuracy": page_accuracy, "matched_pairs": 2, "titles_correct": 2,
            "title_accuracy": 1.0, "fully_correct": False}


def test_baseline_diff_shows_improvement_and_regression_per_document():
    baseline = {"documents": [
        {"doc_slug": "improved", "method": "toc", "raw": _score(0.5, 0.5)},
        {"doc_slug": "regressed", "method": "toc", "raw": _score(0.9, 0.9)},
    ]}
    report = {"documents": [
        {"doc_slug": "improved", "method": "toc", "raw": _score(0.8, 0.8),
         "post_override": None},
        {"doc_slug": "regressed", "method": "toc", "raw": _score(0.6, 0.6),
         "post_override": None},
    ]}

    printed = score.format_baseline_diff(report, baseline)

    assert "improved [raw]" in printed and "(+0.30)" in printed
    assert "regressed [raw]" in printed and "(-0.30)" in printed


def test_refresh_baseline_writes_and_a_plain_run_keeps_it(workspace, capsys):
    code = score.main(["--gold", str(workspace["gold_dir"]),
                       "--baseline", str(workspace["baseline"]), "--refresh-baseline"])
    assert code == 0
    baseline = json.loads(workspace["baseline"].read_text(encoding="utf-8"))
    assert [doc["doc_slug"] for doc in baseline["documents"]] == ["overridden-doc", "plain-doc"]
    assert baseline["summary"]["raw"]["documents"] == 2

    before = workspace["baseline"].stat().st_mtime_ns
    code = score.main(["--gold", str(workspace["gold_dir"]),
                       "--baseline", str(workspace["baseline"])])
    assert code == 0
    assert workspace["baseline"].stat().st_mtime_ns == before
    assert "change from baseline" in capsys.readouterr().out


# --------------------------------------------------------------------------
# 4.4 Gold-versus-gold comparison
# --------------------------------------------------------------------------

def test_compare_gold_reports_a_moved_boundary_and_a_changed_title(workspace):
    tmp = workspace["tmp"]
    first = tmp / "first.json"
    second = tmp / "second.json"
    first.write_text(json.dumps(_gold("plain-doc",
                                      [("Chapter One", 2), ("Chapter Two", 3)])),
                     encoding="utf-8")
    second.write_text(json.dumps(_gold("plain-doc",
                                       [("Chapter One and Context", 2), ("Chapter Two", 4)])),
                      encoding="utf-8")

    printed = score.compare_gold(first, second)

    assert "off by one" in printed
    assert "title differs" in printed
    assert "exact boundary" in printed
    assert "page attribution" in printed


# --------------------------------------------------------------------------
# 4.5 Read-only
# --------------------------------------------------------------------------

def _tree_state(*directories):
    state = {}
    for directory in directories:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [name for name in dirs if name != "__pycache__"]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                path = os.path.join(root, name)
                stat = os.stat(path)
                state[path] = (stat.st_mtime_ns, stat.st_size)
    return state


def test_plain_run_writes_nothing(workspace, capsys, monkeypatch):
    step_dir = score._STEP_DIR
    eval_dir = score._HERE
    before = _tree_state(step_dir, eval_dir)

    code = score.main(["--gold", str(workspace["gold_dir"]),
                       "--baseline", str(workspace["baseline"])])

    assert code == 0
    assert _tree_state(step_dir, eval_dir) == before

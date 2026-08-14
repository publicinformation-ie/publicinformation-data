"""End-to-end test: runs all eight document_pipeline steps as real
subprocesses against a `tmp_path` copy of the pipeline, using
`--local-pdf` to substitute the committed fixture PDF for a network
fetch, and asserts the published bundle matches
`docs/superpowers/specs/2026-08-10-document-bundle-contract.md`.

Two things this file deliberately does *not* do:

* It does not import step internals to drive the run — every step is
  invoked exactly the way a human or `process.py` would invoke it, as a
  subprocess with `--input`/`--output`. That is the only way to catch a
  wiring bug (a wrong sibling-directory lookup, a CLI flag typo) that an
  in-process call graph would paper over.
* It does not prove "no network access" by inspecting the subprocess run
  itself — a monkeypatch in this process cannot reach into a child
  process's `lib.http_utils`. Instead `test_local_pdf_path_never_touches_the_network`
  proves the same guarantee at the unit level: `--local-pdf` rewrites a
  document's URL to a `file://` URI, and `steps.fetch_pdfs.process.download`
  branches on `file://` *before* it ever calls `lib.http_utils.fetch`. That
  branch is exactly what `fixture_run` below exercises for real, end to end;
  this second test is what lets us claim it never touches the network.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve()
while not (REPO_ROOT / ".git").exists():
    REPO_ROOT = REPO_ROOT.parent

PIPELINE_SRC = REPO_ROOT / "pipelines" / "document_pipeline"
FIXTURE_PDF = PIPELINE_SRC / "tests" / "fixtures" / "fixture.pdf"

STEPS = ("find_plan_pdfs", "fetch_pdfs", "extract_pages", "detect_structure", "extract_figures",
         "clean_text", "assemble_sections", "publish_bundles")

DOC_SLUG = "fixture-doc"

DOCUMENTS_YML = f"""\
documents:
  - doc_slug: {DOC_SLUG}
    title: "Fixture Transport Strategy"
    url: "https://example.org/fixture.pdf"
    publisher: "Test Authority"
    public_body_id: 1570
    published_date: "2023-01-19"
"""

EMPTY_INPUT_PLANS_MD = "# Current and Future Plans for all government departments in Ireland\n"

# Anything a prior run (of the real pipeline, against the real documents.yml)
# may have left behind in the copied step directories. Deleted before the
# fixture run so this test never inherits another document's leftovers.
_GENERATED_FILES = ("output.json", "errors.json", "pipeline-status.json", "dirty_ids.json")
_GENERATED_DIRS = ("pdfs", "pages", "sections", "assets", "contact-sheets")


def _clean_step_dir(step_dir: Path) -> None:
    for name in _GENERATED_FILES:
        (step_dir / name).unlink(missing_ok=True)
    for name in _GENERATED_DIRS:
        shutil.rmtree(step_dir / name, ignore_errors=True)
    shutil.rmtree(step_dir / "__pycache__", ignore_errors=True)


@pytest.fixture(scope="session")
def fixture_run(tmp_path_factory):
    """Copy pipelines/document_pipeline/ into a session-scoped tmp dir, point
    it at a one-document documents.yml keyed to the fixture PDF, and run all
    eight steps as subprocesses with --force --local-pdf.

    Returns the *assemble_sections* step directory (a Path), so callers that
    only need the produced Markdown — the golden-file test — can do
    `fixture_run / "sections" / ...` directly. Callers that need the
    published bundle derive `public/documents/` from
    `fixture_run.parents[2] / "public" / "documents"` (see `public_root`
    below); the layout is fixed by how this fixture lays out `tmp_root`.
    """
    tmp_root = tmp_path_factory.mktemp("document_pipeline_e2e")
    pipeline_copy = tmp_root / "document_pipeline"
    shutil.copytree(PIPELINE_SRC, pipeline_copy,
                    ignore=shutil.ignore_patterns("__pycache__"))

    (pipeline_copy / "documents.yml").write_text(DOCUMENTS_YML, encoding="utf-8")
    (pipeline_copy / "input_plans.md").write_text(EMPTY_INPUT_PLANS_MD, encoding="utf-8")

    steps_dir = pipeline_copy / "steps"
    for step in STEPS:
        _clean_step_dir(steps_dir / step)

    public_root = tmp_root / "public" / "documents"

    env = {**os.environ,
           "PYTHONPATH": f"{pipeline_copy}{os.pathsep}{REPO_ROOT / 'src'}"}

    prev_out = None
    input_steps = {"extract_figures": "extract_pages", "clean_text": "extract_pages"}
    for step in STEPS:
        step_dir = steps_dir / step
        out = step_dir / "output.json"
        input_step = input_steps.get(step)
        input_out = (steps_dir / input_step / "output.json") if input_step else prev_out
        cmd = [sys.executable, str(step_dir / "process.py"),
               "--input", str(input_out) if input_out is not None else str(step_dir),
               "--output", str(out), "--force"]
        if step == "fetch_pdfs":
            cmd += ["--local-pdf", f"{DOC_SLUG}={FIXTURE_PDF}"]
        if step == "publish_bundles":
            cmd += ["--public-root", str(public_root)]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert result.returncode == 0, (
            f"step {step!r} exited {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}")
        prev_out = out

    return steps_dir / "assemble_sections"


def _public_root(fixture_run: Path) -> Path:
    # fixture_run == tmp_root/document_pipeline/steps/assemble_sections
    tmp_root = fixture_run.parents[2]
    return tmp_root / "public" / "documents"


def _read_bundle(public_root: Path, doc_slug: str = DOC_SLUG) -> dict[str, bytes]:
    """Return {arcname: bytes} for every member of doc_slug's bundle.tar.gz."""
    data = (public_root / doc_slug / "bundle.tar.gz").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        members = {}
        for member in tar.getmembers():
            extracted = tar.extractfile(member)
            if extracted is not None:
                members[member.name] = extracted.read()
    return members


# --- the real end-to-end assertions --------------------------------------

def test_all_eight_steps_exit_zero(fixture_run):
    # fixture_run's construction already asserts each step's exit code is 0
    # (see the fixture body); reaching this point is the proof.
    assert fixture_run.exists()


def test_index_json_lists_the_fixture_document_with_its_page_count(fixture_run):
    public_root = _public_root(fixture_run)
    index = json.loads((public_root / "index.json").read_text(encoding="utf-8"))
    assert index["failed"] == []
    (entry,) = [d for d in index["documents"] if d["doc_slug"] == DOC_SLUG]
    assert entry["page_count"] == 4


def test_bundle_unpacks_and_every_meta_json_path_resolves(fixture_run):
    public_root = _public_root(fixture_run)
    members = _read_bundle(public_root)

    assert "meta.json" in members
    meta = json.loads(members["meta.json"])

    for chapter in meta["chapters"]:
        for section in chapter["sections"]:
            assert section["file"] in members, (
                f"meta.json references {section['file']!r} which is not in the bundle")
            for asset in section["assets"]:
                asset_path = f"assets/{asset}"
                assert asset_path in members, (
                    f"section {section['slug']!r} references asset {asset!r} "
                    f"which is not in the bundle")


def test_coverage_has_no_gaps_or_overlaps(fixture_run):
    public_root = _public_root(fixture_run)
    members = _read_bundle(public_root)
    meta = json.loads(members["meta.json"])

    assert meta["coverage"]["gaps"] == []
    assert meta["coverage"]["overlaps"] == []


def test_local_pdf_path_never_touches_the_network(tmp_path, monkeypatch):
    """Unit-level proof that --local-pdf's file:// substitution never reaches
    lib.http_utils.fetch — see the module docstring for why this is checked
    separately from the subprocess-based fixture_run above."""
    def _boom(*args, **kwargs):
        raise AssertionError("network access attempted via lib.http_utils.fetch")
    monkeypatch.setattr("lib.http_utils.fetch", _boom)

    from steps.fetch_pdfs.process import download

    dest = tmp_path / "fixture.pdf"
    download(FIXTURE_PDF.resolve().as_uri(), dest)
    assert dest.read_bytes() == FIXTURE_PDF.read_bytes()


# --- the golden-file test --------------------------------------------------

# fetch_pdfs's --local-pdf escape hatch rewrites a document's `url` to the
# resolved, absolute file:// URI of the substituted local file (see
# steps/fetch_pdfs/process.py's _parse_local_pdf_args / main()) — that URI
# bakes in this checkout's absolute path, which differs machine to machine
# and run to run, so it cannot appear verbatim in a golden file committed to
# the repo. `_normalize_source_url` collapses it to a fixed placeholder
# before comparison, the same placeholder the golden file stores; every
# other line — the content this test actually exists to pin — is compared
# byte for byte, unmodified.
_SOURCE_URL_RE = re.compile(r'^source_url: "file://.*"$', re.MULTILINE)
_SOURCE_URL_PLACEHOLDER = 'source_url: "file:///FIXTURE_PDF"'


def _normalize_source_url(markdown: str) -> str:
    return _SOURCE_URL_RE.sub(_SOURCE_URL_PLACEHOLDER, markdown)


def test_first_chapter_markdown_matches_the_golden_file(fixture_run):
    produced = (fixture_run / "sections" / DOC_SLUG /
                "1-first-chapter" / "1-1-introduction.md").read_text(encoding="utf-8")
    golden = (Path(__file__).parent / "golden" /
              "1-first-chapter__1-1-introduction.md").read_text(encoding="utf-8")
    assert _normalize_source_url(produced) == golden

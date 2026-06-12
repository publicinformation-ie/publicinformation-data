import json
import sys
from unittest.mock import patch

from lib.file_utils import read_json, write_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HTML_WITH_DISCLOSURE_LINK = (
    '<html><body><a href="/foi/disclosure/">Disclosure Log</a></body></html>'
)
HTML_NO_DISCLOSURE = "<html><body><p>No disclosure here</p></body></html>"
HTML_WITH_PDF = '<html><body><a href="/disclosures/q1.pdf">Q1</a></body></html>'
HTML_NO_FILES = "<html><body><p>No files here</p></body></html>"


def _make_pipeline(tmp_path, steps):
    pipeline_dir = tmp_path / "foi_pipeline"
    pipeline_dir.mkdir()
    (pipeline_dir / "pipeline.json").write_text(json.dumps({"steps": steps}))
    for step in steps:
        (pipeline_dir / "steps" / step).mkdir(parents=True)
    return pipeline_dir


def _seed_bodies(pipeline_dir, ids):
    fpb = pipeline_dir / "steps" / "find_public_bodies"
    fpb.mkdir(parents=True, exist_ok=True)
    write_json(
        fpb / "output.json",
        {"public_bodies": [{"public_body_id": i} for i in ids]},
    )


# ---------------------------------------------------------------------------
# Test 1: dirty cascade — find_disclosure_pages → find_disclosure_files
# ---------------------------------------------------------------------------

def test_dirty_cascade_targets_single_body(requests_mock, tmp_path, monkeypatch):
    """Step 1 (find_disclosure_pages) writes dirty_ids.json=[1002]; step 2
    (find_disclosure_files) reads it via upstream_dirty_path and evicts only
    1002, leaving 1001 and 1003 untouched."""
    import steps.find_disclosure_pages.process as step1
    import steps.find_disclosure_files.process as step2

    # --- Seed find_disclosure_pages outputs for three bodies ---
    fdp_dir = tmp_path / "find_disclosure_pages"
    fdp_dir.mkdir()

    fdp_output = fdp_dir / "output.json"
    write_json(fdp_output, {
        "metadata": {"step": "find_disclosure_pages"},
        "results": [
            {"public_body_id": 1001, "foi_page_url": "https://a.ie/foi/",
             "disclosure_page_url": "https://a.ie/disc/", "marker": "keep-1001"},
            {"public_body_id": 1002, "foi_page_url": "https://b.ie/foi/",
             "disclosure_page_url": "https://b.ie/disc/", "marker": "stale-1002"},
            {"public_body_id": 1003, "foi_page_url": "https://c.ie/foi/",
             "disclosure_page_url": "https://c.ie/disc/", "marker": "keep-1003"},
        ],
    })

    # Input to step 1 (validate_websites / check_foi_pages style records)
    fdp_input = tmp_path / "step1_input.json"
    write_json(fdp_input, {"results": [
        {"public_body_id": 1001, "foi_page_url": "https://a.ie/foi/"},
        {"public_body_id": 1002, "foi_page_url": "https://b.ie/foi/"},
        {"public_body_id": 1003, "foi_page_url": "https://c.ie/foi/"},
    ]})

    # Mock: only body 1002's URL should be fetched (the others are untouched)
    requests_mock.get("https://b.ie/foi/", text=HTML_WITH_DISCLOSURE_LINK)

    monkeypatch.setattr(step1, "__file__", str(fdp_dir / "process.py"))
    sys.argv = [
        "process.py", "--input", str(fdp_input), "--output", str(fdp_output),
        "--public-body", "1002",
    ]
    step1.main()

    # Verify step 1 produced dirty_ids.json = [1002]
    assert read_json(fdp_dir / "dirty_ids.json") == [1002]

    # Verify step 1 left 1001/1003 untouched in its own output
    s1_results = {r["public_body_id"]: r for r in read_json(fdp_output)["results"]}
    assert s1_results[1001]["marker"] == "keep-1001"
    assert s1_results[1003]["marker"] == "keep-1003"
    assert "marker" not in s1_results[1002] or s1_results[1002]["marker"] != "stale-1002"

    # --- Seed find_disclosure_files output for three bodies ---
    fdf_dir = tmp_path / "find_disclosure_files"
    fdf_dir.mkdir()
    fdf_output = fdf_dir / "output.json"
    write_json(fdf_output, {
        "metadata": {"step": "find_disclosure_files"},
        "results": [
            {"public_body_id": 1001, "file_url": "https://a.ie/a.pdf", "marker": "keep-1001"},
            {"public_body_id": 1002, "file_url": "https://b.ie/old.pdf", "marker": "stale-1002"},
            {"public_body_id": 1003, "file_url": "https://c.ie/c.pdf", "marker": "keep-1003"},
        ],
    })

    # step1 resolved https://b.ie/foi/ + href /foi/disclosure/ → this URL
    requests_mock.get("https://b.ie/foi/disclosure/", text=HTML_WITH_PDF)

    monkeypatch.setattr(step2, "__file__", str(fdf_dir / "process.py"))
    sys.argv = [
        "process.py",
        "--input", str(fdp_output),   # upstream_dirty_path resolves from this
        "--output", str(fdf_output),
        "--public-body", "1002",
    ]
    step2.main()

    s2_results_list = read_json(fdf_output)["results"]
    by_body = {}
    for r in s2_results_list:
        by_body.setdefault(r["public_body_id"], []).append(r)

    # 1001 and 1003 must be preserved exactly
    assert by_body[1001][0]["marker"] == "keep-1001"
    assert by_body[1003][0]["marker"] == "keep-1003"

    # 1002's stale record must be gone; reprocessed record must be present
    assert not any(r.get("marker") == "stale-1002" for r in by_body.get(1002, []))
    assert 1002 in by_body


# ---------------------------------------------------------------------------
# Test 2: orchestrator --from + --public-body passthrough
# ---------------------------------------------------------------------------

def test_from_plus_public_body_passthrough(tmp_path):
    """--from validate_websites --public-body 1002 runs only steps from
    validate_websites onward, and each carries --public-body 1002 but no
    --force."""
    steps = ["find_public_bodies", "validate_websites", "find_foi_pages"]
    pipeline_dir = _make_pipeline(tmp_path, steps)
    _seed_bodies(pipeline_dir, [1002])

    from process import main as orchestrator_main

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = [
            "process.py", str(pipeline_dir),
            "--from", "validate_websites",
            "--public-body", "1002",
        ]
        orchestrator_main()

    called_cmds = [call[0][0] for call in mock_run.call_args_list]

    # find_public_bodies must NOT run (before --from boundary);
    # check cmd[1] (the step script path) to avoid matching it in --input paths
    assert not any("find_public_bodies" in cmd[1] for cmd in called_cmds)

    # validate_websites and find_foi_pages must run with --public-body 1002
    # and without --force
    assert len(called_cmds) >= 2
    for cmd in called_cmds:
        assert "--public-body" in cmd
        idx = cmd.index("--public-body")
        assert cmd[idx + 1] == "1002"
        assert "--force" not in cmd

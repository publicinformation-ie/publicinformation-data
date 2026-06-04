import json
import sys

import steps.find_public_bodies_subject_to_foi.process as proc
from steps.find_public_bodies_subject_to_foi.process import main, STEP_NAME


def make_body(bid, *, exclusion_reason=None):
    body = {
        "public_body_id": bid,
        "name": f"Body {bid}",
        "official_website_url": f"https://body-{bid}.ie/",
        "category": "government department",
        "status": {
            "website_url": {"url": f"https://body-{bid}.ie/", "status": "not_attempted"},
        },
    }
    if exclusion_reason is not None:
        body["exclusion_reason"] = exclusion_reason
    return body


def write_input(path, bodies):
    path.write_text(json.dumps({
        "metadata": {"step": "find_public_bodies", "completed_at": "2026-06-04T00:00:00+00:00"},
        "public_bodies": bodies,
    }))


def run_main(tmp_path, monkeypatch, argv):
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = argv
    main()


def test_step_name():
    assert STEP_NAME == "find_public_bodies_subject_to_foi"


def test_excludes_body_with_not_subject_to_foi(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1099, exclusion_reason="not_subject_to_foi")])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    ids = [b["public_body_id"] for b in result["public_bodies"]]
    assert 1099 not in ids
    assert 1001 in ids


def test_excludes_body_with_any_exclusion_reason(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1088, exclusion_reason="temporary")])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    ids = [b["public_body_id"] for b in result["public_bodies"]]
    assert 1088 not in ids
    assert 1001 in ids


def test_no_exclusion_reason_passes_through(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1002)])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    assert len(result["public_bodies"]) == 2


def test_output_contains_no_exclusion_reason_fields(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1099, exclusion_reason="not_subject_to_foi")])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    for body in result["public_bodies"]:
        assert "exclusion_reason" not in body


def test_skips_if_output_exists_without_force(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001)])
    out.write_text(json.dumps({"metadata": {}, "public_bodies": [{"sentinel": True}]}))
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(out)]
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
    result = json.loads(out.read_text())
    assert result["public_bodies"][0].get("sentinel") is True


def test_scoped_run_confirms_foi_subject_body(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001)])
    out.write_text(json.dumps({
        "metadata": {"step": STEP_NAME},
        "public_bodies": [make_body(1001)],
    }))
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(out), "--public-body", "1001"]
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
    result = json.loads(out.read_text())
    assert result["public_bodies"][0]["public_body_id"] == 1001


def test_scoped_run_errors_for_excluded_body(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001)])
    out.write_text(json.dumps({
        "metadata": {"step": STEP_NAME},
        "public_bodies": [make_body(1001)],
    }))
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(out), "--public-body", "9999"]
    try:
        main()
        assert False, "Expected SystemExit"
    except SystemExit as e:
        assert e.code != 0

import json
import sys
from pathlib import Path

import steps.find_public_bodies_subject_to_foi.process as proc
from steps.find_public_bodies_subject_to_foi.process import main, STEP_NAME


def make_body(bid):
    return {
        "public_body_id": bid,
        "name": f"Body {bid}",
        "official_website_url": f"https://body-{bid}.ie/",
        "category": "government department",
        "status": {
            "website_url": {"url": f"https://body-{bid}.ie/", "status": "not_attempted"},
        },
    }


def write_input(path, bodies):
    path.write_text(json.dumps({
        "metadata": {"step": "find_public_bodies", "completed_at": "2026-06-12T00:00:00+00:00"},
        "public_bodies": bodies,
    }))


def write_inclusions(step_dir, ids):
    (step_dir / "inclusions.json").write_text(json.dumps(ids))


def run_main(tmp_path, monkeypatch, argv):
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = argv
    main()


def test_step_name():
    assert STEP_NAME == "find_public_bodies_subject_to_foi"


def test_body_in_inclusions_passes_through(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1002)])
    write_inclusions(tmp_path, [1001])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    ids = [b["public_body_id"] for b in result["public_bodies"]]
    assert 1001 in ids
    assert 1002 not in ids


def test_body_not_in_inclusions_is_filtered(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1002)])
    write_inclusions(tmp_path, [1001])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    assert len(result["public_bodies"]) == 1


def test_all_bodies_in_inclusions_all_pass(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001), make_body(1002)])
    write_inclusions(tmp_path, [1001, 1002])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    assert len(result["public_bodies"]) == 2


def test_empty_inclusions_filters_all(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001)])
    write_inclusions(tmp_path, [])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    assert len(result["public_bodies"]) == 0


def test_no_exclusion_reason_field_logic(tmp_path, monkeypatch):
    """Bodies should be filtered solely by inclusions list, not by exclusion_reason."""
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    # body 1001 has exclusion_reason but IS in inclusions — should pass through
    body = make_body(1001)
    body["exclusion_reason"] = "not_subject_to_foi"
    write_input(inp, [body])
    write_inclusions(tmp_path, [1001])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    assert len(result["public_bodies"]) == 1


def test_skips_if_output_exists_without_force(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001)])
    write_inclusions(tmp_path, [1001])
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
    write_inclusions(tmp_path, [1001])
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


def test_scoped_run_errors_for_non_included_body(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_input(inp, [make_body(1001)])
    write_inclusions(tmp_path, [1001])
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

import sys as _sys
from lib.file_utils import read_json as _read_json, write_json as _write_json
import steps.extract_disclosures_deduplicate.process as _proc


def test_public_body_scoped_preserves_other_bodies(tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    _write_json(out, {"metadata": {"step": "extract_disclosures_deduplicate"}, "results": [
        {"public_body_id": 1001, "foi_reference_id": "A", "marker": "keep"},
        {"public_body_id": 1002, "foi_reference_id": "OLD", "marker": "stale"},
    ]})
    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "foi_reference_id": "A"},
        {"public_body_id": 1002, "foi_reference_id": "B"},
        {"public_body_id": 1002, "foi_reference_id": "B"},  # duplicate within 1002
    ]})

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    assert {"public_body_id": 1001, "foi_reference_id": "A", "marker": "keep"} in results
    assert not any(r.get("marker") == "stale" for r in results)
    # the within-1002 duplicate is collapsed to one row
    assert sum(1 for r in results if r["public_body_id"] == 1002) == 1

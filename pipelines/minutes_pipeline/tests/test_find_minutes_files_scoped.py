import json

import steps.find_minutes_files.process as process_mod
from steps.find_minutes_files.process import STEP_NAME, process
from lib.file_utils import read_json


def test_scoped_run_keeps_other_bodies_errors(tmp_path, monkeypatch, make_writer):
    """A --public-body run replaces only that body's errors.json entries;
    other bodies' errors must survive (process() used to reset the whole file)."""
    (tmp_path / "errors.json").write_text(json.dumps([
        {"error_type": "Keep", "context": {"public_body_id": 1511}},
        {"error_type": "Replace", "context": {"public_body_id": 1716}},
    ]))
    monkeypatch.setattr(process_mod, "_fetch_one",
                        lambda item: (item["public_body_id"], item["minutes_page_url"], [], [], None))
    process({"results": [{"public_body_id": 1716,
                          "minutes_page_url": "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/Minutes2026/"}]},
            tmp_path, make_writer(STEP_NAME))
    errors = read_json(tmp_path / "errors.json")
    assert [e["error_type"] for e in errors] == ["Keep"]

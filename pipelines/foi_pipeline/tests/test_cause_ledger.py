import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "experiments/2026-11-14-pdf-extractor-bakeoff"))
from cause_ledger import build_ledger, classify_error, per_file_cross_role_rate  # noqa: E402


@pytest.mark.parametrize("etype,ctx,cls", [
    ("UnrecognizedRequesterType", {"raw_requester_type": "Journalist."}, "text_variant"),
    ("UnrecognizedDecisionStatus", {"raw_status": "R S efused. ection 15(1)(a)."}, "glyph_split"),
    ("UnrecognizedDecisionStatus", {"raw_status": "Refusedon administrative grounds"}, "unknown_value"),
    ("UnrecognizedRequesterType", {"raw_requester_type": "Part Grant"}, "cross_role"),
    ("StatusValueIsDate", {"raw_status": "17/07/2023"}, "cross_role"),
    ("UnrecognizedRequesterType", {"raw_requester_type": "Student"}, "unknown_value"),
    ("SomethingElse", {}, "other"),
])
def test_classify_error(etype, ctx, cls):
    assert classify_error({"error_type": etype, "context": ctx}) == cls


def _tree(tmp_path, uniformity):
    url = "http://x/f.pdf"
    canon = tmp_path / "extract_disclosures_canonicalize_rows"
    assess = tmp_path / "assess_table_structure"
    canon.mkdir()
    assess.mkdir()
    errs = [{"error_type": "UnrecognizedRequesterType",
             "context": {"file_url": url, "public_body_id": 5, "raw_requester_type": "Part Grant"}}
            for _ in range(9)]
    errs.append({"error_type": "UnrecognizedRequesterType",
                 "context": {"file_url": url, "public_body_id": 5, "raw_requester_type": "Student"}})
    (canon / "errors.json").write_text(json.dumps(errs))
    (canon / "output.json").write_text(json.dumps({"results": [{"file_url": url}] * 10}))
    (assess / "output.json").write_text(json.dumps({"results": [
        {"file_url": url, "pdf_extractor": "pdfplumber",
         "table_structure": {"width_uniformity": uniformity}}]}))
    return url


def test_build_ledger_header_mapping_upgrade(tmp_path):
    url = _tree(tmp_path, 0.97)
    ledger = build_ledger(tmp_path)
    assert ledger["by_class"]["header_mapping"] == 9
    assert "cross_role" not in ledger["by_class"]
    assert ledger["by_class"]["unknown_value"] == 1
    assert per_file_cross_role_rate(tmp_path)[url] == pytest.approx(9 / 20)


def test_no_upgrade_when_not_uniform(tmp_path):
    _tree(tmp_path, 0.5)
    ledger = build_ledger(tmp_path)
    assert ledger["by_class"]["cross_role"] == 9

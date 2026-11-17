import dataclasses
import hashlib
import json

import pytest

from experiments.gating import ledger
from tests.experiments.gating_fixtures import CLEAN_URL, GATED_URL, HALF_ERRORS_URL, make_steps


def _cache(tmp_path, *urls):
    c = tmp_path / "cache"
    c.mkdir(exist_ok=True)
    for u in urls:
        (c / f"{hashlib.sha256(u.encode()).hexdigest()}.bytes").write_bytes(b"pdf:" + u.encode())
    return c


def _snapshot(tmp_path, gated_records=30):
    snap = make_steps(tmp_path / "snap", gated_records=gated_records)
    return snap


def build(tmp_path, state=None, with_bytes=(GATED_URL, HALF_ERRORS_URL)):
    steps = make_steps(tmp_path / "steps")
    snap = _snapshot(tmp_path)
    sp = tmp_path / "state.json"
    sp.write_text(json.dumps(state or {}))
    entries = ledger.build_ledger(steps, snap, sp, _cache(tmp_path, *with_bytes))
    return {e.file_url: e for e in entries}, sp


def test_build_generates_values(tmp_path):
    es, _ = build(tmp_path)
    assert set(es) == {GATED_URL}
    g = es[GATED_URL]
    assert g.fault_kind == "G" and g.recoverable == 30 and g.status == "open"
    assert g.sha256 == hashlib.sha256(b"pdf:" + GATED_URL.encode()).hexdigest()


def test_ledger_state_overrides_generated_values(tmp_path):
    es, _ = build(tmp_path, {GATED_URL: {"fault_kind": "S", "fault_firm": True, "cluster": "c1",
                                         "status": "parked", "note": "hello"}})
    g = es[GATED_URL]
    assert (g.fault_kind, g.fault_firm, g.cluster, g.status) == ("S", True, "c1", "parked")
    assert g.evidence.endswith("hello")


def test_ledger_marks_no_bytes_regardless_of_state(tmp_path):
    es, _ = build(tmp_path, {GATED_URL: {"status": "resolved"}}, with_bytes=(HALF_ERRORS_URL,))
    assert es[GATED_URL].status == "no_bytes" and es[GATED_URL].sha256 is None


def test_set_state_rejects_unknown_status(tmp_path):
    p = tmp_path / "s.json"
    with pytest.raises(ValueError):
        ledger.set_state([GATED_URL], p, status="bogus")
    with pytest.raises(ValueError):
        ledger.set_state([GATED_URL], p, fault_kind="Q")
    ledger.set_state([GATED_URL, CLEAN_URL], p, status="parked", note="n")
    assert json.loads(p.read_text())[CLEAN_URL]["status"] == "parked"


def test_ledger_md_ranks_clusters_by_recoverable(tmp_path):
    es, _ = build(tmp_path, {GATED_URL: {"cluster": "small"}})
    big = dataclasses.replace(es[GATED_URL], file_url=HALF_ERRORS_URL, cluster="big", recoverable=100)
    es[GATED_URL].recoverable = 5
    es[HALF_ERRORS_URL] = big
    out = tmp_path / "out"
    out.mkdir()
    ledger.write_ledger(list(es.values()), out)
    md = (out / "LEDGER.md").read_text()
    assert md.index("| big |") < md.index("| small |")
    assert len(json.loads((out / "ledger.json").read_text())) == 2


def test_set_state_rejects_unknown_triage_class(tmp_path):
    with pytest.raises(ValueError):
        ledger.set_state([GATED_URL], state_path=tmp_path / "s.json", triage_class="maybe")


def test_triage_class_round_trips_into_entry(tmp_path):
    steps = make_steps(tmp_path / "steps")
    sp = tmp_path / "s.json"
    ledger.set_state([GATED_URL], state_path=sp, triage_class="scan")
    es = ledger.build_ledger(steps, _snapshot(tmp_path), sp, _cache(tmp_path, GATED_URL))
    assert es[0].triage_class == "scan"
    ledger.set_state([GATED_URL], state_path=sp, triage_class="small_log")
    assert json.loads(sp.read_text())[GATED_URL]["triage_class"] == "small_log"


def test_retired_s_proposal_takes_cluster_from_triaged_kind(tmp_path):
    steps = make_steps(tmp_path / "steps")
    sp = tmp_path / "s.json"
    ledger.set_state([GATED_URL], state_path=sp, fault_kind="E", triage_class="hard_table")
    # no snapshot rows before the gate -> proposed kind S
    es = ledger.build_ledger(steps, make_steps(tmp_path / "snap0", gated_records=0), sp, _cache(tmp_path, GATED_URL))
    assert es[0].cluster.startswith("7-E-")
    # a non-S proposal keeps its own kind in the cluster id
    es = ledger.build_ledger(steps, _snapshot(tmp_path), tmp_path / "none.json", _cache(tmp_path, GATED_URL))
    assert es[0].fault_kind == "G" and es[0].cluster.startswith("7-G-")


def test_estimate_rows_counts_date_and_reference_lines():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Header line\n01/02/2024 Request one\nFOI-2024-001 two\nplain text", fontsize=10)
    data = doc.tobytes()
    assert ledger.estimate_rows(data) == 2
    assert ledger.estimate_rows(None) is None
    assert ledger.estimate_rows(b"not a pdf") is None


def test_est_rows_only_where_recoverable_zero(tmp_path):
    steps = make_steps(tmp_path / "steps")
    es = ledger.build_ledger(steps, make_steps(tmp_path / "snap0", gated_records=0), tmp_path / "n.json",
                             _cache(tmp_path, GATED_URL))
    assert es[0].recoverable == 0 and es[0].est_rows is None  # fake bytes are not a PDF
    es = ledger.build_ledger(steps, _snapshot(tmp_path), tmp_path / "n.json", _cache(tmp_path, GATED_URL))
    assert es[0].recoverable == 30 and es[0].est_rows is None

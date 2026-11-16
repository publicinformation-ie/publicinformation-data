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
    assert set(es) == {GATED_URL, HALF_ERRORS_URL}
    g = es[GATED_URL]
    assert g.fault_kind == "G" and g.recoverable == 30 and g.status == "open"
    assert g.sha256 == hashlib.sha256(b"pdf:" + GATED_URL.encode()).hexdigest()
    assert es[HALF_ERRORS_URL].fault_kind in "EMV"


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
    es, _ = build(tmp_path, {GATED_URL: {"cluster": "small"}, HALF_ERRORS_URL: {"cluster": "big"}})
    list(es.values())[0]
    for e in es.values():
        e.recoverable = 100 if e.cluster == "big" else 5
    out = tmp_path / "out"
    out.mkdir()
    ledger.write_ledger(list(es.values()), out)
    md = (out / "LEDGER.md").read_text()
    assert md.index("| big |") < md.index("| small |")
    assert len(json.loads((out / "ledger.json").read_text())) == 2

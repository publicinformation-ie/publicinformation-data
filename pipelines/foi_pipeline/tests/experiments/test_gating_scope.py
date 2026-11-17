from experiments.gating.scope import FileStat, error_rate, file_stats, propose_fault, scope_set, default_cluster, recoverable
from tests.experiments.gating_fixtures import CLEAN_URL, GATED_URL, HALF_ERRORS_URL, make_steps


def fs(**kw):
    base = dict(file_url="u", public_body_id=1, name="n", file_type="pdf", pdf_extractor="pdfplumber",
                gated=False, failed_checks=[], worst_role=None, worst_role_contamination=None,
                anchored_row_share=None, records=10, errors=0, error_classes={}, n_candidates_with_table=1)
    base.update(kw)
    return FileStat(**base)


def test_file_stats_fields(tmp_path):
    st = file_stats(make_steps(tmp_path))
    g = st[GATED_URL]
    assert g.gated and g.failed_checks == ["role_contamination", "anchored_row_share"]
    assert g.worst_role == "requester_type" and g.worst_role_contamination == 0.9
    assert g.n_candidates_with_table == 1 and g.name == "Gated"
    assert st[CLEAN_URL].name == "clean.pdf" and st[CLEAN_URL].records == 5
    h = st[HALF_ERRORS_URL]
    assert (h.records, h.errors) == (1, 1) and sum(h.error_classes.values()) == 1


def test_scope_set_is_gated_files_only(tmp_path):
    # HALF_ERRORS_URL has error_rate 0.5 but is not gated, so it is out of scope
    assert scope_set(file_stats(make_steps(tmp_path))) == [GATED_URL]


def test_error_rate_zero_when_no_rows():
    assert error_rate(fs(records=0, errors=0)) == 0.0
    assert error_rate(fs(records=1, errors=1)) == 0.5


def test_propose_fault_rules():
    assert propose_fault(fs(gated=True, failed_checks=["min_rows"]), None, False)[0] == "S"
    assert propose_fault(fs(gated=True, failed_checks=["role_contamination"]), fs(records=0, errors=0), False)[0] == "S"
    assert propose_fault(fs(errors=5), None, True)[0] == "M"
    assert propose_fault(fs(errors=5, error_classes={"unknown_value": 3, "text_variant": 2}), None, False)[0] == "V"
    assert propose_fault(fs(errors=5, error_classes={"header_mapping": 4, "other": 1}), None, False)[0] == "M"
    assert propose_fault(fs(errors=5, error_classes={"other": 3, "cross_role": 2}), None, False)[0] == "E"
    gated = fs(gated=True, failed_checks=["role_contamination", "anchored_row_share"])
    assert propose_fault(gated, fs(records=50, errors=1), False)[0] == "G"
    assert propose_fault(gated, fs(records=19, errors=0), False)[0] == "E"
    assert propose_fault(gated, fs(records=50, errors=20), False)[0] == "E"
    assert propose_fault(fs(gated=True, failed_checks=["width"]), fs(records=50), False)[0] == "E"
    # tie in top class gives E
    assert propose_fault(fs(errors=4, error_classes={"header_mapping": 2, "other": 2}), None, False)[0] == "E"


def test_cluster_and_recoverable():
    n = fs(public_body_id=9, gated=True, failed_checks=["b", "a"], errors=3)
    assert default_cluster(n, "G") == "9-G-a+b"
    assert default_cluster(fs(public_body_id=9), "E") == "9-E-errors"
    assert recoverable(n, fs(records=40)) == 40 and recoverable(n, None) == 0
    assert recoverable(fs(errors=3), None) == 3

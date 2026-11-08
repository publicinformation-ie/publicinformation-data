from scripts.audit_body_hierarchy import check_hierarchy


def body(id, name, parent=None, dept=None):
    record = {"@id": f"https://data.publicinformation.ie/body/{id}",
              "name": name, "slug": str(id)}
    if parent is not None:
        record["parent_id"] = f"https://data.publicinformation.ie/body/{parent}"
    if dept is not None:
        record["government_department_id"] = (
            f"https://data.publicinformation.ie/body/{dept}")
    return record


def test_a_dangling_parent_is_a_hard_finding():
    findings = check_hierarchy([body(1, "Child", parent=99)])
    assert any(f["severity"] == "hard" and "dangling" in f["code"] for f in findings)


def test_a_self_parent_is_a_hard_finding():
    findings = check_hierarchy([body(1, "Self", parent=1)])
    assert any(f["code"] == "self_parent" for f in findings)


def test_a_parent_cycle_is_a_hard_finding():
    findings = check_hierarchy([body(1, "A", parent=2), body(2, "B", parent=1)])
    assert any(f["code"] == "parent_cycle" for f in findings)


def test_a_local_authority_self_department_is_not_a_cycle():
    findings = check_hierarchy([body(1, "Carlow County Council", dept=1)])
    assert findings == []


def test_a_parent_child_department_mismatch_is_soft():
    findings = check_hierarchy([
        body(1, "Parent", dept=10),
        body(2, "Child", parent=1, dept=20),
    ])
    assert any(f["severity"] == "soft" and f["code"] == "department_mismatch"
               for f in findings)

from scripts.audit_text_artefacts import audit, check_failures


def _action(**kw):
    base = {
        "action_id": "a1",
        "action_text": "Increase staf.f numbers",
        "action_text_clean": "Increase staff numbers",
        "original_deadline_raw": "2025",
        "original_deadline_milestones": "2025: done",
        "original_timeline_raw": None,
        "lead": "NTA", "support": None, "output": None,
    }
    base.update(kw)
    return base


def _obs(**kw):
    base = {
        "action_id": "a1", "report_slug": "r1",
        "reported_deadline_raw": "Q1",
        "progress_text": "ok",
        "progress_text_clean": "ok",
    }
    base.update(kw)
    return base


def test_only_residue_in_a_clean_field_fails():
    actions = [_action()]
    observations = [_obs(progress_text="a betet r plan",
                         progress_text_clean="a betet r plan")]
    report = audit(actions, observations)
    failures = check_failures(report)
    assert len(failures) == 1
    assert "progress_text_clean" in failures[0]
    assert "a1@r1" in failures[0]
    repaired = [r for r in report["records"] if r["status"] == "repaired"]
    assert any(r["field"] == "action_text" and r["after"] == "staff"
               for r in repaired)


def test_raw_only_field_artefact_is_flagged_not_failed():
    report = audit([_action(lead="Staf.f office")], [_obs()])
    assert check_failures(report) == []
    assert any(r["field"] == "lead" and r["status"] == "flagged"
               for r in report["records"])


def test_missing_clean_field_is_a_failure():
    a = _action()
    del a["action_text_clean"]
    failures = check_failures(audit([a], [_obs()]))
    assert any("action_text_clean" in f for f in failures)


def test_clean_data_has_no_failures():
    assert check_failures(audit([_action()], [_obs()])) == []

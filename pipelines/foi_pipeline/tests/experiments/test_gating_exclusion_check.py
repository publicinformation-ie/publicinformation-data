from experiments.gating.exclusion_check import affected, verdict


def _vr(url, status="verified", records=0, link_text=""):
    return {"file_url": url, "public_body_id": 1, "link_text": link_text,
            "verification_status": status, "records": records}


def _urls(rows):
    return {r["file_url"] for r in rows}


def test_three_confirmed_and_nothing_else_is_ok():
    vr = [_vr(f"https://x.test/privacy-statement-{i}.pdf") for i in range(3)] + [_vr("https://x.test/log.pdf")]
    rows = affected(["privacy statement"], [], vr, {})
    v = verdict(rows, {r["file_url"] for r in rows})
    assert v["covers_confirmed"] == 3 and v["ok"] is True
    assert v["would_reject_with_records"] == [] and v["would_reject_unconfirmed"] == []


def test_two_confirmed_is_not_ok():
    vr = [_vr(f"https://x.test/application-{i}.pdf") for i in range(2)]
    rows = affected(["application"], [], vr, {})
    v = verdict(rows, _urls(rows))
    assert v["covers_confirmed"] == 2 and v["ok"] is False


def test_file_with_records_blocks_and_is_listed():
    vr = [_vr(f"https://x.test/application-{i}.pdf") for i in range(3)]
    vr.append(_vr("https://x.test/application-log.pdf", records=5))
    rows = affected(["application"], [], vr, {})
    v = verdict(rows, {f"https://x.test/application-{i}.pdf" for i in range(3)})
    assert v["covers_confirmed"] == 3 and v["ok"] is False
    assert v["would_reject_with_records"] == ["https://x.test/application-log.pdf"]
    assert v["would_reject_unconfirmed"] == ["https://x.test/application-log.pdf"]


def test_already_rejected_never_affected_and_matching_rules():
    vr = [_vr("https://x.test/application.pdf", status="rejected"),
          _vr("https://x.test/a.pdf", link_text="My Application Form"),
          _vr("https://x.test/b.pdf"), _vr("https://x.test/c.pdf")]
    texts = {"https://x.test/b.pdf": "Reason For Decision and Decision Maker",
             "https://x.test/c.pdf": "reason for decision only"}
    rows = affected(["application"], [("reason for decision", "decision maker")], vr, texts)
    assert _urls(rows) == {"https://x.test/a.pdf", "https://x.test/b.pdf"}

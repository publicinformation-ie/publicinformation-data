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


def _pdf(*page_texts):
    import pymupdf
    doc = pymupdf.open()
    for t in page_texts:
        doc.new_page().insert_text((72, 72), t)
    return doc.tobytes()


def test_empty_segments_dropped_and_patterns_lowercased():
    from experiments.gating.exclusion_check import parse_patterns
    urls, content = parse_patterns(["  Calendar ", ""], ["Reason For Decision| |Decision Maker|", "|"])
    assert urls == ["calendar"]
    assert content == [("reason for decision", "decision maker")]


def test_extract_text_matches_verifier_first_page_only():
    from experiments.gating.exclusion_check import extract_text
    data = _pdf("cover page", "reason for decision")
    text = extract_text("pdf", data)
    assert "cover page" in text and "reason for decision" not in text
    vr = [_vr("https://x.test/a.pdf")]
    assert affected([], [("reason for decision",)], vr, {"https://x.test/a.pdf": text}) == []
    assert "reason for decision" in extract_text("pdf", _pdf("reason for decision"))


def test_extract_text_unknown_type_or_missing_bytes_is_none():
    from experiments.gating.exclusion_check import extract_text
    assert extract_text("docx", b"x") is None and extract_text("pdf", None) is None

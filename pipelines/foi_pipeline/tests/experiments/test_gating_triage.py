import json

import pytest

from experiments.gating import triage_page as tp
from experiments.gating.triage import facts
from tests.experiments.gating_fixtures import make_pdf

ENTRY = {"file_url": "https://x.test/a.pdf", "public_body_id": 7, "name": "A"}


def test_facts_text_pdf():
    f = facts(ENTRY, make_pdf(pages=2, text="Ref Date Decision " * 40))
    assert f.pages == 2 and f.likely_scan is False and len(f.text_head) <= 2000 and f.unreadable is None


def test_facts_image_only_pdf_is_likely_scan():
    f = facts(ENTRY, make_pdf(pages=1, text=""))
    assert f.chars_per_page == 0 and f.likely_scan is True


def test_facts_no_bytes():
    assert facts(ENTRY, None).unreadable == "no_bytes"


def test_facts_garbage_bytes_do_not_raise():
    assert facts(ENTRY, b"not a pdf").unreadable is not None


def test_facts_encrypted_pdf():
    assert facts(ENTRY, make_pdf(pages=1, text="x", password="p")).unreadable == "encrypted"


def test_build_inputs_writes_json_and_image(tmp_path):
    import hashlib

    from experiments.gating.triage import build_inputs
    url = "https://x.test/a.pdf"
    cache = tmp_path / "cache"
    cache.mkdir()
    data = make_pdf(pages=2, text="hello " * 50)
    (cache / f"{hashlib.sha256(url.encode()).hexdigest()}.bytes").write_bytes(data)
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps([
        {"file_url": url, "public_body_id": 7, "name": "A", "fault_kind": "S"},
        {"file_url": "https://x.test/b.pdf", "public_body_id": 7, "name": "B", "fault_kind": "E"}]))
    steps = tmp_path / "steps" / "verify_disclosure_files"
    steps.mkdir(parents=True)
    (steps / "output.json").write_text(json.dumps({"results": [
        {"file_url": url, "link_text": "Log", "verification_signal": "sig"}]}))
    out = build_inputs(tmp_path / "round", ledger, tmp_path / "steps", cache)
    assert len(out) == 1 and out[0].link_text == "Log" and out[0].verification_signal == "sig"
    assert (tmp_path / "round" / out[0].image).is_file()
    assert json.loads((tmp_path / "round" / "inputs.json").read_text())[0]["file_url"] == url


import pytest

from experiments.gating.triage import load_proposals


def _round(tmp_path, inputs, proposals):
    (tmp_path / "inputs.json").write_text(json.dumps(inputs))
    (tmp_path / "proposals.json").write_text(json.dumps(proposals))
    return tmp_path


A = {"file_url": "https://x.test/a.pdf", "unreadable": None}
B = {"file_url": "https://x.test/b.pdf", "unreadable": "encrypted"}


def test_load_proposals_valid(tmp_path):
    rd = _round(tmp_path, [A, B], [{"file_url": A["file_url"], "class": "scan", "reason": "image only"}])
    assert load_proposals(rd) == {A["file_url"]: {"class": "scan", "reason": "image only"}}


@pytest.mark.parametrize("prop", [
    {"file_url": A["file_url"], "class": "bogus", "reason": "r"},
    {"file_url": A["file_url"], "class": "scan", "reason": "  "},
    {"file_url": "https://x.test/zzz.pdf", "class": "scan", "reason": "r"},
])
def test_load_proposals_errors_name_url(tmp_path, prop):
    rd = _round(tmp_path, [A], [prop])
    with pytest.raises(ValueError, match=prop["file_url"]):
        load_proposals(rd)


def test_load_proposals_missing_readable_input(tmp_path):
    rd = _round(tmp_path, [A, B], [])
    with pytest.raises(ValueError, match=A["file_url"]):
        load_proposals(rd)

SHA = {n: c * 64 for n, c in zip("abcde", "abcde")}


def _inp(url, bid, name, sha, **kw):
    d = {"file_url": url, "public_body_id": bid, "name": name, "sha256": sha, "pages": 1,
         "link_text": "log", "image": f"review/img/{sha}.png" if sha else None, "unreadable": None}
    d.update(kw)
    return d


@pytest.fixture
def round_dir(tmp_path):
    inputs = [
        _inp("https://x.test/h.pdf", 5, "Body H", SHA["a"]),
        _inp("https://x.test/n2.pdf", 9, "Body N2", SHA["b"]),
        _inp("https://x.test/n1.pdf", 2, "Body N1", SHA["c"]),
        _inp("https://x.test/<b>.pdf", 3, "Body <X>", SHA["d"]),
        _inp("https://x.test/u.pdf", 1, "Body U", None, image=None, unreadable="no_bytes"),
    ]
    props = [
        {"file_url": "https://x.test/h.pdf", "class": "hard_table", "reason": "ticks"},
        {"file_url": "https://x.test/n2.pdf", "class": "not_foi_log", "reason": "form"},
        {"file_url": "https://x.test/n1.pdf", "class": "not_foi_log", "reason": "form"},
        {"file_url": "https://x.test/<b>.pdf", "class": "small_log", "reason": "tiny <r>"},
    ]
    (tmp_path / "inputs.json").write_text(json.dumps(inputs))
    (tmp_path / "proposals.json").write_text(json.dumps(props))
    return tmp_path


def test_every_url_once_and_order(round_dir):
    h = tp.build(round_dir).read_text()
    for u in ("https://x.test/h.pdf", "https://x.test/n1.pdf", "https://x.test/n2.pdf", "https://x.test/u.pdf"):
        assert h.count(f"data-key='file:{u}'") == 1
    pos = lambda s: h.index(f"data-key='file:https://x.test/{s}'")
    assert pos("n1.pdf") < pos("n2.pdf") < pos("&lt;b&gt;.pdf") < pos("h.pdf") < pos("u.pdf")


def test_tag_buttons_and_escape(round_dir):
    h = tp.build(round_dir).read_text()
    for c in ("not_foi_log", "scan", "hard_table", "small_log"):
        assert f"pick(this,'{c}')" in h
    assert "<b>.pdf" not in h and "Body <X>" not in h and "tiny <r>" not in h
    assert "Body &lt;X&gt;" in h


def test_pdf_route_support_and_image(round_dir):
    tp.build(round_dir)
    files = json.loads((round_dir / "results.json").read_text())["files"]
    assert files["https://x.test/h.pdf"]["sha256"] == SHA["a"]
    assert f"/pdf/{SHA['a']}.pdf" in (round_dir / "review/index.html").read_text()
    assert f"img/{SHA['a']}.png" in (round_dir / "review/index.html").read_text()

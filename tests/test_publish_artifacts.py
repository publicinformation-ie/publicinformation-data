import hashlib
import io
import json
import urllib.error
from email.message import Message

import pytest

from scripts import publish_artifacts as pa

TAG = "foi-disclosures-v1.0.0+20261113"
FILES = {rel: f"content of {name}".encode() for name, rel in pa.RELEASE_FILES if name != "manifest.json"}


def fake_builder(root, build_id=None, commit=None):
    for rel, data in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    m = root / dict(pa.RELEASE_FILES)["manifest.json"]
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(json.dumps({"schema_version": "1.0.0", "build": build_id, "total_rows": 1}))


def run(tag, out, tmp_path, **kw):
    return pa.publish(tag, pa.LocalTarget(out), root=tmp_path / "repo", builder=fake_builder,
                      dataset_version=kw.get("dataset_version", "1.0.0"))


def tree(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def test_local_layout_manifest_and_sums(tmp_path):
    out = tmp_path / "out"
    assert run(TAG, out, tmp_path) == "foi-disclosures/v1.0.0/20261113"
    t = tree(out)
    folder = "foi-disclosures/v1.0.0/20261113/"
    assert sorted(k[len(folder):] for k in t) == sorted(
        ["foi-disclosures.json", "foi-disclosures.csv", "foi-disclosures.jsonld",
         "foi-disclosures.xlsx", "manifest.json", "SHA256SUMS"])
    assert all(k.startswith(folder) for k in t) and not any("latest" in k for k in t)
    manifest = json.loads(t[folder + "manifest.json"])
    assert manifest["schema_version"] == "1.0.0" and manifest["build"] == "20261113"
    for line in t[folder + "SHA256SUMS"].decode().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256(t[folder + name]).hexdigest() == digest
    assert len(t[folder + "SHA256SUMS"].decode().splitlines()) == 5


def test_republish_fails_and_changes_nothing(tmp_path):
    out = tmp_path / "out"
    run(TAG, out, tmp_path)
    before = tree(out)
    with pytest.raises(pa.ReleaseError, match="already exists"):
        run(TAG, out, tmp_path)
    assert tree(out) == before


@pytest.mark.parametrize("tag", [
    "foi-disclosures-v1.1.0+20261113",   # schema mismatch
    "foi-disclosures-v1.0.0",            # no build
    "foi-disclosures-v1.0.0+2026-11-13", # malformed build
    "foi-disclosures-v1.0.0+20261113.",  # malformed build
    "v3.3.0",                            # other tag
    "public-bodies-v1.1.0",
])
def test_bad_tags_rejected_before_any_write(tag, tmp_path):
    out = tmp_path / "out"
    with pytest.raises(pa.ReleaseError):
        run(tag, out, tmp_path)
    assert not out.exists() and not (tmp_path / "repo").exists()


def test_second_build_same_day_allowed(tmp_path):
    assert run("foi-disclosures-v1.0.0+20261113.2", tmp_path / "out", tmp_path).endswith("/20261113.2")


class Resp(io.BytesIO):
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def bunny(responses):
    calls = []

    def opener(req, timeout=None):
        calls.append((req.get_method(), req.full_url, req.data, dict(req.header_items())))
        r = responses(req)
        if isinstance(r, Exception):
            raise r
        return r
    return pa.BunnyTarget("zone", "s3cret", opener=opener), calls


def test_bunny_sends_listing_then_puts_with_accesskey(tmp_path):
    def responses(req):
        if req.get_method() == "GET":
            return urllib.error.HTTPError(req.full_url, 404, "nf", Message(), None)
        return Resp(b"{}")
    target, calls = bunny(responses)
    pa.publish(TAG, target, root=tmp_path / "repo", builder=fake_builder, dataset_version="1.0.0")
    assert calls[0][0] == "GET"
    assert calls[0][1] == "https://storage.bunnycdn.com/zone/foi-disclosures/v1.0.0/20261113/"
    puts = [c for c in calls if c[0] == "PUT"]
    assert len(puts) == 6
    assert all(c[1].startswith("https://storage.bunnycdn.com/zone/foi-disclosures/v1.0.0/20261113/") for c in puts)
    assert all(c[3]["Accesskey"] == "s3cret" for c in calls)


def test_bunny_existing_folder_refused_without_put(tmp_path):
    target, calls = bunny(lambda req: Resp(json.dumps([{"ObjectName": "manifest.json"}]).encode()))
    with pytest.raises(pa.ReleaseError, match="already exists"):
        pa.publish(TAG, target, root=tmp_path / "repo", builder=fake_builder, dataset_version="1.0.0")
    assert [c[0] for c in calls] == ["GET"]


def test_bunny_failure_never_leaks_key(tmp_path):
    def responses(req):
        if req.get_method() == "GET":
            return urllib.error.HTTPError(req.full_url, 404, "nf", Message(), None)
        return urllib.error.HTTPError(req.full_url, 401, "denied", Message(), None)
    target, _ = bunny(responses)
    with pytest.raises(pa.ReleaseError) as exc:
        pa.publish(TAG, target, root=tmp_path / "repo", builder=fake_builder, dataset_version="1.0.0")
    assert "s3cret" not in str(exc.value) and "401" in str(exc.value)


def test_make_target_requires_credentials_and_known_spec():
    with pytest.raises(pa.ReleaseError, match="BUNNY_STORAGE"):
        pa.make_target("bunny", env={})
    with pytest.raises(pa.ReleaseError, match="unknown target"):
        pa.make_target("s3")
    assert isinstance(pa.make_target("local:/x"), pa.LocalTarget)

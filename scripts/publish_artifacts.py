#!/usr/bin/env python3
"""Publish an immutable FOI disclosures release.

  python scripts/publish_artifacts.py foi-disclosures-v1.0.0+20261113 --target local:/tmp/out
  python scripts/publish_artifacts.py "$GITHUB_REF_NAME" --target bunny

Tag format: foi-disclosures-v<schema>+<build>, build = YYYYMMDD or YYYYMMDD.<n>.
<schema> must equal DATASET_VERSION at the tagged commit. The release lands in
foi-disclosures/v<schema>/<build>/ and is never overwritten. There is no latest/
copy: the site's /latest/ is the only latest.

Bunny credentials come from BUNNY_STORAGE_ZONE and BUNNY_STORAGE_KEY (never logged).
Nothing here depends on the git host: CI only supplies the tag and the env vars.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TAG_PREFIX = "foi-disclosures-v"
TAG_RE = re.compile(r"^foi-disclosures-v(?P<schema>\d+\.\d+\.\d+)\+(?P<build>\d{8}(?:\.\d+)?)$")
BUNNY_HOST = "https://storage.bunnycdn.com"
RELEASE_HOST = "https://releases.publicinformation.ie"
# (name in the release, path under the repo root)
RELEASE_FILES = [
    ("foi-disclosures.json", "public/foi-disclosures.json"),
    ("foi-disclosures.csv", "public/latest/foi-disclosures/foi-disclosures.csv"),
    ("foi-disclosures.jsonld", "public/latest/foi-disclosures/foi-disclosures.jsonld"),
    ("foi-disclosures.xlsx", "public/latest/foi-disclosures/foi-disclosures.xlsx"),
    ("manifest.json", "public/latest/foi-disclosures/bodies/manifest.json"),
]


class ReleaseError(Exception):
    pass


def parse_tag(tag, dataset_version):
    """Return (schema, build, folder). Raises ReleaseError before anything is written."""
    if not tag.startswith(TAG_PREFIX):
        raise ReleaseError(f"{tag!r} is not a foi-disclosures release tag")
    m = TAG_RE.match(tag)
    if not m:
        raise ReleaseError(
            f"{tag!r}: expected foi-disclosures-v<schema>+<build> with build YYYYMMDD[.n]")
    if m["schema"] != dataset_version:
        raise ReleaseError(f"tag schema {m['schema']} does not match DATASET_VERSION {dataset_version}")
    return m["schema"], m["build"], f"foi-disclosures/v{m['schema']}/{m['build']}"


class LocalTarget:
    def __init__(self, root):
        self.root = Path(root)

    def exists(self, folder):
        d = self.root / folder
        return d.is_dir() and any(d.iterdir())

    def put(self, path, data):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


class BunnyTarget:
    """Bunny Storage HTTP API. `opener` is injectable for tests."""

    def __init__(self, zone, key, opener=None):
        if not zone or not key:
            raise ReleaseError("BUNNY_STORAGE_ZONE and BUNNY_STORAGE_KEY must be set")
        self.zone = zone
        self._key = key
        self._open = opener or urllib.request.urlopen

    def _url(self, path):
        return f"{BUNNY_HOST}/{urllib.parse.quote(self.zone)}/{urllib.parse.quote(path)}"

    def _request(self, method, path, data=None):
        req = urllib.request.Request(self._url(path), data=data, method=method,
                                     headers={"AccessKey": self._key,
                                              "Content-Type": "application/octet-stream",
                                              "Accept": "application/json"})
        return self._open(req, timeout=300)

    def exists(self, folder):
        try:
            with self._request("GET", folder.rstrip("/") + "/") as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise ReleaseError(f"listing {folder} failed: HTTP {exc.code}") from None
        try:
            return bool(json.loads(body or b"[]"))
        except ValueError:
            raise ReleaseError(f"listing {folder} returned unparseable data") from None

    def put(self, path, data):
        try:
            with self._request("PUT", path, data=data) as resp:
                status = getattr(resp, "status", 201)
        except urllib.error.HTTPError as exc:
            raise ReleaseError(f"upload of {path} failed: HTTP {exc.code}") from None
        if status not in (200, 201):
            raise ReleaseError(f"upload of {path} failed: HTTP {status}")


def _sha256sums(files):
    return "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))


def publish(tag, target, root=REPO, builder=None, dataset_version=None):
    """Validate, build, check the folder is new, then upload. Returns the folder."""
    from scripts import build_foi_combined, transform_foi_disclosures as tfd
    schema, build_id, folder = parse_tag(tag, dataset_version or tfd.DATASET_VERSION)
    if target.exists(folder):
        raise ReleaseError(f"{folder} already exists; releases are immutable")

    root = Path(root)
    (builder or build_foi_combined.build)(root, build_id=build_id)
    files = {name: (root / rel).read_bytes() for name, rel in RELEASE_FILES}
    manifest = json.loads(files["manifest.json"])
    if manifest.get("schema_version") != schema or manifest.get("build") != build_id:
        raise ReleaseError("built manifest does not record the tag's schema version and build")
    files["SHA256SUMS"] = _sha256sums(files).encode("utf-8")

    for name, data in files.items():
        target.put(f"{folder}/{name}", data)
    return folder


def make_target(spec, env=None):
    env = os.environ if env is None else env
    if spec.startswith("local:"):
        return LocalTarget(spec[len("local:"):])
    if spec == "bunny":
        return BunnyTarget(env.get("BUNNY_STORAGE_ZONE"), env.get("BUNNY_STORAGE_KEY"))
    raise ReleaseError(f"unknown target {spec!r} (use bunny or local:<dir>)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("tag")
    ap.add_argument("--target", required=True, help="bunny | local:<dir>")
    args = ap.parse_args(argv)
    try:
        folder = publish(args.tag, make_target(args.target))
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Published {RELEASE_HOST}/{folder}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

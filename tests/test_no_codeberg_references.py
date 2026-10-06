"""No tracked file may reference the retired Forgejo/Codeberg hosts.

Walks `git ls-files` (per the design spec) and scans raw bytes so binaries and
non-UTF-8 files are covered. This file is the only permitted self-exception,
because it must name the markers it forbids.

LFS fail-closed rule: payload bytes live in LFS blobs. An unmaterialized
worktree shows pointers (`version https://git-lfs...`) instead of content, in
which a legacy host could hide — so pointers fail the build with an explicit
"materialize with `git lfs pull`" message instead of passing silently.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF = "tests/test_no_codeberg_references.py"
MARKERS = (b"codeberg", b"forgejo")
LFS_POINTER_PREFIX = b"version https://git-lfs"


def _tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                         capture_output=True, check=True).stdout
    return [p for p in out.split(b"\0") if p]


def _is_lfs_pointer(path: Path) -> bool:
    with path.open("rb") as f:
        return f.read(len(LFS_POINTER_PREFIX) + 64).startswith(
            LFS_POINTER_PREFIX)


def test_no_tracked_file_references_the_retired_hosts():
    offenders = []
    for raw in _tracked_files():
        rel = raw.decode()
        if rel == SELF:
            continue
        data = (REPO_ROOT / rel).read_bytes().lower()
        if any(m in data for m in MARKERS):
            offenders.append(rel)
    assert offenders == [], offenders


def test_unmaterialized_lfs_pointers_fail_closed():
    pointers = [raw.decode() for raw in _tracked_files()
                if _is_lfs_pointer(REPO_ROOT / raw.decode())]
    assert pointers == [], (
        "LFS pointer files hide real content — materialize with "
        f"`git lfs pull`: {pointers}")


def test_pointer_detection_flags_lfs_pointer_bytes(tmp_path):
    pointer = tmp_path / "p.json"
    pointer.write_bytes(b"version https://git-lfs.github.com/spec/v1\n"
                        b"oid sha256:abc\nsize 12\n")
    assert _is_lfs_pointer(pointer)
    normal = tmp_path / "n.json"
    normal.write_bytes(b'{"a": 1}')
    assert not _is_lfs_pointer(normal)

"""The strategies-and-plans documents bundle is retired: no tracked file may
still reference its catalog identifier.

Note: the document pipeline still writes its bundle to the gitignored local
`public/documents/` directory (that path is intentionally out of scope), so
this guard covers only the published catalog identifier `dataset/documents`.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MARKERS = (b"dataset/documents",)


def test_no_tracked_file_references_the_retired_documents_bundle():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                         capture_output=True, check=True).stdout
    offenders = []
    for raw in [p for p in out.split(b"\0") if p]:
        rel = raw.decode()
        if rel == "tests/test_no_documents_references.py":
            continue
        data = (REPO_ROOT / rel).read_bytes().lower()
        if any(m in data for m in MARKERS):
            offenders.append(rel)
    assert offenders == [], offenders

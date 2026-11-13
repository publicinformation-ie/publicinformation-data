"""Guards that keep the FOI text datasets in ordinary git (not LFS), small
enough for git to diff and store as deltas."""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAX_BYTES = 45 * 1024 * 1024

FOI_TEXT_PATHS = [
    "public/latest/foi-disclosures/bodies/1052.ndjson",
    "public/disclosure-files.json",
    "pipelines/foi_pipeline/steps/transform_disclosure_files/output.json",
]
FOI_PATHSPECS = [
    "public/latest/foi-disclosures/bodies",
    "public/disclosure-files.json",
    "pipelines/foi_pipeline/steps/transform_disclosure_files/output.json",
]


def oversized(paths, limit=MAX_BYTES):
    return [f"{p} is {p.stat().st_size} bytes (limit {limit})" for p in paths if p.stat().st_size > limit]


def committed_foi_files(repo=REPO):
    out = subprocess.run(["git", "ls-files", "--", *FOI_PATHSPECS], cwd=repo,
                         capture_output=True, text=True, check=True).stdout.split()
    return [repo / p for p in out if (repo / p).is_file()]


def check_attrs(path, repo=REPO):
    out = subprocess.run(["git", "check-attr", "filter", "diff", "merge", "--", path], cwd=repo,
                         capture_output=True, text=True, check=True).stdout
    values = {}
    for line in out.splitlines():
        _, attr, value = line.rsplit(": ", 2)
        values[attr] = value
    return values


def bad_attrs(values):
    return [f"{k}={v}" for k, v in values.items() if v in ("lfs", "unset")]


def test_no_committed_foi_file_over_45mb():
    assert oversized(committed_foi_files()) == []


def test_size_guard_names_an_oversized_file(tmp_path):
    big = tmp_path / "big.ndjson"
    with big.open("wb") as f:
        f.truncate(1024 + 1)
    assert oversized([big], limit=1024) == [f"{big} is 1025 bytes (limit 1024)"]


def test_foi_text_paths_are_not_lfs_binary_or_unmergeable():
    for path in FOI_TEXT_PATHS:
        values = check_attrs(path)
        assert bad_attrs(values) == [], f"{path}: {values}"


def test_attr_check_detects_unset_and_lfs():
    assert bad_attrs({"filter": "lfs", "diff": "lfs", "merge": "lfs"}) == ["filter=lfs", "diff=lfs", "merge=lfs"]
    assert bad_attrs({"filter": "unspecified", "diff": "unset", "merge": "unspecified"}) == ["diff=unset"]

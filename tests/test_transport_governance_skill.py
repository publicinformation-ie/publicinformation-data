import csv
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".claude/skills/transport-governance"
DATASET = REPO / "public/latest/transport-raci"

ASSIGNMENT = re.compile(
    r"`([A-Z]{1,3}-\d{2}[a-z]?\.S\d+[A-Za-z]*(?:~[a-z0-9-]+)?)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BACKTICK = re.compile(r"`([^`]+)`")
REPO_PATH_PREFIXES = ("public/", "pipelines/", "scripts/", "reference/",
                      ".claude/", "openspec/")


def _dataset_columns(filename: str, column: str) -> set[str]:
    with (DATASET / filename).open(encoding="utf-8", newline="") as handle:
        return {row[column] for row in csv.DictReader(handle)}


def _frontmatter(text: str) -> dict[str, str]:
    _, block, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in block.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def test_skill_description_triggers_on_who_does_what_transport_questions():
    description = _frontmatter(
        (SKILL / "SKILL.md").read_text(encoding="utf-8"))["description"].lower()
    assert "who does what" in description
    assert "transport" in description


def test_every_expected_assignment_in_checks_exists_in_the_dataset():
    tokens = ASSIGNMENT.findall((SKILL / "checks.md").read_text(encoding="utf-8"))
    assert len(tokens) >= 15, "the validation set has lost its assignment rows"
    with (DATASET / "rows.csv").open(encoding="utf-8", newline="") as handle:
        coverage = {row["row_id"]: row["coverage"] for row in csv.DictReader(handle)}
    assignments = _dataset_columns("raci-wide.csv", "assignment_id")
    for token in tokens:
        base = token.split("~", 1)[0]
        assert base in coverage, token
        if coverage[base] == "assessed":
            assert token in assignments, token
        else:
            assert coverage[base] == "not assessed", token
            assert "~" not in token, token


def test_every_link_and_named_repository_path_in_the_skill_exists():
    for name in ("SKILL.md", "vocabulary.md", "checks.md"):
        text = (SKILL / name).read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            assert (SKILL / target.split("#", 1)[0]).resolve().exists(), (name, target)
        for token in BACKTICK.findall(text):
            if token.startswith(REPO_PATH_PREFIXES) and "<" not in token:
                assert (REPO / token).exists(), (name, token)


def test_the_skill_holds_no_assignment_table():
    for name in ("SKILL.md", "vocabulary.md"):
        assert not ASSIGNMENT.search((SKILL / name).read_text(encoding="utf-8")), name
    assert sorted(path.name for path in SKILL.iterdir()) == [
        "SKILL.md", "checks.md", "vocabulary.md"]


def test_the_retired_gda_file_is_gone_and_unreferenced():
    assert not (SKILL / "raci-gda.md").exists()
    for path in SKILL.iterdir():
        assert "raci-gda" not in path.read_text(encoding="utf-8"), path.name
    result = subprocess.run(
        ["git", "grep", "-l", "raci-gda", "--", ".",
         ":(exclude)openspec/changes/archive/*"],
        cwd=REPO, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        return  # not a git checkout; the directory check above still ran
    assert result.stdout.strip() == "", result.stdout


def test_the_skill_states_its_coverage_and_gap_rules():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
    for phrase in ("meath county council", "analysed for", "legal advice",
                   "not assessed", "evidence", "variant"):
        assert phrase in text, phrase
    vocabulary = (SKILL / "vocabulary.md").read_text(encoding="utf-8").lower()
    assert "banned terms" in vocabulary
    assert "school transport" in vocabulary

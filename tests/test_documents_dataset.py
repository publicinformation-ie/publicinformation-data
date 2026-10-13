import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO_ROOT / "pipelines" / "document_pipeline"), str(REPO_ROOT / "src")]

INDEX = REPO_ROOT / "public" / "documents" / "index.json"
TTL = REPO_ROOT / "public" / "catalog" / "dataset-documents.ttl"


def test_documents_directory_is_not_gitignored():
    result = subprocess.run(["git", "check-ignore", "-q", "public/documents/index.json"],
                            cwd=REPO_ROOT)
    assert result.returncode == 1                      # 1 = not ignored


def test_bundles_and_index_are_lfs_tracked():
    out = subprocess.run(["git", "check-attr", "filter", "--",
                          "public/documents/index.json",
                          "public/documents/x/bundle.tar.gz"],
                         cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    assert out.count("filter: lfs") == 2


def test_catalog_entry_exists_with_a_stampable_modified_line():
    text = TTL.read_text(encoding="utf-8")
    assert "dataset/documents>" in text
    assert len(re.findall(r'^    dct:modified "\d{4}-\d{2}-\d{2}"\^\^xsd:date ;$', text, re.M)) == 1


def test_index_matches_documents_yml_and_the_policy_table():
    from documents import load_documents
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    curated = {d["doc_slug"]: d for d in load_documents()}
    published = {d["doc_slug"]: d for d in index["documents"]}
    failed = {d["doc_slug"] for d in index.get("failed", [])}
    assert set(published) | failed == set(curated)
    for slug, entry in published.items():
        assert entry["policy_id"] == curated[slug]["policy_id"]
        assert entry["policy_role"] == curated[slug]["policy_role"]

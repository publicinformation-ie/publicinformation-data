"""Guard the GitHub Actions workflows: CI runs the full check suite and the
Pages deploy publishes ``public/`` with LFS-materialized bytes."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEPLOY_YML = REPO_ROOT / ".github" / "workflows" / "deploy-pages.yml"


def test_ci_workflow_has_lfs_checkout_and_check_sequence():
    text = CI_YML.read_text(encoding="utf-8")
    assert "lfs: true" in text
    assert "uv run pytest pipelines/foi_pipeline/tests -q" in text
    assert "uv run pytest pipelines/document_pipeline/tests -q" in text
    assert "uv run pytest tests -q" in text
    assert "uv run pyright" in text
    assert "generate_pipeline_docs.py --check" in text


def test_deploy_workflow_triggers_and_lfs():
    text = DEPLOY_YML.read_text(encoding="utf-8")
    assert "public/**" in text and "workflow_dispatch" in text
    assert "lfs: true" in text
    assert "upload-pages-artifact" in text and "deploy-pages" in text
    assert "environment: github-pages" in text

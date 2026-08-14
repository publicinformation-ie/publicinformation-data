from pathlib import Path

from scripts.generate_pipeline_docs import render, update_text, load_pipelines


def test_generated_pipeline_overview_matches_repository_documents():
    repo_root = Path(__file__).resolve().parents[1]
    agents = (repo_root / "AGENTS.md").read_text()
    expected = update_text(agents, render(load_pipelines(repo_root)))
    assert agents == expected

from pathlib import Path

from scripts.pipeline_status import discover_pipelines, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_every_pipeline_json_loads_with_valid_paid_steps():
    for d in discover_pipelines(REPO_ROOT):
        load_config(d)  # raises PipelineDataError on bad paid_steps


def test_known_paid_steps_are_marked():
    # extract_motions is paid (CLAUDE.md cost rule) — guards against the marker being dropped
    assert load_config(REPO_ROOT / "pipelines/minutes_pipeline")["paid_steps"]["extract_motions"] == ["llm"]

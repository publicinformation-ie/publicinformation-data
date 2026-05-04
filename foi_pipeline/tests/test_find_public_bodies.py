import json
import sys
from pathlib import Path

import pytest

from steps.find_public_bodies.process import scrape_public_bodies, STEP_NAME, BASE_ID

SAMPLE_HTML = """
<!DOCTYPE html>
<html><body>
  <nav><a href="/en/organisation/department-of-finance/">Department of Finance</a></nav>
  <main>
    <a href="/en/organisation/department-of-health/">Department of Health</a>
    <a href="/en/organisation/department-of-education/">Department of Education</a>
    <a href="/en/other-page/">Not an organisation</a>
    <a href="https://external.example.com/">External link</a>
  </main>
</body></html>
"""

DUPLICATE_HTML = """
<html><body>
  <a href="/en/organisation/dept-finance/">Dept Finance</a>
  <a href="/en/organisation/dept-finance/">Dept Finance (again)</a>
</body></html>
"""

NAMELESS_LINK_HTML = """
<html><body>
  <a href="/en/organisation/dept-finance/">  </a>
  <a href="/en/organisation/dept-health/">Health</a>
</body></html>
"""


def test_scrape_extracts_organisation_links(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    urls = [b["official_website_url"] for b in bodies]
    assert "https://www.gov.ie/en/organisation/department-of-finance/" in urls
    assert "https://www.gov.ie/en/organisation/department-of-health/" in urls
    assert "https://www.gov.ie/en/organisation/department-of-education/" in urls


def test_scrape_excludes_non_organisation_links(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    urls = [b["official_website_url"] for b in bodies]
    assert not any("other-page" in u for u in urls)
    assert not any("external.example.com" in u for u in urls)


def test_scrape_deduplicates_urls(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=DUPLICATE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    assert len(bodies) == 1


def test_scrape_skips_nameless_links(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=NAMELESS_LINK_HTML)
    bodies = scrape_public_bodies(tmp_path)
    assert len(bodies) == 1
    assert bodies[0]["name"] == "Health"


def test_scrape_ids_start_at_1001(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    assert bodies[0]["public_body_id"] == BASE_ID + 1
    assert bodies[1]["public_body_id"] == BASE_ID + 2


def test_scrape_ids_are_sequential(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    ids = [b["public_body_id"] for b in bodies]
    assert ids == list(range(BASE_ID + 1, BASE_ID + 1 + len(ids)))


def test_scrape_resets_errors_json(requests_mock, tmp_path):
    # Pre-existing stale errors should be cleared at the start of each run
    errors_path = tmp_path / "errors.json"
    errors_path.write_text('[{"step": "old", "error_type": "OldError"}]')
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    scrape_public_bodies(tmp_path)
    errors = json.loads(errors_path.read_text())
    assert errors == []


def test_process_writes_output_and_status(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    monkeypatch.chdir(tmp_path)

    # Wire the PYTHONPATH so subprocess can import scripts
    import subprocess, os
    pipeline_dir = Path(__file__).parent.parent
    process_script = pipeline_dir / "steps" / "find_public_bodies" / "process.py"
    output_path = tmp_path / "output.json"

    result = subprocess.run(
        [sys.executable, str(process_script), "--input", str(tmp_path), "--output", str(output_path)],
        env={**os.environ, "PYTHONPATH": str(pipeline_dir)},
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert output_path.exists()
    bodies = json.loads(output_path.read_text())
    assert isinstance(bodies, list)
    assert len(bodies) > 0
    status = json.loads((pipeline_dir / "steps" / "find_public_bodies" / "pipeline-status.json").read_text())
    assert status["record_count"] == len(bodies)
    assert "completed_at" in status

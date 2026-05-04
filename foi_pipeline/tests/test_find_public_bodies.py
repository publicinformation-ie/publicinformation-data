import json
import sys
from pathlib import Path

import pytest

from steps.find_public_bodies.process import scrape_public_bodies, STEP_NAME, BASE_ID

SAMPLE_HTML = """
<!DOCTYPE html>
<html><body>
  <nav><a href="/en/some-nav-link/">Nav Link</a></nav>
  <section id="departments">
    <a href="/en/department-of-finance/">Department of Finance</a>
    <a href="/en/department-of-health/">Department of Health</a>
  </section>
  <section id="agencies">
    <a href="/en/central-bank-of-ireland/">Central Bank of Ireland</a>
  </section>
  <section id="local-authorities">
    <a href="/en/carlow-county-council/">Carlow County Council</a>
  </section>
  <footer><a href="/en/privacy-policy/">Privacy Policy</a></footer>
</body></html>
"""

DUPLICATE_HTML = """
<html><body>
  <section id="departments">
    <a href="/en/dept-finance/">Dept Finance</a>
    <a href="/en/dept-finance/">Dept Finance (again)</a>
  </section>
</body></html>
"""

NAMELESS_LINK_HTML = """
<html><body>
  <section id="agencies">
    <a href="/en/dept-finance/">  </a>
    <a href="/en/dept-health/">Health</a>
  </section>
</body></html>
"""


def test_scrape_extracts_organisation_links(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    urls = [b["official_website_url"] for b in bodies]
    assert "https://www.gov.ie/en/department-of-finance/" in urls
    assert "https://www.gov.ie/en/department-of-health/" in urls
    assert "https://www.gov.ie/en/central-bank-of-ireland/" in urls
    assert "https://www.gov.ie/en/carlow-county-council/" in urls


def test_scrape_excludes_non_organisation_links(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    urls = [b["official_website_url"] for b in bodies]
    assert not any("some-nav-link" in u for u in urls)
    assert not any("privacy-policy" in u for u in urls)


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
    output = json.loads(output_path.read_text())
    assert isinstance(output, dict)
    assert "metadata" in output
    assert "public_bodies" in output
    bodies = output["public_bodies"]
    assert isinstance(bodies, list)
    assert len(bodies) > 0
    # Verify fields exist on first body
    first_body = bodies[0]
    assert "status" in first_body, "status field missing"
    assert isinstance(first_body["status"], dict), "status should be a dict"
    # Verify all required status subfields exist
    required_status_fields = ["website_url", "foi_page", "foi_email", "disclosures_page", "disclosure_files", "foi_requests"]
    for field in required_status_fields:
        assert field in first_body["status"], f"status.{field} field missing"
    status = json.loads((pipeline_dir / "steps" / "find_public_bodies" / "pipeline-status.json").read_text())
    assert status["record_count"] == len(bodies)
    assert "completed_at" in status



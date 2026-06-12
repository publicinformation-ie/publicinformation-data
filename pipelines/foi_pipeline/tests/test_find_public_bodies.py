import json
import os
import subprocess
import sys
from pathlib import Path

from steps.find_public_bodies.process import scrape_public_bodies, BASE_ID

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


def test_scrape_includes_category_field(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    assert all("category" in b for b in bodies)


def test_scrape_departments_have_government_department_category(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    dept = next(b for b in bodies if "department-of-finance" in b["official_website_url"])
    assert dept["category"] == "government department"


def test_scrape_agencies_have_public_service_body_category(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    agency = next(b for b in bodies if "central-bank" in b["official_website_url"])
    assert agency["category"] == "public service body"


def test_scrape_local_authorities_have_local_authority_category(requests_mock, tmp_path):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    bodies = scrape_public_bodies(tmp_path)
    council = next(b for b in bodies if "carlow" in b["official_website_url"])
    assert council["category"] == "local authority"


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


EXCLUSION_HTML = """
<html><body>
  <section id="agencies">
    <a href="/en/coillte/">Coillte</a>
    <a href="/en/hse/">HSE</a>
  </section>
</body></html>
"""


def test_excluded_body_has_exclusion_reason_field(requests_mock, tmp_path):
    (tmp_path / "exclusions.json").write_text(
        '[{"source_url": "https://www.gov.ie/en/coillte/", '
        '"name": "Coillte", "exclusion_reason": "not_subject_to_foi", "note": ""}]'
    )
    requests_mock.get("https://www.gov.ie/en/departments/", text=EXCLUSION_HTML)
    bodies = scrape_public_bodies(tmp_path)
    coillte = next(b for b in bodies if "coillte" in b["official_website_url"])
    assert coillte["exclusion_reason"] == "not_subject_to_foi"


def test_excluded_body_has_no_not_subject_to_foi_field(requests_mock, tmp_path):
    (tmp_path / "exclusions.json").write_text(
        '[{"source_url": "https://www.gov.ie/en/coillte/", '
        '"name": "Coillte", "exclusion_reason": "not_subject_to_foi", "note": ""}]'
    )
    requests_mock.get("https://www.gov.ie/en/departments/", text=EXCLUSION_HTML)
    bodies = scrape_public_bodies(tmp_path)
    coillte = next(b for b in bodies if "coillte" in b["official_website_url"])
    assert "not_subject_to_foi" not in coillte


def test_non_excluded_body_has_no_exclusion_reason(requests_mock, tmp_path):
    (tmp_path / "exclusions.json").write_text(
        '[{"source_url": "https://www.gov.ie/en/coillte/", '
        '"name": "Coillte", "exclusion_reason": "not_subject_to_foi", "note": ""}]'
    )
    requests_mock.get("https://www.gov.ie/en/departments/", text=EXCLUSION_HTML)
    bodies = scrape_public_bodies(tmp_path)
    hse = next(b for b in bodies if "hse" in b["official_website_url"])
    assert "exclusion_reason" not in hse


def test_temporary_exclusion_reason_is_preserved(requests_mock, tmp_path):
    (tmp_path / "exclusions.json").write_text(
        '[{"source_url": "https://www.gov.ie/en/coillte/", '
        '"name": "Coillte", "exclusion_reason": "temporary", "note": ""}]'
    )
    requests_mock.get("https://www.gov.ie/en/departments/", text=EXCLUSION_HTML)
    bodies = scrape_public_bodies(tmp_path)
    coillte = next(b for b in bodies if "coillte" in b["official_website_url"])
    assert coillte["exclusion_reason"] == "temporary"


def test_empty_exclusions_file_leaves_no_exclusion_reason(requests_mock, tmp_path):
    (tmp_path / "exclusions.json").write_text("[]")
    requests_mock.get("https://www.gov.ie/en/departments/", text=EXCLUSION_HTML)
    bodies = scrape_public_bodies(tmp_path)
    assert all("exclusion_reason" not in b for b in bodies)


SEPARATE_WEBSITE_HTML = """
<html><body>
  <section id="departments">
    <a href="/en/dept-a/">Dept A</a>
    <a href="/en/dept-b/">Dept B</a>
  </section>
</body></html>
"""

DEPT_A_PAGE = """
<html><body>
  <p>there is a separate website for <a href="https://dept-a.ie/">Dept A</a></p>
</body></html>
"""

DEPT_B_PAGE = """
<html><body>
  <p>No separate website here.</p>
</body></html>
"""


def test_parallel_resolution_follows_separate_website_links(requests_mock, tmp_path):
    """Dept A redirects to dept-a.ie; Dept B stays on gov.ie. Order must be preserved."""
    requests_mock.get("https://www.gov.ie/en/departments/", text=SEPARATE_WEBSITE_HTML)
    requests_mock.get("https://www.gov.ie/en/dept-a/", text=DEPT_A_PAGE)
    requests_mock.get("https://www.gov.ie/en/dept-b/", text=DEPT_B_PAGE)

    bodies = scrape_public_bodies(tmp_path)

    assert len(bodies) == 2
    dept_a = next(b for b in bodies if b["name"] == "Dept A")
    dept_b = next(b for b in bodies if b["name"] == "Dept B")
    assert dept_a["official_website_url"] == "https://dept-a.ie/"
    assert dept_b["official_website_url"] == "https://www.gov.ie/en/dept-b/"


def test_parallel_resolution_preserves_insertion_order(requests_mock, tmp_path):
    """Bodies must appear in the same order as in the source HTML after parallel resolution."""
    requests_mock.get("https://www.gov.ie/en/departments/", text=SEPARATE_WEBSITE_HTML)
    requests_mock.get("https://www.gov.ie/en/dept-a/", text=DEPT_A_PAGE)
    requests_mock.get("https://www.gov.ie/en/dept-b/", text=DEPT_B_PAGE)

    bodies = scrape_public_bodies(tmp_path)

    assert bodies[0]["name"] == "Dept A"
    assert bodies[1]["name"] == "Dept B"


def test_process_writes_output_and_status(requests_mock, tmp_path, monkeypatch):
    requests_mock.get("https://www.gov.ie/en/departments/", text=SAMPLE_HTML)
    monkeypatch.chdir(tmp_path)

    pipeline_dir = Path(__file__).parent.parent
    # pipelines/foi_pipeline/tests/../../.. = repo root; lib lives in src/
    repo_root = Path(__file__).parents[3]
    process_script = pipeline_dir / "steps" / "find_public_bodies" / "process.py"
    output_path = tmp_path / "output.json"

    result = subprocess.run(
        [sys.executable, str(process_script), "--input", str(tmp_path), "--output", str(output_path)],
        env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
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




import sys as _sys
import pytest as _pytest
from lib.file_utils import read_json as _read_json, write_json as _write_json


def test_scoped_run_leaves_output_untouched(tmp_path, monkeypatch):
    import steps.find_public_bodies.process as proc
    step_dir = tmp_path
    out = step_dir / "output.json"
    original = {"metadata": {"step": "find_public_bodies"},
                "public_bodies": [{"public_body_id": 1001}, {"public_body_id": 1002}]}
    _write_json(out, original)

    monkeypatch.setattr(proc, "__file__", str(step_dir / "process.py"))
    _sys.argv = ["process.py", "--input", "x", "--output", str(out), "--public-body", "1001"]
    with _pytest.raises(SystemExit) as exc:
        proc.main()
    assert exc.value.code == 0  # clean exit, not an error

    assert _read_json(out) == original  # byte-for-byte unchanged

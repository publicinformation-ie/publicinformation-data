"""The whole chain over the five committed documents.

These documents are cached, not committed (`pipelines/activetravel_pipeline/cache/`
is git-ignored), so this test runs only where they have been fetched once — the
rest of the suite runs from the committed page fixtures.
"""
from pathlib import Path

import pytest

from allocations import flatten_documents, load_publications
from steps.canonicalize_allocations.process import run as canonicalize_run
from steps.classify_grant_rows.process import run as classify_run
from steps.export_allocations.process import run as export_run
from steps.extract_grant_tables.process import run as extract_run
from steps.fetch_grant_documents.process import cache_path, run as fetch_run
from steps.normalize_grant_amounts.process import run as normalize_run
from steps.reconcile_sections.process import run as reconcile_run
from steps.reconcile_summary.process import run as summary_run
from steps.resolve_recipients.process import run as resolve_run
from steps.segment_funding_streams.process import run as segment_run

PIPELINE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_BODIES = PIPELINE_DIR.parent.parent / "pipelines/foi_pipeline/steps/find_public_bodies/output.json"

# Established by the first clean run over the five editions (2026-11-15). The
# bound is deliberately loose: a reissued PDF may move a few rows either way,
# and this test is about the chain holding together, not pinning the publisher.
BASELINE = {2022: 990, 2023: 1156, 2024: 833, 2025: 913, 2026: 983}
TOLERANCE = 0.02

CACHE_READY = all(cache_path(document["url"]).exists()
                  for document in flatten_documents(load_publications()))
REGISTER_READY = PUBLIC_BODIES.exists()

pytestmark = pytest.mark.skipif(
    not (CACHE_READY and REGISTER_READY),
    reason="source PDFs are cached and the public-body register is generated, not committed",
)


def _no_network(url: str) -> bytes:
    raise AssertionError(f"the cache should have answered this request: {url}")


@pytest.fixture(scope="module")
def chain() -> dict:
    fetched, fetch_errors = fetch_run(fetcher=_no_network)
    assert fetch_errors == []
    assert {d["source"] for d in fetched["documents"] if d["available"]} == {"cache"}

    extracted, _ = extract_run(fetched)
    classified, _ = classify_run(extracted)
    normalized, _ = normalize_run(classified)
    segmented, _ = segment_run(normalized)
    resolved, _ = resolve_run(segmented)
    reconciled, reconcile_errors = reconcile_run(resolved)
    summarized, summary_errors = summary_run(reconciled)
    canonical, _ = canonicalize_run(summarized)
    exported, _ = export_run(canonical)
    return {"exported": exported, "reconcile_errors": reconcile_errors,
            "summary_errors": summary_errors, "summarized": summarized}


@pytest.fixture(scope="module")
def exported(chain) -> dict:
    return chain["exported"]


def test_every_edition_flows(exported):
    for year, expected in BASELINE.items():
        count = exported["metadata"]["counts_by_year"][str(year)]["records"]
        assert abs(count - expected) <= expected * TOLERANCE, (
            f"{year}: {count} records, baseline {expected}")


def test_every_published_record_is_whole_euro_and_linked(exported):
    for record in exported["results"]:
        assert isinstance(record["allocation_eur"], int)
        assert record["allocation_eur"] >= 0
        assert record["funding_stream"] in ("active_travel", "other_nta_streams")
        assert record["source_page"] >= 1
        if record["recipient_name"].endswith("Council"):
            assert record["public_body"], record["@id"]
            assert record["public_body_id"], record["@id"]


def test_no_withheld_row_reaches_the_export(exported):
    withheld = {(row["document_id"], row["page"], row["row_index"])
                for row in exported["withheld_rows"]}
    assert withheld
    for record in exported["results"]:
        assert (record["@id"]) not in withheld


def test_identity_is_unique_and_stable(exported):
    ids = [record["@id"] for record in exported["results"]]
    assert len(ids) == len(set(ids))
    second, _ = fetch_run(fetcher=_no_network)
    assert second["documents"][0]["sha256"] == exported["results"][0]["source_document_sha256"]


def test_a_document_can_be_run_on_its_own():
    fetched, errors = fetch_run(document="nta-active-travel-2026", fetcher=_no_network)
    assert errors == []
    assert [d["document_id"] for d in fetched["documents"]] == ["nta-active-travel-2026"]
    extracted, _ = extract_run(fetched, document="nta-active-travel-2026")
    assert {page["document_id"] for page in extracted["pages"]} == {"nta-active-travel-2026"}


def test_an_undeclared_document_is_refused():
    with pytest.raises(ValueError):
        fetch_run(document="nta-active-travel-2019", fetcher=_no_network)


def test_the_summary_check_confirms_every_published_summary_recipient(chain):
    "Each 2025/2026 per-recipient summary total equals the rows that were published."
    summarized = chain["summarized"]
    assert summarized["summary_comparisons"], "the 2025 and 2026 editions carry a summary"
    for comparison in summarized["summary_comparisons"]:
        assert comparison["declared_eur"] == comparison["extracted_eur"], comparison
    assert chain["summary_errors"] == []


def test_every_withheld_stream_is_reported_with_both_sums(chain):
    for error in chain["reconcile_errors"]:
        assert error["error_type"] == "SectionReconciliationMismatch"
        context = error["context"]
        assert context["recipient"]
        assert context["declared_eur"] is not None
        assert context["extracted_eur"] is not None
        assert context["delta_eur"] == context["extracted_eur"] - context["declared_eur"]

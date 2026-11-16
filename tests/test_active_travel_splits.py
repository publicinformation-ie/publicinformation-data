import csv
import io

from scripts.active_travel_splits import PUBLIC_BASE_URL, build_splits, write_splits
from src.lib.body_refs import BASE_URI


def _rec(slug, name, year, code, amount, body_id: int | None = 1, stream="active_travel"):
    record = {
        "@id": f"{BASE_URI}/allocation/{slug}/{year}/{stream}/{code.lower()}",
        "year": year, "recipient_name": name, "funding_stream": stream,
        "project_code": code, "project_name": f"Project {code}",
        "allocation_eur": amount,
        "source_document_url": f"https://nta.example/{year}.pdf",
        "source_document_sha256": "a" * 64, "source_page": 3,
    }
    if body_id is not None:
        record["public_body_id"] = body_id
    return record


RECORDS = [
    _rec("carlow-county-council", "Carlow County Council", 2023, "CW/23/1", 100, 1085),
    _rec("cork-city-council", "Cork City Council", 2023, "CC/23/1", 50, 1162),
    _rec("carlow-county-council", "Carlow County Council", 2022, "CW/22/1", 200, 1085),
    _rec("carlow-county-council", "Carlow County Council", 2022, "CW/22/2", 25, 1085,
         stream="other_nta_streams"),
    _rec("campuses-hospitals", "Campuses, Hospitals", 2022, "XX/22/1", 10, None),
]


def _read(data: bytes):
    return list(csv.DictReader(io.StringIO(data.decode())))


def test_one_file_per_recipient_and_year_plus_indexes():
    files = build_splits(RECORDS)
    assert set(files) == {
        "by-recipient/carlow-county-council.csv", "by-recipient/cork-city-council.csv",
        "by-recipient/campuses-hospitals.csv", "by-recipient/index.csv",
        "by-year/2022.csv", "by-year/2023.csv", "by-year/index.csv",
    }


def test_recipient_file_holds_all_years_oldest_first_and_friendly_columns():
    rows = _read(build_splits(RECORDS)["by-recipient/carlow-county-council.csv"])
    assert [r["project_code"] for r in rows] == ["CW/22/1", "CW/22/2", "CW/23/1"]
    assert list(rows[0]) == [
        "year", "recipient_name", "funding_stream", "project_code", "project_name",
        "allocation_eur", "source_document_url", "source_page"]


def test_year_file_keeps_the_export_order_of_the_nta_document():
    rows = _read(build_splits(RECORDS)["by-year/2022.csv"])
    assert [r["project_code"] for r in rows] == ["CW/22/1", "CW/22/2", "XX/22/1"]


def test_recipient_index_lists_url_totals_and_years():
    index = {r["file"]: r for r in _read(build_splits(RECORDS)["by-recipient/index.csv"])}
    carlow = index["carlow-county-council.csv"]
    assert carlow["url"] == f"{PUBLIC_BASE_URL}/by-recipient/carlow-county-council.csv"
    assert (carlow["years"], carlow["projects"], carlow["total_allocation_eur"]) == ("2022-2023", "3", "325")
    assert carlow["public_body_id"] == "1085"
    assert index["campuses-hospitals.csv"]["public_body_id"] == ""
    assert index["cork-city-council.csv"]["years"] == "2023"


def test_year_index_counts_recipients_and_links_the_source_document():
    index = {r["year"]: r for r in _read(build_splits(RECORDS)["by-year/index.csv"])}
    assert (index["2022"]["recipients"], index["2022"]["projects"], index["2022"]["total_allocation_eur"]) == ("2", "3", "235")
    assert index["2023"]["source_document_url"] == "https://nta.example/2023.pdf"


def test_splits_reconcile_with_the_whole():
    files = build_splits(RECORDS)
    total = sum(r["allocation_eur"] for r in RECORDS)
    for folder in ("by-recipient", "by-year"):
        rows = [r for name, data in files.items()
                if name.startswith(folder) and not name.endswith("index.csv")
                for r in _read(data)]
        assert len(rows) == len(RECORDS)
        assert sum(int(r["allocation_eur"]) for r in rows) == total


def test_write_splits_is_idempotent_and_removes_stale_files(tmp_path):
    files = build_splits(RECORDS)
    assert write_splits(files, tmp_path) is True
    assert write_splits(files, tmp_path) is False
    (tmp_path / "by-year" / "1999.csv").write_text("stale")
    assert write_splits(files, tmp_path) is True
    assert not (tmp_path / "by-year" / "1999.csv").exists()

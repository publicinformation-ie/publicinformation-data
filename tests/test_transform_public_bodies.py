import pytest
from scripts.transform_public_bodies import (
    slugify,
    map_body_type,
    build_contact_email_lookup,
    build_record,
    BASE_URI,
)


def test_slugify_basic():
    assert slugify("An Coimisiún Pleanála") == "an-coimisiún-pleanála"


def test_slugify_strips_punctuation():
    assert slugify("Abbey Theatre (Amharclann Na Mainistreach)") == "abbey-theatre-amharclann-na-mainistreach"


def test_slugify_empty():
    assert slugify("") == "unknown"


def test_map_body_type_known_categories():
    assert map_body_type("government department") == "department"
    assert map_body_type("local authority") == "local_authority"
    assert map_body_type("public body") == "public_body"


def test_map_body_type_unknown_category_raises():
    with pytest.raises(ValueError, match="Unrecognized public body category"):
        map_body_type("quango")


def test_build_contact_email_lookup_only_includes_successful_crawls():
    pipeline_bodies = [
        {"public_body_id": 1010, "status": {"foi_email": {"email": "foi@pleanala.ie", "status": "success"}}},
        {"public_body_id": 1002, "status": {"foi_email": {"email": None, "status": "failed"}}},
        {"public_body_id": 1014, "status": {"foi_email": {"email": "foi@garda.ieif", "status": "success"}}},
    ]
    lookup = build_contact_email_lookup(pipeline_bodies)
    assert lookup == {1010: "foi@pleanala.ie", 1014: "foi@garda.ieif"}


def test_build_record_foi_subject_body():
    body = {
        "public_body_id": 1010,
        "name": "An Coimisiún Pleanála",
        "official_website_url": "https://www.pleanala.ie/",
        "category": "public body",
    }
    slug_lookup = {1010: "an-coimisiun-pleanala"}
    record = build_record(
        body,
        foi_subject_ids={1010},
        contact_email_lookup={1010: "foi@pleanala.ie"},
        slug_lookup=slug_lookup,
        cso_lookup={},
        crawl_status_lookup={},
    )
    assert record["@id"] == f"{BASE_URI}/body/an-coimisiun-pleanala"
    assert record["@type"] == "foi:PublicBody"
    assert record["name"] == "An Coimisiún Pleanála"
    assert record["type"] == "public_body"
    assert record["website"] == "https://www.pleanala.ie/"
    assert record["foi_subject"] is True
    assert record["foi_scope"] == f"{BASE_URI}/ns/foi#FullScope"
    assert record["contact_email"] == "foi@pleanala.ie"


def test_build_record_non_foi_subject_body_omits_contact_email():
    body = {
        "public_body_id": 1001,
        "name": "Abbey Theatre",
        "official_website_url": "https://www.abbeytheatre.ie/",
        "category": "public body",
    }
    slug_lookup = {1001: "abbey-theatre"}
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={}, slug_lookup=slug_lookup,
        cso_lookup={}, crawl_status_lookup={},
    )
    assert record["foi_subject"] is False
    assert record["foi_scope"] == f"{BASE_URI}/ns/foi#NoScope"
    assert "contact_email" not in record


def test_build_record_missing_website_is_omitted_not_null():
    body = {
        "public_body_id": 1099,
        "name": "No Website Body",
        "official_website_url": None,
        "category": "government department",
    }
    slug_lookup = {1099: "no-website-body"}
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={}, slug_lookup=slug_lookup,
        cso_lookup={}, crawl_status_lookup={},
    )
    assert "website" not in record


from scripts.transform_public_bodies import transform_to_jsonld, transform_to_csv_rows


def test_transform_to_jsonld_single_context_and_graph():
    records = [
        {"@id": f"{BASE_URI}/body/a", "@type": "foi:PublicBody", "name": "A",
         "type": "public_body", "foi_subject": True, "foi_scope": f"{BASE_URI}/ns/foi#FullScope"},
        {"@id": f"{BASE_URI}/body/b", "@type": "foi:PublicBody", "name": "B",
         "type": "department", "foi_subject": False, "foi_scope": f"{BASE_URI}/ns/foi#NoScope"},
    ]
    doc = transform_to_jsonld(records)
    assert "@context" in doc
    assert "@graph" in doc
    assert doc["@graph"] == records
    # no per-record @context duplication
    assert all("@context" not in r for r in doc["@graph"])


def test_transform_to_csv_rows_columns_and_boolean_lexical_form():
    records = [
        {"@id": f"{BASE_URI}/body/a", "@type": "foi:PublicBody", "name": "A",
         "type": "public_body", "website": "https://a.example/", "foi_subject": True,
         "foi_scope": f"{BASE_URI}/ns/foi#FullScope", "contact_email": "foi@a.example",
         "slug": "a"},
        {"@id": f"{BASE_URI}/body/b", "@type": "foi:PublicBody", "name": "B",
         "type": "department", "foi_subject": False, "foi_scope": f"{BASE_URI}/ns/foi#NoScope",
         "slug": "b"},
    ]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames[:7] == ["id", "name", "type", "website", "foi_subject", "foi_scope", "contact_email"]
    assert rows[0]["foi_subject"] == "true"
    assert rows[1]["foi_subject"] == "false"
    assert rows[1]["website"] == ""
    assert rows[1]["contact_email"] == ""


from scripts.transform_public_bodies import build_cso_lookup


def test_build_cso_lookup_only_includes_whitelisted_fields():
    cso_records = [
        {
            "public_body_id": 1001,
            "name": "Abbey Theatre Amharclann Na Mainistreach",
            "parent_name": None,
            "parent_id": None,
            "sector": "S13",
            "legal_status": "Non-Commercial Agency under the aegis of Department",
            "government_department": "Department of Culture, Communications and Sport",
            "government_department_id": 1199,
            "nace_code": "R9001",
            "cro": "414400",
            "data_vintage": 2025,
            "description_for_sub_sector": "Non-Commercial Agencies",
            "official_website_url": "https://www.abbeytheatre.ie/",
            "is_commercial": False,
            "is_financial": None,
            "aegis": "Department",
            "legal_entity_type": "Agency",
            "nace_section": "R",
            "nace_division": "90",
            "nace_group": "900",
            "nace_class": "9001",
            "nace_section_name": "Arts, entertainment and recreation",
            "nace_class_name": "Performing arts",
            "llm_website_url": "https://www.abbeytheatre.ie",
            "llm_url_type": "direct",
            "llm_confidence": "high",
            "llm_notes": "Official website of the Abbey Theatre Amharclann Na Mainistreach.",
            "apify_website_url": None,
            "apify_confidence": None,
        },
    ]
    lookup = build_cso_lookup(cso_records)
    assert lookup == {
        1001: {
            "parent_id": None,
            "parent_name": None,
            "sector": "S13",
            "legal_status": "Non-Commercial Agency under the aegis of Department",
            "government_department_id": 1199,
            "government_department": "Department of Culture, Communications and Sport",
            "nace_code": "R9001",
            "nace_section": "R",
            "nace_section_name": "Arts, entertainment and recreation",
            "nace_division": "90",
            "nace_group": "900",
            "nace_class": "9001",
            "nace_class_name": "Performing arts",
            "cro": "414400",
            "data_vintage": 2025,
            "is_commercial": False,
            "is_financial": None,
            "aegis": "Department",
            "legal_entity_type": "Agency",
        }
    }


from scripts.transform_public_bodies import (
    build_crawl_status_lookup,
    build_status_object,
    build_disclosure_files_object,
    build_foi_requests_object,
)


def test_build_crawl_status_lookup_keys_by_public_body_id():
    pipeline_bodies = [
        {
            "public_body_id": 1002,
            "status": {
                "website_url": {"url": "https://www.abilitywest.ie/", "status": "success"},
                "foi_page": {"url": None, "status": "success"},
                "foi_email": {"email": None, "status": "failed"},
                "disclosures_page": {"url": "https://www.factchecking.ie/toolkit/foi-how-to", "status": "success"},
                "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "failed"},
                "foi_requests": {"valid": 0, "errors": 0, "status": "failed"},
            },
            "public_body_name": "Ability West",
        },
    ]
    lookup = build_crawl_status_lookup(pipeline_bodies)
    assert lookup[1002]["website_url"] == {"url": "https://www.abilitywest.ie/", "status": "success"}
    assert 1099 not in lookup  # body not present in pipeline_bodies -> no key at all


def test_build_status_object_omits_null_value_field():
    raw = {"url": None, "status": "success"}
    obj = build_status_object(raw, "url")
    assert obj == {"status": "success"}
    assert "url" not in obj


def test_build_status_object_includes_value_when_present():
    raw = {"url": "https://www.abilitywest.ie/", "status": "success"}
    obj = build_status_object(raw, "url")
    assert obj == {"url": "https://www.abilitywest.ie/", "status": "success"}


def test_build_status_object_passes_through_verified_only_when_present():
    raw_with_verified = {"url": "https://www.pleanala.ie/", "status": "success", "verified": True}
    obj = build_status_object(raw_with_verified, "url")
    assert obj["verified"] is True

    raw_without_verified = {"url": "https://www.abilitywest.ie/", "status": "success"}
    obj = build_status_object(raw_without_verified, "url")
    assert "verified" not in obj


def test_build_status_object_returns_none_for_missing_raw():
    assert build_status_object(None, "url") is None


def test_build_status_object_email_field():
    raw = {"email": "foi@abilitywest.ie", "status": "success"}
    obj = build_status_object(raw, "email")
    assert obj == {"email": "foi@abilitywest.ie", "status": "success"}


def test_build_disclosure_files_object():
    raw = {"total": 5, "valid": 3, "failed": 2, "status": "success"}
    assert build_disclosure_files_object(raw) == {"total": 5, "valid": 3, "failed": 2, "status": "success"}
    assert build_disclosure_files_object(None) is None


def test_build_foi_requests_object():
    raw = {"valid": 0, "errors": 0, "status": "failed"}
    assert build_foi_requests_object(raw) == {"valid": 0, "errors": 0, "status": "failed"}
    assert build_foi_requests_object(None) is None


def test_build_record_includes_cso_scalar_fields():
    body = {
        "public_body_id": 1001,
        "name": "Abbey Theatre Amharclann Na Mainistreach",
        "official_website_url": "https://www.abbeytheatre.ie/",
        "category": "public body",
    }
    slug_lookup = {1001: "abbey-theatre-amharclann-na-mainistreach"}
    cso_lookup = {
        1001: {
            "parent_id": None,
            "parent_name": None,
            "sector": "S13",
            "legal_status": "Non-Commercial Agency under the aegis of Department",
            "government_department_id": 1199,
            "government_department": "Department of Culture, Communications and Sport",
            "nace_code": "R9001",
            "nace_section": "R",
            "nace_section_name": "Arts, entertainment and recreation",
            "nace_division": "90",
            "nace_group": "900",
            "nace_class": "9001",
            "nace_class_name": "Performing arts",
            "cro": "414400",
            "data_vintage": 2025,
            "is_commercial": False,
            "is_financial": None,
            "aegis": "Department",
            "legal_entity_type": "Agency",
        }
    }
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup=cso_lookup, crawl_status_lookup={},
    )
    assert record["slug"] == "abbey-theatre-amharclann-na-mainistreach"
    assert record["sector"] == "S13"
    assert record["legal_status"] == "Non-Commercial Agency under the aegis of Department"
    assert record["government_department"] == "Department of Culture, Communications and Sport"
    assert record["nace_code"] == "R9001"
    assert record["nace_section_name"] == "Arts, entertainment and recreation"
    assert record["cro"] == "414400"
    assert record["data_vintage"] == 2025
    assert record["is_commercial"] is False
    assert record["aegis"] == "Department"
    assert record["legal_entity_type"] == "Agency"
    # is_financial and parent_name are null in the CSO source -> omitted
    assert "is_financial" not in record
    assert "parent_name" not in record
    assert "parent_id" not in record  # 2b's job, not this task's
    assert "government_department_id" not in record  # 2b's job


def test_build_record_omits_cso_fields_entirely_when_body_id_unmatched():
    body = {
        "public_body_id": 9999,
        "name": "Unmatched Body",
        "official_website_url": None,
        "category": "public body",
    }
    slug_lookup = {9999: "unmatched-body"}
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup={}, crawl_status_lookup={},
    )
    assert "sector" not in record
    assert "cro" not in record
    assert "is_commercial" not in record


def test_build_record_includes_crawl_status_objects_when_present():
    body = {
        "public_body_id": 1002,
        "name": "Ability West",
        "official_website_url": "https://www.abilitywest.ie/",
        "category": "public body",
    }
    slug_lookup = {1002: "ability-west"}
    crawl_status_lookup = {
        1002: {
            "website_url": {"url": "https://www.abilitywest.ie/", "status": "success"},
            "foi_page": {"url": None, "status": "success"},
            "foi_email": {"email": None, "status": "failed"},
            "disclosures_page": {"url": "https://www.factchecking.ie/toolkit/foi-how-to", "status": "success"},
            "disclosure_files": {"total": 0, "valid": 0, "failed": 0, "status": "failed"},
            "foi_requests": {"valid": 0, "errors": 0, "status": "failed"},
        }
    }
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup={}, crawl_status_lookup=crawl_status_lookup,
    )
    assert record["website_url"] == {"url": "https://www.abilitywest.ie/", "status": "success"}
    assert record["foi_page"] == {"status": "success"}  # url omitted, null
    assert record["foi_email"] == {"status": "failed"}  # email omitted, null
    assert record["disclosures_page"] == {"url": "https://www.factchecking.ie/toolkit/foi-how-to", "status": "success"}
    assert record["disclosure_files"] == {"total": 0, "valid": 0, "failed": 0, "status": "failed"}
    assert record["foi_requests"] == {"valid": 0, "errors": 0, "status": "failed"}


def test_build_record_omits_crawl_status_objects_entirely_when_body_never_crawled():
    body = {
        "public_body_id": 9999,
        "name": "Never Crawled Body",
        "official_website_url": None,
        "category": "public body",
    }
    slug_lookup = {9999: "never-crawled-body"}
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup={}, crawl_status_lookup={},
    )
    assert "website_url" not in record
    assert "foi_page" not in record
    assert "foi_email" not in record
    assert "disclosures_page" not in record
    assert "disclosure_files" not in record
    assert "foi_requests" not in record


def test_transform_to_csv_rows_includes_new_flat_columns():
    records = [
        {
            "@id": f"{BASE_URI}/body/a", "@type": "foi:PublicBody", "name": "A",
            "type": "public_body", "foi_subject": True, "foi_scope": f"{BASE_URI}/ns/foi#FullScope",
            "slug": "a", "sector": "S13", "legal_status": "Vote",
            "government_department": "Dept of A", "nace_code": "R9001",
            "nace_section": "R", "nace_section_name": "Arts", "nace_division": "90",
            "nace_group": "900", "nace_class": "9001", "nace_class_name": "Performing arts",
            "cro": "12345", "data_vintage": 2025, "is_commercial": False,
            "is_financial": True, "aegis": "Department", "legal_entity_type": "Agency",
            "website_url": {"url": "https://a.example/", "status": "success"},
            "foi_page": {"status": "success"},
            "foi_email": {"email": "foi@a.example", "status": "success", "verified": True},
            "disclosures_page": {"url": "https://a.example/foi", "status": "success"},
            "disclosure_files": {"total": 5, "valid": 3, "failed": 2, "status": "success"},
            "foi_requests": {"valid": 1, "errors": 0, "status": "success"},
        },
        {
            "@id": f"{BASE_URI}/body/b", "@type": "foi:PublicBody", "name": "B",
            "type": "department", "foi_subject": False, "foi_scope": f"{BASE_URI}/ns/foi#NoScope",
            "slug": "b",
        },
    ]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == [
        "id", "name", "type", "website", "foi_subject", "foi_scope", "contact_email",
        "slug", "parent_name", "sector", "legal_status", "government_department",
        "nace_code", "nace_section", "nace_section_name", "nace_division", "nace_group",
        "nace_class", "nace_class_name", "cro", "data_vintage", "is_commercial",
        "is_financial", "aegis", "legal_entity_type",
        "website_url_url", "website_url_status", "website_url_verified",
        "foi_page_url", "foi_page_status", "foi_page_verified",
        "foi_email_email", "foi_email_status", "foi_email_verified",
        "disclosures_page_url", "disclosures_page_status", "disclosures_page_verified",
        "disclosure_files_total", "disclosure_files_valid", "disclosure_files_failed", "disclosure_files_status",
        "foi_requests_valid", "foi_requests_errors", "foi_requests_status",
    ]
    row_a = rows[0]
    assert row_a["slug"] == "a"
    assert row_a["sector"] == "S13"
    assert row_a["is_commercial"] == "false"
    assert row_a["is_financial"] == "true"
    assert row_a["data_vintage"] == "2025"
    assert row_a["website_url_url"] == "https://a.example/"
    assert row_a["website_url_status"] == "success"
    assert row_a["foi_page_url"] == ""
    assert row_a["foi_page_status"] == "success"
    assert row_a["foi_email_email"] == "foi@a.example"
    assert row_a["foi_email_verified"] == "true"
    assert row_a["disclosure_files_total"] == "5"
    assert row_a["disclosure_files_status"] == "success"
    assert row_a["foi_requests_valid"] == "1"

    row_b = rows[1]
    assert row_b["slug"] == "b"
    assert row_b["parent_name"] == ""
    assert row_b["sector"] == ""
    assert row_b["is_commercial"] == ""
    assert row_b["data_vintage"] == ""
    assert row_b["website_url_url"] == ""
    assert row_b["website_url_status"] == ""
    assert row_b["website_url_verified"] == ""
    assert row_b["disclosure_files_total"] == ""
    assert row_b["foi_requests_valid"] == ""


def test_build_record_resolves_parent_id_and_government_department_id_to_uris():
    body = {
        "public_body_id": 1001,
        "name": "Abbey Theatre Amharclann Na Mainistreach",
        "official_website_url": "https://www.abbeytheatre.ie/",
        "category": "public body",
    }
    slug_lookup = {
        1001: "abbey-theatre-amharclann-na-mainistreach",
        1199: "department-of-culture-communications-and-sport",
    }
    cso_lookup = {
        1001: {
            "parent_id": None,
            "parent_name": None,
            "sector": "S13",
            "legal_status": "Non-Commercial Agency under the aegis of Department",
            "government_department_id": 1199,
            "government_department": "Department of Culture, Communications and Sport",
            "nace_code": "R9001", "nace_section": "R", "nace_section_name": "Arts",
            "nace_division": "90", "nace_group": "900", "nace_class": "9001",
            "nace_class_name": "Performing arts", "cro": "414400", "data_vintage": 2025,
            "is_commercial": False, "is_financial": None,
            "aegis": "Department", "legal_entity_type": "Agency",
        }
    }
    warnings = []
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup=cso_lookup, crawl_status_lookup={},
        warnings=warnings,
    )
    assert record["government_department_id"] == f"{BASE_URI}/body/department-of-culture-communications-and-sport"
    assert "parent_id" not in record  # source value was null -> omitted, no warning
    assert warnings == []


def test_build_record_resolves_parent_id_when_present():
    body = {
        "public_body_id": 1500,
        "name": "Child Body",
        "official_website_url": None,
        "category": "public body",
    }
    slug_lookup = {1500: "child-body", 1001: "parent-body"}
    cso_lookup = {
        1500: {
            "parent_id": 1001, "parent_name": "Parent Body",
            "sector": None, "legal_status": None,
            "government_department_id": None, "government_department": None,
            "nace_code": None, "nace_section": None, "nace_section_name": None,
            "nace_division": None, "nace_group": None, "nace_class": None,
            "nace_class_name": None, "cro": None, "data_vintage": None,
            "is_commercial": None, "is_financial": None,
            "aegis": None, "legal_entity_type": None,
        }
    }
    warnings = []
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup=cso_lookup, crawl_status_lookup={},
        warnings=warnings,
    )
    assert record["parent_id"] == f"{BASE_URI}/body/parent-body"
    assert record["parent_name"] == "Parent Body"
    assert "government_department_id" not in record
    assert warnings == []


def test_build_record_omits_unmatched_government_department_id_and_warns():
    body = {
        "public_body_id": 1001,
        "name": "Orphaned Ref Body",
        "official_website_url": None,
        "category": "public body",
    }
    # 8888 is deliberately absent from slug_lookup -- simulates a
    # government_department_id that has no corresponding public_body_id in
    # the 883-body list.
    slug_lookup = {1001: "orphaned-ref-body"}
    cso_lookup = {
        1001: {
            "parent_id": None, "parent_name": None,
            "sector": None, "legal_status": None,
            "government_department_id": 8888, "government_department": "Ghost Department",
            "nace_code": None, "nace_section": None, "nace_section_name": None,
            "nace_division": None, "nace_group": None, "nace_class": None,
            "nace_class_name": None, "cro": None, "data_vintage": None,
            "is_commercial": None, "is_financial": None,
            "aegis": None, "legal_entity_type": None,
        }
    }
    warnings = []
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup=cso_lookup, crawl_status_lookup={},
        warnings=warnings,
    )
    assert "government_department_id" not in record
    assert record["government_department"] == "Ghost Department"  # string field still published
    assert warnings == [(1001, "government_department_id", 8888)]


def test_build_record_warnings_defaults_to_none_is_safe():
    # main() always passes a warnings list, but build_record must not crash
    # if a caller (e.g. a future test) omits it.
    body = {
        "public_body_id": 1001, "name": "No Warnings List Body",
        "official_website_url": None, "category": "public body",
    }
    slug_lookup = {1001: "no-warnings-list-body"}
    record = build_record(
        body, foi_subject_ids=set(), contact_email_lookup={},
        slug_lookup=slug_lookup, cso_lookup={}, crawl_status_lookup={},
    )
    assert "parent_id" not in record

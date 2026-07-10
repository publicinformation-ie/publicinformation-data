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
    record = build_record(body, foi_subject_ids=set(), contact_email_lookup={}, slug_lookup=slug_lookup)
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
    record = build_record(body, foi_subject_ids=set(), contact_email_lookup={}, slug_lookup=slug_lookup)
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
         "foi_scope": f"{BASE_URI}/ns/foi#FullScope", "contact_email": "foi@a.example"},
        {"@id": f"{BASE_URI}/body/b", "@type": "foi:PublicBody", "name": "B",
         "type": "department", "foi_subject": False, "foi_scope": f"{BASE_URI}/ns/foi#NoScope"},
    ]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == ["id", "name", "type", "website", "foi_subject", "foi_scope", "contact_email"]
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

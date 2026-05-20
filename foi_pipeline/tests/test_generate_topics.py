import pytest
import json
from steps.generate_topics.process import process_topics, sort_disclosures, write_public_topics, STEP_NAME


# ---------------------------------------------------------------------------
# STEP_NAME
# ---------------------------------------------------------------------------

def test_step_name():
    assert STEP_NAME == "generate_topics"


# ---------------------------------------------------------------------------
# sort_disclosures
# ---------------------------------------------------------------------------

def test_sort_disclosures_descending_by_date():
    items = [
        {"request_description": "A", "decision_date": "2022-01-01T00:00:00"},
        {"request_description": "B", "decision_date": "2024-06-01T00:00:00"},
        {"request_description": "C", "decision_date": "2023-03-15T00:00:00"},
    ]
    result = sort_disclosures(items)
    dates = [r["decision_date"] for r in result]
    assert dates == [
        "2024-06-01T00:00:00",
        "2023-03-15T00:00:00",
        "2022-01-01T00:00:00",
    ]


def test_sort_disclosures_nulls_last():
    items = [
        {"request_description": "A", "decision_date": None},
        {"request_description": "B", "decision_date": "2023-01-01T00:00:00"},
        {"request_description": "C", "decision_date": None},
    ]
    result = sort_disclosures(items)
    assert result[0]["decision_date"] == "2023-01-01T00:00:00"
    assert result[1]["decision_date"] is None
    assert result[2]["decision_date"] is None


def test_sort_disclosures_all_null():
    items = [
        {"request_description": "A", "decision_date": None},
        {"request_description": "B", "decision_date": None},
    ]
    result = sort_disclosures(items)
    assert len(result) == 2
    assert all(r["decision_date"] is None for r in result)


def test_sort_disclosures_empty():
    assert sort_disclosures([]) == []


def test_sort_disclosures_does_not_mutate_input():
    items = [
        {"request_description": "A", "decision_date": "2022-01-01T00:00:00"},
        {"request_description": "B", "decision_date": "2024-06-01T00:00:00"},
    ]
    original_order = [i["request_description"] for i in items]
    sort_disclosures(items)
    assert [i["request_description"] for i in items] == original_order


# ---------------------------------------------------------------------------
# process_topics — matching logic
# ---------------------------------------------------------------------------

DISCLOSURES = [
    {
        "public_body_id": 1001,
        "name": "Dept A",
        "file_url": "https://x.ie/q1.xlsx",
        "file_type": "xlsx",
        "foi_reference_id": "23/001",
        "decision_date": "2023-03-15T00:00:00",
        "requester_type": "Journalist",
        "decision_status": "Successful",
        "review_status": None,
        "related_request": None,
        "request_description": "All records relating to housing rent policy",
    },
    {
        "public_body_id": 1002,
        "name": "Dept B",
        "file_url": "https://x.ie/q2.xlsx",
        "file_type": "xlsx",
        "foi_reference_id": "23/002",
        "decision_date": "2022-06-01T00:00:00",
        "requester_type": None,
        "decision_status": "Refused",
        "review_status": None,
        "related_request": None,
        "request_description": "PPE procurement during pandemic",
    },
    {
        "public_body_id": 1003,
        "name": "Dept C",
        "file_url": "https://x.ie/q3.xlsx",
        "file_type": "xlsx",
        "foi_reference_id": "23/003",
        "decision_date": None,
        "requester_type": None,
        "decision_status": None,
        "review_status": None,
        "related_request": None,
        "request_description": "School building contracts",
    },
]

TOPICS_CONFIG = [
    {
        "slug": "housing",
        "label": "Housing",
        "keywords": ["housing", "rent", "homeless", "eviction"],
    },
    {
        "slug": "covid-contracts",
        "label": "Covid Contracts",
        "keywords": ["covid", "ppe", "pandemic", "procurement"],
    },
]


def test_process_topics_returns_one_entry_per_topic():
    result = process_topics(TOPICS_CONFIG, DISCLOSURES)
    assert len(result) == 2


def test_process_topics_output_shape():
    result = process_topics(TOPICS_CONFIG, DISCLOSURES)
    housing = next(t for t in result if t["slug"] == "housing")
    assert housing["slug"] == "housing"
    assert housing["label"] == "Housing"
    assert housing["keywords"] == ["housing", "rent", "homeless", "eviction"]
    assert isinstance(housing["match_count"], int)
    assert isinstance(housing["disclosures"], list)


def test_process_topics_keyword_match_case_insensitive():
    disclosures = [
        {**DISCLOSURES[0], "request_description": "All records relating to HOUSING rent policy"},
    ]
    result = process_topics([TOPICS_CONFIG[0]], disclosures)
    assert result[0]["match_count"] == 1


def test_process_topics_keyword_substring_match():
    disclosures = [
        {**DISCLOSURES[0], "request_description": "homelessness rates in Dublin"},
    ]
    result = process_topics([TOPICS_CONFIG[0]], disclosures)
    assert result[0]["match_count"] == 1


def test_process_topics_or_logic_any_keyword_matches():
    disclosures = [
        {**DISCLOSURES[0], "request_description": "eviction notices issued"},
    ]
    result = process_topics([TOPICS_CONFIG[0]], disclosures)
    assert result[0]["match_count"] == 1


def test_process_topics_no_match_gives_empty_disclosures():
    disclosures = [
        {**DISCLOSURES[2]},  # "School building contracts" — no housing/covid keywords
    ]
    result = process_topics([TOPICS_CONFIG[0]], disclosures)
    assert result[0]["match_count"] == 0
    assert result[0]["disclosures"] == []


def test_process_topics_match_count_equals_disclosures_length():
    result = process_topics(TOPICS_CONFIG, DISCLOSURES)
    for topic in result:
        assert topic["match_count"] == len(topic["disclosures"])


def test_process_topics_disclosures_sorted_descending():
    disclosures = [
        {**DISCLOSURES[0], "decision_date": "2021-01-01T00:00:00"},
        {**DISCLOSURES[1], "decision_date": "2023-06-01T00:00:00", "request_description": "pandemic ppe"},
    ]
    result = process_topics([TOPICS_CONFIG[1]], disclosures)
    covid_topic = result[0]
    assert covid_topic["match_count"] == 1  # only the pandemic ppe record matches
    assert covid_topic["disclosures"][0]["decision_date"] == "2023-06-01T00:00:00"


def test_process_topics_null_request_description_does_not_match():
    disclosures = [
        {**DISCLOSURES[0], "request_description": None},
    ]
    result = process_topics([TOPICS_CONFIG[0]], disclosures)
    assert result[0]["match_count"] == 0


def test_process_topics_disclosures_are_embedded_fully():
    result = process_topics([TOPICS_CONFIG[0]], [DISCLOSURES[0]])
    embedded = result[0]["disclosures"][0]
    assert embedded["public_body_id"] == 1001
    assert embedded["foi_reference_id"] == "23/001"
    assert embedded["decision_status"] == "Successful"


def test_process_topics_empty_config_returns_empty():
    result = process_topics([], DISCLOSURES)
    assert result == []


def test_process_topics_empty_disclosures_all_zero():
    result = process_topics(TOPICS_CONFIG, [])
    for topic in result:
        assert topic["match_count"] == 0
        assert topic["disclosures"] == []


# ---------------------------------------------------------------------------
# write_public_topics
# ---------------------------------------------------------------------------


def test_write_public_topics_creates_file(tmp_path):
    results = [{"slug": "housing", "label": "Housing", "keywords": [], "match_count": 0, "disclosures": []}]
    write_public_topics(results, tmp_path)
    assert (tmp_path / "public" / "topics.json").exists()


def test_write_public_topics_returns_path(tmp_path):
    path = write_public_topics([], tmp_path)
    assert path == tmp_path / "public" / "topics.json"


def test_write_public_topics_content(tmp_path):
    results = [
        {"slug": "housing", "label": "Housing", "keywords": ["rent"], "match_count": 2, "disclosures": []},
    ]
    write_public_topics(results, tmp_path)
    data = json.loads((tmp_path / "public" / "topics.json").read_text())
    assert len(data) == 1
    assert data[0]["slug"] == "housing"
    assert data[0]["match_count"] == 2


def test_write_public_topics_creates_public_dir(tmp_path):
    write_public_topics([], tmp_path)
    assert (tmp_path / "public").is_dir()


def test_write_public_topics_overwrites_existing(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "topics.json").write_text('[{"slug": "old"}]')
    results = [{"slug": "housing", "label": "Housing", "keywords": [], "match_count": 0, "disclosures": []}]
    write_public_topics(results, tmp_path)
    data = json.loads((tmp_path / "public" / "topics.json").read_text())
    assert data[0]["slug"] == "housing"

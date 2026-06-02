import pytest
import json
from steps.generate_topics.process import process_topics, sort_disclosures, write_public_topics, STEP_NAME, _keyword_matches


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


def test_process_topics_keyword_word_boundary_match():
    # "homeless" as a whole word should match (not substring of "homelessness")
    disclosures = [
        {**DISCLOSURES[0], "request_description": "homeless people in Dublin"},
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


# ---------------------------------------------------------------------------
# _keyword_matches - Word Boundary Matching Tests
# ---------------------------------------------------------------------------


class TestKeywordMatches:
    """Tests for the _keyword_matches function with word boundary support."""

    # --- IT keyword (case-sensitive) ---

    def test_it_matches_standalone_uppercase(self):
        """IT should match standalone uppercase IT."""
        assert _keyword_matches("This is an IT request", "IT") is True
        assert _keyword_matches("IT department", "IT") is True
        assert _keyword_matches("The IT team", "IT") is True

    def test_it_does_not_match_lowercase(self):
        """IT should NOT match lowercase 'it'."""
        assert _keyword_matches("this is an it request", "IT") is False
        assert _keyword_matches("The it department", "IT") is False

    def test_it_does_not_match_within_words(self):
        """IT should NOT match within other words."""
        assert _keyword_matches("visit the site", "IT") is False
        assert _keyword_matches("audit report", "IT") is False
        assert _keyword_matches("REPLIT the data", "IT") is False
        assert _keyword_matches("ITINERANT worker", "IT") is False
        assert _keyword_matches("permit required", "IT") is False
        assert _keyword_matches("split the difference", "IT") is False

    def test_it_matches_with_punctuation(self):
        """IT should match with surrounding punctuation."""
        assert _keyword_matches("IT, the department", "IT") is True
        assert _keyword_matches("The IT. Full stop", "IT") is True
        assert _keyword_matches("(IT)", "IT") is True
        assert _keyword_matches("IT:", "IT") is True

    # --- Other keywords (case-insensitive with word boundaries) ---

    def test_housing_matches_case_insensitive(self):
        """Non-IT keywords should be case-insensitive."""
        assert _keyword_matches("Housing policy", "housing") is True
        assert _keyword_matches("HOUSING crisis", "housing") is True
        assert _keyword_matches("This is about housing", "housing") is True

    def test_housing_does_not_match_within_words(self):
        """housing should NOT match within other words."""
        assert _keyword_matches("housings are here", "housing") is False
        assert _keyword_matches("ahousingb", "housing") is False

    def test_rent_matches_case_insensitive(self):
        """rent should match case-insensitively."""
        assert _keyword_matches("Rent prices", "rent") is True
        assert _keyword_matches("rent", "rent") is True

    def test_software_matches(self):
        """software should match with word boundaries."""
        assert _keyword_matches("Software license", "software") is True
        assert _keyword_matches("the software", "software") is True
        assert _keyword_matches("SOFTWARE", "software") is True

    def test_software_does_not_match_within_words(self):
        """software should NOT match within other words."""
        assert _keyword_matches("softwareengineering", "software") is False

    def test_empty_text_never_matches(self):
        """Empty or None text should never match."""
        assert _keyword_matches("", "housing") is False
        assert _keyword_matches(None, "housing") is False

    def test_special_chars_in_keywords_are_escaped(self):
        """Keywords with regex special chars should be escaped and not cause errors."""
        # The important thing is that regex special chars don't cause regex compilation errors
        # They may or may not match depending on word boundary behavior with non-word chars
        try:
            # These should not raise re.error (regex compilation error)
            _keyword_matches("test + pattern", "test + pattern")
            _keyword_matches("test * pattern", "test * pattern")
            _keyword_matches("test ? pattern", "test ? pattern")
            _keyword_matches("cost is $100", "$100")
            _keyword_matches("100% complete", "100%")
        except re.error as e:
            pytest.fail(f"Regex special characters not properly escaped: {e}")


class TestProcessTopicsWordBoundaries:
    """Integration tests for process_topics with word boundary matching."""

    def test_it_topic_excludes_lowercase_it(self):
        """IT topic should not match records with lowercase 'it'."""
        disclosures = [
            {
                "public_body_id": 1001,
                "name": "Dept A",
                "file_url": "https://x.ie/q1.xlsx",
                "file_type": "xlsx",
                "foi_reference_id": "23/001",
                "decision_date": None,
                "requester_type": None,
                "decision_status": None,
                "review_status": None,
                "related_request": None,
                "request_description": "this is an it request",  # lowercase it
            },
            {
                **DISCLOSURES[0],
                "request_description": "IT department records",  # uppercase IT
            },
        ]
        topics_config = [{"slug": "it-spend", "label": "IT Spending", "keywords": ["IT", "software"]}]
        result = process_topics(topics_config, disclosures)
        # Only the uppercase IT should match
        assert result[0]["match_count"] == 1
        assert result[0]["disclosures"][0]["request_description"] == "IT department records"

    def test_it_topic_excludes_it_within_words(self):
        """IT topic should not match 'it' within other words."""
        disclosures = [
            {
                "public_body_id": 1001,
                "name": "Dept A",
                "file_url": "https://x.ie/q1.xlsx",
                "file_type": "xlsx",
                "foi_reference_id": "23/001",
                "decision_date": None,
                "requester_type": None,
                "decision_status": None,
                "review_status": None,
                "related_request": None,
                "request_description": "visit the website",  # 'it' within 'visit'
            },
            {
                **DISCLOSURES[0],
                "request_description": "IT software request",
            },
        ]
        topics_config = [{"slug": "it-spend", "label": "IT Spending", "keywords": ["IT", "software"]}]
        result = process_topics(topics_config, disclosures)
        # Only the IT software request should match (both IT and software)
        assert result[0]["match_count"] == 1

    def test_housing_topic_word_boundaries(self):
        """Housing topic should use word boundary matching."""
        disclosures = [
            {
                "public_body_id": 1001,
                "name": "Dept A",
                "file_url": "https://x.ie/q1.xlsx",
                "file_type": "xlsx",
                "foi_reference_id": "23/001",
                "decision_date": None,
                "requester_type": None,
                "decision_status": None,
                "review_status": None,
                "related_request": None,
                "request_description": "housings are here",  # should NOT match
            },
            {
                **DISCLOSURES[0],
                "request_description": "Housing policy documents",  # should match
            },
        ]
        topics_config = [{"slug": "housing", "label": "Housing", "keywords": ["housing"]}]
        result = process_topics(topics_config, disclosures)
        # Only Housing policy should match
        assert result[0]["match_count"] == 1
        assert result[0]["disclosures"][0]["request_description"] == "Housing policy documents"


import sys as _sys
import json as _json
from scripts.file_utils import read_json as _read_json, write_json as _write_json
import steps.generate_topics.process as _proc


def test_public_body_scoped_only_generates_topics_for_target(tmp_path, monkeypatch):
    # Build fake pipeline directory structure
    step_dir = tmp_path / "steps" / "generate_topics"
    step_dir.mkdir(parents=True)
    canonicalize_dir = tmp_path / "steps" / "extract_disclosures_canonicalize"
    canonicalize_dir.mkdir(parents=True)
    (tmp_path / "public").mkdir(parents=True)

    # Topics config
    (step_dir / "topics-config.json").write_text(_json.dumps([
        {"slug": "housing", "label": "Housing", "keywords": ["housing"]}
    ]))

    # Canonicalize output: records for bodies 1001 and 1002
    _write_json(canonicalize_dir / "output.json", {"results": [
        {"public_body_id": 1001, "request_description": "housing request", "foi_reference_id": "A",
         "decision_date": "2024-01-01"},
        {"public_body_id": 1002, "request_description": "housing budget", "foi_reference_id": "B",
         "decision_date": "2024-02-01"},
    ]})

    out = tmp_path / "output.json"
    monkeypatch.setattr(_proc, "__file__", str(step_dir / "process.py"))
    _sys.argv = ["process.py", "--input", "unused", "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    # Only body 1002's record should contribute to topic matching
    for topic in results:
        for disc in topic.get("disclosures", []):
            assert disc["public_body_id"] == 1002, "Only 1002's disclosures should appear"
